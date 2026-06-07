import os, sys, time
from PyQt6 import QtCore
import numpy as np



class MLAAPI(QtCore.QObject):
    message = QtCore.pyqtSignal(str, str)
    parameters = QtCore.pyqtSignal(dict)    
    amplitudes = QtCore.pyqtSignal(list)
    frequency = QtCore.pyqtSignal(float)
    task_progress = QtCore.pyqtSignal(int)

    def __init__(self, hw_config: dict = {}, message_callback: object = None, status_callback: object = None, test_mode: bool = False):
        super().__init__()

        self.status_callback = lambda status: self.send_status(status) # Use a parameter dict to signal the status to ParameterManager
        if status_callback: self.status_callback = status_callback # If the user provides a callback function, use that instead
        self.message_callback = lambda message_str, message_type: self.logprint(message_str = message_str, message_type = message_type) # Default to PyQt signal-slot signaling
        if message_callback: self.message_callback = message_callback # For testing, e.g. in Jupyter, the user can pass a message_callback

        self.test_mode = test_mode
        
        mla_path = False
        if "mla" in hw_config.keys():
            mla_dict = hw_config["mla"]
            if "library_path" in mla_dict:
                mla_path = mla_dict["library_path"]
        
        if not isinstance(mla_path, str): raise Exception("Could not read the MLA library path")
        if not os.path.isdir(mla_path): raise Exception("The library path provided does not point to a valid folder")

        self.mla_path = mla_path

        sys.path.insert(0, mla_path)

        from mlaapi import mla_globals # These packages should become available if the MLA path is correct
        from mlaapi import mla_api
        
        settings = mla_globals.read_config()
        self.mla = mla_api.MLA(settings)
        self.lockin_running = False
        self.parameters_init()



    def parameters_init(self) -> None:
        self.df = 100 # Defaults, to be overwritten by the first call to time_constant_update()
        self.tm = 10
        self.V = [0, 0]
        self.output_masks = np.zeros((2, 32), dtype = int)
        self.input_mask = np.zeros((32), dtype = int)
        self.status = "online"
        self.status_callback(self.status)
        return

    def link(self) -> None:
        try:
            self.logprint("mla.link()", message_type = "code")
            time.sleep(.2)
            self.mla.connect(server_text_callback = lambda text: self.logprint(text, message_type = "result"), ping_attempts = 4)
            self.status = "running"
            self.set_defaults()
            try:
                self.status_callback(self.status)
            except Exception as e:
                self.status = "offline"
                self.status_callback(self.status)
                self.logprint(f"Error: {e}", message_type = "error")
        except Exception as e:
            self.logprint(f"Error while connecting to the MLA: {e}", message_type = "error")
            self.logprint(f"Unable to connect to the MLA; switching to test mode", message_type = "error")
            self.test_mode = True
            self.status = "offline"
            try: self.status_callback(self.status)
            except: pass
        return f"MLA status: {self.status}"

    def unlink(self) -> None:
        try:            
            self.reset_outputs()
            if self.lockin_running:
                self.get_pixels(1)
                self.stop_lockin()
        finally:
            self.mla.disconnect()
            self.status = "idle"
            try: self.status_callback(self.status)
            except: pass
        return f"MLA status: {self.status}"

    def initialize(self, verbose: bool = True) -> tuple[dict, bool | str]:
        return self.lockin_update(verbose = verbose)

    def start_lockin(self) -> None:
        self.lockin_running = True
        if not self.test_mode: self.mla.lockin.start_lockin()
        return

    def stop_lockin(self) -> None:
        self.lockin_running = False
        if not self.test_mode: self.mla.lockin.stop_lockin()
        return

    def logprint(self, message_str: str = "", message_type: str = "error") -> None:
        self.message.emit(message_str, message_type)
        return

    def send_status(self, status: str = "") -> None:
        status_dict = {"dict_name": "mla_status", "status": status}
        self.parameters.emit(status_dict)
        return



    # Set and get methods
    def set_defaults(self) -> None:
        self.reset_outputs()
        self.set_DACs_ADCs_safe_range()
        self.set_max_downsampling()
        
        numbers = np.arange(0, self.mla.lockin.nr_input_freq, dtype = int)
        numbers[0] = 1
        input_mask = np.full((self.mla.lockin.nr_input_freq), 2, dtype = int)
        input_mask[0] = 1
        self.lockin_update({"df (Hz)": 220, "numbers": numbers, "amplitudes (mV)": {0: 100}, "input_mask": input_mask}, verbose = False)
        
        self.expose_dIdV()
        return

    def reset_outputs(self) -> None:
        try: self.mla.lockin.reset_outputs()
        except Exception as e:
            self.logprint(f"{e}")
        return

    def get_pixels(self, number: int = 1, average: bool = False, bessel_correct: bool = True, data_format: str = "IQ", wait_for_new: bool = True) -> tuple[np.ndarray, None | np.ndarray]:
        """
        Returns MLA lockin measurements. When average is False, the first element returned is a 2D array comprising a list of pixels.
        When average is True, the list of pixels is turned into an average and the variance is returned as the second element.
        """
        if not self.lockin_running: raise Exception("Requesting locking data while it is not running. Call mla.start_lockin() first.")
        
        if self.test_mode:
            rng = np.random.default_rng()
            pix = .01 * rng.random((32, number), dtype = float) + .01j * rng.random((32, number), dtype = float)
            if average: pix = np.average(pix, axis = 1)
            self.parameters.emit({"dict_name": "pixels", "pixels": pix})
            return (pix, None)
        
        if wait_for_new: self.mla.lockin.wait_for_new_pixels(number)
        if data_format == "phase": (pix, _) = self.mla.lockin.get_pixels(number, data_format == "phase", unit = "deg")
        else: (pix, _) = self.mla.lockin.get_pixels(number)
        
        pix_var = None
        if average:
            pix_var = np.var(pix, axis = 1, ddof = int(bessel_correct))
            pix = np.average(pix, axis = 1)
        
        self.parameters.emit({"dict_name": "pixels", "pixels": pix})
        return (pix, pix_var)
    
    def get_phases(self, number_pixels: int = 1) -> np.ndarray:
        return self.get_pixels(number = number_pixels, average = True, data_format = "phase")

    def set_DACs_ADCs_safe_range(self) -> None:
        # Set all analog inputs to the correct configuration (range = +-20 V)
        self.mla.hardware.set_input_relay(1, se = True, nodamp = False, term = False, dc = True, gain = False, bypass = False, gain2 = False, event = True)
        self.mla.hardware.set_input_relay(2, se = True, nodamp = False, term = False, dc = True, gain = False, bypass = False, gain2 = False, event = True)
        self.mla.hardware.set_input_relay(3, se = True, nodamp = False, term = False, dc = True, gain = False, bypass = False, gain2 = False, event = True)
        self.mla.hardware.set_input_relay(4, se = True, nodamp = False, term = False, dc = True, gain = False, bypass = False, gain2 = False, event = True)
        self.set_12V_output(False)
        return

    def set_max_downsampling(self) -> None:
        # Typical sample rate is far too high; we do not need to measure in the MHz range
        self.mla.osc.set_downsampling(250)
        return

    def set_12V_output(self, value: bool = True):
        if not isinstance(value, bool): return
        self.mla.hardware.set_output_relay(1, bypass = not value, event = True)
        self.mla.hardware.set_output_relay(2, bypass = not value, event = True)
        return

    def set_input_multiplexer(self, port_array: np.ndarray | list) -> None:
        self.mla.lockin.set_input_multiplexer(port_array)
        return

    def set_output_masks(self, output_masks: np.ndarray | list) -> None:
        if len(output_masks) == 2:
            self.mla.lockin.set_output_mask(output_masks[0], port = 1, wait_for_effect = True)
            self.mla.lockin.set_output_mask(output_masks[1], port = 2, wait_for_effect = True)
        else:
            self.logprint("Output masks have the wrong shape")
        return

    def set_bias(self, port: int = 1, value: float = 0) -> None:
        self.mla.lockin.set_dc_offset(port = port, value = value)
        return

    def autophase(self, amplitude_mV: float = 500, verbose: bool = False) -> None:
        (amplitudes_dict, error) = self.amplitudes_update(verbose = False)
        if isinstance(amplitude_mV, float | int): self.amplitudes_update({"amplitudes (mV)": {0: amplitude_mV}}, verbose = verbose)
        self.outputs_update({"mod0": {"port": 1, "on": True}, "blank": True}, verbose = False)

        (phases_dict, error) = self.phases_update(verbose = False)
        phases = phases_dict.get("phases (deg)")

        self.start_lockin()
        for iteration in range(3):
            (pix, pix_var) = self.get_pixels(12, average = True, wait_for_new = True)
            measured_phases = np.rad2deg(np.angle(pix))
            delta_phase = 90 - measured_phases[1]
            drive_phase = phases[0] + delta_phase
            (phases_dict, error) = self.phases_update({"phases (deg)": {0: drive_phase}}, verbose = verbose)
            phases = phases_dict.get("phases (deg)")
                
        self.amplitudes_update({"amplitudes (mV)": amplitudes_dict.get("amplitudes (mV)")}, verbose = False)
        self.get_pixels(3, average = True, wait_for_new = True)
        self.stop_lockin()
        return

    def expose_dIdV(self, output_port: str = "A") -> None:
        if not output_port in ["A", "B", "C", "D"]: return
        self.mla.feedback.setup(gain = 1.0, offset = 0.0, output_port = "A")
        self.mla.feedback.set_feedback_type_slow(7)
        return



    # 'Update' methods that both take and apply parameters supplied to them and read from the mla
    def lockin_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        parameters_out = {"dict_name": "mla_parameters"}
        
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"mla.lockin_update({parameters})", message_type = "code")
                else: self.logprint("mla.lockin_update()", message_type = "code")
            
            if not self.status == "running" and not self.test_mode: self.link()
            
            # time_constant_update
            tm = parameters.get("tm (ms)", None)
            df = parameters.get("df (Hz)", None)
            if isinstance(df, float | int): (time_constant, error) = self.time_constant_update({"df (Hz)": df}, verbose = verbose)
            elif isinstance(tm, float | int): (time_constant, error) = self.time_constant_update({"tm (ms)": tm}, verbose = verbose)
            else: (time_constant, error) = self.time_constant_update(verbose = verbose)
            if error: raise Exception(error)
            else: parameters_out.update({time_constant.get("dict_name"): time_constant})
            
            # frequencies_update
            frequencies = parameters.get("frequencies (Hz)", None)
            numbers = parameters.get("numbers", None)
            times = parameters.get("times (ms)", None)
            if isinstance(frequencies, list | np.ndarray): (frequencies_dict, error) = self.frequencies_update({"frequencies (Hz)": frequencies}, verbose = verbose)
            elif isinstance(numbers, list | np.ndarray): (frequencies_dict, error) = self.frequencies_update({"numbers": numbers}, verbose = verbose)
            elif isinstance(times, list | np.ndarray): (frequencies_dict, error) = self.frequencies_update({"times (ms)": times}, verbose = verbose)
            else: (frequencies_dict, error) = self.frequencies_update(verbose = verbose)
            if error: raise Exception(error)
            else: parameters_out.update({frequencies_dict.get("dict_name"): frequencies_dict})
            
            # amplitudes update
            amplitudes = parameters.get("amplitudes (mV)", None)
            if isinstance(amplitudes, list | np.ndarray): (amplitudes_dict, error) = self.amplitudes_update({"amplitudes (mV)": amplitudes}, verbose = verbose)
            else: (amplitudes_dict, error) = self.amplitudes_update(verbose = verbose)
            if error: raise Exception(error)
            else: parameters_out.update({amplitudes_dict.get("dict_name"): amplitudes_dict})
            
            # phases update
            phases = parameters.get("phases (deg)", None)
            if isinstance(phases, list | np.ndarray): (phases_dict, error) = self.phases_update({"phases (deg)": phases}, verbose = verbose)
            else: (phases_dict, error) = self.phases_update(verbose = verbose)
            if error: raise Exception(error)
            else: parameters_out.update({phases_dict.get("dict_name"): phases_dict})
            
            # outputs update
            outputs_keys = {key: value for key, value in parameters.items() if key in ["blank", "output_masks", "mod0", "mod1", "mod2", "mod3"]}
            if len(outputs_keys) > 0: (outputs_dict, error) = self.outputs_update(outputs_keys, verbose = verbose)
            else: (outputs_dict, error) = self.outputs_update(verbose = verbose)
            if error: raise Exception(error)
            else: parameters_out.update({outputs_dict.get("dict_name"): outputs_dict})

            # outputs update
            inputs_keys = {key: value for key, value in parameters.items() if key in ["input_mask"]}
            if len(inputs_keys) > 0: (inputs_dict, error) = self.inputs_update(inputs_keys, verbose = verbose)
            else: (inputs_dict, error) = self.inputs_update(verbose = verbose)
            if error: raise Exception(error)
            else: parameters_out.update({inputs_dict.get("dict_name"): inputs_dict})
            
            # bias update
            bias_keys = {key: value for key, value in parameters.items() if key in ["port_1 (V)", "port_2 (V)"]}
            if len(bias_keys) > 0: (bias_dict, error) = self.bias_update(bias_keys, verbose = verbose)
            else: (bias_dict, error) = self.bias_update(verbose = verbose)
            if error: raise Exception(error)
            else: parameters_out.update({bias_dict.get("dict_name"): bias_dict})
            
            # Create an array that stacks all data
            try:
                output_masks = outputs_dict.get("output_masks")
                array = np.vstack(np.array([amplitudes_dict.get("amplitudes (mV)"), frequencies_dict.get("frequencies (Hz)"), phases_dict.get("phases (deg)"), output_masks[0], output_masks[1], inputs_dict.get("input_mask")]))
                array_channels = ["amplitudes (mV)", "frequencies (Hz)", "phases (deg)", "output_mask port 1", "output_mask port 2", "input_mask"]
                parameters_out.update({"array": array, "array_channels": array_channels})
            except:
                pass
            
            if verbose and len(parameters) < 1: self.logprint(f"{parameters_out}", message_type = "result", verbose = verbose)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (parameters_out, error)

    def time_constant_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        tc_dict = {"dict_name": "time_constant"}
        
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"mla.time_constant_update({parameters})", message_type = "code")
                else: self.logprint("mla.time_constant_update()", message_type = "code")
            
            if not self.status == "running" and not self.test_mode: self.link()
            
            # Read the time constant and df from the parameter dict. If both are given, df takes precedence
            tm = parameters.get("tm (ms)", None)
            df = parameters.get("df (Hz)", None)
            
            # Set
            if not self.test_mode:
                if isinstance(df, float | int): self.mla.lockin.set_df(df, wait_for_effect = True)
                elif isinstance(tm, float | int): self.mla.lockin.set_Tm(tm / 1000, wait_for_effect = True) # Default unit in Scantelligent is ms, not s
            
                # Read            
                self.tm = self.mla.lockin.get_Tm() * 1000 # Default unit in Scantelligent is ms, not s
                self.df = self.mla.lockin.get_df()
            else:
                if df:
                    self.df = df
                    self.tm = 1000 / df
            
            tc_dict.update({"tm (ms)": self.tm, "df (Hz)": self.df})
            self.parameters.emit(tc_dict)
            
            if verbose and len(parameters) < 1: self.logprint(f"{tc_dict}", message_type = "result")
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (tc_dict, error)

    def frequencies_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        freq_dict = {"dict_name": "frequencies"}
        
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"mla.frequencies_update({parameters})", message_type = "code")
                else: self.logprint("mla.frequencies_update()", message_type = "code")
            
            if not self.status == "running" and not self.test_mode: self.link()
            
            # Read the time constant and df from the parameter dict. If both are given, df takes precedence
            frequencies = parameters.get("frequencies (Hz)", None)
            numbers = parameters.get("numbers", None)
            times = parameters.get("times (ms)", None)
            if isinstance(times, list | np.ndarray) and isinstance(times[0], int | float): numbers = times / self.tm
            
            if self.test_mode: old_frequencies = np.random.random(32) * 1000
            else: old_frequencies = self.mla.lockin.get_frequencies()
            new_frequencies = old_frequencies # To be overwritten with user data
            
            # Set            
            if isinstance(frequencies, list | np.ndarray):
                if not self.test_mode:
                    for idx in range(min(self.mla.lockin.nr_input_freq, len(frequencies))): new_frequencies[idx] = frequencies[idx]
            elif isinstance(frequencies, dict):
                for key, value in frequencies.items():
                    if not isinstance(value, float | int): continue
                    try: new_frequencies[int(key)] = value
                    except: pass
            elif isinstance(numbers, list | np.ndarray):
                for idx in range(min(self.mla.lockin.nr_input_freq, len(numbers))): new_frequencies[idx] = numbers[idx] * self.df
            elif isinstance(numbers, dict) and isinstance(numbers[0], int | float):
                for key, value in numbers.items():
                    if not isinstance(value, float | int): continue
                    try: new_frequencies[int(key)] = value * self.df
                    except: pass
            
            if not self.test_mode: self.mla.lockin.set_frequencies(new_frequencies, wait_for_effect = True)
            
            # Read
            if self.test_mode: read_frequencies = np.sort(np.random.random(32) * 1000)
            else: read_frequencies = np.round(self.mla.lockin.get_frequencies(), 5)
            read_numbers = np.round(np.array([frequency / self.df for frequency in read_frequencies]), 5)
            osc_times = np.round(np.array([1000 / frequency if not frequency == 0 else 0 for frequency in read_frequencies]), 5)

            freq_dict.update({"frequencies (Hz)": read_frequencies, "numbers": read_numbers, "times (ms)": osc_times})
            self.parameters.emit(freq_dict)
            
            if verbose and len(freq_dict) < 1: self.logprint(f"{freq_dict}", message_type = "result")
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (freq_dict, error)

    def amplitudes_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        amp_dict = {"dict_name": "amplitudes"}
        
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"mla.amplitudes_update({parameters})", message_type = "code")
                else: self.logprint("mla.amplitudes_update()", message_type = "code")
            
            if not self.status == "running" and not self.test_mode: self.link()
            
            # Read the time constant and df from the parameter dict. If both are given, df takes precedence
            amplitudes = parameters.get("amplitudes (mV)", None)
            
            if self.test_mode: old_amplitudes = np.random.random(32)
            else: old_amplitudes = self.mla.lockin.get_amplitudes() * 1000 # Scantelligent uses mV by default
            new_amplitudes = old_amplitudes # To be overwritten with user data
            
            # Set
            if isinstance(amplitudes, list | np.ndarray):
                if not self.test_mode:
                    for idx in range(min(self.mla.lockin.nr_input_freq, len(amplitudes))): new_amplitudes[idx] = amplitudes[idx]
            elif isinstance(amplitudes, dict):
                for key, value in amplitudes.items():
                    if not isinstance(value, float | int): continue
                    try: new_amplitudes[int(key)] = value
                    except: pass
            if not self.test_mode: self.mla.lockin.set_amplitudes(new_amplitudes / 1000, wait_for_effect = True)
            
            # Read
            if self.test_mode: read_amplitudes = np.random.random((32)) * 500
            else: read_amplitudes = np.round(self.mla.lockin.get_amplitudes() * 1000, 5)

            amp_dict.update({"amplitudes (mV)": read_amplitudes})
            self.parameters.emit(amp_dict)
            
            if verbose and len(parameters) < 1: self.logprint(f"{amp_dict}", message_type = "result")
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (amp_dict, error)

    def phases_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        phase_dict = {"dict_name": "phases"}
        
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"mla.phases_update({parameters})", message_type = "code")
                else: self.logprint("mla.phases_update()", message_type = "code")
            
            if not self.status == "running" and not self.test_mode: self.link()
            
            # Read the time constant and df from the parameter dict. If both are given, df takes precedence
            phases = parameters.get("phases (deg)", None)
            
            if self.test_mode: old_phases = np.random.random(32)
            else: old_phases = self.mla.lockin.get_phases(unit = "degree") # Scantelligent uses degree instead of radians
            new_phases = old_phases # To be overwritten with user data
            
            # Set
            if isinstance(phases, list | np.ndarray):
                if not self.test_mode:
                    for idx in range(min(self.mla.lockin.nr_input_freq, len(phases))): new_phases[idx] = phases[idx]
            elif isinstance(phases, dict):
                for key, value in phases.items():
                    if not isinstance(value, float | int): continue
                    try: new_phases[int(key)] = value
                    except: pass
            if not self.test_mode: self.mla.lockin.set_phases(new_phases, unit = "degree", wait_for_effect = True)
            
            # Read
            if self.test_mode: read_phases = np.random.random((32)) * 360
            else: read_phases = self.mla.lockin.get_phases(unit = "degree")

            phase_dict.update({"phases (deg)": read_phases})
            self.parameters.emit(phase_dict)
            
            if verbose and len(parameters) < 1: self.logprint(f"{phase_dict}", message_type = "result")
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (phase_dict, error)

    def outputs_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        outputs_dict = {"dict_name": "outputs"}
        
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"mla.outputs_update({parameters})", message_type = "code")
                else: self.logprint("mla.outputs_update()", message_type = "code")
            
            if not self.status == "running" and not self.test_mode: self.link()
            
            # Read the parameters
            blank = parameters.get("blank", False)
            if blank: self.output_masks *= 0            
            output_masks = parameters.get("output_masks", False)
            if isinstance(output_masks, np.ndarray) and output_masks.shape == self.output_masks.shape: self.output_masks = output_masks
            
            mod0 = parameters.get("mod0", None)
            if not mod0: mod0 = parameters.get("mla_mod0", None)
            mod1 = parameters.get("mod1", None)
            if not mod1: mod1 = parameters.get("mla_mod1", None)
            mod2 = parameters.get("mod2", None)
            if not mod2: mod2 = parameters.get("mla_mod2", None)
            mod3 = parameters.get("mod3", None)
            if not mod1: mod1 = parameters.get("mla_mod3", None)
            
            for index, mod in enumerate([mod0, mod1, mod2, mod3]):
                if not isinstance(mod, dict):
                    if self.output_masks[0, index]: outputs_dict.update({f"mod{index}": {"on": True, "port": 1}})
                    elif self.output_masks[1, index]: outputs_dict.update({f"mod{index}": {"on": True, "port": 2}})
                    else: outputs_dict.update({f"mod{index}": {"on": False}})
                    continue
                chan = mod.get("channel", None) # Channel, signal and port are all considered valid keywords to indicate the output port
                if not chan: chan = mod.get("signal", None)
                if not chan: chan = mod.get("port", None)
                if chan not in [1, 2]:
                    outputs_dict.update({f"mod{index}": {"on": False}})
                    continue # 0 means that the modulator signal is not applied to any port, 1 means applied to port 1, and 2 is applied to port 2

                if mod.get("on"):
                    self.output_masks[chan - 1, index] = 1
                    outputs_dict.update({f"mod{index}": {"on": True, "port": chan}})
            
            if not self.test_mode: self.set_output_masks(self.output_masks)
            outputs_dict.update({"output_masks": np.copy(self.output_masks)})
            self.parameters.emit(outputs_dict)
            
            if verbose and len(parameters) < 1: self.logprint(f"{outputs_dict}", message_type = "result")
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (outputs_dict, error)

    def inputs_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        inputs_dict = {"dict_name": "inputs"}
        
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"mla.inputs_update({parameters})", message_type = "code")
                else: self.logprint("mla.inputs_update()", message_type = "code")
            
            if not self.status == "running" and not self.test_mode: self.link()
            
            mask = parameters.get("input_mask", None)
            if isinstance(mask, list): mask = np.array(mask, dtype = int)
            if isinstance(mask, np.ndarray) and mask.shape == self.input_mask.shape:
                self.input_mask = mask
                if not self.test_mode: self.set_input_multiplexer(self.input_mask)
            
            inputs_dict.update({"input_mask": np.copy(self.input_mask)})
            self.parameters.emit(inputs_dict)
            
            if verbose and len(parameters) < 1: self.logprint(f"{inputs_dict}", message_type = "result")
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (inputs_dict, error)

    def bias_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        bias_dict = {"dict_name": "mla_bias"}
        
        dt = parameters.get("dt (ms)", 5) / 1000
        dV = parameters.get("dV (mV)", 10) / 1000
        
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"mla.bias_update({parameters})", message_type = "code")
                else: self.logprint("mla.bias_update()", message_type = "code")
            
            if not self.status == "running" and not self.test_mode: self.link()
            
            [port1, port2] = [parameters.get(f"port_{index + 1} (V)", None) for index in range(2)]
            if isinstance(port1, float | int):
                if not self.test_mode:
                    if port1 < self.V[0]: dV *= -1
                    slew = np.arange(self.V[0], port1, dV)
                    for V_t in slew: # Perform the slew to the new bias voltage
                        self.set_bias(port = 1, value = V_t)
                        time.sleep(dt)
                    self.set_bias(port = 1, value = port1)
                self.V[0] = port1
            if isinstance(port2, float | int):
                if not self.test_mode:
                    if port2 < self.V[1]: dV *= -1
                    slew = np.arange(self.V[1], port2, dV)
                    for V_t in slew: # Perform the slew to the new bias voltage
                        self.set_bias(port = 2, value = V_t)
                        time.sleep(dt)
                    self.set_bias(port = 2, value = port2)
                self.V[1] = port2
            
            bias_dict.update({"port_1 (V)": self.V[0], "port_2 (V)": self.V[1]})
            self.parameters.emit(bias_dict)
            
            if verbose and len(parameters) < 1: self.logprint(f"{bias_dict}", message_type = "result")
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (bias_dict, error)



    # Parameter sweep experiments
    def frequency_sweep(self, frequencies = np.ndarray, settle_pixels: int = 1, pixels_per_datapoint: int = 4, measurement: object = None, tia_gain_V_per_pA: float = 0, modulators: list = [0, 1],
                        output_port: int = 1, input_port: int = 2, input_reference_port: int = 1, abort_callback: object = None, data_callback: object = None, channel_names_callback: object = None,
                        insert_parameter: tuple[str, float] = None, tia_corrections: list | np.ndarray = None, post_sweep_outputs: str = "reset") -> tuple[np.ndarray, np.ndarray]:
        
        # In the future, more complicated data acquisitions can be passed rather than just get_pixels
        if measurement: self.logprint(f"Measurements other than data pixel acquisitions are not yet supported for frequency sweeps.", message_type = "error")
        measurement = lambda: self.get_pixels(pixels_per_datapoint, average = True)
        if not data_callback: data_callback = lambda data_chunk: self.logprint(f"{data_chunk = }", message_type = "result")

        (start_outputs, error) = self.outputs_update(verbose = False) # Read for resetting after the sweep
        measurement_output_masks = np.copy(start_outputs.get("output_masks"))
        for mod_index in modulators: # Set the modulators according to what was passed
            measurement_output_masks[output_port - 1, mod_index] = 1
        self.outputs_update({"output_masks": measurement_output_masks}, verbose = False) # Read for resetting after the sweep
        
        (amplitudes_dict, error) = self.amplitudes_update(verbose = False) # Read the amplitude
        mod_voltage_mV = amplitudes_dict.get("amplitudes (mV)")[0]
        
        # Prepare to plot these channels
        channel_names = ["f1 (Hz)", "|a1_ref| (mV)", "arg(a1_ref) (deg)", "|a1| (mV)", "arg(a1) (deg)", "|a2| (mV)", "arg(a2) (deg)"] # When a gain is given, convert the voltages to displacement currents and subsequently capacitances
        if tia_gain_V_per_pA > 1E-12: channel_names = ["f1 (Hz)", "|a1_ref| (mV)", "arg(a1_ref) (deg)", "|a1| (mV)", "|a1| (pA)", "|C1| (fF)", "arg(a1) (deg)", "|a2| (mV)", "|a2| (pA)", "|C2| (fF)", "arg(a2) (deg)"]
        
        insert_value = None
        if isinstance(insert_parameter, tuple) and isinstance(insert_parameter[0], str) and isinstance(insert_parameter[1], float | int):
            channel_names.insert(0, insert_parameter[0]) # When passed, an extra parameter can be inserted at position 0 of the channels
            insert_value = insert_parameter[1]
        if channel_names_callback: channel_names_callback(np.array(channel_names))
        measurement_array = np.empty((len(frequencies), len(channel_names)), dtype = np.float32)
        error_array = np.empty_like(measurement_array, dtype = np.float32)
        
        
        
        # Main loop
        n_total = len(frequencies)
        self.start_lockin()
        for index, f in enumerate(frequencies):
            if abort_callback: abort_callback()
            self.task_progress.emit(int(100 * index / n_total))
            w = 2 * np.pi * int(f) # Frequency in rad per s
            self.time_constant_update({"df (Hz)": int(f)}, verbose = False)
            (frequencies_dict, error) = self.frequencies_update({"numbers": [1, 1, 2, 3]}, verbose = False)
            freqs = frequencies_dict.get("frequencies (Hz)")
            
            self.get_pixels(settle_pixels) # Wait settle_pixels number of pixels
            (pix_V, pix_V_var) = measurement()
            pix_V_std_dev = np.sqrt(pix_V_var)
            
            if isinstance(tia_corrections, list | np.ndarray): # Apply correction
                for tone in range(len(pix_V)):
                    freq_int = int(round(freqs[tone]))
                    if freq_int < len(tia_corrections):
                        tone_correction = tia_corrections[freq_int]
                        pix_V[tone] *= tone_correction
                        pix_V_std_dev *= np.abs(tone_correction)
            
            a1refabs = 2000 * np.abs(pix_V[0]) # Reference signal = output directly copied to an MLA input port
            a1refarg = np.rad2deg(np.angle(pix_V[0]))
            
            a1abs_mV = 2000 * np.abs(pix_V[1]) # Drive and second harmonic output measured on input port
            a2abs_mV = 2000 * np.abs(pix_V[2])
            a1_std_dev_mV = 2000 * np.sqrt(pix_V_std_dev[1])
            a2_std_dev_mV = 2000 * np.sqrt(pix_V_std_dev[2])
            
            a1arg = np.rad2deg(np.angle(pix_V[1]))
            a2arg = np.rad2deg(np.angle(pix_V[2]))

            if tia_gain_V_per_pA > 1E-12: # When a gain is given, convert the voltages to displacement currents and subsequently capacitances. The factor 2 accounts for the discrepancy between the time-averaged lockin signal and the actual voltage amplitude
                a1abs_pA = a1abs_mV / (1000 * tia_gain_V_per_pA) # Displacement current
                a2abs_pA = a2abs_mV / (1000 * tia_gain_V_per_pA)
                
                a1_std_dev_pA = a1_std_dev_mV / (1000 * tia_gain_V_per_pA)
                a2_std_dev_pA = a2_std_dev_mV / (1000 * tia_gain_V_per_pA)
                
                if mod_voltage_mV > .01: # Convert to femtofarad
                    #a1abs_nS = a1abs_pA / mod_voltage_mV # Reactance
                    #a2abs_nS = a2abs_pA / mod_voltage_mV
                    
                    wV = w * mod_voltage_mV
                    a1abs_fF = 1E6 * a1abs_pA / wV # Capacitance is capacitive reactance divided by frequency
                    a2abs_fF = 1E6 * a2abs_pA / wV
                    
                    a1_std_dev_fF = 1E6 * a1_std_dev_pA / wV
                    a2_std_dev_fF = 1E6 * a2_std_dev_pA / wV
                else:
                    a1abs_fF = 0
                    a2abs_fF = 0
                    a1_std_dev_fF = 0
                    a2_std_dev_fF = 0
                
                data_chunk = np.array([f, a1refabs, a1refarg, a1abs_mV, a1abs_pA, a1abs_fF, a1arg, a2abs_mV, a2abs_pA, a2abs_fF, a2arg], dtype = np.float32)
                error_chunk = np.array([0, 0, 0, a1_std_dev_mV, a1_std_dev_pA, a1_std_dev_fF, 0, a2_std_dev_mV, a2_std_dev_pA, a2_std_dev_fF, 0], dtype = np.float32)
            else:
                data_chunk = np.array([f, a1refabs, a1refarg, a1abs_mV, a1arg, a2abs_mV, a2arg], dtype = np.float32)
                error_chunk = np.array([0, 0, 0, a1_std_dev_mV, 0, a2_std_dev_mV, 0], dtype = np.float32)
            
            if isinstance(insert_value, float | int):
                data_chunk = np.insert(data_chunk, 0, insert_value)
                error_chunk = np.insert(error_chunk, 0, 0)
            
            measurement_array[index] = data_chunk
            error_array[index] = error_chunk
            data_callback(data_chunk)
                
        self.task_progress.emit(100) # Signal that the measurement is done
        if post_sweep_outputs == "blank": self.outputs_update({"output_masks": np.zeros((2, 32), dtype = int)}) # Reset outputs
        elif post_sweep_outputs == "reset": self.outputs_update({"output_masks": start_outputs.get("output_masks")}) # Reset outputs
        return (measurement_array, error_array, channel_names)

    def amplitude_sweep(self, amplitudes = np.ndarray, settle_pixels: int = 1, pixels_per_datapoint: int = 4, measurement: object = None, tia_gain_V_per_pA: float = 0,
                        output_port: int = 1, modulators: list = [0], abort_callback: object = None, data_callback: object = None, channel_names_callback: object = None,
                        insert_parameter: tuple[str, float] = None, tia_corrections: list | np.ndarray = None, post_sweep_outputs: str = "reset") -> tuple[np.ndarray, np.ndarray]:
        # In the future, more complicated data acquisitions can be passed rather than just mla.get_pixels
        if measurement: self.logprint(f"Measurements other than data pixel acquisitions are not yet supported for frequency sweeps.", message_type = "error")
        measurement = lambda: self.get_pixels(pixels_per_datapoint, average = True)
        if not data_callback: data_callback = lambda data_chunk: self.logprint(f"{data_chunk = }", message_type = "result")
        
        (start_outputs, error) = self.outputs_update(verbose = False) # Read for resetting after the sweep
        measurement_output_masks = np.copy(start_outputs.get("output_masks"))
        for mod_index in modulators: # Set the modulators according to what was passed
            measurement_output_masks[output_port - 1, mod_index] = 1
        self.outputs_update({"output_masks": measurement_output_masks}, verbose = False) # Read for resetting after the sweep
        
        (frequencies_dict, error) = self.frequencies_update() # Knowledge of the absolute frequencies is relevant when correcting for the frequency-dependent response of the TIA
        freqs = frequencies_dict.get("frequencies (Hz)")

        # Prepare to plot these channels
        channel_names = ["amp (mV)", "|a1_ref| (mV)"]
        if tia_gain_V_per_pA > 1E-12: [channel_names.extend([f"Re(a{i + 1}) (nS)", f"Im(a{i + 1}) (nS)"]) for i in range (31)]
        else: [channel_names.extend([f"Re(a{i + 1}) (mV)", f"Im(a{i + 1}) (mV)"]) for i in range (31)]
        insert_value = None
        if isinstance(insert_parameter, tuple) and isinstance(insert_parameter[0], str) and isinstance(insert_parameter[1], float | int):
            channel_names.insert(0, insert_parameter[0]) # When passed, an extra parameter can be inserted at position 0 of the channels
            insert_value = insert_parameter[1]
        if channel_names_callback: channel_names_callback(np.array(channel_names)) # Signal the gui to start tracking/plotting these data
        measurement_array = np.empty((len(amplitudes), len(channel_names)), dtype = np.float32)
        error_array = np.empty_like(measurement_array, dtype = np.float32)



        # Main loop
        n_total = len(amplitudes)
        self.start_lockin()
        for index, amp_mV in enumerate(amplitudes):
            if abort_callback: abort_callback()
            self.task_progress.emit(int(100 * index / n_total))
            self.amplitudes_update({"amplitudes (mV)": {number: amp_mV for number in modulators}}, verbose = False)
            
            self.get_pixels(settle_pixels)
            (pix_V, pix_V_var) = measurement()
            pix_V_std_dev = np.sqrt(pix_V_var)
            
            if isinstance(tia_corrections, list | np.ndarray): # Apply correction
                for tone in range(len(pix_V)):
                    freq_int = int(round(freqs[tone]))
                    if freq_int < len(tia_corrections):
                        tone_correction = tia_corrections[freq_int]
                        pix_V[tone] *= tone_correction
                        pix_V_std_dev *= np.abs(tone_correction)
            
            if isinstance(insert_value, float | int): data_chunk = np.zeros((len(channel_names) - 1), dtype = np.float32)
            else: data_chunk = np.zeros((len(channel_names)), dtype = np.float32)
            error_chunk = np.zeros_like(data_chunk)
            data_chunk[0] = amp_mV
            data_chunk[1] = 2000 * np.abs(pix_V[0]) # Factor 2 to account for discrepancy between amplitude and lockin measured amplitude
            
            harmonics_V = np.array([[np.real(tone), np.imag(tone)] for tone in pix_V[1:]]).flatten()
            errors_V = np.sqrt(np.array([[tone, 0] for tone in pix_V_std_dev[1:]]).flatten())
            if tia_gain_V_per_pA > 1E-12:
                harmonics_pA = 2 * harmonics_V / tia_gain_V_per_pA
                data_chunk[2:] = harmonics_pA
                
                errors_pA = 2 * errors_V / tia_gain_V_per_pA
                error_chunk[2:] = errors_pA
            else:
                harmonics_mV = 2000 * harmonics_V
                data_chunk[2:] = harmonics_mV
                
                errors_mV = 2000 * errors_V
                error_chunk[2:] = errors_mV

            if isinstance(insert_value, float | int):
                data_chunk = np.insert(data_chunk, 0, insert_value)
                error_chunk = np.insert(error_chunk, 0, 0)
            
            measurement_array[index] = data_chunk
            error_array[index] = error_chunk
            data_callback(data_chunk)

        self.task_progress.emit(100) # Signal that the measurement is done
        if post_sweep_outputs == "blank": self.outputs_update({"output_masks": np.zeros((2, 32), dtype = int)}) # Reset outputs
        elif post_sweep_outputs == "reset": self.outputs_update({"output_masks": start_outputs.get("output_masks")}) # Reset outputs
        return (measurement_array, error_array, channel_names)

    def voltage_sweep(self, voltages = np.ndarray, settle_pixels: int = 1, pixels_per_datapoint: int = 4, measurement: object = None, tia_gain_V_per_pA: float = 0,
                      output_port: int = 1, modulators: list = [0], abort_callback: object = None, data_callback: object = None, channel_names_callback: object = None,
                      insert_parameter: tuple[str, float] = None, return_type: str = "conductance", tia_corrections: list | np.ndarray = None, post_sweep_outputs: str = "reset") -> tuple[np.ndarray, np.ndarray]:
        # In the future, more complicated data acquisitions can be passed rather than just mla.get_pixels
        if measurement: self.logprint(f"Measurements other than data pixel acquisitions are not yet supported for frequency sweeps.", message_type = "error")
        measurement = lambda: self.get_pixels(pixels_per_datapoint, average = True)
        if not data_callback: data_callback = lambda data_chunk: self.logprint(f"{data_chunk = }", message_type = "result")
        
        (start_outputs, error) = self.outputs_update(verbose = False) # Read for resetting after the sweep
        measurement_output_masks = np.copy(start_outputs.get("output_masks"))
        for mod_index in modulators: # Set the modulators according to what was passed
            measurement_output_masks[output_port - 1, mod_index] = 1
        self.outputs_update({"output_masks": measurement_output_masks}, verbose = False) # Read for resetting after the sweep
        
        # Read the TIA gain and oscillator amplitude to be able to convert values
        (frequencies_dict, error) = self.frequencies_update()
        freqs = frequencies_dict.get("frequencies (Hz)")
        (amplitudes_dict, error) = self.amplitudes_update(verbose = False)
        mod_voltage_mV = amplitudes_dict.get("amplitudes (mV)")[0]
        
        # Prepare to plot these channels
        channel_names = [f"V_port{output_port} (V)", "|a1_ref| (mV)"]
        if tia_gain_V_per_pA > 1E-12:
            if return_type == "conductance": [channel_names.extend([f"Re(a{i + 1}) (nS)", f"Im(a{i + 1}) (nS)"]) for i in range(31)] # return_type = conductance
            else: [channel_names.extend([f"Re(a{i + 1}) (pA)", f"Im(a{i + 1}) (pA)"]) for i in range(31)] # return_type = displacement current
        else:
            [channel_names.extend([f"Re(a{i + 1}) (mV)", f"Im(a{i + 1}) (mV)"]) for i in range(31)] # return_type = raw voltages
        insert_value = None
        if isinstance(insert_parameter, tuple) and isinstance(insert_parameter[0], str) and isinstance(insert_parameter[1], float | int):
            channel_names.insert(0, insert_parameter[0]) # When passed, an extra parameter can be inserted at position 0 of the channels
            insert_value = insert_parameter[1]
        if channel_names_callback: channel_names_callback(np.array(channel_names))
        measurement_array = np.empty((len(voltages), len(channel_names)), dtype = np.float32)
        error_array = np.empty_like(measurement_array, dtype = np.float32)



        # Main loop
        n_total = len(voltages)
        self.start_lockin()
        for index, voltage in enumerate(voltages):
            if abort_callback: abort_callback()
            self.task_progress.emit(int(100 * index / n_total))
            self.bias_update({f"port_{output_port} (V)": voltage}, verbose = False)
            
            self.get_pixels(settle_pixels)
            (pix_V, pix_V_var) = measurement()
            pix_V_std_dev = np.sqrt(pix_V_var)
            
            if isinstance(tia_corrections, list | np.ndarray): # Apply correction for tia response if desired
                for tone in range(len(pix_V)):
                    freq_int = int(round(freqs[tone]))
                    if freq_int < len(tia_corrections):
                        tone_correction = tia_corrections[freq_int]
                        pix_V[tone] *= tone_correction
                        pix_V_std_dev *= np.abs(tone_correction)
                        
            if isinstance(insert_value, float | int): data_chunk = np.zeros((len(channel_names) - 1), dtype = np.float32)
            else: data_chunk = np.zeros((len(channel_names)), dtype = np.float32)
            error_chunk = np.zeros_like(data_chunk)
            data_chunk[0] = voltage
            data_chunk[1] = 2000 * np.abs(pix_V[0]) # Reference signal in mA
            
            harmonics_V = np.array([[np.real(tone), np.imag(tone)] for tone in pix_V[1:]]).flatten()
            errors_V = np.sqrt(np.array([[tone, 0] for tone in pix_V_std_dev[1:]]).flatten())            
            if tia_gain_V_per_pA > 1E-12:
                harmonics_pA = 2 * harmonics_V / tia_gain_V_per_pA
                errors_pA = 2 * errors_V / tia_gain_V_per_pA
                
                if mod_voltage_mV > 1E-3:
                    harmonics_nS = harmonics_pA / mod_voltage_mV
                    errors_nS = errors_pA / mod_voltage_mV
                else: # Conductance diverges for zero modulation bias. Replace with zero
                    harmonics_nS = 0 * harmonics_pA
                    errors_nS = 0
                
                if return_type == "conductance":
                    data_chunk[2:] = harmonics_nS
                    error_chunk[2:] = errors_nS
                else:
                    data_chunk[2:] = harmonics_pA
                    error_chunk[2:] = errors_pA
            else:
                data_chunk[2:] = 2000 * harmonics_V
                error_chunk[2:] = 2000 * errors_V
            
            if isinstance(insert_value, float | int):
                data_chunk = np.insert(data_chunk, 0, insert_value)
                error_chunk = np.insert(error_chunk, 0, 0)
            
            measurement_array[index] = data_chunk
            error_array[index] = error_chunk
            data_callback(data_chunk)
        
        self.task_progress.emit(100) # Signal that the measurement is done
        if post_sweep_outputs == "blank": self.outputs_update({"output_masks": np.zeros((2, 32), dtype = int)}) # Reset outputs
        elif post_sweep_outputs == "reset": self.outputs_update({"output_masks": start_outputs.get("output_masks")}) # Reset outputs
        return (measurement_array, error_array, channel_names)


