import sys, os
from time import sleep, time
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import NanonisAPI



class Experiment(NanonisAPI):
    def __init__(self, parent, *args, **kwargs):        
        # 'parent' is a reference to the Scantelligent app itself. It is passed by default when loading the experiment in Scantelligent
        super().__init__(parent, parent.hardware)
        self.line_edits = [parent.gui.line_edits[f"experiment_{i}"] for i in range(3)]
        self.direction_box = parent.gui.comboboxes["direction"]
        
        # Correct way to set tooltip hints and units for the parameter fields in the Scantelligent GUI
        self.direction_box.renewItems(["n", "e", "s", "w"])

        self.line_edits[0].changeToolTip("Coarse steps per iteration")
        self.line_edits[0].setDigits(0)
        self.line_edits[0].setLimits([0, 1000])
        self.line_edits[0].setValue(10)        
        
        self.line_edits[1].changeToolTip("Number of iterations")
        self.line_edits[1].setDigits(0)
        self.line_edits[1].setLimits([0, 10000])
        self.line_edits[1].setValue(200)        

        self.line_edits[2].changeToolTip("Modulators (0: off; 1: 1 on; 2: 2 on; 3: both on)")
        self.line_edits[2].setDigits(0)
        self.line_edits[2].setLimits([0, 3])
        self.line_edits[2].setValue(3)

        [self.line_edits[i].setUnit(unit) for i, unit in enumerate(["steps", "", ""])]



    def run(self) -> None:
        # Correct way to extract data from the line edits
        exp_par = [self.line_edits[i].getValue() for i in range(3)]
        direction = self.direction_box.currentText()
        move_dict = {"h_steps": exp_par[0], "V_hor (V)": 200, "direction": direction}
        lockin_names = ["LI Demod 1 X (A)", "LI Demod 1 Y (A)", "LI Demod 2 X (A)", "LI Demod 2 Y (A)"]
        channels_dict = {i: name for i, name in enumerate(lockin_names)}
        channels_dict.update({"dict_name": "channels"})
        self.parameters.emit(channels_dict) # This triggers the GUI to start tracking and graphing data

        # Start
        self.link()
        self.logprint("Experiment capacitive_walk started", message_type = "success")
        self.scantelligent.toggle_view("camera")

        # Switch on the modulators
        (self.old_lockin_parameters, error) = self.lockin_update()
        match exp_par[2]:
            case 0: self.lockin_update({"modulator_1": {"on": False}, "modulator_2": {"on": False}})
            case 1: self.lockin_update({"modulator_1": {"on": True}, "modulator_2": {"on": False}})
            case 2: self.lockin_update({"modulator_1": {"on": False}, "modulator_2": {"on": True}})
            case 3: self.lockin_update({"modulator_1": {"on": True}, "modulator_2": {"on": True}})
            case _:
                self.logprint("Invalid modulator parameter provided", "error")
                self.cleanup()
        
        [mod1_dict, mod2_dict] = [self.old_lockin_parameters.get(f"modulator_{i + 1}") for i in range(2)]
        [mod1_f, mod1_V] = [mod1_dict.get(quantity) for quantity in ["frequency (Hz)", "amplitude (mV)"]]
        [mod2_f, mod2_V] = [mod1_dict.get(quantity) for quantity in ["frequency (Hz)", "amplitude (mV)"]]


        
        # Start the measurement loop
        for iter in range(exp_par[1]):
            self.check_abort()
            if self.abort_flag:
                break
            
            cycles = 4
            lockin_values = []
            for averaging_cycle in range(cycles):
                (parameter_dict, error) = self.get_parameter_values(lockin_names)
                lockin_values.append(list(parameter_dict.values()))
                sleep(.2)
            lockin_avgs = np.array([np.sum(lockin_values, axis = 0) / cycles], dtype = float)

            # Translate displacement currents into capacitances
            #for i, I_displ_A in enumerate(lockin_avgs):
            #    caps_fF = 1E15 * I_displ_A / (2 * np.pi * mod1_f * mod1_V)

            self.coarse_move(move_dict)
            self.progress.emit(int(100 * iter / exp_par[1]))
            self.data_array.emit(lockin_values_total)
            sleep(.5)
        
        if not self.abort_flag: self.logprint("Experiment capacitive_walk finished", "success")
        self.cleanup()
        return



    def cleanup(self) -> None:
        # Reset the lockin modulators to their original state
        [mod1_dict, mod2_dict] = [self.old_lockin_parameters.get(f"modulator_{i + 1}") for i in range(2)]
        [mod1_on, mod2_on] = [mod_dict.get("on") for mod_dict in [mod1_dict, mod2_dict]]
        
        self.lockin_update({"modulator_1": {"on": mod1_on}, "modulator_2": {"on": mod2_on}})

        self.unlink()
        self.finished.emit()
        return

