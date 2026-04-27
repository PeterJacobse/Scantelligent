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
        self.setup_combobox(gui = gui, items = ["nearest tip", "up", "down"])
        self.setup_line_edits(gui = gui)

    @BaseExperiment.experiment_handler
    def run(self):
        nn = self.nanonis # Using nn as an alias for self.nanonis        
        self.sct.toggle_view("nanonis") # Changing the active view to Nanonis

        # Calculate information
        [scan_metadata, grid, tip_status] = [self.start_parameters["nanonis"].get(parameter) for parameter in ["scan_metadata", "grid", "tip_status"]]
        gui_parameters = self.start_parameters["gui"]
        direction = gui_parameters.get("direction_combobox")

        signal_dict = scan_metadata.get("signal_dict") # All signals
        recorded_channel_indices = scan_metadata.get("channel_dict").values() # Signals currently being recorded
        feedback_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Z (m)"]] # Retrieve the channel indices from the signal_dict
        feedback_channel_indices = [index for index in feedback_channel_indices if index is not None]
        [recorded_channel_indices.append(channel_index) for channel_index in feedback_channel_indices if channel_index not in recorded_channel_indices]

        channels_dict = {i: name for i, name in enumerate(["t (s)", "x (nm)", "y (nm)", "z (nm)", "I (pA)"])} | {"dict_name": "channels"}
        self.parameters.emit(channels_dict) # This triggers the GUI to start graphing data
        nn.scan_metadata_update({"channel_indices": recorded_channel_indices}) # Make sure the correct channel is being recorded
        
        # Determine the scan direction if 'nearest tip' is selected
        if direction == "nearest tip":
            direction = "up"
            
            tip_location = [tip_status[f"{dim} (nm)"] for dim in ["x", "y"]]
            [blc, tlc] = [grid.get(f"{side}_left_corner (nm)") for side in ["bottom", "top"]]

            dist_to_blc = np.linalg.norm(tip_location - blc)
            dist_to_tlc = np.linalg.norm(tip_location - tlc)
            
            if dist_to_tlc < dist_to_blc: direction = "down"

        # Starting the scan
        self.logprint(f"Starting a scan in the {direction} direction", message_type = "message")
        nn.scan_action({"action": "start", "direction": direction})
        self.monitor_scan(channel = feedback_channel_indices[0])


