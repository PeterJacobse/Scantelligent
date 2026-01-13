import numpy as np
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
import cv2
from time import sleep

colors = {"red": "#ff4040", "green": "#00ff00", "white": "#ffffff", "blue": "#0080ff"}



class CameraWorker(QObject):
    """
    Worker to handle the cv2.VideoCapture loop.
    It runs in a separate QThread and emits frames as NumPy arrays.
    """
    frameCaptured = pyqtSignal(np.ndarray) # Signal to send the processed RGB NumPy frame data back to the GUI
    finished = pyqtSignal() # Signal to indicate that the capture loop has finished
    message = pyqtSignal(str, str)

    def __init__(self, camera_index = 0):
        super().__init__()
        self.camera_index = camera_index
        self._running = False
        self.cap = None

    def start_capture(self):
        # Initializes video capture and starts the frame-reading loop.
        if self._running: # The running flag is already true; do not start another capture
            return

        self._running = True
        """
        self.cap = cv2.VideoCapture(self.camera_index)
        
        if not self.cap.isOpened():
            self.message.emit(f"Error. Could not open camera {self.camera_index}.", "red")
            self._running = False
            self.finished.emit()
            return
            
        # Optimization: Set a reasonable resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        """ 
        # Main video-reading loop controlled by the _running flag
        while self._running:
            frame = np.random.rand((10, 10))
            self.frameCaptured.emit(frame)
            sleep(.2)
            """
            ret, frame = self.cap.read()
            if ret:
                # IMPORTANT: Convert BGR (OpenCV default) to RGB 
                # as pyqtgraph expects RGB or Grayscale data.
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frameCaptured.emit(rgb_frame)
            else:
                # Exit loop if frame read fails (e.g., camera unplugged)
                self.message.emit("Warning: Failed to read frame from camera.")
                break
            """

        # Cleanup code runs when the while loop exits
        if self.cap:
             self.cap.release()
        self._running = False
        self.finished.emit() # Notify the main thread that the work is done

    def stop_capture(self):
        # Sets the flag to stop the capture loop cleanly.
        self._running = False



class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)



class TaskWorker(QRunnable):
    def __init__(self, target_function, *args, **kwargs):
        super().__init__()
        self.target_function = target_function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        try:
            result = self.target_function(*self.args, **self.kwargs)
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()

import traceback
import sys



class Worker(QRunnable):
    """
    Worker thread to run a function in a separate thread.
    """
    def __init__(self, target_function, *args, **kwargs):
        super().__init__()
        self.target_function = target_function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self):
        """
        Initialize the runner function with passed args, kwargs, and emit signals.
        """
        try:
            # Execute the function with arguments
            result = self.target_function(*self.args, **self.kwargs)
        except:
            # Handle exceptions and emit error signal
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        else:
            # Emit result signal on success
            self.signals.result.emit(result)
        finally:
            # Emit finished signal
            self.signals.finished.emit()