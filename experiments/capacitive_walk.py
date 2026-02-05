import sys, os
from time import sleep
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib import NanonisAPI



class Experiment(NanonisAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.abort_flag = False

    def run(self):
        
        self.connect()
        self.logprint("Hello from experiment capacitive walk!", message_type = "success")

        lockin_names = ["LI Demod 1 X (A)", "LI Demod 1 Y (A)", "LI Demod 2 X (A)", "LI Demod 2 Y (A)"]
        move_dict = {"h_steps": 1, "V_hor (V)": 200, "z_steps": 0, "V_ver (V)": 120, "direction": "s"}
        
        (parameter_dict, error) = self.get_parameter_values(lockin_names, auto_disconnect = False)

        lockin_values = [list(parameter_dict.values())]

        for i in range(40):
            self.check_abort_flag()
            self.progress.emit(int(.25 * i))
            
            (parameter_dict, error) = self.get_parameter_values(lockin_names, auto_disconnect = False)
            sleep(.2)
            (parameter_dict2, error) = self.get_parameter_values(lockin_names, auto_disconnect = False)
            sleep(.2)
            (parameter_dict3, error) = self.get_parameter_values(lockin_names, auto_disconnect = False)
            sleep(.2)
            (parameter_dict4, error) = self.get_parameter_values(lockin_names, auto_disconnect = False)
            sleep(.2)
            (parameter_dict5, error) = self.get_parameter_values(lockin_names, auto_disconnect = False)
            sleep(.2)
            (parameter_dict6, error) = self.get_parameter_values(lockin_names, auto_disconnect = False)
            sleep(.2)
            (parameter_dict7, error) = self.get_parameter_values(lockin_names, auto_disconnect = False)
            sleep(.2)
            (parameter_dict8, error) = self.get_parameter_values(lockin_names, auto_disconnect = False)
            sleep(.2)

            for key in parameter_dict.keys():
                parameter_dict[key] = (parameter_dict[key] + parameter_dict2[key] + parameter_dict3[key] + parameter_dict4[key] + parameter_dict5[key] + parameter_dict6[key] + parameter_dict7[key] + parameter_dict8[key]) / 8
            
            lockin_values.append(list(parameter_dict.values()))
            self.coarse_move(move_dict)
            sleep(1)

            self.data_array.emit(np.array(lockin_values, dtype = float))
        
        self.disconnect()
        self.progress.emit(100)
        self.logprint("Capacitive walk finished!", message_type = "success")
        self.finished.emit()

    def check_abort_flag(self):
        if self.abort_flag:
            self.abort_flag = False
            self.disconnect()
            self.finished.emit()
            return True
        return False


