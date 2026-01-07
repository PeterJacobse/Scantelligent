import re
import os
import numpy as np
import nanonispy2 as nap
from datetime import datetime
import pint



def get_scientific_numbers(text: str) -> list:
    pattern = r"[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?"
    matches = re.findall(pattern, text)
    numbers = [float(x) for x in matches]

    return numbers



def get_basic_header(file_name) -> dict:
    if not os.path.exists(file_name):
        print(f"Error: File \"{file_name}\" does not exist.")
        return False

    root, extension = os.path.splitext(file_name)
    if extension not in [".sxm", ".dat"]:
        print("Error: Unknown file type.")
        return False
    
    ureg = pint.UnitRegistry()

    # Parse the date and time from a spectroscopy (.dat file)
    if extension == ".dat":
        try:
            [x, y, z] = [False for _ in range(3)]

            # Read the file line by line until the tags are found
            with open(file_name, "rb") as file:
                for line in file:
                    decoded = line.decode()

                    if "X (m)" in decoded and not x: x = get_scientific_numbers(decoded)[0]
                    if "Y (m)" in decoded and not y: y = get_scientific_numbers(decoded)[0]
                    if "Z (m)" in decoded and not z: z = get_scientific_numbers(decoded)[0]
                    if "Saved Date" in decoded:
                        try:
                            format_string = "Saved Date\t%d.%m.%Y %H:%M:%S\t"
                            dt_object = datetime.strptime(decoded, format_string)
                        except:
                            pass

                    if x and y and z and dt_object: break
            
            x = ureg.Quantity(x, "m").to("nm")
            y = ureg.Quantity(y, "m").to("nm")
            z = ureg.Quantity(z, "m").to("nm")
            
            header = {
                "x": x,
                "y": y,
                "z": z,
                "coords": [x, y, z],
                "datetime": dt_object
            }

            return header

        except Exception as e:
            print(f"Could not read date and time from .dat file: {e}")
            
            return False

    # Parse the date and time from the header of an SXM file, using the appropriate tags
    if extension == ".sxm":
        try:
            date_tag = ":REC_DATE:"
            time_tag = ":REC_TIME:"
            range_tag = ":SCAN_RANGE:"
            offset_tag = ":SCAN_OFFSET:"
            angle_tag = ":SCAN_ANGLE:"

            date_found = False
            time_found = False
            range_found = False
            offset_found = False
            angle_found = False
            date_line = ""
            time_line = ""
            range_line = ""
            offset_line = ""
            angle_line = ""

            # Read the file line by line until the tags are found
            with open(file_name, "rb") as file:
                for line in file:
                    decoded = line.decode()

                    if date_found and not date_line: date_line = line.decode().strip() # Use .strip() to remove leading/trailing whitespace including newlines
                    if time_found and not time_line: time_line = line.decode().strip()
                    if range_found and not range_line: range_line = line.decode().strip()
                    if offset_found and not offset_line: offset_line = line.decode().strip()
                    if angle_found and not angle_line: angle_line = line.decode().strip()
                    
                    if date_tag in decoded: date_found = True
                    if time_tag in decoded: time_found = True
                    if range_tag in decoded: range_found = True
                    if offset_tag in decoded: offset_found = True
                    if angle_tag in decoded: angle_found = True

                    if date_line and time_line and range_line and offset_line and angle_line: break

            if not (date_line and time_line and range_line and offset_line and angle_line):
                print("Error! Could not parse the header data from hte sxm file")

            # Construct a datetime object from the found date and time
            try:
                date_list = [int(number) for number in date_line.split(".")]
                time_list = [int(number) for number in time_line.split(":")]

                dt_object = datetime(date_list[2], date_list[1], date_list[0], time_list[0], time_list[1], time_list[2])

                scan_range = get_scientific_numbers(range_line)
                offset = get_scientific_numbers(offset_line)
                angle = get_scientific_numbers(angle_line)[0]

                x = ureg.Quantity(offset[0], "m").to("nm")
                y = ureg.Quantity(offset[1], "m").to("nm")
                range_x = ureg.Quantity(scan_range[0], "m").to("nm")
                range_y = ureg.Quantity(scan_range[1], "m").to("nm")
                angle = ureg.Quantity(angle, "degree")

                header = {
                    "x": x,
                    "y": y,
                    "center": [x, y],
                    "height": range_y,
                    "width": range_x,
                    "size": [range_x, range_y],
                    "scan_range": [range_x, range_y],
                    "angle": angle,
                    "datetime": dt_object
                }

                return header
                
            except Exception as e:
                print(f"Error: could not read all data from the .sxm file: {e}")

        except Exception as e:
            print(f"Error: {e}")



def read_files(directory) -> tuple:
    all_files = os.listdir(directory)
    dat_files = [os.path.join(directory, file) for file in all_files if file.endswith(".dat")]
    sxm_files = [os.path.join(directory, file) for file in all_files if file.endswith(".sxm")]

    # Parse the scan files
    scan_list = []
    for file in sxm_files:
        try:
            header = get_basic_header(file)
            date_time = header.get("datetime")
            file_basename = os.path.basename(file)

            scan_list.append([file_basename, file, date_time, header])
        except:
            pass
    scan_list = np.array(scan_list)

    # Parse the spectroscopy files
    spectrum_list = []
    for file in dat_files:
        try:
            header = get_basic_header(file)
            date_time = header.get("datetime")
            file_basename = os.path.basename(file)
            x = header.get("x")
            y = header.get("y")
            z = header.get("z")
            
            # The '0' elements are placeholders that will be replaced by the file names of the associated scans
            spectrum_list.append([file_basename, file, date_time, 0, x, y, z])
        except:
            pass
    spectrum_list = np.array(spectrum_list)
    no_spectra = len(spectrum_list)

    # Associate spectra with scans
    for spectrum_index in range(no_spectra):
        spectrum_time = spectrum_list[spectrum_index, 2]
        spectrum_recorded_after_scan = spectrum_time > scan_list[:, 2] # List of Trues for scans recorded before the spectrum, and Falses for scans recorded after the spectrum
        spectrum_after_scan_indices = np.where(spectrum_recorded_after_scan)[0] # Find the Trues
        if len(spectrum_after_scan_indices) > 0: # If not empty (i.e. spectrum recorded before the first scan)
            associated_spectrum = spectrum_after_scan_indices[-1] # The last True is the scan associated with the spectrum
            spectrum_list[spectrum_index, 3] = scan_list[associated_spectrum, 0]

    return (scan_list, spectrum_list)



def get_scan(file_name, units: dict = {"length": "m", "current": "A"}, default_channel_units: dict = {"X": "m", "Y": "m", "Z": "m", "Current": "A", "LI Demod 1 X": "A", "LI Demod 1 Y": "A", "LI Demod 2 X": "A", "LI Demod 2 Y": "A"}) -> object:
    if not os.path.exists(file_name):
        print(f"Error: File \"{file_name}\" does not exist.")
        return

    root, extension = os.path.splitext(file_name)
    if extension != ".sxm":
        print("Error: attempting to open a scan that is not an sxm file.")
        return

    try:
        scan_object = nap.read.Scan(file_name) # Read the scan data. scan_data is an object whose attributes contain all the data of the scan
        scans = scan_object.signals # Read the scans
        channels = np.array(list(scan_object.signals.keys())) # Read the channels

        scan_header = scan_object.header
        up_or_down = scan_header.get("scan_dir", "down") # Read whether the scan was recorded in the upward or downward direction
        pixels_uncropped = scan_header.get("scan_pixels", np.array([100, 100], dtype = int)) # Read the number of pixels in the scan
        scan_range_uncropped = scan_header.get("scan_range", np.array([1E-8, 1E-8], dtype = float)) # Read the size of the scan
        bias = round(float(scan_header.get("bias", 0)), 3) # Get the bias (present in the header as a string, passed more directly as a float)
        z_controller = scan_header.get("z-controller") # Extract and convert z-controller parameters
        feedback = bool(z_controller.get("on")[0]) # Bool, true or false
        setpoint_str = z_controller.get("Setpoint")[0]
        angle = scan_header.get("scan_angle")
        offset = scan_header.get("scan_offset")
        
        # Extract and convert time parameters and convert to datetime object
        rec_date = [int(element) for element in scan_header.get("rec_date", "00.00.1900").split(".")]
        rec_time = [int(element) for element in scan_header.get("rec_time", "00:00:00").split(":")]
        dt_object = datetime(rec_date[2], rec_date[1], rec_date[0], rec_time[0], rec_time[1], rec_time[2])
        
        ureg = pint.UnitRegistry()
        bias_unitized = ureg.Quantity(bias, "V")
        scan_range_uncropped_unitized = [ureg.Quantity(range_dim, "m") for range_dim in scan_range_uncropped]

        # Deprecate this after completing the switch to pint:
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
                if channel in length_channels: scans[channel][direction] = np.array(scans[channel][direction] * L_multiplication_factor, dtype = float)
                elif channel in current_channels: scans[channel][direction] = np.array(scans[channel][direction] * I_multiplication_factor, dtype = float)
        
        # Stack the forward and backward scans for each channel in a tensor. Flip the backward scan
        scan_tensor_uncropped = np.stack([np.stack((np.array(scans[channel]["forward"], dtype = float), np.flip(np.array(scans[channel]["backward"], dtype = float), axis = 1))) for channel in channels])
        if up_or_down == "up": scan_tensor_uncropped = np.flip(scan_tensor_uncropped, axis = 2) # Flip the scan if it recorded in the upward direction
        # scan_tensor: axis 0 = direction (0 for forward, 1 for backward); axis 1 = channel; axis 2 and 3 are x and y

        # Determine which rows should be cropped off in case the scan was not completed
        masked_array = np.isnan(scan_tensor_uncropped[0, 1]) # All channels have the same number of NaN values. The backward scan has more NaN values because the scan always starts in the forward direction.
        nan_counts = np.array([sum([int(masked_array[j, i]) for i in range(len(masked_array))]) for j in range(len(masked_array[0]))])
        good_rows = np.where(nan_counts == 0)[0]
        scan_tensor = np.array([[scan_tensor_uncropped[channel, 0, good_rows], scan_tensor_uncropped[channel, 1, good_rows]] for channel in range(len(channels))])
        
        pixels = np.asarray(np.shape(scan_tensor[0, 0])) # The number of pixels is recalculated on the basis of the scans potentially being cropped
        scan_range = np.array([scan_range_uncropped[0] * pixels[0] / pixels_uncropped[0], scan_range_uncropped[1]]) # Recalculate the size of the slow scan direction after cropping
        scan_range_unitized = [ureg.Quantity(range_dim, "m").to("nm") for range_dim in scan_range]
        
        # Apply the re-unitization to various attributes in the header
        scan_range = [scan_dimension * L_multiplication_factor for scan_dimension in scan_range]
        setpoint_unitized = ureg.Quantity(float(setpoint_str.split()[0]), "A").to("pA")
        
        x_center = ureg.Quantity(float(offset[0]), "m").to("nm")
        y_center = ureg.Quantity(float(offset[1]), "m").to("nm")
        angle = ureg.Quantity(float(angle), "degree")
        center = [x_center, y_center]

        # Add new attributes to the scan object
        setattr(scan_object, "default_channel_units", default_channel_units)
        setattr(scan_object, "channel_units", channel_units)
        setattr(scan_object, "units", units)
        setattr(scan_object, "bias", bias_unitized)
        setattr(scan_object, "channels", channels)
        setattr(scan_object, "tensor_uncropped", scan_tensor_uncropped) # Uncropped means the size of the scan before deleting the rows that were not recorded
        setattr(scan_object, "pixels_uncropped", pixels_uncropped)
        setattr(scan_object, "scan_range_uncropped", scan_range_uncropped)
        setattr(scan_object, "scan_range_uncropped_unitized", scan_range_uncropped_unitized)
        setattr(scan_object, "tensor", scan_tensor)
        setattr(scan_object, "pixels", pixels)
        setattr(scan_object, "scan_range", scan_range_unitized)
        setattr(scan_object, "feedback", feedback)
        setattr(scan_object, "setpoint", setpoint_unitized)
        setattr(scan_object, "date_time", dt_object)
        setattr(scan_object, "angle", angle)
        setattr(scan_object, "x", x_center)
        setattr(scan_object, "y", y_center)
        setattr(scan_object, "center", center)
        setattr(scan_object, "offset", center)
    
        return scan_object

    except Exception as e:
        print(f"Error reading sxm file: {e}")
        
        return False



def get_spectrum(file_name) -> object:
    if not os.path.exists(file_name):
        print(f"Error: File \"{file_name}\" does not exist.")
        return

    root, extension = os.path.splitext(file_name)
    if extension != ".dat":
        print("Error: attempting to open a spectroscopy file that is not a dat file.")
        return

    try:
        spec_object = nap.read.Spec(file_name)
        spec_spectra = spec_object.signals
        spec_header = spec_object.header

        ureg = pint.UnitRegistry()
        spec_coords = np.array([spec_header.get("X (m)", 0), spec_header.get("Y (m)", 0), spec_header.get("Z (m)", 0)], dtype = float)
        # Unitize the spectrum coordinates and switch to nm by default
        spec_coords = [ureg.Quantity(coordinate, "m").to("nm") for coordinate in spec_coords]
        [spec_date, spec_time] = spec_header.get("Start time").split()
    
        # Extract and convert time parameters and convert to datetime object
        rec_date = [int(element) for element in spec_date.split(".")]
        rec_time = [int(element) for element in spec_time.split(":")]
        dt_object = datetime(rec_date[2], rec_date[1], rec_date[0], rec_time[0], rec_time[1], rec_time[2])
        
        channels = np.array(list(spec_spectra.keys()), dtype = str)
        spectrum_matrix = np.array(list(spec_spectra.values()))

        # Add the new attributes to the scan object
        # Redundant attribute names for the coordinates are for ease of use
        setattr(spec_object, "coords", spec_coords)
        setattr(spec_object, "location", spec_coords)
        setattr(spec_object, "position", spec_coords)
        setattr(spec_object, "x", spec_coords[0])
        setattr(spec_object, "y", spec_coords[1])
        setattr(spec_object, "z", spec_coords[2])
        setattr(spec_object, "channels", channels)
        setattr(spec_object, "matrix", spectrum_matrix)
        setattr(spec_object, "date_time", dt_object)
    
        return spec_object
    
    except Exception as e:
        print(f"Error: {e}")
        
        return False