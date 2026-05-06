from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np
from . import NanonisAPI, CameraAPI, MLAAPI, KeithleyAPI
import time
import h5py



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
        self.hw_config = kwargs.pop("hw_config", None)
        self.scan_processing_flags = kwargs.pop("scan_processing_flags", None)
        self.experiment_file = kwargs.pop("experiment_file", None)

        self.gui_setup = {}
        self.abort_requested = False
        self.start_parameters = {}
        self.gui_parameters = {"combobox": None, "line_edits": [None], "buttons": [None]}
        
        super().__init__()



    def logprint(self, message: str = "", message_type: str = "error"):
        return self.message.emit(message, message_type)

    def pass_mla_status(self, status: str) -> None:
        self.parameters.emit({"dict_name": "mla_status", "status": status})
        return

    def pass_nanonis_status(self, status: str = "") -> None:
        self.parameters.emit({"dict_name": "nanonis_status", "status": status})
        return

    def prepare_gui(self) -> None:
        self.gui_setup.update({"dict_name": "gui_setup"})
        self.parameters.emit(self.gui_setup)
        return



    def experiment_handler(run):
        def wrapper(self):
            self.logprint("Starting the experiment", "success")
            self.start_parameters.update({"gui": self.gui_parameters})
            
            self.output_file = h5py.File(self.experiment_file, "w")
            try:
                self.output_file.attrs.update({"mla_parameters": self.start_parameters["mla"]})
            except Exception as e:
                self.logprint(f"{e}")
            
            try:
                run(self)
            except AbortedError:
                self.logprint("Experiment aborted.", message_type = "error")
            except Exception as e:
                self.logprint(f"Error: {e}", message_type = "error")
                self.abort_requested = True
            finally:
                self.output_file.close()
                self.finish_experiment()
        return wrapper

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
            
            channel_index = self.scan_processing_flags.get("channel_index")
            backward = self.scan_processing_flags.get("backward")
            
            (scan_image, error) = self.nanonis.scan_update(channel = channel_index, backward = backward, verbose = False)
            nan_mask = np.isnan(scan_image)
            scan_finished = not bool(np.any(nan_mask))
            self.check_abort_request()
            time.sleep(.05)
            
            if scan_finished:
                self.logprint("Scan finished", message_type = "message")
                break
        
        return scan_image

    def connect_hardware(self, target: str = "nanonis") -> None:
        match target:
            case "nanonis":
                self.nanonis = NanonisAPI(hw_config = self.hw_config, status_callback = self.pass_nanonis_status, message_callback = self.logprint)
                self.nanonis.parameters.connect(self.parameters.emit)
                self.nanonis.task_progress.connect(self.task_progress.emit)
                
                (nanonis_parameters, error) = self.nanonis.initialize(verbose = False)
                self.start_parameters.update({"nanonis": nanonis_parameters})
            
            case "keithley":
                self.keithley = KeithleyAPI(hw_config = self.hw_config)

            case "mla":
                self.mla = MLAAPI(hw_config = self.hw_config, status_callback = self.pass_mla_status, message_callback = self.logprint)
                self.mla.parameters.connect(self.parameters.emit)
                
                (mla_parameters, error) = self.mla.lockin_update()
                self.start_parameters.update({"mla": mla_parameters})

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
            try: self.nanonis.unlink()
            except Exception as e: self.logprint(f"Error while unlinking Nanonis: {e}", message_type = "error")

        if hasattr(self, "mla"):
            try: self.mla.unlink()
            except Exception as e: self.logprint(f"Error while unlinking the MLA: {e}", message_type = "error")

        if not self.abort_requested:
            self.logprint("Experiment finished!", message_type = "success")
            self.exp_progress.emit(100)
        else:
            self.logprint("Experiment aborted and cleanup sequence finished.", message_type = "error")
        self.finished.emit()
        return

