from PyQt6 import QtCore, QtWidgets
import array as ar
import numpy as np
from pysoundio import PySoundIo, SoundIoFormatFloat32LE



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

