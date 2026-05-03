import os, sys, time
from PyQt6 import QtCore
import numpy as np



class MLAAPI(QtCore.QObject):
    amplitudes = QtCore.pyqtSignal(list)
    frequency = QtCore.pyqtSignal(float)
    message = QtCore.pyqtSignal(str, str)
    parameters = QtCore.pyqtSignal(dict)

    def __init__(self, hw_config: dict = {}, status_callback: object = None):
        super().__init__()
        self.callback = None
        if status_callback: self.callback = status_callback
        
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

        self.df = 100 # Defaults, to be overwritten by the first call to time_constant_update()
        self.tm = 10
        self.status = "offline"



    def link(self) -> None:
        try:
            self.logprint("mla.link()", message_type = "code")
            self.mla.connect()
            self.status = "running"
            self.set_defaults()
            self.start_lockin()            
            try: self.callback.setState("running")
            except: pass            
        except Exception as e:
            self.logprint(f"Error while connecting to the MLA: {e}", message_type = "error")
            self.unlink()
            self.status = "idle"
            try: self.callback.setState("idle")
            except: pass
        return

    def unlink(self) -> None:
        try:
            self.stop_lockin()
            self.oscillator_on(False)
            self.set_V(0)
        finally:
            self.mla.disconnect()
            self.parameters.emit({"dict_name": "mla_status", "status": "idle"})
            try: self.callback.setState("idle")
            except: pass
        return

    def start_lockin(self) -> None:
        return self.mla.lockin.start_lockin()

    def stop_lockin(self) -> None:
        return self.mla.lockin.stop_lockin()

    def logprint(self, text: str = "", message_type: str = "") -> None:
        self.message.emit(text, message_type)
        return

    def unwrap(self) -> object:
        return self.mla



    # Set and get methods
    def oscillator_on(self, value: bool = True) -> None:
        # Configure output ports
        mask1 = np.zeros(shape = self.mla.lockin.nr_output_freq, dtype = int) # List of 32 zeros
        mask1[0] = int(value)
        self.mla.lockin.set_output_mask(mask1, port = 1)
        self.parameters.emit({"dict_name": "lockin", "mla_mod1": {"on": value}})
        return

    def set_defaults(self) -> None:
        self.set_DACs_ADCs_safe_range()
        self.set_max_downsampling()
        self.time_constant_update({"df (Hz)": 100})
        self.frequencies_update()

        """
        # Use port 2 for drive waveform (not feedback)
        mla.lockin.set_output_mode_lockin(two_channels = True)

        # Configure lockin
        phases = np.random.rand(mla.lockin.nr_output_freq)
        mla.lockin.set_phases(phases, 'degree')

        input_ports= np.ones(mla.lockin.nr_output_freq - 1) + 1
        mla.lockin.set_input_multiplexer(np.insert(input_ports, 0, 1))
        """
        return

    def get_pixel(self) -> np.ndarray:
        (pix, _) = self.mla.lockin.get_pixels(1)
        self.amplitudes.emit(pix)
        return pix

    def convert_pixel_to_amp_phase(self) -> np.ndarray:
        return

    def get_tone(self, idx = 0, n_points: int = 1) -> np.ndarray:
        return self.mla.lockin.set_tone(idx, n_points)

    def set_V(self, V: float = 0, output_port: int = 1) -> None:
        self.mla.lockin.set_dc_offset(output_port, V)
        return

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
    def time_constant_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        tc_dict = {"dict_name": "time_constant"}
        
        try:
            if len(parameters) > 0: print(f"mla.time_constant_update({parameters})")
            else: print("mla.time_constant_update()")
            
            if not self.status == "running": self.link()
            
            # Read the time constant and df from the parameter dict. If both are given, df takes precedence
            tm = parameters.get("tm (ms)", None)
            df = parameters.get("df (Hz)", None)
            
            # Set
            if isinstance(df, float | int): self.mla.lockin.set_df(df)
            elif isinstance(tm, float | int): self.mla.lockin.set_Tm(tm / 1000) # Default unit in Scantelligent is ms, not s
            
            # Read
            self.tm = self.mla.lockin.get_Tm() * 1000 # Default unit in Scantelligent is ms, not s
            self.df = self.mla.lockin.get_df()
            
            tc_dict.update({"tm (ms)": self.tm, "df (Hz)": self.df})
            self.parameters.emit(tc_dict)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (tc_dict, error)

    def lockin_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        return

    def frequencies_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        freq_dict = {"dict_name": "frequencies"}
        
        try:
            if len(parameters) > 0: print(f"mla.frequencies_update({parameters})")
            else: print("mla.frequencies_update()")
            
            if not self.status == "running": self.link()
            
            # Read the time constant and df from the parameter dict. If both are given, df takes precedence
            frequencies = parameters.get("frequencies (Hz)", None)
            numbers = parameters.get("numbers", None)
            
            old_frequencies = self.mla.lockin.get_frequencies()
            new_frequencies = old_frequencies # To be overwritten with user data
            
            # Set
            if isinstance(frequencies, list) and isinstance(frequencies[0], int | float):
                for idx in range(min(self.mla.lockin.nr_input_freq, len(frequencies))): new_frequencies[idx] = frequencies[idx]
            elif isinstance(frequencies, dict):
                for key, value in frequencies.items():
                    if not isinstance(value, float | int): continue
                    try: new_frequencies[int(key)] = value
                    except: pass
            elif isinstance(numbers, list) and isinstance(numbers[0], int | float):
                for idx in range(min(self.mla.lockin.nr_input_freq, len(numbers))): new_frequencies[idx] = numbers[idx] * self.df
            elif isinstance(numbers, dict) and isinstance(numbers[0], int | float):
                for key, value in numbers.items():
                    if not isinstance(value, float | int): continue
                    try: new_frequencies[int(key)] = value * self.df
                    except: pass
            self.mla.lockin.set_frequencies(new_frequencies, wait_for_effect = True)
            
            # Read
            read_frequencies = np.round(self.mla.lockin.get_frequencies(), 5)
            read_numbers = np.round(np.array([frequency / self.df for frequency in read_frequencies]), 5)
            osc_times = np.round(np.array([1000 / frequency if not frequency == 0 else 0 for frequency in read_frequencies]), 5)

            freq_dict.update({"frequencies (Hz)": read_frequencies, "numbers": read_numbers, "times (ms)": osc_times})
            self.parameters.emit(freq_dict)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (freq_dict, error)

    def amplitudes_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        amp_dict = {"dict_name": "amplitudes"}
        
        try:
            if len(parameters) > 0: print(f"mla.frequencies_update({parameters})")
            else: print("mla.frequencies_update()")
            
            if not self.status == "running": self.link()
            
            # Read the time constant and df from the parameter dict. If both are given, df takes precedence
            amplitudes = parameters.get("amplitudes (mV)", None)
            
            old_amplitudes = self.mla.lockin.get_amplitudes() * 1000 # Scantelligent uses mV by default
            new_amplitudes = old_amplitudes # To be overwritten with user data
            
            # Set
            if isinstance(amplitudes, list) and isinstance(amplitudes[0], int | float):
                for idx in range(min(self.mla.lockin.nr_input_freq, len(amplitudes))): new_amplitudes[idx] = amplitudes[idx]
            elif isinstance(amplitudes, dict):
                for key, value in amplitudes.items():
                    if not isinstance(value, float | int): continue
                    try: new_amplitudes[int(key)] = value
                    except: pass
            self.mla.lockin.set_frequencies(new_amplitudes / 1000)
            
            # Read
            read_amplitudes = np.round(self.mla.lockin.get_amplitudes() * 1000, 5)

            amp_dict.update({"amplitudes (mV)": read_amplitudes})
            self.parameters.emit(amp_dict)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (amp_dict, error)

    def outputs_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        outputs_dict = {"dict_name": "outputs"}
        
        try:
            if len(parameters) > 0: print(f"mla.outputs_update({parameters})")
            else: print("mla.outputs_update()")
            
            if not self.status == "running": self.link()
            
            # Read the time constant and df from the parameter dict. If both are given, df takes precedence
            mod0 = parameters.get("mod0", None)
            if not mod0: mod0 = parameters.get("mla_mod0", None)
            mod1 = parameters.get("mod1", None)
            if not mod1: mod1 = parameters.get("mla_mod1", None)
            mod2 = parameters.get("mod2", None)
            if not mod2: mod2 = parameters.get("mla_mod2", None)
            mod1 = parameters.get("mod2", None)
            if not mod1: mod1 = parameters.get("mla_mod2", None)
            
            # Set
            #output_mask = [0, 0, 0, 0]
            #if isinstance(mod1, dict):
            #    port1 = mod1.get("port1", False)
            #    port2 = mod1.get("port2", False)
            #    on = mod1.get("on", True)
            #    if on:
            #        if port1: output
            #elif isinstance(tm, float | int): self.mla.lockin.set_Tm(tm / 1000) # Default unit in Scantelligent is ms, not s
            
            # Read
            
            outputs_dict.update({})
            self.parameters.emit(outputs_dict)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (outputs_dict, error)

    def phases_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        phases_dict = {"dict_name": "phases"}
        
        try:
            if len(parameters) > 0: print(f"mla.phases_update({parameters})")
            else: print("mla.phases_update()")
            
            if not self.status == "running": self.link()
            
            # Read the time constant and df from the parameter dict. If both are given, df takes precedence
            mod0 = parameters.get("mod0", None)
            if not mod0: mod0 = parameters.get("mla_mod0", None)
            mod1 = parameters.get("mod1", None)
            if not mod1: mod1 = parameters.get("mla_mod1", None)
            mod2 = parameters.get("mod2", None)
            if not mod2: mod2 = parameters.get("mla_mod2", None)
            mod1 = parameters.get("mod2", None)
            if not mod1: mod1 = parameters.get("mla_mod2", None)
            
            # Set
            #output_mask = [0, 0, 0, 0]
            #if isinstance(mod1, dict):
            #    port1 = mod1.get("port1", False)
            #    port2 = mod1.get("port2", False)
            #    on = mod1.get("on", True)
            #    if on:
            #        if port1: output
            #elif isinstance(tm, float | int): self.mla.lockin.set_Tm(tm / 1000) # Default unit in Scantelligent is ms, not s
            
            # Read
            
            phases_dict.update({})
            self.parameters.emit(phases_dict)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (phases_dict, error)

    def bias_update(self, parameters: dict = {}, unlink: bool = True, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        bias_dict = {"dict_name": "phases"}
        
        try:
            if len(parameters) > 0: print(f"mla.phases_update({parameters})")
            else: print("mla.phases_update()")
            
            if not self.status == "running": self.link()
            
            # Read the time constant and df from the parameter dict. If both are given, df takes precedence
            mod0 = parameters.get("mod0", None)
            if not mod0: mod0 = parameters.get("mla_mod0", None)
            mod1 = parameters.get("mod1", None)
            if not mod1: mod1 = parameters.get("mla_mod1", None)
            mod2 = parameters.get("mod2", None)
            if not mod2: mod2 = parameters.get("mla_mod2", None)
            mod1 = parameters.get("mod2", None)
            if not mod1: mod1 = parameters.get("mla_mod2", None)
            
            # Set
            #output_mask = [0, 0, 0, 0]
            #if isinstance(mod1, dict):
            #    port1 = mod1.get("port1", False)
            #    port2 = mod1.get("port2", False)
            #    on = mod1.get("on", True)
            #    if on:
            #        if port1: output
            #elif isinstance(tm, float | int): self.mla.lockin.set_Tm(tm / 1000) # Default unit in Scantelligent is ms, not s
            
            # Read
            
            bias_dict.update({})
            self.parameters.emit(bias_dict)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (bias_dict, error)

