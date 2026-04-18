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
        nn = self.nanonis
        gui_parameters = self.read_parameters_from_gui()
        # self.read_parameters_from_gui() # The following parameters can be accessed: self.direction, self.line_value_0, self.line_value_1, self.line_value_2, etc.
        direction = gui_parameters["direction_combobox"]
        
        (frame, error) = nn.frame_update()
        (grid, error) = nn.grid_update()
        (scan_metadata, error) = nn.scan_metadata_update()
        scan_channels = scan_metadata["channel_dict"]
        chan_index = list(scan_channels.values())[0]
        [pixels, lines] = [grid.get(attribute) for attribute in ["pixels", "lines"]]
        n_grid = pixels * lines

        self.logprint(f"Starting a Nanonis scan in direction {direction}. Recording channels: {list(scan_channels.keys())}", message_type = "success")



        self.nanonis.scan_action({"action": "start", "direction": direction})
        
        iteration = 0
        while iteration < 100000:
            iteration += 1
            (scan_image, error) = nn.scan_update(chan_index, verbose = False)
            nan_percentage = np.mean(np.isnan(scan_image)) * 100
            self.task_progress.emit(100 - nan_percentage)
            nn.tip_update(verbose = False)

            self.check_abort_request()
            if self.abort_requested: break
            sleep(.1)

        self.cleanup()
        self.experiment_finished()

    def cleanup(self):
        self.nanonis.scan_action({"action": "stop"})

