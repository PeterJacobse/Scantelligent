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
        
        # Read parameters from gui
        gui_parameters = self.start_parameters["gui"]
        [spec_button_states, spec_line_edits, modulators] = [gui_parameters.get(key) for key in ["spectroscopy_buttons", "spectroscopy_line_edits", "modulators"]]
                
        [t_settle, t_int] = [int(spec_line_edits[f"t_{key}"]) for key in ["settle", "int"]]
        [nanonis_or_mla, tia_correct] = [spec_button_states.get(key) for key in ["nanonis_mla", "tia_correct"]]
        [blank_modulators, intermediate_feedback, spectroscopy_feedback] = [spec_button_states.get(key) for key in ["blank_modulators", "intermediate_feedback", "spectroscopy_feedback"]]
        
        [V_fb, p_gain_fb, I_fb, t_fb, t_const_fb, z_fb] = [spec_line_edits[f"{key}_feedback"] for key in ["V", "p", "I", "t", "t_const", "z"]]
        """
        connected_device = self.connection_test(frequency_Hz = 600, amplitude_mV = 200, verbose = False, autophase = True)
        if not connected_device == nanonis_or_mla:
            self.logprint(f"Warning. The STM seems to be connected to {connected_device}. However, an experiment using {nanonis_or_mla} was requested", message_type = "warning")
        if not connected_device == "mla":
            self.logprint(f"Warning. Only spectroscopy using the MLA is supported at this moment.", message_type = "warning")
        """
       
        # Read parameters from Nanonis
        nanonis_parameters = self.start_parameters["nanonis"]
        nn_hardware_dict = nanonis_parameters.get("hardware", {})
        [tia_gain, tia_gain_V_per_pA] = [nn_hardware_dict.get(key) for key in ["current_gain", "gain (V/pA)"]]
        start_feedback = nanonis_parameters.get("tip_status").get("feedback")
        
        # Read parameters from the MLA
        mla_parameters = self.start_parameters["mla"]
        mla_setup_array = mla_parameters.get("array")
        mla_array_channels = mla_parameters.get("array_channels")
        time_constant_dict = mla_parameters.get("time_constant")
        mla_bias = mla_parameters.get("mla_bias")
        mla_output_masks = mla_parameters.get("outputs").get("output_masks")
        if not V_fb: V_fb = mla_bias.get("port_1 (V)", 1.0)
        
        tia_corrections = None
        if tia_correct:
            try: tia_corrections = self.tia_corrections.get(tia_gain)[1]
            except: pass
        
        # Set up spectroscopy x axis
        x_values = None
        x_axis_label = ""
        x_ds = None
        
        [x_start, x_end, x_steps] = [spec_line_edits.get(key) for key in ["x_start", "x_end", "x_points"]]
        x_values = np.linspace(x_start, x_end, x_steps)
        dx = (x_end - x_start) / (x_steps - 1)
        
        if blank_modulators: post_sweep_outputs = "blank"
        else: post_sweep_outputs = "reset"
        
        match spec_button_states["x_axis"]:
            case "V":
                x_axis_label = "voltage (V)"
                if spec_button_states.get("V_retrace", False): x_values = np.concatenate((x_values, x_values[::-1]))
                x_axis_info = {"V start (V)": x_start, "V end (V)": x_end, "dV (V)": dx, "V steps": x_steps}
                
                x_measurement = lambda insert_parameter, channel_names_callback: mla.voltage_sweep(
                    x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, modulators = modulators, post_sweep_outputs = post_sweep_outputs,
                    tia_gain_V_per_pA = tia_gain_V_per_pA, insert_parameter = insert_parameter, return_type = "conductance", tia_corrections = tia_corrections,
                    abort_callback = self.check_abort_request, data_callback = self.data_array.emit, channel_names_callback = channel_names_callback)
            case "z":
                x_axis_label = "tip height (nm)"
                if spec_button_states.get("z_retrace", False): x_values = np.concatenate((x_values, x_values[::-1]))
                x_axis_info = {"z start (nm)": x_start, "z end (nm)": x_end, "dz (nm)": dx, "z steps": x_steps}
                
                raise Exception("Experiment not yet implemented")
            case "f":
                x_axis_label = "frequency (Hz)"
                if spec_button_states.get("f_retrace", False): x_values = np.concatenate((x_values, x_values[::-1]))
                x_axis_info = {"f start (Hz)": x_start, "f end (Hz)": x_end, "df (Hz)": dx, "f steps": x_steps}
                
                x_measurement = lambda insert_parameter, channel_names_callback: mla.frequency_sweep(
                    x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, modulators = modulators, post_sweep_outputs = post_sweep_outputs,
                    tia_gain_V_per_pA = tia_gain_V_per_pA, insert_parameter = insert_parameter, tia_corrections = tia_corrections,
                    abort_callback = self.check_abort_request, data_callback = self.data_array.emit, channel_names_callback = channel_names_callback)
            case "amp":
                x_axis_label = "amplitude (mV)"
                if spec_button_states.get("amp_retrace", False): x_values = np.concatenate((x_values, x_values[::-1]))
                x_axis_info = {"amp start (mV)": x_start, "amp end (mV)": x_end, "damp (mV)": dx, "amp steps": x_steps}
                
                x_measurement = lambda insert_parameter, channel_names_callback: mla.amplitude_sweep(
                    x_values, settle_pixels = t_settle, pixels_per_datapoint = t_int, modulators = modulators, post_sweep_outputs = post_sweep_outputs,
                    tia_gain_V_per_pA = tia_gain_V_per_pA, insert_parameter = insert_parameter, tia_corrections = tia_corrections,
                    abort_callback = self.check_abort_request, data_callback = self.data_array.emit, channel_names_callback = channel_names_callback)
            case "V_keithley":
                x_axis_label = "V_Keithley (V)"
                if spec_button_states.get("V_keithley_retrace", False): x_values = np.concatenate((x_values, x_values[::-1]))
                x_axis_info = {"V_Keithley start (V)": x_start, "V_Keithley end (V)": x_end, "dV_Keithley (mV)": dx, "V_Keithley steps": x_steps}
                
                raise Exception("Experiment not yet implemented")
            
            case _: # No parameter to sweep on the x-axis. Resort to a single point measurement
                raise Exception("0D spectroscopy not yet implemented")

        if not isinstance(x_values, np.ndarray): raise Exception("No parameter selected to sweep on the x axis. Aborting experiment")
        
        
        
        # Create the experiment HDF5 file
        experiment_folder = os.path.dirname(self.experiment_file)
        if spec_button_states["y_axis"] in ["V", "z", "f", "amp"]: experiment_filename = "_".join([spec_button_states["x_axis"], spec_button_states["y_axis"], "spectroscopy"]) # 2D spectroscopy
        else: experiment_filename = "_".join([spec_button_states["x_axis"], "spectroscopy"]) # 1D spectroscopy
        
        self.experiment_file = os.path.join(experiment_folder, self.file_functions.get_next_indexed_filename(experiment_folder, experiment_filename, ".hdf5")[1])
        self.output_file = h5py.File(self.experiment_file, "w") # Open the new HDF5 file
                
        # Write metadata
        self.output_file.attrs.update({"date": datetime.now().strftime("%Y/%m/%d"), "time": datetime.now().strftime("%H:%M:%S"),
                                       "device": "MLA", "MLA time constant (ms)": time_constant_dict.get("tm (ms)", ""), "MLA df (Hz)": time_constant_dict.get("df (Hz)", ""), "V_port1 (V)": mla_bias.get("port_1 (V)", 0), "V_port2 (V)": mla_bias.get("port_2 (V)", 0),
                                       "tia gain setting": tia_gain, "tia gain (V/pA)": tia_gain_V_per_pA, "f / df": 1, "setling time (1 / df)": 1, "pixels per datapoint (1 / df)": t_int,
                                       "intermediate_feedback": intermediate_feedback, "spectroscopy_feedback": spectroscopy_feedback})
        self.output_file.attrs.update(x_axis_info)
        mla_settings_ds = self.output_file.create_dataset("MLA settings", data = mla_setup_array)
        mla_channels_ds = self.output_file.create_dataset("MLA setup parameters", data = mla_array_channels)
        mla_channels_ds.make_scale("MLA setup parameters")
        mla_settings_ds.dims[0].attach_scale(mla_channels_ds)
        
        x_ds = self.output_file.create_dataset(x_axis_label, data = x_values)
        x_ds.make_scale(x_axis_label)
        self.output_file.attrs.update({"x axis": x_axis_label})
        self.parameters.emit({"dict_name": "view_request", "view": "graph"})
        
        
        
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
                if spec_button_states.get("V_retrace", False): y_values = np.concatenate((y_values, y_values[::-1]))
                y_axis_info = {"V start (V)": y_start, "V end (V)": y_end, "dV (V)": dy, "steps": y_steps}
                
                # Set to the first value of the y parameter sweep, then do the first measurement
                voltage = y_values[0]
                
                if intermediate_feedback: self.intermediate_feedback(V_fb, I_fb, p_gain_fb, t_const_fb, t_fb, z_fb) # The z step relative to the feedback setpoint will automatically switch the feedback off
                if spectroscopy_feedback == "unchanged": nn.tip_update({"feedback": start_feedback}) # Feedback unchanged: switch it back on if it was on when the experiment was started
                elif spectroscopy_feedback == "on": nn.tip_update({"feedback": True})
                else: nn.tip_update({"feedback": False})

                mla.bias_update({"port_1 (V)": voltage}, verbose = False)
                (single_sweep_array, single_sweep_error_array, channel_names) = x_measurement(insert_parameter = ("voltage (V)", voltage), channel_names_callback = self.data_array.emit)
            
            case "z":
                y_axis_label = "tip height (nm)"
                if spec_button_states.get("z_retrace", False): y_values = np.concatenate((y_values, y_values[::-1]))                
                y_axis_info = {"z start (nm)": y_start, "z end (nm)": y_end, "dz (nm)": dy, "steps": y_steps}
                
                # Set to the first value of the y parameter sweep, then do the first measurement
                tip_height = y_values[0]
                
                if intermediate_feedback: self.intermediate_feedback(V_fb, I_fb, p_gain_fb, t_const_fb, t_fb, z_fb) # The z step relative to the feedback setpoint will automatically switch the feedback off
                if spectroscopy_feedback == "unchanged": nn.tip_update({"feedback": start_feedback}) # Feedback unchanged: switch it back on if it was on when the experiment was started
                elif spectroscopy_feedback == "on": nn.tip_update({"feedback": True})
                else: nn.tip_update({"feedback": False})

                nn.tip_update({"feedback": False, "z_rel (nm)": tip_height}, verbose = False)
                (single_sweep_array, single_sweep_error_array, channel_names) = x_measurement(insert_parameter = ("z (nm)", tip_height), channel_names_callback = self.data_array.emit)
            
            case "f":
                y_axis_label = "frequency (Hz)"
                if spec_button_states.get("f_retrace", False): y_values = np.concatenate((y_values, y_values[::-1]))
                y_axis_info = {"f start (Hz)": y_start, "f end (Hz)": y_end, "df (Hz)": dy, "steps": y_steps}
                
                # Set to the first value of the y parameter sweep, then do the first measurement
                f_Hz = y_values[0]
                
                if intermediate_feedback: self.intermediate_feedback(V_fb, I_fb, p_gain_fb, t_const_fb, t_fb, z_fb) # The z step relative to the feedback setpoint will automatically switch the feedback off
                if spectroscopy_feedback == "unchanged": nn.tip_update({"feedback": start_feedback}) # Feedback unchanged: switch it back on if it was on when the experiment was started
                elif spectroscopy_feedback == "on": nn.tip_update({"feedback": True})
                else: nn.tip_update({"feedback": False})
                
                mla.lockin_update({"df (Hz)": f_Hz, "numbers": [1, 1, 2, 3]}, verbose = False)
                (single_sweep_array, single_sweep_error_array, channel_names) = x_measurement(insert_parameter = ("frequency (Hz)", f_Hz), channel_names_callback = self.data_array.emit)
            
            case "amp":
                y_axis_label = "amplitude (mV)"
                if spec_button_states.get("amp_retrace", False): y_values = np.concatenate((y_values, y_values[::-1]))
                y_axis_info = {"amp start (mV)": y_start, "amp end (mV)": y_end, "damp (mV)": dy, "steps": y_steps}
                
                # Set to the first value of the y parameter sweep, then do the first measurement
                amp_mV = y_values[0]
                
                if intermediate_feedback: self.intermediate_feedback(V_fb, I_fb, p_gain_fb, t_const_fb, t_fb, z_fb) # The z step relative to the feedback setpoint will automatically switch the feedback off
                if spectroscopy_feedback == "unchanged": nn.tip_update({"feedback": start_feedback}) # Feedback unchanged: switch it back on if it was on when the experiment was started
                elif spectroscopy_feedback == "on": nn.tip_update({"feedback": True})
                else: nn.tip_update({"feedback": False})
                
                mla.amplitudes_update({"amplitudes (mV)": {0: amp_mV}}, verbose = False)
                (single_sweep_array, single_sweep_error_array, channel_names) = x_measurement(insert_parameter = ("amplitude (mV)", amp_mV), channel_names_callback = self.data_array.emit)
            
            case _: # No parameter on the y axis. Perform a 1D sweep instead
                if intermediate_feedback: self.intermediate_feedback(V_fb, I_fb, p_gain_fb, t_const_fb, t_fb, z_fb) # The z step relative to the feedback setpoint will automatically switch the feedback off
                if spectroscopy_feedback == "unchanged": nn.tip_update({"feedback": start_feedback}) # Feedback unchanged: switch it back on if it was on when the experiment was started
                elif spectroscopy_feedback == "on": nn.tip_update({"feedback": True})
                else: nn.tip_update({"feedback": False})
                
                (single_sweep_array, single_sweep_error_array, channel_names) = x_measurement(insert_parameter = None, channel_names_callback = self.data_array.emit)
                
                measurement_ds = self.output_file.create_dataset("Sweep", data = single_sweep_array, dtype = float)
                error_ds = self.output_file.create_dataset("Errors (std. dev.)", data = single_sweep_error_array, dtype = float)
                channels_ds = self.output_file.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8"))
                channels_ds.make_scale("channels")
                
                [measurement_ds.dims[dim].attach_scale(dataset) for dim, dataset in enumerate ([channels_ds, x_ds])]
                [error_ds.dims[dim].attach_scale(dataset) for dim, dataset in enumerate ([channels_ds, x_ds])]
                
                self.exp_progress.emit(100) # Experiment finished
                mla.outputs_update({"output_masks": mla_output_masks}, verbose = False)
                mla.start_lockin()
                mla.get_pixels(3)
                mla.stop_lockin()
                nn.tip_update({"feedback": start_feedback}, verbose = False)
                return
        
        # Everything below is for 2D measurements only. 1D sweeps have already returned at this point
        y_ds = self.output_file.create_dataset(y_axis_label, shape = (0,), maxshape = (len(y_values),), dtype = float) # The y axis dataset will grow along with the measurement dataset after every sweep
        y_ds.make_scale(y_axis_label)
        self.output_file.attrs.update({"y axis": y_axis_label} | y_axis_info)



        # Create the measurement array and the hdf5 dataset
        measurement_array = np.zeros((len(y_values), len(x_values), len(channel_names)))
        measurement_array[0] = single_sweep_array
        error_array = np.zeros_like(measurement_array)
        
        measurement_ds = self.output_file.create_dataset("Sweep", shape = (0,) + single_sweep_array.shape, maxshape = measurement_array.shape, dtype = float)
        error_ds = self.output_file.create_dataset("Errors (std. dev.)", shape = (0,) + single_sweep_array.shape, maxshape = measurement_array.shape, dtype = float)
        channels_ds = self.output_file.create_dataset("Channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8")) # z axis (channels)
        channels_ds.make_scale("channels")
        [measurement_ds.dims[dim].attach_scale(dataset) for dim, dataset in enumerate([y_ds, x_ds, channels_ds])]
        [error_ds.dims[dim].attach_scale(dataset) for dim, dataset in enumerate([y_ds, x_ds, channels_ds])]
       
        n_total = len(y_values)
        match y_axis_label:
            case "voltage (V)": # Experiments that sweep along one parameter while slowly ramping the bias
                self.add_data_to_datasets(single_sweep_array, single_sweep_error_array, measurement_ds, error_ds, y_ds, 0, parameter = voltage) # Save the first sweep
                
                for index, voltage in enumerate(y_values):
                    self.exp_progress.emit(int(100 * index / n_total))
                    
                    if intermediate_feedback: self.intermediate_feedback(V_fb, I_fb, p_gain_fb, t_const_fb, t_fb, z_fb)
                    if spectroscopy_feedback == "unchanged": nn.tip_update({"feedback": start_feedback}) # Feedback unchanged: switch it back on if it was on when the experiment was started
                    elif spectroscopy_feedback == "on": nn.tip_update({"feedback": True})
                    else: nn.tip_update({"feedback": False})
                    mla.bias_update({"port_1 (V)": voltage}, verbose = False)                    
                    if blank_modulators: mla.outputs_update({"output_masks": mla_output_masks})
                    
                    (single_sweep_array, single_sweep_error_array, sweep_channel_names) = x_measurement(insert_parameter = ("voltage (V)", voltage), channel_names_callback = None)
                    self.add_data_to_datasets(single_sweep_array, single_sweep_error_array, measurement_ds, error_ds, y_ds, index, parameter = voltage)
                    measurement_array[index] = single_sweep_array
            
            case "amplitude (mV)":
                self.add_data_to_datasets(single_sweep_array, single_sweep_error_array, measurement_ds, error_ds, y_ds, 0, parameter = amp_mV) # Save the first sweep
                
                for index, amp_mV in enumerate(y_values):
                    self.exp_progress.emit(int(100 * index / n_total))
                    
                    if intermediate_feedback: self.intermediate_feedback(V_fb, I_fb, p_gain_fb, t_const_fb, t_fb, z_fb)
                    if spectroscopy_feedback == "unchanged": nn.tip_update({"feedback": start_feedback}) # Feedback unchanged: switch it back on if it was on when the experiment was started
                    elif spectroscopy_feedback == "on": nn.tip_update({"feedback": True})
                    else: nn.tip_update({"feedback": False})
                    mla.amplitudes_update({"amplitudes (mV)": {0: amp_mV}}, verbose = False)
                    if blank_modulators: mla.outputs_update({"output_masks": mla_output_masks})
                    
                    (single_sweep_array, single_sweep_error_array, sweep_channel_names) = x_measurement(insert_parameter = ("amplitude (mV)", amp_mV), channel_names_callback = None)
                    self.add_data_to_datasets(single_sweep_array, single_sweep_error_array, measurement_ds, error_ds, y_ds, index, parameter = amp_mV)
                    measurement_array[index] = single_sweep_array

            case "frequency (Hz)":
                self.add_data_to_datasets(single_sweep_array, single_sweep_error_array, measurement_ds, error_ds, y_ds, 0, parameter = f_Hz) # Save the first sweep
                
                for index, f_Hz in enumerate(y_values):
                    self.exp_progress.emit(int(100 * index / n_total))
                    mla.time_constant_update({"df (Hz)": f_Hz}, verbose = False)
                    numbers = np.arange(0, 32)
                    numbers[0] = 1
                    
                    if intermediate_feedback: self.intermediate_feedback(V_fb, I_fb, p_gain_fb, t_const_fb, t_fb, z_fb)
                    if spectroscopy_feedback == "unchanged": nn.tip_update({"feedback": start_feedback}) # Feedback unchanged: switch it back on if it was on when the experiment was started
                    elif spectroscopy_feedback == "on": nn.tip_update({"feedback": True})
                    else: nn.tip_update({"feedback": False})
                    mla.frequencies_update({"numbers": numbers})
                    if blank_modulators: mla.outputs_update({"output_masks": mla_output_masks})
                    
                    (single_sweep_array, single_sweep_error_array, sweep_channel_names) = x_measurement(insert_parameter = ("frequency (Hz)", f_Hz), channel_names_callback = None)
                    self.add_data_to_datasets(single_sweep_array, single_sweep_error_array, measurement_ds, error_ds, y_ds, index, parameter = f_Hz)
                    measurement_array[index] = single_sweep_array
            
            case _:
                raise Exception("This experiment is not yet implemented")
    
        self.exp_progress.emit(100) # Experiment finished
        mla.outputs_update({"output_masks": mla_output_masks}, verbose = False)
        mla.start_lockin()
        mla.get_pixels(3)
        mla.stop_lockin()
        nn.tip_update({"feedback": start_feedback}, verbose = False)



    # Convenience functions
    def intermediate_feedback(self, V_fb, I_fb, p_gain_fb, t_const_fb, t_fb, z_fb) -> None:
        try:
            self.mla.bias_update({"port_1 (V)": V_fb}, verbose = False)
            self.nanonis.feedback_update({"I_fb (pA)": I_fb, "p_gain (pm)": p_gain_fb, "t_const (us)": t_const_fb}, verbose = False)
            self.nanonis.tip_update({"feedback": True}, verbose = False)
            self.mla.get_pixels(t_fb)
            self.nanonis.tip_update({"z_rel (nm)": z_fb}, verbose = False)
        except:
            pass
        return

    def add_data_to_datasets(self, single_sweep_array, single_sweep_error_array, measurement_ds, error_ds, y_ds, index, parameter) -> None:
        measurement_ds.resize((index + 1,) + single_sweep_array.shape)
        error_ds.resize((index + 1,) + single_sweep_array.shape)
        y_ds.resize((index + 1,))
        
        measurement_ds[index, :, :] = single_sweep_array
        error_ds[index, :, :] = single_sweep_error_array
        y_ds[index] = parameter
        return

