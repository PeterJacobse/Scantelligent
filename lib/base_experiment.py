import time, h5py
from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np
from datetime import datetime



class AbortedError(Exception):
    def __init__(self):
        super().__init__()



class BaseExperiment(QObject):
    task_progress = pyqtSignal(int) # Integer between 0 and 100 to indicate the progress of a task
    exp_progress = pyqtSignal(int) # Integer between 0 and 100 to indicate the progress of the experiment
    message = pyqtSignal(str, str) # First argument is the message string, sedond argument is the message type, like 'warning', 'code', 'result', 'message', or 'error'
    parameters = pyqtSignal(dict) # Any parameters dictionary sent through this signal should include a self-reference 'dict_name' such that the receiver can read it and understand what kind of parameters they are
    image = pyqtSignal(np.ndarray) # A two-dimensional np.ndarray that is plotted in the gui when sent
    finished = pyqtSignal() # Signal to indicate an experiment is finished. Emission of this signal is connected to cleanup
    data_array = pyqtSignal(np.ndarray) # 2D array of collected data, with columns representing progression of the experiment and the rows being the different parameters being measured

    def __init__(self, *args, **kwargs):
        self.hw_config = kwargs.pop("hw_config", None) # Will become redundant again
        self.scan_processing_flags = kwargs.pop("scan_processing_flags", None)
        self.experiment_file = kwargs.pop("experiment_file", None)
        
        self.mla = kwargs.pop("mla", None)
        self.nanonis = kwargs.pop("nanonis", None)

        self.gui_setup = {}
        self.abort_requested = False
        self.current_spikes = 0
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
            
            if hasattr(self, "nanonis"):
                (nanonis_parameters, error) = self.nanonis.initialize(verbose = False)
                self.start_parameters.update({"nanonis": nanonis_parameters})
            
            if hasattr(self, "mla"):
                (mla_parameters, error) = self.mla.lockin_update()
                self.start_parameters.update({"mla": mla_parameters})
            
            self.output_file = h5py.File(self.experiment_file, "w")
            self.output_file.attrs.update({"date": datetime.now().strftime("%Y/%m/%d"), "time": datetime.now().strftime("%H:%M:%S")})
            
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
                #fb = tip_parameters.get("feedback")
                #self.nanonis.tip_update({"feedback": fb})
            except Exception as e:
                self.logprint(f"Error while resetting Nanonis: {e}", message_type = "error")
        
        if hasattr(self, "mla"):
            try:
                self.mla.outputs_update({"blank": True})
            except:
                pass

        if not self.abort_requested:
            self.logprint("Experiment finished!", message_type = "success")
            self.exp_progress.emit(100)
        else:
            self.logprint("Experiment aborted and cleanup sequence finished.", message_type = "error")
        self.finished.emit()
        return

