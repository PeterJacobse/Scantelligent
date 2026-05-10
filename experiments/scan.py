import sys, os, time
import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.gui_setup = {"combobox": {"items": ["nearest tip", "up", "down"]}, "line_edits": {}, "buttons": {}}

    @BaseExperiment.experiment_handler
    def run(self):        
        nn = self.nanonis # Using nn as an alias for self.nanonis

        # Calculate information
        [scan_metadata, grid, tip_status] = [self.start_parameters["nanonis"].get(parameter) for parameter in ["scan_metadata", "grid", "tip_status"]]
        gui_parameters = self.start_parameters["gui"]
        direction = gui_parameters.get("combobox")

        signal_dict = scan_metadata.get("signal_dict") # All signals
        recorded_channel_indices = list(scan_metadata.get("channel_dict").values()) # Signals currently being recorded
        
        feedback_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Z (m)"]] # Retrieve the channel indices from the signal_dict
        feedback_channel_indices = [index for index in feedback_channel_indices if index is not None]
        
        # (sig_dict, error) = nn.signals_update("Z (m)") Another valid way to retrieve the scan channel index is by requesting a signals_update and passing the name of the channel
        # sig_dict.pop("dict_name")
        # z_channel_index = list(sig_dict.keys())

        [recorded_channel_indices.append(channel_index) for channel_index in feedback_channel_indices if channel_index not in recorded_channel_indices] # Add the z channel to the list of recorded channels
        nn.scan_metadata_update({"channel_indices": recorded_channel_indices}, verbose = False) # Make sure the correct channel is being recorded
        
        graph_channels = ["t (s)", "x (nm)", "y (nm)", "z (nm)", "I (pA)"]
        self.prepare_graph(graph_channels) # This triggers the GUI to start graphing data
                
        # Determine the scan direction if 'nearest tip' is selected
        if direction == "nearest tip":
            direction = "up"
            
            tip_location = [tip_status[f"{dim} (nm)"] for dim in ["x", "y"]]
            [blc, tlc] = [grid.get(f"{side}_left_corner (nm)") for side in ["bottom", "top"]]

            dist_to_blc = np.linalg.norm(tip_location - blc)
            dist_to_tlc = np.linalg.norm(tip_location - tlc)
            
            if dist_to_tlc < dist_to_blc: direction = "down"

        self.output_file.attrs.update({"frame_offset_x (nm)": 100})


        # Starting the scan
        self.logprint(f"Starting a scan in the {direction} direction", message_type = "message")
        nn.scan_action({"action": "start", "direction": direction})
        scan_image = self.monitor_scan(output_channel = feedback_channel_indices[0])

