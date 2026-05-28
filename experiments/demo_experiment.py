import sys, os, time
from time import sleep
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.gui_setup = {"combobox": {"items": ["n", "e", "s", "w"]},
                          "line_edits": {"tooltips": ["Time per iteration", "Number of iterations"], "values": [100, 4, 3], "digits": [0, 0, 0], "limits": [[0, 1000], [0, 200], [0, 3]], "units": ["ms", "steps", ""]}}

    @BaseExperiment.experiment_handler
    def run(self):
        gui_parameters = self.start_parameters.get("gui")
        
        self.logprint("Hello from this demo experiment!", message_type = "message")
        self.logprint(f"I read the following parameters from the GUI: {gui_parameters}", message_type = "message")
        
        rng = np.random.default_rng()
        options = ["apple", "banana", "cherry", "date"]
        
        self.data_array.emit(rng.choice(options, (12)))
        time.sleep(2)
        for _ in range(300):
            self.data_array.emit(np.random.random((25, 5)))
            time.sleep(.01)
        self.data_array.emit(np.array(["clear"]))
        
        

        
