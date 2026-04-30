from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np
from . import NanonisAPI, CameraAPI, MLAAPI, KeithleyAPI
import time



class AbortedError(Exception):
    def __init__(self):
        super().__init__()



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
        parent = kwargs.pop("scantelligent", None)
        if not parent: parent = kwargs.pop("parent", None)
        
        super().__init__()

        self.abort_requested = False
        self.hw_config = hw_config
        self.sct = parent
        self.logprint(f"Class BaseExperiment instantiated with hw_config {self.hw_config}", message_type = "message")

    def logprint(self, message: str = "", message_type: str = "error"):
        return self.message.emit(message, message_type)

    def prepare_gui(self, setup: dict = {}) -> None:
        if not hasattr(self, "sct"):
            self.logprint("Error setting up the gui. Scantelligent not found", message_type = "error")
            return
        if not hasattr(self.sct, "gui"):
            self.logprint("Error setting up the gui. Scantelligent GUI not found", message_type = "error")
            return
        
        self.logprint(f"{setup = }")
        
        try:
            combobox_dict = setup.get("combobox", {})
            self.setup_combobox(items = combobox_dict.get("items", []))
            
            line_edits_dict = setup.get("line_edits", {})
            self.setup_line_edits(tooltips = line_edits_dict.get("tooltips", []), values = line_edits_dict.get("values", []), digits = line_edits_dict.get("digits", []),
                                  limits = line_edits_dict.get("limits", []), units = line_edits_dict.get("units", []))
            
            buttons_dict = setup.get("buttons", {})
            self.setup_buttons(states = buttons_dict.get("states"))
        except Exception as e:
            self.logprint(f"Error setting up the gui: {e}")
        return

    def setup_line_edits(self, tooltips: list = [], values: list = [], digits: list = [], limits: list = [], units: list = []) -> None:
        self.line_edits = [self.sct.gui.line_edits[f"experiment_{index}"] for index in range(9)]
        #[self.line_edits[index].show() for index in range(9)]
        #[self.line_edits[index].setTooltip(f"Experiment parameter field {index}\ngui.line_edits[\"experiment_{index}\"]") for index in range(9)]
        #[self.line_edits[index].setUnit("") for index in range(9)]
        #[self.line_edits[index].setValue(None) for index in range(9)]

        [self.line_edits[index].changeToolTip(tooltip) for index, tooltip in enumerate(tooltips)]
        [self.line_edits[index].setDigits(digits) for index, digits in enumerate(digits)]
        [self.line_edits[index].setLimits(limits) for index, limits in enumerate(limits)]
        [self.line_edits[index].setValue(value) for index, value in enumerate(values)]
        [self.line_edits[index].setUnit(unit) for index, unit in enumerate(units)]
        
        max_number = max([len(key) for key in [tooltips, digits, limits, values, units]])
        #[self.line_edits[index].hide() for index in range(max_number, 9)]
        return

    def setup_combobox(self, tooltip: str = "", items: list = []) -> None:        
        self.direction_combobox = self.sct.gui.comboboxes["direction"]
        self.direction_combobox.renewItems(items)
        
        self.logprint(f"{self.direction_combobox}.renewItems({items})")
        return

    def setup_buttons(self, states: list = []) -> None:
        self.buttons = [self.sct.gui.buttons[f"experiment_{i}"] for i in range(9)]
        
        single_button_states = states[0]
        self.buttons[0].setStates(single_button_states)
        return



    def experiment_handler(run):
        def wrapper(self):
            self.logprint("Starting the experiment", "success")
            
            self.start_parameters = {}
            if hasattr(self, "nanonis"):
                (nanonis_parameters, error) = self.nanonis.initialize(verbose = False)
                self.start_parameters.update({"nanonis": nanonis_parameters})
            
            gui_parameters = self.read_parameters_from_gui()
            self.start_parameters.update({"gui": gui_parameters})
            
            try:
                run(self)
            except AbortedError:
                self.logprint("Experiment aborted.", message_type = "error")
            except Exception as e:
                self.logprint(f"Error: {e}", message_type = "error")
                self.abort_requested = True
            finally:
                self.finish_experiment()
        return wrapper

    def toggle_view(self, target: str = "nanonis") -> None:
        return

    def monitor_scan(self, channel, timeout_s: int = 100000) -> np.ndarray:
        channels_dict = {i: name for i, name in enumerate(["t (s)", "x (nm)", "y (nm)", "z (nm)", "I (pA)"])} | {"dict_name": "channels"}
        self.parameters.emit(channels_dict) # This triggers the GUI to start graphing data

        # Loop to check scan progress
        t_start = time.time()
        t_elapsed = 0

        while t_elapsed < timeout_s:
            t_elapsed = time.time() - t_start
            (tip_status, error) = self.nanonis.tip_update(wait = False, fast_mode = True, verbose = False)
            [x_nm, y_nm, z_nm, I_pA] = [tip_status.get(parameter) for parameter in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
            self.data_array.emit(np.array([[t_elapsed, x_nm, y_nm, z_nm, I_pA]]))
            
            channel_index = self.sct.data.scan_processing_flags.get("channel_index")
            backward = self.sct.data.scan_processing_flags.get("backward")
            
            (scan_image, error) = self.nanonis.scan_update(channel = channel_index, backward = backward, verbose = False)
            nan_mask = np.isnan(scan_image)
            scan_finished = not bool(np.any(nan_mask))
            self.check_abort_request()
            time.sleep(.05)
            
            if scan_finished:
                self.logprint("Scan finished", message_type = "message")
                break
        
        return scan_image

    def read_parameters_from_gui(self) -> dict:
        parameters = {"dict_name": "gui_parameters"}
        if hasattr(self, "line_edits"): parameters.update({"line_edits": [self.line_edits[i].getValue() for i in range(9)]})
        if hasattr(self, "direction_combobox"): parameters.update({"direction_combobox": self.direction_combobox.currentText()})
        if hasattr(self, "buttons"): parameters.update({"buttons": [self.buttons[i].state for i in range(9)]})
        return parameters

    def connect_hardware(self, target: str = "nanonis") -> None:
        match target:
            case "nanonis":
                if not hasattr(self.sct, "nanonis"):
                    raise Exception("Error. Nanonis not found")
                else:
                    self.nanonis = self.sct.nanonis
            case "keithley":
                self.keithley = KeithleyAPI(hw_config = self.hw_config)
            case "mla":
                self.mla = MLAAPI(hw_config = self.hw_config)
            case "camera":
                self.camera = CameraAPI(hw_config = self.hw_config)
            case _:
                pass
        
        return

    def check_abort_request(self) -> None:
        if self.thread().isInterruptionRequested():
            self.abort_requested = True
            raise AbortedError
        return

    def finish_experiment(self) -> None:
        self.logprint("Starting cleanup sequence", message_type = "message")
        
        if hasattr(self, "nanonis"):
            try:
                nanonis_parameters = self.start_parameters.get("nanonis", {})
                
                self.nanonis.scan_action({"action": "stop"})
                
                grid = nanonis_parameters.get("grid", None)
                if grid: self.nanonis.grid_update(grid)

                self.nanonis.tip_update({"z_rel (nm)": 1})
                
                lockin_parameters = nanonis_parameters.get("lockin", {})
                self.nanonis.lockin_update(lockin_parameters)
                
                V_nanonis = round(nanonis_parameters.get("bias", {}).get("V_nanonis (V)", None), 2)
                if isinstance(V_nanonis, float | int): self.nanonis.bias_update({"V_nanonis (V)": V_nanonis})

                feedback_parameters = nanonis_parameters.get("feedback", {})
                self.nanonis.feedback_update(feedback_parameters)

                speed_parameters = nanonis_parameters.get("speeds", {})
                self.nanonis.speeds_update(speed_parameters)

                tip_parameters = nanonis_parameters.get("tip_status", {})
                fb = tip_parameters.get("feedback")
                self.nanonis.tip_update({"feedback": fb})
            except Exception as e:
                self.logprint(f"Error while resetting Nanonis: {e}", message_type = "error")
            try:
                self.nanonis.unlink()
            except: pass
            
            if not self.abort_requested:
                self.logprint("Experiment finished!", message_type = "success")
                self.exp_progress.emit(100)
            else:
                self.logprint("Experiment aborted and cleanup sequence finished.", message_type = "error")
            self.finished.emit()
        return

