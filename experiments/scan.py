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
        inverted_signal_dict = {value: key for key, value in signal_dict.items()}
        recorded_channel_indices = list(scan_metadata.get("channel_dict").values()) # Signals currently checked to be recorded
        feedback_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Z (m)"]] # Retrieve the channel indices from the signal_dict
        feedback_channel_indices = [index for index in feedback_channel_indices if index is not None]
        [recorded_channel_indices.append(channel_index) for channel_index in feedback_channel_indices if channel_index not in recorded_channel_indices] # Add the z channel to the list of recorded channels
        recorded_channel_names = [inverted_signal_dict.get(index) for index in recorded_channel_indices]
        
        [pixels, lines] = [grid.get(key) for key in ["pixels", "lines"]]
        [width_nm, height_nm] = grid.get("scan_range (nm)")
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
        
        # Start writing initial data to file and then start the experiment
        if direction in ["up", "down"]:
            scan_group: h5py.Group = self.output_file.create_group("scan_group")
            scan_group.attrs.update({"NX_class": "NXdata"})
            
            dir_ds = scan_group.create_dataset("directions", data = np.array([item.encode("utf-8") for item in ["forward", "backward"]]), dtype = h5py.string_dtype(encoding = "utf-8"))
            dir_indices_ds = scan_group.create_dataset("direction indices", data = np.array([0, 1], dtype = np.int32))
            dir_indices_ds.make_scale("direction indices")
            channels_ds = scan_group.create_dataset("channels", data = np.array([item.encode("utf-8") for item in recorded_channel_names]), dtype = h5py.string_dtype(encoding = "utf-8"))
            channel_indices_ds = scan_group.create_dataset("channel indices", data = np.arange(len(recorded_channel_indices), dtype = np.int32))
            channel_indices_ds.make_scale("channel indices")
            x_ds = scan_group.create_dataset("x (nm)", data = np.linspace(-width_nm / 2, width_nm / 2, pixels), dtype = np.float32)
            x_ds.make_scale("x (nm)")
            y_ds = scan_group.create_dataset("y (nm)", data = np.linspace(-height_nm / 2, height_nm / 2, lines), dtype = np.float32)
            y_ds.make_scale("y (nm)")
            
            scan_ds = scan_group.create_dataset("scan", shape = ((2, len(recorded_channel_indices), lines, pixels)), dtype = np.float32)
            scan_ds.dims[0].attach_scale(dir_indices_ds)
            scan_ds.dims[1].attach_scale(channel_indices_ds)
            scan_ds.dims[2].attach_scale(y_ds)
            scan_ds.dims[3].attach_scale(x_ds)
            
            scan_group.attrs.update({"signal": "scan"})
            scan_group.attrs.update({"axes": np.array(["direction indices", "channel indices", "y (nm)", "x (nm)"], dtype = "S")})
            
            # Start the scan. Passing the dataset will allow it to be updated during scanning
            scan_data = self.nanonis_scan(direction = direction, dataset = scan_ds, iterations = 20) # Save the entire dataset every 20 iterations



        elif direction == "gaussian_process":
            n_points = 160
            n_iterations = 8
            iteration = 0
            
            output_channels = ["t (s)", "x (nm)", "y (nm)", "z (nm)", "\u03C3\u00B2(z) (nm2)", "I (pA)"]
            self.data_array.emit(np.array(output_channels))
            measurement_array = np.zeros((n_points * n_iterations, len(output_channels)))
            
            # Start data            
            [x_grid, y_grid] = [grid.get(key) for key in ["x_grid (nm)", "y_grid (nm)"]]
            z_fit_nm = np.zeros_like(x_grid, dtype = np.float32)
            (lists, error) = nn.grids_to_lists(grid, direction = "down")
            tip_xy = [tip_status.get(key) for key in ["x (nm)", "y (nm)"]]
            [x_list, y_list] = [lists.get(key) for key in ["x_list (nm)", "y_list (nm)"]]
            xy_list = np.array([x_list, y_list]).transpose()
            list_len = len(x_list)
            
            # GPR model
            #k_periodic = gp.kernels.ExpSineSquared(length_scale = 1.0, periodicity = 2.0, length_scale_bounds = (0.2, 5.0), periodicity_bounds=(0.5, 10.0))
            #k_periodic_decay = gp.kernels.Matern(length_scale = 10, length_scale_bounds = (5., 50.), nu = 1.5)            
            k_fine_detail = gp.kernels.Matern(length_scale = .8, length_scale_bounds = (.1, 3), nu = 0.5)
            k_large_scale = gp.kernels.Matern(length_scale = 40, length_scale_bounds = (20, 120), nu = 2.5)
            k_electronic = gp.kernels.ExpSineSquared(length_scale = 2.0, periodicity = .5, length_scale_bounds = (0.5, 5.0), periodicity_bounds = (.3, .5))
            k_decay = gp.kernels.Matern(length_scale = 5.0, length_scale_bounds = (2.0, 15.0), nu = 1.5)
            k_ripples = k_electronic * k_decay
            k_noise = gp.kernels.WhiteKernel(noise_level = .01, noise_level_bounds = (1e-5, .05))
            k_composite = k_fine_detail + k_large_scale + k_noise #+ k_ripples
            gpr = gp.GaussianProcessRegressor(k_composite, n_restarts_optimizer = 15, random_state = 42)
            
            # Generate self-avoiding random coordinates
            rng = np.random.default_rng()
            selected_indices = rng.choice(a = list_len, size = n_points, replace = False)
            
            
            
            # Measurement loop
            self.logprint(f"Starting the Gaussian Process Regression experiment with {n_points} random points in the scan frame", message_type = "message")
            t_start = time.time()
            t_elapsed = 0
            for iteration in range(n_iterations):
                xy_random_nm = np.insert(xy_list[selected_indices], 0, tip_xy, axis = 0)                
                xy_ordered_nm = self.data.find_shortest_path(xy_random_nm)
                self.parameters.emit({"dict_name": "path", "coordinates (nm)": xy_ordered_nm, "visible": True})
                
                # Sample the points
                for point_number, coordinate in enumerate(xy_ordered_nm[1:]):
                    if point_number == 10: self.image.emit(np.flipud(z_fit_nm))
                    self.check_abort_request()
                    (tip_status, error) = nn.tip_update({"x (nm)": coordinate[0], "y (nm)": coordinate[1]}, verbose = False, wait = True, fast_mode = True)
                    (jitter_dict, error) = nn.jitter_tip({"radius (nm)": .1, "iterations": 4}, verbose = False)
                    z_values = jitter_dict.get("z_values (nm)")
                    z_avg_nm = np.average(z_values)
                    z_var_nm2 = np.var(z_values, ddof = 1)
                    
                    t_elapsed = time.time() - t_start
                    if not error:
                        [x_nm, y_nm, z_nm, I_pA] = [tip_status.get(parameter) for parameter in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
                        data_chunk = np.array([t_elapsed, x_nm, y_nm, z_avg_nm, z_var_nm2, I_pA])
                        
                        measurement_array[point_number + iteration * n_points, :] = data_chunk
                        self.data_array.emit(data_chunk)
                
                # Apply the Gaussian process regression to the data
                xy_coords_nm = measurement_array[:(iteration + 1) * n_points, 1:3]
                z_coords_nm = measurement_array[:(iteration + 1) * n_points, 3]
                z_vars_nm2 = measurement_array[:(iteration + 1) * n_points, 4]

                gpr.set_params(alpha = z_vars_nm2 + .2)
                gpr.fit(xy_coords_nm, z_coords_nm)
                gpr.kernel = gpr.kernel_
                
                # Extrapolate the GPR fit to model the entire surface
                (z_fit_col, z_std_dev_col) = gpr.predict(xy_list, return_std = True)
                z_fit_nm = z_fit_col.reshape(x_grid.shape)
                self.image.emit(np.flipud(z_fit_nm))
            
                       
            
                # Calculate the next points to sample
                z_std_dev_nm_masked = z_std_dev_col.copy()
                l2 = (gpr.kernel_.get_params().get("k1__length_scale", .5)) ** 2
                n_cut = 12
                l2_cut = n_cut * l2 # Do not mask distances farther than 4 * l2 away from the new coord, where l2 is the small length scale (small scale kernel)
                cut_edge = 1 + 1 / (n_cut + 1) # Value of the Lorentzian function at its cutoff distance of n_cut times the square of the distance from the center
                
                selected_indices = []
                for _ in range(n_points):
                    best_index = np.argmax(z_std_dev_nm_masked)
                    selected_indices.append(best_index)
                    next_coord = xy_list[best_index]
                    
                    # Mask the region of the selected point
                    for index, xy in enumerate(xy_list):
                        dx2 = (xy[0] - next_coord[0]) ** 2
                        if dx2 > l2_cut: continue

                        dy2 = (xy[1] - next_coord[1]) ** 2
                        if dy2 > l2_cut: continue
                        
                        dr2 = dx2 + dy2
                        if dr2 > l2_cut: continue
                        
                        n_l2 = dr2 / l2 # Number of distances l2 that xy is away from the new coord
                        
                        z_std_dev_nm_masked[index] *= (cut_edge - 1 / (1 + n_l2))
                
                masked_image = z_std_dev_nm_masked.reshape(x_grid.shape)
                self.image.emit(np.flipud(masked_image))
            
            self.image.emit(np.flipud(z_fit_nm))

