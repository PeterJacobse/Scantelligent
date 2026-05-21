import sys, os, time, re, h5py
import numpy as np
from scipy.ndimage import gaussian_filter
from datetime import datetime

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
        
        #if not connected_device == "mla":
        #    raise Exception("The bias cable does not seem to be connected to the MLA. This experiment requires the MLA. Please connect the bias cable to the MLA first")
        
        # Read parameters from gui
        gui_parameters = self.start_parameters["gui"]
        [spec_button_states, spec_line_edits] = [gui_parameters.get(key) for key in ["spectroscopy_buttons", "spectroscopy_line_edits"]]
        self.logprint(f"I read the following things from the gui", message_type = "warning")
        self.logprint(f"{spec_button_states = }", message_type = "result")
        self.logprint(f"{spec_line_edits = }", message_type = "warning")
        self.logprint(f"{self.experiment_file = }")
        
        [t_settle, t_int] = [int(spec_line_edits[f"t_{key}"]) for key in ["settle", "int"]]
        nanonis_or_mla = spec_button_states.get("nanonis_mla")
        """
        connected_device = self.connection_test(frequency_Hz = 600, amplitude_mV = 200, verbose = False, autophase = True)
        if not connected_device == nanonis_or_mla:
            self.logprint(f"Warning. The STM seems to be connected to {connected_device}. However, an experiment using {nanonis_or_mla} was requested", message_type = "warning")
        if not connected_device == "mla":
            self.logprint(f"Warning. Only spectroscopy using the MLA is supported at this moment.", message_type = "warning")
        """
       
        # Read parameters from Nanonis
        nn_hardware_dict = self.start_parameters["nanonis"].get("hardware", {})
        [tia_gain, tia_gain_V_per_pA] = [nn_hardware_dict.get(key) for key in ["current_gain", "gain (V/pA)"]]
        (amplitudes, error) = mla.amplitudes_update(verbose = False)
        mod_voltage_mV = amplitudes.get("amplitudes (mV)")[0]
        

        
        # Set up spectroscopy axes
        experiment_filename = "spectroscopy"
        # x axis
        x_values = None
        x_axis_label = ""
        x_ds = None
        
        [x_start, x_end, x_steps] = [spec_line_edits.get(key) for key in ["x_start", "x_end", "x_points"]]
        x_values = np.linspace(x_start, x_end, x_steps)
        dx = (x_end - x_start) / (x_steps - 1)
        
        match spec_button_states["x_axis"]:
            case "V":
                x_axis_label = "voltage (V)"
                experiment_filename = "V_" + experiment_filename
                
                if spec_button_states.get("V_retrace", False): x_values = np.concatenate((x_values, x_values[::-1]))
                x_axis_info = {"V start (V)": x_start, "V end (V)": x_end, "dV (V)": dx, "V steps": x_steps}
                x_ds = self.output_file.create_dataset("voltage axis", data = x_values)
                
                x_measurement = lambda insert_parameter: mla.voltage_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True,
                                                                           tia_gain_V_per_pA = tia_gain_V_per_pA, insert_parameter = insert_parameter, return_type = "conductance",
                                                                           abort_callback = self.check_abort_request, data_array_callback = self.data_array.emit, graph_callback = self.prepare_graph)
            case "z":
                x_axis_label = "tip height (nm)"
                experiment_filename = "z_" + experiment_filename
                
                if spec_button_states.get("z_retrace", False): x_values = np.concatenate((x_values, x_values[::-1]))
                x_axis_info = {"z start (nm)": x_start, "z end (nm)": x_end, "dz (nm)": dx, "z steps": x_steps}
                x_ds = self.output_file.create_dataset("tip height axis", data = x_values)
                
                # x_measurement not yet defined
            case "f":
                x_axis_label = "frequency (Hz)"
                experiment_filename = "f_" + experiment_filename
                
                if spec_button_states.get("f_retrace", False): x_values = np.concatenate((x_values, x_values[::-1]))
                x_axis_info = {"f start (Hz)": x_start, "f end (Hz)": x_end, "df (Hz)": dx, "f steps": x_steps}
                x_ds = self.output_file.create_dataset("frequency axis", data = x_values)
                
                x_measurement = lambda insert_parameter: mla.frequency_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True,
                                                                             tia_gain_V_per_pA = tia_gain_V_per_pA, insert_parameter = insert_parameter,
                                                                             abort_callback = self.check_abort_request, data_array_callback = self.data_array.emit, graph_callback = self.prepare_graph)
            case "amp":
                x_axis_label = "amplitude (mV)"
                experiment_filename = "amp_" + experiment_filename
                
                if spec_button_states.get("amp_retrace", False): x_values = np.concatenate((x_values, x_values[::-1]))
                x_axis_info = {"amp start (mV)": x_start, "amp end (mV)": x_end, "damp (mV)": dx, "amp steps": x_steps}
                x_ds = self.output_file.create_dataset("amplitude axis", data = x_values)
                
                x_measurement = lambda insert_parameter: mla.amplitude_sweep(x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, setup_defaults = True,
                                                                             tia_gain_V_per_pA = tia_gain_V_per_pA, insert_parameter = insert_parameter,
                                                                             abort_callback = self.check_abort_request, data_array_callback = self.data_array.emit, graph_callback = self.prepare_graph)
            case "V_keithley":
                x_axis_label = "V_Keithley (V)"
                experiment_filename = "V_Keithley_" + experiment_filename
                
                if spec_button_states.get("V_keithley_retrace", False): x_values = np.concatenate((x_values, x_values[::-1]))
                x_axis_info = {"V_Keithley start (V)": x_start, "V_Keithley end (V)": x_end, "dV_Keithley (mV)": dx, "V_Keithley steps": x_steps}
                
                # x_measurement not yet defined            
            case _:
                pass

        if not isinstance(x_values, np.ndarray): raise Exception("No parameter selected to sweep on the x axis. Aborting experiment")
        x_ds.make_scale(x_axis_label)
        self.output_file.attrs.update({"x axis": x_axis_label})
        
        
        
        # y axis
        y_values = None
        y_axis_label = ""
        y_ds = None
        
        [y_start, y_end, y_steps] = [spec_line_edits.get(key) for key in ["y_start", "y_end", "y_points"]]
        if isinstance(y_start, int | float) and isinstance(y_end, int | float):
            y_values = np.linspace(y_start, y_end, y_steps)
            dy = (y_end - y_start) / (y_steps - 1)
                
        match spec_button_states["y_axis"]:
            case "V":
                y_axis_label = "voltage (V)"
                split_name = re.split("_", experiment_filename)
                split_name.insert(-1, "V")
                experiment_filename = "_".join(split_name)
                
                y_values = y_values
                y_values = np.concatenate((y_values, y_values[::-1]))
                y_axis_info = {"V start (V)": y_start, "V end (V)": y_end, "dV (V)": dy, "steps": y_steps}
                
                voltage = y_values[0] # Set the MLA to the first value of the y parameter sweep
                mla.bias_update({"port_1 (V)": voltage}, verbose = False)
                (single_sweep_array, channel_names) = x_measurement(insert_parameter = ("voltage (V)", voltage)) # Perform the first sweep on the x axis
            case "z":
                y_axis_label = "tip height (nm)"
                split_name = re.split("_", experiment_filename)
                split_name.insert(-1, "z")
                experiment_filename = "_".join(split_name)
                
                y_values = y_values
                self.output_file.attrs.update({"z start (nm)": y_start, "z end (nm)": y_end, "dz (nm)": dy, "steps": y_steps})
                y_ds = self.output_file.create_dataset("tip height axis", shape = (0,), maxshape = (len(y_values),), dtype = float)
                
                tip_height = y_values[0] # Set to the first value of the y parameter sweep
                nn.tip_update({"feedback": False, "z_rel (nm)": tip_height}, verbose = False)
                (single_sweep_array, channel_names) = x_measurement(insert_parameter = ("z (nm)", tip_height)) # Perform the first sweep on the x axis
            case "f":
                y_axis_label = "frequency (Hz)"
                split_name = re.split("_", experiment_filename)
                split_name.insert(-1, "f")
                experiment_filename = "_".join(split_name)
                
                experiment_filename = "f_" + experiment_filename
                y_values = y_values
                self.output_file.attrs.update({"f start (Hz)": y_start, "f end (Hz)": y_end, "df (Hz)": dy, "steps": y_steps})
                y_ds = self.output_file.create_dataset("frequency axis", shape = (0,), maxshape = (len(y_values),), dtype = float)
                
                f_Hz = y_values[0] # Set the MLA to the first value of the y parameter sweep
                mla.lockin_update({"df (Hz)": f_Hz, "numbers": [1, 1, 2, 3]}, verbose = False)
                (single_sweep_array, channel_names) = x_measurement(insert_parameter = ("frequency (Hz)", f_Hz)) # Perform the first sweep on the x axis
            case "amp":
                y_axis_label = "amplitude (mV)"
                split_name = re.split("_", experiment_filename)
                split_name.insert(-1, "amp")
                experiment_filename = "_".join(split_name)
                
                experiment_filename = "amp_" + experiment_filename
                y_values = y_values
                self.output_file.attrs.update({"amp start (mV)": y_start, "amp end (mV)": y_end, "damp (mV)": dy, "steps": y_steps})
                y_ds = self.output_file.create_dataset("amplitude axis", shape = (0,), maxshape = (len(y_values),), dtype = float)
                
                amp_mV = y_values[0] # Set the MLA to the first value of the y parameter sweep
                mla.amplitudes_update({"amplitudes (mV)": {0: amp_mV}}, verbose = False)
                (single_sweep_array, channel_names) = x_measurement(insert_parameter = ("amplitude (mV)", amp_mV)) # Perform the first sweep on the x axis
            case _: # No parameter on the y axis. Perform a 1D sweep instead
                (single_sweep_array, channel_names) = x_measurement(insert_parameter = None) # Perform the first sweep on the x axis
                self.exp_progress.emit(100)
                
                measurement_ds = self.output_file.create_dataset("sweep", data = single_sweep_array, dtype = float)
                channels_ds = self.output_file.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8"))
                channels_ds.make_scale("channels")
                measurement_ds.dims[0].attach_scale(channels_ds)
                measurement_ds.dims[1].attach_scale(x_ds)
                return
        
        
        
        # Change the experiment file name to include the spectroscopic axes
        experiment_folder = os.path.dirname(self.experiment_file)
        self.experiment_file = self.file_functions.get_next_indexed_filename(experiment_folder, experiment_filename, ".hdf5")[1]
        self.output_file = h5py.File(self.experiment_file, "w") # Open the new HDF5 file
        self.output_file.attrs.update({"date": datetime.now().strftime("%Y/%m/%d"), "time": datetime.now().strftime("%H:%M:%S"), "device": "mla",
                                       "modulator amplitude (mV)": mod_voltage_mV, "tia gain setting": tia_gain, "tia gain (V/pA)": tia_gain_V_per_pA, "f / df": 1, "setling time (1 / df)": 1, "pixels per datapoint (1 / df)": t_int
                                       } | x_axis_info | y_axis_info)
        
        # Create axes data sets
        match spec_button_states["x_axis"]:
            case "V": x_ds = self.output_file.create_dataset("voltage axis (V)", data = x_values)
            case "z": x_ds = self.output_file.create_dataset("tip height axis (nm)", data = x_values)
            case "f": x_ds = self.output_file.create_dataset("frequency axis (Hz)", data = x_values)
            case "amp": x_ds = self.output_file.create_dataset("amplitude axis (Hz)", data = x_values)
            case "V_keithley": x_ds = self.output_file.create_dataset("Keithley voltage axis (V)", data = x_values)
        
        y_ds = self.output_file.create_dataset("voltage axis", shape = (0,), maxshape = (len(y_values),), dtype = float)
        y_ds.make_scale(y_axis_label)
        self.output_file.attrs.update({"y axis": y_axis_label})

        
                
        # Create the measurement array and the hdf5 dataset
        measurement_array = np.zeros((len(y_values), len(x_values), len(channel_names)))
        measurement_array[0] = single_sweep_array
        
        measurement_ds = self.output_file.create_dataset("sweep", shape = (0,) + single_sweep_array.shape, maxshape = measurement_array.shape, dtype = float)
        channels_ds = self.output_file.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8")) # z axis (channels)
        channels_ds.make_scale("channels")
        measurement_ds.dims[2].attach_scale(channels_ds)
        measurement_ds.dims[1].attach_scale(x_ds)
        measurement_ds.dims[0].attach_scale(y_ds)
        
        n_total = len(y_values)
        match y_axis_label:
            case "voltage (V)": # Experiments that sweep along one parameter while slowly ramping the bias
                for index, voltage in enumerate(y_values):
                    self.exp_progress.emit(int(100 * index / n_total))                    
                    mla.bias_update({"port_1 (V)": voltage}, verbose = False)
                    
                    (single_sweep_array, sweep_channel_names) = x_measurement(insert_parameter = ("voltage (V)", voltage))
                    measurement_array[index] = single_sweep_array
                    measurement_ds.resize((index + 1,) + single_sweep_array.shape)
                    y_ds.resize((index + 1,))
                    measurement_ds[index, :, :] = single_sweep_array
                    y_ds[index] = voltage
            
            case "amplitude (mV)":
                for index, amp_mV in enumerate(y_values):
                    self.exp_progress.emit(int(100 * index / n_total))
                    mla.amplitudes_update({"amplitudes (mV)": {0: amp_mV}}, verbose = False)
                    
                    (single_sweep_array, sweep_channel_names) = x_measurement(insert_parameter = ("amplitude (mV)", amp_mV))                    
                    measurement_array[index] = single_sweep_array
                    measurement_ds.resize((index + 1,) + single_sweep_array.shape)
                    y_ds.resize((index + 1,))
                    measurement_ds[index, :, :] = single_sweep_array
                    y_ds[index] = amp_mV

            case "frequency (Hz)":
                for index, f_Hz in enumerate(y_values):
                    self.exp_progress.emit(int(100 * index / n_total))
                    mla.time_constant_update({"df (Hz)": f_Hz}, verbose = False)
                    numbers = np.arange(0, 32)
                    numbers[0] = 1
                    mla.frequencies_update({"numbers": numbers})
                    
                    (single_sweep_array, sweep_channel_names) = x_measurement(insert_parameter = ("frequency (Hz)", f_Hz))
                    measurement_array[index] = single_sweep_array                            
                    measurement_ds.resize((index + 1,) + single_sweep_array.shape)
                    y_ds.resize((index + 1,))
                    measurement_ds[index, :, :] = single_sweep_array
                    y_ds[index] = f_Hz
            
            case _:
                raise Exception("This experiment is not yet implemented")
    
        self.exp_progress.emit(100) # Experiment finished

