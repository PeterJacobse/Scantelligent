import html
import numpy as np
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
from .hw_nanonis import NanonisHardware
from time import sleep
from datetime import datetime
from time import sleep, time
import cv2

colors = {"red": "#ff6060", "dark_red": "#800000", "green": "#00e000", "dark_green": "#005000",
          "white": "#ffffff", "blue": "#20a0ff", "dark_orange": "#A05000", "black": "#000000", "purple": "#700080"}



class Nanonis(NanonisHardware):
    def __init__(self, hardware: dict):
        super().__init__(hardware = hardware)

    def logprint(self, message: str, color: None):
        # Placeholder for callback function
        pass

    def get_grid(self, verbose: bool = True, callback = logprint):
        error_flag = False
        if hasattr(self, "NTCP"):
            callback("Error. Existing TCP connection found. Aborting.", color = "red")
            return False
        
        if verbose: callback("  [dict] grid = nanonis_functions.get_grid()", color = "blue")

        # Set up the TCP connection to Nanonis and read the frame and buffer, then disconnect
        try:
            self.connect()
            grid_data = self.scan.FrameGet()
            buffer_data = self.scan.BufferGet()
        except Exception as e:
            self.logprint(f"{e}", color = "red")
            error_flag = True
        finally:
            self.disconnect()
            sleep(.1)
        
        if error_flag:
            return False

        # Save the data to a dictionary
        grid = {
            "x": grid_data[0],
            "y": grid_data[1],
            "center": [grid_data[0], grid_data[1]],
            "width": grid_data[2],
            "height": grid_data[3],
            "size": [grid_data[2], grid_data[3]],
            "angle": grid_data[4],
            "pixels": [buffer_data[2], buffer_data[3]],
            "aspect_ratio": grid_data[3] / grid_data[2],
            "pixel_width": grid_data[2] / buffer_data[2],
            "pixel_height": grid_data[3] / buffer_data[3],
            "pixel_ratio": buffer_data[3] / buffer_data[2],
            "num_channels": buffer_data[0],
            "channel_indices": buffer_data[1]
        }

        if np.abs(grid["aspect_ratio"] - grid["pixel_ratio"]) > 0.001 and verbose:
            self.logprint("Warning! The aspect ratio of the scan frame does not correspond to that of the pixels. This will result in rectangular pixels!", color = "red")

        # Construct a local grid with the same size as the Nanonis grid, whose center is at (0, 0)
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
        
        if verbose: self.logprint(f"  grid.keys() = {grid.keys()}", color = "blue")

        return grid

    def tip(self, withdraw: bool = False, feedback = None, callback = logprint):
        error_flag = False
        if hasattr(self, "NTCP"):
            callback("Error. Existing TCP connection found. Aborting.", message_type = "error")
            return False
        callback("Test", message_type = "code")
        # Set up the TCP connection to Nanonis and read the frame and buffer, then disconnect
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
            
            # Set up a dictionary containing the actual tip status parameters
            tip_status = {
                "height": z_pos,
                "limits": [z_min, z_max],
                "feedback": feedback_new,
                "withdrawn": withdrawn
            }

        except Exception as e:
            error_flag = True
            #print(f"{e}", color = "red")
        finally:
            self.disconnect()
            sleep(.1)
            
        if error_flag:
            return False
        else:
            return tip_status

    def get_parameters(self):
        error_flag = False
        if hasattr(self, "NTCP"):
            #print("Error. Existing TCP connection found. Aborting.", color = "red")
            return False
        
        # Set up the TCP connection to Nanonis and read the frame and buffer, then disconnect
        try:
            self.connect()
            
            V = self.get_V()
            I_fb = self.get_setpoint()
            [p_gain, t_const, i_gain] = gains = self.get_gains()
            [v_fwd, v_bwd, t_fwd, t_bwd, lock_parameter, v_ratio] = self.scan.SpeedGet()
            v_move = self.get_speed()
            session_path = self.get_path()

            parameters = {
                "bias": V,
                "gains": gains,
                "I_fb": I_fb,
                "p_gain": p_gain,
                "t_const": t_const,
                "i_gain": i_gain,
                #"v_fwd": v_fwd,
                #"v_bwd": v_bwd,
                #"t_fwd": t_fwd,
                #"t_bwd": t_bwd,
                #"v_ratio": v_ratio,
                "v_move": v_move,
                "session_path": session_path
            }

        except Exception as e:
            #print(f"{e}", color = "red")
            error_flag = True
        finally:
            self.disconnect()
            sleep(.1)

        if error_flag:
            return False
        else:
            return parameters

    def change_bias(self, V = None, dt: float = .01, dV: float = .02, dz: float = 1E-9, V_limits = 10):
        error_flag = False

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
            feedback = self.get_feedback()
            tip_height = self.get_z()
            polarity_difference = np.sign(V) * np.sign(V_old) < 0 # Calculate the polarity and voltage slew values
            
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
            #print(f"{e}", color = "red")
            error_flag = True
        finally:
            self.disconnect()
            sleep(.1)

        if error_flag:
            return False
        else:
            return V_old

    def change_feedback(self, I = None, p_gain = None, t_const = None):
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
            self.disconnect()
            sleep(.1)

        if error_flag:
            return False
        else:
            return I_old

    def get_frame(self):
        """
        get_scan_data is an appended version of get_grid.
        get_grid already gets data regarding the properties of the current scan frame
        To get the names of the recorded channels and the save properties, the grid dictionary is appended
        """
        error_flag = False
        
        # Set up the TCP connection to Nanonis and read the frame and buffer, then disconnect
        try:
            grid = self.get_grid(verbose = False)
            channel_indices = grid.get("channel_indices") # The indices of the Nanonis signals being recorded in the scan
            self.connect()
            [signal_names, signal_indices] = self.signals.InSlotsGet()
            scan_props = self.scan.PropsGet()
            auto_save = bool(scan_props[1])
            
            channel_names = []
            for channel_index in channel_indices:
                channel_name = signal_names[channel_index]
                channel_names.append(channel_name)
            
            frame = grid | {
                "signal_names": signal_names,
                "signal_indices": signal_indices,
                "channel_names": channel_names,
                "channel_indices": channel_indices,
                "auto_save": auto_save
                }

        except Exception as e:
            #print(f"{e}", color = "red")
            error_flag = True
        finally:
            self.disconnect()
            sleep(.1)

        if error_flag:
            return False
        else:
            return frame

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