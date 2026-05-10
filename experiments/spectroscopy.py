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
        #[self.connect_hardware(component) for component in ["nanonis", "mla"]] # Set up the required hardware connections
        
        # Aliases
        nn = self.nanonis
        mla = self.mla
        
        # Read parameters from gui
        gui_parameters = self.start_parameters["gui"]
        [spec_button_states, spec_line_edits] = [gui_parameters.get(key) for key in ["spectroscopy_buttons", "spectroscopy_line_edits"]]
        [t_settle, t_int] = [int(spec_line_edits[f"t_{key}"]) for key in ["settle", "int"]]
        nanonis_or_mla = spec_button_states.get("nanonis_mla")
        if nanonis_or_mla == "nanonis": raise Exception(f"Nanonis sweep not yet implemented. Try setting the spectroscopy to MLA")
        
        [V_start_V, V_end_V, n_steps] = [spec_line_edits.get(key) for key in ["V_start", "V_end", "V_points"]]
        V_linspace = np.linspace(V_start_V, V_end_V, n_steps)
        dV = (V_end_V - V_start_V) / (n_steps - 1)
        [z_start_nm, z_end_nm, n_steps] = [spec_line_edits.get(key) for key in ["z_start", "z_end", "z_points"]]
        z_linspace = np.linspace(z_start_nm, z_end_nm, n_steps)
        dz = (z_end_nm - z_start_nm) / (n_steps - 1)
        [f_start_Hz, f_end_Hz, n_steps] = [spec_line_edits.get(key) for key in ["f_start", "f_end", "f_points"]]
        f_linspace = np.linspace(f_start_Hz, f_end_Hz, n_steps)
        df = (f_end_Hz - f_start_Hz) / (n_steps - 1)
        [amp_start_mV, amp_end_mV, n_steps] = [spec_line_edits.get(key) for key in ["amp_start", "amp_end", "amp_points"]]
        amp_linspace = np.linspace(amp_start_mV, amp_end_mV, n_steps)
        damp = (amp_end_mV - amp_start_mV) / (n_steps - 1)
        
        # Read parameters from Nanonis
        nn_hardware_dict = self.start_parameters["nanonis"].get("hardware", {})
        [tia_gain, tia_gain_V_per_pA] = [nn_hardware_dict.get(key) for key in ["current_gain", "gain (V/pA)"]]
        (amplitudes, error) = mla.amplitudes_update()
        mod_voltage_mV = amplitudes.get("amplitudes (mV)")[0]
        self.output_file.attrs.update({"modulator amplitude (mV)": mod_voltage_mV, "tia gain setting": tia_gain, "tia gain (V/pA)": tia_gain_V_per_pA, "f / df": 1, "setling time (1 / df)": 1, "pixels per datapoint (1 / df)": t_int})

        # Read what kind of spectroscopic axes are requested
        x_values = None
        y_values = None

        if spec_button_states.get("V") == "x":
            x_axis_label = "voltage (V)"
            x_values = V_linspace
            self.output_file.attrs.update({"V start (V)": V_start_V, "V end (V)": V_end_V, "dV (V)": dV, "steps": n_steps})
        
        elif spec_button_states.get("z") == "x":
            x_axis_label = "tip height (nm)"
            x_values = z_linspace
            self.output_file.attrs.update({"z start (nm)": z_start_nm, "z end (nm)": z_end_nm, "dz (nm)": dz, "steps": n_steps})
        
        elif spec_button_states.get("f") == "x":
            x_axis_label = "frequency (Hz)"
            x_values = f_linspace
            self.output_file.attrs.update({"f start (Hz)": f_start_Hz, "f end (Hz)": f_end_Hz, "df (Hz)": df, "steps": n_steps})

        elif spec_button_states.get("amp") == "x":
            x_axis_label = "amplitude (mV)"
            x_values = amp_linspace
            self.output_file.attrs.update({"amp start (mV)": f_start_Hz, "amp end (mV)": f_end_Hz, "damp (mV)": df, "steps": n_steps})

        # y axis
        if spec_button_states.get("V") == "y":
            y_axis_label = "voltage (V)"
            y_values = V_linspace
            self.output_file.attrs.update({"V start (V)": V_start_V, "V end (V)": V_end_V, "dV (V)": dV, "steps": n_steps})
        
        elif spec_button_states.get("z") == "y":
            y_axis_label = "tip height (nm)"
            y_values = z_linspace
            self.output_file.attrs.update({"z start (nm)": z_start_nm, "z end (nm)": z_end_nm, "dz (nm)": dz, "steps": n_steps})
        
        elif spec_button_states.get("f") == "y":
            y_axis_label = "frequency (Hz)"
            y_values = f_linspace
            self.output_file.attrs.update({"f start (Hz)": f_start_Hz, "f end (Hz)": f_end_Hz, "df (Hz)": df, "steps": n_steps})

        elif spec_button_states.get("amp") == "y":
            y_axis_label = "amplitude (mV)"
            y_values = amp_linspace
            self.output_file.attrs.update({"amp start (mV)": f_start_Hz, "amp end (mV)": f_end_Hz, "damp (mV)": df, "steps": n_steps})

        if not isinstance(x_values, np.ndarray): raise Exception("No parameter selected to sweep on the x axis. Aborting experiment")
        self.output_file.attrs.update({"x axis": x_axis_label})
        if isinstance(y_values, np.ndarray): self.output_file.attrs.update({"y-axis": y_axis_label})



        # Perform the sweep
        match x_axis_label:
            case "frequency (Hz)":
                """
                Frequency sweeps are assumed to target the tip-sample capacitance.
                A pure tone is set on port 1, and the response is converted into capacitance in femtoFarad using the calculated displacement current (from the TIA gain setting) and the frequency.
                This measurement uses a reference of the applied tone on input 1 and measures the response from the STM on input 2.
                The response of the second harmonic is captured as well.
                """
                
                # Initialize the MLA.
                mla.set_input_multiplexer([1, 2, 2])
                mla.outputs_update({"blank": True, "mod0": {"on": True, "port": 1}}) # Output modulator 1 onto port 1
                if mod_voltage_mV < .01: mla.amplitudes_update({"amplitudes (mV)": {0: 500}}) # If the amplitude was not yet set, default to 500 mV
                        
                (measurement_array, channel_names) = self.mla_frequency_sweep(x_values, settle_pixels = 1, pixels_per_datapoint = t_int) # Perform the measurement and retrieve the data as a numpy array
                measurement_ds = self.output_file.create_dataset("sweep", data = measurement_array, dtype = float)
                channels_ds = self.output_file.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8"))
                channels_ds.make_scale("channels")
                frequency_ds = self.output_file.create_dataset("frequency axis", data = x_values)
                frequency_ds.make_scale("frequency (Hz)")                
                measurement_ds.dims[0].attach_scale(channels_ds)
                measurement_ds.dims[1].attach_scale(frequency_ds)
            
            case "amplitude (mV)":
                """
                Amplitude sweeps show how the higher harmonic peaks increase in amplitude with increasing drive.
                The responses are converted to conductances.
                A pure tone is set on port 1, a reference of the applied tone is measured on input 1, and the response from the STM is measured on input 2.
                """
                
                # Initialize the MLA
                mla.set_input_multiplexer([1, 2, 2])
                mla.outputs_update({"blank": True, "mod0": {"on": True, "port": 1}}) # Output modulator 1 onto port 1
                        
                (measurement_array, channel_names) = self.mla_amplitude_sweep(x_values, settle_pixels = 1, pixels_per_datapoint = t_int) # Perform the measurement and retrieve the data as a numpy array
                measurement_ds = self.output_file.create_dataset("sweep", data = measurement_array, dtype = float)
                channels_ds = self.output_file.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8"))
                channels_ds.make_scale("channels")
                amplitude_ds = self.output_file.create_dataset("amplitude axis", data = x_values)
                amplitude_ds.make_scale("frequency (Hz)")
                measurement_ds.dims[0].attach_scale(channels_ds)
                measurement_ds.dims[1].attach_scale(amplitude_ds)
            
            case "voltage (V)":
                self.logprint("Performing a voltage sweep")
            
            case "tip height (nm)":
                self.logprint("Performing a z sweep")
            
            case _:
                pass





