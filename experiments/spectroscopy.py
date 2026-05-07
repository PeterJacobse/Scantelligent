import sys, os, time
import numpy as np
from scipy.ndimage import gaussian_filter
import h5py

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
        gui_parameters = self.start_parameters["gui"]
        [spec_button_states, spec_line_edits] = [gui_parameters.get(key) for key in ["spectroscopy_buttons", "spectroscopy_line_edits"]]
        nanonis_or_mla = spec_button_states.get("nanonis_mla")
        if nanonis_or_mla == "nanonis": self.logprint(f"Nanonis sweep not yet implemented. Try setting the spectroscopy to MLA")
        
        mod_voltage_mV = 500
        pixels_per_datapoint = 4
        
        # Read what kind of spectroscopic axes are requested
        if spec_button_states.get("V") == "x":
            x_axis_label = "voltage (V)"
            [V_start_V, V_end_V, n_steps] = [spec_line_edits.get(key) for key in ["V_start", "V_end", "V_points"]]
            x_values = np.linspace(V_start_V, V_end_V, n_steps)
            dV = (V_end_V - V_start_V) / (n_steps - 1)
            
            self.output_file.attrs.update({"V start (V)": V_start_V, "V end (V)": V_end_V, "dV (V)": dV, "steps": n_steps})
        elif spec_button_states.get("z") == "x":
            x_axis_label = "tip height (nm)"
            [z_start_nm, z_end_nm, n_steps] = [spec_line_edits.get(key) for key in ["z_start", "z_end", "z_points"]]
            x_values = np.linspace(z_start_nm, z_end_nm, n_steps)
            dz = (z_end_nm - z_start_nm) / (n_steps - 1)
            
            self.output_file.attrs.update({"z start (nm)": f_start_Hz, "z end (nm)": f_end_Hz, "dz (nm)": dz, "steps": n_steps})
        elif spec_button_states.get("f") == "x":
            x_axis_label = "frequency (Hz)"
            [f_start_Hz, f_end_Hz, n_steps] = [spec_line_edits.get(key) for key in ["f_start", "f_end", "f_points"]]
            x_values = np.linspace(f_start_Hz, f_end_Hz, n_steps)
            df = (f_end_Hz - f_start_Hz) / (n_steps - 1)
            
            self.output_file.attrs.update({"f start (Hz)": f_start_Hz, "f end (Hz)": f_end_Hz, "df (Hz)": df, "steps": n_steps})
        else:
            raise Exception("No parameter selected to sweep on the x axis. Aborting experiment")

        
        
        # Read parameters from Nanonis
        nn_hardware_dict = self.start_parameters["nanonis"].get("hardware", {})
        [tia_gain, tia_gain_V_per_pA] = [nn_hardware_dict.get(key) for key in ["current_gain", "gain (V/pA)"]]
        self.output_file.attrs.update({"x axis": x_axis_label, "modulator amplitude (mV)": mod_voltage_mV, "tia gain setting": tia_gain, "tia gain (V/pA)": tia_gain_V_per_pA, "f / df": 1, "setling time (1 / df)": 1, "pixels per datapoint (1 / df)": pixels_per_datapoint})

        # Initialize the MLA
        mla.amplitudes_update({"amplitudes (mV)": {0: mod_voltage_mV, 1: 0}}) # Set the amplitude of modulator 0 to 100 mV and that of number 1 to 120 mV
        mla.set_input_multiplexer([1, 2, 2])
        mla.outputs_update({"blank": True, "mod0": {"on": True, "port": 1}}) # Output modulator 1 onto port 1
        
        # Perform the sweep
        self.frequency_sweep(x_values, pixels_per_datapoint = pixels_per_datapoint, mod_voltage_mV = mod_voltage_mV)


   
    def frequency_sweep(self, frequencies = np.ndarray, pixels_per_datapoint: int = 4, mod_voltage_mV: float = 500):
        (hardware_dict, error) = self.nanonis.hardware_update()
        tia_gain_V_per_pA = hardware_dict.get("gain (V/pA)")
        
        channel_names = ["f1 (Hz)", "|a1_ref| (mV)", "arg(a1_ref) (rad)", "|a1| (mV)", "|a1| (pA)", "|C1| (fF)", "arg(a1) (rad)", "|a2| (mV)", "|a2| (pA)", "|C2| (fF)", "arg(a2) (rad)"]
        channels_dict = {i: name for i, name in enumerate(channel_names)} | {"dict_name": "channels"} # Prepare the GUI for plotting these channels
        self.parameters.emit(channels_dict)
        
        measurement_ds = self.output_file.create_dataset("sweep", (len(channel_names), 0), maxshape = (len(channel_names), None), chunks = True, dtype = float)
        channels_ds = self.output_file.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8"))
        channels_ds.make_scale("channels")
        frequency_ds = self.output_file.create_dataset("frequency axis", data = frequencies)
        frequency_ds.make_scale("frequency (Hz)")        

        # Main loop
        self.mla.start_lockin()
        for f in frequencies:
            self.check_abort_request()
            w = 2 * np.pi * int(f)
            self.mla.time_constant_update({"df (Hz)": int(f)}, verbose = False) # Set the measurement resolution to 200 Hz. This corresponds to a primitive time constant or period of 5 ms.
            self.mla.frequencies_update({"numbers": [1, 1, 2, 3]}, verbose = False) # Frequencies set in units of numbers of whole oscillations per period
            
            self.mla.get_pixels(1) # Throw away 1 pixel (settling)
            pix = self.mla.get_pixels(pixels_per_datapoint)
            
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
            
            data_chunk = np.array([[f, a1refabs, a1refarg, a1abs_mV, a1abs_pA, a1abs_fF, a1arg, a2abs_mV, a2abs_pA, a2abs_fF, a2arg]], dtype = float)
            self.data_array.emit(data_chunk)
            measurement_ds.resize((measurement_ds.shape[0], measurement_ds.shape[1] + 1))
            measurement_ds[:, -1] = data_chunk        
        
        measurement_ds.dims[0].attach_scale(channels_ds)
        measurement_ds.dims[1].attach_scale(frequency_ds)
        return
