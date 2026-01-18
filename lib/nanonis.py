import numpy as np
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
from .hw_nanonis import NanonisHardware, NanonisHardwareNew
from time import sleep, time
import pint



colors = {"red": "#ff5050", "dark_red": "#800000", "green": "#00ff00", "dark_green": "#005000", "lightblue": "#30d0ff",
          "white": "#ffffff", "blue": "#2090ff", "orange": "#FFA000","dark_orange": "#A05000", "black": "#000000", "purple": "#700080"}



class Nanonis(NanonisHardware):
    def __init__(self, hardware: dict):
        super().__init__(hardware = hardware)
        self.ureg = pint.UnitRegistry()
        self.nanonis_hardware = NanonisHardwareNew(hardware = hardware)

    def logprint(self, message: str, color: None):
        # Placeholder for callback function
        pass

    def tip(self, parameters: dict = {}) -> tuple[dict, bool | str]:
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

        # Set up the TCP connection and set/get
        try:
            nhw.connect()
            z_nm = nhw.get_z_nm()
            [z_min, z_max] = nhw.get_z_limits_nm()

            # Switch the feedback if desired, and retrieve the feedback status
            if type(feedback) == bool: nhw.set_fb(False)
            
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
                #"height": z_pos,
                "z_nm": z_nm,
                #"limits": [z_min, z_max],
                "z_limits_nm": [z_min, z_max],
                "feedback": feedback_new,
                "withdrawn": withdrawn
            }

        except Exception as e: error = e
        finally: nhw.disconnect()

        return (tip_status, error)

    def parameters(self, parameters: dict = {}) -> tuple[dict, bool | str]:
        """
        Function to get and set parameters from Nanonis
        """
        # Initalize outputs
        parameters = None
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get
        try:
            nhw.connect()
            V = nhw.get_V()
            I_fb_pA = nhw.get_I_fb_pA()
            gains_dict = nhw.get_gains()
            speed_dict = nhw.get_v_scan_nm_per_s()
            v_xy_nm_per_s = nhw.get_v_xy_nm_per_s()
            session_path = nhw.get_path()

            parameters = gains_dict | speed_dict | {
                "V_nanonis": V,
                "bias_V": V,
                "I_fb_pA": I_fb_pA,
                "v_xy_nm_per_s": v_xy_nm_per_s,
                "session_path": session_path
            }

        except Exception as e: error = e
        finally: nhw.disconnect()

        return (parameters, error)

    def frame(self, parameters: dict ={}) -> tuple[dict, bool | str]:
        """
        Function to get and set frame
        """
        # Initalize outputs
        frame = None
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get the frame
        try:
            nhw.connect()
            frame = nhw.get_scan_frame_nm()
        
        except Exception as e: error = e
        finally: nhw.disconnect()

        return (frame, error)

    def grid(self, parameters: dict = {}) -> tuple[dict, bool | str]:
        """
        Function to get and set grid properties
        """
        # Initalize outputs
        grid = None
        error = False
        nhw = self.nanonis_hardware

        try:
            # Get the frame and buffer
            nhw.connect()
            frame = nhw.get_scan_frame_nm()
            buffer = nhw.get_scan_buffer()

            # Save the data to a dictionary
            width = frame.get("width_nm")
            height = frame.get("height_nm")
            angle = frame.get("angle_deg")
            pixels = buffer.get("pixels")
            lines = buffer.get("lines")
            grid = frame | buffer | {
                "pixel_width": width / pixels,
                "pixel_height": height / lines
            }

        except Exception as e: error = e
        finally: nhw.disconnect()

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
            x_grid += grid["x_nm"]
            y_grid += grid["y_nm"]

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
        
        return (frame, error)

    def scan_metadata(self, parameters: dict = {}) -> tuple[dict | str]:
        """
        get_scan_metadata gets data regarding the properties of the current scan frame, such as the names of the recorded channels and the save properties
        """
        # Initalize outputs
        scan_metadata = None
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get grid dat
        try:
            nhw.connect()
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
        finally: nhw.disconnect()

        return (scan_metadata, error)

    def bias(self, parameters: dict = {}) -> float:
        # Initalize outputs
        error = False
        nhw = self.nanonis_hardware

        # Set default parameters
        standard_parameters = {"V": None, "dt": .005, "dV": .01, "dz_nm": 1, "V_limits": 10}
        standard_parameters.update(parameters)
        
        # Extract parameters from the dictionary
        V = parameters["V"]
        dt = parameters["dt"]
        dV = parameters["dV"]
        dz_nm = parameters["dz_nm"]
        V_limits = parameters["V_limits"]

        if type(V) != float and type(V) != int:
            return False
        if type(V_limits) == float or type(V_limits) == int:
            if np.abs(V) > np.abs(V_limits): # Bias outside of limits
                return False

        try:
            nhw.connect()                            
            V_old = self.get_V() # Read data from Nanonis
            if np.abs(V - V_old) < dV: return (standard_parameters, error) # If the bias is unchanged, don't slew it
            
            feedback = nhw.get_fb()
            tip_height = self.get_z_nm()
            polarity_difference = np.sign(V) * np.sign(V_old) < 0 # True if the sign changes
            
            if V > V_old: delta_V = dV # Change the sign of deltaV to get the arange right
            else: delta_V = -dV
            slew = np.arange(V_old, V, delta_V)

            if bool(feedback) and bool(polarity_difference): # If the bias polarity is switched, switch off the feedback and lift the tip by dz for safety
                nhw.set_fb(False)
                sleep(.1) # If the tip height is set too quickly, the controller won't be off yet
                nhw.set_z_nm(tip_height + dz_nm)

            for V_t in slew: # Perform the slew to the new bias voltage
                self.set_V(V_t)
                sleep(dt)
            self.set_V(V) # Final bias value
        
            if bool(feedback) and bool(polarity_difference):
                self.set_feedback(True) # Turn the feedback back on

        except Exception as e: error = e
        finally: nhw.disconnect()

        return (standard_parameters, error)

    def feedback(self, parameters: dict = {}):
        error_flag = False
        
        {"I_fb": None, "p_gain": None, "t_const": None}

        if type(I) == int or type(I) == float:
            if np.abs(I) > 1E-3: I *= 1E-12

        try:
            self.connect()
            I_old = self.get_setpoint()
            if type(I) == int or type(I) == float: self.set_setpoint(I)
        except Exception as e:
            self.logprint(f"{e}", color = "red")
            error_flag = True
        finally:
            sleep(.1)

        if error_flag: return False
        else: return I_old

    def get_scan(self, channel_index, backward: bool = False) -> np.ndarray:
        # Initalize outputs
        scan_data = None
        error = False
        nhw = self.nanonis_hardware

        # Set up the TCP connection and get grid dat
        try:
            nhw.connect()
            scan_data = nhw.get_scan_data(channel_index, backward)
            #frame_data = self.scan.FrameDataGrab(channel_index = channel_index, data_direction = direction)
            scan_image = scan_data["scan_data"]

        except Exception as e: error = e
        finally: nhw.disconnect()

        return (scan_image, error)

    def scan_control(self, action: str = "stop", direction: str = "down", verbose: bool = True, monitor: bool = False):
        error_flag = False

        try:
            self.connect()
            
            dirxn = "up"
            if direction == "down": dirxn = "down"
            match action:
                case "start":
                    #print(f"  nanonis_functions.start_scan({dirxn})", color = "blue")
                    self.start_scan(dirxn)
                case "pause":
                    #print(f"  nanonis_functions.pause_scan()", color = "blue")
                    self.pause_scan()
                case "resume":
                    #print(f"  nanonis_functions.resume_scan()", color = "blue")
                    self.resume_scan()
                case "stop":
                    #print(f"  nanonis_functions.stop_scan()", color = "blue")
                    self.stop_scan()
                case _:
                    pass
        except Exception as e:
            #self.logprint(f"{e}", color = "red")
            pass
        finally:
            self.disconnect()
            sleep(.1)
        
        return
