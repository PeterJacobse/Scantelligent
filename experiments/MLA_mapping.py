import sys, os, time
import numpy as np
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable to find the APIs for type checking
from lib import BaseExperiment, MLAAPI, NanonisAPI, KeithleyAPI



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)



    @BaseExperiment.experiment_handler
    def run(self):        
        # Hardware (aliases)
        nn = self.nanonis
        if not isinstance(nn, NanonisAPI): raise Exception("Error. Cannot access Nanonis.")
        mla = self.mla        
        if not isinstance(mla, MLAAPI): raise Exception("Error. Cannot access the MLA.")
        
        # Read parameters from gui
        gui_parameters = self.start_parameters["gui"]
        [spec_button_states, spec_line_edits] = [gui_parameters.get(key) for key in ["spectroscopy_buttons", "spectroscopy_line_edits"]]
        assert isinstance(spec_line_edits, dict) and isinstance(spec_button_states, dict)
        [t_settle, t_int] = [int(spec_line_edits[f"t_{key}"]) for key in ["settle", "int"]]
        [nanonis_or_mla, tia_correct] = [spec_button_states.get(key) for key in ["nanonis_mla", "tia_correct"]]
        nanonis_or_mla = spec_button_states.get("nanonis_mla")
        
        if nanonis_or_mla == "nanonis": self.logprint(f"Nanonis sweep not yet implemented. Try setting the spectroscopy to MLA")
        direction = gui_parameters.get("direction_combobox", "up")
        
        # Read from Nanonis
        [scan_metadata, grid, tip_status, nn_bias, nn_hardware] = [self.start_parameters["nanonis"].get(parameter) for parameter in ["scan_metadata", "grid", "tip_status", "bias", "hardware"]]
        assert isinstance(grid, dict) and isinstance(nn_hardware, dict) and isinstance(direction, str)
        [pixels, lines, x_grid, y_grid, domain_nm] = [grid.get(key, 10) for key in ["pixels", "lines", "x_grid (nm)", "y_grid (nm)", "domain (nm)"]]
        [tia_gain, tia_gain_V_per_pA] = [nn_hardware.get(key) for key in ["current_gain", "gain (V/pA)"]]
        if not isinstance(domain_nm, list | np.ndarray):
            print("Error. Invalid xy domain.")
            return
        [width_nm, height_nm] = [float(domain_nm[0]), float(domain_nm[1])]
        x_values = np.linspace(-width_nm / 2, width_nm / 2, int(pixels)).astype(np.float32)
        y_values = np.linspace(-height_nm / 2, height_nm / 2, int(lines)).astype(np.float32)
        ch_values = np.arange(32).astype(np.float32)

        # Read from the MLA
        [mla_bias, amplitudes_dict, time_constant_dict, frequency_dict, mla_setup_array] = [self.start_parameters["mla"].get(key) for key in ["mla_bias", "amplitudes", "time_constant", "frequencies", "array"]]
        assert isinstance(mla_bias, dict) and isinstance(amplitudes_dict, dict) and isinstance(frequency_dict, dict) and isinstance(time_constant_dict, dict)
        amplitudes = amplitudes_dict.get("amplitudes (mV)", [])
        freqs = frequency_dict.get("frequencies (Hz)", [])
        V_dc = mla_bias.get("port_1 (V)", 0)
        V_ac_mV = amplitudes[0]

        # Retrieve the tia corrections
        tia_corrections = None
        if tia_correct and tia_gain in self.luts.keys():
            self.logprint(f"TIA corrections requested. I found them")
            tia_corrections = self.luts.get(tia_gain)

        # Prepare the output
        channel_names = ["t (s)", "V (V)", "x (nm)", "y (nm)", "z (nm)", "I (pA)"]
        [channel_names.extend([f"G({demod_index + 1}) (nS)"]) for demod_index in range(32)]
        n_channels = len(channel_names)
        


        # Set up the HDF5 datasets and groups
        x_ds = self.io.h5.create_ancillary_dataset(self.output_file, name = "x", units = "nm", data = x_values)
        y_ds = self.io.h5.create_ancillary_dataset(self.output_file, name = "y", units = "nm", data = y_values)
        ch_ds = self.io.h5.create_ancillary_dataset(self.output_file, name = "lockin_channel", units = "#", data = ch_values)
                
        lockin_ds = self.io.h5.create_main_dataset(self.output_file, name = "lockin_data", units = "mV", modality = "MLA_map", shape = (32, lines, pixels), dtype = np.complex64)
        lockin_errors_ds = self.io.h5.create_main_dataset(self.output_file, name = "errors", units = "mV", modality = "MLA_map", shape = (32, lines, pixels), dtype = np.float32)
        z_ds = self.io.h5.create_main_dataset(self.output_file, name = "z", units = "nm", modality = "MLA_map", shape = (pixels, lines), make_default = True, dtype = np.float32)
        I_ds = self.io.h5.create_main_dataset(self.output_file, name = "I", units = "pA", modality = "MLA_map", shape = (pixels, lines), make_default = False, dtype = np.float32)
        
        for main_ds in [lockin_ds, lockin_errors_ds]: [self.io.h5.attach_axis(main_ds, dataset, axis) for axis, dataset in enumerate([ch_ds, y_ds, x_ds])]
        for main_ds in [z_ds, I_ds]: [self.io.h5.attach_axis(main_ds, dataset, axis) for axis, dataset in enumerate([x_ds, y_ds])]
        
        # Create the ArrayItem (for the GUI)
        lockin_array = np.zeros(shape = (n_channels, pixels, lines), dtype = np.float32)
        self.create_array_item(name = f"{os.path.basename(self.experiment_file)}", axes = ["channel", "x", "y"], shape = (n_channels, pixels, lines), frame = grid, dtype = np.float32, axis_values = [channel_names, x_values, y_values])



        # Main loop
        t_start = time.time()
        t_s = 0
        mla.start_lockin()
        for line_index in range(lines):
            pixel_list = range(pixels)
            for pix_index in pixel_list:
                # Move the tip to the new location and get the non-lockin data from Nanonis
                x_nm = x_grid[line_index, pix_index]
                y_nm = y_grid[line_index, pix_index]

                tip_status, error = nn.update.tip(x_nm = x_nm, y_nm = y_nm, wait = True, fast_mode = True, verbose = False) # Wait for move
                mla.get_pixels(1 + t_settle) # Settle
                if not error: [x_nm, y_nm, z_nm, I_pA] = [tip_status.get(key, 0) for key in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
                t_s = time.time() - t_start
                non_lockin_channels = np.array([t_s, V_dc, x_nm, y_nm, z_nm, I_pA])
                
                # Safetip
                if I_pA > 9000:
                    self.current_spikes += 1
                    self.logprint("Warning! Current spike detected", message_type = "warning")
                if self.current_spikes > 2:
                    self.logprint("Warning! 3 current spikes detected. Aborting the experiment", message_type = "error")
                    nn.update.tip(feedback = False, z_rel_nm = 10)
                    raise Exception("Aborting")

                # Acquire the pixel
                pix_V, pix_V_var = mla.get_pixels(t_int, average = True)
                assert isinstance(pix_V, np.ndarray) and isinstance(pix_V_var, np.ndarray)
                pix_V_std_dev = np.sqrt(pix_V_var)
                                
                """
                # Apply correction for the transimpedance amplifier response if desired
                if isinstance(tia_corrections, list | np.ndarray):
                    for tone in range(len(pix_V)):
                        freq_int = int(round(freqs[tone]))
                        if freq_int < len(tia_corrections):
                            tone_correction = tia_corrections[freq_int]
                            pix_V[tone] *= tone_correction
                            pix_V_std_dev *= np.abs(tone_correction)
                """
                # Convert from voltages to currents (using knowledge of the TIA gain setting) and then to conductances (using knowledge of the V_ac)
                pix_nS = 2 * pix_V / (tia_gain_V_per_pA * V_ac_mV)                
                pix_nS_std_dev = 2 * pix_V_std_dev / (tia_gain_V_per_pA * V_ac_mV)
    
                combined_pixel = np.concatenate((non_lockin_channels, np.real(pix_nS)))
                self.data_array.emit(combined_pixel)
                
                lockin_ds[:, line_index, pix_index] = pix_nS
                lockin_errors_ds[:, line_index, pix_index] = pix_nS_std_dev
                z_ds[line_index, pix_index] = z_nm
                I_ds[line_index, pix_index] = I_pA
                
                # Update the array for plotting to the GUI. Then read which channel is being viewed in the GUI and output the corresponding slice
                lockin_array[:, pix_index, line_index] = combined_pixel
                try:
                    channel_index = self.scan_processing_flags.get("channel_index")
                    self.image.emit(lockin_array[channel_index])
                except:
                    pass
            
                self.check_abort_request()

        nn.update.tip(feedback = False, z_rel_nm = 5)

