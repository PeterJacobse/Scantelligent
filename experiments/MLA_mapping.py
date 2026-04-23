import sys, os, time
import numpy as np
from scipy.ndimage import gaussian_filter

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
        [self.connect_hardware(hardware_component) for hardware_component in ["nanonis", "mla"]]
        self.sct = scantelligent

    def prepare_gui(self, gui) -> None:
        self.setup_combobox(gui = gui, items = ["scan down / map up", "scan up / map down"])
        self.setup_line_edits(gui = gui, tooltips = ["V_start", "V_step", "V_end", "integration time per pixel\n(forward direction)\nEnsure this is at least twice the modulation time constant", "tip speed (backward direction)",
                                                     "max current", "V_calibration\n(use this voltage for calibrating the height)\nSet to zero to use the begin and end voltages"],
                              values = [-2, 100, 2, 1, 30, 2000, 0], digits = [2, 0, 2, 2, 2, 1, 2], limits = [[-10, 10], [0, 10000], [-10, 10], [0, 1000], [.01, 10000], [.01, 10000], [-10, 10]],
                              units = ["V", "mV", "V", "ms", "nm/s", "pA", "V"])
        self.setup_buttons(gui = gui, states = [{"tooltip": "state 1", "color": gui.colors["blue"]}])

    def run(self):
        mla = self.mla
        
        try:
            self.logprint(f"Initializing the experiment", message_type = "message")
            mla.link()
            
            (pixels, _) = mla.lockin.get_pixels(2)
            print(pixels)
            
            mla.lockin.start_lockin()
            (pixels, _) = mla.lockin.get_pixels(2)
            print(pixels)
            fs = mla.lockin.get_frequencies()
            print(fs)
            
            mla.lockin.stop_lockin()
            mla.unlink()
        
        except Exception as e:
            self.logprint(f"{e}", message_type = "error")
            self.abort_requested = True
        finally:
            self.cleanup()
            self.experiment_finished()



    def cleanup(self):
        try:
            self.logprint("Cleaning up")
        except:
            pass
        return

