import sys, os
from time import sleep
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        scantelligent = kwargs.pop("parent", None)
        if scantelligent == None: scantelligent = kwargs.pop("scantelligent", None)
        self.hw_config = kwargs.pop("hw_config", None)

        super().__init__(hw_config = self.hw_config)
        
        try: self.prepare_gui(scantelligent.gui)
        except: self.gui_not_found_error()
        
        #self.connect_hardware("nanonis")

    def prepare_gui(self, gui) -> None:        
        self.setup_combobox(gui = gui, tooltip = "direction", items = ["n", "e", "s", "w"])
        self.setup_line_edits(gui = gui, tooltips = ["Coarse steps per iteration", "Number of iterations", "Modulators (0: off; 1: 1 on; 2: 2 on; 3: both on)"],
                              values = [10, 200, 3], digits = [0, 0, 0], limits = [[0, 1000], [0, 10000], [0, 3]], units = ["steps", "", ""])

    def run(self):
        # self.read_parameters_from_gui() # The following parameters can be accessed: self.direction, self.line_value_0, self.line_value_1, self.line_value_2
        
        self.logprint("Hello from experiment 1", message_type = "message")
        
        self.check_abort_request()
        self.logprint(f"Is an abort requested? {self.abort_requested}", message_type = "message")

        sleep(2)
        self.check_abort_request()
        self.logprint(f"Is an abort requested? {self.abort_requested}", message_type = "message")
        
        self.experiment_finished()
    
    def cleanup(self):
        self.logprint("Cleaning things up")

