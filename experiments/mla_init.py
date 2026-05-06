import sys, os, time
import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.gui_setup = {"combobox": {},
                          "line_edits": {"tooltips": ["1", "2"], "values": [-2, 10, 2, 100], "units": ["V", "mV", "V", "ms"], "digits": [3, 2, 1, 0, 4], "tooltips": ["bla"]},
                          "buttons": {}}

    @BaseExperiment.experiment_handler
    def run(self):
        [self.connect_hardware(component) for component in ["nanonis", "mla"]] # Set up the required hardware connections
        
        # Aliases
        nn = self.nanonis
        mla = self.mla
        nhw = nn.nanonis_hardware



        # Frequency sweep
        nn_hardware_dict = self.start_parameters["nanonis"].get("hardware", {})
        mod_voltage_mV = 500
        tia_gain_V_per_pA = nn_hardware_dict.get("gain (V/pA)")
        
        channel_names = ["f1 (Hz)", "|a1_ref| (mV)", "arg(a1_ref) (rad)", "|a1| (pA)", "arg(a1) (rad)", "|C1| (fF)", "|a2| (pA)", "arg(a2) (rad)", "|C2| (fF)"]
        channels_dict = {i: name for i, name in enumerate(channel_names)} | {"dict_name": "channels"} # Prepare the GUI for plotting these channels
        self.parameters.emit(channels_dict)
        
        x_axis = np.arange(5, 6000, 5, dtype = int)
        x_axis_label = "frequencies (Hz)"
        mla.amplitudes_update({"amplitudes (mV)": {0: mod_voltage_mV, 1: 0}}) # Set the amplitude of modulator 0 to 100 mV and that of number 1 to 120 mV
        mla.set_input_multiplexer([1, 2, 2])
        mla.outputs_update({"blank": True, "mod0": {"on": True, "port": 1}}) # Output modulator 1 onto port 1
        mla.start_lockin()
        
        for x in x_axis:
            self.check_abort_request()
            w = 2 * np.pi * int(x)
            mla.time_constant_update({"df (Hz)": int(x)}, verbose = False) # Set the measurement resolution to 200 Hz. This corresponds to a primitive time constant or period of 5 ms.
            mla.frequencies_update({"numbers": [1, 1, 2, 3]}, verbose = False) # Frequencies set in units of numbers of whole oscillations per period
            pix = mla.get_pixels(4)
            
            a1refabs = 2 * 1000 * np.abs(np.average(pix[0])) # Output directly copied to the MLA port 1 in
            a1refarg = np.angle(np.average(pix[0]))
            
            a1abs_V = 2 * np.abs(np.average(pix[1])) # Displacement currents measured through the TIA
            a1abs_pA = a1abs_V / tia_gain_V_per_pA
            a1abs_fF = 1000 * a1abs_pA / (w * mod_voltage_mV)
            a1arg = np.angle(np.average(pix[1]))
            
            a2abs_V = 2 * np.abs(np.average(pix[2]))
            a2abs_pA = a2abs_V / tia_gain_V_per_pA
            a2abs_fF = 1000 * a2abs_pA / (w * mod_voltage_mV)
            a2arg = np.angle(np.average(pix[2]))
            
            self.data_array.emit(np.array([[x, a1refabs, a1refarg, a1abs_pA, a1arg, a1abs_fF, a2abs_pA, a2arg, a2abs_fF]]))
       
        

