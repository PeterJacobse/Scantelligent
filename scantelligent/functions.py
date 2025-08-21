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
import nanonispy as nap
import numpy as np
from datetime import datetime
from time import sleep
from pathlib import Path
from scipy.signal import convolve2d
import os

# Establish a TCP/IP connection
# TCP_IP = "192.168.236.1"                           # Local host
TCP_IP = "127.0.0.1"
TCP_PORT = 6501                                    # Check available ports in NANONIS > File > Settings Options > TCP Programming Interface
version_number = 13520

def logprint(message):
    current_time = datetime.now().strftime("%H:%M:%S")
    timestamped_message = current_time + "  " + message
    print(timestamped_message)

def get_session_path():
    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        util = Util(NTCP)
        
        session_path = util.SessionPathGet() # Read the session path

    finally:
        NTCP.close_connection()
        sleep(.05)
    
    return session_path

def get_file_data(session_path):
    image_files = [str(file) for file in Path(session_path).glob("*.sxm")]
    spectroscopy_files = [str(file) for file in Path(session_path).glob("*.dat")]

    image_indices = [int(os.path.splitext(os.path.basename(file))[0][-4:]) for file in image_files]
    spectroscopy_indices = [int(os.path.splitext(os.path.basename(file))[0][-4:]) for file in spectroscopy_files]

    current_image_index = max(image_indices)
    current_spectroscopy_index = max(spectroscopy_indices)

    class sessionfiles:
        def __init__(self, image_files, spectroscopy_files, image_indices, spectroscopy_indices, current_image_index, current_spectroscopy_index):
            self.image_files = image_files
            self.spectroscopy_files = spectroscopy_files
            self.image_indices = image_indices
            self.spectroscopy_indices = spectroscopy_indices
            self.current_image_index = current_image_index
            self.current_spectroscopy_index = current_spectroscopy_index

    return sessionfiles(image_files, spectroscopy_files, image_indices, spectroscopy_indices, current_image_index, current_spectroscopy_index)

def get_scan(file_name, crop_unfinished: bool = True):
    if not os.path.exists(file_name):
        print(f"Error: File '{file_name}' does not exist.")
        return
    else:
        scan_data = nap.read.Scan(file_name)
        channels = np.array([key for key in scan_data.signals.keys()])
        scans = [scan_data.signals[key] for key in channels]
        scan_header = scan_data.header
        header_keys = [key for key in scan_header.keys()]
        header_values = [scan_header[key] for key in header_keys]
        up_or_down = scan_header.get("scan_dir", "down")

        all_scans = np.stack([np.stack((np.array(scan_data.signals[channel]["forward"], dtype = float), np.flip(np.array(scan_data.signals[channel]["backward"], dtype = float), axis = 1))) for channel in channels])
        if up_or_down == "up": all_scans = np.flip(all_scans, axis = 2)

        if crop_unfinished:
            # Determine which rows should be cropped off in an uncompleted scan
            masked_array = np.isnan(all_scans[0, 1]) # The backward scan has more NaN values because the scan always starts in the forward direction
            nan_counts = np.array([sum([int(masked_array[j, i]) for i in range(len(masked_array))]) for j in range(len(masked_array[0]))])
            good_rows = np.where(nan_counts == 0)[0]
            all_scans_processed = np.array([[all_scans[channel, 0, good_rows], all_scans[channel, 1, good_rows]] for channel in range(len(channels))])
        else: all_scans_processed = all_scans

        angle = float(scan_header.get("scan_angle", 0))
        pixels = np.shape(all_scans_processed[0, 0])
        date = scan_header.get("rec_date", "00.00.1900")
        time = scan_header.get("rec_time", "00:00:00")
        center = scan_header.get("scan_offset", np.array([0, 0], dtype = float))
        size = scan_header.get("scan_range", np.array([1E-7, 1E-7], dtype = float))

        class scandata:
            def __init__(self, scans, header, channels, angle, pixels, date, time, center, size):
                self.scans = scans
                self.header = header
                self.channels = channels
                self.angle = angle
                self.pixels = pixels
                self.date = date
                self.time = time
                self.center = center
                self.size = size

        return scandata(all_scans_processed, scan_header, channels, angle, pixels, date, time, center, size)

def image_gradient(image):
    sobel_x = [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]
    sobel_y = [[-1, -2, -1], [0, 0, 0], [1, 2, 1]]
    ddx = convolve2d(image, sobel_x, mode = "valid")
    ddy = convolve2d(image, sobel_y, mode = "valid")
    gradient_image = .125 * ddx + .125 * 1j * ddy

    return gradient_image

def image_clip(image, clip_fraction: float = .1):
    values_list = np.sort(image.flatten())
    minmax_index = round(len(values_list) * clip_fraction / 2)
    min_value = values_list[minmax_index]
    max_value = values_list[-minmax_index - 1]
    image_clipped = np.array([[max(min(image[i, j], max_value), min_value) for j in range(len(image[0]))] for i in range(len(image))])

    return image_clipped

def background_subtract(image, mode: str = "plane"):
    avg_image = np.mean(image.flatten()) # The average value of the image, or the offset
    gradient_image = image_gradient(image) # The (complex) gradient of the image
    avg_gradient = np.mean(gradient_image.flatten()) # The average value of the gradient

    pix_y, pix_x = np.shape(image)
    x_values = np.arange(-(pix_x - 1) / 2, pix_x / 2, 1)
    y_values = np.arange(-(pix_y - 1) / 2, pix_y / 2, 1)

    plane = np.array([[-x * np.real(avg_gradient) - y * np.imag(avg_gradient) for x in x_values] for y in y_values])

    if mode == "plane":
        return image - plane - avg_image
    else:
        return image - avg_image

def get_latest_scan(preferred_channels = np.array(["Z", "LI Demod 1 X (A)"]), scan_direction: str = "forward", subtraction: str = "plane", clip_fraction: float = .1):
    session_path = get_session_path()
    session_files = get_file_data(session_path)
    image_files = session_files.image_files
    scan_data = get_scan(image_files[-1], crop_unfinished = True)

    if len(np.where(scan_data.channels == preferred_channels[0])[0]): # First preference channel exists
        channel_index = np.where(scan_data.channels == preferred_channels[0])[0][0]
    elif len(np.where(scan_data.channels == preferred_channels[1])[0]): # Second preference channel exists
        channel_index = np.where(scan_data.channels == preferred_channels[1])[0][0]
    else: channel_index = 0 # No preferred channels found; defaulting to showing the first channel
    if scan_direction == "backward": direction_index = 1
    else: direction_index = 0

    image = scan_data.scans[channel_index, direction_index]
    image_processed = image_clip(background_subtract(image, mode = subtraction), clip_fraction = clip_fraction)

    return image_processed

def change_bias(V: float = 1., dt: float = .01, dV: float = .02, dz: float = 1E-9, verbose: bool = True):
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
            if verbose: logprint("Bias polarity change detected while in feedback. Tip retracted by = " + str(round(dz * 1E9, 3)) + " nm during slew.")

        for V_t in slew: # Perform the slew to the new bias voltage
            bias.Set(V_t)
            sleep(dt)
        bias.Set(V)
        
        if bool(feedback) and bool(polarity_difference): zcontroller.OnOffSet(True) # Turn the feedback back on
        
        if verbose: logprint("Bias changed from V = " + str(round(V_old, 3)) + " V to V = " + str(round(V, 3)) + " V.")

    finally:
        NTCP.close_connection()
        sleep(.05)
    
    return

def change_feedback(I = None, p_gain = None, t_const = None, controller = None, withdraw: bool = False, verbose: bool = True):
    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        zcontroller = ZController(NTCP)
        
        I_old = zcontroller.SetpntGet() # Read data from Nanonis
        p_gain_old, t_const_old, i_gain_old = zcontroller.GainGet()
        controller_old = zcontroller.OnOffGet()
        
        if type(I) == float or type(I) == int: # Set the new current setpoint
            if round(float(I), 3) != round(I_old * 1E12, 3):
                zcontroller.SetpntSet(I * 1E-12)
                if verbose: logprint("Current setpoint changed from I = " + str(round(I_old * 1E12, 3)) + " pA to I = " + str(round(I, 3)) + " pA.")
                sleep(.05)
        
        p_gain_new = p_gain_old # Change the gain settings
        t_const_new = t_const_old
        if type(p_gain) == float or type(p_gain) == int: p_gain_new = p_gain * 1E-12
        if type(t_const) == float or type(t_const) == int: t_const_new = t_const * 1E-6
        if t_const_old != t_const_new or p_gain_old != p_gain_new:
            zcontroller.GainSet(p_gain = p_gain_new, time_constant = t_const_new)
            if verbose: logprint("Gains changed from p_gain = " + str(round(p_gain_old * 1E12, 3)) + " pm to p_gain = " + str(round(p_gain_new * 1E12, 3)) + " pm; t_const = " + str(round(t_const_old * 1E6)) + " us to t_const = " + str(round(t_const_new * 1E6)) + " us.")
            sleep(.05)

        if type(controller) == int or type(controller) == bool: # Change the controller status
            if int(controller) == 1 and controller_old == 0:
                if verbose: logprint("z controller switched on.")
                zcontroller.OnOffSet(1)
            elif int(controller) == 0 and controller_old == 1:
                if verbose: logprint("z controller switched off.")
                zcontroller.OnOffSet(0)
            sleep(.05)
        
        if withdraw:
            zcontroller.Withdraw(wait_until_finished = True)
            if verbose: logprint("Tip withdrawn.")

    finally:
        NTCP.close_connection()
        sleep(.05)

def auto_approach(wait_for_approach: bool = False, verbose: bool = True):
    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        autoapproach = AutoApproach(NTCP)
        
        autoapproach.OnOffSet(1)
        busy = 1
        if verbose: logprint("Auto approach initiated.")
        
        if wait_for_approach:
            while busy:
                busy = bool(autoapproach.OnOffGet())
                sleep(.1)
            if verbose: logprint("Auto approach done.")

    finally:
        NTCP.close_connection()
        sleep(.05)

def scan_control(action: str = "stop", scan_direction: str = "down", verbose: bool = True):
    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        scan = Scan(NTCP)
        
        if scan_direction != "down": scan_direction = "up"
        if action == "start":
            scan.Action(action, scan_direction)
            if verbose: logprint("Scan started in the " + scan_direction + " direction.")
        elif action == "stop":
            scan.Action(action)
            if verbose: logprint("Scan stopped.")
        elif action == "pause":
            scan.Action(action)
            if verbose: logprint("Scan paused.")
        elif action == "resume":
            scan.Action(action)
            if verbose: logprint("Scan resumed.")

    finally:
        NTCP.close_connection()
        sleep(.05)

def coarse_move(direction: str = "up", steps: int = 1, xy_voltage: float = 240, z_voltage: float = 210, motor_frequency = False, override: bool = False, verbose: bool = True):
    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        motor = Motor(NTCP)
        zcontroller = ZController(NTCP)
        
        motor_frequency_old, motor_voltage_old = motor.FreqAmpGet()
        feedback = bool(zcontroller.OnOffGet())
        if feedback:
            if override:
                if verbose: logprint("Coarse motion attempted with the tip still in feedback. Overridden.")
            else:
                if verbose: logprint("Coarse motion attempted with the tip still in feedback. Blocked.")
                return
        motor_frequency_new = motor_frequency_old
        if type(motor_frequency) == int or type(motor_frequency) == float: motor_frequency_new = motor_frequency
        
        dirxn = "Z+" # Select the direction and motor voltage
        motor_voltage = min([xy_voltage, z_voltage])
        if direction == "away" or direction == "Y+" or direction == "north":
            dirxn = "Y+"
            motor_voltage = xy_voltage
        if direction == "towards" or direction == "Y-" or direction == "south":
            dirxn = "Y-"
            motor_voltage = xy_voltage
        if direction == "left" or direction == "X-" or direction == "west":
            dirxn = "X-"
            motor_voltage = xy_voltage
        if direction == "right" or direction == "X+" or direction == "east":
            dirxn = "X+"
            motor_voltage = xy_voltage
        if direction == "up" or direction == "Z+" or direction == "lift":
            dirxn = "Z+"
            motor_voltage = z_voltage
        if direction == "down" or direction == "Z-" or direction == "approach":
            dirxn = "Z-"
            motor_voltage = z_voltage
        motor.FreqAmpSet(frequency = motor_frequency_new, amplitude = motor_voltage)
        sleep(.05)
        motor.StartMove(direction = dirxn, steps = steps, wait_until_finished = True)
        if verbose: logprint("Coarse motion: " + str(steps) + " steps in the " + dirxn + " direction.")
        sleep(.05)

    finally:
        NTCP.close_connection()
        sleep(.05)

def move_over(direction: str = "west", steps: int = 20, z_steps: int = 10, I_approach: float = 100, p_gain_approach: float = 40, t_const_approach: float = 167, xy_voltage: float = 240, z_voltage: float = 210, start_scan: bool = False):
    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        zcontroller = ZController(NTCP)
        
        I_old = zcontroller.SetpntGet() # Read data from Nanonis
        p_gain_old, t_const_old, i_gain_old = zcontroller.GainGet()
        controller_old = zcontroller.OnOffGet()
    
    finally:
        NTCP.close_connection()
        sleep(.05)
    
    scan_control(action = "stop")
    change_feedback(I = I_approach, p_gain = p_gain_approach, t_const = t_const_approach, withdraw = True)
    coarse_move(direction = "lift", steps = z_steps, xy_voltage = xy_voltage, z_voltage = z_voltage)
    coarse_move(direction = direction, steps = steps, xy_voltage = xy_voltage, z_voltage = z_voltage)
    auto_approach(wait_for_approach = True)
    change_feedback(I = I_old * 1E12, p_gain = p_gain_old * 1E12, t_const = t_const_old * 1E6, controller = True)
    
    if start_scan: scan_control(action = "start")

def scan_mode(mode: str = "topo", bwd_speed: float = 34, verbose: bool = True, topo_channels = np.array(["Z (m)"]), const_height_channels = np.array(["Current (A)", "LI Demod 1 X (A)", "LI Demod 1 Y (A)", "LI Demod 2 X (A)", "LI Demod 2 X (A)"])):
    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        scan = Scan(NTCP)
        signals = Signals(NTCP)
        
        speed_parameters = scan.SpeedGet() # Get the current scan parameters
        fwd_speed_old = speed_parameters[0] * 1E9
        channel_indices_old = np.array(scan.BufferGet()[1]) # Obtain the currently recorded channels, and the names of all channels
        channel_names = np.array(signals.NamesGet())
        
        topo_channel_indices = np.array([np.where(channel_names == name)[0][0] for name in topo_channels], dtype = int)
        const_height_channel_indices = np.array([np.where(channel_names == name)[0][0] for name in const_height_channels], dtype = int)
        # Retain the channels that are being recorded
        channels_old_indices = [channel for channel in channel_indices_old if not channel in np.concatenate((topo_channel_indices, const_height_channel_indices))]
           
        #scan_control(action = "stop") # Stop a scan if it happened to be running
        
        if mode == "constant height":
            scan.SpeedSet(fwd_speed = fwd_speed_old * 1E-9, bwd_speed = bwd_speed * 1E-9) # In constant height mode, use a slow forward direction and a fast backward direction
            if verbose: logprint("Constant height mode activated. Forward scan speed: " + str(round(fwd_speed_old, 3)) + " nm/s. Backward speed: " + str(round(bwd_speed, 3)) + " nm/s.")
            target_channel_indices = np.concatenate((channels_old_indices, const_height_channel_indices))
        else:
            scan.SpeedSet(fwd_speed = fwd_speed_old * 1E-9, bwd_speed = fwd_speed_old * 1E-9) # In topographic imaging mode, set the forward and backward speeds equal.
            if verbose: logprint("Topographic imaging mode activated. Forward scan speed: " + str(round(fwd_speed_old, 3)) + " nm/s. Backward speed: " + str(round(fwd_speed_old, 3)) + " nm/s.")
            target_channel_indices = np.concatenate((channels_old_indices, topo_channel_indices))
        
        target_channels = [channel_names[index] for index in target_channel_indices]
        #scan.BufferSet(channel_indexes = )
        if verbose: logprint("Recording the following channels: " + "; ".join(target_channels))
        
    finally:
        NTCP.close_connection()
        sleep(.05)

