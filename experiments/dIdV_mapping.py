import sys, os, time
import numpy as np

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
        self.setup_line_edits(gui = gui, tooltips = ["V_start", "V_step", "V_end", "t_per_pixel"],
                              values = [-2, 100, 2, 1], digits = [2, 0, 2, 2], limits = [[-10, 10], [0, 10000], [-10, 10], [0, 1000]], units = ["V", "mV", "V", "ms"])

    def run(self):
        # Load methods and data; initialize
        nn = self.nanonis
        nhw = nn.nanonis_hardware
        gui_parameters = self.read_parameters_from_gui()
        direction_str = gui_parameters["direction_combobox"]
        [V_begin, V_step, V_end] = [gui_parameters["line_edits"][index] for index in range(3)]
        V_step /= 1000
        timeout_s = 36000 # 10 hours
        
        map_direction = "up" if direction_str == "scan down / map up" else "down"
        scan_direction = "down" if direction_str == "scan down / map up" else "up"
        if V_end < V_begin: V_step = -V_step
        V_list = np.append(np.arange(V_begin, V_end, V_step), V_end)
        n_steps = len(V_list)
        
        (frame, error) = nn.frame_update()
        (grid, error) = nn.grid_update()
        self.V_feedback = nn.bias_update()
        (scan_metadata, error) = nn.scan_metadata_update()
        signal_dict = scan_metadata["signal_dict"]
        feedback_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Z (m)"]]
        feedback_channel_indices = [index for index in feedback_channel_indices if index is not None]
        constant_height_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Lockin Demod 1 X (A)", "Lockin Demod 1 Y (A)", "Current (A)"]]
        constant_height_channel_indices = [index for index in constant_height_channel_indices if index is not None]

        self.logprint(f"Starting a dI/dV mapping series from V = {V_begin} V to V = {V_end} V in steps of dV = {V_step} mV.", message_type = "success")
        self.sct.toggle_view("nanonis")



        for scan_number, voltage in enumerate(V_list):
            if self.abort_requested: break
            self.logprint(f"Iteration {scan_number + 1} of {n_steps}", message_type = "message")
            self.logprint(f"Switching the lockin off, lifting the tip by 1 nm and restoring the bias to V = {self.V_feedback} V", message_type = "message")
            
            nn.tip_update({"z_rel (nm)": 1})
            nn.lockin_update({"mod1": {"on": False}, "mod2": {"on": False}, "mla_mod1": {"on": False}}) # Switch lockin off for feedback scan
            nn.bias_update({"V_nanonis (V)": self.V_feedback})
            
            self.logprint(f"Switching to feedback (topographic STM) mode and starting a scan in the {scan_direction} direction", message_type = "message")
            nn.scan_metadata_update({"channel_indices": feedback_channel_indices})
            nn.tip_update({"feedback": True})
            time.sleep(1)
            
            nn.scan_action({"action": "start", "direction": scan_direction})
            
            # Loop to check scan progress
            t_start = time.time()
            t_elapsed = 0
            
            while t_elapsed < timeout_s:
                t_elapsed = time.time()
                scan_finished = self.get_scan_updates(channel = feedback_channel_indices[0])
                if scan_finished or self.abort_requested: break
                time.sleep(.5)
            
            if self.abort_requested: break
            time.sleep(1)
            self.logprint("Feedback scan completed", message_type = "message")
            
            self.logprint(f"Switching to constant height mode and switching the lockin on. Setting the bias to V = {voltage} V", message_type = "message")
            nn.tip_update({"feedback": False})
            nn.bias_update({"V_nanonis (V)": voltage})
            nn.lockin_update({"mod1": {"on": True}})
            nn.scan_metadata_update({"channel_indices": constant_height_channel_indices})
            
            nn.scan_action({"action": "start", "direction": map_direction})
            
            # Loop to check scan progress
            t_start = time.time()
            t_elapsed = 0
            
            while t_elapsed < timeout_s:
                t_elapsed = time.time()
                scan_finished = self.get_scan_updates(channel = constant_height_channel_indices[0])
                if scan_finished or self.abort_requested: break
                time.sleep(.5)
            
            self.exp_progress.emit(int(100 * scan_number / n_steps)) # Emit experiment progress
            if self.abort_requested: break
            time.sleep(1)
            self.logprint("Constant height scan completed", message_type = "message")



        self.cleanup()
        self.experiment_finished()

    def cleanup(self):
        nn = self.nanonis
        nn.scan_action({"action": "stop"})
        nn.tip_update({"z_rel (nm)": 1})
        nn.lockin_update({"mod1": {"on": False}, "mod2": {"on": False}, "mla_mod1": {"on": False}}) # Switch lockin off for feedback scan
        nn.bias_update({"V_nanonis (V)": self.V_feedback})
        nn.tip_update({"feedback": True})

    def get_scan_updates(self, channel) -> bool | bool:
        (frame, error) = self.nanonis.frame_update(verbose = False)
        (tip_status, error) = self.nanonis.tip_update(verbose = False)
        (scan_image, error) = self.nanonis.scan_update(channel = channel, verbose = False)
        nan_mask = np.isnan(scan_image)
        scan_finished = not np.any(nan_mask)
        self.check_abort_request()
        return scan_finished

