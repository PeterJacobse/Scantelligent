import os, sys, time
from PyQt6 import QtCore, QtWidgets
import array as ar
import numpy as np
import importlib
#from pysoundio import PySoundIo, SoundIoFormatFloat32LE



class AudioGenerator(QtCore.QObject):
    finished = QtCore.pyqtSignal()

    def __init__(self, backend = None, output_device = None, sample_rate = None, block_size = None):
        super().__init__()
        self.pysoundio = PySoundIo(backend = backend)

        self.f1_rad_per_s = 80 * 2.0 * np.pi # 80 Hz
        self.amplitudes = [1, 0, .4, 0, .2, 0, .6, 0]

        self.output_device = output_device
        self.sample_rate = sample_rate
        self.block_size = block_size

        self.offset_rad = 0.0
        self.frame_duration = 1.0 / sample_rate
        self.abort_flag = False



    def run(self) -> None:
        self.pysoundio.start_output_stream(device_id = self.output_device, channels = 1, sample_rate = self.sample_rate, block_size = self.block_size, dtype = SoundIoFormatFloat32LE, write_callback = self.make_waveform)
        return

    def make_waveform(self, data, length) -> None:
        print(f"Making a new waveform using f1 = {self.f1_rad_per_s / (2 * np.pi)} Hz and amplitudes: {self.amplitudes} (a.u.)")
        waveform = ar.array('f', [0] * length)

        for harm, amplitude in enumerate(self.amplitudes):
            freq_rad_per_s = self.f1_rad_per_s * (harm + 1)
            
            for i in range(length):
                waveform[i] += amplitude * np.sin(self.offset_rad + freq_rad_per_s * i * self.frame_duration)
        data[:] = waveform.tobytes()

        self.offset_rad += 2 * np.pi * self.frame_duration * length
        return

    @QtCore.pyqtSlot(float)
    def update_frequency(self, frequency: float) -> None:
        self.f1_rad_per_s = frequency * 2.0 * np.pi
        self.pysoundio.flush()
        return

    @QtCore.pyqtSlot(list)
    def update_amplitudes(self, amplitudes: list) -> None:
        self.amplitudes = amplitudes
        return

    def close(self) -> None:
        self.pysoundio.close()
        self.finished.emit()
        return



class MLAAPI:
    def __init__(self, mla_path):
        self.mla_path = mla_path

        sys.path.insert(0, mla_path)

        from mlaapi import mla_globals # These packages should become available if the MLA path is correct
        settings = mla_globals.read_config()

        from mlaapi import mla_api
        self.mla = mla_api.MLA(settings)
        # self.mla.connect()
        # self.set_defaults()
        # self.mla.disconnect()



    def set_defaults(self) -> None:
        mla = self.mla

        f1 = 400 # The base frequency is set to 400 Hz
        mla.osc.set_downsampling(250) # Typical sample rate is far too high; we do not need to measure in the MHz range

        # Set all analog inputs to the correct configuration (range = +-20 V)
        mla.hardware.set_input_relay(1, se = True, nodamp = False, term = False, dc = True, gain = False, bypass = False, gain2 = False, event = True)
        mla.hardware.set_input_relay(2, se = True, nodamp = False, term = False, dc = True, gain = False, bypass = False, gain2 = False, event = True)
        mla.hardware.set_input_relay(3, se = True, nodamp = False, term = False, dc = True, gain = False, bypass = False, gain2 = False, event = True)
        mla.hardware.set_input_relay(4, se = True, nodamp = False, term = False, dc = True, gain = False, bypass = False, gain2 = False, event = True)

        # Set +-12 V range for all analog outputs
        mla.hardware.set_output_relay(1, bypass = False, event = True)
        mla.hardware.set_output_relay(2, bypass = False, event = True)

        # Configure output ports
        mask_1 = np.zeros(mla.lockin.nr_output_freq)
        mla.lockin.set_output_mask(mask_1, port = 1)
        mask_1[0] = 1

        mask_2 = np.zeros(mla.lockin.nr_output_freq)
        mla.lockin.set_output_mask(mask_2, port = 2)

        # Use port 2 for drive waveform (not feedback)
        mla.lockin.set_output_mode_lockin(two_channels = True)

        # Configure lockin
        phases = np.random.rand(mla.lockin.nr_output_freq)
        mla.lockin.set_phases(phases, 'degree')

        ampls = np.zeros(mla.lockin.nr_output_freq)
        mla.lockin.set_amplitudes(ampls)

        freqs_hz = np.arange(mla.lockin.nr_output_freq - 1) * f1 + f1
        mla.lockin.set_frequencies(np.insert(freqs_hz, 0, f1))

        input_ports= np.ones(mla.lockin.nr_output_freq - 1) + 1
        mla.lockin.set_input_multiplexer(np.insert(input_ports, 0, 1))

        mla.lockin.set_df(100)  # set df in Hz
        return

    def unwrap(self) -> object:
        return self.mla


