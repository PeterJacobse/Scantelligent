import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import sounddevice as sd



# AudioGenerator class. Used to provide auditory feedback when using lockin amplifiers
class AudioGenerator(QObject):
    finished = pyqtSignal()

    def __init__(self, sample_rate: int = 44100):
        super().__init__()
        self.sample_rate = sample_rate
        self.w = np.pi * 220.0 * np.arange(32)
        self.amplitudes = np.zeros(shape = (32), dtype = float)
        self.volumes = np.zeros_like(self.amplitudes, dtype = int)
        self.phases = np.zeros_like(self.amplitudes)
        self.stream = None

    @pyqtSlot()
    def start(self):
        self.stream = sd.OutputStream(channels = 1, callback = self.callback, samplerate = self.sample_rate)
        self.stream.start()

    def callback(self, outdata, frames, time, status):
        if self.thread().isInterruptionRequested(): self.stop()
        time_list = np.arange(frames) / self.sample_rate
        wave = np.zeros(frames)
        wnyquist = np.pi * self.sample_rate
        
        for i in range(32):
            wn = self.w[i]
            amp = 1E-8 * self.amplitudes[i] * self.volumes[i]
            
            if wn < wnyquist:
                wave += amp * np.sin(wn * time_list + self.phases[i])
                # Update this harmonic's phase for the next block
                self.phases[i] = (self.phases[i] + wn * frames / self.sample_rate) % (2 * np.pi)

        # Soft-clipping to prevent digital distortion if harmonics sum too high
        outdata[:] = np.tanh(wave * 0.2)[:, np.newaxis]

    @pyqtSlot(list)
    def volumes_update(self, values: list = []) -> None:
        for idx in range(min(32, len(values))): self.volumes[idx] = int(values[idx])
        return

    @pyqtSlot(list)
    def amplitudes_update(self, values: list = []) -> None:
        for idx in range(min(32, len(values))): self.amplitudes[idx] = float(values[idx])
        return

    @pyqtSlot(list)
    def frequencies_update(self, values: list = []) -> None:
        for idx in range(min(32, len(values))): self.w[idx] = 2 * np.pi * float(values[idx])
        return

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.finished.emit()
        #self.moveToThread(self.home_thread)

