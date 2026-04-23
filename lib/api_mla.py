import os, sys, time
from PyQt6 import QtCore
import array as ar
import numpy as np



class MLAAPI:
    def __init__(self, mla_path):
        self.mla_path = mla_path

        sys.path.insert(0, mla_path)

        from mlaapi import mla_globals # These packages should become available if the MLA path is correct
        settings = mla_globals.read_config()

        from mlaapi import mla_api
        self.mla = mla_api.MLA(settings)



    def link(self) -> None:
        self.mla.connect()
        
        self.set_defaults()
        self.set_base_frequency(200)
        
        self.lockin = self.mla.lockin
        self.analog = self.mla.analog
        self.hardware = self.mla.hardware
        self.feedback = self.mla.feedback
        return

    def unlink(self) -> None:
        self.mla.disconnect()
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

    def set_output_port_mask(self) -> None:
        # Configure output ports
        mask1 = np.zeros(shape = self.mla.lockin.nr_output_freq, dtype = int)
        mask1[0] = 1
        self.mla.lockin.set_output_mask(mask1, port = 1)
        return

    def set_defaults(self) -> None:
        self.set_DACs_ADCs_safe_range()
        self.set_max_downsampling()
        
        """

        mask2 = np.zeros(mla.lockin.nr_output_freq)
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
        """
        return

    def set_base_frequency(self, f: float = 220):
        harmonics_list = np.array(range(32), dtype = int)
        harmonics_list[0] = 1
        self.mla.lockin.set_frequencies_by_n_and_df(harmonics_list, f)
        return

    def unwrap(self) -> object:
        return self.mla

