import sys, os, time
import numpy as np
from scipy.ndimage import gaussian_filter
import h5py

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.gui_setup = {"combobox": {"items": ["up", "down"]},
                          "line_edits": {},
                          "buttons": {"states": [{"name": "off", "tooltip": "feedback OFF during measurement"}, {"name": "on", "tooltip": "feedback ON during measurement"}]}}

    @BaseExperiment.experiment_handler
    def run(self):
        # [self.connect_hardware(component) for component in ["nanonis", "mla"]] # Set up the required hardware connections
        
        # Aliases
        nn = self.nanonis
        mla = self.mla
                
        # Read parameters from gui
        gui_parameters = self.start_parameters["gui"]
        [spec_button_states, spec_line_edits] = [gui_parameters.get(key) for key in ["spectroscopy_buttons", "spectroscopy_line_edits"]]
        [t_settle, t_int] = [int(spec_line_edits[f"t_{key}"]) for key in ["settle", "int"]]
        [nanonis_or_mla, tia_correct] = [spec_button_states.get(key) for key in ["nanonis_mla", "tia_correct"]]
        nanonis_or_mla = spec_button_states.get("nanonis_mla")
        if nanonis_or_mla == "nanonis": self.logprint(f"Nanonis sweep not yet implemented. Try setting the spectroscopy to MLA")
        direction = gui_parameters.get("direction_combobox")
        
        # Read from Nanonis
        [scan_metadata, grid, tip_status, nn_bias, nn_hardware] = [self.start_parameters["nanonis"].get(parameter) for parameter in ["scan_metadata", "grid", "tip_status", "bias", "hardware"]]
        [pixels, lines, x_grid, y_grid, scan_range_nm] = [grid.get(key) for key in ["pixels", "lines", "x_grid (nm)", "y_grid (nm)", "domain (nm)"]]
        [tia_gain, tia_gain_V_per_pA] = [nn_hardware.get(key) for key in ["current_gain", "gain (V/pA)"]]
        (list_data, error) = nn.grids_to_lists(grid, direction = direction)
        [x_list_nm, y_list_nm] = [list_data[f"{dim}_list (nm)"] for dim in ["x", "y"]]
        n_pixels = len(x_list_nm)
        [width_nm, height_nm] = [scan_range_nm[0], scan_range_nm[1]]
        
        # Read from the MLA
        [mla_bias, amplitudes_dict, time_constant_dict, frequency_dict, mla_setup_array] = [self.start_parameters["mla"].get(key) for key in ["mla_bias", "amplitudes", "time_constant", "frequencies", "array"]]
        amplitudes = amplitudes_dict.get("amplitudes (mV)")
        freqs = frequency_dict.get("frequencies (Hz)")
        V_dc = mla_bias.get("port_1 (V)", 0)
        V_ac_mV = amplitudes[0]

        # Retrieve the tia corrections
        tia_corrections = None
        if tia_correct and tia_gain in self.luts.keys():
            self.logprint(f"TIA corrections requested. I found them")
            tia_corrections = self.luts.get(tia_gain)

        # Prepare the output
        channel_names = ["t (s)", "V (V)", "x (nm)", "y (nm)", "z (nm)", "I (pA)"]
        [channel_names.extend([f"Re(G{demod_index + 1}) (nS)", f"Im(G{demod_index + 1}) (nS)"]) for demod_index in range(32)]
        n_channels = len(channel_names)
        self.data_array.emit(np.array(channel_names)) # This triggers the GUI to start graphing data
        self.parameters.emit({"dict_name": "scan_metadata", "channel_dict": {channel_name: index for index, channel_name in enumerate(channel_names)}}) # This triggers the GUI and scan_processing_flags to assign the correct scan channels to the slices of the data array



        # Set up the HDF5 datasets and groups
        spectroscopy_group: h5py.Group = self.output_file.create_group("spectrocopy_settings")
        spectroscopy_group.attrs.update({"device": "MLA", "MLA time constant (ms)": time_constant_dict.get("tm (ms)", ""), "MLA df (Hz)": time_constant_dict.get("df (Hz)", ""), "V_port1 (V)": mla_bias.get("port_1 (V)", 0), "V_port2 (V)": mla_bias.get("port_2 (V)", 0),
                                         "f / df": 1, "settling time (1 / df)": t_settle, "pixels per datapoint (1 / df)": t_int, "tia gain setting": tia_gain, "tia gain (V/pA)": tia_gain_V_per_pA})
        mla_settings_ds = spectroscopy_group.create_dataset("MLA settings", data = mla_setup_array)

        map_group: h5py.Group = self.output_file.create_group("map_group")
        map_group.attrs.update({"NX_class": "NXdata"})
        
        channels_ds = map_group.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channel_names]), dtype = h5py.string_dtype(encoding = "utf-8"))
        channel_indices_ds = map_group.create_dataset("channel index axis", data = np.arange(len(channel_names), dtype = np.int32))
        channel_indices_ds.make_scale("channel indices")
        x_ds = map_group.create_dataset("x axis", data = np.linspace(-width_nm / 2, width_nm / 2, pixels), dtype = np.float32)
        x_ds.make_scale("x values")
        y_ds = map_group.create_dataset("y axis", data = np.linspace(-height_nm / 2, height_nm / 2, lines), dtype = np.float32)
        y_ds.make_scale("y values")
        
        map_array = np.empty((n_channels, lines, pixels), dtype = np.float32)
        map_ds = map_group.create_dataset("map", shape = ((n_channels, lines, pixels)), dtype = np.float32)
        map_ds.dims[0].attach_scale(channel_indices_ds)
        map_ds.dims[1].attach_scale(y_ds)
        map_ds.dims[2].attach_scale(x_ds)
        map_errors_ds = map_group.create_dataset("map_errors", shape = ((n_channels, lines, pixels)), dtype = np.float32)
        map_errors_ds.dims[0].attach_scale(channel_indices_ds)
        map_errors_ds.dims[1].attach_scale(y_ds)
        map_errors_ds.dims[2].attach_scale(x_ds)
        
        map_group.attrs.update({"signal": "map"})
        map_group.attrs.update({"axes": ["channel index axis", "y axis", "x axis"]})
        map_group.attrs.update({"units": ["", "nm", "nm"]})
        


        # Main loop
        t_start = time.time()
        t_elapsed = 0
        mla.start_lockin()
        for line_index in range(lines):
            pixel_list = range(pixels)
            for pix_index in pixel_list:
                x_nm = x_grid[line_index, pix_index]
                y_nm = y_grid[line_index, pix_index]

                (tip_status, error) = nn.tip_update({"x (nm)": x_nm, "y (nm)": y_nm}, wait = True, fast_mode = True, verbose = False) # Wait for move
                mla.get_pixels(1 + t_settle) # Settle
                if not error: [x_nm, y_nm, z_nm, I_pA] = [tip_status.get(key) for key in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
                t_elapsed = time.time() - t_start
                
                # Safetip
                if I_pA > 9000:
                    self.current_spikes += 1
                    self.logprint("Warning! Current spike detected", message_type = "warning")
                if self.current_spikes > 2:
                    self.logprint("Warning! 3 current spikes detected. Aborting the experiment", message_type = "error")
                    nn.tip_update({"z_rel (nm)": 10})
                    raise Exception("Aborting")

                data_chunk = np.array([t_elapsed, V_dc, x_nm, y_nm, z_nm, I_pA])
                (pix_V, pix_V_var) = mla.get_pixels(t_int, average = True)
                pix_V_std_dev = np.sqrt(pix_V_var)
                
                if isinstance(tia_corrections, list | np.ndarray): # Apply correction for tia response if desired
                    for tone in range(len(pix_V)):
                        freq_int = int(round(freqs[tone]))
                        if freq_int < len(tia_corrections):
                            tone_correction = tia_corrections[freq_int]
                            pix_V[tone] *= tone_correction
                            pix_V_std_dev *= np.abs(tone_correction)
                
                pix_nS = 2 * pix_V / (tia_gain_V_per_pA * V_ac_mV)
                pix_nS_std_dev = 2 * pix_V_std_dev / (tia_gain_V_per_pA * V_ac_mV)
                
                in_phase = np.real(pix_nS)
                quadrature = np.imag(pix_nS)
                ext_pix = np.zeros(2 * len(pix_V), dtype = np.float32)
                ext_pix[0::2] = in_phase
                ext_pix[1::2] = quadrature
                
                combined_pixel = np.concatenate((data_chunk, ext_pix))
                self.data_array.emit(combined_pixel)
                
                error_pixel = np.zeros_like(combined_pixel)
                error_pixel[6 : len(pix_nS_std_dev) + 6] = pix_nS_std_dev
                
                map_ds[:, line_index, pix_index] = combined_pixel
                map_array[:, line_index, pix_index] = combined_pixel
                
                channel_index = self.scan_processing_flags.get("channel_index")                
                try: self.image.emit(map_array[channel_index])
                except: pass                
            
                self.check_abort_request()

        nn.tip_update({"z_rel (nm)": 5})


