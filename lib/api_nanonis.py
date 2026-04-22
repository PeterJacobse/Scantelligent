import numpy as np
from PyQt6 import QtCore
from . import NanonisHardware
from .data_processing import DataProcessing
from time import sleep, time



class NanonisAPI(QtCore.QObject):
    connection = QtCore.pyqtSignal(str) # This signal emits 'running' on connect, 'idle' after disconnect and 'offline' after an error to indicate the TCP connection status to the gui/program
    task_progress = QtCore.pyqtSignal(int) # Integer between 0 and 100 to indicate the progress of an experiment
    message = QtCore.pyqtSignal(str, str) # First argument is the message string, sedond argument is the message type, like 'warning', 'code', 'result', 'message', or 'error'
    parameters = QtCore.pyqtSignal(dict) # Any parameters dictionary sent through this signal should include a self-reference 'dict_name' such that the receiver can read it and understand what kind of parameters they are
    image = QtCore.pyqtSignal(np.ndarray) # A two-dimensional np.ndarray that is plotted in the gui when sent
    finished = QtCore.pyqtSignal() # Signal to indicate an experiment is finished
    data_array = QtCore.pyqtSignal(np.ndarray) # 2D array of collected data, with columns representing progression of the experiment and the rows being the different parameters being measured
    
    def __init__(self, hw_config: dict):
        super().__init__()
        self.nanonis_hardware = NanonisHardware(hw_config = hw_config)
        # nanonis_hardware methods are low-level methods performing direct communication to the Nanonis FPGA over TCP-IP
        # nanonisAPI methods are higher-level methods that incorporate these methods, but provide a friendlier interface
        # The alias nhw = self.nanonis_hardware is typically used within the methods of this API
        # Note:
        # Instantiation of NanonisHardware triggers a connection test, and an exception is raised when the connection fails
        # The exception should be caught in the code where the NanonisAPI object is instantiated
        self.status = "idle" # status turns to 'running' when an active TCP-IP connection exists
        self.data = DataProcessing()



    def link(self) -> None:
        nhw = self.nanonis_hardware
        if self.status == "running":
            self.logprint("Attempting to connect to Nanonis while it is already running. Operation aborted.", message_type = "error")
            return False

        connection_success = nhw.link()
        if connection_success:
            self.status = "running"
        else:
            self.status = "offline"
            self.logprint("Failed to connect to Nanonis.", message_type = "error")

        self.parameters.emit({"dict_name": "nanonis_status", "status": self.status})
        return f"Nanonis status: {self.status}"

    def unlink(self) -> None:
        nhw = self.nanonis_hardware
        nhw.unlink()
        self.status = "idle"
        self.parameters.emit({"dict_name": "nanonis_status", "status": self.status})
        return f"Nanonis status: {self.status}"

    def initialize(self, unlink: bool = True) -> tuple[dict, bool | str]:
        return self.nanonis_update(unlink = unlink)

    def nanonis_update(self, unlink: bool = True) -> tuple[dict, bool | str]:
        error = False
        parameters = {"dict_name": "nanonis_parameters"}

        try:
            if not self.status == "running": self.link()
            self.logprint("nanonis.nanonis_update()", message_type = "code")

            (session_path, error) = self.session_path_update() # Sends piezo range data with "dict_name": "piezo_range"
            if error: raise Exception(error)
            else: parameters.update({session_path.get("dict_name"): session_path})
            
            (piezo_range, error) = self.piezo_range_update() # Sends piezo range data with "dict_name": "piezo_range"
            if error: raise Exception(error)
            else: parameters.update({piezo_range.get("dict_name"): piezo_range})
            
            (coarse_parameters, error) = self.coarse_parameters_update() # Sends coarse parameter data with "dict_name": "coarse_parameters"
            if error: pass # Not useful to raise this error because the simulator does not have motor control
            else: parameters.update({coarse_parameters.get("dict_name"): coarse_parameters})
            
            (lockin_parameters, error) = self.lockin_update() # Sends coarse parameter data with "dict_name": "coarse_parameters"
            if error: raise Exception(error)
            else: parameters.update({lockin_parameters.get("dict_name"): lockin_parameters})
            
            (tip_status, error) = self.tip_update() # Sends tip status, position and current data with "dict_name": "tip_status"
            if error: raise Exception(error)
            else: parameters.update({tip_status.get("dict_name"): tip_status})
            
            (frame, error) = self.frame_update(update_new_frame = True) # Sends frame offset (relative to scan range origin), rotation angle and scan_range (size) with "dict_name": "frame"
            if error: raise Exception(error)
            else: parameters.update({frame.get("dict_name"): frame})
            
            (gains, error) = self.gains_update() # Sends gain parameters with "dict_name": "gains"
            if error: raise Exception(error)
            else: parameters.update({gains.get("dict_name"): gains})
            
            (speeds, error) = self.speeds_update() # Sends scan metadata like the channels being recorded in Nanonis; "dict_name": "grid"
            if error: raise Exception(error)
            else: parameters.update({speeds.get("dict_name"): speeds})
            
            (feedback_parameters, error) = self.feedback_update() # Sends scan parameters like voltage and current (parent of self.bias_update())
            if error: raise Exception(error)
            else: parameters.update({feedback_parameters.get("dict_name"): feedback_parameters})
            
            (grid, error) = self.grid_update() # Sends frame data combined with grid aspects like number of pixels and lines and calculated x_grid and y_grid, with "dict_name": "grid" (parent of self.frame_update())
            if error: raise Exception(error)
            else: parameters.update({grid.get("dict_name"): grid})
            
            (scan_metadata, error) = self.scan_metadata_update() # Sends scan metadata like the channels being recorded in Nanonis; "dict_name": "grid"
            if error: raise Exception(error)
            else: parameters.update({scan_metadata.get("dict_name"): scan_metadata})

            self.logprint("Initialization successful", "success")

        except Exception as e:
            error = e
            self.logprint(f"Initialization failed: {e}", "error")
            self.status == "offline"
            self.parameters.emit({"dict_name": "nanonis_status", "status": self.status})
        finally:
            if unlink: self.unlink()

        return (parameters, error)



    # Misc
    def logprint(self, message: str, message_type: str = "error") -> None:
        self.message.emit(message, message_type)
        return

    def grids_to_lists(self, grid_dict: dict = {}, direction: str = "up") -> tuple[dict, bool | str]:
        error = False
        lists = {"dict_name": "coordinate_lists"}
        conv = self.nanonis_hardware.conv

        for tag in ["x_grid (nm)", "y_grid (nm)"]:
            if not tag in grid_dict.keys():
                error = "grids_to_lists: Input is missing valid grids"
                return (lists, error)

        [x_grid, y_grid] = [grid_dict.get(attribute) for attribute in ["x_grid (nm)", "y_grid (nm)"]]
        match direction:
            case "down":
                x_grid = np.flipud(x_grid)
                y_grid = np.flipud(x_grid)
            case _:
                pass

        x_list = x_grid.flatten()
        y_list = y_grid.flatten()
        
        lists.update({"x_list (nm)": x_list, "y_list (nm)": y_list})
        
        xy_list = [conv.float64_to_hex(x * 1E-9) + conv.float64_to_hex(y * 1E-9) for x, y in zip(x_list, y_list)] # X and y merged in hexadecimal format for efficient use with nanonis_hardware.set_xy
        lists.update({"xy_list": xy_list})

        return (lists, error)

    def coords_of_grid_pixel(self, grid_dict: dict = {}, indices: list = [0, 0]) -> list:
        [x_nm, y_nm, angle_deg, width_nm, height_nm, pixels, lines] = [grid_dict.get(parameter) for parameter in ["x (nm)", "y (nm)", "angle (deg)", "width (nm)", "height (nm)", "pixels", "lines"]]
        [pixel, line] = indices
        
        x_local = ((pixel + .5) / pixels - 0.5) * width_nm
        y_local = (0.5 - (line + .5) / pixels) * height_nm
        
        cos = np.cos(np.deg2rad(angle_deg))
        sin = np.sin(np.deg2rad(angle_deg))

        x_abs_nm = x_nm + x_local * cos + y_local * sin
        y_abs_nm = y_nm + y_local * cos - x_local * sin

        return [x_abs_nm, y_abs_nm]

    def find_scan_image_minmax(self, scan_image: np.ndarray, grid_dict: dict = {}) -> dict:
        (blurred_image, error) = self.data.apply_gaussian(scan_image, sigma = 3)
        
        (max_line, max_pixel) = np.unravel_index(blurred_image.argmax(), blurred_image.shape)
        max_value = blurred_image[max_line, max_pixel]
        [x_max_nm, y_max_nm] = self.coords_of_grid_pixel(grid_dict = grid_dict, indices = [max_pixel, max_line])
        
        (min_line, min_pixel) = np.unravel_index(blurred_image.argmin(), blurred_image.shape)
        min_value = blurred_image[min_line, min_pixel]
        [x_min_nm, y_min_nm] = self.coords_of_grid_pixel(grid_dict = grid_dict, indices = [max_pixel, max_line])
        
        output_dict = {"minimum": {"pixel": int(min_pixel), "line": int(min_line), "value": float(min_value), "x (nm)": float(x_min_nm), "y (nm)": float(y_min_nm)},
                       "maximum": {"pixel": int(max_pixel), "line": int(max_line), "value": float(max_value), "x (nm)": float(x_max_nm), "y (nm)": float(y_max_nm)}}
        return output_dict



    # 'update' methods that can only read and not write
    def session_path_update(self, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        session_path = {"dict_name": "session_path"}
        error = False
        nhw = self.nanonis_hardware        
        
        # Set up the TCP connection and set/get
        try:
            if verbose: self.logprint(f"nanonis.session_path_update()", "code")
            if not self.status == "running": self.link()
            
            session_path.update({"path": nhw.get_path()})
            self.parameters.emit(session_path)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return (session_path, error)

    def piezo_range_update(self, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        nhw = self.nanonis_hardware
        piezo_range_dict = {"dict_name": "piezo_range"}

        try:
            if verbose: self.logprint(f"nanonis.piezo_range_update()", "code")
            if not self.status == "running": self.link()
            piezo_range = nhw.get_xy_range_nm()
            
            piezo_range_dict.update({
                "x_min (nm)": -0.5 * piezo_range[0], "x_max (nm)": 0.5 * piezo_range[0],
                "y_min (nm)": -0.5 * piezo_range[1], "y_max (nm)": 0.5 * piezo_range[1],
                "z_min (nm)": -0.5 * piezo_range[2], "z_max (nm)": 0.5 * piezo_range[2],
                "x_range (nm)": piezo_range[0], "y_range (nm)": piezo_range[1], "z_range (nm)": piezo_range[2]
            })
            self.parameters.emit(piezo_range_dict)

        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return (piezo_range_dict, error)

    def scan_metadata_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        """
        get_scan_metadata gets data regarding the properties of the current scan frame, such as the names of the recorded channels and the save properties
        """
        # Initalize outputs
        scan_metadata = None
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get grid dat
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"nanonis.scan_metadata_update({parameters})", "code")
                else: self.logprint(f"nanonis.scan_metadata_update()", "code")
            if not self.status == "running": self.link()
            
            props = nhw.get_scan_props()
            buffer = nhw.get_scan_buffer() # The buffer has the number of channels, indices of these channels, and pixels and lines
            
            if "channel_indices" in parameters.keys():
                indices = parameters["channel_indices"]
                if isinstance(indices, list) and len(indices) > 0 and isinstance(indices[0], int):
                    nhw.set_scan_buffer(channel_indices = indices)
            
            channel_indices = buffer.get("channel_indices")
            
            if nhw.version > 14000: # Newer versions of Nanonis work with signals in slots, meaning that a small subset of the total of 128 channels is put into numbered 'slots', which are available for data acquisition
                sig_in_slots = nhw.get_signals_in_slots()
                signal_names = sig_in_slots["names"]
                signal_indices = sig_in_slots["indices"]
            else:
                signal_names = nhw.get_signal_names()
            
            signal_dict = {signal_name: index for index, signal_name in enumerate(signal_names)} # Signal_dict is a dict of all signals and their corresponding indices
            channel_dict = {signal_names[index]: index for index in channel_indices} # Channel_dict is the subset of signals that are actively recorded in the scan

            scan_metadata = props | {"channel_dict": channel_dict, "signal_dict": signal_dict, "dict_name": "scan_metadata"}
            
            self.parameters.emit(scan_metadata)

        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return (scan_metadata, error)

    def scan_update(self, channel: int | str, backward: bool = False, unlink: bool = False, verbose: bool = True) -> tuple[np.ndarray, bool | str]:
        # Initalize outputs
        scan_data = None
        error = False
        nhw = self.nanonis_hardware
        scan_image = None

        # Set up the TCP connection and get grid data
        try:
            if verbose: self.logprint(f"nanonis.scan_update(channel_index = {channel}, backward = {backward})", "code")
            
            if isinstance(channel, str):
                (metadata, _) = self.scan_metadata_update()
                channel_dict = metadata.get("channel_dict")
                channel_index = channel_dict.get(channel)
            else:
                channel_index = channel
            
            if not isinstance(channel_index, int):
                error = "Requested channel not found"
                return (scan_image, error)
            
            if not self.status == "running": self.link()
            scan_data = nhw.get_scan_data(channel_index, not backward)
            scan_image = scan_data.get("scan_data")

            n_scan_image = np.size(scan_image)
            n_nans = np.count_nonzero(np.isnan(scan_image))

            completed_percentage = int(100 * (1 - n_nans / n_scan_image))
            self.task_progress.emit(completed_percentage)
            
            self.image.emit(scan_image)

        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return (scan_image, error)

    def signals_update(self, parameter_names: str | list, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        nhw = self.nanonis_hardware
        parameter_values = {"dict_name": "signals"}

        # If only a single parameter_name is provided, turn it into a list
        if isinstance(parameter_names, str): parameter_names = [parameter_names]

        try:
            if verbose: self.logprint(f"nanonis.signals_update({parameter_names})", "code")
            if not self.status == "running": self.link()

            (scan_metadata, error) = self.scan_metadata_update(verbose = False, unlink = False)
            if error: raise Exception(error)

            signal_dict = scan_metadata.get("signal_dict")

            # Find the requested parameters in the signal_dict
            for parameter_name in parameter_names:
                signal_index = signal_dict.get(parameter_name, None)
                
                # The parameter name is found in the dict and has a corresponding index
                if isinstance(signal_index, int):
                    signal_value = nhw.get_signal_value(signal_index)
                    parameter_values.update({parameter_name: signal_value})
                
                else:
                    parameter_values.update({parameter_name: "not found"})
            
            self.parameters.emit(parameter_values)
        
        except Exception as e: error = f"Unable to retrieve the requested parameters. {e}"
        finally:
            if unlink: self.unlink()

        return (parameter_values, error)



    # Update methods (Gives updates on all parameters and updates those parameters given)
    def tip_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        """
        Function to both control the tip status and receive it
        """
        # Initalize outputs
        tip_status = None
        error = False
        nhw = self.nanonis_hardware
                
        # Extract parameters from the dictionary
        [withdraw, feedback, x_nm, y_nm, z_nm, z_rel_nm] = [parameters.get(key, None) for key in ["withdraw", "feedback", "x (nm)", "y (nm)", "z (nm)", "z_rel (nm)"]]
        if withdraw == None: withdraw = False
        if x_nm and y_nm: xy_nm = [x_nm, y_nm]
        else: xy_nm = None

        # Set up the TCP connection and set/get
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"nanonis.tip_update({parameters})", "code")
                else: self.logprint(f"nanonis.tip_update()", "code")
            if not self.status == "running": self.link()
            
            if xy_nm: nhw.set_xy_nm(xy_nm) # Set the tip position
            xy_nm = nhw.get_xy_nm() # Get the tip position
            [x_nm, y_nm] = xy_nm
            if z_nm:
                nhw.set_fb(False)
                sleep(.2)
                nhw.set_z_nm(z_nm)
            z_nm = nhw.get_z_nm()
            if z_rel_nm:
                z_nm += z_rel_nm
                nhw.set_fb(False)
                sleep(.2)
                nhw.set_z_nm(z_nm)
            [z_min, z_max] = nhw.get_z_limits_nm()

            I_pA = nhw.get_I_pA() # get the current

            # Switch the feedback if desired, and retrieve the feedback status
            if type(feedback) == bool: nhw.set_fb(feedback)
                        
            withdrawn = False
            if not feedback and np.abs(z_nm - z_max) < 1E-11: # Tip is already withdrawn
                withdrawn = True
            if withdraw and not withdrawn: # Tip is not yet withdrawn, but a withdraw request is made
                nhw.withdraw(wait = True)
                withdrawn = True
            sleep(.2)
            
            # Retrieve the feedback status
            feedback_new = nhw.get_fb()

            # Set up a dictionary containing the actual tip status parameters
            tip_status = {
                "dict_name": "tip_status", "x (nm)": round(x_nm, 6), "y (nm)": round(y_nm, 6), "z (nm)": round(z_nm, 6), "I (pA)": round(I_pA, 6),
                "location (nm)": [round(x_nm, 6), round(y_nm, 6), round(z_nm, 6)], "z_limits (nm)": [round(z_min, 6), round(z_max, 6)],
                "feedback": feedback_new, "withdrawn": withdrawn
            }
            
            self.parameters.emit(tip_status)

        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return (tip_status, error)

    def coarse_parameters_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        nhw = self.nanonis_hardware
        motor_dict = {}
        
        # Set up the TCP connection and get
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"nanonis.coarse_parameters_update({parameters})", "code")
                else: self.logprint(f"nanonis.coarse_parameters_update()", "code")
            if not self.status == "running": self.link()
            
            # Read the parameters from Nanonis
            motor_dict = nhw.get_motor_f_A()
            motor_dict.update({"dict_name": "coarse_parameters"})
            self.message.emit(motor_dict)
            
            if "V_motor (V)" in parameters.keys(): motor_dict.update({"V_motor (V)": parameters.get("V_motor (V)")})
            if "f_motor (Hz)" in parameters.keys(): motor_dict.update({"f_motor (Hz)": parameters.get("f_motor (Hz)")})
            
            # Send the updated parameters back to Nanonis to update them
            if "V_motor (V)" in parameters.keys() or "f_motor (Hz)" in parameters.keys(): nhw.set_motor_f_A(motor_dict)
            
            self.parameters.emit(motor_dict)

        except Exception as e: error = e            
        finally:
            if unlink: self.unlink()

        return (motor_dict, error)

    def speeds_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        """
        Function to get and set speed parameters from Nanonis
        """
        # Initalize outputs
        coarse_parameters = False
        error = False
        nhw = self.nanonis_hardware
        
        # Extract numbers from parameters input
        [v_xy_nm_per_s, v_fwd_nm_per_s, v_bwd_nm_per_s, t_fwd_s, t_bwd_s, lock_param] = [parameters.get(key, None) for key in ["v_xy (nm/s)", "v_fwd (nm/s)", "v_bwd (nm/s)", "t_fwd (s)", "t_bwd (s)", "lock_v_or_t"]]

        # Set up the TCP connection and get
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"nanonis.scan_speeds_update({parameters})", "code")
                else: self.logprint(f"nanonis.scan_speeds_update()", "code")
            if not self.status == "running": self.link()

            new_speed_dict = {} # Compile the speed dict to send to nhw.set_v_scan
            for tag, parameter in zip(["v_fwd (nm/s)", "v_bwd (nm/s)", "t_fwd (s)", "t_bwd (s)", "lock_v_or_t"], [v_fwd_nm_per_s, v_bwd_nm_per_s, t_fwd_s, t_bwd_s, lock_param]):
                if parameter: new_speed_dict.update({tag: parameter})
            if len(new_speed_dict) > 0: nhw.set_v_scan(new_speed_dict) # Send
            
            speed_dict = nhw.get_v_scan() # Request the (updated) speeds from Nanonis

            # Tip speed
            v_xy_nm_per_s = nhw.get_v_xy_nm_per_s()
            
            parameters = speed_dict | {
                "dict_name": "speeds",
                "v_xy (nm/s)": v_xy_nm_per_s,
            }
            
            self.parameters.emit(parameters)

        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return (parameters, error)



    # To do: break this up in scan_parameters, gains, scan_speeds
    def feedback_update(self, parameters: dict = {}, unlink: bool = False) -> tuple[dict, bool | str]:
        """
        Function to get and set parameters from Nanonis
        """
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware
        
        # Extract numbers from parameters input
        I_fb_pA = parameters.get("I_fb (pA)", None)

        # Set up the TCP connection and get
        try:
            self.logprint(f"nanonis.feedback_update({parameters})", "code")
            if not self.status == "running": self.link()
            
            # Bias voltage
            (bias_dict, error) = self.bias_update(parameters, unlink = False)

            # Feedback current
            if I_fb_pA: nhw.set_I_fb_pA(I_fb_pA)
            else: I_fb_pA = nhw.get_I_fb_pA()

            bias_dict.pop("dict_name")
            parameters = {"dict_name": "feedback", "I_fb (pA)": I_fb_pA} | bias_dict
            
            self.parameters.emit(parameters)

        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return (parameters, error)

    def gains_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        """
        Function to get and set gains
        """
        # Initalize outputs
        gains_dict = {}
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get the frame
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"nanonis.gains_update({parameters})", "code")
                else: self.logprint(f"nanonis.gains_update()", "code")
            if not self.status == "running": self.link()

            # Extract the parameters from the provided dict
            p_gain_pm = parameters.get("p_gain (pm)", None)
            t_const_us = parameters.get("t_const (us)", None)

            # Retrieve the current gains from Nanonis, then overwrite them with the requested new parameters
            gains_dict = nhw.get_gains()
            if p_gain_pm: gains_dict.update({"p_gain (pm)": p_gain_pm})
            if t_const_us: gains_dict.update({"t_const (us)": t_const_us})
            if p_gain_pm or t_const_us: nhw.set_gains(gains_dict)

            gains_dict.update({"dict_name": "gains"})
            self.parameters.emit(gains_dict)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return (gains_dict, error)

    def frame_update(self, parameters: dict = {}, unlink: bool = False, update_new_frame: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        """
        Function to get and set frame
        """
        # Initalize outputs
        frame = None
        error = False
        nhw = self.nanonis_hardware
        new_parameters = {}

        # Set up the TCP connection and get the frame
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"nanonis.frame_update({parameters})", "code")
                else: self.logprint(f"nanonis.frame_update()", "code")
            if not self.status == "running": self.link()

            w_nm = None
            h_nm = None
            if "width (nm)" in parameters.keys():
                w_nm = parameters.get("width (nm)")
                h_nm = parameters.get("height (nm)", w_nm)
            elif "scan_range (nm)" in parameters.keys():
                [w_nm, h_nm] = parameters.get("scan_range (nm)")
            elif "size (nm)" in parameters.keys():
                [w_nm, h_nm] = parameters.get("size (nm)")
            if w_nm and h_nm: new_parameters.update({"width (nm)": w_nm, "height (nm)": h_nm, "size (nm)": [w_nm, h_nm], "scan_range (nm)": [w_nm, h_nm]})
            
            x_nm = None
            y_nm = None
            if "x (nm)" in parameters.keys():
                x_nm = parameters.get("x (nm)")
                y_nm = parameters.get("y (nm)", x_nm)
            elif "offset (nm)" in parameters.keys():
                [x_nm, y_nm] = parameters.get("offset (nm)")
            elif "center (nm)" in parameters.keys():
                [x_nm, y_nm] = parameters.get("center (nm)")
            if x_nm and y_nm: new_parameters.update({"x (nm)": x_nm, "y (nm)": y_nm, "offset (nm)": [x_nm, y_nm], "center (nm)": [x_nm, y_nm]})

            angle_deg = parameters.get("angle (deg)", None)
            if isinstance(angle_deg, float) or isinstance(angle_deg, int): new_parameters.update({"angle (deg)": angle_deg})

            frame = nhw.get_scan_frame_nm()
            if len(new_parameters) > 0:
                frame.update(new_parameters)
                nhw.set_scan_frame_nm(frame)

            frame.update({"dict_name": "frame"})
            self.parameters.emit(frame)
            
            if update_new_frame:
                frame.update({"dict_name": "new_frame"})
                self.parameters.emit(frame)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return (frame, error)

    def grid_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        """
        Function to get and set grid properties
        """
        # Initalize outputs
        grid = None
        error = False
        nhw = self.nanonis_hardware

        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"nanonis.grid_update({parameters})", "code")
                else: self.logprint(f"nanonis.grid_update()", "code")
            if not self.status == "running": self.link()
            
            # Get the frame and buffer
            frame = nhw.get_scan_frame_nm()
            buffer = nhw.get_scan_buffer()

            # Save the data to a dictionary
            [width, height, angle] = [frame.get(key) for key in ["width (nm)", "height (nm)", "angle (deg)"]]
            [pixels, lines] = [buffer.get(key) for key in ["pixels", "lines"]]            
            grid = frame | buffer | {
                "pixel_width (nm)": width / pixels,
                "pixel_height (nm)": height / lines,
                "dict_name": "grid"
            }

        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        if error: return (grid, error)
        
        # Append the grid data with calculated information
        try:
            # Construct a local grid with the same size as the Nanonis grid, with center is at (0, 0)
            x_coords_local = np.linspace(-width / 2, width / 2, pixels)
            y_coords_local = np.linspace(-height / 2, height / 2, lines)
            x_grid_local, y_grid_local = np.meshgrid(x_coords_local, y_coords_local)

            # Apply a rotation
            cos = np.cos(np.deg2rad(angle))
            sin = np.sin(np.deg2rad(angle))
            x_grid = np.zeros_like(x_grid_local)
            y_grid = np.zeros_like(y_grid_local)

            for i in range(lines):
                for j in range(pixels):
                    x_grid[i, j] = x_grid_local[i, j] * cos + y_grid_local[i, j] * sin
                    y_grid[i, j] = y_grid_local[i, j] * cos - x_grid_local[i, j] * sin

            # Apply a translation
            x_grid += grid["x (nm)"]
            y_grid += grid["y (nm)"]

            # Add the meshgrids to the grid dictionary
            grid["x_grid (nm)"] = x_grid
            grid["y_grid (nm)"] = y_grid

            # Add vertex information
            frame_vertices = np.asarray([[x_grid[0, 0], y_grid[0, 0]], [x_grid[-1, 0], y_grid[-1, 0]], [x_grid[-1, -1], y_grid[-1, -1]], [x_grid[0, -1], y_grid[0, -1]]])
            bottom_left_corner = frame_vertices[0]
            top_left_corner = frame_vertices[1]
            grid["vertices (nm)"] = frame_vertices
            grid["bottom_left_corner (nm)"] = bottom_left_corner
            grid["top_left_corner (nm)"] = top_left_corner
            
            self.parameters.emit(grid)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return (grid, error)

    def bias_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware
        
        # Extract parameters from the dictionary
        V = parameters.get("V_nanonis (V)", None)
        dt = parameters.get("dt_nanonis (ms)", 5) / 1000
        dV = parameters.get("dV_nanonis (mV)", 10) / 1000
        dz_nm = parameters.get("dz_nanonis (nm)", 1)
        
        bias_dict = {"dV_nanonis (mV)": dV * 1000, "dt_nanonis (ms)": dt * 1000, "dz_nanonis (nm)": dz_nm, "dict_name": "bias"}
        
        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"nanonis.bias_update({parameters})", "code")
                else: self.logprint(f"nanonis.bias_update()", "code")
            if not self.status == "running": self.link()                            
            V_old = nhw.get_V() # Read data from Nanonis
            if not isinstance(V, float | int): V = V_old # V not provided; substitute the old bias
            bias_dict.update({"V_nanonis (V)": V})
            if np.abs(V - V_old) < dV:
                self.parameters.emit(bias_dict)
                return (bias_dict, error) # If the bias is unchanged, don't slew it

            feedback = nhw.get_fb()
            tip_height = nhw.get_z_nm()
            polarity_difference = np.sign(V) * np.sign(V_old) < 0 # True if the sign changes
            
            if V > V_old: delta_V = dV # Change the sign of deltaV to get the arange right
            else: delta_V = -dV
            slew = np.arange(V_old, V, delta_V)

            if bool(feedback) and bool(polarity_difference): # If the bias polarity is switched, switch off the feedback and lift the tip by dz for safety
                nhw.set_fb(False)
                sleep(.1) # If the tip height is set too quickly, the controller won't be off yet
                nhw.set_z_nm(tip_height + dz_nm)

            for V_t in slew: # Perform the slew to the new bias voltage
                nhw.set_V(V_t)
                sleep(dt)
            nhw.set_V(V) # Final bias value
        
            if bool(feedback) and bool(polarity_difference):
                nhw.set_fb(True) # Turn the feedback back on
            
            if unlink: self.unlink()
            
            self.parameters.emit(bias_dict)

        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (bias_dict, error)

    def lockin_update(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict | str]:
        error = False
        nhw = self.nanonis_hardware

        lockin_parameters = {"dict_name": "lockin"}

        try:
            if verbose:
                if len(parameters) > 0: self.logprint(f"nanonis.lockin_update({parameters})", "code")
                else: self.logprint(f"nanonis.lockin_update()", "code")
                    
            if not self.status == "running": self.link()
            mod1_dict = parameters.get("mod1", None)
            mod2_dict = parameters.get("mod2", None)

            for mod_number, mod in enumerate([mod1_dict, mod2_dict]):
                mod_on = nhw.get_lockin_on(mod_number + 1)
                amplitude_mV = nhw.get_lockin_amp(mod_number + 1)
                frequency_Hz = nhw.get_lockin_freq(mod_number + 1)
                phase_deg = nhw.get_lockin_phase(mod_number + 1)
                if frequency_Hz > .01: time_ms = 1000 / frequency_Hz
                else: time_ms = None
                
                mod_new = {"on": mod_on, "frequency (Hz)": frequency_Hz, "amplitude (mV)": amplitude_mV, "phase (deg)": phase_deg, "time_constant (ms)": time_ms}
    
                if isinstance(mod, dict):
                    mod_on = mod.get("on", None)
                    if isinstance(mod_on, bool):
                        try:
                            nhw.set_lockin_on(mod_number + 1, mod_on)
                            mod_new.update({"on": mod_on})
                        except:
                            pass
                    
                    amp = mod.get("amplitude (mV)", None)
                    if isinstance(amp, float) or isinstance(amp, int):
                        try:
                            nhw.set_lockin_amp(mod_number + 1, amp)
                            mod_new.update({"amplitude (mV)": amp})
                        except:
                            pass
                    
                    freq = mod.get("frequency (Hz)", None)
                    if isinstance(freq, float) or isinstance(freq, int):
                        try:
                            nhw.set_lockin_freq(mod_number + 1, freq)
                            mod_new.update({"frequency (Hz)": freq})
                            
                            mod_new.update({"time_constant (ms)": 1000 / freq})
                        except:
                            pass
                    
                    phase = mod.get("phase (deg)", None)
                    if isinstance(phase, float) or isinstance(phase, int):
                        try:
                            nhw.set_lockin_phase(mod_number + 1, phase)
                            mod_new.update({"phase (deg)": phase})
                        except:
                            pass
                    
                lockin_parameters.update({f"mod{mod_number + 1}": mod_new})
        
            self.parameters.emit(lockin_parameters)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return (lockin_parameters, error)



    # Simple actions
    def tip_prep(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> bool | str:
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware

        try:
            if verbose: self.logprint(f"nanonis.tip_prep({parameters})", "code")
            if not self.status == "running": self.link()
            if parameters.get("action", "pulse") == "pulse":
                V_pulse_V = parameters.get("V_pulse (V)", 6)
                t_pulse_ms = parameters.get("t_pulse (ms)", 1000)
                nhw.pulse(V_pulse_V, t_pulse_ms)
            else:
                nhw.shape_tip()

        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return error

    def coarse_move(self, parameters: dict, unlink: bool = False, verbose: bool = True) -> bool | str:
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware

        motions = []
        V_hor = parameters.get("V_hor (V)")
        V_ver = parameters.get("V_ver (V)")
        f_motor = parameters.get("f_motor (Hz)")
        
        try:
            if verbose: self.logprint(f"nanonis.coarse_move({parameters})", message_type = "code")
            if not self.status == "running": self.link()
            
            # 1. Withdraw
            withdraw = parameters.get("withdraw", False)
            if withdraw: self.tip_update({"withdraw": True}, unlink = False)

            # 2. Retract
            steps = parameters.get("z_steps", 0)
            if type(steps) == int and steps > 0:
                motions.append({"direction": "up", "steps": steps, "V_motor (V)": V_ver, "f_motor (Hz)": f_motor})
            
            # 3. Move horizontally
            steps = parameters.get("h_steps", 0)
            if type(steps) == int and steps > 0:
                direction = parameters.get("direction", "none")
                match direction:
                    case "up": directions = []
                    case "down": directions = []
                    case "ne": directions = ["n", "e"]
                    case "se": directions = ["s", "e"]
                    case "sw": directions = ["s", "w"]
                    case "nw": directions = ["n", "w"]
                    case _: directions = [direction]
                [motions.append({"direction": drxn, "steps": steps, "V_motor (V)": V_hor, "f_motor (Hz)": f_motor}) for drxn in directions]
            
            # 4. Advance
            minus_z_steps = parameters.get("minus_z_steps", 0)
            if type(minus_z_steps) == int and minus_z_steps > 0:
                motions.append({"direction": "down", "steps": minus_z_steps, "V_motor (V)": V_ver, "f_motor (Hz)": f_motor})
            
            # 5. Execute the motions
            for motion in motions:
                direction = motion.get("direction", "none")
                steps = motion.get("steps", 0)
                V_motor = motion.get("V_motor (V)")
                f_motor = motion.get("f_motor (Hz)")
                self.logprint(f"Moving {steps} steps in direction {direction}", message_type = "message")
                
                nhw.set_motor_f_A({"V_motor (V)": V_motor, "f_motor (Hz)": f_motor})
                nhw.coarse_move({"direction": direction, "steps": steps, "wait": True})

            # 5. Approach
            approach = parameters.get("approach", False)
            if approach: self.auto_approach(True, V_motor = V_ver, unlink = False)

        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
        
        return error

    def auto_approach(self, status: bool = True, V_motor: float = None, unlink: bool = False, verbose: bool = True) -> bool | str:
        """
        Function to turn on/off the auto approach feature of the Nanonis
        """
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware

        try:
            if verbose: self.logprint(f"nanonis.auto_approach({status})", "code")
            if not self.status == "running": self.link()
            if V_motor: nhw.set_motor_f_A({"V_motor (V)": V_motor})
            nhw.auto_approach(status)

        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return error

    def scan_action(self, parameters: dict, unlink: bool = False, verbose: bool = True) -> bool | str:
        error = False
        nhw = self.nanonis_hardware
        direction = parameters.get("direction", "down")
        
        try:
            if verbose: self.logprint(f"nanonis.scan_action({parameters})", "code")
            if not self.status == "running": self.link()
            
            if "start" in parameters.values(): nhw.start_scan(direction)
            elif "stop" in parameters.values(): nhw.stop_scan()
            elif "resume" in parameters.values(): nhw.resume_scan()
            else: nhw.pause_scan()
        
        except Exception as e:
            error = f"Unable to execute the scan action. {e}"
        
        finally:
            if unlink: self.unlink()
        
        return error

    def jitter_tip(self, parameters: dict = {}, unlink: bool = False, verbose: bool = True) -> tuple[dict, bool | str]:
        error = False
        
        [iterations, radius] = [parameters.get(parameter) for parameter in ["iterations", "radius"]]
        if not isinstance(iterations, int): iterations = 32
        if not isinstance(radius, float | int): radius = 1.
        
        results_dict = {"dict_name": "jitter_result", "iterations": iterations, "radius": radius}
        
        try:
            if verbose: self.logprint(f"nanonis.jitter_tip({parameters})", "code")
            if not self.status == "running": self.link()
            (begin_status, error) = self.tip_update(verbose = False)
            [x_start_nm, y_start_nm, z_start_nm, I_start_pA] = [begin_status.get(parameter) for parameter in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]

            rng = np.random.default_rng()
            
            x_list = [x_start_nm]
            y_list = [y_start_nm]
            z_list = [z_start_nm]
            I_list = [I_start_pA]
            
            for iteration in range(iterations):            
                theta = rng.uniform(0, 2 * np.pi)
                r = radius * np.sqrt(rng.uniform(0, 1))
                x_nm = x_start_nm + r * np.cos(theta)
                y_nm = y_start_nm + r * np.sin(theta)
                
                (status, error) = self.tip_update({"x (nm)": x_nm, "y (nm)": y_nm}, verbose = False)            
                [x_nm, y_nm, z_nm, I_pA] = [status.get(parameter) for parameter in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
                x_list.append(x_nm)
                y_list.append(y_nm)
                z_list.append(z_nm)
                I_list.append(I_pA)
        
            (end_status, error) = self.tip_update({"x (nm)": x_start_nm, "y (nm)": y_start_nm}, verbose = False) # Reset
            
            results_dict.update({"x_values (nm)": x_list, "y_values (nm)": y_list, "z_values (nm)": z_list, "I_values (pA)": I_list,
                            "x_avg (nm)": round(float(np.average(x_list)), 6), "y_avg (nm)": round(float(np.average(y_list)), 6),
                            "z_avg (nm)": round(float(np.average(z_list)), 6), "x_avg (nm)": round(float(np.average(z_list)), 6)})
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()
            
        return (results_dict, error)



    # Idling
    def tip_tracker(self, timeout = 6000, unlink = False) -> None:
        error = False
        nhw = self.nanonis_hardware
        
        # Emit the parameters to be captured to the GUI
        recorded_channels = ["t (s)", "x (nm)", "y (nm)", "z (nm)", "I (pA)", "v_xy (nm/s)", "v_z (nm/s)"]
        channel_dict = {index: channel for index, channel in enumerate(recorded_channels)}
        channel_dict.update({"dict_name": "channels"})
        self.parameters.emit(channel_dict)
        
        chunk_size = 10
        data = np.zeros((chunk_size, len(recorded_channels)), dtype = float)
        
        try:
            self.message.emit(f"tip_tracker()", "code")
            if not self.status == "running": self.link()
            
            t0 = time() # Start time            
            
            for iteration in range(100):
                mod_iteration = iteration % chunk_size
                
                t = time() - t0
                xy_nm = nhw.get_xy_nm()
                z_nm = nhw.get_z_nm()
                I_pA = nhw.get_I_pA()
                                
                data[mod_iteration] = [t, xy_nm[0], xy_nm[1], z_nm, I_pA, 0, 0]
                if mod_iteration == chunk_size - 1: self.data_array.emit(data)
                
                if t > timeout: break
        
        except Exception as e:
            error = e
            if unlink: self.unlink()
            return error    
        
        return



    # Does not work yet
    def get_spectrum(self, unlink: bool = True) -> tuple[dict | str]:
        # Initalize outputs
        data_dict = {}
        parameters = []
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get the frame
        try:
            if not self.status == "running": self.link()
            spectrum = nhw.get_spectrum()
            #self.parameters.emit(frame)
        
        except Exception as e: error = e
        finally:
            if unlink: self.unlink()

        return (spectrum, error)


