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
        if direction not in ["up", "down", "gaussian_process"]: raise Exception("Unkown scan direction")
        self.set_view("nanonis")
        
        if direction in ["up", "down"]:
            self.output_file = h5py.File(self.experiment_file, "w") # Open the new HDF5 file
            self.output_file.attrs.update({"date": datetime.now().strftime("%Y/%m/%d"), "time": datetime.now().strftime("%H:%M:%S")})

            # Starting the scan
            self.logprint(f"Starting a scan in the {direction} direction", message_type = "message")
            nn.scan_action({"action": "start", "direction": direction})
            scan_image = self.monitor_scan(output_channel = feedback_channel_indices[0])
            time.sleep(1)
        


        elif direction == "gaussian_process":
            n_points = 20
            
            self.logprint(f"Starting the experiment with 20 random points in the scan frame", message_type = "message")
            [x_grid, y_grid] = [grid.get(key) for key in ["x_grid (nm)", "y_grid (nm)"]]
            (lists, error) = nn.grids_to_lists(grid, direction = "down")
            tip_xy = [tip_status.get(key) for key in ["x (nm)", "y (nm)"]]
            [x_list, y_list] = [lists.get(key) for key in ["x_list (nm)", "y_list (nm)"]]
            xy_list = np.array([x_list, y_list]).transpose()
            list_len = len(x_list)

            rng = np.random.default_rng()
            random_flat_indices = rng.choice(a = list_len, size = n_points, replace = False)
            random_coordinates = np.insert(np.array([[x_list[index], y_list[index]] for index in random_flat_indices]), 0, tip_xy, axis = 0)
            ordered_coordinates = self.data.find_shortest_path(random_coordinates)
            
            self.parameters.emit({"dict_name": "path", "coordinates (nm)": ordered_coordinates, "visible": True})
            output_channels = ["t (s)", "x (nm)", "y (nm)", "z (nm)", "\u03C3\u00B2(z) (nm2)", "I (pA)"]
            self.data_array.emit(np.array(output_channels))

            measurement_array = np.zeros((n_points, len(output_channels)))
            t_start = time.time()
            t_elapsed = 0
            for iteration, coordinate in enumerate(ordered_coordinates[1:]):
                self.check_abort_request()
                (tip_status, error) = nn.tip_update({"x (nm)": coordinate[0], "y (nm)": coordinate[1]}, verbose = False, wait = True, fast_mode = True)
                (jitter_dict, error) = nn.jitter_tip({"radius (nm)": .2, "iterations": 4}, verbose = False)
                z_values = jitter_dict.get("z_values (nm)")
                z_avg_nm = np.average(z_values)
                z_var_nm2 = np.var(z_values, ddof = 1)
                
                t_elapsed = time.time() - t_start
                if not error:
                    [x_nm, y_nm, z_nm, I_pA] = [tip_status.get(parameter) for parameter in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
                    data_chunk = np.array([t_elapsed, x_nm, y_nm, z_avg_nm, z_var_nm2, I_pA])
                    
                    measurement_array[iteration] = data_chunk
                    self.data_array.emit(data_chunk)
            
            # Apply the Gaussian process regression to the data
            xy_coords_nm = measurement_array[:, 1:3]
            z_coords_nm = measurement_array[:, 3]
            z_vars_nm2 = measurement_array[:, 4] + .05
            
            l_guess_nm = (2., 2.)
            l_bounds_nm = ((1e-1, 100), (1e-1, 100))
            kernel = gp.kernels.RBF(length_scale = l_guess_nm, length_scale_bounds = l_bounds_nm)
            gpr = gp.GaussianProcessRegressor(kernel, normalize_y = True, alpha = z_vars_nm2)
            gpr.fit(xy_coords_nm, z_coords_nm)
            
            # Extrapolate the GPR fit to model the entire surface
            (z_fit_col, z_std_dev_col) = gpr.predict(xy_list, return_std = True)
            z_fit_nm = z_fit_col.reshape(x_grid.shape)
            self.image.emit(z_fit_nm)
            
            selected_indices = []
            gpr.set_params(alpha = np.append(z_vars_nm2, 0))
            for _ in range(n_points):
                z_var_col = z_std_dev_col ** 2
                best_index = np.argmax(z_var_col)
                selected_indices.append(best_index)
                next_coord = xy_list[best_index]
                
                # Recalculate the fit considering that measuring the new point would collapse the variance in that region
                gpr.fit(np.vstack([xy_coords_nm, next_coord]), np.append(z_coords_nm, 0))
                (z_fit_col, z_std_dev_col) = gpr.predict(xy_list, return_std = True)
                z_fit_nm = z_fit_col.reshape(x_grid.shape)
            
            
            
            ordered_coordinates = self.data.find_shortest_path(np.insert(xy_list[selected_indices], 0, tip_xy, axis = 0))
            self.parameters.emit({"dict_name": "path", "coordinates (nm)": ordered_coordinates, "visible": True})
            
            t_start = time.time()
            t_elapsed = 0
            for iteration, coordinate in enumerate(ordered_coordinates[1:]):
                self.check_abort_request()
                (tip_status, error) = nn.tip_update({"x (nm)": coordinate[0], "y (nm)": coordinate[1]}, verbose = False, wait = True, fast_mode = True)
                (jitter_dict, error) = nn.jitter_tip({"radius (nm)": .2, "iterations": 4}, verbose = False)
                z_values = jitter_dict.get("z_values (nm)")
                z_avg_nm = np.average(z_values)
                z_var_nm2 = np.var(z_values, ddof = 1)
                
                t_elapsed = time.time() - t_start
                if not error:
                    [x_nm, y_nm, z_nm, I_pA] = [tip_status.get(parameter) for parameter in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
                    data_chunk = np.array([t_elapsed, x_nm, y_nm, z_avg_nm, z_var_nm2, I_pA])
                    
                    measurement_array[iteration] = data_chunk
                    self.data_array.emit(data_chunk)
            
            # Apply the Gaussian process regression to the data
            xy_coords_nm = np.append(xy_coords_nm, measurement_array[:, 1:3])
            z_coords_nm = np.append(xy_coords_nm, measurement_array[:, 3])
            z_vars_nm2 = np.append(z_vars_nm2, measurement_array[:, 4]) + .05
            
            # Extrapolate the GPR fit to model the entire surface
            gpr.set_params(alpha = z_vars_nm2)
            gpr.fit(xy_coords_nm, z_coords_nm)
            (z_fit_col, z_std_dev_col) = gpr.predict(xy_list, return_std = True)
            z_fit_nm = z_fit_col.reshape(x_grid.shape)
            self.image.emit(z_fit_nm)


