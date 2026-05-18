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
        # Aliases
        nn = self.nanonis
        mla = self.mla
        
        #connected_device = self.connection_test(frequency_Hz = 600, amplitude_mV = 200, verbose = False, autophase = True)
        #self.logprint(f"{connected_device = }")
        #if not connected_device == "mla":
        #    raise Exception("The bias cable does not seem to be connected to the MLA. This experiment requires the MLA. Please connect the bias cable to the MLA first")
        
        # Read parameters from gui
        gui_parameters = self.start_parameters["gui"]
        [spec_button_states, spec_line_edits] = [gui_parameters.get(key) for key in ["spectroscopy_buttons", "spectroscopy_line_edits"]]
        [t_settle, t_int] = [int(spec_line_edits[f"t_{key}"]) for key in ["settle", "int"]]
        nanonis_or_mla = spec_button_states.get("nanonis_mla")
        if nanonis_or_mla == "nanonis": raise Exception(f"Nanonis sweep not yet implemented. Try setting the spectroscopy to MLA")
        
        [x_start, x_end, x_steps] = [spec_line_edits.get(key) for key in ["x_start", "x_end", "x_points"]]
        x_values = np.linspace(x_start, x_end, x_steps)
        dx = (x_end - x_start) / (x_steps - 1)
        [y_start, y_end, y_steps] = [spec_line_edits.get(key) for key in ["y_start", "y_end", "y_points"]]
        if isinstance(y_start, int | float) and isinstance(y_end, int | float):
            y_values = np.linspace(y_start, y_end, y_steps)
            dy = (y_end - y_start) / (y_steps - 1)
        
        """
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
        """
        
        # Read parameters from Nanonis
        nn_hardware_dict = self.start_parameters["nanonis"].get("hardware", {})
        [tia_gain, tia_gain_V_per_pA] = [nn_hardware_dict.get(key) for key in ["current_gain", "gain (V/pA)"]]
        (amplitudes, error) = mla.amplitudes_update()
        mod_voltage_mV = amplitudes.get("amplitudes (mV)")[0]
        self.output_file.attrs.update({"modulator amplitude (mV)": mod_voltage_mV, "tia gain setting": tia_gain, "tia gain (V/pA)": tia_gain_V_per_pA, "f / df": 1, "setling time (1 / df)": 1, "pixels per datapoint (1 / df)": t_int})

        # Read what kind of spectroscopic axes are requested
        x_values = None
        x_axis_label = ""
        y_values = None
        y_axis_label = ""
        x_ds = None
        y_ds = None

        match spec_button_states["x_axis"].state_name:
            case "V":
                x_axis_label = "voltage (V)"
                x_values = np.concatenate((x_values, x_values[::-1]))
                self.output_file.attrs.update({"V start (V)": x_start, "V end (V)": x_end, "dV (V)": dx, "steps": x_steps})
                x_ds = self.output_file.create_dataset("voltage axis", data = x_values)

            case "z":
                x_axis_label = "tip height (nm)"
                x_values = x_values
                self.output_file.attrs.update({"z start (nm)": x_start, "z end (nm)": x_end, "dz (nm)": dx, "steps": x_steps})
                x_ds = self.output_file.create_dataset("tip height axis", data = x_values)
            
                """
                case "f":
                    x_axis_label = "frequency (Hz)"
                    x_values = f_linspace
                    self.output_file.attrs.update({"f start (Hz)": f_start_Hz, "f end (Hz)": f_end_Hz, "df (Hz)": df, "steps": n_steps})
                    x_ds = self.output_file.create_dataset("frequency axis", data = x_values)

                case "amp":
                    x_axis_label = "amplitude (mV)"
                    x_values = amp_linspace
                    self.output_file.attrs.update({"amp start (mV)": amp_start_mV, "amp end (mV)": amp_end_mV, "damp (mV)": damp, "steps": n_steps})
                    x_ds = self.output_file.create_dataset("amplitude axis", data = x_values)

                """
            case _:
                pass

                    
        if not isinstance(x_values, np.ndarray): raise Exception("No parameter selected to sweep on the x axis. Aborting experiment")
        x_ds.make_scale(x_axis_label)
        self.output_file.attrs.update({"x axis": x_axis_label})

        # y axis
        match spec_button_states["y_axis"].state_name:
            case _:
                pass

                """
            case "V":
                y_axis_label = "voltage (V)"
                y_values = V_linspace
                y_values = np.concatenate((y_values, y_values[::-1]))
                self.output_file.attrs.update({"V start (V)": V_start_V, "V end (V)": V_end_V, "dV (V)": dV, "steps": n_steps})
                y_ds = self.output_file.create_dataset("voltage axis", shape = (0,), maxshape = (len(y_values),), dtype = float)
            
            elif spec_button_states.get("z") == "y":
                y_axis_label = "tip height (nm)"
                y_values = z_linspace
                self.output_file.attrs.update({"z start (nm)": z_start_nm, "z end (nm)": z_end_nm, "dz (nm)": dz, "steps": n_steps})
                y_ds = self.output_file.create_dataset("tip height axis", shape = (0,), maxshape = (len(y_values),), dtype = float)
            
            elif spec_button_states.get("f") == "y":
                y_axis_label = "frequency (Hz)"
                y_values = f_linspace
                self.output_file.attrs.update({"f start (Hz)": f_start_Hz, "f end (Hz)": f_end_Hz, "df (Hz)": df, "steps": n_steps})
                y_ds = self.output_file.create_dataset("frequency axis", shape = (0,), maxshape = (len(y_values),), dtype = float)

            elif spec_button_states.get("amp") == "y":
                y_axis_label = "amplitude (mV)"
                y_values = amp_linspace
                self.output_file.attrs.update({"amp start (mV)": amp_start_mV, "amp end (mV)": amp_end_mV, "damp (mV)": damp, "steps": n_steps})
                y_ds = self.output_file.create_dataset("amplitude axis", shape = (0,), maxshape = (len(y_values),), dtype = float)
                """
        if "y" in [spec_button_states.get(key) for key in ["V", "z", "f", "amp"]] and isinstance(y_values, np.ndarray):
            self.output_file.attrs.update({"y axis": y_axis_label})
            y_ds.make_scale(y_axis_label)        



        # Perform the sweep
        match y_axis_label:
            case "voltage (V)": # Experiments that sweep along one parameter while slowly ramping the bias                
                match x_axis_label:
                    case "frequency (Hz)": # Frequency sweeps on the x axis while sweeping voltage on the y axis                        
                        # Go to initial value and perform a single sweep to retrieve the channels and single sweep array
                        voltage = y_values[0]
                        mla.bias_update({"port_1 (V)": voltage}, verbose = False)
                        (single_sweep_array, sweep_channel_names) = self.mla_frequency_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True) # Perform the measurement and retrieve the data as a numpy array
                        
                        # Extract data from the first measurement and set up a measurement array accordingly
                        channel_names = np.insert(sweep_channel_names, 0, "voltage (V)")
                        single_sweep_array_with_voltage = np.insert(single_sweep_array, 0, voltage, axis = 1)
                        sweep_array_shape = single_sweep_array_with_voltage.shape
                        
                        # Create the measurement array with the right size
                        measurement_array = np.zeros((len(y_values), len(x_values), len(channel_names)))
                        measurement_array[0] = single_sweep_array_with_voltage
                        
                        # Create the hdf5 dataset
                        measurement_ds = self.output_file.create_dataset("sweep", shape = (0,) + sweep_array_shape, maxshape = measurement_array.shape, dtype = float)
                        channels_ds = self.output_file.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8")) # z axis (channels)
                        channels_ds.make_scale("channels")
                        measurement_ds.dims[2].attach_scale(channels_ds)
                        measurement_ds.dims[1].attach_scale(x_ds)
                        measurement_ds.dims[0].attach_scale(y_ds)
                        
                        # Perform the sweep
                        n_total = len(y_values)
                        for index, voltage in enumerate(y_values):
                            self.exp_progress.emit(int(100 * index / n_total))
                            mla.bias_update({"port_1 (V)": voltage}, verbose = False)
                            (single_sweep_array, sweep_channel_names) = self.mla_frequency_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True) # Perform the measurement and retrieve the data as a numpy array
                            single_sweep_array_with_voltage = np.insert(single_sweep_array, 0, voltage, axis = 1) # Insert the voltage
                            measurement_array[0] = single_sweep_array_with_voltage
                            
                            measurement_ds.resize((index + 1,) + sweep_array_shape)
                            y_ds.resize((index + 1,))
                            measurement_ds[index, :, :] = single_sweep_array_with_voltage
                            y_ds[index] = voltage
                        
                        self.exp_progress.emit(100)
                    
                    case "amplitude (mV)": # Increasing the amplitude at each bias voltage point
                        # Go to initial value and perform a single sweep to retrieve the channels and single sweep array
                        voltage = y_values[0]
                        mla.bias_update({"port_1 (V)": voltage}, verbose = False)
                        (single_sweep_array, sweep_channel_names) = self.mla_amplitude_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True) # Perform the measurement and retrieve the data as a numpy array
                        
                        # Extract data from the first measurement and set up a measurement array accordingly
                        channel_names = np.insert(sweep_channel_names, 0, "voltage (V)")
                        single_sweep_array_with_voltage = np.insert(single_sweep_array, 0, voltage, axis = 1)
                        sweep_array_shape = single_sweep_array_with_voltage.shape
                        
                        # Create the measurement array with the right size
                        measurement_array = np.zeros((len(y_values), len(x_values), len(channel_names)))
                        measurement_array[0] = single_sweep_array_with_voltage
                        
                        # Create the hdf5 dataset
                        measurement_ds = self.output_file.create_dataset("sweep", shape = (0,) + sweep_array_shape, maxshape = measurement_array.shape, dtype = float)
                        channels_ds = self.output_file.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8")) # z axis (channels)
                        channels_ds.make_scale("channels")
                        measurement_ds.dims[2].attach_scale(channels_ds)
                        measurement_ds.dims[1].attach_scale(x_ds)
                        measurement_ds.dims[0].attach_scale(y_ds)
                        
                        # Perform the sweep
                        n_total = len(y_values)
                        for index, voltage in enumerate(y_values):
                            self.exp_progress.emit(int(100 * index / n_total))
                            mla.bias_update({"port_1 (V)": voltage}, verbose = False)
                            (single_sweep_array, sweep_channel_names) = self.mla_amplitude_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True) # Perform the measurement and retrieve the data as a numpy array
                            single_sweep_array_with_voltage = np.insert(single_sweep_array, 0, voltage, axis = 1) # Insert the voltage
                            measurement_array[0] = single_sweep_array_with_voltage
                            
                            measurement_ds.resize((index + 1,) + sweep_array_shape)
                            y_ds.resize((index + 1,))
                            measurement_ds[index, :, :] = single_sweep_array_with_voltage
                            y_ds[index] = voltage
                        
                        self.exp_progress.emit(100)
                    
                    case _:
                        self.logprint(f"Not yet implemented")
            
            
            
            case "amplitude (mV)":
                match x_axis_label:                    
                    case "voltage (V)": # Bias spectroscopy at increasing amplitude values
                        # Go to initial value and perform a single sweep to retrieve the channels and single sweep array
                        amp_mV = y_values[0]
                        mla.amplitudes_update({"amplitudes (mV)": {0: amp_mV}}, verbose = False)
                        (single_sweep_array, sweep_channel_names) = self.mla_voltage_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True) # Perform the measurement and retrieve the data as a numpy array
                        
                        # Extract data from the first measurement and set up a measurement array accordingly
                        channel_names = np.insert(sweep_channel_names, 0, "amplitude (mV)")
                        single_sweep_array_with_amplitude = np.insert(single_sweep_array, 0, amp_mV, axis = 1)
                        sweep_array_shape = single_sweep_array_with_amplitude.shape
                        
                        # Create the measurement array with the right size
                        measurement_array = np.zeros((len(y_values), len(x_values), len(channel_names)))
                        measurement_array[0] = single_sweep_array_with_amplitude
                        
                        # Create the hdf5 dataset
                        measurement_ds = self.output_file.create_dataset("sweep", shape = (0,) + sweep_array_shape, maxshape = measurement_array.shape, dtype = float)
                        channels_ds = self.output_file.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8")) # z axis (channels)
                        channels_ds.make_scale("channels")
                        measurement_ds.dims[2].attach_scale(channels_ds)
                        measurement_ds.dims[1].attach_scale(x_ds)
                        measurement_ds.dims[0].attach_scale(y_ds)
                        
                        # Perform the sweep
                        n_total = len(y_values)
                        for index, amp_mV in enumerate(y_values):
                            self.exp_progress.emit(int(100 * index / n_total))
                            mla.amplitudes_update({"amplitudes (mV)": {0: amp_mV}}, verbose = False)
                            (single_sweep_array, sweep_channel_names) = self.mla_voltage_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True) # Perform the measurement and retrieve the data as a numpy array
                            single_sweep_array_with_amplitude = np.insert(single_sweep_array, 0, amp_mV, axis = 1) # Insert the amplitude
                            measurement_array[0] = single_sweep_array_with_amplitude
                            
                            measurement_ds.resize((index + 1,) + sweep_array_shape)
                            y_ds.resize((index + 1,))
                            measurement_ds[index, :, :] = single_sweep_array_with_amplitude
                            y_ds[index] = amp_mV
                        
                        self.exp_progress.emit(100)

                    case "frequency (Hz)": # Frequency sweeps on the x axis while sweeping voltage on the y axis                        
                        # Go to initial value and perform a single sweep to retrieve the channels and single sweep array
                        amp_mV = y_values[0]
                        mla.amplitudes_update({"amplitudes (mV)": {0: amp_mV}}, verbose = False)
                        (single_sweep_array, sweep_channel_names) = self.mla_frequency_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True) # Perform the measurement and retrieve the data as a numpy array
                        
                        # Extract data from the first measurement and set up a measurement array accordingly
                        channel_names = np.insert(sweep_channel_names, 0, "voltage (V)")
                        single_sweep_array_with_amplitude = np.insert(single_sweep_array, 0, amp_mV, axis = 1)
                        sweep_array_shape = single_sweep_array_with_amplitude.shape
                        
                        # Create the measurement array with the right size
                        measurement_array = np.zeros((len(y_values), len(x_values), len(channel_names)))
                        measurement_array[0] = single_sweep_array_with_amplitude
                        
                        # Create the hdf5 dataset
                        measurement_ds = self.output_file.create_dataset("sweep", shape = (0,) + sweep_array_shape, maxshape = measurement_array.shape, dtype = float)
                        channels_ds = self.output_file.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8")) # z axis (channels)
                        channels_ds.make_scale("channels")
                        measurement_ds.dims[2].attach_scale(channels_ds)
                        measurement_ds.dims[1].attach_scale(x_ds)
                        measurement_ds.dims[0].attach_scale(y_ds)
                        
                        # Perform the sweep
                        n_total = len(y_values)
                        for index, amp_mV in enumerate(y_values):
                            self.exp_progress.emit(int(100 * index / n_total))
                            mla.amplitudes_update({"amplitudes (mV)": {0: amp_mV}}, verbose = False)
                            (single_sweep_array, sweep_channel_names) = self.mla_frequency_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True) # Perform the measurement and retrieve the data as a numpy array
                            single_sweep_array_with_amplitude = np.insert(single_sweep_array, 0, amp_mV, axis = 1) # Insert the amplitude
                            measurement_array[0] = single_sweep_array_with_amplitude
                            
                            measurement_ds.resize((index + 1,) + sweep_array_shape)
                            y_ds.resize((index + 1,))
                            measurement_ds[index, :, :] = single_sweep_array_with_amplitude
                            y_ds[index] = amp_mV
                        
                        self.exp_progress.emit(100)
                    
                    case _:
                        self.logprint(f"Not yet implemented")



            case _: # Pure x-axis measurements
                channel_names = [] # TBD                
                match x_axis_label:                    
                    case "frequency (Hz)": # Simple frequency sweep (capacitive)                        
                        """
                        Frequency sweeps are assumed to target the tip-sample capacitance.
                        A pure tone is set on port 1, and the response is converted into capacitance in femtoFarad using the calculated displacement current (from the TIA gain setting) and the frequency.
                        This measurement uses a reference of the applied tone on input 1 and measures the response from the STM on input 2.
                        The response of the second harmonic is captured as well.
                        """
                        (measurement_array, channel_names) = self.mla_frequency_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True) # Perform the measurement and retrieve the data as a numpy array
                    
                    case "amplitude (mV)": # Simple amplitude sweep
                        """
                        Amplitude sweeps show how the higher harmonic peaks increase in amplitude with increasing drive.
                        The responses are converted to conductances.
                        A pure tone is set on port 1, a reference of the applied tone is measured on input 1, and the response from the STM is measured on input 2.
                        """
                        (measurement_array, channel_names) = self.mla_amplitude_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True) # Perform the measurement and retrieve the data as a numpy array

                    case "voltage (V)": # Simple voltage sweep
                        (measurement_array, channel_names) = self.mla_voltage_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True) # Perform the measurement and retrieve the data as a numpy array
                        
                    case "tip height (nm)":
                        self.logprint("Z sweep is not yet implemented")
                    
                    case _:
                        pass
                
                self.exp_progress.emit(100)
                measurement_ds = self.output_file.create_dataset("sweep", data = measurement_array, dtype = float)
                channels_ds = self.output_file.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8"))
                channels_ds.make_scale("channels")
                measurement_ds.dims[0].attach_scale(channels_ds)
                measurement_ds.dims[1].attach_scale(x_ds)







