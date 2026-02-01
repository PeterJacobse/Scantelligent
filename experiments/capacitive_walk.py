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
        move_dict = {"h_steps": 1, "V_hor (V)": 200, "direction": "s"}
        
        (parameter_dict, error) = self.get_parameter_values(lockin_names, auto_disconnect = False)

        lockin_values = [list(parameter_dict.values())]
        for i in range(10):
            self.check_abort_flag()
            self.progress.emit(i * 10)
            
            self.coarse_move(move_dict)
            sleep(1)
            (parameter_dict, error) = self.get_parameter_values(lockin_names, auto_disconnect = False)
            lockin_values.append(list(parameter_dict.values()))

            self.data_array.emit(np.array(lockin_values, dtype = float))
        
        self.disconnect()
        self.progress.emit(100)
        self.logprint("Capacitive walk finished!", message_type = "success")
        self.finished.emit()
    
    def abort(self):
        self.logprint("Experiment 1 was aborted!", message_type = "error")
        self.abort_flag = True

    def check_abort_flag(self):
        if self.abort_flag:
            self.abort_flag = False
            self.disconnect()
            self.finished.emit()
            return True
        return False


