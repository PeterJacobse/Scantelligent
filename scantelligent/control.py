import os
import sys
import numpy as np
import matplotlib.pyplot as plt
from numpy import sqrt
from PyQt6.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot
from nanonisTCP import nanonisTCP
from nanonisTCP.ZController import ZController
from nanonisTCP.Motor import Motor
from nanonisTCP.AutoApproach import AutoApproach
from nanonisTCP.Scan import Scan
from nanonisTCP.Current import Current
from nanonisTCP.LockIn import LockIn
from nanonisTCP.Bias import Bias
from nanonisTCP.Signals import Signals
from nanonisTCP.Util import Util
from nanonisTCP.FolMe import FolMe
from nanonisTCP.BiasSpectr import BiasSpectr
from nanonisTCP.TipShaper import TipShaper
from time import sleep
from types import SimpleNamespace
from scipy.interpolate import Rbf
from datetime import datetime
from time import sleep, time
import traceback

# Establish a TCP/IP connection
#TCP_IP = "192.168.236.1"                           # Local host
TCP_IP = "127.0.0.1"
TCP_PORT = 6501                                    # Check available ports in NANONIS > File > Settings Options > TCP Programming Interface
version_number = 13520



class HelperFunctions:
    def __init__(self, tcp_ip, tcp_port, version_number):
        self.tcp_ip = tcp_ip
        self.tcp_port = tcp_port
        self.version_number = version_number

    def clean_lists(self, V_list, x_list, y_list, V_limit = 10, x_limit = 1E-7, y_limit = 1E-7):
        if type(V_list) == int or type(V_list) == float: V_list = [V_list]
        if type(x_list) == int or type(x_list) == float: x_list = [x_list]
        if type(y_list) == int or type(y_list) == float: y_list = [y_list]

        if type(V_list) == list: V_list = np.array(V_list, dtype = float)
        if type(x_list) == list: x_list = np.array(x_list, dtype = float)
        if type(y_list) == list: y_list = np.array(y_list, dtype = float)
        
        if type(V_list) == np.ndarray:
            n_V = len(V_list)
        else:
            V_list = None
            n_V = -1
        if type(x_list) == np.ndarray:
            n_x = len(x_list)
        else:
            x_list = None
            n_x = -1
        if type(y_list) == np.ndarray:
            n_y = len(y_list)
        else:
            y_list = None
            n_y = -1
        
        # Pad lists that are given but are not the same length as the longest one
        iterations = np.max([n_V, n_x, n_y])
        if n_V != -1 and n_V < iterations:
            n_v = iterations
            V_list = np.pad(V_list, (0, iterations - n_V), mode = "edge")
        if n_x != -1 and n_x < iterations:
            n_x = iterations
            x_list = np.pad(x_list, (0, iterations - n_x), mode = "edge")
        if n_y != -1 and n_y < iterations:
            y_list = np.pad(y_list, (0, iterations - n_y), mode = "edge")
            n_y = iterations
        
        # Check if all elements are within the limits
        print(x_list)
        if n_V > -1:
            for element in V_list:
                if np.abs(element) > V_limit:
                    print(f"Error! Elements in V_list exceed the limits (-{V_limit} < {element} < {V_limit} = False)")
                    return False
        if n_x > -1:
            for element in x_list:
                if np.abs(element) > x_limit:
                    print(f"Error! Elements in x_list exceed the limits (-{x_limit} < {element} < {x_limit} = False)")
                    return False
        if n_y > -1:
            for element in y_list:
                if np.abs(element) > y_limit:
                    print(f"Error! Elements in x_list exceed the limits (-{y_limit} < {element} < {y_limit} = False)")
                    return False

        return [V_list, x_list, y_list, iterations]

    def get_grid(self): # Retrieve the grid data
        try:
            NTCP = nanonisTCP(self.tcp_ip, self.tcp_port, self.version_number) # Initiate the connection and get the module handles
            try:
                scan = Scan(NTCP)
                grid_data = scan.FrameGet() # Request the data from Nanonis
                buffer_data = scan.BufferGet()
                NTCP.close_connection() # Close the TCP connection
                sleep(.05)

                grid = SimpleNamespace() # Set up a grid object with attributes reflecting the grid data
                setattr(grid, "x", grid_data[0])
                setattr(grid, "y", grid_data[1])
                setattr(grid, "center", [grid_data[0], grid_data[1]])
                setattr(grid, "width", grid_data[2])
                setattr(grid, "height", grid_data[3])
                setattr(grid, "size", [grid_data[2], grid_data[3]])
                setattr(grid, "angle", grid_data[4])
                setattr(grid, "pixels", [buffer_data[2], buffer_data[3]])
                setattr(grid, "aspect_ratio", grid_data[3] / grid_data[2])
                setattr(grid, "pixel_width", grid_data[2] / buffer_data[2])
                setattr(grid, "pixel_height", grid_data[3] / buffer_data[3])
                setattr(grid, "pixel_ratio", buffer_data[3] / buffer_data[2])

                if np.abs(grid.aspect_ratio - grid.pixel_ratio) > 0.001:
                    print("Warning! The aspect ratio of the scan frame does not correspond to that of the pixels. This will result in rectangular pixels!")

                # Construct a local grid with the same size as the Nanonis grid, whose center is at (0, 0)
                x_coords_local = np.linspace(- grid.width / 2, grid.width / 2, grid.pixels[0])
                y_coords_local = np.linspace(- grid.height / 2, grid.height / 2, grid.pixels[1])
                x_grid_local, y_grid_local = np.meshgrid(x_coords_local, y_coords_local, indexing = "ij")

                # Apply a rotation
                cos = np.cos(grid.angle)
                sin = np.sin(grid.angle)
                x_grid = np.zeros_like(x_grid_local)
                y_grid = np.zeros_like(y_grid_local)

                for i in range(grid.pixels[0]):
                    for j in range(grid.pixels[1]):
                        x_grid[i, j] = x_grid_local[i, j] * cos + y_grid_local[i, j] * sin
                        y_grid[i, j] = y_grid_local[i, j] * cos - x_grid_local[i, j] * sin

                # Apply a translation
                x_grid += grid.x
                y_grid += grid.y

                # Add the meshgrids as attributes to the grid object
                setattr(grid, "x_grid", x_grid)
                setattr(grid, "y_grid", y_grid)

                return grid

            except Exception as e:
                NTCP.close_connection()
                sleep(.05)
                print(f"Error: {e}")
                return False

        except Exception as e:
            print(f"{e}")
            return False

    def tip(self, withdraw: bool = False, feedback = None):
        try:
            NTCP = nanonisTCP(self.tcp_ip, self.tcp_port, self.version_number) # Initiate the connection and get the module handles
            try:
                zcontroller = ZController(NTCP)
                
                # Get the current height and lmits
                z_pos = zcontroller.ZPosGet()
                [z_max, z_min] = zcontroller.LimitsGet()

                # Switch the feedback if desired, and retrieve the feedback status
                if type(feedback) == bool: zcontroller.OnOffSet(feedback)

                withdrawn = False
                if not feedback and np.abs(z_pos - z_max) < 1E-11: # Tip is already withdrawn
                    withdrawn = True
                if withdraw and not withdrawn: # Tip is not yet withdrawn, but a withdraw request is made
                    zcontroller.Withdraw(wait_until_finished = True)
                    withdrawn = True

                # Retrieve the feedback status
                sleep(.1)
                feedback_new = bool(zcontroller.OnOffGet())
                #fb_number = zcontroller.StatusGet()
                #if fb_number == 2: feedback = True
                #else: feedback = False

                tip_status = SimpleNamespace()
                setattr(tip_status, "height", z_pos)
                setattr(tip_status, "limits", [z_min, z_max])
                setattr(tip_status, "feedback", feedback_new)
                setattr(tip_status, "withdrawn", withdrawn)

                return tip_status

            except Exception as e:
                NTCP.close_connection()
                sleep(.1)
                print(f"Error: {e}")
                return False

        except Exception as e:
            print(f"{e}")
            return False

    def get_session_path(self):
        try:
            sleep(.2)
            NTCP = nanonisTCP(self.tcp_ip, self.tcp_port, self.version_number) # Initiate the connection and get the module handles
            try:
                util = Util(NTCP)
                session_path = util.SessionPathGet() # Read the session path
                sleep(.1)

                return session_path

            except Exception as e:
                NTCP.close_connection()
                sleep(.1)
                print(f"Error: {e}")
                return False

        except Exception as e:
            print(f"{e}")
            return False



class WorkerSignals(QObject):
    data = pyqtSignal(np.ndarray)
    finished = pyqtSignal()
    interrupted = pyqtSignal()



class CameraWorker(QObject):
    """
    Worker to handle the time-consuming cv2.VideoCapture loop.
    It runs in a separate QThread and emits frames as NumPy arrays.
    """
    # Signal to send the processed RGB NumPy frame data back to the GUI
    frameCaptured = pyqtSignal(np.ndarray)  
    # Signal to indicate that the capture loop has finished
    finished = pyqtSignal()
    
    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self._running = False
        self.cap = None

    def start_capture(self):
        """Initializes VideoCapture and starts the frame-reading loop."""
        if self._running:
            return

        self._running = True
        # Initialize VideoCapture
        self.cap = cv2.VideoCapture(self.camera_index)
        
        if not self.cap.isOpened():
            print(f"Error: Could not open camera {self.camera_index}. Check connections.")
            self._running = False
            self.finished.emit()
            return
            
        # Optimization: Set a reasonable resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
        # Main video-reading loop controlled by the _running flag
        while self._running:
            ret, frame = self.cap.read()
            if ret:
                # IMPORTANT: Convert BGR (OpenCV default) to RGB 
                # as pyqtgraph expects RGB or Grayscale data.
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frameCaptured.emit(rgb_frame)
            else:
                # Exit loop if frame read fails (e.g., camera unplugged)
                print("Warning: Failed to read frame from camera.")
                break 
                
        # Cleanup code runs when the while loop exits
        if self.cap:
             self.cap.release()
        self._running = False
        self.finished.emit() # Notify the main thread that the work is done

    def stop_capture(self):
        """Sets the flag to stop the capture loop cleanly."""
        self._running = False



class MeasurementWorker(QRunnable):
    def __init__(self, measurement_func, *args, **kwargs):
        super().__init__()
        self.measurement_func = measurement_func
        self.args = args,
        self.kwargs = kwargs,
        self.signals = WorkerSignals()
    
    @pyqtSlot()
    def run(self):
        """
        Your code goes in this function.
        """
        try:
            # Pass the progress signal to the measurement function
            result = self.measurement_func(self.signals.progress, *self.args, **self.kwargs)
            self.signals.result.emit(result)
        except:
            traceback.print_exc()
            exctype, value = sys.exc_info()[:2]
            self.signals.error.emit((exctype, value, traceback.format_exc()))
        finally:
            self.signals.finished.emit()



class Experiments(QObject):
    data = pyqtSignal(np.ndarray)
    finished = pyqtSignal()
    interrupted = pyqtSignal()

    def __init__(self, tcp_ip, tcp_port, version_number, parent = None):
        super().__init__(parent)
        self.tcp_ip = tcp_ip
        self.tcp_port = tcp_port
        self.version_number = version_number
        self._running = False

    @pyqtSlot()
    def active_measurement_loop(self, V_list = None, x_list = None, y_list = None, chunk_size = 10, delay = 0):
        # Determine what biases and locations to iterate over
        helper = HelperFunctions(self.tcp_ip, self.tcp_port, self.version_number)
        lists = helper.clean_lists(V_list, x_list, y_list)
        if type(lists) == list: # clean_lists will return False if a problem is found in the supplied data
            [V_list, x_list, y_list, iterations] = lists
        else:
            print("Aborting the measurement.")
            return False
        # Determine what parameters to update in the measurement loop
        if type(x_list) == np.ndarray: set_pos = True
        else: set_pos = False
        if type(V_list) == np.ndarray: set_bias = True
        else: set_bias = False

        # Determine the delays and the iterations
        if type(delay) != int and type(delay) != float: delay = 0
        if type(chunk_size) != int: chunk_size = 10

        # Initialize the data object
        self._running = True
        data_chunk = np.zeros((chunk_size, 5), dtype = float)
        
        try:
            # Initialize NTCP
            NTCP = nanonisTCP(self.tcp_ip, self.tcp_port, self.version_number) # Initiate the connection and get the module handles
            try:
                folme = FolMe(NTCP)
                zcontroller = ZController(NTCP)
                bias = Bias(NTCP)
                current = Current(NTCP)

                # Get the initial state of the parameters
                t0 = time
                V0 = bias.Get()
                [x0, y0] = folme.XYPosGet(Wait_for_newest_data = True)
                z0 = zcontroller.ZPosGet()
                i0 = current.Get()
                [t, V, x, y, z] = [t0, V0, x0, y0, z0, i0]

                # Fill the x_list/y_list with current x/y values if it does not exist
                if type(x_list) == np.ndarray and type(y_list) != np.ndarray:
                    y_list = np.full_like(x_list, y)
                if type(y_list) == np.ndarray and type(x_list) != np.ndarray:
                    x_list = np.full_like(y_list, x)



                # The actual measurement loop
                for iteration in range(iterations):
                    modulo_iteration = iteration % chunk_size
                    # Abort the measurement if the _running flag is set to False
                    if not self._running:
                        return False
                    
                    # ACT
                    if set_bias:
                        V = V_list[iteration]
                        bias.Set(V)
                    if set_pos:
                        x = x_list[iteration]
                        y = y_list[iteration]
                        folme.XYPosSet(x, y, Wait_end_of_move = True)
                    
                    # DELAY
                    sleep(delay)

                    # MEASURE
                    t = time - t0 # Elapsed time
                    i = current.Get()
                    # Measuring V, x, y is unnecessary: They are known if they are set and they remain V_0, x_0, y_0 if they are not set
                    
                    # SAVE / RELAY
                    data_chunk[modulo_iteration] = [t, V, x, y, z, i]
                    if iteration % chunk_size == chunk_size - 1:
                        self.data.emit(data_chunk) # Emit the data to Scantelligent
                
                return True

            except Exception as e:
                NTCP.close_connection()
                sleep(.05)
                print(f"Error: {e}. Measurement failed.")
                return False

        except Exception as e:
            print(f"{e}. Measurement failed.")
            return False

    @pyqtSlot()
    def grid_scan(self, direction: str = "up", chunk_size = 10, delay = 0):
        try:
            helper = HelperFunctions(self.tcp_ip, self.tcp_port, self.version_numbe)
            grid = helper.get_grid()
            [x_grid, y_grid] = [grid.x_grid, grid.y_grid]
            [pixels_x, pixels_y] = grid.pixels
            match direction:
                case "up":
                    x_list = x_grid.ravel()
                    y_list = y_grid.ravel()

        
        except Exception as e:
            print("Error: {e}. Measurement failed.")

    @pyqtSlot(object, int)
    def sample_grid(self, grid, points):
        try:
            # Ensure the running flag is True at the start of each new
            # measurement invocation. This allows aborting (which sets
            # _running = False) to be followed by starting a new experiment.
            self._running = True
            # Initialize parameters
            [x_grid, y_grid] = [grid.x_grid, grid.y_grid]
            [pixels_x, pixels_y] = grid.pixels
            
            flat_index_list = np.arange(x_grid.size)
            z_grid = np.zeros_like(x_grid)
            x_list = []
            y_list = []
            z_list = []
            chunk = 10
            data_chunk = np.zeros((chunk, 3), dtype = float)

            # Initiate the Nanonis TCP connection
            NTCP = nanonisTCP(self.tcp_ip, self.tcp_port, self.version_number) # Initiate the connection and get the module handles
            try:
                # Initialize modules for measurement and control
                folme = FolMe(NTCP)
                zcontroller = ZController(NTCP)

                # The first four data points are the grid corners
                for iteration in range(4):
                    if not self._running:
                        break
                    match iteration:
                        case 0: [x_index, y_index] = [0, 0]
                        case 1: [x_index, y_index] = [pixels_x - 1, 0]
                        case 2: [x_index, y_index] = [pixels_x - 1, pixels_y - 1]
                        case 3: [x_index, y_index] = [0, pixels_y - 1]

                    # Act
                    [x, y] = [x_grid[x_index, y_index], y_grid[x_index, y_index]]
                    folme.XYPosSet(x, y, Wait_end_of_move = True)

                    # Measure
                    z = zcontroller.ZPosGet()
                    data_chunk[iteration] = [x, y, z]

                # Measurement loop
                for iteration in range(4, points):
                    modulo_iteration = iteration % chunk
                    if not self._running: # Abort the measurement
                        break

                    # Choose a random index and map it to the 2D x and y grids
                    flat_index = np.random.choice(flat_index_list)
                    flat_index_list[flat_index] += 1
                    x_index, y_index = np.unravel_index(flat_index, x_grid.shape)
                    [x, y] = [x_grid[x_index, y_index], y_grid[x_index, y_index]]

                    # Act
                    folme.XYPosSet(x, y, Wait_end_of_move = True)

                    # Measure
                    z = zcontroller.ZPosGet()

                    z_grid[x_index, y_index] = z

                    data_chunk[modulo_iteration] = [x, y, z]

                    if iteration % chunk == chunk - 1:
                        self.data.emit(data_chunk) # Emit the data to Scantelligent

                NTCP.close_connection() # Close the TCP connection
                sleep(.05)
                self.finished.emit()

                return True

            except Exception as e:
                NTCP.close_connection()
                sleep(.05)
                print(f"Error: {e}")
                return False

        except Exception as e:
            print(f"{e}")
            return False

    def stop(self):
        # Set the experiment running flag to False to abort the experiment
        self._running = False



def coarse_move(direction: str = "up", steps: int = 1, xy_voltage: float = 240, z_voltage: float = 210, motor_frequency = False, override: bool = False, verbose: bool = True):
    #logfile = get_session_path() + "\\logfile.txt"

    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        motor = Motor(NTCP)
        zcontroller = ZController(NTCP)
        
        motor_frequency_old, motor_voltage_old = motor.FreqAmpGet()
        #feedback = bool(zcontroller.OnOffGet())
        #if feedback:
        #    if override:
        #        if verbose: logprint("Coarse motion attempted with the tip still in feedback. Overridden.", logfile = logfile)
        #    else:
        #        if verbose: logprint("Coarse motion attempted with the tip still in feedback. Blocked.", logfile = logfile)
        #        return
        motor_frequency_new = motor_frequency_old
        if type(motor_frequency) == int or type(motor_frequency) == float: motor_frequency_new = motor_frequency
        
        dirxn = "Z+" # Select the direction and motor voltage
        motor_voltage = min([xy_voltage, z_voltage])
        dirxn = direction.lower()
        if dirxn in ["away", "y+", "north", "n"]:
            dirxn = "Y+"
            motor_voltage = xy_voltage
        if dirxn in ["towards", "y-", "south", "s"]:
            dirxn = "Y-"
            motor_voltage = xy_voltage
        if dirxn in ["left", "x-", "west", "w"]:
            dirxn = "X-"
            motor_voltage = xy_voltage
        if dirxn in ["right", "x+", "east", "e"]:
            dirxn = "X+"
            motor_voltage = xy_voltage
        if dirxn in ["up", "z+", "lift"]:
            dirxn = "Z+"
            motor_voltage = z_voltage
        if dirxn in ["down", "z-", "approach", "advance"]:
            dirxn = "Z-"
            motor_voltage = z_voltage
        motor.FreqAmpSet(frequency = motor_frequency_new, amplitude = motor_voltage)
        sleep(.05)
        
        motor.StartMove(direction = dirxn, steps = steps, wait_until_finished = True)
        #if verbose: logprint("Coarse motion: " + str(steps) + " steps in the " + dirxn + " direction.", logfile = logfile)
        sleep(.05)

    finally:
        NTCP.close_connection()
        sleep(.05)

def scan_control(tcp_ip, tcp_port, version_number, action: str = "stop", scan_direction: str = "down", verbose: bool = True, monitor: bool = True, sampling_time: float = 4, velocity_threshold: float = .4):
    # logfile = get_session_path() + "\\logfile.txt"

    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        scan = Scan(NTCP)
        
        if scan_direction != "down": scan_direction = "up"
        if action == "start":
            scan.Action(action, scan_direction)
            #if verbose: logprint("Scan started in the " + scan_direction + " direction.", logfile = logfile)
        elif action == "stop":
            scan.Action(action)
            #if verbose: logprint("Scan stopped.", logfile = logfile)
        elif action == "pause":
            scan.Action(action)
            #if verbose: logprint("Scan paused.", logfile = logfile)
        elif action == "resume":
            scan.Action(action)
            #if verbose: logprint("Scan resumed.", logfile = logfile)

    finally:
        NTCP.close_connection()
        sleep(.05)
    
    #if action == "start" or action == "resume":
    #    if monitor: # Continue monitoring the progress of the scan until it is done
    #        txyz = tip_tracker(sampling_time = sampling_time, velocity_threshold = velocity_threshold, timeout = 100000, exit_when_still = True, N_no_motion = 4, verbose = verbose, monitor_roughness = False)

def change_bias(V = None, dt: float = .01, dV: float = .02, dz: float = 1E-9, verbose: bool = True):
    #logfile = get_session_path() + "\\logfile.txt"
    
    if V == None:
        #if verbose: logprint("No new bias set. Returning.", logfile = logfile)
        return
    
    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        bias = Bias(NTCP)
        zcontroller = ZController(NTCP)
        
        V_old = bias.Get() # Read data from Nanonis
        feedback = zcontroller.OnOffGet()
        tip_height = zcontroller.ZPosGet()
        
        polarity_difference = int(np.abs(np.sign(V) - np.sign(V_old)) / 2) # Calculate the polarity and voltage slew values
        if V > V_old: delta_V = dV
        else: delta_V = -dV
        slew = np.arange(V_old, V, delta_V)

        if bool(feedback) and bool(polarity_difference): # If the bias polarity is switched, switch off the feedback and lift the tip by dz for safety
            zcontroller.OnOffSet(False)
            sleep(.05) # If the tip height is set too quickly, the controller won't be off yet
            zcontroller.ZPosSet(tip_height + dz)
            #if verbose: logprint("Bias polarity change detected while in feedback. Tip retracted by = " + str(round(dz * 1E9, 3)) + " nm during slew.", logfile = logfile)

        for V_t in slew: # Perform the slew to the new bias voltage
            bias.Set(V_t)
            sleep(dt)
        bias.Set(V)
        
        if bool(feedback) and bool(polarity_difference): zcontroller.OnOffSet(True) # Turn the feedback back on
        
        #if verbose: logprint("Bias changed from V = " + str(round(V_old, 3)) + " V to V = " + str(round(V, 3)) + " V.", logfile = logfile)

    finally:
        NTCP.close_connection()
        sleep(.05)
        return V_old