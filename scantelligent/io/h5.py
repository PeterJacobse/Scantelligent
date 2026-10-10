import re, os, sys, yaml, pint, h5py, inspect
from typing import Literal
import importlib.util
from contextlib import contextmanager
import numpy as np
import nanonispy2 as nap
from datetime import datetime, timezone
from .file_picker import get_file_path_from_dialog



@contextmanager
def read_file(file_path: str = ""):
    if not file_path: file_path = get_file_path_from_dialog(extensions = ["h5", "hdf5"])
    
    if not os.path.isfile(file_path):
        print(f"Invalid file path provided to read_file: {file_path}")
        yield False
        return

    ext = os.path.splitext(file_path)
    if not ext[1].lower() in {".h5", ".hdf5"}:
        print(f"Provided file path is not an HDF5 file: {file_path}")
        yield False
        return
    
    try:
        root = h5py.File(file_path, "r")
        yield root
    finally:
        root.close()
    return

@contextmanager
def write_file(file_path: str = "", label_root: bool = True):
    try:
        root = h5py.File(file_path, "w")
        if label_root: create_attributes(root, {"NX_class": "NXroot"})
        yield root
    finally:
        root.close()
    return

@contextmanager
def append_file(file_path: str = ""):
    if not file_path: file_path = get_file_path_from_dialog(extensions = ["h5", "hdf5"])

    if not os.path.isfile(file_path):
        print(f"Invalid file path provided to append_file: {file_path}")
        yield False
        return
    
    try:
        root = h5py.File(file_path, "a")
        yield root
    finally:
        root.close()
    return

def get_attributes(h5object: h5py.File | h5py.Group | h5py.Dataset) -> dict:
    return {key: value for key, value in h5object.attrs.items()}

def get_groups(root_or_group: h5py.File | h5py.Group) -> dict:
    return {key: value for key, value in root_or_group.items() if isinstance(value, h5py.Group)}

def get_datasets(root_or_group: h5py.File | h5py.Group) -> dict:
    return {key: value for key, value in root_or_group.items() if isinstance(value, h5py.Dataset)}

def get_items(root_or_group: h5py.File | h5py.Group) -> dict:
    return {key: value for key, value in root_or_group.items()}

def create_attributes(h5object: h5py.File | h5py.Group | h5py.Dataset, attributes: dict = {}) -> None:
    for key, value in attributes.items():
        try:
            if isinstance(value, str): h5object.attrs.create(key, value, dtype = h5py.string_dtype(encoding = "utf-8"))
            else: h5object.attrs[key] = value
        except: pass
    return

def create_group(root_or_group: h5py.File | h5py.Group, name: str = "", *, attributes: dict = {}) -> h5py.Group:
    try:
        new_group = root_or_group.create_group(name)
        create_attributes(new_group, attributes)
        return new_group
    except:
        raise Exception(f"Error encountered while attempting to create a new h5py group called {name} under {root_or_group}")

def get_entry_group(root: h5py.File, name: str = "Measurement_000", verbose: bool = False) -> h5py.Group:
    """Finds the entry group in an HDF5 file, first by searching for the default tag at the root, then by trying to find the NXentry tags in the groups at the root level. If the entry group does not exist, it is created.

    Args:
        root (h5py.File): HDF5 file
        name (str, optional): Name of the entry group: only relevant when creating a new group. Defaults to "Measurement_000".
        verbose (bool, optional): Whether to output messages. Defaults to False.

    Returns:
        h5py.Group: The entry group
    """
    try:
        root_attributes = get_attributes(root)
        root_groups = get_groups(root)
        
        if "default" in root_attributes.keys(): # Cases where the root has the default attribute that is supposed to point to an entry group
            entry_group_name = root_attributes["default"]
            
            if verbose: print(f"Entry group {entry_group_name} was found from the 'default' tag at the root.")
            if entry_group_name in root_groups.keys(): # Case 1: The default attribute in the root points to a valid entry group
                entry_group = root_groups[entry_group_name]
                if verbose: print(f"Entry group is valid ({entry_group = }).")
                
                entry_group_attrs = get_attributes(entry_group)
                if not "NX_class" in entry_group_attrs.keys(): create_attributes(entry_group, {"NX_class": "NXentry"})
                return entry_group
            else:
                if verbose: print(f"Entry group is invalid.")
        
        for group_name, group in root_groups.items():
            group_attrs = get_attributes(group)
            group_class = group_attrs.get("NX_class", None)
            if group_class == "NXentry":
                entry_group = group
                if verbose: print(f"Entry group {group_name} was found from its NX_class tag.")
                create_attributes(root, {"default": group_name})
                if verbose: print(f"The 'default' tag was added to the root to point to the entry group.")
                return entry_group

        if verbose: print(f"No valid entry group was found. Creating a new entry group")
        create_attributes(root, {"default": name})
        entry_group = create_group(root, name, attributes = {"NX_class": "NXentry"})        
        return entry_group
    
    except Exception as e:
        raise Exception(f"Error encountered while finding or creating an entry group: {e}")

def create_data_group(root_or_group: h5py.File | h5py.Group, name: str = "", *, attributes: dict = {}) -> h5py.Group:
    try:
        attributes.update({"NX_class": "NXdata"})
        new_group = create_group(root_or_group, name, attributes = attributes)
        return new_group
    except:
        raise Exception(f"Error encountered while attempting to create a new h5py group called {name} under {root_or_group}")

def create_instrument(root: h5py.File, name: str = "", *, long_name: str = "", vendor: str = "", attributes: dict = {}) -> h5py.Group:
    try:
        attributes.update({"NX_class": "NXinstrument"})
        if vendor: attributes.update({"vendor": vendor})
        if long_name: attributes.update({"long_name": long_name})
        
        instrument_group = create_group(root, name, attributes = attributes)
        return instrument_group
    except Exception as e:
        raise Exception(f"Error encountered while attempting to create a new h5py group called {name} under {root}: {e}")

def create_thumbnail_group(root_or_group: h5py.File | h5py.Group, *, attributes: dict = {}) -> h5py.Group:
    try:
        attributes.update({"NX_class": "NXimage"})
        new_group = create_group(root_or_group, "Thumbnail", attributes = attributes)
        return new_group
    except:
        raise Exception(f"Error encountered while attempting to create a new h5py group called \"thumbnail\" under {root_or_group}")

def create_dataset(root_or_group: h5py.File | h5py.Group, name: str = "", *, units: str | None = None, attributes: dict = {}, data: np.ndarray | None = None,
                    dtype: np.typing.DTypeLike | None = None, shape: tuple | None = None, maxshape: tuple | int | None = None, **kwargs) -> h5py.Dataset:
    try:
        if dtype is None and isinstance(data, np.ndarray): parsed_dtype = data.dtype
        else: parsed_dtype = np.dtype(dtype)
        
        match parsed_dtype.kind:
            case "U":
                char_len = parsed_dtype.itemsize // 4
                target_dtype = h5py.string_dtype(encoding = "utf-8", length = char_len if char_len > 0 else None)
            case "S" | "O":
                target_dtype = h5py.string_dtype(encoding = "utf-8")
            case "i" | "u" | "f" | "b":
                target_dtype = parsed_dtype
            case _:
                raise TypeError(f"Unsupported data type family for h5py: {parsed_dtype}")
        
        if isinstance(data, np.ndarray):
            if parsed_dtype.kind == "U":
                dataset = root_or_group.create_dataset(name, shape = data.shape, dtype = target_dtype, **kwargs)
                dataset[...] = data.astype("O")
            else:
                dataset = root_or_group.create_dataset(name, data = data, dtype = target_dtype, **kwargs)
        else:
            dataset = root_or_group.create_dataset(name, dtype = target_dtype, shape = shape, chunks = True, maxshape = maxshape, *kwargs)
        
        attributes.update({"title": name, "quantity": name, "long_name": name})
        if isinstance(units, str): attributes.update({"units": units})
        create_attributes(dataset, attributes)
        return dataset
    except Exception as e:
        raise Exception(f"Error encountered while attempting to create a new h5py dataset called {name} under {root_or_group}: {e}")

def create_main_dataset(root: h5py.File, name: str = "", *, existsok: bool = True, units: str | None = None, modality: str = "SPM", make_default: bool = True, attributes: dict = {},
                        data: np.ndarray | None = None, dtype: np.typing.DTypeLike | None = None, shape: tuple | None = None, maxshape: tuple | int | None = None, verbose: bool = False) -> h5py.Dataset:
    try:
        # Find or create the entry group
        entry_group = get_entry_group(root, name = "Measurement_000", verbose = verbose)
        entry_subgroups = get_groups(entry_group)
        
        if name in entry_subgroups.keys():
            if existsok:
                print(f"Warning: A dataset with the same name ({name}) was already found in this HDF5 file. Overwriting.")
                data_group = entry_subgroups[name]
            else:
                raise Exception(f"Error: A dataset with the same name ({name}) was already found in this HDF5 file. Aborting.")
        else: data_group = create_group(entry_group, name, attributes = {"signal": name, "NX_class": "NXdata", "units": units})
        
        data_type = "2D_image"
        if isinstance(data, np.ndarray):
            if data.ndim > 2: data_type = "image_stack"
            elif data.ndim < 2: data_type = "graph"
        if isinstance(shape, tuple):
            if len(shape) > 2: data_type = "image_stack"
            elif len(shape) < 2: data_type = "graph"
        
        # Create the dataset
        root_attrs = get_attributes(root)
        nsid_version = root_attrs.get("nsid_version", "0.0.4")
        dset_attributes = {"units": units, "data_type": data_type, "modality": modality, "nsid_version": nsid_version} | attributes
        if isinstance(data, np.ndarray): dataset = create_dataset(data_group, name, data = data, dtype = dtype, attributes = dset_attributes)
        elif isinstance(shape, tuple): dataset = create_dataset(data_group, name, shape = shape, maxshape = maxshape, dtype = dtype, attributes = dset_attributes)
        else:
            raise Exception("Neither data nor shape were provided when attempting to create a dataset")
        
        if make_default: create_attributes(entry_group, {"default": name})
        return dataset
    
    except Exception as e:
        raise Exception(f"Error encountered while attempting to create a new h5py dataset called {name}: {e}")

def create_ancillary_dataset(root: h5py.File, name: str = "", *, existsok: bool = True, units: str | None = None, attributes: dict = {},
                                data: np.ndarray | None = None, dtype: np.typing.DTypeLike | None = None, shape: tuple | None = None, maxshape: tuple | int | None = None, verbose: bool = False) -> h5py.Dataset:
    try:            
        # Find or create the entry group
        entry_group = get_entry_group(root, name = "Measurement_000", verbose = verbose)
        entry_subgroups = get_groups(entry_group)
        
        # Find or create the Ancillary group (The group that stores the axes)
        if "Ancillary" in entry_subgroups.keys(): ancillary_group = entry_subgroups["Ancillary"]
        else: ancillary_group = create_group(entry_group, name = "Ancillary", attributes = {"NX_class": "NXaxes"})
        
        ancillary_datasets = get_datasets(ancillary_group)
        
        if name in ancillary_datasets.keys():
            if existsok: print(f"Warning: A dataset with the same name ({name}) was already found in this HDF5 file. Overwriting.")
            else: raise Exception(f"Error: A dataset with the same name ({name}) was already found in this HDF5 file. Aborting.")
        
        # Interpret the dimension type
        dimension_type = "spectral"
        if units in {"m", "dm", "cm", "mm", "um", "nm", "pm", "Ang"}: dimension_type = "spatial"
        
        # Create the dataset
        dset_attributes = {"NX_class": "NXaxis", "units": units, "dimension_type": dimension_type} | attributes
        if isinstance(data, np.ndarray): dataset = create_dataset(ancillary_group, name, data = data, dtype = dtype, attributes = dset_attributes)
        elif isinstance(shape, tuple): dataset = create_dataset(ancillary_group, name, shape = shape, maxshape = maxshape, dtype = dtype, attributes = dset_attributes)
        else: raise Exception("Neither data nor shape were provided when attempting to create a dataset")
        return dataset
    
    except Exception as e:
        raise Exception(f"Error encountered while attempting to create a new h5py dataset called {name}: {e}")

def attach_axis(main_dataset: h5py.Dataset, ancillary_dataset: h5py.Dataset, axis: int = 0) -> None:
    try:
        # Extract all the information from the main dataset and its parent group
        main_dataset_path = main_dataset.name
        main_dataset_group = main_dataset.parent
        assert isinstance(main_dataset_path, str) and isinstance(main_dataset_group, h5py.Group | h5py. File)
        main_dataset_name = os.path.basename(main_dataset_path)
        main_dataset_group_attrs = get_attributes(main_dataset_group)
        main_dataset_rank = main_dataset.ndim
        
        # Extract all the information from the axis dataset and its parent group
        axis_dataset_path = ancillary_dataset.name
        axis_dataset_group = ancillary_dataset.parent
        assert isinstance(axis_dataset_path, str) and isinstance(axis_dataset_group, h5py.Group | h5py.File)
        axis_name = os.path.basename(axis_dataset_path)        
        axis_attrs = get_attributes(ancillary_dataset)
        
        axis_units = axis_attrs.get("units", "none")        
        axis_dtype = ancillary_dataset.dtype
        axis_data = ancillary_dataset[:]
        axis_dpoints = len(axis_data)
        axis_is_strings = (axis_dtype.kind in ('O', 'S', 'U')) or (h5py.check_string_dtype(axis_dtype) is not None)
    
        # Put the axis dataset in the main dataset group in the form of a soft link to its origin in the Ancillary group
        main_dataset_group[axis_name] = h5py.SoftLink(axis_dataset_path)
        local_axis_ds = main_dataset_group[axis_name]
        assert isinstance(local_axis_ds, h5py.Dataset)
        
        # Attach it directly for NSID compliance
        local_axis_ds.make_scale(axis_name)
        main_dataset.dims[axis].attach_scale(local_axis_ds)
        
        # Find the declared axes (NeXus) attribute in the main dataset group and update it with the name of the axis dataset
        main_dataset_axes = main_dataset_group_attrs.get("axes", None)
        if not isinstance(main_dataset_axes, list | np.ndarray) or not len(main_dataset_axes) == main_dataset_rank: main_dataset_axes = ["." for _ in range(main_dataset_rank)]        
        
        nexus_attributes = {}
        if axis_is_strings:
            main_dataset_axes[axis] = "." # NeXus/H5Web compliance: Provide "." as the axis placeholder so it renders as numeric indices
            nexus_attributes.update({f"{axis_name}_indices": [axis]})
        else:
            main_dataset_axes[axis] = axis_name
            axis_range = np.array([min(axis_data), max(axis_data)], dtype = axis_dtype)
            
            # Attributes for Gwyddion compatibility
            gwyddion_attributes = {}                
            match axis:
                case 0: [create_attributes(target, {"X Range": axis_range, "X Units": axis_units, "X No": axis_dpoints}) for target in [main_dataset, main_dataset_group]]
                case 1: [create_attributes(target, {"Y Range": axis_range, "Y Units": axis_units, "Y No": axis_dpoints}) for target in [main_dataset, main_dataset_group]]
                case 2: [create_attributes(target, {"Z Range": axis_range, "Z Units": axis_units, "Z No": axis_dpoints}) for target in [main_dataset, main_dataset_group]]
                case _: pass                
            if gwyddion_attributes: [create_attributes(target, gwyddion_attributes) for target in [main_dataset, main_dataset_group]]
        
        nexus_attributes.update({"axes": main_dataset_axes})            
        create_attributes(main_dataset_group, nexus_attributes)
    
    except Exception as e:
        print(f"Failed to attach dataset {axis_name} to axis {axis} of {main_dataset_name}: {e}")
    return

def read(file_path: str = "", lazy: bool = True) -> dict:
    output_dict: dict[str, object] = {}
    nx_entries: list[str] = []
    
    if not file_path: file_path = get_file_path_from_dialog(extensions = ["h5", "hdf5"])

    def recurse(h5obj: h5py.File | h5py.Group, current_path: str = "") -> None:
        # Find attributes, groups and datasets
        attributes = get_attributes(h5obj)
        datasets = get_datasets(h5obj)
        groups = get_groups(h5obj)            

        if attributes:
            attribute_key = "." if current_path == "" else current_path
            output_dict.update({f"{attribute_key}/attrs": attributes})
            
            if attributes.get("NX_class", None) in ("NXdata", b"NXdata"):
                nx_entries.append(current_path)

        for dataset_name, dataset in datasets.items():
            prefix = f"{current_path}/" if current_path else ""
            dataset_path = f"{prefix}{dataset_name}"
            
            if lazy: output_dict.update({dataset_path: dataset})
            else: output_dict.update({dataset_name: dataset[()]})

        for group_name, group in groups.items():
            # Build the cumulative internal path string
            prefix = f"{current_path}/" if current_path else ""
            
            recurse(group, f"{prefix}{group_name}")
        
        return

    try:
        with read_file(file_path) as root:
            if root is False:
                return output_dict

            file_tree = recurse(root)
            output_dict.update({"./": file_tree, "NXdata": nx_entries})

    except Exception as e:
        print(f"Problem encountered while reading HDF5 file: {e}")

    return output_dict

def get_object(root_or_path: str | h5py.File | h5py.Group, internal_path: str = "") -> h5py.Group | h5py.Dataset | h5py.Datatype | None:
    should_close = isinstance(root_or_path, str)
    
    if should_close: root = h5py.File(root_or_path, "r")
    elif isinstance(root_or_path, h5py.File | h5py.Group): root = root_or_path
    else:
        print(f"Invalid type {type(root_or_path)} provided to get_dataset")
        return None
    
    try:
        obj = root.get(internal_path, None)
        if obj == None:
            print(f"Path {internal_path} not found in HDF5 file")
            return None
        
        elif isinstance(obj, h5py.Dataset): return obj[()]
        return obj
    
    except Exception as e:
        print(f"Could not retrieve object from file using internal path {internal_path}")
    
    finally:
        if should_close: root.close()
    return

def get_data(file_path: str) -> dict:
    output_dict: dict[str, object] = {"file_path": file_path}
    frame = None
    dataset = None
    main_group = None
    axes_names = []
    axis_data = {}

    try:
        with read_file(file_path) as root:
            """
            Parsing the root
            """
            assert isinstance(root, h5py.File)
            
            # Open groups at the root level
            root_items = get_items(root)
            root_groups = get_groups(root)
            root_attributes = get_attributes(root)
            root_datasets = get_datasets(root)
            
            # Write root-level attributes to output dictionary
            output_dict.update({"root": root_attributes})
            
            # Try to find the frame (or grid) at the root level
            for obj in ["frame", "grid"]:
                if not obj in root_groups.keys(): continue
                
                frame_group = root_items[obj]
                input_frame = get_attributes(frame_group)
                #frame = parent.convert_to_sct_frame(input_frame)
                #if not "domain (nm)" in frame.keys(): frame = None

            # Read the attributes from all groups. At the same time, try to find the main (Nexus) measurement group while reading the different groups.
            for group_name, group in root_groups.items():                
                if "NX_class" in group.attrs:
                    main_group = root_items[group_name]
                    continue
                
                group_dict = {key: value for key, value in group.attrs.items() if not key in ["frame", "grid"]}
                output_dict.update({group_name: group_dict})
            
            # Fall back to recognizing group tags. If nothing works: break
            if not main_group:
                recognized_tags = ["session", "session_group", "main", "main_group", "sweep", "sweep_group", "scan", "scan_group",
                                    "measurement", "measurement_group", "spectrum", "spectrum_group", "spectroscopy", "spectroscopy_group", "data", "data_group"]
                for group_tag in recognized_tags:
                    if group_tag in root_items.keys():
                        main_group = root_items[group_tag]
                        break
            
            if not main_group:
                print("Could not determine the main group in HDF5 file")
                return(output_dict)
            
            
            
            """
            Parsing the main group
            """
            # If the frame was not yet found at the root level, try to find it at the main group level
            if not frame and main_group:
                for obj in ["frame", "grid"]:
                    if not obj in main_group.keys(): continue
                    
                    input_frame = {key: value for key, value in main_group[obj].attrs.items()}
                    frame = convert_to_sct_frame(input_frame)
                    if not "domain (nm)" in frame.keys(): frame = None
            if isinstance(frame, dict): output_dict.update({"frame": frame})

            # Retrieve the signal and axes
            if "signal" in main_group.attrs:
                signal_name = main_group.attrs.get("signal", "")
                if isinstance(signal_name, bytes): signal_name = signal_name.decode("utf-8")

                dataset = main_group[signal_name][:]
                output_dict.update({"signal": signal_name, "dataset": dataset})

            if "axes" in main_group.attrs:
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
            if not isinstance(dataset, np.ndarray):
                recognized_tags = ["main", "sweep", "scan", "measurement", "spectrum", "spectroscopy", "data", "array"]
                for tag in recognized_tags:
                    if tag in main_group.keys():
                        dataset = main_group[tag][:]
                        output_dict.update({"dataset": dataset})
                        break
            
            shape = dataset.shape
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

def create_file(file_path: str, close: bool = True, existsok: bool = False, nsid_version: str = "0.0.4") -> None | h5py.File:
    """
    Generate a NSID and NeXus-compatible HDF5 file for n-dimensional parameter space measurements.

    Args:
        file_path (str): File path as as string
        close (bool, optional): Whether to close the file after creation or keep it open and return a reference to the root. Defaults to True.
        existsok (bool, optional): Whether to overwrite if a file with the same path already exists. Defaults to True.
        channel_names (list | str, optional): Names of the different measurements. Defaults to "Channel_000".
        nsid_version (str, optional): String reflecting the NSID compatibility version. Defaults to "0.0.4".

    Returns:
        (None | tuple[h5py.File, h5py.Group, list[h5py.Group]]): None if 'close' is True. Otherwise, a tuple with the file root as first element, the entry group as second argument, and a list of channel groups as the third argument.
    """        
    if os.path.isfile(file_path):
        if existsok:
            print(f"File already exists at path {file_path}. Overwriting")
        else:
            print(f"File already exists at path {file_path}. Aborting")
            return

    try:
        root = h5py.File(file_path, "w")
        create_thumbnail_group(root)
        
        creation_timestamp = os.path.getctime(file_path)
        creation_datetime = datetime.fromtimestamp(creation_timestamp, tz = timezone.utc)
        datetime_iso_8601 = creation_datetime.isoformat()            
        create_attributes(root, {"filename": os.path.basename(file_path), "file_time": datetime_iso_8601, "creator": "Scantelligent", "data_model": "NSID", "version": nsid_version, "nsid_version": nsid_version, "NX_class": "NXroot"})
    
    except Exception as e:
        print(f"Error encountered while setting up HDF5 file: {e}")

    if close:
        root.close()
        return
    else:
        return root

