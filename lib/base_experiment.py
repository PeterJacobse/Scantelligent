from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np
from . import NanonisAPI, CameraAPI, MLAAPI, KeithleyAPI



class BaseExperiment(QObject):
    connection = pyqtSignal(str) # This signal emits 'running' on connect, 'idle' after disconnect and 'offline' after an error to indicate the TCP connection status to the gui/program
    task_progress = pyqtSignal(int) # Integer between 0 and 100 to indicate the progress of a task
    exp_progress = pyqtSignal(int) # Integer between 0 and 100 to indicate the progress of the experiment
    message = pyqtSignal(str, str) # First argument is the message string, sedond argument is the message type, like 'warning', 'code', 'result', 'message', or 'error'
    parameters = pyqtSignal(dict) # Any parameters dictionary sent through this signal should include a self-reference 'dict_name' such that the receiver can read it and understand what kind of parameters they are
    image = pyqtSignal(np.ndarray) # A two-dimensional np.ndarray that is plotted in the gui when sent
    finished = pyqtSignal() # Signal to indicate an experiment is finished. Emission of this signal is connected to cleanup
    data_array = pyqtSignal(np.ndarray) # 2D array of collected data, with columns representing progression of the experiment and the rows being the different parameters being measured
    
    def __init__(self, parent, hw_config: dict):
        super().__init__()
        self.abort_requested = False
        self.hw_config = hw_config
        # Note:
        # Instantiation of NanonisHardware triggers a connection test, and an exception is raised when the connection fails
        # The exception is caught in Scantelligent rather than here
        self.abort_flag = False
        self.scantelligent = parent
        if hasattr(self.scantelligent, "data"): self.data = self.scantelligent.data

    def logprint(self, message: str = "", message_type: str = "error"):
        return self.message.emit(message, message_type)

    def connect_hardware(self, target: str = "nanonis") -> None:
        match target:
            case "nanonis":
                self.nanonis = NanonisAPI(hw_config = self.hw_config)
            case "keithley":
                self.keithley = KeithleyAPI(hw_config = self.hw_config)
            case "mla":
                self.mla = MLAAPI(hw_config = self.hw_config)
            case "camera":
                self.camera = CameraAPI(hw_config = self.hw_config)
            case _:
                pass
        
        return

    def check_abort_request(self):
        if self.thread().isInterruptionRequested():
            self.logprint("Experiment aborted", message_type = "error")
            self.abort_requested = True
        return

    def experiment_finished(self):
        self.logprint("Experiment finished", message_type = "success")
        self.finished.emit()
        return
