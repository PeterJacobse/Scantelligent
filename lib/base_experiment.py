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
    
    def __init__(self, *args, **kwargs):
        hw_config = kwargs.pop("hw_config", None)        
        super().__init__()
        self.abort_requested = False
        self.hw_config = hw_config
        self.logprint(f"Class BaseExperiment instantiated with hw_config {self.hw_config}", message_type = "message")
        # Note:
        # Instantiation of NanonisHardware triggers a connection test, and an exception is raised when the connection fails
        # The exception is caught in Scantelligent rather than here
        self.abort_flag = False

    def logprint(self, message: str = "", message_type: str = "error"):
        return self.message.emit(message, message_type)

    def setup_line_edits(self, gui, tooltips: list = [], values: list = [], digits: list = [], limits: list = [], units: list = []) -> None:
        self.logprint("Setting up line edits")
        self.line_edits = [gui.line_edits[f"experiment_{i}"] for i in range(3)]
        for list_object in [tooltips, digits, limits, units]:
            if len(list_object) > 2: list_object = list_object[:2]
        
        [self.line_edits[index].changeToolTip(tooltip) for index, tooltip in enumerate(tooltips)]
        [self.line_edits[index].setDigits(digits) for index, digits in enumerate(digits)]
        [self.line_edits[index].setLimits(limits) for index, limits in enumerate(limits)]
        [self.line_edits[index].setValue(value) for index, value in enumerate(values)]
        [self.line_edits[index].setUnit(unit) for index, unit in enumerate(units)]
        return

    def setup_combobox(self, gui, tooltip: str = "", items: list = []) -> None:
        self.direction_combobox = gui.comboboxes["direction"]
        self.direction_combobox.renewItems(items)
        return

    def toggle_view(self, target: str = "nanonis") -> None:

        return

    def read_parameters_from_gui(self) -> dict:
        parameters = {"dict_name": "gui_parameters"}
        if hasattr(self, "line_edits"): parameters.update({"line_edits": [self.line_edits[i].getValue() for i in range(3)]})
        if hasattr(self, "direction_combobox"): parameters.update({"direction_combobox": self.direction_combobox.currentText()})
        return parameters        

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

    def disconnect_hardware(self) -> False:
        if hasattr(self, "nanonis"): self.nanonis.unlink()
        return

    def check_abort_request(self):
        if self.thread().isInterruptionRequested():
            self.logprint("Experiment aborted", message_type = "error")
            self.abort_requested = True
        return

    def experiment_finished(self):
        if not self.abort_requested:
            self.logprint("Experiment finished", message_type = "success")
            self.task_progress.emit(100)
            self.exp_progress.emit(100)
        
        self.disconnect_hardware()
        
        self.finished.emit()
        return
    
    def gui_not_found_error(self):
        self.logprint("This experiment reads parameters from the Scantelligent GUI, but the GUI could not be found or initialized properly", message_type = "error")
        return
