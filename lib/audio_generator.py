import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import sounddevice as sd
from math import pi



# AudioGenerator class. Used to provide auditory feedback when using lockin amplifiers
class AudioGenerator(QObject):
    finished = pyqtSignal()

    def __init__(self, sample_rate: int = 44100):
        super().__init__()
        self.sample_rate = sample_rate
        self.w1 = 2 * pi * 220.0
        self.amplitudes = np.zeros(shape = (32), dtype = float)
        self.amplitudes[0] = 1
        self.amplitude_volumes = 100 * np.ones(shape = (32), dtype = int)
        self.volume = 20
        self.phases = np.zeros(len(self.amplitudes))
        self.stream = None
        self.home_thread = self.thread()

    @pyqtSlot()
    def start(self):
        self.stream = sd.OutputStream(channels = 1, callback = self.callback, samplerate = self.sample_rate)
        self.stream.start()

    def callback(self, outdata, frames, time, status):
        if self.thread().isInterruptionRequested(): self.stop()
        time_list = np.arange(frames) / self.sample_rate
        wave = np.zeros(frames)
        wnyquist = pi * self.sample_rate
        
        for i, amp in enumerate(self.amplitudes):
            amp_vol = self.volume * amp / 100
            wn = self.w1 * (i + 1)
            
            if wn < wnyquist:
                wave += amp_vol * np.sin(wn * time_list + self.phases[i])
                # Update this harmonic's phase for the next block
                self.phases[i] = (self.phases[i] + wn * frames / self.sample_rate) % (2 * pi)

        # Soft-clipping to prevent digital distortion if harmonics sum too high
        outdata[:] = np.tanh(wave * 0.2)[:, np.newaxis]

    @pyqtSlot(int)
    def update_volume(self, volume: int = 0) -> None:
        self.volume = volume
        return

    @pyqtSlot(list)
    def update_amplitudes(self, values: list = []) -> None:
        self.amplitudes = values
        return

    @pyqtSlot(list)
    def update_amplitude_volumes(self, values: list = []) -> None:
        self.amplitude_volumes = values
        return

    @pyqtSlot(float)
    def update_frequency(self, value: float = 100) -> None:
        self.w1 = 2 * pi * float(value)
        return

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.finished.emit()
        self.moveToThread(self.home_thread)

