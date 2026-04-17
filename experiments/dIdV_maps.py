import sys, os
from time import sleep
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        scantelligent = kwargs.pop("parent", None)
        if scantelligent == None: scantelligent = kwargs.pop("scantelligent", None)
        super().__init__(*args, **kwargs)
        
        # Set up the GUI. See below
        try: self.prepare_gui(scantelligent.gui)
        except: self.gui_not_found_error()
        
        # Set up the required hardware connections
        #self.connect_hardware("nanonis")

    def prepare_gui(self, gui) -> None:
        self.setup_combobox(gui = gui, items = ["upward", "downward"])
        self.setup_line_edits(gui = gui, tooltips = ["Time per iteration", "Number of iterations"],
                              values = [100, 4, 3], digits = [0, 0, 0], limits = [[0, 1000], [0, 200], [0, 3]], units = ["ms", "steps", ""])

    def run(self):
        gui_parameters = self.read_parameters_from_gui()
        # self.read_parameters_from_gui() # The following parameters can be accessed: self.direction, self.line_value_0, self.line_value_1, self.line_value_2
        
        self.logprint("Hello from the MLA mapping experiment!", message_type = "message")
        self.logprint(f"I read the following parameters from the GUI: {gui_parameters}", message_type = "message")
        
        max_iter = gui_parameters.get("line_edits")[1]
        t_ms = gui_parameters.get("line_edits")[0]

        for iteration in range(max_iter):
            experiment_progress = 100 * (iteration / max_iter)
            self.exp_progress.emit(experiment_progress)
            self.check_abort_request()
            self.logprint(f"Iteration {iter}\nIs an abort requested? {self.abort_requested}", message_type = "message")
            if self.abort_requested: break
            sleep(t_ms / 1000)

        self.experiment_finished()

    def cleanup(self):
        self.disconnect_hardware()

