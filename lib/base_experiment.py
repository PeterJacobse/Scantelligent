import time, h5py, types
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
        self.feedback_changed = False
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

    def prepare_graph(self, entries: list = []) -> None:
        channels_dict = {i: name for i, name in enumerate(entries)} | {"dict_name": "channels"}
        self.parameters.emit(channels_dict)

    def prepare_scan_channels(self, entries: list = []) -> None:
        channels_dict = {name: i for i, name in enumerate(entries)} | {"dict_name": "channels"}
        self.parameters.emit({"dict_name": "scan_metadata", "channel_dict": channels_dict})
        return

    def mla_frequency_sweep(self, frequencies = np.ndarray, settle_pixels: int = 1, pixels_per_datapoint: int = 4, measurement: object = None, setup_defaults: bool = True) -> np.ndarray:
        # In the future, more complicated data acquisitions can be passed rather than just mla.get_pixels
        if measurement: self.logprint(f"Measurements other than data pixel acquisitions are not yet supported for frequency sweeps.", message_type = "error")
        measurement = lambda: 2 * self.mla.get_pixels(pixels_per_datapoint, average = True)
        
        if setup_defaults:
            self.mla.set_input_multiplexer([1, 2, 2])
            self.mla.outputs_update({"blank": True, "mod0": {"on": True, "port": 1}}) # Output modulator 1 onto port 1
        
        # Read the TIA gain and oscillator amplitude to be able to convert values
        (hardware_dict, error) = self.nanonis.hardware_update()
        tia_gain_V_per_pA = hardware_dict.get("gain (V/pA)")
        
        (amplitudes_dict, error) = self.mla.amplitudes_update()
        mod_voltage_mV = amplitudes_dict.get("amplitudes (mV)")[0]
        if mod_voltage_mV < .001: (amplitudes_dict, error) = self.mla.amplitudes_update({"amplitudes (mV)": {0: 500}}) # Default to 500 mV amplitude if the amplitude is too close to zero
        mod_voltage_mV = amplitudes_dict.get("amplitudes (mV)")[0]
        
        # Prepare to plot these channels
        channel_names = ["f1 (Hz)", "|a1_ref| (mV)", "arg(a1_ref) (rad)", "|a1| (mV)", "|a1| (pA)", "|C1| (fF)", "arg(a1) (rad)", "|a2| (mV)", "|a2| (pA)", "|C2| (fF)", "arg(a2) (rad)"]
        self.prepare_graph(channel_names)
        measurement_array = np.empty((len(frequencies), len(channel_names)), dtype = float)
        
        
        
        # Main loop
        self.mla.start_lockin()
        for index, f in enumerate(frequencies):
            self.check_abort_request()
            w = 2 * np.pi * int(f)
            self.mla.time_constant_update({"df (Hz)": int(f)}, verbose = False) # Set the measurement resolution to 200 Hz. This corresponds to a primitive time constant or period of 5 ms.
            self.mla.frequencies_update({"numbers": [1, 1, 2, 3]}, verbose = False) # Frequencies set in units of numbers of whole oscillations per period
            
            self.mla.get_pixels(settle_pixels)
            pix = measurement()
            
            a1refabs = 1000 * np.abs(pix[0]) # Output directly copied to the MLA port 1 in
            a1refarg = np.angle(pix[0])
            
            a1abs_mV = 1000 * np.abs(pix[1]) # Displacement currents measured through the TIA
            a1abs_pA = a1abs_mV / (1000 * tia_gain_V_per_pA)
            a1abs_fF = 1000000 * a1abs_pA / (w * mod_voltage_mV)
            a1arg = np.angle(pix[1])
            
            a2abs_mV = 1000 * np.abs(pix[2])
            a2abs_pA = a2abs_mV / (1000 * tia_gain_V_per_pA)
            a2abs_fF = 1000000 * a2abs_pA / (w * mod_voltage_mV)
            a2arg = np.angle(pix[2])
            
            data_chunk = np.array([f, a1refabs, a1refarg, a1abs_mV, a1abs_pA, a1abs_fF, a1arg, a2abs_mV, a2abs_pA, a2abs_fF, a2arg], dtype = float)
            self.data_array.emit(data_chunk)
            measurement_array[index] = data_chunk
        
        return (measurement_array, channel_names)

    def mla_amplitude_sweep(self, amplitudes = np.ndarray, settle_pixels: int = 1, pixels_per_datapoint: int = 4, measurement: object = None, setup_defaults: bool = True) -> np.ndarray:
        # In the future, more complicated data acquisitions can be passed rather than just mla.get_pixels
        if measurement: self.logprint(f"Measurements other than data pixel acquisitions are not yet supported for frequency sweeps.", message_type = "error")
        measurement = lambda: 2 * self.mla.get_pixels(pixels_per_datapoint, average = True)
        
        # Initialize the MLA.
        if setup_defaults:
            input_mask = 2 * np.ones(32)
            input_mask[0] = 1
            self.mla.set_input_multiplexer(input_mask)
            numbers = np.arange(0, 32)
            numbers[0] = 1
            self.mla.frequencies_update({"numbers": numbers})
            self.mla.outputs_update({"blank": True, "mod0": {"on": True, "port": 1}}) # Output modulator 1 onto port 1
        
        # Read the TIA gain and oscillator amplitude to be able to convert values
        (hardware_dict, error) = self.nanonis.hardware_update()
        tia_gain_V_per_pA = hardware_dict.get("gain (V/pA)")
                
        # Prepare to plot these channels
        channel_names = ["amp (mV)", "|a1_ref| (mV)", "Re(a1) (nS)"]
        [channel_names.append(f"|a{i}| (nS)") for i in range (30)]
        self.prepare_graph(channel_names)
        
        measurement_array = np.empty((len(amplitudes), len(channel_names)), dtype = float)



        # Main loop
        self.mla.start_lockin()
        for index, amp_mV in enumerate(amplitudes):
            self.check_abort_request()
            self.mla.amplitudes_update({"amplitudes (mV)": {0: amp_mV}}, verbose = False)
            
            self.mla.get_pixels(settle_pixels)
            pix_V = measurement()
            
            pix_pA = pix_V / tia_gain_V_per_pA
            pix_nS = pix_pA / amp_mV
            
            data_chunk = np.zeros((len(channel_names)), dtype = float)
            data_chunk[0] = amp_mV
            data_chunk[1] = np.abs(pix_nS[0])
            data_chunk[2] = np.real(pix_nS[1])
            data_chunk[3:] = np.abs(pix_nS[2:])
            
            self.data_array.emit(data_chunk)
            measurement_array[index] = data_chunk
        
        return (measurement_array, channel_names)

    def mla_voltage_sweep(self, voltages = np.ndarray, settle_pixels: int = 1, pixels_per_datapoint: int = 4, measurement: object = None, setup_defaults: bool = True) -> np.ndarray:
        # In the future, more complicated data acquisitions can be passed rather than just mla.get_pixels
        if measurement: self.logprint(f"Measurements other than data pixel acquisitions are not yet supported for frequency sweeps.", message_type = "error")
        measurement = lambda: 2 * self.mla.get_pixels(pixels_per_datapoint, average = True)
        
        # Initialize the MLA.
        if setup_defaults:
            input_mask = 2 * np.ones(32)
            input_mask[0] = 1
            self.mla.set_input_multiplexer(input_mask)
            numbers = np.arange(0, 32)
            numbers[0] = 1
            self.mla.frequencies_update({"numbers": numbers})
            self.mla.outputs_update({"blank": True, "mod0": {"on": True, "port": 1}}) # Output modulator 1 onto port 1
        
        # Read the TIA gain and oscillator amplitude to be able to convert values
        (hardware_dict, error) = self.nanonis.hardware_update()
        tia_gain_V_per_pA = hardware_dict.get("gain (V/pA)")
        (amplitudes_dict, error) = self.mla.amplitudes_update()
        mod_voltage_mV = amplitudes_dict.get("amplitudes (mV)")[0]
        if mod_voltage_mV < .001: (amplitudes_dict, error) = self.mla.amplitudes_update({"amplitudes (mV)": {0: .5}}) # Default to 500 uV amplitude if the amplitude is too close to zero
        mod_voltage_mV = amplitudes_dict.get("amplitudes (mV)")[0]

        # Prepare to plot these channels
        channel_names = ["V_port1 (V)", "Re(a1) (nS)"]
        [channel_names.append(f"|a{i}| (nS)") for i in range (31)]
        self.prepare_graph(channel_names)
        
        measurement_array = np.empty((len(voltages), len(channel_names)), dtype = float)



        # Main loop
        self.mla.start_lockin()
        for index, voltage in enumerate(voltages):
            self.check_abort_request()
            self.mla.bias_update({"port_1 (V)": voltage}, verbose = False)
            
            self.mla.get_pixels(settle_pixels)
            pix_V = measurement()
            
            pix_pA = pix_V / tia_gain_V_per_pA
            pix_nS = pix_pA / mod_voltage_mV
            
            data_chunk = np.zeros((len(channel_names)), dtype = float)
            data_chunk[0] = voltage
            data_chunk[1] = np.real(pix_nS[0])
            data_chunk[2:] = np.abs(pix_nS[1:])
            
            self.data_array.emit(data_chunk)
            measurement_array[index] = data_chunk
        
        return (measurement_array, channel_names)



    def experiment_handler(run):
        def wrapper(self):
            self.logprint("Starting the experiment", "success")
            self.start_parameters.update({"gui": self.gui_parameters})
            
            if hasattr(self, "nanonis"):
                (nanonis_parameters, error) = self.nanonis.initialize(verbose = False)
                self.start_parameters.update({"nanonis": nanonis_parameters})
            
            if hasattr(self, "mla") and hasattr(self.mla, "lockin"):
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

    def monitor_scan(self, output_channel = None, timeout_s: int = 100000) -> np.ndarray:
        (scan_metadata, error) = self.nanonis.scan_metadata_update() # Calling scan_metadata_update refreshes the channels that are being recorded, so that they can be selected
        channel_dict = scan_metadata.get("channel_dict")
        (frame, error) = self.nanonis.frame_update() # Calling frame_update refreshes the frame

        # Loop to check scan progress
        t_start = time.time()
        t_elapsed = 0

        while t_elapsed < timeout_s:
            t_elapsed = time.time() - t_start
            
            # Monitor and emit data while scanning
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
        
        # When the scan is finished, return the scan image
        if isinstance(output_channel, str) and output_channel in channel_dict.keys(): channel_index = channel_dict[output_channel]
        if isinstance(output_channel, int) and output_channel in channel_dict.values(): (scan_image, error) = self.nanonis.scan_update(channel = output_channel, send_data = False, backward = backward, verbose = False)
    
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
                self.nanonis.scan_action({"action": "stop"})
                if self.feedback_changed: self.nanonis.tip_update({"z_rel (nm)": 1})
                
                # Read the start parameters and try to reset all of them
                nanonis_parameters = self.start_parameters.get("nanonis", {})
                [grid, lockin_parameters, feedback_parameters, speed_parameters, bias, tip_status] = [nanonis_parameters.get(key, None) for key in ["grid", "lockin", "feedback", "speeds", "bias", "tip_status"]]
                if grid: self.nanonis.grid_update(grid)
                if lockin_parameters: self.nanonis.lockin_update(lockin_parameters)
                V_nanonis = round(bias.get("V_nanonis (V)", None), 2)
                if isinstance(V_nanonis, float | int): self.nanonis.bias_update({"V_nanonis (V)": V_nanonis})
                self.nanonis.feedback_update(feedback_parameters)
                self.nanonis.speeds_update(speed_parameters)
                
                fb = tip_status.get("feedback")
                self.nanonis.tip_update({"feedback": fb})
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

