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
                
        # Testing the connected device using the lock-in amplifiers
        connected_device = self.connection_test(frequency_Hz = 600, amplitude_mV = 200, verbose = False, autophase = False)
        if not connected_device in ["nanonis", "mla"]:
            raise Exception("The STM does not seem to be connected to either Nanonis or the MLA. I am unable to see a response in the tunneling current. It is not safe to approach.")
        self.logprint(f"I detected that the STM sample bias is applied through the following device: {connected_device}.", message_type = "message")
        if connected_device == "mla":
            bias_dict = self.start_parameters["mla"].get("mla_bias")
            V_start = bias_dict.get("port_1 (V)")
        
        """
        iterations = 0
        while iterations < 20:
            iterations += 1
            self.check_abort_request()
            connected_device = self.connection_test(frequency_Hz = 600, amplitude_mV = 200, verbose = False, autophase = False)
            self.logprint(f"{connected_device = }")
            if connected_device == "nanonis": break
        
        self.logprint(f"I noticed you connected the sample bias to: {connected_device}. Please connect it to the MLA", message_type = "warning")
        
        iterations = 0
        while iterations < 20:
            iterations += 1
            self.check_abort_request()
            connected_device = self.connection_test(frequency_Hz = 600, amplitude_mV = 200, verbose = False, autophase = False)
            if connected_device == "mla": break

        self.logprint(f"Thank you for obeying my demands", message_type = "success")
        
        time.sleep(2)
        """

        if np.abs(V_start) < .6:
            if np.abs(V_start) < .1: self.logprint(f"Warning. Attempting to approach while applying a very low bias voltage ({V_start} V). Risk of tip crash. I suggest to abort the approach and to change the bias.", message_type = "warning")
            else: self.logprint(f"Warning. Attempting to approach while applying a relatively low bias voltage ({V_start} V). Risk of tip crash. I suggest to abort the approach and to change the bias.", message_type = "warning")
            t0 = time.time()
            t_elapsed = 0
            while t_elapsed < 5:
                self.check_abort_request()
                time.sleep(.01)
                t_elapsed = time.time() - t0
            
            self.logprint(f"No abort requested from user. I am proceeding.", message_type = "warning")

        match connected_device:
            case "nanonis":
                (tip_status, error) = nn.tip_update(fast_mode = False)
                signal_names = ["LI Demod 1 X (A)", "LI Demod 1 Y (A)"]
                (signal_dict, error) = nn.signals_update(signal_names)
                [LI_X_index, LI_Y_index] = [signal_dict[signal_name] for signal_name in signal_names]
                (lockin, error) = nn.lockin_update({"mod1": {"on": True, "amplitude (mV)": 2, "frequency (Hz)": 600}})

                (tip_status, error) = nn.tip_update({"withdraw": True}, fast_mode = False)
                [z_min_nm, z_max_nm] = tip_status.get("z_limits (nm)")
                (feedback, error) = nn.feedback_update({"I_fb (pA)": 300, "p_gain (pm)": 40, "t_const (us)": 200})
                I_fb_pA = feedback.get("I_fb (pA)")

                (tip_status, error) = nn.tip_update({"feedback": True}, fast_mode = True)
                z_tip_nm = tip_status.get("z (nm)")

                self.prepare_graph(["t (s)", "z (nm)", "I (pA)", "LI X (pA)", "LI Y (pA)"])

                surface_reached = False
                max_observations = 10000
                max_steps = 10000
                t0 = time.time()
                t_elapsed = 0
                
                for step in range(max_steps):
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
                        
                        if np.abs(I_pA) > I_fb_pA: counter += 1
                        else: counter = 0
                        if counter > 3:
                            surface_reached = True
                            break
                        if z_tip_nm < z_min_nm + 1: break
                        self.check_abort_request()
                
                    nn.tip_update({"withdraw": True})
                    if surface_reached:
                        self.logprint(f"Surface detected!", message_type = "message")
                        self.parameters.emit({"dict_name": "view_request", "view": "nanonis"})
                        break
                    
                    # Reset the feedback parameters
                    nn.feedback_update(start_feedback)
                    nn.coarse_move({"minus_z_steps": 1})
                    
                    
            
            case "mla":
                self.logprint(f"Sorry. I haven't learned to approach with the MLA yet")
        
        (tip_status, error) = nn.tip_update({"withdraw": True}, fast_mode = False)


        