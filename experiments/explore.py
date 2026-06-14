import sys, os, time, h5py
import numpy as np
from datetime import datetime
import sklearn.gaussian_process as gp

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.gui_setup = {}

    @BaseExperiment.experiment_handler
    def run(self):        
        nn = self.nanonis # Using nn as an alias for self.nanonis
        
        # Get the start parameters
        gui_parameters = self.start_parameters["gui"]
        spec_buttons = gui_parameters.get("spectroscopy_buttons")
        direction = spec_buttons.get("scan_direction")
        if direction == "gaussian_process":
            raise Exception("Gaussian Process not valid for measure_drift. Select a different scan direction.")
                
        [scan_metadata, grid, tip_status] = [self.start_parameters["nanonis"].get(key) for key in ["scan_metadata", "grid", "tip_status"]]
        [pixels, lines, domain] = [grid.get(key) for key in ["pixels", "lines", "domain (nm)"]]
        [x_range, y_range] = domain
        x_values = np.linspace(-.5 * x_range, .5 * x_range, pixels)
        y_values = np.linspace(-.5 * y_range, .5 * y_range, lines)

        # Determine the scan direction if 'nearest tip' is selected
        if direction == "nearest_tip":            
            tip_location = [tip_status[f"{dim} (nm)"] for dim in ["x", "y"]]
            [blc, tlc] = [grid.get(f"{side}_left_corner (nm)") for side in ["bottom", "top"]]

            dist_to_blc = np.linalg.norm(tip_location - blc)
            dist_to_tlc = np.linalg.norm(tip_location - tlc)
            
            if dist_to_tlc < dist_to_blc: direction = "down"
            else: direction = "up"
        if direction not in ["up", "down"]: raise Exception("Unkown scan direction")

        # Find the channels to scan over
        signal_dict = scan_metadata.get("signal_dict") # All signals
        inverted_signal_dict = {value: key for key, value in signal_dict.items()}        
        Z_channel_index = signal_dict.get("Z (m)")
        nn.scan_metadata_update({"channel_indices": [Z_channel_index]}, verbose = False) # Bounce the z channel index to Nanonis so it will be recorded
        sct_names = ["z (nm)"]
        directions = ["forward", "backward"]
        
        rng = np.random.default_rng()
        self.set_view("nanonis")
        
        z_fwds = []
        (frame, error) = nn.frame_update()
        for iteration in range(5):
            # Create the ArrayItem (for the GUI) and the hdf5 datasets to store the measurement data        
            self.create_array_item(name = f"scan{iteration} @ {os.path.basename(self.experiment_file)}", axes = ["direction", "channel", "x (nm)", "y (nm)"],
                                   shape = (len(directions), len(sct_names), pixels, lines), frame = frame, dtype = np.float32, axis_values = [directions, sct_names, x_values, y_values])

            # Create a new Nexus group for every iteration
            scan_group: h5py.Group = self.output_file.create_group(f"scan{iteration}")

            scan_group.create_dataset("direction", data = np.array([item.encode("utf-8") for item in directions]), dtype = h5py.string_dtype(encoding = "utf-8"))
            scan_group.create_dataset("direction indices", data = np.array([0, 1], dtype = np.int32))            
            scan_group.create_dataset("channel", data = np.array([item.encode("utf-8") for item in sct_names]), dtype = h5py.string_dtype(encoding = "utf-8"))
            scan_group.create_dataset("channel indices", data = np.arange(len(sct_names), dtype = np.int32))            
            scan_group.create_dataset("x (nm)", data = x_values, dtype = np.float32)
            scan_group.create_dataset("y (nm)", data = y_values, dtype = np.float32)            
            
            scan_ds = scan_group.create_dataset("scan", shape = (len(directions), len(sct_names), pixels, lines), dtype = np.float32)
            scan_group.attrs.update({"NX_class": "NXdata",
                                        "signal": "scan",
                                        "axes": ["direction indices", "channel indices", "x (nm)", "y (nm)"]})

            # Start the scan. Passing the dataset will allow it to be updated during scanning            
            data_array = self.nanonis_scan(direction = direction, dataset = scan_ds, verbose = False)
            z_fwds.append(data_array[0, 0])
            
            step = 5 * rng.random(2, dtype = np.float32) - 2.5
            self.logprint(f"Done with scan {iteration}. Now moving the frame by delta_x = {float(step[0]):.4f} nm, delta_y = {float(step[1]):.4f} nm", message_type = "message")
            center = frame.get("center (nm)")
            (frame, error) = nn.frame_update({"center (nm)": np.array([center[0] + step[0], center[1] + step[1]])})

