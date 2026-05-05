import os, sys, time
from PyQt6 import QtCore
import numpy as np
import asyncio



class MLAAPI(QtCore.QObject):
    amplitudes = QtCore.pyqtSignal(list)
    frequency = QtCore.pyqtSignal(float)
    parameters = QtCore.pyqtSignal(dict)

    def __init__(self, hw_config: dict = {}, status_callback: object = None, message_callback: object = None, test_mode: bool = False):
        super().__init__()
        
        self.status_callback = print
        if status_callback: self.status_callback = status_callback
        self.message_callback = lambda message, message_type: print(message)
        if message_callback: self.message_callback = message_callback
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
        self.parameters_init()



    def parameters_init(self) -> None:
        self.df = 100 # Defaults, to be overwritten by the first call to time_constant_update()
        self.tm = 10
        self.V = [0, 0]
        self.output_masks = np.zeros((2, 32), dtype = int)
        self.status = "online"
        self.status_callback(self.status)        
        return

    def link(self) -> None:
        try:
            self.logprint("mla.link()", message_type = "code")
            self.mla.connect(server_text_callback = lambda text: self.logprint(text, message_type = "result"), ping_attempts = 4)
            self.status = "running"
            self.set_defaults()
            try: self.status_callback(self.status)
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
        return

    def unlink(self) -> None:
        try:
            self.stop_lockin()
            self.reset_outputs()
        finally:
            self.mla.disconnect()
            self.status = "idle"
            try: self.status_callback(self.status)
            except: pass
        return

    def start_lockin(self) -> None:
        return self.mla.lockin.start_lockin()

    def stop_lockin(self) -> None:
        return self.mla.lockin.stop_lockin()

    def logprint(self, message: str = "", message_type: str = "", append_new_line: bool = False) -> None:
        self.message_callback(message = message, message_type = message_type)
        return

    def unwrap(self) -> object:
        return self.mla



    # Set and get methods
    def set_defaults(self) -> None:
        self.reset_outputs()
        self.set_DACs_ADCs_safe_range()
        self.set_max_downsampling()
        self.bias_update()
        self.lockin_update({"df (Hz)": 100, "numbers": np.arange(1, 32), "amplitudes (mV)": [100]})

        """
        input_ports= np.ones(mla.lockin.nr_output_freq - 1) + 1
        mla.lockin.set_input_multiplexer(np.insert(input_ports, 0, 1))
        """
        return

    def reset_outputs(self):
        try: self.mla.lockin.reset_outputs()
        except Exception as e:
            self.logprint(f"{e}")
        return

    def get_pixels(self, number: int = 1, wait_for_new: bool = True) -> np.ndarray:
        if self.test_mode:
            rng = np.random.default_rng()
            pix = rng.random(32) + 1j * rng.random(32)
        else:
            if wait_for_new: self.mla.lockin.wait_for_new_pixels(number)
            (pix, _) = self.mla.lockin.get_pixels(number)
        self.parameters.emit({"dict_name": "pixels", "pixels": pix})
        return pix

    def set_DACs_ADCs_safe_range(self) -> None:
        # Set all analog inputs to the correct configuration (range = +-20 V)
        self.mla.hardware.set_input_relay(1, se = True, nodamp = False, term = False, dc = True, gain = False, bypass = False, gain2 = False, event = True)
        self.mla.hardware.set_input_relay(2, se = True, nodamp = False, term = False, dc = True, gain = False, bypass = False, gain2 = False, event = True)
        self.mla.hardware.set_input_relay(3, se = True, nodamp = False, term = False, dc = True, gain = False, bypass = False, gain2 = False, event = True)
        self.mla.hardware.set_input_relay(4, se = True, nodamp = False, term = False, dc = True, gain = False, bypass = False, gain2 = False, event = True)

        # Set +-12 V range for all analog outputs
        self.mla.hardware.set_output_relay(1, bypass = False, event = True)
        self.mla.hardware.set_output_relay(2, bypass = False, event = True)
        return

    def set_max_downsampling(self) -> None:
        # Typical sample rate is far too high; we do not need to measure in the MHz range
        self.mla.osc.set_downsampling(250)
        return



    # 'Update' methods that both take and apply parameters supplied to them and read from the mla
    def lockin_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        parameters_dict = {"dict_name": "parameters"}
        
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"mla.lockin_update({parameters})", message_type = "code")
                else: self.logprint("mla.lockin_update()", message_type = "code")
            
            if not self.status == "running" and not self.test_mode: self.link()
            
            # time_constant_update
            tm = parameters.get("tm (ms)", None)
            df = parameters.get("df (Hz)", None)
            if isinstance(df, float | int): (time_constant, error) = self.time_constant_update({"df (Hz)": df})
            elif isinstance(tm, float | int): (time_constant, error) = self.time_constant_update({"tm (ms)": tm})
            else: (time_constant, error) = self.time_constant_update()
            parameters_dict.update(time_constant)
            
            # frequencies_update
            frequencies = parameters.get("frequencies (Hz)", None)
            numbers = parameters.get("numbers", None)
            times = parameters.get("times (ms)", None)
            if isinstance(frequencies, list | np.ndarray): (frequencies_dict, error) = self.frequencies_update({"frequencies (Hz)": frequencies})
            elif isinstance(numbers, list | np.ndarray): (frequencies_dict, error) = self.frequencies_update({"numbers": numbers})
            elif isinstance(times, list | np.ndarray): (frequencies_dict, error) = self.frequencies_update({"times (ms)": times})
            else: (frequencies_dict, error) = self.frequencies_update()
            parameters_dict.update(frequencies_dict)
            
            # amplitudes update
            amplitudes = parameters.get("amplitudes (mV)", None)
            if isinstance(amplitudes, list | np.ndarray): (amplitudes_dict, error) = self.amplitudes_update({"frequencies (Hz)": frequencies})
            else: (amplitudes_dict, error) = self.amplitudes_update()
            parameters_dict.update(amplitudes_dict)
            
            # phases update
            phases = parameters.get("phases (deg)", None)
            if isinstance(phases, list | np.ndarray): (phase_dict, error) = self.phases_update({"phases (deg)": phases})
            else: (phases_dict, error) = self.phases_update()
            parameters_dict.update(phases_dict)
            
            # outputs update
            outputs_keys = {key: value for key, value in parameters.items() if key in ["blank", "mod0", "mod1", "mod2", "mod3"]}
            if len(outputs_keys) > 0:(outputs_dict, error) = self.outputs_update(outputs_keys)
            else: (outputs_dict, error) = self.outputs_update()
            parameters_dict.update(outputs_dict)
            
            if verbose and len(parameters) < 1: self.logprint(f"{parameters}", message_type = "result")
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (parameters_dict, error)

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
            if isinstance(frequencies, list | np.ndarray) and isinstance(frequencies[0], int | float):
                if not self.test_mode:
                    for idx in range(min(self.mla.lockin.nr_input_freq, len(frequencies))): new_frequencies[idx] = frequencies[idx]
            elif isinstance(frequencies, dict):
                for key, value in frequencies.items():
                    if not isinstance(value, float | int): continue
                    try: new_frequencies[int(key)] = value
                    except: pass
            elif isinstance(numbers, list | np.ndarray) and isinstance(numbers[0], int | float):
                for idx in range(min(self.mla.lockin.nr_input_freq, len(numbers))): new_frequencies[idx] = numbers[idx] * self.df
            elif isinstance(numbers, dict) and isinstance(numbers[0], int | float):
                for key, value in numbers.items():
                    if not isinstance(value, float | int): continue
                    try: new_frequencies[int(key)] = value * self.df
                    except: pass
            
            if not self.test_mode: self.mla.lockin.set_frequencies(new_frequencies, wait_for_effect = True)
            
            # Read
            if self.test_mode: read_frequencies = np.random.random(32) * 1000
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
            if isinstance(amplitudes, list | np.ndarray) and isinstance(amplitudes[0], int | float):
                if not self.test_mode:
                    for idx in range(min(self.mla.lockin.nr_input_freq, len(amplitudes))): new_amplitudes[idx] = amplitudes[idx]
            elif isinstance(amplitudes, dict):
                for key, value in amplitudes.items():
                    if not isinstance(value, float | int): continue
                    try: new_amplitudes[int(key)] = value
                    except: pass
            if not self.test_mode: self.mla.lockin.set_amplitudes(new_amplitudes / 1000, wait_for_effect = True)
            
            # Read
            if self.test_mode: read_amplitudes = np.random.random(32)
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
            else: old_phases = self.mla.lockin.get_phases() * 1000 # Scantelligent uses mV by default
            new_phases = old_phases # To be overwritten with user data
            
            # Set
            if isinstance(phases, list | np.ndarray) and isinstance(phases[0], int | float):
                if not self.test_mode:
                    for idx in range(min(self.mla.lockin.nr_input_freq, len(phases))): new_phases[idx] = phases[idx]
            elif isinstance(phases, dict):
                for key, value in phases.items():
                    if not isinstance(value, float | int): continue
                    try: new_phases[int(key)] = value
                    except: pass
            if not self.test_mode: self.mla.lockin.set_phases(new_phases / 1000, wait_for_effect = True)
            
            # Read
            if self.test_mode: read_phases = np.random.random(32)
            else: read_phases = np.round(self.mla.lockin.get_phases() * 1000, 5)

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
            
            # Read the modulator data
            blank = parameters.get("blank", False)
            if blank: self.output_masks *= 0
            
            mod0 = parameters.get("mod0", None)
            if not mod0: mod0 = parameters.get("mla_mod0", None)
            mod1 = parameters.get("mod1", None)
            if not mod1: mod1 = parameters.get("mla_mod1", None)
            mod2 = parameters.get("mod2", None)
            if not mod2: mod2 = parameters.get("mla_mod2", None)
            mod3 = parameters.get("mod3", None)
            if not mod1: mod1 = parameters.get("mla_mod3", None)
            
            if mod0 or mod1 or mod2 or mod3: self.output_masks *= 0 # Reset the output masks
            
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
            
            if not self.test_mode:
                self.mla.lockin.set_output_mask(self.output_masks[0], port = 1)
                self.mla.lockin.set_output_mask(self.output_masks[1], port = 2)
            outputs_dict.update({"output_mask": self.output_masks})
            self.parameters.emit(outputs_dict)
            
            if verbose and len(parameters) < 1: self.logprint(f"{outputs_dict}", message_type = "result")
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (outputs_dict, error)

    def bias_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        bias_dict = {"dict_name": "mla_bias"}
        
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"mla.bias_update({parameters})", message_type = "code")
                else: self.logprint("mla.bias_update()", message_type = "code")
            
            if not self.status == "running" and not self.test_mode: self.link()
            
            [port1, port2] = [parameters.get(f"port_{index + 1} (V)", None) for index in range(2)]
            if isinstance(port1, float | int):
                if not self.test_mode: self.mla.lockin.set_dc(port = 1, value = port1, wait_for_effect = True)
                self.V[0] = port1
            if isinstance(port2, float | int):
                if not self.test_mode: self.mla.lockin.set_dc(port = 1, value = port2, wait_for_effect = True)
                self.V[1] = port2
            
            bias_dict.update({"port_1 (V)": self.V[0], "port_2 (V)": self.V[1]})
            self.parameters.emit(bias_dict)
            
            if verbose and len(parameters) < 1: self.logprint(f"{bias_dict}", message_type = "result")
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (bias_dict, error)

