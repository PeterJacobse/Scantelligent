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
import nanonispy as nap
import numpy as np
from pynput import keyboard
from datetime import datetime
import time
from time import sleep
from pathlib import Path
from scipy.signal import convolve2d
import os

# Establish a TCP/IP connection
TCP_IP = "192.168.236.1"                           # Local host
#TCP_IP = "127.0.0.1"
TCP_PORT = 6501                                    # Check available ports in NANONIS > File > Settings Options > TCP Programming Interface
version_number = 13520

# Object classes

class imagestatistics:
    def __init__(self, data_sorted, n_data, range_min, Q1, range_mean, Q3, range_max, range_total, standard_deviation, histogram):
        self.sorted = data_sorted
        self.n = n_data
        self.min = range_min
        self.mean = range_mean
        self.max = range_max
        self.range = range_total
        self.Q1 = Q1
        self.Q3 = Q3
        self.IQR = Q3 - Q1
        self.standard_deviation = standard_deviation
        self.histogram = histogram

class sessionfiles:
    def __init__(self, image_files, spectroscopy_files, image_indices, spectroscopy_indices, current_image_index, current_spectroscopy_index):
        self.image_files = image_files
        self.spectroscopy_files = spectroscopy_files
        self.image_indices = image_indices
        self.spectroscopy_indices = spectroscopy_indices
        self.current_image_index = current_image_index
        self.current_spectroscopy_index = current_spectroscopy_index

class scandata:
    def __init__(self, scans, header, channels, angle, pixels, date, time, center, size, V):
        self.scans = scans
        self.header = header
        self.channels = channels
        self.angle = angle
        self.pixels = pixels
        self.date = date
        self.time = time
        self.center = center
        self.size = size
        self.V = V

class parameters:
    def __init__(self, v_fwd, v_bwd, t_fwd, t_bwd, lock_parameter, v_ratio, V, V_ac, f_ac, phase_ac, lockin_status, I_fb, p_gain, t_const, i_gain, x_center, y_center, scan_width, scan_height, scan_angle, pixels, lines, z_min, z_max, scan_channels):
        self.v_fwd = v_fwd
        self.v_bwd = v_bwd
        self.t_fwd = t_fwd
        self.t_bwd = t_bwd
        self.lock_parameter = lock_parameter
        self.v_ratio = v_ratio
        self.V = V
        self.V_ac = V_ac
        self.f_ac = f_ac
        self.phase_ac = phase_ac
        self.lockin_status = lockin_status
        self.I_fb = I_fb
        self.p_gain = p_gain
        self.t_const = t_const
        self.i_gain = i_gain
        self.x_center = x_center
        self.y_center = y_center
        self.center = [x_center, y_center]
        self.scan_width = scan_width
        self.scan_height = scan_height
        self.size = [scan_width, scan_height]
        self.pixels = pixels
        self.lines = lines
        self.grid = [pixels, lines]
        self.scan_angle = scan_angle
        self.z_min = z_min
        self.z_max = z_max
        self.z_range = [z_min, z_max]
        self.scan_channels = scan_channels

# Miscellaneous

def on_release(key):
    # A keystroke listener for manual abort
    global exit_flag
    try:
        if key == keyboard.Key.esc or key.char == "q":
            print("KEYSTROKE")
            exit_flag = True
            return False
    finally:
        pass

def logprint(message, timestamp: bool = True, logfile: str = ""):
    current_time = datetime.now().strftime("%H:%M:%S")
    if timestamp: timestamped_message = current_time + "  " + message
    else: timestamped_message = "          " + message
    if os.path.exists(logfile):
        with open(logfile, "a") as f:
            f.write(timestamped_message + "\n")
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

    if len(image_indices) > 0: current_image_index = max(image_indices)
    else: current_image_index = 0
    if len(spectroscopy_indices) > 0: current_spectroscopy_index = max(spectroscopy_indices)
    else: current_spectroscopy_index = 0

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
        V = scan_data.header.get("bias", 0)

        return scandata(all_scans_processed, scan_header, channels, angle, pixels, date, time, center, size, V)

def initialize():
    session_path = get_session_path()
    images_path = session_path + "\\Extracted Files"
    logfile_path = session_path + "\\logfile.txt"

    timestamp = datetime.now().strftime("Scantelligent log file created on %Y-%m-%d at %H:%M:%S")
    logprint("Scantelligent session initialized. " + timestamp, logfile = logfile_path)

    try:
        with open(logfile_path, "x") as f:
            f.write(timestamp)
            f.write("\n\nMeasurement session folder: " + session_path)
            f.write("\nImages and spectra extracted to: " + images_path)
            f.write("\n\n")

    except FileExistsError:
        with open(logfile_path, "w") as f:
            f.write(timestamp)
            f.write("\n\nMeasurement session folder: " + session_path)
            f.write("\nImages and spectra extracted to: " + images_path)
            f.write("\n\n")
        pass
    
    try:
        os.makedirs(images_path, exist_ok = True)
        logprint(f"Directory '{images_path}' created successfully or already existed.", timestamp = False, logfile = logfile_path)
    except OSError as e:
        logprint(f"Error creating directory '{images_path}': {e}", timestamp = False, logfile = logfile_path)

    parameters = get_parameters(verbose = True)
    
    return session_path, images_path, logfile_path, parameters

# Image functions

def get_image_statistics(image, pixels_per_bin: int = 200):
    data_sorted = np.sort(image.flatten())
    n_data = len(data_sorted)
    data_firsthalf = data_sorted[:int(n_data / 2)]
    data_secondhalf = data_sorted[-int(n_data / 2):]

    range_mean = np.mean(data_sorted) # Calculate the mean
    Q1 = np.mean(data_firsthalf) # Calculate the first and third quartiles
    Q3 = np.mean(data_secondhalf)
    range_min, range_max = (data_sorted[0], data_sorted[-1]) # Calculate the total range
    range_total = range_max - range_min
    standard_deviation = np.sum(np.sqrt((data_sorted - range_mean) ** 2) / n_data) # Calculate the standard deviation
    
    n_bins = int(np.floor(n_data / pixels_per_bin))
    counts, bounds = np.histogram(data_sorted, bins = n_bins)
    binsize = bounds[1] - bounds[0]
    padded_counts = np.pad(counts, 1, mode = "constant")
    bincenters = np.concatenate([[bounds[0] - .5 * binsize], np.convolve(bounds, [.5, .5], mode = "valid"), [bounds[-1] + .5 * binsize]])
    histogram = np.array([bincenters, padded_counts])
    
    return imagestatistics(data_sorted, n_data, range_min, Q1, range_mean, Q3, range_max, range_total, standard_deviation, histogram)

def clip_range(image, method: str = "standard_deviation", values = [-2, 2], default_to_data_range: bool = True, tie_to_zero = [False, False]):
    stats = get_image_statistics(image)
    clip_values = [0, 0]
    
    if type(values) == int or type(values) == float:
        if method == "percentiles":
            values = np.sort([values, 1 - values])
        values = [-values, values]
    if method == "IQR": clip_values = [stats.Q1 + values[0] * stats.IQR, stats.Q3 + values[1] * stats.IQR]
    elif method == "standard_deviation": clip_values = [stats.mean + values[0] * stats.standard_deviation, stats.Q3 + values[1] * stats.standard_deviation]
    elif method == "percentiles": clip_values = [stats.min + .01 * values[0] * stats.range, stats.min + .01 * values[1] * stats.range]
    else: print("No valid clipping method selected")
    
    if tie_to_zero[0]: clip_values[0] = 0
    if tie_to_zero[1]: clip_values[1] = 0
    
    if clip_values[0] < stats.min:
        print("Warning: Lower limit is below the lower limit of the data.")
        if default_to_data_range:
            print("Resetting lower limit to the lower limit of the data.")
            clip_values[0] = stats.min
    if clip_values[1] > stats.max:
        print("Warning: Upper limit is above the upper limit of the data.")
        if default_to_data_range:
            print("Resetting upper limit to the upper limit of the data.")
            clip_values[1] = stats.max
    
    if clip_values[1] < clip_values[0]:
        print("Warning: Lower limit is set to a lower value than the upper limit. Inverting.")
        clip_values = [clip_values[1], clip_values[0]]
    
    return clip_values

def image_gradient(image):
    sobel_x = [[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]]
    sobel_y = [[-1, -2, -1], [0, 0, 0], [1, 2, 1]]
    ddx = convolve2d(image, sobel_x, mode = "valid")
    ddy = convolve2d(image, sobel_y, mode = "valid")
    gradient_image = .125 * ddx + .125 * 1j * ddy

    return gradient_image

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

# Nanonis functions

def get_parameters(verbose: bool = False):
    logfile = get_session_path() + "\\logfile.txt"

    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        scan = Scan(NTCP)
        zcontroller = ZController(NTCP)
        bias = Bias(NTCP)
        lockin = LockIn(NTCP)
        folme = FolMe(NTCP)
        signals = Signals(NTCP)
        biasspectr = BiasSpectr(NTCP)
        tipshaper = TipShaper(NTCP)
        
        x_tip, y_tip = folme.XYPosGet(Wait_for_newest_data = True ) # Get the current scan parameters
        v_tip = folme.SpeedGet()[0] # Tip positions and speed (FolMe)
        x_tip *= 1E9
        y_tip *= 1E9
        v_tip *= 1E9
        
        V = bias.Get() # Bias
        V_ac = lockin.ModAmpGet(modulator_number = 1) # Lockin
        f_ac = lockin.ModPhasFreqGet(modulator_number = 1)
        phase_ac = lockin.DemodPhasGet(demod_number = 1)
        lockin_status = lockin.ModOnOffGet(modulator_number = 1)
        
        I_fb = zcontroller.SetpntGet() * 1E12 # Z controller
        p_gain, t_const, i_gain = zcontroller.GainGet()
        p_gain *= 1E12
        t_const *= 1E6
        i_gain *= 1E9
        z_max, z_min = zcontroller.LimitsGet()
        z_tip = zcontroller.ZPosGet()
        z_tip *= 1E9
        z_min *= 1E9
        z_max *= 1E9
        z_range = [z_min, z_max]
        fb = zcontroller.OnOffGet()
        
        v_fwd, v_bwd, t_fwd, t_bwd, lock_parameter, v_ratio = scan.SpeedGet() # Scan
        x_center, y_center, scan_width, scan_height, scan_angle = scan.FrameGet()   
        [scan_num_channels, scan_channels, pixels, lines] = scan.BufferGet()
        x_center *= 1E9
        y_center *= 1E9
        scan_width *= 1E9
        scan_height *= 1E9
        v_fwd *= 1E9
        v_bwd *= 1E9
        
        spectr_advprops = biasspectr.AdvPropsGet() # Spectroscopy
        spectr_props = biasspectr.PropsGet_v0()
        spectr_timing = biasspectr.TimingGet()
        print(spectr_timing)
        reset_bias = spectr_advprops.get("reset_bias", 1)
        z_controller_hold = spectr_advprops.get("z_controller_hold", 1)
        num_sweeps = spectr_props.get("num_sweeps", 1)
        
        tipshaper_props = tipshaper.PropsGet() # Tip shaper
        
        #channels = np.array(signals.NamesGet()) # Alternative way to extract the tip positions
        #x_channel_index = np.where(channels == "X (m)")[0][0]
        #y_channel_index = np.where(channels == "Y (m)")[0][0]
        #z_channel_index = np.where(channels == "Z (m)")[0][0]
        #[x_tip, y_tip, z_tip] = [signals.ValGet(index) for index in [x_channel_index, y_channel_index, z_channel_index]]

    finally:
        NTCP.close_connection()
        sleep(.05)

    if verbose:
        logprint("Report of parameters:\n", logfile = logfile)
        
        logprint("Tip parameters:", timestamp = False, logfile = logfile)
        logprint(f"  Location (x_tip, y_tip, z_tip) = ({round(x_tip, 3)}, {round(y_tip, 3)}, {round(z_tip, 3)}) nm. Tip displacement speed (v_tip) = {round(v_tip)} nm/s.", timestamp = False, logfile = logfile)
        
        logprint("Bias parameters:", timestamp = False, logfile = logfile)
        logprint(f"  Bias voltage (V) = {round(V, 3)} V.", timestamp = False, logfile = logfile)
        logprint(f"  Lockin modulation voltage (V_ac) = {round(V_ac, 3)} V; Lockin modulation frequency (f_ac) = {round(f_ac, 3)} Hz; Lockin phase (phase_ac) = {round(phase_ac, 3)} degree.", timestamp = False, logfile = logfile)
        if bool(lockin_status): logprint("  Lockin is switched on (lockin_status = 1).", timestamp = False, logfile = logfile)
        else: logprint("  Lockin is switched off (lockin_status = 0).", timestamp = False, logfile = logfile)

        logprint("Z controller parameters:", timestamp = False, logfile = logfile)
        if bool(fb): logprint(f"  Feedback current (I_fb) = {round(I_fb, 3)} pA. Feedback is switched on (fb = 1).", timestamp = False, logfile = logfile)
        else: logprint(f"  Feedback current (I_fb) = {round(I_fb, 3)} pA. Feedback is switched off (fb = 0).", timestamp = False, logfile = logfile)
        logprint(f"  Gains (p_gain, t_const, i_gain) = ({round(p_gain, 3)} pm, {round(t_const, 3)} us, {round(i_gain, 3)} nm/s).", timestamp = False, logfile = logfile)
        logprint(f"  Limits (z_range = [z_min, z_max]) = [{round(z_min, 3)}, {round(z_max, 3)}] nm.", timestamp = False, logfile = logfile)

        logprint("Scan parameters:", timestamp = False, logfile = logfile)
        logprint(f"  Center (center = [x_center, y_center]) = [{round(x_center, 3)}, {round(y_center, 3)}] nm. Size (size = [width, height]) = [{round(scan_width, 3)}, {round(scan_height, 3)}] nm. Rotation angle (angle) = {round(scan_angle, 3)} degree.", timestamp = False, logfile = logfile)
        logprint(f"  Number of pixels and lines (grid = [pixels, lines]) = [{pixels}, {lines}]. Time per line (t_fwd, t_bwd) = ({round(t_fwd, 3)}, {round(t_bwd, 3)}) s.", timestamp = False, logfile = logfile)
        logprint(f"  Scan speed (v_fwd, v_bwd) = ({round(v_fwd, 3)}, {round(v_bwd, 3)}) nm/s. Speed ratio (v_ratio) = {round(v_ratio, 3)}.", timestamp = False, logfile = logfile)
        
        logprint("Bias spectroscopy parameters:", timestamp = False, logfile = logfile)
        logprint(f"  Reset bias after spectroscopy (reset_bias) = {str(bool(reset_bias))}. Number of sweeps = {str(num_sweeps)}", timestamp = False, logfile = logfile)
        logprint(str(spectr_advprops), timestamp = False, logfile = logfile)
        logprint(str(spectr_props), timestamp = False, logfile = logfile)
        logprint(str(spectr_timing), timestamp = False, logfile = logfile)
        
        logprint("Tip shaper properties:", timestamp = False, logfile = logfile)
        logprint(" ".join(str(item) for item in tipshaper_props), timestamp = False, logfile = logfile)

        logprint("\n          End of report.\n", timestamp = False, logfile = logfile)
    
    return parameters(v_fwd = v_fwd, v_bwd = v_bwd, t_fwd = t_fwd, t_bwd = t_bwd, lock_parameter = lock_parameter, v_ratio = v_ratio, V = V, V_ac = V_ac, f_ac = f_ac, phase_ac = phase_ac, lockin_status = lockin_status, I_fb = I_fb, p_gain = p_gain, t_const = t_const, i_gain = i_gain, x_center = x_center, y_center = y_center, scan_width = scan_width, scan_height = scan_height, scan_angle = scan_angle, pixels = pixels, lines = lines, z_min = z_min, z_max = z_max, scan_channels = scan_channels);

def change_bias(V = None, dt: float = .01, dV: float = .02, dz: float = 1E-9, verbose: bool = True):
    logfile = get_session_path() + "\\logfile.txt"
    
    if V == None:
        if verbose: logprint("No new bias set. Returning.", logfile = logfile)
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
            if verbose: logprint("Bias polarity change detected while in feedback. Tip retracted by = " + str(round(dz * 1E9, 3)) + " nm during slew.", logfile = logfile)

        for V_t in slew: # Perform the slew to the new bias voltage
            bias.Set(V_t)
            sleep(dt)
        bias.Set(V)
        
        if bool(feedback) and bool(polarity_difference): zcontroller.OnOffSet(True) # Turn the feedback back on
        
        if verbose: logprint("Bias changed from V = " + str(round(V_old, 3)) + " V to V = " + str(round(V, 3)) + " V.", logfile = logfile)

    finally:
        NTCP.close_connection()
        sleep(.05)
        return V_old

def change_feedback(I = None, p_gain = None, t_const = None, controller = None, withdraw: bool = False, verbose: bool = True):
    logfile = get_session_path() + "\\logfile.txt"
    
    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        zcontroller = ZController(NTCP)
        
        I_old = zcontroller.SetpntGet() # Read data from Nanonis
        p_gain_old, t_const_old, i_gain_old = zcontroller.GainGet()
        controller_old = zcontroller.OnOffGet()

        if withdraw:
            zcontroller.Withdraw(wait_until_finished = True)
            if verbose: logprint("Tip withdrawn.", logfile = logfile)
            sleep(.05)

        if type(I) == float or type(I) == int: # Set the new current setpoint
            if round(float(I), 3) != round(I_old * 1E12, 3):
                zcontroller.SetpntSet(I * 1E-12)
                if verbose: logprint("Current setpoint changed from I = " + str(round(I_old * 1E12, 3)) + " pA to I = " + str(round(I, 3)) + " pA.", logfile = logfile)
                sleep(.05)
        
        p_gain_new = p_gain_old # Change the gain settings
        t_const_new = t_const_old
        if type(p_gain) == float or type(p_gain) == int: p_gain_new = p_gain * 1E-12
        if type(t_const) == float or type(t_const) == int: t_const_new = t_const * 1E-6
        if t_const_old != t_const_new or p_gain_old != p_gain_new:
            zcontroller.GainSet(p_gain = p_gain_new, time_constant = t_const_new)
            if verbose: logprint("Gains changed from p_gain = " + str(round(p_gain_old * 1E12, 3)) + " pm to p_gain = " + str(round(p_gain_new * 1E12, 3)) + " pm; t_const = " + str(round(t_const_old * 1E6)) + " us to t_const = " + str(round(t_const_new * 1E6)) + " us.", logfile = logfile)
            sleep(.05)

        if type(controller) == int or type(controller) == bool: # Change the controller status
            if int(controller) == 1 and controller_old == 0:
                if verbose: logprint("z controller switched on.", logfile = logfile)
                zcontroller.OnOffSet(1)
            elif int(controller) == 0 and controller_old == 1:
                if verbose: logprint("z controller switched off.", logfile = logfile)
                zcontroller.OnOffSet(0)

    finally:
        NTCP.close_connection()
        sleep(.05)
        return (I_old * 1E12, p_gain_old * 1E12, t_const_old * 1E6)

def change_scan_window(center = None, size = None, grid = None, angle = None, verbose: bool = True):
    logfile = get_session_path() + "\\logfile.txt"
    parameters = get_parameters() # Use get_parameters to extract all the old scan parameters
    scan_channels = parameters.scan_channels
    grid_old = parameters.grid
    size_old = parameters.size
    angle_old = parameters.scan_angle
    center_old = parameters.center
    
    if type(center) == int or type(center) == float: center = None # Do not change the scan window location if only a single value is given
    if center == None: center = center_old
    center = [center[0], center[1]]
    if type(angle) != int and type(angle) != float: angle = angle_old # Do not change the scan angle if no value is given
    if type(size) == int or type(size) == float: size = [size, size] # If a single value is given for the scan window size, make a square window
    if size == None: size = size_old # If no scan size was given, retain the old scan window size
    size = [size[0], size[1]]
    aspect_ratio = size[1] / size[0] # Calculate the aspect ratio of the scan window
    
    if type(grid) == int or type(grid) == float:
        grid = [int(16 * np.round(grid / 16)), 0] # The number of pixels always needs to be a multiple of 16 in Nanonis
        grid[1] = int(grid[0] * aspect_ratio) # If only the horizontal number of pixels is given, calculate the number of lines based on the aspect ratio of the scan window
    elif type(grid) == list or type(grid) == np.ndarray or type(grid) == tuple: grid = [int(16 * np.round(grid[0] / 16)), int(grid[1])]
    if grid == None: grid = grid_old
    
    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        scan = Scan(NTCP)
        scan.BufferSet(scan_channels, grid[0], grid[1])
        scan.FrameSet(center[0] * 1E-9, center[1] * 1E-9, size[0] * 1E-9, size[1] * 1E-9, angle)
        if verbose: logprint(f"Scan window parameters changed. Center: ({round(center[0], 3)}, {round(center[1], 3)}) nm. Size: ({round(size[0], 3)}, {round(size[1], 3)}) nm. Grid: ({grid[0]}, {grid[1]}) pixels. Angle = {angle} degrees.", logfile = logfile)

    finally:
        NTCP.close_connection()
        sleep(.05)        
        return (center_old, size_old, grid_old, angle_old)

def tip_tracker(sampling_time: float = .5, velocity_threshold: float = .02, timeout: float = 30, exit_when_still: bool = True, N_no_motion: int = 4, verbose: bool = True, tracking_info: bool = False, monitor_roughness: bool = False, measurement_interval = 10, max_z_range: float = 20):
    logfile = get_session_path() + "\\logfile.txt"
    #listener = keyboard.Listener(on_release = on_release)

    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        folme = FolMe(NTCP)
        zcontroller = ZController(NTCP)
        
        start_time = time.monotonic() # Obtain the first tip position and time data
        current_time = start_time
        elapsed_time = 0
        no_motion = 0
        x_tip, y_tip = folme.XYPosGet(Wait_for_newest_data = True)
        x_tip *= 1E9 # Use nm as the natural unit for tip distances
        y_tip *= 1E9
        z_tip = zcontroller.ZPosGet() * 1E9
        x_tip_old, y_tip_old, z_tip_old = (x_tip, y_tip, z_tip)
        x_list = [x_tip_old]
        y_list = [y_tip_old]
        z_list = [z_tip_old]
        t_list = [0]
        velocity_threshold2 = velocity_threshold ** 2
        
        if verbose: logprint("Tip tracker started.", logfile = logfile)
        if tracking_info: logprint(f"Tip position: ({round(x_tip, 3)}, {round(y_tip, 3)}, {round(z_tip, 3)}) nm.")
        exit_flag = False
        #listener.start()
        sleep(sampling_time)
        
        while True:
            x_tip, y_tip = folme.XYPosGet(Wait_for_newest_data = True) # Get new data
            x_tip *= 1E9
            y_tip *= 1E9
            z_tip = zcontroller.ZPosGet() * 1E9
            current_time = time.monotonic() # Keep track of the time and check for a timeout with each iteration
            elapsed_time = current_time - start_time
            
            delta_pos = [x_tip - x_tip_old, y_tip - y_tip_old, z_tip - z_tip_old] # Calculate displacement and velocity
            displacement2 = delta_pos[0] ** 2 + delta_pos[1] ** 2 + delta_pos[2] ** 2
            min_velocity2 = displacement2 / sampling_time
            x_tip_old, y_tip_old, z_tip_old = (x_tip, y_tip, z_tip)
            
            x_list.append(x_tip) # Save the position and time information
            y_list.append(y_tip)
            z_list.append(z_tip)
            t_list.append(elapsed_time)
        
            if tracking_info:
                min_velocity = np.sqrt(min_velocity2)
                logprint(f"Tip position: ({round(x_tip, 3)}, {round(y_tip, 3)}, {round(z_tip, 3)}) nm. Displacement vector since last measurement: ({round(delta_pos[0], 3)}, {round(delta_pos[1], 3)}, {round(delta_pos[2], 3)}) nm. Minimum velocity: {round(min_velocity, 3)} nm/s.")
            
            if min_velocity2 < velocity_threshold2: # Routine to handle the tip being detected to be no longer moving
                if tracking_info: logprint("Tip appears to be at rest.", logfile = logfile)
                no_motion += 1 # no_motion counts the number of samples that no tip motion has been detected. After N_no_motion samples of no motion, the tip is assumed to be at rest.
            else: no_motion = 0 # Reset the no_motion parameter if motion is detected
            if no_motion > N_no_motion - 1 and exit_when_still:
                if verbose: logprint("Tip deemed to be at rest. Exiting tip tracker.", logfile = logfile)
                break
            
            if elapsed_time > timeout: # Routine to handle timeouts
                if verbose: logprint("Tip tracker experienced a timeout.", logfile = logfile)
                break
            
            if monitor_roughness:
                if np.mod(np.floor(elapsed_time), measurement_interval) == 0: # Calculate the roughness every measurement_interval seconds
                    n_list = len(z_list)
                    z_list_np = np.array(z_list)
                    z_avg = np.mean(z_list_np)
                    z_minmax = [np.min(z_list_np), np.max(z_list_np)]
                    z_diff = (z_list_np - z_avg) ** 2
                    z_rms = np.sqrt(np.sum(z_diff) / n_list)
                    logprint(f"Surface roughness monitoring. [z_min, z_avg, z_max] = [{z_minmax[0]}, {z_avg}, {z_minmax[1]}] nm. RMS deviation from average: [{z_rms}] nm.")
            
            if exit_flag:
                if verbose: logprint("Exit keystroke detected. Aborting tip tracker.", logfile = logfile)
                break
            
            sleep(sampling_time)

    finally:
        NTCP.close_connection()
        #listener.stop()
        sleep(.05)        
        return np.array([t_list, x_list, y_list, z_list])

def auto_phase(V_ac = None, f_ac = None, verbose: bool = True):
    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        lockin = LockIn(NTCP)
        signals = Signals(NTCP)
        
        V_ac_old = lockin.ModAmpGet(modulator_number = 1) # Read the old lockin settings
        f_ac_old = lockin.ModPhasFreqGet(modulator_number = 1)
        phase_ac_old = lockin.DemodPhasGet(demod_number = 1)
        lockin_on_old = lockin.ModOnOffGet(modulator_number = 1)
        rt_signals_old = lockin.DemodRTSignalsGet(demod_number = 1)
            
        if type(V_ac) != int and type(V_ac) != float: V_ac = V_ac_old # Set the lockin to the custom settings
        if type(f_ac) != int and type(f_ac) != float: f_ac = f_ac_old
        lockin.ModAmpSet(modulator_number = 1, amplitude = V_ac)
        lockin.ModPhasFreqSet(modulator_number = 1, frequency = f_ac)
        lockin.DemodRTSignalsSet(demod_number = 1, rt_signals = 1) # Use R/phi instead of X/Y
        lockin.DemodPhasSet(demod_number = 1, phase_deg = 0)
        lockin.ModOnOffSet(1, 1)
        sleep(.1)
        
        channels = np.array(signals.NamesGet()) # The channel names are actively updated in Nanonis to use R/phi or X/Y
        lockin_phi_index = np.where(channels == "LI Demod 1 Phi (deg)")[0][0]
        
        lockin_phi_av = 0
        for samples in range(20):
            lockin_phi_av += signals.ValGet(lockin_phi_index, wait_for_newest_data = True)
        new_phase = lockin_phi_av / 20 - 90
        if new_phase > 180: new_phase -= 360
        if new_phase < -180: new_phase += 360
        
        lockin.DemodPhasSet(demod_number = 1, phase_deg = new_phase) # Set the new phase
        lockin.DemodRTSignalsSet(demod_number = 1, rt_signals = rt_signals_old) # Reset to the old settings

        lockin.ModOnOffSet(1, lockin_on_old)
        lockin.ModPhasFreqSet(modulator_number = 1, frequency = f_ac_old)
        lockin.ModAmpSet(modulator_number = 1, amplitude = V_ac_old)

        logprint(f"Lockin autophased at a frequency of {round(f_ac, 3)} Hz. Demodulator phase set to phi = {round(new_phase, 3)} degree.")

    finally:
        NTCP.close_connection()
        sleep(.05)

def auto_approach(verbose: bool = True, timeout = 1000, I_approach: float = 100, p_gain_approach: float = 40, t_const_approach: float = 167, z_voltage: float = 210, land_tip: bool = True, adjust_percentile: float =  75, velocity_threshold: float = .02):
    logfile = get_session_path() + "\\logfile.txt"
    I_old, p_gain_old, t_const_old = change_feedback(I = I_approach, p_gain = p_gain_approach, t_const = t_const_approach, withdraw = True) # Change to the approach settings while withdrawing the tip

    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        autoapproach = AutoApproach(NTCP)
        motor = Motor(NTCP)
        zcontroller = ZController(NTCP)
        
        motor_frequency_old, motor_voltage_old = motor.FreqAmpGet()
        [z_max, z_min] = zcontroller.LimitsGet()
        z_min *= 1E9
        z_max *= 1E9
        z_range = z_max - z_min
        if adjust_percentile < 50 or adjust_percentile > 100: adjust_percentile = 90
        z_limits = [z_max - .01 * adjust_percentile * z_range, z_min + .01 * adjust_percentile * z_range] # If the tip comes to rest outside of these limits, do a coarse step and reapproach
        if type(z_voltage) == int or type(z_voltage) == float: motor.FreqAmpSet(frequency = motor_frequency_old, amplitude = z_voltage)
        autoapproach.OnOffSet(1) # Start the auto approach
        if verbose: logprint("Auto approach initiated.", logfile = logfile)

    finally:
        NTCP.close_connection()
        sleep(.05)

    tip_tracker(sampling_time = .5, timeout = timeout, velocity_threshold = .001, exit_when_still = True, N_no_motion = 2, verbose = verbose, tracking_info = False) # Use tip tracker to monitor when the approach is done
    if verbose: logprint("Surface detected.", logfile = logfile)

    change_feedback(I = I_old, p_gain = p_gain_old, t_const = t_const_old, withdraw = True) # Change the feedback settings back to the scan settings
    sleep(.4)
    auto_phase() # Autophase the lock-in amplifier to zero
      
    if land_tip:
        adjust_iteration = 0
        in_range = False
        while not in_range and adjust_iteration < 10: # Loop for tip adjustments to get the tip in the desired range
            change_feedback(controller = True) # Land the tip if desired
            txyz = tip_tracker(sampling_time = .5, timeout = 8, exit_when_still = False, N_no_motion = 4, verbose = False, tracking_info = False) # Use tip tracker to gauge where the tip has landed
            z_avg = np.mean(txyz[3, -3:])
            adjust_iteration += 1
            
            if z_avg < z_limits[0]:
                if verbose: logprint(f"Tip landed too low in the z range ({round(z_avg, 3)} nm < {round(z_limits[0], 3)} nm). Adjusting by going down one coarse step.", logfile = logfile)
                change_feedback(withdraw = True)
                coarse_move(steps = 1, direction = "Z-", z_voltage = z_voltage, verbose = False)
            elif z_avg > z_limits[1]:
                if verbose: logprint(f"Tip landed too high in the z range ({round(z_avg, 3)} nm > {round(z_limits[1], 3)} nm). Adjusting by retracting one coarse step.", logfile = logfile)
                change_feedback(withdraw = True)
                coarse_move(steps = 1, direction = "Z+", z_voltage = z_voltage, verbose = False)
            else:
                if verbose: logprint(f"Success! Tip landed in the desired z range ({round(z_limits[0], 3)} nm < {round(z_avg, 3)} nm < {round(z_limits[1])} nm).", logfile = logfile)
                in_range = True
        
        txyz = tip_tracker(sampling_time = .5, timeout = 180, exit_when_still = True, velocity_threshold = velocity_threshold, N_no_motion = 4, verbose = verbose, tracking_info = False) # Use tip tracker to let the drift settle

    try: # Reset the motor voltage if it was changed
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        motor = Motor(NTCP)
        motor.FreqAmpSet(frequency = motor_frequency_old, amplitude = motor_voltage_old)
    
    finally:
        NTCP.close_connection()
        sleep(.05)
        if verbose: logprint("Auto approach sequence completed.", logfile = logfile)

def coarse_move(direction: str = "up", steps: int = 1, xy_voltage: float = 240, z_voltage: float = 210, motor_frequency = False, override: bool = False, verbose: bool = True):
    logfile = get_session_path() + "\\logfile.txt"

    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        motor = Motor(NTCP)
        zcontroller = ZController(NTCP)
        
        motor_frequency_old, motor_voltage_old = motor.FreqAmpGet()
        feedback = bool(zcontroller.OnOffGet())
        if feedback:
            if override:
                if verbose: logprint("Coarse motion attempted with the tip still in feedback. Overridden.", logfile = logfile)
            else:
                if verbose: logprint("Coarse motion attempted with the tip still in feedback. Blocked.", logfile = logfile)
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
        if verbose: logprint("Coarse motion: " + str(steps) + " steps in the " + dirxn + " direction.", logfile = logfile)
        sleep(.05)

    finally:
        NTCP.close_connection()
        sleep(.05)

def move_over(direction: str = "north", steps: int = 20, z_steps: int = 10, I_approach: float = 100, p_gain_approach: float = 40, t_const_approach: float = 167, xy_voltage: float = 240, z_voltage: float = 220, adjust_percentile: float =  75, velocity_threshold: float = .02):
    scan_control(action = "stop")
    I_old, p_gain_old, t_const_old = change_feedback(withdraw = True)
    coarse_move(direction = "lift", steps = z_steps, xy_voltage = xy_voltage, z_voltage = z_voltage)
    coarse_move(direction = direction, steps = steps, xy_voltage = xy_voltage, z_voltage = z_voltage)
    auto_approach(I_approach = I_approach, p_gain_approach = p_gain_approach, t_const_approach = t_const_approach, land_tip = True, adjust_percentile = adjust_percentile, velocity_threshold = velocity_threshold)

def scan_control(action: str = "stop", scan_direction: str = "down", verbose: bool = True, monitor: bool = True, sampling_time: float = 4, velocity_threshold: float = .4):
    logfile = get_session_path() + "\\logfile.txt"

    try:
        NTCP = nanonisTCP(TCP_IP, TCP_PORT, version = version_number) # Initiate the connection and get the module handles
        scan = Scan(NTCP)
        
        if scan_direction != "down": scan_direction = "up"
        if action == "start":
            scan.Action(action, scan_direction)
            if verbose: logprint("Scan started in the " + scan_direction + " direction.", logfile = logfile)
        elif action == "stop":
            scan.Action(action)
            if verbose: logprint("Scan stopped.", logfile = logfile)
        elif action == "pause":
            scan.Action(action)
            if verbose: logprint("Scan paused.", logfile = logfile)
        elif action == "resume":
            scan.Action(action)
            if verbose: logprint("Scan resumed.", logfile = logfile)

    finally:
        NTCP.close_connection()
        sleep(.05)
    
    if action == "start" or action == "resume":
        if monitor: # Continue monitoring the progress of the scan until it is done
            txyz = tip_tracker(sampling_time = sampling_time, velocity_threshold = velocity_threshold, timeout = 100000, exit_when_still = True, N_no_motion = 4, verbose = verbose, monitor_roughness = False)
    return

def scan_mode(mode: str = "topo", bwd_speed: float = 34, verbose: bool = True, topo_channels = np.array(["Z (m)"]), const_height_channels = np.array(["Current (A)", "LI Demod 1 X (A)", "LI Demod 1 Y (A)", "LI Demod 2 X (A)", "LI Demod 2 X (A)"])):
    logfile = get_session_path() + "\\logfile.txt"

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
            if verbose: logprint("Constant height mode activated. Forward scan speed: " + str(round(fwd_speed_old, 3)) + " nm/s. Backward speed: " + str(round(bwd_speed, 3)) + " nm/s.", logfile = logfile)
            target_channel_indices = np.concatenate((channels_old_indices, const_height_channel_indices))
        else:
            scan.SpeedSet(fwd_speed = fwd_speed_old * 1E-9, bwd_speed = fwd_speed_old * 1E-9) # In topographic imaging mode, set the forward and backward speeds equal.
            if verbose: logprint("Topographic imaging mode activated. Forward scan speed: " + str(round(fwd_speed_old, 3)) + " nm/s. Backward speed: " + str(round(fwd_speed_old, 3)) + " nm/s.", logfile = logfile)
            target_channel_indices = np.concatenate((channels_old_indices, topo_channel_indices))
        
        target_channels = [channel_names[index] for index in target_channel_indices]
        #scan.BufferSet(channel_indexes = )
        if verbose: logprint("Recording the following channels: " + "; ".join(target_channels))
        
    finally:
        NTCP.close_connection()
        sleep(.05)


