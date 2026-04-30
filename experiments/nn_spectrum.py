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
        nhw = nn.nanonis_hardware

        # Calculate information
        gui_parameters = self.start_parameters["gui"]
        [V_start, V_end, n_points, t_int_ms, t_settle_ms] = [self.sct.gui.line_edits[name].getValue() for name in ["V_start_STS", "V_end_STS", "points_STS", "t_integration", "t_settle"]]
        t_settle_s = t_settle_ms / 1000
        t_int_s = t_int_ms / 1000

        channels_dict = {i: name for i, name in enumerate(["t (s)", "V (V)", "I (pA)", "z (nm)", "Lockin Demod 1 X (pA)"])} | {"dict_name": "channels"}
        self.parameters.emit(channels_dict) # This triggers the GUI to start graphing data
        
        scan_metadata = self.start_parameters["nanonis"].get("scan_metadata")
        self.logprint(f"{scan_metadata = }")



        # Main loop
        V_list = np.linspace(V_start, V_end, n_points)
        
        t_start = time.time()
        t_elapsed = 0

        for iteration, voltage in enumerate(V_list):
            nhw.set_V(voltage)
            time.sleep(t_settle_s)
            
            t_elapsed = time.time() - t_start
            self.data_array.emit(np.array([[2, 0]]))
            
            self.check_abort_request()

