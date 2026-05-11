import sys, os, time
import numpy as np
from scipy.ndimage import gaussian_filter

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) # Add the lib folder to the path variable
from lib import BaseExperiment



class Experiment(BaseExperiment):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.gui_setup = {"combobox": {},
                          "line_edits": {},
                          "buttons": {}}

    @BaseExperiment.experiment_handler
    def run(self):
        # Aliases
        nn = self.nanonis
        
        (bias, error) = nn.bias_update({"V_nanonis (V)": -2})
        (tip_status, error) = nn.tip_update(fast_mode = False)
        (signal_dict, error) = nn.signals_update(["LI Demod 1 X (A)", "LI Demod 1 Y (A)"])
        (lockin, error) = nn.lockin_update({"mod1": {"on": True, "amplitude (mV)": 2, "frequency (Hz)": 600}})
        
        LI_X_index = 0
        LI_Y_index = 0
        for key, value in signal_dict.items():
            if value[0] == "LI Demod 1 X (A)": LI_X_index = key
            if value[0] == "LI Demod 1 Y (A)": LI_Y_index = key

        
        
        (tip_status, error) = nn.tip_update({"withdraw": True}, fast_mode = False)
        [z_min_nm, z_max_nm] = tip_status.get("z_limits (nm)")
        (feedback, error) = nn.feedback_update({"I_fb (pA)": 300, "p_gain (pm)": 40, "t_const (us)": 200})
        I_fb_pA = feedback.get("I_fb (pA)")

        (tip_status, error) = nn.tip_update({"feedback": True}, fast_mode = True)
        z_tip_nm = tip_status.get("z (nm)")

        self.prepare_graph(["t (s)", "z (nm)", "I (pA)", "LI X (pA)", "LI Y (pA)"])
        
        surface_reached = 0
        max_observations = 10000
        t0 = time.time()
        t_elapsed = 0
        
        for step in range(10):
            self.logprint(f"Auto approach step {step}", message_type = "message")
            counter = 0
            
            (tip_status, error) = nn.tip_update({"feedback": True}, fast_mode = False, verbose = False)
            for observation in range(max_observations):
                (tip_status, error) = nn.tip_update({"feedback": True}, fast_mode = True, verbose = False)
                (signal_dict, error) = nn.signals_update([LI_X_index, LI_Y_index], name_lookup = False, verbose = False)
                t_elapsed = time.time() - t0
                
                I_in_phase = signal_dict.get(LI_X_index)[1]
                I_quadrature = signal_dict.get(LI_Y_index)[1]
                I_pA = tip_status.get("I (pA)")
                z_tip_nm = tip_status.get("z (nm)")
                
                self.data_array.emit(np.array([t_elapsed, z_tip_nm, I_pA, I_in_phase, I_quadrature]))
                
                if I_pA > I_fb_pA: counter += 1
                if counter > 4:
                    surface_reached = 1
                    break
                if z_tip_nm < z_min_nm + 1: break
                self.check_abort_request()
        
            nn.tip_update({"withdraw": True})
            if surface_reached == 1: break
            
            nn.coarse_move({"minus_z_steps": 1})
            
        
        (tip_status, error) = nn.tip_update({"withdraw": True}, fast_mode = False)
        