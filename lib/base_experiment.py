import os, time, h5py, types
from PyQt6.QtCore import QObject, pyqtSignal
import numpy as np
from datetime import datetime
from .file_functions import FileFunctions



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
        
        self.mla = kwargs.pop("mla", None)
        self.nanonis = kwargs.pop("nanonis", None)
        
        self.file_functions = FileFunctions()
        self.gui_setup = {}
        self.abort_requested = False
        self.current_spikes = 0
        self.feedback_changed = False
        self.start_parameters = {}
        self.gui_parameters = {"combobox": None, "line_edits": [None], "buttons": [None]}
        
        super().__init__()
        
        self.tia_corrections = ""
        if isinstance(self.sct_folder, str) and os.path.isdir(self.sct_folder):
            try:
                sys_folder = os.path.join(self.sct_folder, "sys")
                with h5py.File(os.path.join(sys_folder, "TIA_corrections.hdf5"), "r") as f:
                    datasets = {key: value for key, value in f.items() if isinstance(value, h5py.Dataset)}
                    self.tia_corrections = {key: datasets[key][:] for key in datasets.keys()}
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
        if view_name in ["none", "nanonis", "camera"]:
            self.parameters.emit({"dict_name": "view_request", "view": view_name})
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

    def connection_test(self, amplitude_mV: float = 200, frequency_Hz: float = 600, output_port: int = 1, verbose: bool = True, autophase: bool = True) -> str:
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

    def mla_amplitude_sweep(self, amplitudes = np.ndarray, settle_pixels: int = 1, pixels_per_datapoint: int = 4, measurement: object = None, setup_defaults: bool = True) -> np.ndarray:
        # In the future, more complicated data acquisitions can be passed rather than just mla.get_pixels
        if measurement: self.logprint(f"Measurements other than data pixel acquisitions are not yet supported for frequency sweeps.", message_type = "error")
        measurement = lambda: 2 * self.mla.get_pixels(pixels_per_datapoint, average = True)
        
        # Initialize the MLA.
        if setup_defaults:
            input_mask = np.full((32), 2, dtype = int)
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
        [channel_names.append(f"|a{i + 2}| (nS)") for i in range (30)]
        self.prepare_graph(channel_names)
        
        measurement_array = np.empty((len(amplitudes), len(channel_names)), dtype = float)



        # Main loop
        n_total = len(amplitudes)
        self.mla.start_lockin()
        for index, amp_mV in enumerate(amplitudes):
            self.check_abort_request()
            self.task_progress.emit(int(100 * index / n_total))
            self.mla.amplitudes_update({"amplitudes (mV)": {0: amp_mV}}, verbose = False)
            
            self.mla.get_pixels(settle_pixels)
            (pix_V, pix_V_var) = measurement()
            
            pix_pA = pix_V / tia_gain_V_per_pA
            pix_nS = pix_pA / amp_mV
            
            data_chunk = np.zeros((len(channel_names)), dtype = float)
            data_chunk[0] = amp_mV
            data_chunk[1] = np.abs(pix_nS[0])
            data_chunk[2] = np.real(pix_nS[1])
            data_chunk[3:] = np.abs(pix_nS[2:])
            
            self.data_array.emit(data_chunk)
            measurement_array[index] = data_chunk
        
        self.task_progress.emit(100)
        return (measurement_array, channel_names)

    def mla_voltage_sweep(self, voltages = np.ndarray, settle_pixels: int = 1, pixels_per_datapoint: int = 4, measurement: object = None, setup_defaults: bool = True) -> np.ndarray:
        # In the future, more complicated data acquisitions can be passed rather than just mla.get_pixels
        if measurement: self.logprint(f"Measurements other than data pixel acquisitions are not yet supported for frequency sweeps.", message_type = "error")
        measurement = lambda: 2 * self.mla.get_pixels(pixels_per_datapoint, average = True)
        
        # Initialize the MLA.
        if setup_defaults:
            input_mask = np.full((32), 2, dtype = int)
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
        if mod_voltage_mV < .001:
            (amplitudes_dict, error) = self.mla.amplitudes_update({"amplitudes (mV)": {0: .05}}) # Default to a minimum of 50 uV amplitude if the amplitude is too close to zero
            self.logprint(f"Warning. Very low modulation amplitude set. Calculated conductance values may diverge.")
        mod_voltage_mV = amplitudes_dict.get("amplitudes (mV)")[0]

        # Prepare to plot these channels
        channel_names = ["V_port1 (V)", "Re(a1) (nS)"]
        [channel_names.append(f"|a{i + 2}| (nS)") for i in range (31)]
        self.prepare_graph(channel_names)
        
        measurement_array = np.empty((len(voltages), len(channel_names)), dtype = float)



        # Main loop
        self.mla.start_lockin()
        for index, voltage in enumerate(voltages):
            n_total = len(voltages)
            self.check_abort_request()
            self.task_progress.emit(int(100 * index / n_total))
            self.mla.bias_update({"port_1 (V)": voltage}, verbose = False)
            
            self.mla.get_pixels(settle_pixels)
            (pix_V, pix_V_var) = measurement()
            
            pix_pA = pix_V / tia_gain_V_per_pA
            pix_nS = pix_pA / mod_voltage_mV
            
            data_chunk = np.zeros((len(channel_names)), dtype = float)
            data_chunk[0] = voltage
            data_chunk[1] = np.real(pix_nS[0])
            data_chunk[2:] = np.abs(pix_nS[1:])
            
            self.data_array.emit(data_chunk)
            measurement_array[index] = data_chunk
        
        self.task_progress.emit(100)
        return (measurement_array, channel_names)



    def experiment_handler(run):
        def wrapper(self):
            self.logprint("Starting the experiment", "success")
            self.start_parameters.update({"gui": self.gui_parameters})
            
            if hasattr(self, "nanonis"):
                (nanonis_parameters, error) = self.nanonis.initialize(verbose = False)
                self.start_parameters.update({"nanonis": nanonis_parameters})
            
            if hasattr(self, "mla") and self.mla.status == "running":
                (mla_parameters, error) = self.mla.initialize(verbose = False)
                self.start_parameters.update({"mla": mla_parameters})
            
            try:
                run(self)
            except AbortedError:
                self.logprint("Experiment aborted.", message_type = "error")
            except Exception as e:
                self.logprint(f"Error: {e}", message_type = "error")
                self.abort_requested = True
            finally:
                try: self.output_file.close()
                except: pass
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

