import numpy as np
from PyQt6 import QtCore
import cv2



class CameraAPI(QtCore.QObject):
    frame_captured = QtCore.pyqtSignal(np.ndarray)
    finished = QtCore.pyqtSignal()
    message = QtCore.pyqtSignal(str, str)
    parameters = QtCore.pyqtSignal(dict)

    def __init__(self, hw_config: dict = {}):
        super().__init__()
        self.running = False
        self.configure(hw_config)
        success = self.cap.isOpened()
        if not success: raise
        else: pass



    def configure(self, hw_config):
        if "camera" in [key.lower() for key in hw_config.keys()] and isinstance(hw_config["camera"], dict): camera_config = hw_config.get("camera")
        else: camera_config = hw_config

        tags = ["index", "argument", "camera_index", "camera_argument"]
        for entry in camera_config.keys():
            if entry in tags:
                index = camera_config[entry]

        try:
            self.cap = cv2.VideoCapture(index)
            self.parameters.emit({"dict_name": "camera_status", "status": "running"})
        except:
            self.parameters.emit({"dict_name": "camera_status", "status": "offline"})
            raise

    def initialize(self):
        self.parameters.emit({"dict_name": "camera_status", "status": "online"})
        return

    def run(self):
        self.running = True
        
        if not self.cap.isOpened():
            self.message.emit(f"Error. Could not open camera.", "error")
            self.running = False
            self.finished.emit()
            self.parameters.emit({"dict_name": "camera_status", "status": "offline"})
            return
        
        self.parameters.emit({"dict_name": "camera_status", "status": "running"})        
        while self.running:
            (ret, frame) = self.cap.read()
            
            if ret:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                rgb_frame = cv2.convertScaleAbs(rgb_frame, alpha = 2, beta = -100)
                self.frame_captured.emit(rgb_frame)
            else:
                self.message.emit("Warning: Failed to read frame from camera.", "error")
                break

            self.check_abort()

        try:
            if self.cap: self.cap.release()
        except:
            pass
        self.running = False
        
        self.finished.emit() # Notify the main thread that the work is done
        self.parameters.emit({"dict_name": "camera_status", "status": "idle"})
        self.message.emit("Camera thread ended", "message")
        return

    def check_abort(self):
        if self.thread().isInterruptionRequested():
            self.running = False
        return
