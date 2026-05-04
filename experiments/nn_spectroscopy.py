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
        self.connect_hardware("nanonis") # Set up the required hardware connections
        
        nn = self.nanonis # Using nn as an alias for self.nanonis
        nhw = nn.nanonis_hardware
        # nn.link() # Although NanonisAPI functions will automatically manage TCP connections, NanonisHardware will not work unless a TCP connection is established explicitly

        # Read and calculate information
        [t_int_ms, t_settle_ms] = [self.sct.gui.line_edits[name].getValue() for name in ["STS_t_int", "STS_t_settle"]]
        t_settle_s = t_settle_ms / 1000
        t_int_s = t_int_ms / 1000
        
        button_states = [self.sct.gui.buttons[name].state_index for name in ["STS_V", "STS_z", "STS_f", "STS_amp", "STS_V_keithley"]]
        if not 1 in button_states:
            raise Exception("Error. No variable on the x-axis selected. Check one of the variable buttons in the spectroscopy module")
        if button_states[0] == 1: x_axis = "V"
        elif button_states[1] == 1: x_axis = "z"
        
        self.logprint(f"Starting a spectroscopy experiment, measuring as a function of {x_axis}", message_type = "success")
        #V_start, V_end, n_points "STS_V_start", "STS_V_end", "STS_V_points"
        #V_0 = self.start_parameters["nanonis"].get("bias").get("V_nanonis (V)")
        #V_list = np.linspace(V_start, V_end, n_points)
        #V_list_retrace = np.linspace(V_end, V_start, n_points)
        
        
        # Find the LI demodulator channels and put them in slots 20 through 23 so that they can be accessed by nanonis.signals_update
        scan_metadata = self.start_parameters["nanonis"].get("scan_metadata")
        LI_indices = [scan_metadata.get("all_signals", {}).get(parameter_name) for parameter_name in ["LI Demod 1 X (A)", "LI Demod 1 Y (A)", "LI Demod 2 X (A)", "LI Demod 2 Y (A)"]]
        
        #for slot_index, LI_index in zip([20, 21, 22, 23], LI_indices):
        #    nhw.set_signal_in_slot(slot_index, LI_index)

        # We first directly pass the parameter names to signals_update. The function will then return the indices it found that correspond to these parameters. Subsequent calls can be done using the indices, which is faster.
        (signals, error) = nn.signals_update(["LI Demod 1 X (A)", "LI Demod 1 Y (A)", "LI Demod 2 X (A)", "LI Demod 2 Y (A)"])
        signals.pop("dict_name")
        signal_indices = []
        signal_names = []

        for key, value in signals.items():
            if isinstance(key, int):
                signal_indices.append(key)
                signal_names.append(value[0])
        
        # Convert signal names to pA units
        for index in range(len(signal_names)):
            signal_name = signal_names[index]
            (quantity, unit, backward, error) = self.sct.file_functions.split_physical_quantity(signal_name)
            if unit == "A": signal_names[index] = quantity + " (pA)"
        
        channel_names = ["V (V)", "t (s)", "I (pA)"] + signal_names
        channels_dict = {i: name for i, name in enumerate(channel_names)} | {"dict_name": "channels"} # Prepare the GUI for plotting these channels
        self.parameters.emit(channels_dict)
        
        (sigs, error) = nn.signals_update(signal_indices, name_lookup = True)
        self.logprint(f"{sigs}")



        # Start ramp
        nn.tip_update({"feedback": False})
        nn.bias_update({"V": V_start})
        nn.lockin_update({"mod1": {"on": True}})
        time.sleep(.2)

        # Trace
        t_start = time.time()
        t_elapsed = 0
        for iteration, V_t in enumerate(V_list):
            nhw.set_V(V_t)
            time.sleep(t_settle_s)            
            t_elapsed = time.time() - t_start
            
            current = nhw.get_I_pA()
            bias = nhw.get_V()
            (signals, error) = nn.signals_update(signal_indices, verbose = False)
            [li_1x, li_1y, li_2x, li_2y] = [signals.get(index)[1] * 1E12 for index in signal_indices] # Conversion to pA included
            
            self.data_array.emit(np.array([[bias, t_elapsed, current, li_1x, li_1y, li_2x, li_2y]]))
            self.sct.amplitudes.emit([li_1x / 10, li_2x / 10])
            self.exp_progress.emit(int(50 * iteration / n_points))
            
            self.check_abort_request()
        
        # Retrace
        for V_t in V_list_retrace:
            nhw.set_V(V_t)
            time.sleep(t_settle_s)            
            t_elapsed = time.time() - t_start
            
            current = nhw.get_I_pA()
            bias = nhw.get_V()
            (signals, error) = nn.signals_update(signal_indices, verbose = False)
            [li_1x, li_1y, li_2x, li_2y] = [signals.get(index)[1] * 1E12 for index in signal_indices]
            
            self.data_array.emit(np.array([[bias, t_elapsed, current, li_1x, li_1y, li_2x, li_2y]]))
            self.sct.amplitudes.emit([li_1x / 10, li_2x / 10])
            self.exp_progress.emit(int(50 * iteration / n_points))
            
            self.check_abort_request()
        
        # Reset
        nn.lockin_update({"mod1": {"on": False}})
        nn.bias_update({"V": V_0})
        nn.tip_update({"feedback": False})
        time.sleep(.5)

