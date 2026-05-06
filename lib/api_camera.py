import numpy as np
from PyQt6 import QtCore
import cv2



class CameraAPI(QtCore.QObject):
    frame_captured = QtCore.pyqtSignal(np.ndarray)
    finished = QtCore.pyqtSignal()

    def __init__(self, hw_config: dict = {}, message_callback = None, status_callback = None):
        self.message_callback = lambda message, message_type: print(message)
        if message_callback: self.message_callback = message_callback
        self.status_callback = print
        if status_callback: self.status_callback = status_callback
        
        super().__init__()
        self.running = False
        self.status = "offline"
        self.configure(hw_config)



    def configure(self, hw_config):
        if "camera" in [key.lower() for key in hw_config.keys()] and isinstance(hw_config["camera"], dict): camera_config = hw_config.get("camera")
        else: camera_config = hw_config

        tags = ["index", "argument", "camera_index", "camera_argument"]
        for entry in camera_config.keys():
            if entry in tags:
                index = camera_config[entry]

        try:
            self.cap = cv2.VideoCapture(index)
            if self.cap.isOpened():
                self.status_callback("online")
                self.status = "online"
            else:
                raise Exception("Unable to open the camera")            
        except:
            self.status = "offline"
            self.status_callback("offline")
        
        

    def run(self):
        self.running = True
        
        if not self.cap.isOpened():
            self.message_callback("Error. Could not open camera.", "error")
            self.running = False
            self.finished.emit()
            self.status_callback("offline")
            return
        
        self.status_callback("running")
        while self.running:
            (ret, frame) = self.cap.read()
            
            if ret:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb_frame = cv2.convertScaleAbs(rgb_frame, alpha = 2, beta = -100)
                self.frame_captured.emit(rgb_frame)
            else:
                self.message_callback("Warning: Failed to read frame from camera.", "error")
                break

            self.check_abort()

        try:
            if self.cap: self.cap.release()
        except:
            pass
        self.running = False
        
        self.finished.emit() # Notify the main thread that the work is done
        self.status_callback("idle")
        self.message_callback("Camera thread ended", "message")
        return

    def check_abort(self):
        if self.thread().isInterruptionRequested():
            self.running = False
        return
