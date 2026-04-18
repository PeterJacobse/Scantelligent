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
        self.setup_combobox(gui = gui, items = ["map up / scan down", "map down / scan up"])
        self.setup_line_edits(gui = gui, tooltips = ["V_start", "V_step", "V_end", "t_per_pixel"],
                              values = [-2, 100, 2, 1], digits = [2, 0, 2, 2], limits = [[-10, 10], [0, 10000], [-10, 10], [0, 1000]], units = ["V", "mV", "V", "ms"])

    def run(self):
        nn = self.nanonis
        nhw = nn.nanonis_hardware
        gui_parameters = self.read_parameters_from_gui()
        # self.read_parameters_from_gui() # The following parameters can be accessed: self.direction, self.line_value_0, self.line_value_1, self.line_value_2, etc.
        direction = gui_parameters["direction_combobox"]
        [V_begin, V_step, V_end] = [gui_parameters["line_edits"][index] for index in range(3)]

        self.logprint(f"Starting a dI/dV mapping series from V = {V_begin} V to V = {V_end} V in steps of dV = {V_step} mV.", message_type = "success")
        


        (scan_metadata, error) = nn.scan_metadata_update()
        signal_dict = scan_metadata["signal_dict"]
        feedback_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Z (m)"]]
        feedback_channel_indices = [index for index in feedback_channel_indices if index is not None]
        constant_height_channel_indices = [signal_dict.get(channel_name) for channel_name in ["Lockin Demod 1 X (A)", "Lockin Demod 1 Y (A)", "Current (A)"]]
        constant_height_channel_indices = [index for index in constant_height_channel_indices if index is not None]

        self.logprint("Switching to current feedback (topographic STM) mode", message_type = "message")
        nhw.set_scan_buffer(channel_indices = constant_height_channel_indices)
        sleep(2)
        self.logprint("Switching to constant height (mapping) mode")
        nhw.set_scan_buffer(channel_indices = feedback_channel_indices)

        self.nanonis.scan_action({"action": "start", "direction": direction})
        
        iteration = 0
        while iteration < 100000:
            iteration += 1
            scan_image = nn.scan_update(channel = constant_height_channel_indices[0])
            nan_percentage = np.mean(np.isnan(scan_image)) * 100
            nn.tip_update(verbose = False)

            self.check_abort_request()
            if self.abort_requested: break
            sleep(.1)

        self.cleanup()
        self.experiment_finished()

    def cleanup(self):
        self.nanonis.scan_action({"action": "stop"})

