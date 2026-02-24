import numpy as np
from PyQt6 import QtCore
import cv2



class CameraAPI(QtCore.QObject):
    frame_captured = QtCore.pyqtSignal(np.ndarray)
    finished = QtCore.pyqtSignal()
    message = QtCore.pyqtSignal(str, str)

    def __init__(self, config: dict = {}):
        super().__init__()
        self.running = False
        self.configure(config)
        success = self.cap.isOpened()
        if not success: raise
        else: pass

            
    
    def configure(self, config):
        if "camera" in config.keys() and isinstance(config["camera"], dict):
            config_data = config["camera"]
        else:
            config_data = config
        
        tags = ["index", "argument", "camera_index", "camera_argument"]
        for entry in config_data.keys():
            if entry in tags:
                index = config_data[entry]

        try:
            self.cap = cv2.VideoCapture(index)
        except:
            pass

    def run(self):
        self.running = True
        
        if not self.cap.isOpened():
            self.message.emit(f"Error. Could not open camera.", "error")
            self.running = False
            self.finished.emit()
            return
        
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
        self.message.emit("Camera thread ended", "message")
        return

    def check_abort(self):
        if self.thread().isInterruptionRequested():
            self.running = False
        return
