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
        nanonis_or_mla = spec_button_states.get("nanonis_mla")
        if nanonis_or_mla == "nanonis": self.logprint(f"Nanonis sweep not yet implemented. Try setting the spectroscopy to MLA")
        direction = gui_parameters.get("direction_combobox")
        
        # Read from Nanonis
        [scan_metadata, grid, tip_status, nn_bias, nn_hardware] = [self.start_parameters["nanonis"].get(parameter) for parameter in ["scan_metadata", "grid", "tip_status", "bias", "hardware"]]
        [pixels, lines, x_grid, y_grid] = [grid.get(key) for key in ["pixels", "lines", "x_grid (nm)", "y_grid (nm)"]]
        [tia_gain, tia_gain_V_per_pA] = [nn_hardware.get(key) for key in ["current_gain", "gain (V/pA)"]]
        (list_data, error) = nn.grids_to_lists(grid, direction = direction)
        [x_list_nm, y_list_nm] = [list_data[f"{dim}_list (nm)"] for dim in ["x", "y"]]
        n_pixels = len(x_list_nm)
        
        # Read from the MLA
        [V_dc, amplitudes, df, tm] = [self.start_parameters["mla"].get(key) for key in ["port_1 (V)", "amplitudes (mV)", "df (Hz)", "tm (ms)"]]
        V_ac = amplitudes[0]

        # Prepare the output        
        channels_list = ["t (s)", "V (V)", "x (nm)", "y (nm)", "z (nm)", "I (pA)"]
        [channels_list.extend([f"Re(G{demod_index + 1}) (nS)", f"Im(G{demod_index + 1}) (nS)"]) for demod_index in range(32)]
        n_channels = len(channels_list)
        channels_dict = {i: name for i, name in enumerate(channels_list)} | {"dict_name": "channels"}
        self.parameters.emit(channels_dict) # This triggers the GUI to start graphing data



        # Action
        input_mask = 2 * np.ones(32)
        input_mask[0] = 1 # Measure the output voltage against demod 0 as a reference
        mla.set_input_multiplexer(input_mask)
        freq_numbers = np.arange(0, 32, 1) # Use demod 1 to measure the base frequency (f1), then demod 2 to measure f2, etc.
        freq_numbers[0] = 1 # Base frequency to demodulate the output voltage
        (f_dict, error) = mla.frequencies_update({"numbers": freq_numbers})
        mla.outputs_update({"blank": True, "mod0": {"on": True, "port": 1}}) # Output modulator 1 onto port 1
        
        measurement_array = np.empty((lines, pixels, n_channels), dtype = float)
        self.output_file.attrs.update({"V_dc (V)": V_dc, "V_ac (V)": V_ac, "df (Hz)": df, "tm (ms)": tm, "t_settle (tm)": t_settle, "t_int (tm)": t_int, "t_settle (ms)": t_settle * tm, "t_int (ms)": t_int * tm})
        self.output_file.attrs.update({"frequencies (Hz)": f_dict["frequencies (Hz)"], "numbers (f / df)": f_dict["numbers"], "tia gain setting": tia_gain, "tia gain (V/pA)": tia_gain_V_per_pA})
        measurement_ds = self.output_file.create_dataset("MLA map", shape = measurement_array.shape, dtype = float, chunks = True)
        channels_ds = self.output_file.create_dataset("channel axis", data = np.array([item.encode("utf-8") for item in channels_list]), dtype = h5py.string_dtype(encoding = "utf-8"))
        channels_ds.make_scale("channels")
        measurement_ds.dims[2].attach_scale(channels_ds)



        # Main loop
        t_start = time.time()
        t_elapsed = 0
        mla.start_lockin()
        for line_index in range(lines):
            for pixel_index in range(pixels):
                x_nm = x_grid[line_index, pixel_index]
                y_nm = y_grid[line_index, pixel_index]

                (tip_status, error) = nn.tip_update({"x (nm)": x_nm, "y (nm)": y_nm}, wait = True, fast_mode = True, verbose = False) # Wait for move
                mla.get_pixels(1 + t_settle) # Settle
                [x_nm, y_nm, z_nm, I_pA] = [tip_status.get(key) for key in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
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
                pixel_V = mla.get_pixels(t_int, average = True)
                
                pixel_nS = pixel_V / (tia_gain_V_per_pA * V_ac)
                
                in_phase = np.real(pixel_nS)
                quadrature = np.imag(pixel_nS)
                ext_pix = np.zeros(2 * len(pixel_V), dtype = float)
                ext_pix[0::2] = in_phase
                ext_pix[1::2] = quadrature
                
                combined_pixel = np.concatenate((data_chunk, ext_pix))
                self.data_array.emit(combined_pixel)
                measurement_array[line_index, pixel_index] = combined_pixel
                self.image.emit(measurement_array[:, :, 8])
                measurement_ds[line_index, pixel_index, :] = combined_pixel
            
                self.check_abort_request()

        mla.stop_lockin()


