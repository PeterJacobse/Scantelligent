import numpy as np
from PyQt6 import QtCore
import cv2, time
from .base_experiment import AbortedError



class CameraAPI(QtCore.QObject):
    captured_frame = QtCore.pyqtSignal(np.ndarray)
    parameters = QtCore.pyqtSignal(dict)
    finished = QtCore.pyqtSignal()

    def __init__(self, hw_config: dict = {}):
        super().__init__()
        self.status = "offline"
        self.hw_config = hw_config
        self.home_thread = QtCore.QCoreApplication.instance().thread()



    def initialize(self) -> None:
        if "camera" in [key.lower() for key in self.hw_config.keys()] and isinstance(self.hw_config["camera"], dict): camera_config = self.hw_config.get("camera")
        else: camera_config = self.hw_config

        tags = ["index", "argument", "camera_index", "camera_argument"]
        for entry in camera_config.keys():
            if entry in tags:
                index = camera_config[entry]
        
        self.index = index

        try:
            self.cap = cv2.VideoCapture(index)
            if self.cap.isOpened():
                self.status = "online"
                self.send_status(self.status)
            else:
                self.status = "offline"
                self.send_status(self.status)
                raise Exception("Unable to open the camera")            
        except Exception as e:
            self.status = "offline"
            self.send_status(self.status)
            raise Exception(e)
        return

    def send_status(self, status: str = "") -> None:
        self.parameters.emit({"dict_name": "camera_status", "status": status})
        return

    def grab_frame(self) -> object:
        try: self.cap.open(self.index)
        except: pass
        
        if not self.cap.isOpened():
            self.initialize()
            time.sleep(.1)
        
        (ret, frame) = self.cap.read()
        if ret:
            adjusted = frame.astype(float) * 2 + (-100)
            rgb_frame = np.clip(adjusted, 0, 255).astype(np.uint8)
            rgb_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_BGR2RGB)
            self.captured_frame.emit(rgb_frame)
        else:
            raise Exception
        return rgb_frame

    def run(self) -> None:
        self.home_thread = QtCore.QCoreApplication.instance().thread()
        self.status = "running"
        try: self.cap.open(self.index)
        except: pass
        
        if not self.cap.isOpened():
            self.initialize()
            time.sleep(.1)
        
        if not self.cap.isOpened():
            self.status = "offline"
            self.send_status(self.status)
            self.moveToThread(self.home_thread)
            self.finished.emit()
            return
        
        self.send_status(self.status)
        try:
            while self.status == "running":
                time.sleep(.1)
                if self.thread().isInterruptionRequested():
                    self.abort_requested = True
                    raise AbortedError
                
                (ret, frame) = self.cap.read()
                if ret:
                    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                    rgb_frame = cv2.convertScaleAbs(rgb_frame, alpha = 2, beta = -100)
                    self.captured_frame.emit(rgb_frame)
                else:
                    raise Exception
        finally:
            self.status = "idle"
            
            try:
                self.send_status(self.status)
                self.cap.release()
            except:
                pass
            
            self.moveToThread(self.home_thread)
            self.finished.emit() # Notify the main thread that the work is done
        return

