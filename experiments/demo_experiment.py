import sys, os
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
        
        max_iter = gui_parameters.get("line_edits")[1]
        t_ms = gui_parameters.get("line_edits")[0]

        for iteration in range(max_iter):
            experiment_progress = int(100 * (iteration / max_iter))
            self.exp_progress.emit(experiment_progress)
            self.check_abort_request()
            self.logprint(f"Iteration {iter}\nIs an abort requested? {self.abort_requested}", message_type = "message")
            if self.abort_requested: break
            sleep(t_ms / 1000)

