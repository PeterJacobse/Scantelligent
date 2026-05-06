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
        
        # Read parameters from gui
        nanonis_or_mla = self.start_parameters["gui"].get("nanonis_mla")
        if nanonis_or_mla == "nanonis": self.logprint(f"Nanonis sweep not yet implemented. Try setting the spectroscopy to MLA")
        spec_button_states = self.start_parameters["gui"].get("spectroscopy_buttons")
        x_axis_label = "Voltage (V)"
        self.logprint(f"{spec_button_states = }")

        # Frequency sweep
        nn_hardware_dict = self.start_parameters["nanonis"].get("hardware", {})
        mod_voltage_mV = 500
        [tia_gain, tia_gain_V_per_pA] = [nn_hardware_dict.get(key) for key in ["current_gain", "gain (V/pA)"]]        
        self.output_file.attrs.update({"modulator amplitude (mV)": mod_voltage_mV, "tia gain setting:": tia_gain, "tia gain (V/pA)": tia_gain_V_per_pA})
        
        # Set up the output data
        channel_names = ["f1 (Hz)", "|a1_ref| (mV)", "arg(a1_ref) (rad)", "|a1| (mV)", "|a1| (pA)", "|C1| (fF)", "arg(a1) (rad)", "|a2| (mV)", "|a2| (pA)", "|C2| (fF)", "arg(a2) (rad)"]
        channels_dict = {i: name for i, name in enumerate(channel_names)} | {"dict_name": "channels"} # Prepare the GUI for plotting these channels
        self.parameters.emit(channels_dict)
        measurement_ds = self.output_file.create_dataset("sweep", (len(channel_names), 0), maxshape = (len(channel_names), None), chunks = True, dtype = float)
        
        
        
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
            pix = mla.get_pixels(1) # Throw away 1 pixel (settling)
            pix = mla.get_pixels(4)
            
            a1refabs = 1000 * np.abs(np.average(pix[0])) # Output directly copied to the MLA port 1 in
            a1refarg = np.angle(np.average(pix[0]))
            
            a1abs_mV = 1000 * np.abs(np.average(pix[1])) # Displacement currents measured through the TIA
            a1abs_pA = a1abs_mV / (1000 * tia_gain_V_per_pA)
            a1abs_fF = 1000 * a1abs_pA / (w * mod_voltage_mV)
            a1arg = np.angle(np.average(pix[1]))
            
            a2abs_mV = 1000 * np.abs(np.average(pix[2]))
            a2abs_pA = a2abs_mV / (1000 * tia_gain_V_per_pA)
            a2abs_fF = 1000 * a2abs_pA / (w * mod_voltage_mV)
            a2arg = np.angle(np.average(pix[2]))
            
            data_chunk = np.array([[x, a1refabs, a1refarg, a1abs_mV, a1abs_pA, a1abs_fF, a1arg, a2abs_mV, a2abs_pA, a2abs_fF, a2arg]], dtype = float)
            self.data_array.emit(data_chunk)
            measurement_ds.resize((measurement_ds.shape[0], measurement_ds.shape[1] + 1))
            measurement_ds[:, -1] = data_chunk
