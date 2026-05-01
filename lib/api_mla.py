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
        settings = mla_globals.read_config()

        from mlaapi import mla_api
        self.mla = mla_api.MLA(settings)



    def link(self) -> None:
        try:
            self.logprint("mla.link()", message_type = "code")
            self.mla.connect()
            self.set_defaults()
            self.start_lockin()
            try: self.callback.setState("running")
            except: pass
            # self.parameters.emit({"dict_name": "mla_status", "status": "running"})
        except Exception as e:
            self.logprint(f"Error while connecting to the MLA: {e}", message_type = "error")
            self.unlink()
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
        self.oscillator_on(False)
        self.set_amp_mV(0)
        self.set_f1(200)

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

    def set_f1(self, f: float = 220, samples: int = 1) -> None:
        harmonics_list = np.array(range(32), dtype = int)
        harmonics_list[0] = 1
        self.mla.lockin.set_frequencies_by_n_and_df(harmonics_list, f)
        self.mla.lockin.set_df(f / samples)
        
        self.frequency.emit(f)
        return

    def set_amp_mV(self, amp_mV: float = 0) -> None:
        self.mla.lockin.set_amplitudes(amp_mV / 1000)
        return

    def set_V(self, V: float = 0, output_port: int = 1) -> None:
        self.mla.lockin.set_dc_offset(output_port, V)
        return

    def unwrap(self) -> object:
        return self.mla

