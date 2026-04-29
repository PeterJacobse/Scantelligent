import sys, os, time
import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        gui_setup = {
            "combobox": {"items": ["scan down / map up", "scan up / map down"]},
            "line_edits": {"tooltips": ["V_start", "V_step", "V_end", "integration time per pixel\n(forward direction)\nEnsure this is at least twice the modulation time constant", "tip speed (backward direction)",
                                        "max current", "V_reference\n(use this voltage for calibrating the height)\nIf set to zero, the begin and end voltages are used for calibration"],
                           "values": [-2, 100, 2, 1, 30, 2000, 0], "units": ["V", "mV", "V", "ms", "nm/s", "pA", "V"],
                           "digits": [2, 0, 2, 2, 2, 1, 2], "limits": [[-10, 10], [0, 10000], [-10, 10], [0, 1000], [.01, 10000], [.01, 10000], [-10, 10]]},
            "buttons": {"states": [
                [{"name": "off", "color": "#101010", "tooltip": "Lockin 1 = OFF during daq"},
                 {"name": "on", "color": "#808080", "tooltip": "Lockin 1 = ON during daq"}]

                ]}
                     }

        self.prepare_gui(gui_setup)
        self.connect_hardware("nanonis") # Set up the required hardware connections

    @BaseExperiment.experiment_handler
    def run(self):
        # Load methods and data; initialize
        nn = self.nanonis
        self.sct.toggle_view("nanonis") # Changing the active view to Nanonis
        timeout_s = 260000 # 10 hours
        
        # Load methods and data; initialize
        nn = self.nanonis
        gui_parameters = self.read_parameters_from_gui()
        direction_str = gui_parameters["direction_combobox"] # Reading user parameters
        [V_begin, V_step, V_end, t_per_pixel_ms, v_bwd_nm_per_s, I_max, V_cal] = [gui_parameters["line_edits"][index] for index in range(7)]
        V_step /= 1000 # Convert from mV to V

        map_direction = "up" if direction_str == "scan down / map up" else "down"
        scan_direction = "down" if direction_str == "scan down / map up" else "up"
        start_corner = "top left" if scan_direction == "up" else "bottom left" # The start corner is the corner where the tip is before each map. Here the tip height is calibrated
        if V_end < V_begin: V_step = -V_step # Adjust the sign of the step if going down
        V_list = np.append(np.arange(V_begin, V_end, V_step), V_end)
        n_steps = len(V_list)

        # Information from Nanonis
        nanonis_parameters = self.start_parameters.get("nanonis")
        [bias, feedback, grid, speeds, scan_metadata, tip_status] = [nanonis_parameters.get(parameter_dict) for parameter_dict in ["bias", "feedback", "grid", "speeds", "scan_metadata", "tip_status"]]
        self.V_start = bias.get("V_nanonis (V)")
        [self.x_start, self.y_start] = [tip_status.get(dim) for dim in ["x (nm)", "y (nm)"]]
        [self.v_fwd_nm_per_s, self.v_bwd_nm_per_s] = [speeds.get(parameter) for parameter in ["v_fwd (nm/s)", "v_bwd (nm/s)"]]
        [self.I_feedback_pA, self.p_gain_pm] = [feedback.get(parameter) for parameter in ["I_fb (pA)", "p_gain (pm)"]]

        # Calculate information
        self.corner_before_mapping = list(grid.get("bottom_left_corner (nm)")) if start_corner == "bottom left" else list(grid.get("top_left_corner (nm)"))
        self.corner_before_scanning = list(grid.get("top_left_corner (nm)")) if start_corner == "bottom left" else list(grid.get("bottom_left_corner (nm)"))
        t_per_line_s = t_per_pixel_ms * grid.get("pixels") / 1000 # Calculate the time per line

        signal_dict = scan_metadata.get("signal_dict")
        feedback_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Z (m)"]]
        feedback_channel_indices = [index for index in feedback_channel_indices if index is not None]
        constant_height_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Lockin Demod 1 X (A)", "Lockin Demod 1 Y (A)", "Current (A)"]]
        constant_height_channel_indices = [index for index in constant_height_channel_indices if index is not None]
        
        nn.lockin_update({"mod1": {"on": False}, "mod2": {"on": False}, "mla_mod1": {"on": False}}) # Make sure the lockins are initially turned off
        nn.scan_metadata_update({"channel_indices": feedback_channel_indices}) # Make sure the correct channel is being recorded
        self.sct.set_view_range("frame")



        # Tip height calibration routine
        tip_height_calibration = True
        z_above_reference = 0

        if tip_height_calibration:
            self.logprint("Making feedback scans at the bias extremes to determine the highest apparent point in the scan window", message_type = "message")

            z_at_highest_feature = []
            relative_z_at_highest_feature = []
            for scan_number, voltage in enumerate([V_begin, V_end]):                
                nn.tip_update({"z_rel (nm)": 1})
                nn.bias_update({"V_nanonis (V)": voltage})
                nn.tip_update({"feedback": True, "x (nm)": self.corner_before_scanning[0], "y (nm)": self.corner_before_scanning[1]}, wait = True)
                time.sleep(3)
                nn.scan_action({"action": "start", "direction": scan_direction})
                self.monitor_scan(channel = feedback_channel_indices[0])
                (z_image, error) = nn.scan_update(channel = feedback_channel_indices[0]) # Retrieve the scan image created at V = V_begin

                # Image analysis
                image_data = nn.find_scan_image_minmax(z_image * 1E9, grid) # Convert height to nm
                [x_max_nm, y_max_nm] = [image_data["maximum"].get(parameter) for parameter in ["x (nm)", "y (nm)"]]

                self.logprint(f"Moving the tip to the highest apparent point of the scan at ({x_max_nm:.4f}, {y_max_nm:.4f}) nm and 500 pm jitter to find the height", message_type = "message")
                nn.tip_update({"x (nm)": x_max_nm, "y (nm)": y_max_nm}, wait = True)
                nn.feedback_update({"I_fb (pA)": I_max, "p_gain (pm)": 1}) # Reducing the proportional gain to a very low value to stabilize the tip height
                time.sleep(1)
                                
                (tip_data, error) = nn.jitter_tip({"iterations": 32, "radius": .5})
                z_feature = tip_data.get("z_avg (nm)")
                z_at_highest_feature.append(z_feature)
                
                nn.feedback_update({"I_fb (pA)": self.I_feedback_pA, "p_gain (pm)": self.p_gain_pm})
                time.sleep(2)



                # Now collect a reference height at the corner under normal feedback conditions
                self.logprint(f"Measuring a reference tip height at the {start_corner} corner at the feedback voltage of {self.V_start:.4f} V using a 500 pm jitter", message_type = "message")
                nn.bias_update({"V_nanonis (V)": self.V_start})
                nn.tip_update({"x (nm)": self.corner_before_mapping[0], "y (nm)": self.corner_before_mapping[1]}, wait = True)
                nn.feedback_update({"p_gain (pm)": 1}) # Reducing the proportional gain to a very low value to stabilize the tip height
                time.sleep(1)

                (tip_data, error) = nn.jitter_tip({"iterations": 32, "radius": .5})
                z_corner = tip_data.get("z_avg (nm)")
                z_relative = z_feature - z_corner
                relative_z_at_highest_feature.append(z_relative)

                nn.feedback_update({"p_gain (pm)": self.p_gain_pm})

                self.logprint(f"The measured tip height on the highest feature (z = {z_at_highest_feature[0]:.4f} nm while drawing I_max = {I_max:.4f} pA at V = {voltage:.4f} V)\n" +
                        f"is {z_relative:.4f} nm higher than the tip height in the corner (z = {z_corner:.4f} nm while drawing I = {self.I_feedback_pA:.4f} pA at V = {self.V_start:.4f}) V", message_type = "message")
                time.sleep(2)
            
            if not self.abort_requested:
                # After iterating over the min and max bias values, determine what ultimately is the height of the plane relative to the reference point
                z_above_reference = np.max(relative_z_at_highest_feature)
                self.logprint(f"Relative height determined to be f{z_above_reference}", message_type = "message")



        # Main experiment
        if not self.abort_requested: self.logprint(f"Now starting the dI/dV mapping series from V = {V_begin:.4f} V to V = {V_end:.4f} V in steps of dV = {V_step:.4f} mV.", message_type = "success")        
        for scan_number, voltage in enumerate(V_list):
            if self.abort_requested: break
            self.exp_progress.emit(int(100 * scan_number / n_steps)) # Emit experiment progress
            self.logprint(f"Iteration {scan_number + 1} of {n_steps}", message_type = "message")
            
            self.logprint(f"Switching the lockin off, lifting the tip by 1 nm, restoring the scan speeds and restoring the bias to V = {self.V_start:.4f} V", message_type = "message")
            
            nn.tip_update({"z_rel (nm)": 1})
            nn.lockin_update({"mod1": {"on": False}, "mod2": {"on": False}, "mla_mod1": {"on": False}})
            nn.speeds_update({"v_fwd (nm/s)": self.v_fwd_nm_per_s, "v_bwd (nm/s)": self.v_bwd_nm_per_s})
            nn.bias_update({"V_nanonis (V)": self.V_start})
            nn.feedback_update({"I_fb (pA)": self.I_feedback_pA})

            self.logprint(f"Switching to feedback (topographic STM) mode and starting a scan in the {scan_direction} direction", message_type = "message")
            nn.scan_metadata_update({"channel_indices": feedback_channel_indices})
            nn.tip_update({"feedback": True, "x (nm)": self.corner_before_scanning[0], "y (nm)": self.corner_before_scanning[1]}, wait = True)
            time.sleep(3)
            
            nn.scan_action({"action": "start", "direction": scan_direction})
            self.monitor_scan(channel = feedback_channel_indices[0])



            self.logprint("Measuring the height at the reference point", message_type = "message")
            nn.tip_update({"x (nm)": self.corner_before_mapping[0], "y (nm)": self.corner_before_mapping[1]}, wait = True)
            nn.feedback_update({"I_fb (pA)": self.I_feedback_pA, "p_gain (pm)": 1}) # Reducing the proportional gain to a very low value to stabilize the tip height
            time.sleep(1)

            (tip_data, error) = nn.jitter_tip({"iterations": 32, "radius": .5})
            z_corner = tip_data.get("z_avg (nm)")

            nn.feedback_update({"p_gain (pm)": self.p_gain_pm})
            self.logprint(f"Now going into constant height mode. Lifting the tip by {z_above_reference:.4f} nm, switching the lockin on and setting the bias to V = {voltage:.4f} V", message_type = "message")
            nn.tip_update({"z (nm)": z_corner + z_above_reference})
            nn.bias_update({"V_nanonis (V)": voltage})
            nn.lockin_update({"mod1": {"on": True}})
            nn.speeds_update({"t_fwd (s)": t_per_line_s, "v_bwd (nm/s)": v_bwd_nm_per_s})
            nn.scan_metadata_update({"channel_indices": constant_height_channel_indices})
            time.sleep(3)
            
            nn.scan_action({"action": "start", "direction": map_direction})
            self.monitor_scan(channel = constant_height_channel_indices[0])

            if self.abort_requested: break
            self.logprint("Constant height scan completed", message_type = "success")

