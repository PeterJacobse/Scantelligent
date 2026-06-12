import re, os, sys, yaml, pint, h5py
import importlib.util
import numpy as np
import nanonispy2 as nap
from datetime import datetime
from .data_processing import DataProcessing



class FileFunctions():
    def __init__(self):
        self.ureg = pint.UnitRegistry()
        self.data = DataProcessing()



    # IO
    def read_file(self, file_path: str) -> dict:
        output = {}
        match os.path.splitext(file_path)[1]:
            case ".hdf5" | ".h5": output = self.read_hdf5(file_path)
            case ".sxm": output = self.read_sxm(file_path)
            case _: print("I do not know how to read this file")        
        return output
    
    def read_hdf5(self, file_path: str) -> dict:
        if not os.path.isfile(file_path):
            print("Invalid file path provided to read_hdf5")
            return {}
        
        output_dict = {"file_path": file_path}
        frame = None
        array = None
        main_group = None
        axes_names = []
        axis_data = {}

        try:
            with h5py.File(file_path, "r") as f:
                """
                Parsing the root
                """
                # Write root-level attributes to output file
                root_attrs = {key: value for key, value in f.attrs.items()}
                output_dict.update(root_attrs)
                
                # Open groups at the root level
                root_items = {key: value for key, value in f.items()}
                
                # Trying to find the frame (or grid) at the root level
                for obj in ["frame", "grid"]:
                    if not obj in root_items.keys(): continue
                    
                    input_frame = {key: value for key, value in root_items[obj].attrs.items()}
                    frame = self.convert_to_sct_frame(input_frame)
                    if not "scan_range (nm)" in frame.keys(): frame = None
                
                # Trying to find the measurement channels at the root level
                for tag in ["channels", "channel_names"]:
                    if tag in root_items.keys(): channels = main_group[tag].asstr()[:]

                # Read the attributes from all groups. At the same time, try to find the main (Nexus) measurement group while reading the different groups.
                for group_name, group in root_items.items():                
                    if "NX_class" in group.attrs.keys():
                        main_group = root_items[group_name]
                        continue
                    
                    group_dict = {key: value for key, value in group.attrs.items()}
                    output_dict.update({group_name: group_dict})
                
                # Fall back to recognizing group tags. If nothing works: break
                if not main_group:
                    recognized_tags = ["session", "session_group", "main", "main_group", "sweep", "sweep_group", "scan", "scan_group",
                                       "measurement", "measurement_group", "spectrum", "spectrum_group", "spectroscopy", "spectroscopy_group", "data", "data_group"]
                    for group_tag in recognized_tags:
                        if group_tag in root_items.keys():
                            main_group = root_items[group_tag]
                            break
                if not main_group: return(output_dict)
                
                
                
                """
                Parsing the main group
                """
                # If the frame was not yet found at the root level, try to find it at the main group level
                if not frame and main_group:
                    for obj in ["frame", "grid"]:
                        if not obj in main_group.keys(): continue
                        
                        input_frame = {key: value for key, value in main_group[obj].attrs.items()}
                        frame = self.convert_to_sct_frame(input_frame)
                        if not "scan_range (nm)" in frame.keys(): frame = None
                if isinstance(frame, dict): output_dict.update({"frame": frame})

                # Retrieve the signal and axes
                if "signal" in main_group.attrs.keys():
                    signal_name = main_group.attrs.get("signal", "")
                    if isinstance(signal_name, bytes): signal_name = signal_name.decode("utf-8")
                                    
                    array = main_group[signal_name][:]
                    output_dict.update({"signal": signal_name, "array": array})

                if "axes" in main_group.attrs.keys():
                    axes_attr = main_group.attrs.get("axes")
                    if isinstance(axes_attr, bytes): axes_names.append(axes_attr.decode("utf-8"))
                    elif isinstance(axes_attr, (list, tuple)): axes_names = [ax.decode("utf-8") if isinstance(ax, bytes) else ax for ax in axes_attr]
                    elif hasattr(axes_attr, "tolist"): axes_names = [ax.decode("utf-8") if isinstance(ax, bytes) else ax for ax in axes_attr.tolist()]

                    # Try to swap out indices of axes for names wherever possible
                    for axis_index, axis_name in enumerate(axes_names): # Loop over axis names
                        split_name = axis_name.split()
                        if not "indices" in split_name[-1]:
                            axis_data.update({axis_name: main_group[axis_name][:]})
                            continue
                        
                        quantity = " ".join(split_name[:-1]) # Discard 'indices' from the name
                        for new_name in main_group.keys(): # Loop over main group items and find data whose name matches the quantity without 'indices'
                            if new_name == axis_name or not quantity in new_name: continue
                            
                            new_axis_data = main_group[new_name].asstr()[:]
                            axis_data.update({new_name: new_axis_data})
                            axes_names[axis_index] = new_name
                
                    output_dict.update({"axes": axes_names, "axes_data": axis_data})



                # If Nexus parsing failed: extract the scan or spectroscopy data
                if not isinstance(array, np.ndarray):
                    recognized_tags = ["main", "sweep", "scan", "measurement", "spectrum", "spectroscopy", "data", "array"]
                    for tag in recognized_tags:
                        if tag in main_group.keys():
                            array = main_group[tag][:]
                            output_dict.update({"array": array})
                            break
                
                shape = array.shape
                rank = len(shape)
                """
                match rank:
                    case 2: # The data represents a flat image or 1D input-output sweep
                        pass
                    case 3: # The data represents a multi-channel dataset or 2D spectroscopy experiment
                        for channel_index, channel_name in enumerate(channels):
                            (channel_quantity, channel_unit, backward, error) = file_functions.split_physical_quantity(channel_name)
                            target_unit = "nm"
                            match channel_unit[-1]:
                                case "m": target_unit = "nm"
                                case "A": target_unit = "pA"                                
                                case "S": target_unit = "nS"
                                case "F": target_unit = "fF"
                                case _: target_unit = channel_unit
                            (converted_slice, new_quantity) = file_functions.convert_data_to_unit(data[direction_index, channel_index], channel_name, target_unit)
                            data[direction_index, channel_index, :, :] = converted_slice
                            channels[channel_index] = new_quantity
                    case 4: # The data represents multiple 3D datasets, possibly one for each scan direction or spin direction
                        for direction_index, data_slice_3D in enumerate(data):
                            for channel_index, channel_name in enumerate(channels):
                                (channel_quantity, channel_unit, backward, error) = file_functions.split_physical_quantity(channel_name)
                                target_unit = "nm"
                                match channel_unit[-1]:
                                    case "m": target_unit = "nm"
                                    case "A": target_unit = "pA"                                
                                    case "S": target_unit = "nS"
                                    case "F": target_unit = "fF"
                                    case _: target_unit = channel_unit
                                (converted_slice, new_quantity) = file_functions.convert_data_to_unit(data[direction_index, channel_index], channel_name, target_unit)
                                data[direction_index, channel_index, :, :] = converted_slice
                                channels[channel_index] = new_quantity
                    case _: # I am not sure how to interpret these data
                        pass
                """
        except Exception as e: print(f"Problem encountered while reading HDF5 file: {e}")
        finally:
            pass
        return output_dict

    def read_sxm(self, file_path: str, convert_to_sct_units: bool = True) -> dict:
        (header, file_data) = self.full_sxm_header_read(file_path)
        [pixels, lines, channels, up_or_down] = [file_data.get(key) for key in ["pixels", "lines", "channels", "up_or_down"]]

        n_directions = 2
        n_channels = len(channels)
        axes = ["directions", "channels", "x (nm)", "y (nm)"]
        axes_data = {"directions": ["forward", "backward"], "channels": channels}
        file_data.update({"raw_header": header, "axes": axes, "axes_data": axes_data})
        
        try:
            output_array = np.empty((n_directions, n_channels, pixels, lines), dtype = np.float32)
            chunk_size = 256
            tag = b":SCANIT_END:"
            tag_len = len(tag)

            with open(file_path, "rb") as f:
                # First locate the tag
                current_pos = 0
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break

                    idx = chunk.find(tag)
                    if idx != -1:
                        tag_pos = current_pos + idx
                    
                    if len(chunk) == chunk_size:
                        f.seek(1 - tag_len, 1)  # 1 means relative to current position
                        current_pos += chunk_size - tag_len + 1
                    else:
                        current_pos += len(chunk)
                    
                # Move the pointer, then read the scan data
                f.seek(tag_pos + tag_len + 5)

                new_channels = channels
                for channel_index, channel_name in enumerate(channels):
                    for direction_index in range(2):
                        float_array = np.fromfile(f, dtype = ">f4", count = int(pixels * lines))
                        image_slice = float_array.reshape(lines, pixels).transpose()
                        
                        if convert_to_sct_units:
                            new_channel_name = self.convert_data_to_unit(image_slice, channel_name)
                            new_channels[channel_index] = new_channel_name
                        
                        match (up_or_down, direction_index):
                            case ("up", 0): output_array[direction_index, channel_index] = image_slice
                            case ("up", 1): output_array[direction_index, channel_index] = np.flipud(image_slice)
                            case (_, 0): output_array[direction_index, channel_index] = np.fliplr(image_slice)
                            case (_, 1): output_array[direction_index, channel_index] = np.flipud(np.fliplr(image_slice))
            
            if convert_to_sct_units:
                axes_data.update({"channels": new_channels})
                file_data.update({"axes_data": axes_data})
            file_data.update({"array": output_array})
        except Exception as e:
            print(f"Problem reading .sxm file: {e}")
        return file_data

    def save_yaml(self, data, path: str) -> bool | str:
        error = False

        try: # Save the currently opened scan folder to the config yaml file so it opens automatically on startup next time
            with open(path, "w") as file:
                yaml.safe_dump(data, file)
        except Exception as e:
            error = f"Failed to save to yaml: {e}"
        
        return error

    def load_yaml(self, path: str) -> tuple[object, bool | str]:
        error = False
        yaml_data = {}
        
        try: # Read the last scan file from the config yaml file
            with open(path, "r") as file:
                yaml_data = yaml.safe_load(file)
        except Exception as e:
            error = e

        return (yaml_data, error)

    def save_files_dict(self, files_dict: dict, folder: str) -> bool:
        error = False
        
        clean_scan_dict = {"dict_name": "scan_files"}
        clean_spec_dict = {"dict_name": "spectroscopy_files"}

        try:
            spec_dict = files_dict.get("spectroscopy_files")
            scan_dict = files_dict.get("scan_files")
            path = os.path.join(folder, "metadata.yml")
            
            # Parse the scan dictionary
            for key, single_file_dict in scan_dict.items():
                if not isinstance(single_file_dict, dict): continue # Pass the dict_name entry; only parse single_file dictionaries
                
                allowed_entries = ["frame", "date_time_str", "path", "file_name"] # Allowed entries for saving to yaml
                clean_single_file_dict = {entry: single_file_dict.get(entry) for entry in allowed_entries}
                clean_single_file_dict.update({"dict_name": "single_file_dict"})
                
                clean_scan_dict.update({key: clean_single_file_dict})
            
            # Parse the spectroscopy dictionary
            for key, single_file_dict in spec_dict.items():
                if not isinstance(single_file_dict, dict): continue # Pass the dict_name entry; only parse single_file dictionaries
                
                allowed_entries = ["x (nm)", "y (nm)", "z (nm)", "date_time_str", "path", "file_name", "associated_scan_name", "associated_scan_path"] # Allowed entries for saving to yaml
                clean_single_file_dict = {entry: single_file_dict.get(entry) for entry in allowed_entries}
                clean_single_file_dict.update({"dict_name": "single_file_dict"})
                
                clean_spec_dict.update({key: clean_single_file_dict})
            
            # Compose the new files_dict
            clean_files_dict = {
                "dict_name": "files_dict",
                "scan_files": clean_scan_dict,
                "spectroscopy_files": clean_spec_dict
            }
            
            error = self.save_yaml(clean_files_dict, path)
            if error:
                print(f"Error: {e}")
                raise Exception(error)
        except Exception as e:
            error = e
        
        return error

    def find_experiment_files(self, directory: str):
        all_files = os.listdir(directory)
        python_files = [os.path.join(directory, file) for file in all_files if file.endswith(".py")]
        
        found_files = []
        
        # Iterate through each file and search for the string "class Experiment"
        for file_path in python_files:
            try:
                with open(file_path, 'r', encoding = 'utf-8') as f:
                    if "class Experiment" in f.read():
                        found_files.append(os.path.basename(file_path)[:-3])
            except Exception as e:
                print(f"Could not read file {file_path}: {e}")
                
        return found_files

    def load_experiment_from_file(self, file_path: str, hw_config: dict = {}, experiment_file: str = "", scantelligent_folder: str = "", scan_processing_flags = None, nanonis: object = None, mla: object = None):
        """
        Finds and instantiates the 'Experiment' class from a specific file.
        """
        file_name = os.path.basename(file_path)
        module_name = file_name.split('.')[0] # Use filename as module name

        # 1. Load the module dynamically
        spec = importlib.util.spec_from_file_location(module_name, file_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        # 2. Get the 'Experiment' class and instantiate it
        experiment = getattr(module, "Experiment")        
        return experiment(hw_config = hw_config, experiment_file = experiment_file, scantelligent_folder = scantelligent_folder, scan_processing_flags = scan_processing_flags, nanonis = nanonis, mla = mla)



    # Misc
    def split_physical_quantity(self, text: str) -> tuple:
        error = False
        quantity = None
        unit = None
        backward = False
        first_bracket_index = None
        
        try:
            split_text = text.split()
            for index, text_item in enumerate(split_text):
                if text_item.startswith("(") | text_item.startswith("["):
                    if not first_bracket_index: first_bracket_index = index
                    if text_item[1:-1] in {"bwd", "backward"}: backward = True
                    if text_item[1:-1] not in {"fwd", "forward", "bwd", "backward"}: unit = text_item[1:-1]
            quantity = " ".join(split_text[:first_bracket_index])

            return (quantity, unit, backward, error)
        except:
            error = True
        
        return (quantity, unit, backward, error)

    def convert_data_to_unit(self, data: np.ndarray, quantity: str, target_unit: str = None) -> str:
        output_data = data
        output_quantity = quantity
        input_multiplier = 1
        target_multiplier = 1
        
        try:
            (input_quantity, input_unit, backward, error) = self.split_physical_quantity(quantity)
            
            if not target_unit:
                match input_unit[-1]:
                    case "A": target_unit = "pA"
                    case "m": target_unit = "nm"
                    case "S": target_unit = "nS"
                    case "V": target_unit = "V"
                    case _: target_unit = input_unit
            
            if len(input_unit) > 1 and input_unit[0] in {"f", "p", "n", "u", "m", "k", "M", "G"}:
                input_prefix = input_unit[0]
                match input_prefix:
                    case "f": input_multiplier = 1E-15
                    case "p": input_multiplier = 1E-12
                    case "n": input_multiplier = 1E-9
                    case "u": input_multiplier = 1E-6
                    case "m": input_multiplier = 1E-3
                    case "k": input_multiplier = 1E3
                    case "M": input_multiplier = 1E6
                    case "G": input_multiplier = 1E9
                    case _: pass
            
            if len(target_unit) > 1 and target_unit[0] in {"f", "p", "n", "u", "m", "k", "M", "G"}:
                target_prefix = target_unit[0]
                match target_prefix:
                    case "f": target_multiplier = 1E15
                    case "p": target_multiplier = 1E12
                    case "n": target_multiplier = 1E9
                    case "u": target_multiplier = 1E6
                    case "m": target_multiplier = 1E3
                    case "k": target_multiplier = 1E-3
                    case "M": target_multiplier = 1E-6
                    case "G": target_multiplier = 1E-9
                    case _: pass
            
            data *= (input_multiplier * target_multiplier)
            output_quantity = " ".join((input_quantity, f"({target_unit})"))
        except Exception as e:
            print(f"Error encountered while trying to convert data ({quantity}) to unit {target_unit}: {e}")
        return output_quantity

    def convert_to_sct_frame(self, frame: dict) -> dict:
        w_nm = None
        h_nm = None
        x_nm = None
        y_nm = None

        output_dict = {}
        for key, value in frame.items():
            (quantity, unit, backward, error) = self.split_physical_quantity(key)
            if not quantity or not unit: continue

            match quantity.lower():
                case "translation" | "center" | "offset":
                    array = np.array(value, dtype = np.float32)
                    quantity = self.convert_data_to_unit(array, key, "nm")
                    output_dict.update({"offset (nm)": array, "center (nm)": array})
                case "size" | "scan_size" | "area" | "scan_area" | "range" | "scan_range" | "scan range" | "domain" | "scan_domain":
                    array = np.array(value, dtype = np.float32)
                    quantity = self.convert_data_to_unit(array, key, "nm")
                    output_dict.update({"scan_range (nm)": array, "domain (nm)": array})
                
                case "w" | "width" | "range_x" | "x_range" | "x range" | "size_x" | "x_size":
                    array = np.array(value, dtype = np.float32)
                    quantity = self.convert_data_to_unit(array, key, "nm")
                    w_nm = float(array)
                case "h" | "height" | "range_y" | "y_range" | "y range" | "size_y" | "y_size":
                    array = np.array(value, dtype = np.float32)
                    quantity = self.convert_data_to_unit(array, key, "nm")
                    h_nm = float(array)

                case "x" | "x_value" | "x_val" | "x_offset" | "offset_x" | "x_center" | "center_x":
                    array = np.array(value, dtype = np.float32)
                    quantity = self.convert_data_to_unit(array, key, "nm")
                    x_nm = float(array)
                case "y" | "y_value" | "y_val" | "y_offset" | "offset_y" | "y_center" | "center_y":
                    array = np.array(value, dtype = np.float32)
                    quantity = self.convert_data_to_unit(array, key, "nm")
                    y_nm = float(array)

                case "angle":
                    if unit == "rad": output_value = np.rad2deg(value)
                    else: output_value = value
                    output_dict.update({"angle (deg)": ((output_value + 180) % 360 - 180)})
                case _:
                    pass

            if not "offset (nm)" in output_dict.keys() and x_nm and y_nm: output_dict.update({"offset (nm)": np.array([x_nm, y_nm], dtype = np.float32)})
            if not "scan_range (nm)" in output_dict.keys() and w_nm and h_nm: output_dict.update({"scan_range (nm)": np.array([w_nm, h_nm], dtype = np.float32)})
            
            if not "angle (deg)" in output_dict.keys(): output_dict.update({"angle (deg)": 0.})
            if "pixels" in frame.keys(): output_dict.update({"pixels": int(frame["pixels"])})
            if "lines" in frame.keys(): output_dict.update({"lines": int(frame["lines"])})
        return output_dict

    def get_scientific_numbers(self, text: str) -> list:
        pattern = r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?"
        matches = re.findall(pattern, text)
        numbers = [float(x) for x in matches]
        return numbers

    def get_next_indexed_filename(self, folder_path, base_name, extension) -> str:
        # Pattern to match files with the base name and exactly 3 digits for the index
        # \d{3} matches exactly three digits
        pattern = rf"^{re.escape(base_name)}_(\d{{3}}){re.escape(extension)}$"
        
        # List all files in the directory
        try:
            files = os.listdir(folder_path)
        except FileNotFoundError:
            # If the folder doesn't exist, the first file will be index 000
            return f"{base_name}_000{extension}"

        matching_indices = []
        for filename in files:
            match = re.match(pattern, filename)
            if match: matching_indices.append(int(match.group(1)))

        max_index = 0
        next_index = 0
        if matching_indices:
            # If files were found, find the highest index
            max_index = max(matching_indices)
            next_index = max_index + 1
            
        # Format the next index to be a 3-digit string with leading zeros if necessary
        current_formatted_index = f"{max_index:03d}"
        next_formatted_index = f"{next_index:03d}"
        
        return [f"{base_name}_{current_formatted_index}{extension}", f"{base_name}_{next_formatted_index}{extension}"]



    # To be deprecated
    def get_basic_header(self, file_name: str) -> tuple[dict, bool | str]:
        error = False
        header = {}

        if not os.path.exists(file_name):
            error = f"Error: File \"{file_name}\" does not exist."
            return (header, error)

        root, extension = os.path.splitext(file_name)
        if extension not in [".sxm", ".dat"]:
            error = "Error: Unknown file type."
            return (header, error)

        # Parse the date and time from a spectroscopy (.dat file)
        if extension == ".dat":
            try:
                [x, y, z] = [False for _ in range(3)]

                # Read the file line by line until the tags are found
                with open(file_name, "rb") as file:
                    for line in file:
                        decoded = line.decode()

                        if "X (m)" in decoded and not x: x = self.get_scientific_numbers(decoded)[0]
                        if "Y (m)" in decoded and not y: y = self.get_scientific_numbers(decoded)[0]
                        if "Z (m)" in decoded and not z: z = self.get_scientific_numbers(decoded)[0]
                        if "Saved Date" in decoded:
                            try:
                                format_string = "Saved Date\t%d.%m.%Y %H:%M:%S\t"
                                dt_object = datetime.strptime(decoded, format_string)
                            except:
                                pass

                        if x and y and z and dt_object: break
                
                x = self.ureg.Quantity(x, "m").to("nm")
                y = self.ureg.Quantity(y, "m").to("nm")
                z = self.ureg.Quantity(z, "m").to("nm")
                
                header = {
                    "x": x,
                    "y": y,
                    "z": z,
                    "coords": [x, y, z],
                    "date_time": dt_object
                }

                return (header, error)

            except Exception as e:
                error = f"Could not read date and time from .dat file: {e}"
                
                return (header, error)

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

                    scan_range = self.get_scientific_numbers(range_line)
                    offset = self.get_scientific_numbers(offset_line)
                    angle = self.get_scientific_numbers(angle_line)[0]

                    x = self.ureg.Quantity(offset[0], "m").to("nm")
                    y = self.ureg.Quantity(offset[1], "m").to("nm")
                    range_x = self.ureg.Quantity(scan_range[0], "m").to("nm")
                    range_y = self.ureg.Quantity(scan_range[1], "m").to("nm")
                    angle = self.ureg.Quantity(angle, "degree")

                    header = {
                        "x": x,
                        "y": y,
                        "center": [x, y],
                        "offset": [x, y],
                        "height": range_y,
                        "width": range_x,
                        "size": [range_x, range_y],
                        "scan_range": [range_x, range_y],
                        "angle": angle,
                        "date_time": dt_object
                    }

                    return (header, error)
                    
                except Exception as e:
                    error = f"Error: could not read all data from the .sxm file: {e}"
                    return (header, error)

            except Exception as e:
                error = f"Error: {e}"
                return (header, error)



    # Raw file functions
    def minimal_sxm_header_read(self, file_path: str) -> tuple[np.ndarray, dict]:
        try:
            (raw_header, end_pos) = self.get_raw_sxm_header(file_path)
            header = np.array(raw_header, dtype = np.str_)

            nanonis_tags = [":SCAN_RANGE:\n", ":SCAN_ANGLE:\n", ":SCAN_OFFSET:\n", ":REC_TIME:\n", ":REC_DATE:\n", ":SCAN_PIXELS:\n", ":SCAN_DIR:\n", ":BIAS:\n"]
            sct_tags = ["scan_range (m)", "angle (deg)", "offset (m)", "start_time", "scan_date", "grid_size", "up_or_down", "V_nanonis (V)"]

            sct_dict = {}
            for nanonis_tag, sct_tag in zip(nanonis_tags, sct_tags):
                try:
                    index = np.where(header == nanonis_tag)[0][0]
                    values_split = header[index + 1].split()

                    if nanonis_tag in [":REC_TIME:\n", ":REC_DATE:\n", ":SCAN_DIR:\n"]:
                        sct_dict.update({sct_tag: values_split[0]})
                    else:
                        values_num = [self.get_scientific_numbers(value)[0] for value in values_split]
                        if len(values_num) < 2: values_num = values_num[0]
                        sct_dict.update({sct_tag: values_num})
                except Exception as e:
                    print(f"Problem reading tag {nanonis_tag.split()[0]} from .sxm file")
        except Exception as e:
            print(f"Error getting the SXM file header: {e}")
        return (header, sct_dict)

    def full_sxm_header_read(self, file_path: str) -> tuple[np.ndarray, dict]:
        (header_array, sct_dict) = self.minimal_sxm_header_read(file_path)
        [pixels, lines] = [int(sct_dict.get("grid_size", [1, 1])[i]) for i in range(2)]
        sct_dict.update({"pixels": pixels, "lines": lines})
        
        frame = self.convert_to_sct_frame(sct_dict)
        sct_dict.update({"frame": frame})

        # Z_controller
        try:
            z_controller_index = np.where(header_array == ":Z-CONTROLLER:\n")[0][0]
            z_controller_data = header_array[z_controller_index + 2].split("\t")
            [_, z_controller_name, feedback, setpoint, p_gain, i_gain, t_const] = z_controller_data
            sct_dict.update({"z_controller": {"name": z_controller_name, "feedback": bool(feedback), "setpoint": setpoint, "p_gain": p_gain, "i_gain": i_gain, "t_const": t_const}})
        except Exception as e:
            print(f"Problem retrieving z-controller data from .sxm file: {e}")

        # Channels
        try:
            channel_data_index = np.where(header_array == ":DATA_INFO:\n")[0][0]
            channel_names = []
            for channel_index in range(100):
                channel_data = header_array[channel_data_index + 2 + channel_index].split()
                if len(channel_data) < 1: break
                [channel_index, quantity, unit, direction, calibration, offset] = channel_data
                channel_names.append(" ".join((quantity, f"({unit})")))
            
            sct_dict.update({"channels": channel_names})
        except Exception as e:
            print(f"Problem retrieving channel data from .sxm file: {e}")
        return (header_array, sct_dict)

    def create_empty_files_dict(self, directory_name: str) -> tuple[dict, bool | str]:
        error = False
        files_dict = {"dict_name": "files_dict"} # Self reference to facilitate the app recognizing what kind of dictionary this is
        
        if os.path.isfile(directory_name): directory_name = os.path.dirname(directory_name)
        if not os.path.isdir(directory_name):
            error = "No valid directory was provided"
            return (files_dict, error)
        
        try:
            all_files = os.listdir(directory_name)
            dat_files = [os.path.join(directory_name, file) for file in all_files if file.endswith(".dat")]
            sxm_files = [os.path.join(directory_name, file) for file in all_files if file.endswith(".sxm")]

            # Set up dictionaries
            scans_dict = {"dict_name": "scan_files"} # Self reference to facilitate the app recognizing what kind of dictionary this is
            specs_dict = {"dict_name": "spectroscopy_files"}

            # Iterate over the sxm files (scan files)
            for index, file in enumerate(sxm_files):
                file_basename = os.path.basename(file)
                single_file_dict = {
                    "dict_name": "single_file_dict", # Self reference to facilitate the app recognizing what kind of dictionary this is
                    "file_name": file_basename,
                    "path": file
                }
                scans_dict.update({index: single_file_dict})
            
            # Iterate over the dat files (potential spectroscopy files)            
            for index, file in enumerate(dat_files):
                file_basename = os.path.basename(file)
                single_file_dict = {
                    "dict_name": "single_file_dict",
                    "file_name": file_basename,
                    "path": file
                }
                specs_dict.update({index: single_file_dict})
    
        except Exception as e:
            error = e
            return (files_dict, error)
                
        # Create and return the dictionary
        files_dict.update({
            "scan_files": scans_dict,
            "spectroscopy_files": specs_dict
        })
        
        return (files_dict, error)

    def get_spectroscopy_header(self, file_name: str) -> tuple[dict, bool | str]:
        error = False
        header = {}
        [x, y, z, dt_object] = [False for _ in range(4)]
        
        try:
            # Read the file line by line until the tags are found
            line_count = 0
            with open(file_name, "rb") as file:
                for line in file:
                    decoded = line.decode()

                    (quantity, unit, backward_bool, error) = self.split_physical_quantity(decoded)
                    if not error and isinstance(quantity, str):
                        match quantity.lower():
                            case "x":
                                x_magnitude = self.get_scientific_numbers(decoded)[0]
                                x = self.ureg.Quantity(x_magnitude, unit)
                            case "y":
                                y_magnitude = self.get_scientific_numbers(decoded)[0]
                                y = self.ureg.Quantity(y_magnitude, unit)
                            case "z":
                                z_magnitude = self.get_scientific_numbers(decoded)[0]
                                z = self.ureg.Quantity(z_magnitude, unit)
                            case _:
                                pass

                    if "Saved Date" in decoded:
                        try:
                            format_string = "Saved Date\t%d.%m.%Y %H:%M:%S\t"
                            dt_object = datetime.strptime(decoded, format_string)
                        except:
                            pass
                        
                    # Found all tags
                    if x and y and z and dt_object: break
                
                # One of the tags was not found
                if not x or not y or not z or not dt_object:
                    error = True
                    return (header, error)
            
            # x_nm, y_nm, z_nm are the (unitless) magnitudes of the pint Quantities when expressed in nm
            x_nm = x.to("nm").magnitude
            y_nm = y.to("nm").magnitude
            z_nm = z.to("nm").magnitude
            
            dt_str = dt_object.strftime("%Y-%m-%d %H:%M:%S")
            
            header = {
                "x": x,
                "y": y,
                "z": z,
                
                "x (nm)": x_nm,
                "y (nm)": y_nm,
                "z (nm)": z_nm,
                
                "coords": [x, y, z],
                "location": [x, y, z],
                "position": [x, y, z],
                
                "coords (nm)": [x_nm, y_nm, z_nm],
                "location (nm)": [x_nm, y_nm, z_nm],
                "position (nm)": [x_nm, y_nm, z_nm],
                
                "date_time": dt_object,
                "date_time_str": dt_str
            }

            return (header, error)

        except Exception as e:
            error = f"Could not read date and time from .dat file: {e}"
            
            return (header, error)

    def populate_spectroscopy_headers(self, files_dict: dict) -> tuple[dict, bool | str]:
        error = False
        new_files_dict = {"dict_name": "files_dict"}
        new_spec_dict = {"dict_name": "spectroscopy_files"}
        
        try:
            scan_dict = files_dict.get("scan_files")
            spec_dict = files_dict.get("spectroscopy_files")
            
            for key, value in spec_dict.items():
                if not isinstance(value, dict): continue # The dict_name entry is of type str and should be ignored
                file_name = value.get("path")
                (header, error) = self.get_spectroscopy_header(file_name)
                                
                if not error:
                    value.update(header)
                    new_spec_dict.update({key: value})

            # Update the total files_dict
            error = False
            new_files_dict.update({"scan_files": scan_dict, "spectroscopy_files": new_spec_dict})
        
        except Exception as e:
            error = e

        return (new_files_dict, error)

    def get_raw_sxm_header(self, file_name: str) -> tuple[list, bool | str]:
        error = False
        header_end_tag = ":SCANIT_END:"
        raw_header = []
        
        try:
            with open(file_name, "rb") as file:
                for line in file:
                    decoded = line.decode()
                    
                    raw_header.append(decoded)
                    if header_end_tag in decoded: break
        except Exception as e:
            error = e
        
        return (raw_header, error)

    def parse_scan_header(self, header_list: list) -> tuple[dict, bool | str]:
        error = False
        header = {}
        
        try:
            date_tag = ":REC_DATE:"
            time_tag = ":REC_TIME:"
            range_tag = ":SCAN_RANGE:"
            offset_tag = ":SCAN_OFFSET:"
            angle_tag = ":SCAN_ANGLE:"
            
            date_line = ""
            time_line = ""
            range_line = ""
            offset_line = ""
            angle_line = ""

            # Read the file line by line until the tags are found
            for index, line in enumerate(header_list):                
                if date_tag in line: date_line = header_list[index + 1]
                if time_tag in line: time_line = header_list[index + 1]
                if range_tag in line: range_line = header_list[index + 1]
                if offset_tag in line: offset_line = header_list[index + 1]
                if angle_tag in line: angle_line = header_list[index + 1]

                if date_line and time_line and range_line and offset_line and angle_line: break

            if not (date_line and time_line and range_line and offset_line and angle_line):
                error = "Could not parse the header data from the sxm file"
                return (header, error)

            # Construct a datetime object from the found date and time
            date_list = [int(number) for number in date_line.split(".")]
            time_list = [int(number) for number in time_line.split(":")]
            dt_object = datetime(date_list[2], date_list[1], date_list[0], time_list[0], time_list[1], time_list[2])

            scan_range = self.get_scientific_numbers(range_line)
            offset = self.get_scientific_numbers(offset_line)
            angle = self.get_scientific_numbers(angle_line)[0]

            x = self.ureg.Quantity(offset[0], "m").to("nm")
            y = self.ureg.Quantity(offset[1], "m").to("nm")
            width = self.ureg.Quantity(scan_range[0], "m").to("nm")
            height = self.ureg.Quantity(scan_range[1], "m").to("nm")
            scan_range = [width, height]
            angle = self.ureg.Quantity(angle, "degree")
            
            x_nm = x.magnitude
            y_nm = y.magnitude
            offset_nm = [x_nm, y_nm]
            width_nm = width.magnitude
            height_nm = height.magnitude
            scan_range_nm = [width_nm, height_nm]
            angle_deg = angle.magnitude
            dt_str = dt_object.strftime("%Y-%m-%d %H:%M:%S")

            header = {
                "dict_name": "single_file_dict",
                "x": x,
                "y": y,
                "center": [x, y],
                "offset": [x, y],
                "height": height,
                "width": width,
                "size": scan_range,
                "scan_range": scan_range,
                "angle": angle,
                "date_time": dt_object,
                "date_time_str": dt_str,

                "frame": {
                    "dict_name": "frame_dict",
                    "offset (nm)": offset_nm,
                    "scan_range (nm)": scan_range_nm,
                    "angle_deg": angle_deg                    
                }
            }
            return (header, error)
        
        except Exception as e:
            error = e
        
        return (header, error)

    def populate_scan_headers(self, files_dict: dict) -> tuple[dict, bool | str]:
        new_files_dict = {"dict_name": "files_dict"}
        new_scan_dict = {"dict_name": "scan_files"}
        
        try:
            scan_dict = files_dict.get("scan_files")
            spec_dict = files_dict.get("spectroscopy_files")
            
            for key, value in scan_dict.items():
                if not isinstance(value, dict): continue # The dict_name entry is of type str and should be ignored
                file_name = value.get("path")
                (raw_header, error) = self.get_raw_sxm_header(file_name)
                if error:
                    continue
                else:
                    (header, error) = self.parse_scan_header(raw_header)
                    
                    if not error:
                        value.update(header)
                        new_scan_dict.update({key: value})

            # Update the total files_dict
            error = False
            new_files_dict.update({"scan_files": new_scan_dict, "spectroscopy_files": spec_dict})
        
        except Exception as e:
            error = e

        return (new_files_dict, error)

    def populate_associated_scans(self, files_dict: dict) -> tuple[dict, bool | str]:
        error = False
        new_files_dict = files_dict

        try:
            scan_dict = files_dict.get("scan_files")
            spec_dict = files_dict.get("spectroscopy_files")

            for spec_key, spec_file_dict in spec_dict.items():
                if not isinstance(spec_file_dict, dict): continue
                
                # Find the time at which the spectrum was acquired
                spec_time = spec_file_dict.get("date_time")
                
                # Loop over all scans
                previous_scan = None
                for scan_key, scan_file_dict in scan_dict.items():
                    if not isinstance(scan_file_dict, dict): continue
                    
                    # Find the time at which the scan was acquired
                    scan_time = scan_file_dict.get("date_time")
                    
                    # If the scan was acquired before the spectrum, it may be associated with it: check at the next iteration
                    if scan_time < spec_time:
                        previous_scan = scan_file_dict
                    # If the scan was acquired after the spectrum, the previous scan was associated with the spectrum
                    else:
                        if previous_scan: spec_file_dict.update({
                            "associated_scan_name": previous_scan.get("file_name"),
                            "associated_scan_path": previous_scan.get("path"),
                            })
                
                spec_dict.update({spec_key: spec_file_dict})
            
            new_files_dict.update({"spectroscopy_files": spec_dict})
        except Exception as e:
            error = e
        
        return (new_files_dict, error)

    def get_spectroscopy_object(self, file_name: str) -> tuple[object, bool | str]:
        error = False
        spec_object = None
        
        try:
            spec_object = nap.read.Spec(file_name)
            spec_spectra = spec_object.signals
            spec_header = spec_object.header
            new_spec_header = spec_header.copy()
            
            # Extract physical quantitiies and create copies with the preferred nm, pA, s units
            for key, value in spec_header.items():
                (quantity, unit, backward_bool, error) = self.split_physical_quantity(key)
                if not error:
                    match unit:
                        case "m":
                            try:
                                number = self.get_scientific_numbers(value)[0]
                                new_spec_header.update({f"{quantity} (nm)": number * 1E9})
                            except:
                                pass
                        case "s":
                            try:
                                number = self.get_scientific_numbers(value)[0]
                                new_spec_header.update({f"{quantity} (s)": number})
                            except:
                                pass
                        case "A":
                            try:
                                number = self.get_scientific_numbers(value)[0]
                                new_spec_header.update({f"{quantity} (pA)": number * 1E12})
                            except:
                                pass
                        case _:
                            pass

            spec_coords = np.array([spec_header.get("X (m)", 0), spec_header.get("Y (m)", 0), spec_header.get("Z (m)", 0)], dtype = float)
            
            # Unitize the spectrum coordinates and switch to nm by default
            spec_coords = [self.ureg.Quantity(coordinate, "m").to("nm") for coordinate in spec_coords]
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
        
        except Exception as e:
            error = f"Error: {e}"
        
        return (spec_object, error)

    def populate_spec_objects(self, files_dict: dict) -> tuple[dict, bool | str]:
        error = False
        new_files_dict = files_dict

        try:
            scan_dict = files_dict.get("scan_files")
            spec_dict = files_dict.get("spectroscopy_files")

            for spec_key, spec_file_dict in spec_dict.items():
                if not isinstance(spec_file_dict, dict): continue
                
                spec_path = spec_file_dict.get("path")
                (spec_object, error) = self.get_spectroscopy_object(spec_path)
                
                if not error:
                    channels = spec_object.channels
                    spec_file_dict.update({"spec_object": spec_object, "channels": channels})
            
            new_files_dict.update({"spectroscopy_files": spec_dict})
        except Exception as e:
            error = e
        
        return (new_files_dict, error)

    def read_files(self, directory: str) -> tuple:
        error = False

        all_files = os.listdir(directory)
        dat_files = [os.path.join(directory, file) for file in all_files if file.endswith(".dat")]
        sxm_files = [os.path.join(directory, file) for file in all_files if file.endswith(".sxm")]

        # Parse the scan files
        scan_list = []
        for file in sxm_files:
            try:
                header = self.get_basic_header(file)
                date_time = header.get("date_time")
                file_basename = os.path.basename(file)

                scan_list.append([file_basename, file, date_time, header])
            except Exception as e:
                error = e
        
        scan_list = np.array(scan_list)

        # Parse the spectroscopy files
        spectrum_list = []
        for file in dat_files:
            try:
                header = self.get_basic_header(file)
                date_time = header.get("date_time")
                file_basename = os.path.basename(file)
                x = header.get("x")
                y = header.get("y")
                z = header.get("z")
                
                # The '0' elements are placeholders that will be replaced by the file names of the associated scans
                spectrum_list.append([file_basename, file, date_time, 0, x, y, z])
            except Exception as e:
                error = e
        
        spectrum_list = np.array(spectrum_list)
        no_spectra = len(spectrum_list)

        # Associate spectra with scans
        try:
            for spectrum_index in range(no_spectra):
                spectrum_time = spectrum_list[spectrum_index, 2]
                spectrum_recorded_after_scan = spectrum_time > scan_list[:, 2] # List of Trues for scans recorded before the spectrum, and Falses for scans recorded after the spectrum
                spectrum_after_scan_indices = np.where(spectrum_recorded_after_scan)[0] # Find the Trues
                if len(spectrum_after_scan_indices) > 0: # If not empty (i.e. spectrum recorded before the first scan)
                    associated_spectrum = spectrum_after_scan_indices[-1] # The last True is the scan associated with the spectrum
                    spectrum_list[spectrum_index, 3] = scan_list[associated_spectrum, 0]
        except Exception as e:
            error = e



        # Set up dictionaries
        scans_dict = {}
        specs_dict = {}

        try:
            for index, sxm_file in enumerate(scan_list):
                header = sxm_file[3]
                scan_range = header.get("scan_range")
                scan_range_nm = [dim.to("nm").magnitude for dim in scan_range]
                offset = header.get("offset")
                offset_nm = [dim.to("nm").magnitude for dim in offset]
                angle = header.get("angle")

                sxm_dict = {
                    "file_name": sxm_file[0],
                    "path": sxm_file[1],
                    "date_time": sxm_file[2].strftime("%Y-%m-%d %H:%M:%S"),
                    "frame": {
                        "scan_range (nm)": f"({scan_range_nm[0]:.3f}, {scan_range_nm[1]:.3f})",
                        "offset (nm)": f"({offset_nm[0]:.3f}, {offset_nm[1]:.3f})",
                        "angle (deg)": f"{angle:.3f}"
                        }
                }
                scans_dict.update({index: sxm_dict})
            
            for index, spec_file in enumerate(spectrum_list):
                scan_range = header.get("scan_range")
                scan_range_nm = [dim.to("nm").magnitude for dim in scan_range]
                offset = header.get("offset")
                offset_nm = [dim.to("nm").magnitude for dim in offset]
                angle = header.get("angle")

                dat_dict = {
                    "file_name": spec_file[0],
                    "path": spec_file[1],
                    "date_time": spec_file[2].strftime("%Y-%m-%d %H:%M:%S"),
                    "position": {
                        "x (nm)": f"{spec_file[4]:.3f}",
                        "y (nm)": f"{spec_file[5]:.3f}",
                        "z (nm)": f"{spec_file[6]:.3f}"
                        }
                }
                specs_dict.update({index: dat_dict})

            files_dict = {
                "scan_files": scans_dict,
                "spectroscopy_files": specs_dict
            }
        except Exception as e:
            error = e

        return (scan_list, spectrum_list, files_dict, error)

    def get_scan(self, file_name, units: dict = {"length": "m", "current": "A"}, default_channel_units: dict = {"X": "m", "Y": "m", "Z": "m", "Current": "A", "LI Demod 1 X": "A", "LI Demod 1 Y": "A", "LI Demod 2 X": "A", "LI Demod 2 Y": "A"}) -> tuple[object, bool | str]:
        error = False

        if not os.path.exists(file_name):
            error = f"Error: File \"{file_name}\" does not exist."
            return (error, error)

        root, extension = os.path.splitext(file_name)
        if extension != ".sxm":
            error = "Error: attempting to open a scan that is not an sxm file."
            return (error, error)

        try:
            scan_object = nap.read.Scan(file_name) # Read the scan data. scan_data is an object whose attributes contain all the data of the scan
            scans = scan_object.signals # Read the scans
            scan_header = scan_object.header
            data_info = scan_header.get("data_info")
                                    
            # Attach the units to the scan array keys
            chan_names = np.array(data_info.get("Name"))
            chan_units = np.array(data_info.get("Unit"))
            unitized_scans = {}
            for scan_channel, scan_array in scans.items():
                if scan_channel in chan_names:
                    index = np.where(scan_channel == chan_names)[0][0]
                    channel_unit = chan_units[index]
                    
                    # Translate to preferred units
                    match channel_unit:
                        case "A":
                            channel_unit = "pA"
                            for array in scan_array.values(): array *= 1E12
                        case "m":
                            channel_unit = "nm"                            
                            for array in scan_array.values(): array *= 1E9
                        case _:
                            pass
                    unitized_scans.update({f"{scan_channel} ({channel_unit})": scan_array})
                else:
                    unitized_scans.update({f"{scan_channel}": scan_array})
            scans = unitized_scans
            channels = np.array(list(scans.keys())) # Read the channels. Only the quantity names are returned, no units
            
            
            
            up_or_down = scan_header.get("scan_dir", "down") # Read whether the scan was recorded in the upward or downward direction
            (pixels, lines_uncropped) = scan_header.get("scan_pixels", np.array([100, 100], dtype = int)) # Read the number of pixels in the scan
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
            
            bias_unitized = self.ureg.Quantity(bias, "V")
            scan_range_uncropped_unitized = [self.ureg.Quantity(range_dim, "m") for range_dim in scan_range_uncropped]

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
            #for channel in channels:
            #    for direction in ["forward", "backward"]:
            #        if channel in length_channels: scans[channel][direction] = np.array(scans[channel][direction] * L_multiplication_factor, dtype = float)
            #        elif channel in current_channels: scans[channel][direction] = np.array(scans[channel][direction] * I_multiplication_factor, dtype = float)
          
            # Stack the forward and backward scans for each channel in a tensor. Flip the backward scan
            scan_tensor_uncropped = np.stack([np.stack((np.array(scans[channel]["forward"], dtype = float), np.flip(np.array(scans[channel]["backward"], dtype = float), axis = 1))) for channel in channels])
            if up_or_down == "down": scan_tensor_uncropped = np.flip(scan_tensor_uncropped, axis = 2) # Flip the scan if it recorded in the upward direction
            # scan_tensor: axis 0 = direction (0 for forward, 1 for backward); axis 1 = channel; axis 2 and 3 are x and y

            # Determine which rows should be cropped off in case the scan was not completed
            masked_array = np.isnan(scan_tensor_uncropped[0, 1]) # All channels have the same number of NaN values. The backward scan has more NaN values because the scan always starts in the forward direction.
            nan_counts = np.array([sum([int(masked_array[j, i]) for i in range(len(masked_array))]) for j in range(len(masked_array[0]))])
            good_rows = np.where(nan_counts == 0)[0]
            scan_tensor = np.array([[scan_tensor_uncropped[channel, 0, good_rows], scan_tensor_uncropped[channel, 1, good_rows]] for channel in range(len(channels))])
            
            # Recalculate the scan range on the basis of the fraction of leftover lines (after cropping) to lines before cropping
            [lines, pixels] = np.shape(scan_tensor[0, 0]) # The number of pixels is recalculated on the basis of the scans potentially being cropped
            scan_range = np.array([scan_range_uncropped[0], scan_range_uncropped[1] * lines / lines_uncropped]) # Recalculate the size of the slow scan direction after cropping
            scan_range_unitized = [self.ureg.Quantity(range_dim, "m").to("nm") for range_dim in scan_range]

            # Apply the re-unitization to various attributes in the header
            setpoint_unitized = self.ureg.Quantity(float(setpoint_str.split()[0]), "A").to("pA")
            
            x_center = self.ureg.Quantity(float(offset[0]), "m").to("nm")
            y_center = self.ureg.Quantity(float(offset[1]), "m").to("nm")
            angle = self.ureg.Quantity(float(angle), "degree")
            center = [x_center, y_center]
            
            x_nm = x_center.magnitude
            y_nm = y_center.magnitude
            center_nm = [dim.magnitude for dim in center]
            angle_deg = angle.magnitude
            scan_range_nm = [dim.magnitude for dim in scan_range_unitized]
            frame = {
                "x (nm)": x_nm,
                "y (nm)": y_nm,
                "center (nm)": center_nm,
                "offset (nm)": center_nm,                
                "scan_range (nm)": scan_range_nm,
                "angle (deg)": angle_deg
            }

            # Add new attributes to the scan object
            setattr(scan_object, "default_channel_units", default_channel_units)
            setattr(scan_object, "channel_units", channel_units)
            setattr(scan_object, "units", units)
            setattr(scan_object, "bias", bias_unitized)
            setattr(scan_object, "channels", channels)
            setattr(scan_object, "tensor_uncropped", scan_tensor_uncropped) # Uncropped means the size of the scan before deleting the rows that were not recorded
            setattr(scan_object, "pixels_uncropped", pixels)
            setattr(scan_object, "lines_uncropped", lines_uncropped)
            setattr(scan_object, "scan_range_uncropped", scan_range_uncropped)
            setattr(scan_object, "scan_range_uncropped_unitized", scan_range_uncropped_unitized)
            setattr(scan_object, "tensor", scan_tensor)
            setattr(scan_object, "pixels", pixels)
            setattr(scan_object, "lines", lines)
            setattr(scan_object, "scan_range", scan_range_unitized)
            setattr(scan_object, "feedback", feedback)
            setattr(scan_object, "setpoint", setpoint_unitized)
            setattr(scan_object, "date_time", dt_object)
            setattr(scan_object, "angle", angle)
            setattr(scan_object, "x", x_center)
            setattr(scan_object, "y", y_center)
            setattr(scan_object, "center", center)
            setattr(scan_object, "offset", center)
            setattr(scan_object, "frame", frame)
        
            return (scan_object, error)

        except Exception as e:
            error = f"Error reading sxm file: {e}"
            return (error, error)

    def get_spectrum(self, file_name: str) -> tuple[object, bool | str]:
        error = False
        spec_object = None
        
        if not isinstance(file_name, str):
            error = "Provided file_name was not a valid string"
            return (spec_object, error)

        if not os.path.exists(file_name):
            error = f"Error: File \"{file_name}\" does not exist."
            return (spec_object, error)

        root, extension = os.path.splitext(file_name)
        if extension != ".dat":
            error = "Error: attempting to open a spectroscopy file that is not a dat file."
            return (spec_object, error)

        try:
            spec_object = nap.read.Spec(file_name)
            spec_spectra = spec_object.signals
            spec_header = spec_object.header

            spec_coords = np.array([spec_header.get("X (m)", 0), spec_header.get("Y (m)", 0), spec_header.get("Z (m)", 0)], dtype = float)
            
            # Unitize the spectrum coordinates and switch to nm by default
            spec_coords = [self.ureg.Quantity(coordinate, "m").to("nm") for coordinate in spec_coords]
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
        
        except Exception as e:
            error = f"Error: {e}"
        
        return (spec_object, error)

