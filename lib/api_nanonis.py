import numpy as np
from PyQt6 import QtCore, QtGui, QtWidgets
from .hw_nanonis import NanonisHardware
from .data_processing import DataProcessing
from time import sleep, time
import pint



colors = {"red": "#ff5050", "dark_red": "#800000", "green": "#00ff00", "dark_green": "#005000", "lightblue": "#30d0ff",
          "white": "#ffffff", "blue": "#2090ff", "orange": "#FFA000","dark_orange": "#A05000", "black": "#000000", "purple": "#700080"}



class NanonisAPI(QtCore.QObject):
    connection = QtCore.pyqtSignal(str)
    progress = QtCore.pyqtSignal(int)
    message = QtCore.pyqtSignal(str, str)
    parameters = QtCore.pyqtSignal(dict)
    image = QtCore.pyqtSignal(np.ndarray)
    
    def __init__(self, hardware: dict):
        super().__init__()
        self.ureg = pint.UnitRegistry()
        self.nanonis_hardware = NanonisHardware(hardware = hardware)
        self.data = DataProcessing()
        self.status = "idle"

    def connect(self) -> None:
        nhw = self.nanonis_hardware
        if self.status == "running": self.disconnect()
        self.status = "running"
        self.connection.emit(self.status)
        nhw.connect()
    
    def disconnect(self) -> None:
        nhw = self.nanonis_hardware
        nhw.disconnect()
        self.status = "idle"
        self.connection.emit(self.status)

    def test_function(self) -> None:
        scan_image = np.random.rand(256, 256) * 10
        self.image.emit(np.flipud(scan_image))
        return

    def start_timed_updates(self) -> None:
        self.timer = QtCore.QTimer(self) # Timer for regular updates
        self.timer.timeout.connect(self.scan_update)
        self.timer.start(5000)
        return

    def stop_timed_updates(self) -> None:
        if hasattr(self, "timer"):
            self.timer.timeout.disconnect(self.scan_update)
            self.timer.deleteLater()
            delattr(self, "timer")
        return

    def send_tip_update(self) -> None:
        self.tip_update()
        return

    def get_window(self, auto_connect: bool = True, auto_disconnect: bool = True) -> None:
        error = False
        nhw = self.nanonis_hardware
        window_dict = {}

        try:
            if auto_connect: self.connect()
            piezo_range = nhw.get_range_nm()
            
            window_dict = {"dict_name": "window",
                "x_min (nm)": -0.5 * piezo_range[0], "x_max (nm)": 0.5 * piezo_range[0],
                "y_min (nm)": -0.5 * piezo_range[1], "y_max (nm)": 0.5 * piezo_range[1],
                "z_min (nm)": -0.5 * piezo_range[2], "z_max (nm)": 0.5 * piezo_range[2],
                "x_range (nm)": piezo_range[0], "y_range (nm)": piezo_range[1], "z_range (nm)": piezo_range[2]
            }
            self.parameters.emit(window_dict)
                
        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (window_dict, error)



    def auto_approach(self, status: bool = True, auto_connect: bool = True, auto_disconnect: bool = True) -> bool | str:
        """
        Function to turn on/off the auto approach feature of the Nanonis
        """
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware
                
        try:
            if auto_connect: self.connect()
            nhw.auto_approach(status)

        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return error



    def tip_update(self, parameters: dict = {}, auto_connect: bool = True, auto_disconnect: bool = True) -> tuple[dict, bool | str]:
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
            if auto_connect: self.connect()
            
            if xy_nm: nhw.set_xy_nm(xy_nm) # Set the tip position
            else: xy_nm = nhw.get_xy_nm() # Get the tip position
            [x_nm, y_nm] = xy_nm
            z_nm = nhw.get_z_nm()
            z_bs = nhw.get_z()
            [z_min, z_max] = nhw.get_z_limits_nm()

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

    def parameters_update(self, parameters: dict = {}, auto_connect: bool = True, auto_disconnect: bool = True) -> tuple[dict, bool | str]:
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
        V_nanonis = parameters.get("V_nanonis (V)", None)

        # Set up the TCP connection and get
        try:
            if auto_connect: self.connect()
            
            if V_nanonis: V = self.bias_update({"V_nanonis (V)": V_nanonis}, auto_connect = False, auto_disconnect = False)
            else: V = nhw.get_V()
            
            if I_fb_pA: nhw.set_I_fb_pA(I_fb_pA)
            else: I_fb_pA = nhw.get_I_fb_pA()
            
            gains_dict = nhw.get_gains()
            speed_dict = nhw.get_v_scan_nm_per_s()
            v_xy_nm_per_s = nhw.get_v_xy_nm_per_s()
            session_path = nhw.get_path()
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

    def frame_update(self, parameters: dict ={}, auto_connect: bool = True, auto_disconnect: bool = True) -> tuple[dict, bool | str]:
        """
        Function to get and set frame
        """
        # Initalize outputs
        frame = None
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get the frame
        try:
            if auto_connect: self.connect()
            frame = nhw.get_scan_frame_nm()
            
            frame.update({"dict_name": "frame"})
            self.parameters.emit(frame)
        
        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (frame, error)

    def grid_update(self, parameters: dict = {}, auto_connect: bool = True, auto_disconnect: bool = True) -> tuple[dict, bool | str]:
        """
        Function to get and set grid properties
        """
        # Initalize outputs
        grid = None
        error = False
        nhw = self.nanonis_hardware

        try:
            # Get the frame and buffer
            if auto_connect: self.connect()
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
                "pixel_height (nm)": height / lines
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
        
        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (grid, error)

    def scan_metadata_update(self, parameters: dict = {}, auto_connect: bool = True, auto_disconnect: bool = True) -> tuple[dict | str]:
        """
        get_scan_metadata gets data regarding the properties of the current scan frame, such as the names of the recorded channels and the save properties
        """
        # Initalize outputs
        scan_metadata = None
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get grid dat
        try:
            if auto_connect: self.connect()
            sig_in_slots = nhw.get_signals_in_slots()
            props = nhw.get_scan_props()
            buffer = nhw.get_scan_buffer()
            
            signal_names = sig_in_slots["names"]
            signal_indices = sig_in_slots["indices"]            
            channel_indices = buffer["channel_indices"]
            
            # Find out the names of the channels being recorded and their corresponding indices
            
            recorded_channels = {}
            for channel_index in channel_indices:
                channel_name = signal_names[channel_index]
                recorded_channels.update({str(channel_index): channel_name})
                        
            scan_metadata = props | {
                "signal_names": signal_names,
                "signal_indices": signal_indices,
                "recorded_channels": recorded_channels
                }

        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (scan_metadata, error)

    def bias_update(self, parameters: dict = {}, auto_connect: bool = True, auto_disconnect: bool = True) -> float | bool:
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
            if auto_connect: self.connect()                            
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

    def tip_prep(self, parameters: dict = {}, auto_connect: bool = True, auto_disconnect: bool = True) -> bool | str:
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware

        try:
            if auto_connect: self.connect()
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

    def get_spectrum(self, auto_connect: bool = True, auto_disconnect: bool = True) -> tuple[dict | str]:
        # Initalize outputs
        data_dict = {}
        parameters = []
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get the frame
        try:
            if auto_connect: self.connect()
            spectrum = nhw.get_spectrum()
            #self.parameters.emit(frame)
        
        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return (spectrum, error)



    # Work in progress
    def feedback(self, parameters: dict = {}, auto_connect: bool = True, auto_disconnect: bool = True):
        error_flag = False
        
        {"I_fb": None, "p_gain": None, "t_const": None}

        if type(I) == int or type(I) == float:
            if np.abs(I) > 1E-3: I *= 1E-12

        try:
            if auto_connect: self.connect()
            I_old = self.get_setpoint()
            if type(I) == int or type(I) == float: self.set_setpoint(I)
        except Exception as e:
            self.logprint(f"{e}", color = "red")
            error_flag = True
        finally:
            sleep(.1)

        if error_flag: return False
        else: return I_old

    def scan_update(self, channel_index, backward: bool = False, auto_connect: bool = True, auto_disconnect: bool = True) -> np.ndarray:
        # Initalize outputs
        scan_data = None
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get grid dat
        try:
            if auto_connect: nhw.connect()
            self.frame_update(auto_connect = False, auto_disconnect = False)
            self.tip_update(auto_connect = False, auto_disconnect = False)
            scan_data = nhw.get_scan_data(channel_index, backward)
            scan_image = scan_data["scan_data"]
            
            number_of_elements = scan_image.size
            number_of_nans = np.sum(np.isnan(scan_image))
            completed_percentage = int(100 - 100 * (number_of_nans / number_of_elements))
            self.progress.emit(completed_percentage)
            
            if number_of_elements - number_of_nans < 2: return # Do not perform data processing if the scan is all NaNs
            
            #(processed_image, error) = self.data.subtract_background(scan_image)
            
            self.image.emit(np.flipud(scan_image))

        except Exception as e: error = e
        finally:
            if auto_disconnect: nhw.disconnect()

        return (scan_image, error)

    def scan_control(self, parameters: dict = {}, auto_connect: bool = True, auto_disconnect: bool = True) -> bool | str:
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware
        
        action = parameters.get("action", "pause")
        direction = parameters.get("direction", "down")
        
        # Set up the TCP connection and get grid dat
        try:
            if auto_connect: self.connect()
            
            dirxn = "up"
            if direction == "down": dirxn = "down"
            match action:
                case "start":
                    self.progress.emit(0)
                    nhw.start_scan(dirxn)
                case "pause": nhw.pause_scan()
                case "resume": nhw.resume_scan()
                case "stop": nhw.stop_scan()
                case _: pass
        
        except Exception as e: error = e
        finally:
            if auto_disconnect: self.disconnect()

        return error


