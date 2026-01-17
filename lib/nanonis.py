import numpy as np
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
from .hw_nanonis import NanonisHardware
from time import sleep
from datetime import datetime
from time import sleep, time
import pint



colors = {"red": "#ff5050", "dark_red": "#800000", "green": "#00ff00", "dark_green": "#005000", "lightblue": "#30d0ff",
          "white": "#ffffff", "blue": "#2090ff", "orange": "#FFA000","dark_orange": "#A05000", "black": "#000000", "purple": "#700080"}



class Nanonis(NanonisHardware):
    def __init__(self, hardware: dict):
        super().__init__(hardware = hardware)
        self.ureg = pint.UnitRegistry()

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
        
        # Extract parameters from the dictionary
        withdraw = parameters.get("withdraw", False)
        feedback = parameters.get("feedback", None)

        # Set up the TCP connection and set/get
        try:
            self.connect()
            z_pos = self.get_z()
            [z_max, z_min] = self.zcontroller.LimitsGet()

            # Switch the feedback if desired, and retrieve the feedback status
            if type(feedback) == bool: self.set_feedback(feedback)
            
            withdrawn = False # Initialize the withdrawn parameter, which tells whether the tip is withdrawn
            if not feedback and np.abs(z_pos - z_max) < 1E-11: # Tip is already withdrawn
                withdrawn = True
            if withdraw and not withdrawn: # Tip is not yet withdrawn, but a withdraw request is made
                self.zcontroller.Withdraw(wait_until_finished = True)
                withdrawn = True

            # Retrieve the feedback status
            sleep(.2)
            feedback_new = self.get_feedback()
            
            # Convert all length units to nm for consistency
            z_pos_unitized = self.ureg.Quantity(z_pos, "m")
            z_min_unitized = self.ureg.Quantity(z_min, "m")
            z_max_unitized = self.ureg.Quantity(z_max, "m")
            z_nm = z_pos_unitized.to("nm").magnitude
            z_min_nm = z_min_unitized.to("nm").magnitude
            z_max_nm = z_max_unitized.to("nm").magnitude

            # Set up a dictionary containing the actual tip status parameters
            tip_status = {
                "height": z_pos,
                "height_nm": z_nm,
                "limits": [z_min, z_max],
                "limits_nm": [z_min_nm, z_max_nm],
                "feedback": feedback_new,
                "withdrawn": withdrawn
            }

        except Exception as e: error = e

        return (tip_status, error)

    def parameters(self, parameters: dict = {}) -> tuple[dict, bool | str]:
        """
        Function to get and set parameters from Nanonis
        """
        # Initalize outputs
        parameters = None
        error = False

        # Set up the TCP connection and get
        try:
            self.connect()
            
            V = self.get_V()
            I_fb = self.get_setpoint()
            [p_gain, t_const, i_gain] = gains = self.get_gains()
            [v_fwd, v_bwd, t_fwd, t_bwd, lock_parameter, v_ratio] = self.scan.SpeedGet()
            v_move = self.get_speed()
            session_path = self.get_path()

            # Convert units
            V_unitized = self.ureg.Quantity(V, "V")
            V_V = V_unitized.to("V").magnitude
            I_fb_unitized = self.ureg.Quantity(I_fb, "A")
            I_fb_pA = I_fb_unitized.to("pA").magnitude
            p_gain_unitized = self.ureg.Quantity(p_gain, "m")
            p_gain_pm = p_gain_unitized.to("pm").magnitude
            t_const_unitized = self.ureg.Quantity(t_const, "s")
            t_const_us = t_const_unitized.to("us").magnitude
            i_gain_unitized = self.ureg.Quantity(i_gain, "m/s")
            i_gain_nm_per_s = i_gain_unitized.to("nm/s").magnitude
            v_fwd_unitized = self.ureg.Quantity(v_fwd, "m/s")
            v_fwd_nm_per_s = v_fwd_unitized.to("nm/s").magnitude
            v_bwd_unitized = self.ureg.Quantity(v_bwd, "m/s")
            v_bwd_nm_per_s = v_bwd_unitized.to("nm/s").magnitude
            v_move_unitized = self.ureg.Quantity(v_move[0], "m/s")
            v_move_nm_per_s = v_move_unitized.to("nm/s").magnitude

            parameters = {
                "V_nanonis": V,
                "V_V": V_V,
                "bias": V,
                "gains": gains,
                "I_fb": I_fb,
                "p_gain": p_gain,
                "t_const": t_const,
                "i_gain": i_gain,
                "v_fwd": v_fwd,
                "v_bwd": v_bwd,
                "t_fwd": t_fwd,
                "t_bwd": t_bwd,
                "v_ratio": v_ratio,
                "v_move": v_move,
                "v_move_nm_per_s": v_move_nm_per_s,
                "I_fb_pA": I_fb_pA,
                "p_gain_pm": p_gain_pm,
                "t_const_us": t_const_us,
                "i_gain_nm_per_s": i_gain_nm_per_s,
                "session_path": session_path
            }

        except Exception as e: error = e

        return (parameters, error)

    def frame(self, parameters: dict ={}) -> tuple[dict, bool | str]:
        """
        Function to get and set frame
        """
        # Initalize outputs
        frame = None
        error = False

        # Set up the TCP connection and get
        try:
            self.connect()
            frame_data = self.scan.FrameGet()

            # Save the data to a dictionary
            frame = {
                "x": frame_data[0],
                "y": frame_data[1],
                "center": [frame_data[0], frame_data[1]],
                "offset": [frame_data[0], frame_data[1]],
                "width": frame_data[2],
                "height": frame_data[3],
                "size": [frame_data[2], frame_data[3]],
                "scan_range": [frame_data[2], frame_data[3]],
                "angle": frame_data[4],
                "aspect_ratio": frame_data[3] / frame_data[2]
            }
        
        except Exception as e: error = e

        return (frame, error)

    def grid(self, parameters: dict = {}) -> tuple[dict, bool | str]:
        """
        Function to get and set grid properties
        frame() is called internally in order to get the frame properties necessary fo calculating the size and aspect ratio of the grid
        """
        # Initalize outputs
        grid = None
        error = False

        # Call get_frame to get the frame data
        try:
            (frame, error) = self.frame()
            if error: raise

            # Set up the TCP connection and get grid data
            self.connect()
            buffer_data = self.scan.BufferGet()

            # Save the data to a dictionary
            width = frame.get("width")
            height = frame.get("height")
            
            grid = frame | {
                "pixels": [buffer_data[2], buffer_data[3]],
                "pixel_width": width / buffer_data[2],
                "pixel_height": height / buffer_data[3],
                "pixel_ratio": buffer_data[3] / buffer_data[2],
                "num_channels": buffer_data[0],
                "channel_indices": buffer_data[1]                
            }
            
        except Exception as e: error = e

        if error: return (grid, error)
        
        # Append the grid data with calculated information
        try:
            # Construct a local grid with the same size as the Nanonis grid, with center is at (0, 0)
            x_coords_local = np.linspace(- grid["width"] / 2, grid["width"] / 2, grid["pixels"][0])
            y_coords_local = np.linspace(- grid["height"] / 2, grid["height"] / 2, grid["pixels"][1])
            x_grid_local, y_grid_local = np.meshgrid(x_coords_local, y_coords_local)

            # Apply a rotation
            cos = np.cos(np.deg2rad(grid["angle"]))
            sin = np.sin(np.deg2rad(grid["angle"]))
            x_grid = np.zeros_like(x_grid_local)
            y_grid = np.zeros_like(y_grid_local)

            for i in range(grid["pixels"][0]):
                for j in range(grid["pixels"][1]):
                    x_grid[i, j] = x_grid_local[i, j] * cos + y_grid_local[i, j] * sin
                    y_grid[i, j] = y_grid_local[i, j] * cos - x_grid_local[i, j] * sin

            # Apply a translation
            x_grid += grid["x"]
            y_grid += grid["y"]

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

        # Set up the TCP connection and get grid dat
        try:
            self.connect()
            #[signal_names, signal_indices] = self.signals.InSlotsGet() # signals.InSlotsGet() is not working on Hermes for some reason
            scan_props = self.scan.PropsGet()
            buffer_data = self.scan.BufferGet()
            auto_save = bool(scan_props[1])
            channel_indices = buffer_data[1] # The indices of the Nanonis signals being recorded in the scan
            
            # Find out the names of the channels being recorded and their corresponding indices
            channel_names = []
            #for channel_index in channel_indices:
            #    channel_name = signal_names[channel_index]
            #    channel_names.append(channel_name)
            
            scan_metadata = {
                #"signal_names": signal_names,
                #"signal_indices": signal_indices,
                "channel_names": channel_names,
                "channel_indices": channel_indices,
                "auto_save": auto_save
                }

        except Exception as e: error = e

        return (scan_metadata, error)

    def bias(self, parameters: dict = {}) -> float:
        error_flag = False

        # Set default parameters
        standard_parameters = {"V": None, "dt": .005, "dV": .01, "dz": 1E-9, "V_limits": 10}
        standard_parameters.update(parameters)
        
        # Extract parameters from the dictionary
        V = parameters["V"]
        dt = parameters["dt"]
        dV = parameters["dV"]
        dz = parameters["dz"]
        V_limits = parameters["V_limits"]

        if type(V) != float and type(V) != int:
            #print("Wrong bias supplied", color = colors["red"])
            return False
        if type(V_limits) == float or type(V_limits) == int:
            if np.abs(V) > np.abs(V_limits):
                #print("Bias outside of limits")
                return False

        try:
            self.connect()
                            
            V_old = self.get_V() # Read data from Nanonis
            if np.abs(V - V_old) < dV: return V_old # If the bias is unchanged, don't slew it
            
            feedback = self.get_feedback()
            tip_height = self.get_z()
            polarity_difference = np.sign(V) * np.sign(V_old) < 0 # True if the sign changes
            
            if V > V_old: delta_V = dV
            else: delta_V = -dV
            slew = np.arange(V_old, V, delta_V)

            if bool(feedback) and bool(polarity_difference): # If the bias polarity is switched, switch off the feedback and lift the tip by dz for safety
                self.set_feedback(False)
                sleep(.1) # If the tip height is set too quickly, the controller won't be off yet
                self.set_z(tip_height + dz)

            for V_t in slew: # Perform the slew to the new bias voltage
                self.set_V(V_t)
                sleep(dt)
            self.set_V(V) # Final bias value
        
            if bool(feedback) and bool(polarity_difference):
                self.set_feedback(True) # Turn the feedback back on

        except Exception as e:
            error_flag = True
        finally:
            sleep(.1)

        if error_flag: return False
        else: return V_old

    def change_feedback(self, I_fb = None, p_gain = None, t_const = None):
        error_flag = False

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

    def get_scan(self, channel_index, direction):
        """
        get_scan is an appended version of get_grid.
        get_grid already gets data regarding the properties of the current scan frame
        To get the names of the recorded channels and the save properties, the grid dictionary is appended
        """
        error_flag = False
        
        # Set up the TCP connection to Nanonis and read the frame and buffer, then disconnect
        try:
            self.connect()
            frame_data = self.scan.FrameDataGrab(channel_index = channel_index, data_direction = direction)
            scan_frame = frame_data[1]

        except Exception as e:
            #print(f"{e}", color = "red")
            error_flag = True
        finally:
            self.disconnect()
            sleep(.1)

        if error_flag:
            return False
        else:
            return scan_frame

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
