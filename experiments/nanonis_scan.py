import sys, os
from time import sleep, time
import numpy as np

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import NanonisAPI



class Experiment(NanonisAPI):
    def __init__(self, parent, *args, **kwargs):
        
        # 'parent' is a reference to the Scantelligent app itself. It is passed by default when loading the experiment in Scantelligent
        super().__init__(parent.hardware)
        self.line_edits = [parent.gui.line_edits[f"experiment_{i}"] for i in range(3)]
        self.direction_box = parent.gui.comboboxes["direction"]
        
        # Correct way to set tooltip hints and units for the parameter fields in the Scantelligent GUI
        self.line_edits[0].changeToolTip("Timeout")
        self.line_edits[0].setValue(1000)
        
        self.line_edits[1].changeToolTip("From")
        self.line_edits[2].changeToolTip("Experiment")
        [self.line_edits[i].setUnit(unit) for i, unit in enumerate(["s", "nm", "pA"])]
        [self.line_edits[i].setValue(0) for i in range(1, 3)]

    def run(self):
        # Correct way to extract data from the line edits
        experiment_parameters = [self.line_edits[i].getValue() for i in range(3)]
        timeout = experiment_parameters[0]
        direction = self.direction_box.currentText()
        
        self.connect()
        self.logprint("Experiment nanonis_scan started", message_type = "success")
        
        t = time()
        (tip_status, error) = self.tip_update()
        [x, y, z] = [tip_status.get(f"{dim} (nm)") for dim in ["x", "y", "z"]]
        curr = tip_status.get("I (pA)")
        [t0, x0, y0, z0, curr0] = [t, x, y, z, curr]
        self.parameters.emit({"dict_name": "channels", 0: "time (s)", 1: "x (nm)", 2: "y (nm)", 3: "z (nm)", 4: "I (pA)"})
        
        match direction:
            case "up":
                self.scan_action({"action": "start", "direction": "up"})
            
            case "down":
                self.scan_action({"action": "start", "direction": "down"})
            
            case _:
                pass
        
        for iteration in range(1000):
            self.check_abort()
            if self.abort_flag:
                self.cleanup()
                break
            
            t = time() - t0
            (tip_status, error) = self.tip_update()
            [x, y, z] = [tip_status.get(f"{dim} (nm)") for dim in ["x", "y", "z"]]
            curr = tip_status.get("I (pA)")
        
            self.logprint(f"Elapsed time: {t}")
            if t > timeout:
                self.logprint("Timeout encountered", "warning")
                break
            
            self.frame_update()
            self.scan_metadata_update()
            print(self.data.processing_flags)
            
            sleep(1)

        if not self.abort_flag:
            self.logprint("Experiment nanonis_scan finished!", message_type = "success")
            self.cleanup()
        return
    
    def cleanup(self):        
        self.scan_action({"action": "stop"})
        self.disconnect()
        self.finished.emit()
        return

