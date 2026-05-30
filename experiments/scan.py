import sys, os, time, h5py
import numpy as np
from scipy.ndimage import gaussian_filter
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.gui_setup = {}

    @BaseExperiment.experiment_handler
    def run(self):        
        nn = self.nanonis # Using nn as an alias for self.nanonis

        # Calculate information
        [scan_metadata, grid, tip_status] = [self.start_parameters["nanonis"].get(parameter) for parameter in ["scan_metadata", "grid", "tip_status"]]
        gui_parameters = self.start_parameters["gui"]
        spec_buttons = gui_parameters.get("spectroscopy_buttons")
        direction = spec_buttons.get("scan_direction")
        
        signal_dict = scan_metadata.get("signal_dict") # All signals
        recorded_channel_indices = list(scan_metadata.get("channel_dict").values()) # Signals currently checked to be recorded
        feedback_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Z (m)"]] # Retrieve the channel indices from the signal_dict
        feedback_channel_indices = [index for index in feedback_channel_indices if index is not None]
        [recorded_channel_indices.append(channel_index) for channel_index in feedback_channel_indices if channel_index not in recorded_channel_indices] # Add the z channel to the list of recorded channels
        nn.scan_metadata_update({"channel_indices": recorded_channel_indices}, verbose = False) # Make sure the correct channel is being recorded
        
        graph_channels = ["t (s)", "x (nm)", "y (nm)", "z (nm)", "I (pA)"]
        self.data_array.emit(np.array(graph_channels)) # This triggers the GUI to start graphing data
                
        # Determine the scan direction if 'nearest tip' is selected
        if direction == "nearest_tip":            
            tip_location = [tip_status[f"{dim} (nm)"] for dim in ["x", "y"]]
            [blc, tlc] = [grid.get(f"{side}_left_corner (nm)") for side in ["bottom", "top"]]

            dist_to_blc = np.linalg.norm(tip_location - blc)
            dist_to_tlc = np.linalg.norm(tip_location - tlc)
            
            if dist_to_tlc < dist_to_blc: direction = "down"
            else: direction = "up"

        if direction in ["up", "down"]:
            self.output_file = h5py.File(self.experiment_file, "w") # Open the new HDF5 file
            self.output_file.attrs.update({"date": datetime.now().strftime("%Y/%m/%d"), "time": datetime.now().strftime("%H:%M:%S")})

            # Starting the scan
            self.logprint(f"Starting a scan in the {direction} direction", message_type = "message")
            nn.scan_action({"action": "start", "direction": direction})
            scan_image = self.monitor_scan(output_channel = feedback_channel_indices[0])
            time.sleep(1)
        
        elif direction == "gaussian_process":
            n_points = 40
            
            self.logprint(f"Starting the experiment with 20 random points in the scan frame", message_type = "message")
            (lists, error) = nn.grids_to_lists(grid, direction = "down")
            tip_xy = [tip_status.get(key) for key in ["x (nm)", "y (nm)"]]
            [x_list, y_list] = [lists.get(key) for key in ["x_list (nm)", "y_list (nm)"]]
            list_len = len(x_list)

            rng = np.random.default_rng()
            random_flat_indices = rng.choice(a = list_len, size = n_points, replace = False)
            random_coordinates = np.insert(np.array([[x_list[index], y_list[index]] for index in random_flat_indices]), 0, tip_xy, axis = 0)
            ordered_coordinates = self.data.find_shortest_path(random_coordinates)
            
            self.parameters.emit({"dict_name": "path", "coordinates (nm)": ordered_coordinates, "visible": True})            
            output_channels = ["t (s)", "x (nm)", "y (nm)", "z (nm)", "I (pA)"]
            self.data_array.emit(np.array(output_channels))            

            measurement_array = np.zeros((n_points, len(output_channels)))            
            t_start = time.time()
            t_elapsed = 0
            for iteration, coordinate in enumerate(ordered_coordinates[1:]):
                self.check_abort_request()
                (tip_status, error) = nn.tip_update({"x (nm)": coordinate[0], "y (nm)": coordinate[1]}, verbose = False, wait = True, fast_mode = True)
                t_elapsed = time.time() - t_start
                if not error:
                    [x_nm, y_nm, z_nm, I_pA] = [tip_status.get(parameter) for parameter in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
                    data_chunk = np.array([t_elapsed, x_nm, y_nm, z_nm, I_pA])
                    
                    measurement_array[iteration] = data_chunk
                    self.data_array.emit(data_chunk)
            
            self.logprint(f"{measurement_array = }")
            
        else:
            raise Exception("Unkown scan direction")

