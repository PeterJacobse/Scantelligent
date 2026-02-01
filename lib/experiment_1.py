from .api_nanonis import NanonisAPI
from time import sleep
import numpy as np



class Experiment1(NanonisAPI):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.abort_flag = False

    def run(self):
        
        self.connect()
        self.logprint("Hello from experiment 1", message_type = "message")
        (tip_status, error) = self.tip_update({"withdraw": True}, auto_connect = False, auto_disconnect = False)
        self.logprint(f"{error}", message_type = "message")

        sleep(1)
        self.check_abort_flag()
        
        self.logprint("Look at this witchcraft. I will move the tip to the opposite corner!", message_type = "warning")
        [x_tip_nm, y_tip_nm] = [tip_status.get(value) for value in ["x (nm)", "y (nm)"]]
        [x_tip_nm, y_tip_nm] = [-value for value in [x_tip_nm, y_tip_nm]]
        self.logprint(f"New tip position will be: x = {x_tip_nm} nm, y = {y_tip_nm} nm", message_type = "message")
        tip_status.update({"x (nm)": x_tip_nm, "y (nm)": y_tip_nm})
        self.tip_update(tip_status, auto_connect = False, auto_disconnect = False)

        sleep(1)
        self.check_abort_flag()

        current_frame = self.frame_update(auto_connect = False, auto_disconnect = False)
        self.logprint("Dont mind me playing with the scan frame")
        for angle in np.linspace(0, 4 * np.pi, 300):
            offset_nm = [200 * np.cos(angle), 200 * np.sin(angle)]
            angle_deg = -5 * angle * 180 / np.pi
            self.frame_update({"offset (nm)": offset_nm, "angle (deg)": angle_deg}, auto_connect = False, auto_disconnect = False)
            sleep(.05)
        
        self.disconnect()
        self.logprint("Experiment 1 finished!", message_type = "success")
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


