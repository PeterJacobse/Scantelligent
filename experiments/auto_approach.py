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
        mla = self.mla

        # Read parameters
        [bias, start_feedback, hardware] = [self.start_parameters["nanonis"].get(key) for key in ["bias", "feedback", "hardware"]]
        V_start = bias.get("V_nanonis (V)")
        tia_gain_V_per_pA = hardware.get("gain (V/pA)", None)
        f_approach_Hz = 600
        amp_approach_mV = 2
                
        # Testing the connected device using the lock-in amplifiers
        connected_device = self.connection_test(frequency_Hz = f_approach_Hz, amplitude_mV = 200, verbose = False, autophase = True)
        if not connected_device in ["nanonis", "mla"]:
            raise Exception("The STM does not seem to be connected to either Nanonis or the MLA. I am unable to see a response in the tunneling current. It is not safe to approach.")
        self.logprint(f"I detected that the STM sample bias is applied through the following device: {connected_device}.", message_type = "message")
        if connected_device == "mla":
            bias_dict = self.start_parameters["mla"].get("mla_bias")
            V_start = bias_dict.get("port_1 (V)")
        
        """
        self.logprint(f"I noticed you connected the sample bias to: {connected_device}. Please connect it to the MLA", message_type = "warning")
        iterations = 0
        while iterations < 20:
            iterations += 1
            self.check_abort_request()
            connected_device = self.connection_test(frequency_Hz = 600, amplitude_mV = 200, verbose = False, autophase = False)
            self.logprint(f"{connected_device = }")
            if connected_device == "mla": break
        """

        if np.abs(V_start) < .6:
            phrasing = "very" if np.abs(V_start) < .1 else "relatively"
            self.logprint(f"Warning. Attempting to approach while applying a {phrasing} low bias voltage ({V_start} V). Risk of tip crash. I suggest to abort the approach and to change the bias.", message_type = "warning")            
            t0 = time.time()
            t_elapsed = 0
            while t_elapsed < 5: # Give the user 5 seconds to respond
                self.check_abort_request()
                time.sleep(.01)
                t_elapsed = time.time() - t0
            
            self.logprint(f"No abort requested from user. I am proceeding.", message_type = "warning")



        # Prepare the approach sequence
        surface_reached = False
        max_observations = 10000
        max_steps = 10000
        t0 = time.time()
        t_elapsed = 0
        
        (tip_status, error) = nn.tip_update({"withdraw": True}, fast_mode = False)
        [z_min_nm, z_max_nm] = tip_status.get("z_limits (nm)")
        (feedback, error) = nn.feedback_update({"I_fb (pA)": 300, "p_gain (pm)": 40, "t_const (us)": 200}) # Alternative feedback settings specifically for the approach
        I_fb_pA = feedback.get("I_fb (pA)")
        
        match connected_device:
            case "nanonis":
                self.data_array.emit(np.array(["t (s)", "z (nm)", "I (pA)", "Re(a1) (nS)", "Im(a1) (fF)"]))
                
                signal_names = ["LI Demod 1 X (A)", "LI Demod 1 Y (A)"]
                (signal_dict, error) = nn.signals_update(signal_names)
                [LI_X_index, LI_Y_index] = [signal_dict[signal_name][0] for signal_name in signal_names]
                (lockin, error) = nn.lockin_update({"mod1": {"on": True, "amplitude (mV)": amp_approach_mV, "frequency (Hz)": f_approach_Hz}})

                (tip_status, error) = nn.tip_update({"feedback": True}, fast_mode = True)
                z_tip_nm = tip_status.get("z (nm)")
                
                for step in range(max_steps):
                    self.logprint(f"Auto approach step {step}", message_type = "message")
                    counter = 0
                    
                    (tip_status, error) = nn.tip_update({"feedback": True}, fast_mode = False, verbose = False)
                    for observation in range(max_observations):
                        (tip_status, error) = nn.tip_update({"feedback": True}, fast_mode = True, verbose = False)
                        (signal_dict, error) = nn.signals_update([LI_X_index, LI_Y_index], name_lookup = False, verbose = False)
                        t_elapsed = time.time() - t0
                        
                        LI_I_pA = signal_dict.get(LI_X_index)[1] * 1E12
                        LI_Q_pA = signal_dict.get(LI_Y_index)[1] * 1E12
                        LI_I_nS = LI_I_pA / amp_approach_mV
                        LI_Q_fF = LI_Q_pA * 1E6 / (amp_approach_mV * 2 * np.pi * f_approach_Hz)
                        
                        I_pA = tip_status.get("I (pA)")
                        z_tip_nm = tip_status.get("z (nm)")
                        
                        self.data_array.emit(np.array([t_elapsed, z_tip_nm, I_pA, LI_I_nS, LI_Q_fF]))
                        
                        if np.abs(I_pA) > I_fb_pA: counter += 1
                        else: counter = 0
                        if counter > 3:
                            surface_reached = True
                            break
                        if z_tip_nm < z_min_nm + 1: break
                        self.check_abort_request(withdraw = True)

                    nn.tip_update({"withdraw": True}, verbose = False)
                    if surface_reached:
                        self.logprint(f"Surface detected!", message_type = "message")
                        self.parameters.emit({"dict_name": "view_request", "view": "nanonis"})
                        break
                
                    nn.coarse_move({"minus_z_steps": 1}, verbose = False)
            
                nn.tip_update({"withdraw": True}, verbose = False)
                nn.feedback_update(start_feedback, verbose = False)
            
            case "mla":
                if tia_gain_V_per_pA: self.prepare_graph(["t (s)", "z (nm)", "I (pA)", "Re(a1) (nS)", "Im(a1) (fF)"])
                else: self.prepare_graph(["t (s)", "z (nm)", "I (pA)", "Re(a1) (mV)", "Im(a1) (mV)"])
                amplitudes = np.zeros(32)
                mla.autophase()
                mla.lockin_update({"df (Hz)": f_approach_Hz, "amplitudes (mV)": [amp_approach_mV, 0, 0, 0], "numbers": [1, 1, 2, 3], "mod0": {"on": True, "port": 1}, "input_mask": [1, 2, 2, 2]})
                mla.start_lockin()

                (tip_status, error) = nn.tip_update({"withdraw": True}, fast_mode = False)
                [z_min_nm, z_max_nm] = tip_status.get("z_limits (nm)")
                (feedback, error) = nn.feedback_update({"I_fb (pA)": 300, "p_gain (pm)": 40, "t_const (us)": 200}) # Alternative feedback settings specifically for the approach
                I_fb_pA = feedback.get("I_fb (pA)")

                (tip_status, error) = nn.tip_update({"feedback": True}, fast_mode = True)
                z_tip_nm = tip_status.get("z (nm)")
                
                for step in range(max_steps):
                    self.logprint(f"Auto approach step {step}", message_type = "message")
                    counter = 0
                    
                    (tip_status, error) = nn.tip_update({"feedback": True}, fast_mode = False, verbose = False)
                    for observation in range(max_observations):
                        (tip_status, error) = nn.tip_update({"feedback": True}, fast_mode = True, verbose = False)
                        t_elapsed = time.time() - t0
                        
                        (pix_V, pix_var_V) = mla.get_pixels(3, average = True)
                        pix_mV = 2000 * pix_V
                        I_pA = tip_status.get("I (pA)")
                        z_tip_nm = tip_status.get("z (nm)")
                        
                        if tia_gain_V_per_pA:
                            pix_pA = 2 * pix_V / tia_gain_V_per_pA
                            pix_nS = pix_pA / amp_approach_mV
                            cap_fF = 1E6 * np.imag(pix_nS[1]) / (2 * np.pi * f_approach_Hz)
                            self.data_array.emit(np.array([t_elapsed, z_tip_nm, I_pA, np.real(pix_nS[1]), cap_fF]))
                        else:
                            pix_mV = 2000 * pix_V
                            self.data_array.emit(np.array([t_elapsed, z_tip_nm, I_pA, np.real(pix_mV[1]), np.imag(pix_mV[1])]))
                        
                        if np.abs(I_pA) > I_fb_pA: counter += 1
                        else: counter = 0
                        if counter > 3:
                            surface_reached = True
                            break
                        if z_tip_nm < z_min_nm + 1: break
                        self.check_abort_request(withdraw = True)

                    nn.tip_update({"withdraw": True}, verbose = False)
                    if surface_reached:
                        self.logprint(f"Surface detected!", message_type = "message")
                        self.parameters.emit({"dict_name": "view_request", "view": "nanonis"})
                        break
                
                    nn.coarse_move({"minus_z_steps": 1}, verbose = False)
            
                nn.tip_update({"withdraw": True}, verbose = False)
                nn.feedback_update(start_feedback, verbose = False)
                mla.stop_lockin()
        
        (tip_status, error) = nn.tip_update({"withdraw": True}, fast_mode = False)


        