import os, time, h5py, types
from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np
from datetime import datetime
from .file_functions import FileFunctions
from .data_processing import DataProcessing
from .api_mla import MLAAPI # For type checking only
from .api_nanonis import NanonisAPI # For type checking only



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
        self.sct_folder = kwargs.pop("scantelligent_folder", None)
        
        self.mla: MLAAPI = kwargs.pop("mla", None)
        self.nanonis: NanonisAPI = kwargs.pop("nanonis", None)
        
        self.file_functions = FileFunctions()
        self.data = DataProcessing() # You can use self.data to access data processing functions. However, do not use self.data.scan_processing_flags to communicate with the GUI. Use self.scan_processing_flags instead
        self.gui_setup = {}
        self.abort_requested = False
        self.current_spikes = 0
        self.feedback_changed = False
        self.start_parameters = {}
        self.luts = {}
        self.gui_parameters = {}
        
        super().__init__()
        
        # Read look-up tables
        if isinstance(self.sct_folder, str) and os.path.isdir(self.sct_folder):
            try:
                sys_folder = os.path.join(self.sct_folder, "sys")
                with h5py.File(os.path.join(sys_folder, "LUTs.hdf5"), "r") as f:
                    datasets = {key: value for key, value in f.items() if isinstance(value, h5py.Dataset)} # Filter out datasets from the items in the HDF5 file
                    self.luts.update({key: datasets[key][:] for key in datasets.keys() if key in ["LN 10^9", "LN 10^8", "LN 10^7"]}) # Transimpedance amplifier corrections are stored as a dict with key given by the TIA setting name
                    
                    # Retrieve the temperature diode calibration
                    if "DT-670" in datasets.keys(): self.luts.update({"DT-670": datasets["DT-670"][:]})
            except:
                pass



    def logprint(self, message: str = "", message_type: str = "error"):
        return self.message.emit(message, message_type)

    def pass_mla_status(self, status: str) -> None:
        self.parameters.emit({"dict_name": "mla_status", "status": status})
        return

    def pass_nanonis_status(self, status: str = "") -> None:
        self.parameters.emit({"dict_name": "nanonis_status", "status": status})
        return

    def set_view(self, view_name: str = "none") -> None:
        if view_name in ["none", "nanonis", "camera", "graph"]: self.parameters.emit({"dict_name": "view_request", "view": view_name})
        return

    def prepare_gui(self) -> None:
        self.gui_setup.update({"dict_name": "gui_setup"})
        self.parameters.emit(self.gui_setup)
        return

    def prepare_scan_channels(self, entries: list = []) -> None:
        channels_dict = {name: i for i, name in enumerate(entries)} | {"dict_name": "channels"}
        self.parameters.emit({"dict_name": "scan_metadata", "channel_dict": channels_dict})
        return

    def prepare_hdf5(self) -> None:
        self.output_file = h5py.File(self.experiment_file, "w") # Open the new HDF5 file
        date_time_group = self.output_file.create_group("date_time")
        date_time_group.attrs.update({"date": datetime.now().strftime("%Y/%m/%d"), "start_time": datetime.now().strftime("%H:%M:%S")})
        
        # Fetch the temperature using a Nanonis call and conversion using a lookup table
        if "DT-670" in self.luts.keys():
            temp_calib = self.luts["DT-670"]
            try:
                # Find the signal index corresponding to the temperature sensor
                metadata = self.start_parameters["nanonis"].get("scan_metadata")
                signal_dict = metadata.get("signal_dict")                
                for key, value in signal_dict.items():
                    if "temperature" in key.lower():
                        temp_channel = value
                        break
                
                result = None
                if temp_channel: (result, error) = self.nanonis.signals_update([temp_channel], samples = 4, verbose = False)
                if result:
                    temp_V = result[temp_channel][1]
                    temp_K = float(np.interp(temp_V, temp_calib[:, 0][::-1], temp_calib[:, 1][::-1]))
                    temp_group = self.output_file.create_group("temperature")
                    temp_group.attrs.update({"temperature (K)": temp_K})
            except:
                pass
        
        # Add the bias, grid and tip data
        [bias, feedback, grid, tip, hardware] = [self.start_parameters["nanonis"].get(key) for key in ["bias", "feedback", "grid", "tip_status", "hardware"]]
        grid_group = self.output_file.create_group("grid")
        grid_group.attrs.update({key: grid.get(key) for key in ["offset (nm)", "scan_range (nm)", "angle (deg)", "pixels", "lines"]})
        tip_group = self.output_file.create_group("tip_status")
        tip_group.attrs.update({"start_location (x, y, z) (nm)": [tip.get(f"{dim} (nm)") for dim in ["x", "y", "z"]], "start_current (pA)": tip.get(f"I (pA)")})

        feedback.pop("dict_name")
        feedback_group = self.output_file.create_group("bias_feedback_settings")
        feedback_group.attrs.update({"V_Nanonis (V)": bias.get(f"V_nanonis (V)")} | feedback)
        feedback_group.attrs.update({"feedback on": tip.get("feedback")})
        active_controller = feedback.get("active_controller", "")
        
        if "mla" in self.start_parameters.keys():
            mla_bias = self.start_parameters["mla"].get("mla_bias", {})
            feedback_group.attrs.update({"MLA port_1 (V)": mla_bias.get("port_1 (V)", "unknown"), "MLA port_2 (V)": mla_bias.get("port_2 (V)", "unknown")})
        
        tia_group = self.output_file.create_group("transimpedance_amplifier")
        [tia_gain, tia_gain_V_per_pa] = [hardware.get(key, "unknown") for key in ["current_gain", "gain (V/pA)"]]
        tia_group.attrs.update({"TIA gain setting": tia_gain, "TIA gain (V/pA)": tia_gain_V_per_pa})
        return

    def connection_test(self, amplitude_mV: float = 200, frequency_Hz: float = 600, output_port: int = 1, verbose: bool = True, autophase: bool = False) -> str:
        """
        Returns which device the STM bias cable is connected to, and autophases the lockin amplifier for the corresponding device
        """
        nn = self.nanonis
        mla = self.mla
        if verbose: self.logprint(f"Testing and autophasing the lock-in amplifier, starting with Nanonis", message_type = "message")
        
        lockin_signal_names = ["LI Demod 1 X (A)", "LI Demod 1 Y (A)"]
        (signal_dict, error) = nn.signals_update(lockin_signal_names, verbose = verbose) # Retrieve the signal indices for more efficient lookup
        lockin_signal_indices = [signal_dict.get(signal)[0] for signal in lockin_signal_names]
        (lockin, error) = nn.lockin_update({"mod1": {"on": True, "amplitude (mV)": amplitude_mV, "frequency (Hz)": frequency_Hz, "phase (deg)": 0}, "mod2": {"on": True}}, verbose = verbose)
        (signal_dict, error) = nn.signals_update(lockin_signal_indices, verbose = False)
        [li_x_pA, li_y_pA] = [signal_dict[index][1] * 1E12 for index in lockin_signal_indices]
        li_complex_pA = (li_x_pA + 1j * li_y_pA)
        
        if np.abs(li_complex_pA) < 10:
            if verbose: self.logprint(f"I cannot measure a response from Nanonis from the applied modulation. I will check if the cable is connected to the MLA instead.", message_type = "warning")
            
            try:
                # Start up the MLA if it wasn't started yet. Save the current parameters to self.start_parameters so the MLA can be reset later
                if not "mla" in self.start_parameters.keys():
                    (mla_parameters, error) = self.mla.initialize(verbose = False)
                    self.start_parameters.update({"mla": mla_parameters})
                [time_constant, mla_bias, amplitudes_dict, frequencies_dict, outputs_dict] = [self.start_parameters["mla"].get(key) for key in ["time_constant", "mla_bias", "amplitudes", "frequencies", "outputs"]]
                
                # Set parameters for conenction test
                output_numbers = np.arange(0, 32)
                output_numbers[0] = 1
                input_multiplexer = np.full((32), 2, dtype = int)
                input_multiplexer[0] = 1
                mla.set_input_multiplexer(input_multiplexer)
                amplitudes = np.zeros((32), dtype = float)
                amplitudes[0] = 200
                mla.lockin_update({"df (Hz)": frequency_Hz, "numbers": output_numbers, "amplitudes (mV)": amplitudes}, verbose = verbose)
                mla.outputs_update({"blank": True, "mod0": {"on": True, "port": output_port}}, verbose = verbose)
                
                mla.start_lockin()
                
                mla.get_pixels(2)
                (pix, pix_var) = mla.get_pixels(100, average = True)
                mla.stop_lockin()
                li_complex_V = pix[1]
                print(f"MLA: {li_complex_V = }")
                
                if np.abs(li_complex_V) < .1:
                    if verbose: self.logprint(f"I cannot measure a response from the MLA either!", message_type = "error")
                    return "none"
                
                if autophase:
                    li_phase = np.rad2deg(np.angle(li_complex_V))
                    phases = np.zeros((32), dtype = float)
                    phases[0] = 90 - li_phase
                    mla.phases_update({"phases (deg)": phases}, verbose = verbose)
                    if verbose: self.logprint(f"The MLA seems to be connected. I autophased the lockin amplifier to {phases[0]:.4f} degree", message_type = "message")
                
                # Calculate the capacitance
                if verbose:
                    (hardware, error) = nn.hardware_update()
                    if "gain (V/pA)" in hardware.keys():
                        li_complex_pA = li_complex_V / hardware["gain (V/pA)"]
                        cap_fC = np.abs(1000 * li_complex_pA / (2 * np.pi * frequency_Hz * amplitude_mV))
                        self.logprint(f"The tip-sample capacitance as measured by the MLA is {cap_fC:.4f} fC", message_type = "message")
                    else:
                        self.logprint(f"I could not read the tia gain and therefore I do not know the tip-sample capacitance, but the voltage amplitude response is {np.abs(li_complex_V):.4f} V", message_type = "message")
                                
                # Reset the MLA
                try:
                    mla.lockin_update({"df (Hz)": time_constant.get("df (Hz)"), "frequencies (Hz)": frequencies_dict.get("frequencies (Hz)"), "port_1 (V)": mla_bias.get("port_1 (V)"), "port_2 (V)": mla_bias.get("port_1 (V)"),
                                        "amplitudes (mV)": amplitudes_dict.get("amplitudes (mV)"), "outputs": outputs_dict.get("outputs")}, verbose = verbose)
                except Exception as e:
                    self.logprint(f"{type(e)}: {e}", message_type = "error")
                return "mla"
            
            except Exception as e:
                try:
                    mla.lockin_update({"df (Hz)": time_constant.get("df (Hz)"), "frequencies (Hz)": frequencies_dict.get("frequencies (Hz)"), "port_1 (V)": mla_bias.get("port_1 (V)"), "port_2 (V)": mla_bias.get("port_1 (V)"),
                                        "amplitudes (mV)": amplitudes_dict.get("amplitudes (mV)"), "outputs": outputs_dict.get("outputs")}, verbose = verbose)
                except Exception as e2:
                    self.logprint(f"{type(e2)}: {e2}", message_type = "error")
                self.logprint(f"Problem ancountered while trying to run the MLA. {type(e)}: {e}", message_type = "error")
                return "none"
        
        if autophase:
            li_phase = np.rad2deg(np.angle(li_complex_pA))
            new_phase = li_phase - 90
            (lockin, error) = nn.lockin_update({"mod1": {"on": True, "amplitude (mV)": amplitude_mV, "frequency (Hz)": frequency_Hz, "phase (deg)": new_phase}, "mod2": {"on": False}}, verbose = verbose)
            if verbose: self.logprint(f"Nanonis lockin amplifier autophased to {new_phase:.4f} degree", message_type = "message")
        nn.lockin_update({"mod1": {"on": False}}, verbose = verbose)
        
        if verbose:
            cap_fC = np.abs(1000 * li_complex_pA / (2 * np.pi * frequency_Hz * amplitude_mV))
            self.logprint(f"The tip-sample capacitance as measured by Nanonis is {cap_fC:.4f} fC", message_type = "message")
        return "nanonis"



    def experiment_handler(run):
        def wrapper(self: BaseExperiment):
            self.logprint("Starting the experiment", "success")
            self.start_parameters.update({"gui": self.gui_parameters})
            
            if hasattr(self, "nanonis"):
                (nanonis_parameters, error) = self.nanonis.initialize(verbose = False)
                self.start_parameters.update({"nanonis": nanonis_parameters})
            
            if hasattr(self, "mla") and self.mla.status == "running":
                (mla_parameters, error) = self.mla.initialize(verbose = False)
                self.start_parameters.update({"mla": mla_parameters})
            
            # Create the experiment HDF5 file
            self.prepare_hdf5()


            
            # Run the core experiment
            try:
                run(self)
            except AbortedError:
                self.logprint("Experiment aborted.", message_type = "error")
            except Exception as e:
                self.logprint(f"Error: {e}", message_type = "error")
                self.abort_requested = True
            finally:
                try: self.output_file["date_time"].attrs.update({"end_time": datetime.now().strftime("%H:%M:%S"), "experiment_aborted": self.abort_requested})
                except: pass
                try: self.output_file.close()
                except: pass
                self.finish_experiment()
        return wrapper

    def nanonis_scan(self, direction: str = "down", timeout_s: int = 100000, dataset: h5py.Dataset = None, iterations: int = 10, verbose: bool = True) -> np.ndarray:
        if verbose: self.logprint(f"Starting a scan in the {direction} direction", message_type = "message")
        self.nanonis.scan_action({"action": "start", "direction": direction})
        
        (scan_metadata, error) = self.nanonis.scan_metadata_update(verbose = False) # Calling scan_metadata_update refreshes the channels that are being recorded, so that they can be selected
        channel_dict = scan_metadata.get("channel_dict")
        channel_indices = channel_dict.values()
        
        # Loop to check scan progress
        t_start = time.time()
        t_elapsed = 0
        for iteration in range(1000000):
            # Monitor and emit data while scanning
            (tip_status, error) = self.nanonis.tip_update(wait = False, fast_mode = True, verbose = False)
            if not error:
                [x_nm, y_nm, z_nm, I_pA] = [tip_status.get(parameter) for parameter in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
                self.data_array.emit(np.array([t_elapsed, x_nm, y_nm, z_nm, I_pA], dtype = np.float16))
            
            channel_index = self.scan_processing_flags.get("channel_index")
            backward = self.scan_processing_flags.get("backward")
            
            if channel_index in channel_indices:
                (scan_image, error) = self.nanonis.scan_update(channel = channel_index, backward = backward, verbose = False)
                nan_mask = np.isnan(scan_image)
                scan_finished = not bool(np.any(nan_mask))
            
            if iteration % iterations == 0: self.scan_data_update(channel_indices, dataset) # Every so many iterations, retrieve all data by looping over all recorded channels and scan directions and save to the dataset
            
            self.check_abort_request()
            time.sleep(.05)            
            t_elapsed = time.time() - t_start
            if t_elapsed > timeout_s: break
            if scan_finished:
                self.logprint("Scan finished", message_type = "message")
                break
        
        scan_data = self.scan_data_update(channel_indices, dataset)        
        if verbose: self.logprint(f"Scan completed", message_type = "success")
        return (scan_image, scan_data)

    def scan_data_update(self, channel_indices: list | np.ndarray, dataset: h5py.Dataset) -> None:
        scan_data = np.zeros(dataset.shape, dtype = np.float32)
        
        for index, channel_index in enumerate(channel_indices):
            (forward_scan, error) = self.nanonis.scan_update(channel = channel_index, backward = False, verbose = False, emit_image = False)
            (backward_scan, error) = self.nanonis.scan_update(channel = channel_index, backward = True, verbose = False, emit_image = False)
            dataset[0, index] = forward_scan
            dataset[1, index] = backward_scan
            scan_data[0, index] = forward_scan
            scan_data[1, index] = backward_scan
        return scan_data

    def check_abort_request(self, withdraw: bool = False) -> None:
        if self.thread().isInterruptionRequested():
            self.abort_requested = True
            if withdraw:
                try: self.nanonis.tip_update({"withdraw": True})
                except: pass
            raise AbortedError
        return

    def finish_experiment(self) -> None:
        self.logprint("Starting cleanup sequence", message_type = "message")
        
        # Try to reset Nanonis
        try:
            self.nanonis.scan_action({"action": "stop"})
            if self.feedback_changed: self.nanonis.tip_update({"z_rel (nm)": 1})
            
            # Read the start parameters and try to reset all of them
            nanonis_parameters = self.start_parameters.get("nanonis")
            if not isinstance(nanonis_parameters, dict):
                raise Exception("")
            
            [grid, lockin_parameters, feedback_parameters, speed_parameters, bias, tip_status] = [nanonis_parameters.get(key, None) for key in ["grid", "lockin", "feedback", "speeds", "bias", "tip_status"]]
            if grid: self.nanonis.grid_update(grid, verbose = False)
            if lockin_parameters: self.nanonis.lockin_update(lockin_parameters, verbose = False)
            V_nanonis = round(bias.get("V_nanonis (V)", None), 2)
            if isinstance(V_nanonis, float | int): self.nanonis.bias_update({"V_nanonis (V)": V_nanonis}, verbose = False)
            self.nanonis.feedback_update(feedback_parameters, verbose = False)
            self.nanonis.speeds_update(speed_parameters, verbose = False)
            
            withdrawn = tip_status.get("withdrawn")
            fb = tip_status.get("feedback")
            self.nanonis.tip_update({"feedback": fb, "withdrawn": withdrawn})
        except Exception as e:
            self.logprint(f"Problem encountered while trying to reset Nanonis. I could not read the start parameters. {e}", message_type = "error")
        
        try:
            # Read the start parameters and try to reset all of them
            mla_parameters = self.start_parameters.get("mla")
            if isinstance(mla_parameters, dict):
                [time_constant, mla_bias, amplitudes_dict, frequencies_dict, outputs_dict] = [self.start_parameters["mla"].get(key) for key in ["time_constant", "mla_bias", "amplitudes", "frequencies", "outputs"]]
                self.mla.lockin_update({"df (Hz)": time_constant.get("df (Hz)"), "frequencies (Hz)": frequencies_dict.get("frequencies (Hz)"), "port_1 (V)": mla_bias.get("port_1 (V)"), "port_2 (V)": mla_bias.get("port_2 (V)"),
                                        "amplitudes (mV)": amplitudes_dict.get("amplitudes (mV)"), "output_masks": outputs_dict.get("output_masks")}, verbose = False)
        except Exception as e:
            self.logprint(f"Problem encountered while trying to reset the MLA. I could not read the start parameters. {e}", message_type = "error")

        if not self.abort_requested:
            self.logprint("Experiment finished!", message_type = "success")
            self.exp_progress.emit(100)
        else:
            self.logprint("Experiment aborted and cleanup sequence finished.", message_type = "error")
        self.finished.emit()
        return

