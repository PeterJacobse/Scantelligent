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

        # Find the channels to scan over
        signal_dict = scan_metadata.get("signal_dict") # All signals
        inverted_signal_dict = {value: key for key, value in signal_dict.items()}
        nanonis_channel_indices = list(scan_metadata.get("channel_dict").values()) # Signals currently checked to be recorded
        fb_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Z (m)"]] # Retrieve the channel indices from the signal_dict
        [nanonis_channel_indices.append(channel_index) for channel_index in fb_channel_indices if channel_index is not None and channel_index not in nanonis_channel_indices] # Add the z channel to the list of recorded channels
        nn.scan_metadata_update({"channel_indices": nanonis_channel_indices}, verbose = False) # Bounce the channel indices back to Nanonis with the z channel included, so it will be recorded
        
        # Retrieve the names of the recorded channels and define the two scan directions
        channel_names = [inverted_signal_dict.get(index) for index in nanonis_channel_indices]
        directions = ["forward", "backward"]

        # Set the view to Nanonis and create the ArrayItem to store the measurement data
        self.set_view("nanonis")
        self.create_array_item(name = "scan0 @ drift_detect", axes = ["direction", "channel", "x (nm)", "y (nm)"],
                               shape = (len(directions), len(channel_names), pixels, lines), frame = grid, dtype = np.float32, axis_values = [directions, channel_names, x_values, y_values])

        self.nanonis_scan_new(direction = "up")



    def nanonis_scan_new(self, direction: str = "down", timeout_s: int = 100000, iterations: int = 200, verbose: bool = True) -> np.ndarray:
        if verbose: self.logprint(f"Starting a scan in the {direction} direction", message_type = "message")
        self.nanonis.scan_action({"action": "start", "direction": direction})
        
        (scan_metadata, error) = self.nanonis.scan_metadata_update(verbose = False) # Calling scan_metadata_update refreshes the channels that are being recorded, so that they can be selected
        [signal_dict, channel_dict] = [scan_metadata.get(key) for key in ["signal_dict", "channel_dict"]]
        nanonis_channel_indices = list(channel_dict.values())
        inverted_signal_dict = {value: key for key, value in signal_dict.items()}
        channel_names = [inverted_signal_dict.get(index) for index in nanonis_channel_indices]
        
        
        
        # Loop to check scan progress
        t_start = time.time()
        t_elapsed = 0
        scan_finished = False
        for iteration in range(1000000):
            this_iteration_channel_index = iteration % len(channel_names)
            this_iteration_nanonis_index = nanonis_channel_indices[this_iteration_channel_index]
            
            # 1. Monitor and emit 'tip status' data while scanning
            (tip_status, error) = self.nanonis.tip_update(wait = False, fast_mode = True, verbose = False)
            if not error:
                [x_nm, y_nm, z_nm, I_pA] = [tip_status.get(parameter) for parameter in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
                self.data_array.emit(np.array([t_elapsed, x_nm, y_nm, z_nm, I_pA], dtype = np.float32))
            
            # 2. Emit data slices
            (scan_image, error) = self.nanonis.scan_update(this_iteration_nanonis_index, backward = False, emit_image = False, verbose = True)
            self.array_slice.emit(scan_image.transpose(), [0, this_iteration_channel_index], [0, 1])
            (scan_image_bwd, error) = self.nanonis.scan_update(this_iteration_nanonis_index, backward = True, emit_image = False, verbose = True)
            self.array_slice.emit(scan_image_bwd.transpose(), [1, this_iteration_channel_index], [0, 1])

            # 3. Check exit conditions
            self.check_abort_request()
            
            time.sleep(.05)
            t_elapsed = time.time() - t_start
            if t_elapsed > timeout_s: break
            
            nan_mask = np.isnan(scan_image)
            scan_finished = not bool(np.any(nan_mask))
            if scan_finished:
                self.logprint("Scan finished", message_type = "message")
                break
        return
