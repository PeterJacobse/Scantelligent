import os
import numpy as np
import nanonispy2 as nap
from scipy.signal import convolve2d
from datetime import datetime
from types import SimpleNamespace

def get_scan(file_name, units: dict = {"length": "m", "current": "A"}, default_channel_units: dict = {"X": "m", "Y": "m", "Z": "m", "Current": "A", "LI Demod 1 X": "A", "LI Demod 1 Y": "A", "LI Demod 2 X": "A", "LI Demod 2 Y": "A"}):
    if not os.path.exists(file_name):
        print(f"Error: File \"{file_name}\" does not exist.")
        return
    else:
        scan_data = nap.read.Scan(file_name) # Read the scan data. scan_data is an object whose attributes contain all the data of the scan
        channels = np.array(list(scan_data.signals.keys())) # Read the channels
        scan_header = scan_data.header
        up_or_down = scan_header.get("scan_dir", "down") # Read whether the scan was recorded in the upward or downward direction
        pixels_uncropped = scan_header.get("scan_pixels", np.array([100, 100], dtype = int)) # Read the number of pixels in the scan
        scan_range_uncropped = scan_header.get("scan_range", np.array([1E-8, 1E-8], dtype = float)) # Read the size of the scan
        bias = round(float(scan_header.get("bias", 0)), 3) # Get the bias (present in the header as a string, passed more directly as a float)
        z_controller = scan_header.get("z-controller") # Extract and convert z-controller parameters
        feedback = bool(z_controller.get("on")[0]) # Bool, true or false
        setpoint_str = z_controller.get("Setpoint")[0]
        
        # Extract and convert time parameters and convert to datetime object
        rec_date = [int(element) for element in scan_data.header.get("rec_date", "00.00.1900").split(".")]
        rec_time = [int(element) for element in scan_data.header.get("rec_time", "00:00:00").split(":")]
        dt_object = datetime(rec_date[2], rec_date[1], rec_date[0], rec_time[0], rec_time[1], rec_time[2])
        
        # Compute the re-unitization factors
        # Lengths
        channel_units = default_channel_units.copy() # Initialize channel_units to the default setting
        match units.get("length", "m"):
            case "m": L_multiplication_factor = 1
            case "dm": L_multiplication_factor = 10
            case "cm": L_multiplication_factor = 100
            case "mm": L_multiplication_factor = 1E3
            case "um": L_multiplication_factor = 1E6
            case "nm": L_multiplication_factor = 1E9
            case "A": L_multiplication_factor = 1E10
            case "pm": L_multiplication_factor = 1E12
            case "fm": L_multiplication_factor = 1E15
            case _: L_multiplication_factor = 1
        if L_multiplication_factor == 1: units["length"] = "m" # Fall back to m
     
        # Current
        match units.get("current", "A"):
            case "A": I_multiplication_factor = 1
            case "dA": I_multiplication_factor = 10
            case "cA": I_multiplication_factor = 100
            case "mA": I_multiplication_factor = 1E3
            case "uA": I_multiplication_factor = 1E6
            case "nA": I_multiplication_factor = 1E9
            case "pA": I_multiplication_factor = 1E12
            case "fA": I_multiplication_factor = 1E15
            case _: I_multiplication_factor = 1
        if I_multiplication_factor == 1: units["current"] = "A" # Fall back to A
        
        # Update the unit in channel_units (which will now be different from default_channel_units)
        length_channels = [key for key, value in default_channel_units.items() if value == "m"]
        current_channels = [key for key, value in default_channel_units.items() if value == "A"]
        for channel in length_channels:
            if channel in channel_units: channel_units[channel] = units.get("length", "m")
        for channel in current_channels:
            if channel in channel_units: channel_units[channel] = units.get("current", "A")
        filtered_channel_units = {str(key): channel_units[key] for key in channels if key in channel_units} # Remove channels that are not present in the scan
        channel_units = filtered_channel_units
        
        # Rescale the scan data by the multiplication factors determined in the reunitization        
        for channel in channels:
            for direction in ["forward", "backward"]:
                if channel in length_channels: scan_data.signals[channel][direction] = np.array(scan_data.signals[channel][direction] * L_multiplication_factor, dtype = float)
                elif channel in current_channels: scan_data.signals[channel][direction] = np.array(scan_data.signals[channel][direction] * I_multiplication_factor, dtype = float)
        
        # Stack the forward and backward scans for each channel in a tensor. Flip the backward scan
        scan_tensor_uncropped = np.stack([np.stack((np.array(scan_data.signals[channel]["forward"], dtype = float), np.flip(np.array(scan_data.signals[channel]["backward"], dtype = float), axis = 1))) for channel in channels])
        if up_or_down == "up": scan_tensor_uncropped = np.flip(scan_tensor_uncropped, axis = 2) # Flip the scan if it recorded in the upward direction
        # scan_tensor: axis 0 = direction (0 for forward, 1 for backward); axis 1 = channel; axis 2 and 3 are x and y

        # Determine which rows should be cropped off in case the scan was not completed
        masked_array = np.isnan(scan_tensor_uncropped[0, 1]) # All channels have the same number of NaN values. The backward scan has more NaN values because the scan always starts in the forward direction.
        nan_counts = np.array([sum([int(masked_array[j, i]) for i in range(len(masked_array))]) for j in range(len(masked_array[0]))])
        good_rows = np.where(nan_counts == 0)[0]
        scan_tensor = np.array([[scan_tensor_uncropped[channel, 0, good_rows], scan_tensor_uncropped[channel, 1, good_rows]] for channel in range(len(channels))])
        
        pixels = np.asarray(np.shape(scan_tensor[0, 0])) # The number of pixels is recalculated on the basis of the scans potentially being cropped
        scan_range = np.array([scan_range_uncropped[0] * pixels[0] / pixels_uncropped[0], scan_range_uncropped[1]]) # Recalculate the size of the slow scan direction after cropping
        
        # Apply the re-unitization to various attributes in the header
        scan_range = [scan_dimension * L_multiplication_factor for scan_dimension in scan_range]
        setpoint = float(setpoint_str.split()[0]) * I_multiplication_factor

        # Add new attributes to the scan object
        setattr(scan_data, "default_channel_units", default_channel_units)
        setattr(scan_data, "channel_units", channel_units)
        setattr(scan_data, "units", units)
        setattr(scan_data, "bias", bias)
        setattr(scan_data, "channels", channels)
        setattr(scan_data, "scan_tensor_uncropped", scan_tensor_uncropped) # Uncropped means the size of the scan before deleting the rows that were not recorded
        setattr(scan_data, "pixels_uncropped", pixels_uncropped)
        setattr(scan_data, "scan_range_uncropped", scan_range_uncropped)
        setattr(scan_data, "scan_tensor", scan_tensor)
        setattr(scan_data, "pixels", pixels)
        setattr(scan_data, "scan_range", scan_range)
        setattr(scan_data, "feedback", feedback)
        setattr(scan_data, "setpoint", setpoint)
        setattr(scan_data, "date_time", dt_object)

        return scan_data

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
    elif mode == "average":
        return image - avg_image
    else:
        return image

def get_image_statistics(image, pixels_per_bin: int = 200):
    data_sorted = np.sort(image.flatten())
    n_pixels = len(data_sorted)
    data_firsthalf = data_sorted[:int(n_pixels / 2)]
    data_secondhalf = data_sorted[-int(n_pixels / 2):]

    range_mean = np.mean(data_sorted) # Calculate the mean
    Q1 = np.mean(data_firsthalf) # Calculate the first and third quartiles
    Q2 = data_secondhalf[0] # Q2 is the median
    Q3 = np.mean(data_secondhalf)
    range_min, range_max = (data_sorted[0], data_sorted[-1]) # Calculate the total range
    range_total = range_max - range_min
    standard_deviation = np.sum(np.sqrt((data_sorted - range_mean) ** 2) / n_pixels) # Calculate the standard deviation
    
    n_bins = int(np.floor(n_pixels / pixels_per_bin))
    counts, bounds = np.histogram(data_sorted, bins = n_bins)
    binsize = bounds[1] - bounds[0]
    padded_counts = np.pad(counts, 1, mode = "constant")
    bincenters = np.concatenate([[bounds[0] - .5 * binsize], np.convolve(bounds, [.5, .5], mode = "valid"), [bounds[-1] + .5 * binsize]])
    histogram = np.array([bincenters, padded_counts])

    image_statistics = SimpleNamespace()
    
    setattr(image_statistics, "data_sorted", data_sorted)
    setattr(image_statistics, "n_pixels", n_pixels)
    setattr(image_statistics, "min", range_min)
    setattr(image_statistics, "Q1", Q1)
    setattr(image_statistics, "mean", range_mean)
    setattr(image_statistics, "average", range_mean)
    setattr(image_statistics, "Q2", Q2)
    setattr(image_statistics, "median", Q2)
    setattr(image_statistics, "Q3", Q3)
    setattr(image_statistics, "max", range_max)
    setattr(image_statistics, "range_total", range_total)
    setattr(image_statistics, "standard_deviation", standard_deviation)
    setattr(image_statistics, "histogram", histogram)
    
    return image_statistics