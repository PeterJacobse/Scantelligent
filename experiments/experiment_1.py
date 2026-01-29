#from .api_nanonis import NanonisAPI
from time import sleep
import numpy as np



class Experiment1(NanonisAPI):
    def __init__(self):
        super().__init__()

    def run(self):
        
        self.connect()
        self.logprint("Hello from experiment 1", message_type = "message")
        (tip_status, error) = self.tip_update({"withdraw": True}, auto_connect = False, auto_disconnect = False)

        sleep(1)

        self.logprint("Look at this witchcraft. I will move the tip to the opposite corner!", message_type = "warning")
        [x_tip_nm, y_tip_nm] = [tip_status.get(value) for value in ["x_nm", "y_nm"]]
        [x_tip_nm, y_tip_nm] = [-value for value in [x_tip_nm, y_tip_nm]]
        tip_status.update({"x_nm": x_tip_nm, "y_nm": y_tip_nm})
        self.tip_update(tip_status, auto_connect = False, auto_disconnect = False)

        sleep(1)

        self.logprint("I am at 50 percent!", message_type = "success")
        self.progress.emit(50)

        sleep(1)

        current_frame = self.frame_update(auto_connect = False, auto_disconnect = False)
        self.logprint("Dont mind me playing with the scan frame")
        for angle in np.linspace(0, 4 * np.pi, 300):
            offset_nm = 200 * [np.cos(angle), np.sin(angle)]
            angle_deg = -5 * angle * 180 / np.pi
            self.frame_update({"offset_nm": offset_nm, "angle_deg": angle}, auto_connect = False, auto_disconnect = False)
            sleep(.1)
        
        self.disconnect()

