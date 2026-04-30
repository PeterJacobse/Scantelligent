import sys, os, time
import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        gui_setup = {
            "combobox": {},
            "line_edits": {"tooltips": ["1", "2"],
                           "values": [-2, 10, 2, 100], "units": ["V", "mV", "V", "ms"]
                           },
            "buttons": {}
                     }

        self.prepare_gui(gui_setup)
        self.connect_hardware("nanonis") # Set up the required hardware connections

    @BaseExperiment.experiment_handler
    def run(self):
        nn = self.nanonis # Using nn as an alias for self.nanonis        
        self.sct.toggle_view("nanonis") # Changing the active view to Nanonis

        # Calculate information        
        gui_parameters = self.start_parameters["gui"]
        direction = gui_parameters.get("direction_combobox")
        
        [scan_metadata, grid, tip_status] = [self.start_parameters["nanonis"].get(parameter) for parameter in ["scan_metadata", "grid", "tip_status"]]
        (list_data, error) = nn.grids_to_lists(grid, direction = direction)
        [x_list_nm, y_list_nm] = [list_data[f"{dim}_list (nm)"] for dim in ["x", "y"]]
        n_pixels = len(x_list_nm)

        channels_dict = {i: name for i, name in enumerate(["t (s)", "x (nm)", "y (nm)", "z (nm)", "I (pA)"])} | {"dict_name": "channels"}
        channels_dict.update({4: f"Re(I_f0) (pA)", 5: f"Im(I_f0) (pA)", 6: f"Re(I_f1) (pA)", 7: f"Im(I_f1) (pA)", 8: f"Re(I_f2) (pA)", 9: f"Im(I_f2) (pA)"})
        [channels_dict.update({i + 10: f"Re(I_{i + 3}) (pA)"}) for i in range(29)]
        self.parameters.emit(channels_dict) # This triggers the GUI to start graphing data
        
        
        
        # Main loop
        t_start = time.time()
        t_elapsed = 0
        
        for pixel in range(n_pixels):
            x_nm = x_list_nm[pixel]
            y_nm = y_list_nm[pixel]            
            (tip_status, error) = nn.tip_update({"x (nm)": x_nm, "y (nm)": y_nm}, wait = True, fast_mode = True, verbose = False)
            t_elapsed = time.time() - t_start
            
            pixel = np.random.random(size = 32)
            
            combined_pixel = np.array([np.concatenate((np.array([t_elapsed]), np.array([tip_status.get(key) for key in ["x (nm)", "y (nm)", "z (nm)"]]), pixel))])
            self.data_array.emit(combined_pixel)
            
            self.check_abort_request()
        
        
        self.logprint(f"{x_list_nm}")
