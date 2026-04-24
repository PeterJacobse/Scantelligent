import sys, os, time
import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        scantelligent = kwargs.pop("parent", None)
        if scantelligent == None: scantelligent = kwargs.pop("scantelligent", None)
        super().__init__(*args, **kwargs)
        
        # Set up the GUI. See below
        try: self.prepare_gui(scantelligent.gui)
        except: self.gui_not_found_error()
        
        # Set up the required hardware connections
        self.connect_hardware("nanonis")
        self.sct = scantelligent

    def prepare_gui(self, gui) -> None:
        self.setup_combobox(gui = gui, items = ["scan down / map up", "scan up / map down"])
        self.setup_line_edits(gui = gui)

    def run(self):
        self.logprint(f"Initializing the experiment", message_type = "message")
        try:
            # Load methods and data; initialize
            nn = self.nanonis
            self.sct.toggle_view("nanonis") # Changing the active view to Nanonis
            timeout_s = 10000

            (self.start_parameters, error) = nn.initialize(verbose = False)
            [bias, feedback, grid, speeds, scan_metadata, tip_status] = [self.start_parameters.get(parameter_dict)
                                                                         for parameter_dict in ["bias", "feedback", "grid", "speeds", "scan_metadata", "tip_status"]]
            self.frame = {key: value for key, value in grid.items() if key in ["offset (nm)", "scan_range (nm)", "angle (deg)"]}
            self.V_start = bias.get("V_nanonis (V)")
            [self.x_start, self.y_start] = [tip_status.get(dim) for dim in ["x (nm)", "y (nm)"]]
            [self.v_fwd_nm_per_s, self.v_bwd_nm_per_s] = [speeds.get(parameter) for parameter in ["v_fwd (nm/s)", "v_bwd (nm/s)"]]
            [self.I_feedback_pA, self.p_gain_pm] = [feedback.get(parameter) for parameter in ["I_fb (pA)", "p_gain (pm)"]]

            # Calculate information
            signal_dict = scan_metadata.get("signal_dict")
            feedback_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Z (m)"]]
            feedback_channel_indices = [index for index in feedback_channel_indices if index is not None]
            constant_height_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Lockin Demod 1 X (A)", "Lockin Demod 1 Y (A)", "Current (A)"]]
            constant_height_channel_indices = [index for index in constant_height_channel_indices if index is not None]

            nn.lockin_update({"mod1": {"on": False}, "mod2": {"on": False}, "mla_mod1": {"on": False}}) # Make sure the lockins are initially turned off
            channels_dict = {i: name for i, name in enumerate(["x (nm)", "y (nm)", "z (nm)", "I (pA)"])} | {"dict_name": "channels"}
            self.parameters.emit(channels_dict) # This triggers the GUI to start graphing data
            nn.scan_metadata_update({"channel_indices": feedback_channel_indices}) # Make sure the correct channel is being recorded
                        
            
            
            self.logprint(f"Starting the experiment", message_type = "success")
            
            # Setting the scan frame in the top right corner
            (scan_area, error) = nn.frame_update({"offset (nm)": [500, 500], "scan_range (nm)": [100, 100], "angle (deg)": 0})
            nn.scan_action({"action": "start", "direction": "down"})
            self.sct.set_view_range("frame")
            
            # Loop to check scan progress
            t_start = time.time()
            t_elapsed = 0
            while t_elapsed < timeout_s:
                t_elapsed = time.time() - t_start
                scan_finished = self.get_scan_updates(channel = feedback_channel_indices[0])
                if scan_finished or self.abort_requested: break

            self.sct.set_view_range("full")
            time.sleep(1)
            self.logprint("Moving the frame to the bottom left corner", message_type = "warning")
            for iteration, position in enumerate(np.linspace(500, 0, 20)):
                nn.frame_update({"offset (nm)": [500, position]}, verbose = False)
                time.sleep(.05)            
            for iteration, angle in enumerate(np.linspace(0, 5 * np.pi, 80)):
                nn.frame_update({"angle (deg)": 2 * np.rad2deg(angle), "offset (nm)": [500 * np.cos(angle), 500 * np.sin(angle)], "scan_range (nm)": [100 + 80 * np.sin(angle), 100 - 80 * np.sin(angle)]}, verbose = False)
                time.sleep(.05)
            for iteration, position in enumerate(np.linspace(0, -500, 20)):
                nn.frame_update({"angle (deg)": 0, "offset (nm)": [-500, position]}, verbose = False)
                time.sleep(.05)
            
            (poke_area, error) = nn.frame_update()            
            time.sleep(1)
            self.sct.set_view_range("frame")
            self.abort_requested = False
            nn.scan_action({"action": "start", "direction": "down"})
            
            # Loop to check scan progress
            t_start = time.time()
            t_elapsed = 0
            while t_elapsed < timeout_s:
                t_elapsed = time.time() - t_start
                scan_finished = self.get_scan_updates(channel = feedback_channel_indices[0])
                if scan_finished or self.abort_requested: break
            
            self.logprint("This looks like a great area to condition the tip!", message_type = "message")
            [width_nm, height_nm] = poke_area.get("scan_range (nm)")
            [x_nm, y_nm] = poke_area.get("offset (nm)")
            
            
            
            self.logprint("Performing 5 tip pokes in sequence in this area", message_type = "message")
            # Create a random number generator
            rng = np.random.default_rng()
            poke_locations = rng.uniform(low = [x_nm - .5 * width_nm, y_nm - .5 * height_nm], high = [x_nm + .5 * width_nm, y_nm + .5 * height_nm], size = (5, 2))
            
            for iteration, location in enumerate(poke_locations):
                nn.tip_update({"x (nm)": location[0], "y (nm)": location[0]})
                nn.tip_update(verbose = False)
                nn.shape_tip()
            
            self.logprint("I am done poking the tip. Let's move back to the top right corner and continue scanning there", message_type = "message")            
            self.sct.set_view_range("full")
            
            for iteration, position in enumerate(np.linspace(-500, 0, 20)):
                nn.frame_update({"offset (nm)": [-500, position]}, verbose = False)
                time.sleep(.05)            
            for iteration, angle in enumerate(np.linspace(np.pi, 6 * np.pi, 80)):
                nn.frame_update({"angle (deg)": - np.rad2deg(angle), "offset (nm)": [500 * np.cos(angle), 500 * np.sin(angle)], "scan_range (nm)": [100 + 80 * np.sin(angle), 100 + 80 * np.sin(angle)]}, verbose = False)
                time.sleep(.05)
            for iteration, position in enumerate(np.linspace(0, 500, 20)):
                nn.frame_update({"angle (deg)": 0, "offset (nm)": [500, position]}, verbose = False)
                time.sleep(.05)
            
            nn.scan_action({"action": "start", "direction": "down"})
            
            # Loop to check scan progress
            t_start = time.time()
            t_elapsed = 0
            while t_elapsed < timeout_s:
                t_elapsed = time.time() - t_start
                scan_finished = self.get_scan_updates(channel = feedback_channel_indices[0])
                if scan_finished or self.abort_requested: break



        except Exception as e:
            self.logprint(f"{e}", message_type = "error")
            self.abort_requested = True
        finally:
            self.cleanup()
            self.experiment_finished()



    def get_scan_updates(self, channel) -> bool:        
        (tip_status, error) = self.nanonis.tip_update(verbose = False)
        [x_nm, y_nm, z_nm, I_pA] = [tip_status.get(parameter) for parameter in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
        self.data_array.emit(np.array([[x_nm, y_nm, z_nm, I_pA]]))
        (scan_image, error) = self.nanonis.scan_update(channel = channel, verbose = False)
        nan_mask = np.isnan(scan_image)
        scan_finished = not bool(np.any(nan_mask))
        self.check_abort_request()
        return scan_finished

    def cleanup(self) -> None:
        nn = self.nanonis
        
        try:
            nn.scan_action({"action": "stop"})
            nn.frame_update(self.frame)
            nn.tip_update({"z_rel (nm)": 1})
            nn.lockin_update({"mod1": {"on": False}, "mod2": {"on": False}, "mla_mod1": {"on": False}}) # Switch lockin off for feedback scan
            nn.bias_update({"V_nanonis (V)": self.V_start})
            nn.feedback_update({"I_fb (pA)": self.I_feedback_pA, "p_gain (pm)": self.p_gain_pm})
            nn.speeds_update({"v_fwd (nm/s)": self.v_fwd_nm_per_s, "v_bwd (nm/s)": self.v_bwd_nm_per_s})
            nn.tip_update({"feedback": True, "x (nm)": self.x_start, "y (nm)": self.y_start})
            nn.tip_update(verbose = False)
            self.sct.set_view_range("full")
        except:
            pass
        return

