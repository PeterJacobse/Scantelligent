import numpy as np
from PyQt6.QtCore import QObject, pyqtSignal, pyqtSlot
import sounddevice as sd



# AudioGenerator class. Used to provide auditory feedback when using lockin amplifiers
class AudioGenerator(QObject):
    finished = pyqtSignal()

    def __init__(self, sample_rate: int = 44100):
        super().__init__()
        self.sample_rate = sample_rate
        self.block_size = 2048
        self.wnyquist = np.pi * self.sample_rate
        self.w = 2 * np.pi * 220.0 * np.arange(32)
        self.amplitudes = np.zeros(shape = (32), dtype = float)
        self.volumes = np.zeros_like(self.amplitudes, dtype = int)
        self.amps_old = np.zeros_like(self.amplitudes, dtype = float) # Amps is the absolute amplitudes weighed by the volumes
        self.amps_new = np.zeros_like(self.amplitudes, dtype = float)
        self.phases = np.zeros_like(self.amplitudes)
        self.stream = None
        self.time_list = np.arange(self.block_size) / self.sample_rate
        self.max_time = self.block_size / self.sample_rate

    @pyqtSlot()
    def start(self):
        self.stream = sd.OutputStream(channels = 1, callback = self.callback, samplerate = self.sample_rate, blocksize = self.block_size)
        self.stream.start()

    def callback(self, outdata, frames, time, status):
        if self.thread().isInterruptionRequested(): self.stop()
        wave = np.zeros(self.block_size, dtype = np.float64)

        for i, wn in enumerate(self.w):
            if wn > self.wnyquist: continue
            
            amp_envelope = np.linspace(self.amps_old[i], self.amps_new[i], self.block_size) # Define the cross-fade
            waveform = np.sin(wn * self.time_list + self.phases[i]) # Define the bare wave
            
            wave += amp_envelope * waveform # Calculate the wave
            self.phases[i] = (self.phases[i] + wn * self.max_time) % (2 * np.pi) # Update the phase
        
        self.amps_old = self.amps_new.copy()
        wave = np.tanh(.3 * wave) # Soft clipping
        outdata[:] = wave.astype(np.float32)[:, np.newaxis]

    @pyqtSlot(list)
    def volumes_update(self, values: list | np.ndarray = []) -> None:
        self.volumes = np.array(values, dtype = int)
        self.amps_old = np.copy(self.amps_new)
        self.amps_new = self.amplitudes * self.volumes * 1E-8
        return

    @pyqtSlot(list)
    def amplitudes_update(self, values: list | np.ndarray = []) -> None:
        self.amplitudes = np.array(values, dtype = float)
        self.amps_old = self.amps_new.copy()
        self.amps_new = self.amplitudes * self.volumes * 1E-8
        return

    @pyqtSlot(list)
    def frequencies_update(self, values: list | np.ndarray = []) -> None:
        self.w = 2 * np.pi * np.array(values, dtype = float)
        return

    def stop(self):
        if self.stream:
            self.stream.stop()
            self.stream.close()
        self.finished.emit()

