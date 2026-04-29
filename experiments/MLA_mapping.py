import sys, os, time
import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        gui_setup = {
            "combobox": {"items": ["up", "down"]},
            "line_edits": {},
            "buttons": {}
                     }

        self.prepare_gui(gui_setup)
        self.connect_hardware("nanonis") # Set up the required hardware connections

    @BaseExperiment.experiment_handler
    def run(self):
        nn = self.nanonis # Using nn as an alias for self.nanonis        
        self.sct.toggle_view("nanonis") # Changing the active view to Nanonis

        # Calculate information
        [scan_metadata, grid, tip_status] = [self.start_parameters["nanonis"].get(parameter) for parameter in ["scan_metadata", "grid", "tip_status"]]
        gui_parameters = self.start_parameters["gui"]
        direction = gui_parameters.get("direction_combobox")
        
        self.logprint("Starting a grid scan")
