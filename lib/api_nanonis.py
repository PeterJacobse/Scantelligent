import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets

from .hw_nanonis import NanonisHardware
from .data_processing import DataProcessing
from time import sleep, time
import pint



colors = {"red": "#ff5050", "dark_red": "#800000", "green": "#00ff00", "dark_green": "#005000", "lightblue": "#30d0ff",
          "white": "#ffffff", "blue": "#2090ff", "orange": "#FFA000","dark_orange": "#A05000", "black": "#000000", "purple": "#700080"}



class NanonisAPI(QtCore.QObject):
    connection = QtCore.pyqtSignal(str) # This signal emits 'running' on connect, 'idle' after disconnect and 'offline' after an error to indicate the TCP connection status to the gui/program
    progress = QtCore.pyqtSignal(int) # Integer between 0 and 100 to indicate the progress of an experiment
    message = QtCore.pyqtSignal(str, str) # First argument is the message string, sedond argument is the message type, like 'warning', 'code', 'result', 'message', or 'error'
    parameters = QtCore.pyqtSignal(dict) # Any parameters dictionary sent through this signal should include a self-reference 'dict_name' such that the receiver can read it and understand what kind of parameters they are
    image = QtCore.pyqtSignal(np.ndarray) # A two-dimensional np.ndarray that is plotted in the gui when sent
    finished = QtCore.pyqtSignal() # Signal to indicate an experiment is finished
    data_array = QtCore.pyqtSignal(np.ndarray) # 2D array of collected data, with columns representing progression of the experiment and the rows being the different parameters being measured
    
    def __init__(self, hardware: dict):
        super().__init__()
        self.ureg = pint.UnitRegistry() # For dealing with quantities
        self.nanonis_hardware = NanonisHardware(hardware = hardware)
        self.data = DataProcessing()
        self.status = "idle" # status turns to 'running' when an active TCP-IP connection exists
        self.timer = QtCore.QTimer()

    def connect(self) -> None:
        nhw = self.nanonis_hardware
        if self.status == "running":
            self.logprint("Attempting to connect to Nanonis while it is already running. Operation aborted.", message_type = "error")
            return False

        connection_success = nhw.connect()
        if connection_success:
            self.status = "running"
        else:
            self.status = "offline"
            self.logprint("Failed to connect to Nanonis.", message_type = "error")
        
        self.connection.emit(self.status)

        return f"Nanonis status: {self.status}"

    def disconnect(self) -> None:
        nhw = self.nanonis_hardware
        nhw.disconnect()
        self.status = "idle"
        self.connection.emit(self.status)
        return

    def initialize(self, auto_disconnect: bool = False) -> None:
        # Set up the TCP connection and get all relevant parameters
        self.logprint("nanonis.initialize()", message_type = "code")
        try:
            if not self.status == "running": self.connect()

            (piezo_range, error) = self.piezo_range_update() # Sends piezo range data with "dict_name": "piezo_range"
            if error: raise Exception(error)
            (coarse_parameters, error) = self.coarse_parameters_update() # Sends coarse parameter data with "dict_name": "coarse_parameters"
            # if error: raise Exception(error)
            # Not useful to raise this error because the simulator does not have motor control
            (tip_status, error) = self.tip_update() # Sends tip status, position and current data with "dict_name": "tip_status"
            if error: raise Exception(error)
            (frame, error) = self.frame_update() # Sends frame offset (relative to scan range origin), rotation angle and scan_range (size) with "dict_name": "frame"
            if error: raise Exception(error)
            (parameters, error) = self.parameters_update() # Sends scan parameters like voltage, current, feedback and scan speed with "dict_name": "scan_parameters"
            if error: raise Exception(error)
            (grid, error) = self.grid_update() # Sends frame data combined with grid aspects like number of pixels and lines and calculated x_grid and y_grid, with "dict_name": "grid"
            if error: raise Exception(error)
            (scan_metadata, error) = self.scan_metadata_update() # Sends scan metadata like the channels being recorded in Nanonis; "dict_name": "grid"
            if error: raise Exception(error)
            
            self.logprint("Initialization successful", "success")

        except Exception as e:
            error = e
            self.logprint(f"Initialization failed: {e}", "error")
            self.status == "offline"
            self.connection.emit("offline")
        finally:
            if auto_disconnect: self.disconnect()

        return error



    #PyQt slots
    @QtCore.pyqtSlot()
    def receive_parameters(self, parameters: dict) -> None:
        self.logprint(f"Class NanonisAPI received parameters: {parameters}", message_type = "message")
        return

    @QtCore.pyqtSlot(int, bool)
    def receive_image_request(self, channel_index: int = 0, backward: bool = False) -> None:
        try:
            self.connect()

            self.frame_update(auto_disconnect = False)
            self.tip_update(auto_disconnect = False)
            self.scan_metadata_update(auto_disconnect = False)
            self.scan_update(channel_index = channel_index, backward = backward, auto_disconnect = False)
        
        except Exception as e:
            self.logprint(f"Error in receive_image_request: {e}", message_type = "error")
        
        finally:
            self.disconnect()

        return

    @QtCore.pyqtSlot()
    def abort(self) -> None:
        try:
            # self.connect()
            # self.scan_control({"action": "stop"}, auto_disconnect = False)
            # self.stop_timed_updates()
            self.abort_flag = True
        finally:
            self.disconnect()

        return

    def logprint(self, message: str, message_type: str = "error") -> None:
        self.message.emit(message, message_type)
        return



    def start_timed_updates(self) -> None:
        self.timer.timeout.connect(self.receive_image_request)
        self.timer.start(1000)
        return

    def stop_timed_updates(self) -> None:
        self.timer.timeout.disconnect(self.receive_image_request)
        self.timer.stop()
        return

    def send_tip_update(self) -> None:
        self.tip_update()
        return

    def scan_control(self, parameters: dict = {}, auto_disconnect: bool = False) -> bool | str:
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware
        
        action = parameters.get("action", "pause")
        direction = parameters.get("direction", "down")
        
        # Set up the TCP connection and get grid dat
        try:
            if not self.status == "running": self.connect()
            
            dirxn = "up"
            if direction == "down": dirxn = "down"
            match action:
                case "start":
                    self.progress.emit(0)
                    nhw.start_scan(dirxn)
                case "pause":
                    nhw.pause_scan()
                case "resume":
                    nhw.resume_scan()
                case "stop":
                    nhw.stop_scan()
                    self.finished.emit()
                case _: pass
        
        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return error



    # 'update' methods that can only read and not write
    def piezo_range_update(self, auto_disconnect: bool = False) -> None:
        error = False
        nhw = self.nanonis_hardware
        piezo_range_dict = {}

        try:
            self.message.emit(f"piezo_range_update()", "code")
            if not self.status == "running": self.connect()
            piezo_range = nhw.get_range_nm()
            
            piezo_range_dict = {"dict_name": "piezo_range",
                "x_min (nm)": -0.5 * piezo_range[0], "x_max (nm)": 0.5 * piezo_range[0],
                "y_min (nm)": -0.5 * piezo_range[1], "y_max (nm)": 0.5 * piezo_range[1],
                "z_min (nm)": -0.5 * piezo_range[2], "z_max (nm)": 0.5 * piezo_range[2],
                "x_range (nm)": piezo_range[0], "y_range (nm)": piezo_range[1], "z_range (nm)": piezo_range[2]
            }
            self.parameters.emit(piezo_range_dict)

        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (piezo_range_dict, error)

    def scan_update(self, channel_index, backward: bool = False, auto_disconnect: bool = False) -> np.ndarray:
        # Initalize outputs
        scan_data = None
        error = False
        nhw = self.nanonis_hardware
        scan_image = None

        # Set up the TCP connection and get grid dat
        try:
            if not self.status == "running": self.connect()
            
            scan_data = nhw.get_scan_data(channel_index, backward)
            scan_image = scan_data.get("scan_data")
            
            n_scan_image = np.size(scan_image)
            n_nans = np.count_nonzero(np.isnan(scan_image))

            completed_percentage = int(100 * (1 - n_nans / n_scan_image))
            self.progress.emit(completed_percentage)
            
            (processed_image, error) = self.data.subtract_background(scan_image, mode = "plane")
            processed_image = np.real(processed_image)
            self.image.emit(processed_image)

            # Finished
            if n_nans == 0:
                self.stop_timed_updates()
                self.finished.emit()

        except Exception as e: error = e
        finally:
            if auto_disconnect: nhw.disconnect()

        return (scan_image, error)



    # Update methods (Gives updates on all parameters and updates those parameters given)
    def tip_update(self, parameters: dict = {}, auto_disconnect: bool = False) -> tuple[dict, bool | str]:
        """
        Function to both control the tip status and receive it
        """
        # Initalize outputs
        tip_status = None
        error = False
        nhw = self.nanonis_hardware
                
        # Extract parameters from the dictionary
        withdraw = parameters.get("withdraw", False)
        feedback = parameters.get("feedback", None)
        x_nm = parameters.get("x (nm)", None)
        y_nm = parameters.get("y (nm)", None)
        if x_nm and y_nm: xy_nm = [x_nm, y_nm]
        else: xy_nm = None

        # Set up the TCP connection and set/get
        try:
            self.message.emit(f"tip_update({{parameters = {parameters}}})", "code")
            if not self.status == "running": self.connect()
            
            if xy_nm: nhw.set_xy_nm(xy_nm) # Set the tip position
            xy_nm = nhw.get_xy_nm() # Get the tip position
            [x_nm, y_nm] = xy_nm
            z_nm = nhw.get_z_nm()
            z_bs = nhw.get_z()
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
                "dict_name": "tip_status",
                "x (nm)": x_nm,
                "y (nm)": y_nm,
                "z (nm)": z_nm,
                "I (pA)": I_pA,
                "location (nm)": [x_nm, y_nm, z_nm],
                "z (bytestring)": z_bs,
                "z_limits (nm)": [z_min, z_max],
                "feedback": feedback_new,
                "withdrawn": withdrawn
            }
            
            self.parameters.emit(tip_status)

        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (tip_status, error)

    def coarse_parameters_update(self, parameters: dict = {}, auto_disconnect: bool = False) -> tuple[dict, bool | str]:
        error = False
        nhw = self.nanonis_hardware
        motor_dict = {}
        
        # Set up the TCP connection and get
        try:
            self.message.emit(f"coarse_parameters_update({{parameters = {parameters}}})", "code")
            if not self.status == "running": self.connect()
            
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
            if auto_disconnect: self.disconnect()

        return (motor_dict, error)

    def scan_speeds_update(self, parameters: dict = {}, auto_disconnect: bool = False) -> tuple[dict, bool | str]:
        """
        Function to get and set speed parameters from Nanonis
        """
        # Initalize outputs
        coarse_parameters = False
        error = False
        nhw = self.nanonis_hardware
        
        # Extract numbers from parameters input
        I_fb_pA = parameters.get("I_fb (pA)", None)
        v_fwd_nm_per_s = parameters.get("v_fwd (nm/s)", None)
        v_bwd_nm_per_s = parameters.get("v_bwd (nm/s)", None)
        t_fwd_s = parameters.get("t_fwd (s)", None)
        t_bwd_s = parameters.get("t_bwd (s)", None)
        const_param = parameters.get("const_param", None)
        V_nanonis = parameters.get("V_nanonis (V)", None)
        p_gain_pm = parameters.get("p_gain (pm)", None)
        t_const_us = parameters.get("t_const (us)", None)

        # Set up the TCP connection and get
        try:
            if not self.status == "running": self.connect()
            
            # Bias voltage
            if V_nanonis: V = self.bias_update({"V_nanonis (V)": V_nanonis}, auto_disconnect = False)
            else: V = nhw.get_V()
            
            # Feedback current
            if I_fb_pA: nhw.set_I_fb_pA(I_fb_pA)
            else: I_fb_pA = nhw.get_I_fb_pA()

            # Feedback gains
            gains_dict = nhw.get_gains()
            if p_gain_pm: gains_dict.update({"p_gain (pm)": p_gain_pm})
            if t_const_us: gains_dict.update({"t_const (us)": t_const_us})
            if p_gain_pm or t_const_us: nhw.set_gains(gains_dict)

            # Scan speeds
            speed_dict = nhw.get_v_scan_nm_per_s()
            new_speed_dict = {}
            if v_fwd_nm_per_s:
                new_speed_dict.update({"v_fwd (nm/s)": v_fwd_nm_per_s})
            elif t_fwd_s:
                new_speed_dict.update({"t_fwd (s)": t_fwd_s})
            
            if v_bwd_nm_per_s:
                new_speed_dict.update({"v_bwd (nm/s)": v_bwd_nm_per_s})
            elif t_bwd_s:
                new_speed_dict.update({"t_bwd (s)": t_bwd_s})
            if v_fwd_nm_per_s or v_bwd_nm_per_s or t_fwd_s or t_bwd_s or const_param: nhw.set_v_scan_nm_per_s(new_speed_dict)

            # Tip speed
            v_xy_nm_per_s = nhw.get_v_xy_nm_per_s()

            # Session path
            session_path = nhw.get_path()

            # Coarse motor parameters
            try: coarse_parameters = nhw.get_motor_f_A() # Evidently does not work in the simulator, which does not have coarse motor control
            except: pass
            
            parameters = gains_dict | speed_dict | {
                "dict_name": "scan_parameters",
                "V_nanonis (V)": V,
                "I_fb (pA)": I_fb_pA,
                "v_xy (nm/s)": v_xy_nm_per_s,
                "session_path": session_path
            }
            if coarse_parameters: parameters.update({"motor_frequency": coarse_parameters.get("frequency"), "motor_amplitude": coarse_parameters.get("amplitude")})
            
            self.parameters.emit(parameters)

        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (parameters, error)



    # To do: break this up in scan_parameters, gains, scan_speeds
    def parameters_update(self, parameters: dict = {}, auto_disconnect: bool = False) -> tuple[dict, bool | str]:
        """
        Function to get and set parameters from Nanonis
        """
        # Initalize outputs
        coarse_parameters = False
        error = False
        nhw = self.nanonis_hardware
        
        # Extract numbers from parameters input
        I_fb_pA = parameters.get("I_fb (pA)", None)
        v_fwd_nm_per_s = parameters.get("v_fwd (nm/s)", None)
        v_bwd_nm_per_s = parameters.get("v_bwd (nm/s)", None)
        t_fwd_s = parameters.get("t_fwd (s)", None)
        t_bwd_s = parameters.get("t_bwd (s)", None)
        const_param = parameters.get("const_param", None)
        V_nanonis = parameters.get("V_nanonis (V)", None)
        p_gain_pm = parameters.get("p_gain (pm)", None)
        t_const_us = parameters.get("t_const (us)", None)

        # Set up the TCP connection and get
        try:
            self.message.emit(f"parameters_update({{parameters = {parameters}}})", "code")
            if not self.status == "running": self.connect()
            
            # Bias voltage
            if V_nanonis: V = self.bias_update({"V_nanonis (V)": V_nanonis}, auto_disconnect = False)
            else: V = nhw.get_V()
            
            # Feedback current
            if I_fb_pA: nhw.set_I_fb_pA(I_fb_pA)
            else: I_fb_pA = nhw.get_I_fb_pA()

            # Feedback gains
            gains_dict = nhw.get_gains()
            if p_gain_pm: gains_dict.update({"p_gain (pm)": p_gain_pm})
            if t_const_us: gains_dict.update({"t_const (us)": t_const_us})
            if p_gain_pm or t_const_us: nhw.set_gains(gains_dict)

            # Scan speeds
            speed_dict = nhw.get_v_scan_nm_per_s()
            new_speed_dict = {}
            if v_fwd_nm_per_s:
                new_speed_dict.update({"v_fwd (nm/s)": v_fwd_nm_per_s})
            elif t_fwd_s:
                new_speed_dict.update({"t_fwd (s)": t_fwd_s})
            
            if v_bwd_nm_per_s:
                new_speed_dict.update({"v_bwd (nm/s)": v_bwd_nm_per_s})
            elif t_bwd_s:
                new_speed_dict.update({"t_bwd (s)": t_bwd_s})
            if v_fwd_nm_per_s or v_bwd_nm_per_s or t_fwd_s or t_bwd_s or const_param: nhw.set_v_scan_nm_per_s(new_speed_dict)

            # Tip speed
            v_xy_nm_per_s = nhw.get_v_xy_nm_per_s()

            # Session path
            session_path = nhw.get_path()
            
            parameters = gains_dict | speed_dict | {
                "dict_name": "scan_parameters",
                "V_nanonis (V)": V,
                "I_fb (pA)": I_fb_pA,
                "v_xy (nm/s)": v_xy_nm_per_s,
                "session_path": session_path
            }
            
            self.parameters.emit(parameters)

        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (parameters, error)

    def frame_update(self, parameters: dict ={}, auto_disconnect: bool = False) -> tuple[dict, bool | str]:
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
            self.message.emit(f"frame_update({{parameters = {parameters}}})", "code")
            if not self.status == "running": self.connect()

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
            if angle_deg: new_parameters.update({"angle (deg)": angle_deg})

            frame = nhw.get_scan_frame_nm()
            if len(new_parameters) > 0:
                frame.update(new_parameters)
                nhw.set_scan_frame_nm(frame)

            frame.update({"dict_name": "frame"})
            self.parameters.emit(frame)
        
        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (frame, error)

    def grid_update(self, parameters: dict = {}, auto_disconnect: bool = False) -> tuple[dict, bool | str]:
        """
        Function to get and set grid properties
        """
        # Initalize outputs
        grid = None
        error = False
        nhw = self.nanonis_hardware

        try:
            self.message.emit(f"grid_update({{parameters = {parameters}}})", "code")
            # Get the frame and buffer
            if not self.status == "running": self.connect()
            frame = nhw.get_scan_frame_nm()
            buffer = nhw.get_scan_buffer()

            # Save the data to a dictionary
            width = frame.get("width (nm)")
            height = frame.get("height (nm)")
            angle = frame.get("angle (deg)")
            pixels = buffer.get("pixels")
            lines = buffer.get("lines")
            grid = frame | buffer | {
                "pixel_width (nm)": width / pixels,
                "pixel_height (nm)": height / lines,
                "dict_name": "grid"
            }

        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

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

            for i in range(pixels):
                for j in range(lines):
                    x_grid[i, j] = x_grid_local[i, j] * cos + y_grid_local[i, j] * sin
                    y_grid[i, j] = y_grid_local[i, j] * cos - x_grid_local[i, j] * sin

            # Apply a translation
            x_grid += grid["x (nm)"]
            y_grid += grid["y (nm)"]

            # Add the meshgrids to the grid dictionary
            grid["x_grid"] = x_grid
            grid["y_grid"] = y_grid

            # Add vertex information
            frame_vertices = np.asarray([[x_grid[0, 0], y_grid[0, 0]], [x_grid[-1, 0], y_grid[-1, 0]], [x_grid[-1, -1], y_grid[-1, -1]], [x_grid[0, -1], y_grid[0, -1]]])
            bottom_left_corner = frame_vertices[0]
            top_left_corner = frame_vertices[1]
            grid["vertices"] = frame_vertices
            grid["bottom_left_corner"] = bottom_left_corner
            grid["top_left_corner"] = top_left_corner
            
            self.parameters.emit(grid)
        
        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (grid, error)

    def scan_metadata_update(self, auto_disconnect: bool = False) -> tuple[dict | str]:
        """
        get_scan_metadata gets data regarding the properties of the current scan frame, such as the names of the recorded channels and the save properties
        """
        # Initalize outputs
        scan_metadata = None
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get grid dat
        try:
            self.message.emit(f"scan_metadata_update()", "code")
            
            if not self.status == "running": self.connect()
            props = nhw.get_scan_props()
            buffer = nhw.get_scan_buffer() # The buffer has the number of channels, indices of these channels, and pixels and lines
            channel_indices = buffer["channel_indices"]

            if nhw.version > 14000: #Newer versions of Nanonis work with signals in slots, meaning that a small subset of the total of 128 channels is put into numbered 'slots', which are available for data acquisition
                sig_in_slots = nhw.get_signals_in_slots()
                signal_names = sig_in_slots["names"]
                signal_indices = sig_in_slots["indices"]
            
                # Find out the names of the channels being recorded and their corresponding indices
                channel_dict = {signal_names[index]: index for index in channel_indices}

            else:
                signal_names = nhw.get_signal_names()
            
            signal_dict = {signal_names[index]: index for index in range(len(signal_names))} # Signal_dict is a dict of all signals and their corresponding indices
            channel_dict = {signal_names[index]: index for index in buffer.get("channel_indices")} # Channel_dict is the subset of signals that are actively recorded in the scan

            scan_metadata = props | {
                "channel_dict": channel_dict,
                "signal_dict": signal_dict,
                "dict_name": "scan_metadata"
                }
            
            self.parameters.emit(scan_metadata)

        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (scan_metadata, error)

    def bias_update(self, parameters: dict = {}, auto_disconnect: bool = False) -> float | bool:
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware
        
        # Extract parameters from the dictionary
        V = parameters.get("V_nanonis (V)", None)
        dt = parameters.get("dt", .005)
        dV = parameters.get("dV", .01)
        dz_nm = parameters.get("dz_nm", 1)
        V_limits = parameters.get("V_limits", 10)

        if type(V) != float and type(V) != int:
            return False
        if type(V_limits) == float or type(V_limits) == int:
            if np.abs(V) > np.abs(V_limits): # Bias outside of limits
                return False

        try:
            self.message.emit(f"bias_update({{parameters = {parameters}}})", "code")
            if not self.status == "running": self.connect()                            
            V_old = nhw.get_V() # Read data from Nanonis
            if np.abs(V - V_old) < dV: return V_old # If the bias is unchanged, don't slew it
            
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
            
            if auto_disconnect: self.disconnect()
            return V

        except Exception as e:
            error = e
            if auto_disconnect: self.disconnect()
            return error

    def lockin_update(self, parameters: dict = {}, auto_disconnect: bool = False) -> tuple[dict | str]:
        error = False
        nhw = self.nanonis_hardware

        lockin_parameters = {}

        self.logprint(f"nanonis.lockin_update({parameters})", message_type = "code")

        try:
            self.message.emit(f"lockin_update({{parameters = {parameters}}})", "code")
            if not self.status == "running": self.connect()
            mod1_dict = parameters.get("modulator_1", None)
            mod2_dict = parameters.get("modulator_2", None)

            for mod_number, mod in enumerate([mod1_dict, mod2_dict]):
                if isinstance(mod, dict):
                    mod_on = mod.get("on")
                    nhw.set_lockin(mod_number + 1, mod_on)
        
        except Exception as e:
            error = e
        finally:
            if auto_disconnect: self.disconnect()
        
        return (lockin_parameters, error)



    # Simple actions
    def tip_prep(self, parameters: dict = {}, auto_disconnect: bool = False) -> bool | str:
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware
        self.logprint(f"nanonis.tip_prep({parameters})", message_type = "code")

        try:
            self.message.emit(f"tip_prep({{parameters = {parameters}}})", "code")
            if not self.status == "running": self.connect()
            if parameters.get("action", "pulse") == "pulse":
                V_pulse_V = parameters.get("V_pulse (V)", 6)
                t_pulse_ms = parameters.get("t_pulse (ms)", 1000)
                nhw.pulse(V_pulse_V, t_pulse_ms)
            else:
                nhw.shape_tip()

        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return error

    def coarse_move(self, parameters: dict, auto_disconnect: bool = False) -> bool | str:
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware
        self.logprint(f"nanonis.coarse_move({parameters})", message_type = "code")

        motions = []
        V_hor = parameters.get("V_hor (V)")
        V_ver = parameters.get("V_ver (V)")
        f_motor = parameters.get("f_motor (Hz)")
        
        try:
            if not self.status == "running": self.connect()
            
            # 1. Withdraw
            withdraw = parameters.get("withdraw", True)
            if withdraw: self.tip_update({"withdraw": True}, auto_disconnect = False)

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
            if approach: self.auto_approach(True, V_motor = V_ver, auto_disconnect = False)

        except Exception as e:
            error = e
        finally:
            if auto_disconnect: self.disconnect()
        
        return error

    def auto_approach(self, status: bool = True, V_motor: float = None, auto_disconnect: bool = False) -> bool | str:
        """
        Function to turn on/off the auto approach feature of the Nanonis
        """
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware
        self.logprint(f"nanonis.auto_approach({status})", message_type = "code")
                
        try:
            if not self.status == "running": self.connect()
            if V_motor: nhw.set_motor_f_A({"V_motor (V)": V_motor})
            nhw.auto_approach(status)

        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return error

    def get_parameter_values(self, parameter_names, auto_disconnect: bool = False) -> tuple[dict, bool | str]:
        error = False
        nhw = self.nanonis_hardware
        parameter_values = {}

        # If only a single parameter_name is provided, turn it into a list
        if isinstance(parameter_names, str): parameter_names = [parameter_names]

        try:
            if not self.status == "running": self.connect()
            
            (scan_metadata, error) = self.scan_metadata_update(auto_disconnect = False)
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
        
        except Exception as e:
            error = f"Unable to retrieve the requested parameters. {e}"
        
        finally:
            if auto_disconnect: self.disconnect()
        
        return (parameter_values, error)



    # Idling
    def tip_tracker(self, timeout = 6000, auto_disconnect = False) -> None:
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
            if not self.status == "running": self.connect()
            
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
            if auto_disconnect: self.disconnect()
            return error    
        
        return



    # Does not work yet
    def get_spectrum(self, auto_disconnect: bool = True) -> tuple[dict | str]:
        # Initalize outputs
        data_dict = {}
        parameters = []
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get the frame
        try:
            if not self.status == "running": self.connect()
            spectrum = nhw.get_spectrum()
            #self.parameters.emit(frame)
        
        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (spectrum, error)




