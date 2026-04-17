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
        self.connect_hardware("nanonis")

    def prepare_gui(self, gui) -> None:
        self.setup_combobox(gui = gui, items = ["up", "down"])
        self.setup_line_edits(gui = gui, tooltips = ["Time per iteration", "Number of iterations"],
                              values = [100, 4, 3], digits = [0, 0, 0], limits = [[0, 1000], [0, 200], [0, 3]], units = ["ms", "steps", ""])

    def run(self):
        gui_parameters = self.read_parameters_from_gui()
        # self.read_parameters_from_gui() # The following parameters can be accessed: self.direction, self.line_value_0, self.line_value_1, self.line_value_2
        
        self.logprint("Hello from the MLA mapping experiment!", message_type = "message")
        self.logprint(f"I read the following parameters from the GUI: {gui_parameters}", message_type = "message")
        direction = gui_parameters.get("direction_combobox")
        
        nn = self.nanonis
        nhw = nn.nanonis_hardware
        self.logprint(f"I have my aliases for nanonis {nn} and nanonis_hardware: {nhw}", message_type = "success")
        
        (grid_data, error) = nn.grid_update()
        self.logprint(f"{grid_data}; {error}", message_type = "message")
        (coord_lists, error) = nn.grids_to_lists(grid_data, direction = direction)
        self.logprint(f"{coord_lists}; {error}", message_type = "message")
        xy_list_hex = coord_lists.get("xy_list")
        max_iter = len(xy_list_hex)
        self.logprint(f"{xy_list_hex}; {error}", message_type = "message")

        for iter, xy_val in enumerate(xy_list_hex):
            self.logprint(f"Iteration {iter}", message_type = "message")
            experiment_progress = 100 * (iter / max_iter)
            self.exp_progress.emit(experiment_progress)
            self.check_abort_request()
            if self.abort_requested: break
            nhw.set_xy(xy_val)
            sleep(.01)

        self.experiment_finished()

    def cleanup(self):
        self.disconnect_hardware()

