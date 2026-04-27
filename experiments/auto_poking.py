import sys, os, time
import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        try: self.prepare_gui(self.sct.gui) # Set up the GUI. See below
        except: self.gui_not_found_error()

        self.connect_hardware("nanonis") # Set up the required hardware connections

    def prepare_gui(self, gui) -> None:
        self.setup_combobox(gui = gui, items = ["scan down / map up", "scan up / map down"])
        self.setup_line_edits(gui = gui)

    @BaseExperiment.experiment_handler
    def run(self):
        nn = self.nanonis # Using nn as an alias for self.nanonis        
        self.sct.toggle_view("nanonis") # Changing the active view to Nanonis

        # Calculate information
        nanonis_parameters = self.start_parameters.get("nanonis")
        [bias, feedback, grid, speeds, scan_metadata, tip_status, tip_shaper] = [nanonis_parameters.get(parameter_dict, None) for parameter_dict in ["bias", "feedback", "grid", "speeds", "scan_metadata", "tip_status", "tip_shaper"]]
        if not isinstance(tip_shaper, dict): raise Exception("Error. Could not obtain the parameters from the tip shaper module. Please open the module in Nanonis if it is not yet open and retry")
        
        signal_dict = scan_metadata.get("signal_dict")
        feedback_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Z (m)"]]
        feedback_channel_indices = [index for index in feedback_channel_indices if index is not None]

        nn.lockin_update({"mod1": {"on": False}, "mod2": {"on": False}, "mla_mod1": {"on": False}}) # Make sure the lockins are initially turned off
        channels_dict = {i: name for i, name in enumerate(["t (s)", "x (nm)", "y (nm)", "z (nm)", "I (pA)"])} | {"dict_name": "channels"}
        self.parameters.emit(channels_dict) # This triggers the GUI to start graphing data
        nn.scan_metadata_update({"channel_indices": feedback_channel_indices}) # Make sure the correct channel is being recorded

        # Setting the scan frame in the top right corner
        nn.frame_update({"offset (nm)": [500, 500], "scan_range (nm)": [100, 100], "angle (deg)": 0})
        nn.scan_action({"action": "start", "direction": "down"})
        self.sct.set_view_range("frame")
        self.monitor_scan(channel = feedback_channel_indices[0])

        # Silly frame update number 1
        self.sct.set_view_range("full")
        time.sleep(1)
        self.logprint("Moving the frame to the bottom left corner", message_type = "warning")
        for iteration, position in enumerate(np.linspace(500, 0, 12)):
            nn.frame_update({"offset (nm)": [500, position]}, verbose = False)
            time.sleep(.05)
        for iteration, angle in enumerate(np.linspace(0, 3 * np.pi, 80)):
            nn.frame_update({"angle (deg)": 2 * np.rad2deg(angle), "offset (nm)": [500 * np.cos(angle), 500 * np.sin(angle)], "scan_range (nm)": [100 + 80 * np.sin(angle), 100 - 80 * np.sin(angle)]}, verbose = False)
            time.sleep(.05)
        for iteration, position in enumerate(np.linspace(0, -500, 12)):
            nn.frame_update({"angle (deg)": 0, "offset (nm)": [-500, position]}, verbose = False)
            time.sleep(.05)
        
        (poke_area, error) = nn.frame_update()            
        time.sleep(1)
        self.sct.set_view_range("frame")
        self.abort_requested = False
        nn.scan_action({"action": "start", "direction": "down"})
        self.monitor_scan(channel = feedback_channel_indices[0])
        
        self.logprint("This looks like a great area to condition the tip!", message_type = "message")
        [width_nm, height_nm] = poke_area.get("scan_range (nm)")
        [x_nm, y_nm] = poke_area.get("offset (nm)")



        self.logprint("Performing 5 tip pokes in sequence in this area", message_type = "message")
        # Create a random number generator
        rng = np.random.default_rng()
        poke_locations = rng.uniform(low = [x_nm - .5 * width_nm, y_nm - .5 * height_nm], high = [x_nm + .5 * width_nm, y_nm + .5 * height_nm], size = (5, 2))
        
        for iteration, location in enumerate(poke_locations):
            nn.tip_update({"x (nm)": location[0], "y (nm)": location[0]}, wait = True)
            nn.tip_update(verbose = False)
            nn.shape_tip()
        
        self.logprint("I am done poking the tip. Let's move back to the top right corner and continue scanning there", message_type = "message")            
        self.sct.set_view_range("full")
        
        # Silly frame update number 2
        for iteration, position in enumerate(np.linspace(-500, 0, 12)):
            nn.frame_update({"offset (nm)": [-500, position]}, verbose = False)
            time.sleep(.05)            
        for iteration, angle in enumerate(np.linspace(np.pi, 4 * np.pi, 80)):
            nn.frame_update({"angle (deg)": - np.rad2deg(angle), "offset (nm)": [500 * np.cos(angle), 500 * np.sin(angle)], "scan_range (nm)": [100 + 80 * np.sin(angle), 100 + 80 * np.sin(angle)]}, verbose = False)
            time.sleep(.05)
        for iteration, position in enumerate(np.linspace(0, 500, 12)):
            nn.frame_update({"angle (deg)": 0, "offset (nm)": [500, position]}, verbose = False)
            time.sleep(.05)
        
        nn.scan_action({"action": "start", "direction": "down"})
        self.monitor_scan(channel = feedback_channel_indices[0])


