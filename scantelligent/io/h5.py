import os, h5py, yaml, pprint, textwrap
from contextlib import contextmanager
import numpy as np
from datetime import datetime, timezone
from .file_picker import get_file_path_from_dialog
from .data_objects import SPMH5Dataset, CoordinateFrame, DataGrid
from typing import Literal
from collections.abc import Sequence
Numeric = float | int | complex | np.integer | np.floating



@contextmanager
def read_file(file_path: str = ""):
    if not file_path: file_path = get_file_path_from_dialog(extensions = ["h5", "hdf5"], io = "load")
    if not os.path.isfile(file_path): raise IOError(f"Invalid file path provided to read_file: {file_path}")

    ext = os.path.splitext(file_path)
    if not ext[1].lower() in {".h5", ".hdf5"}: raise Exception(f"Provided file path is not an HDF5 file: {file_path}")
    
    try:
        root = h5py.File(file_path, "r")
        yield root
    finally:
        root.close()
    return

# File is set up correctly upon using this function in a context manager, like with write_file(file_path) as root: ...
@contextmanager
def write_file(file_path: str = "", creator: str = "spmh5", nsid_version: str = "0.0.4", existsok: bool = False):
    if not file_path: file_path = get_file_path_from_dialog(extensions = ["h5", "hdf5"], io = "save")
    try:
        if os.path.isfile(file_path):
            if existsok: print(f"Warning: file {file_path} already exists. Overwriting")
            else: raise IOError(f"Error: file {file_path} already exists. Aborting")
        
        root = h5py.File(file_path, "w")
        
        # Attach the attributes for a compliant file
        creation_timestamp = os.path.getctime(file_path)
        creation_datetime = datetime.fromtimestamp(creation_timestamp, tz = timezone.utc)
        datetime_iso_8601 = creation_datetime.isoformat()
        root_attrs = {"filename": os.path.basename(file_path), "creator": creator, "data_model": "NSID", "version": nsid_version, "nsid_version": nsid_version, "NX_class": "NXroot", "file_time": datetime_iso_8601} | create_datetime()
        create_attributes(root, root_attrs)
        
        yield root
    finally:
        root.close()
    return

@contextmanager
def append_file(file_path: str = ""):
    if not file_path: file_path = get_file_path_from_dialog(extensions = ["h5", "hdf5"], io = "load")
    if not os.path.isfile(file_path): raise IOError(f"Invalid file path provided to append_file: {file_path}")
    
    try:
        root = h5py.File(file_path, "a")
        yield root
    finally:
        root.close()
    return

# Single shot file creation / setup
def setup_file(file_path: str = "", close: bool = True, existsok: bool = False, nsid_version: str = "0.0.4", creator: str = "spmh5") -> None | h5py.File:
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
    if not file_path: file_path = get_file_path_from_dialog(extensions = ["h5", "hdf5"], io = "save")
    if os.path.isfile(file_path):
        if existsok: print(f"Warning: File already exists at path {file_path}. Overwriting")
        else: raise IOError(f"Error: File already exists at path {file_path}. Aborting")

    try:
        root = h5py.File(file_path, "w")
        
        # Date and time attributes
        creation_timestamp = os.path.getctime(file_path)
        creation_datetime = datetime.fromtimestamp(creation_timestamp, tz = timezone.utc)
        datetime_iso_8601 = creation_datetime.isoformat()        
        create_attributes(root, {"filename": os.path.basename(file_path), "file_time": datetime_iso_8601, "creator": creator, "data_model": "NSID", "version": nsid_version, "nsid_version": nsid_version, "NX_class": "NXroot"} | create_datetime())
    
    except Exception as e:
        print(f"Error encountered while setting up HDF5 file: {e}")

    if close:
        root.close()
        return
    else:
        return root



# File reading
def dict_from_file(root: h5py.File, extract_datasets: bool = False) -> dict[str, dict[str, dict[str, object]]]:
    """
    Generates a nested dict describing the file.
    The top layer describes the object class, with keys \"main_datasets\", \"axis_datasets\", \"groups\" and \"instruments\".
    The second layer describes the path of the individual objects belonging to that class.
    The third layer is the data for that individual object.
    

    Args:
        root (h5py.File): Reference to a HDF5 file

    Returns:
        dict: Nested dictionary.
    """
    output_dict: dict[str, dict[str, dict[str, object]]] = {"groups": {}, "main_datasets": {}, "axis_datasets": {}, "instruments": {}}
    
    group_dict: dict[str, dict[str, object]] = {}
    instruments_dict: dict[str, dict[str, object]] = {}
    main_datasets_dict: dict[str, dict[str, object]] = {}
    axis_datasets_dict: dict[str, dict[str, object]] = {}
    
    root_data: dict[str, object] = {}
    entry_group_data: dict[str, object] = {}
    ancillary_group_data: dict[str, object] = {}
    
    axis_dataset_names: dict[str, str] = {} # Convenience dict for finding the path from a name later



    # Parse the root
    root_attrs = get_attributes(root)
    root_groups = get_groups(root)
    root_data.update({"path": "./", "name": "root", "attrs": root_attrs, "child_groups": [group_name for group_name in root_groups.keys()], "object_type": "root"})
    group_dict.update({"./": root_data})
    output_dict["groups"].update(group_dict)



    # Parse the entry group
    entry_path = root_attrs.get("default", "")
    if not entry_path: # No default found
        if len(root_groups) < 1: # No groups at all
            print("No groups found in this file!")
            return output_dict
        else: # There are groups
            for group_name, group in root_groups.items(): # Parse the individual groups for NX_class keys
                group_attrs = get_attributes(group)
                str_values = [value for value in group_attrs.values() if isinstance(value, str)]
                
                if "NXentry" in str_values:
                    entry_path = group_name # NXentry key found
                    break
            if not entry_path: # NXentry not found
                if len(root_groups) == 1: # Only a single group present
                    print("Warning! No entry group was found in this HDF5 file.\nPlease tag the entry group by adding the attribute \"default\": [group_name] to the root attributes.\nI did however, find a single group under the root and I will assume that it is the entry group.")
                    entry_path = list(root_groups.keys())[0]
                else: # Multiple groups but no tagged NXentry. Ambiguous
                    print("This file contains multiple groups, but no group is tagged as the entry group. Aborting file read")
                    return output_dict
    
    entry_group = root[entry_path]
    assert isinstance(entry_group, h5py.Group)
    entry_group_attrs = get_attributes(entry_group)
    entry_subgroups = get_groups(entry_group)
    entry_datasets = get_datasets(entry_group)
    
    entry_group_data.update({"path": entry_path, "attrs": entry_group_attrs, "parent_group": "./", "child_groups": [entry_path + "/" + group_name for group_name in entry_subgroups.keys()], "object_type": "group"})
    if len(entry_datasets) > 0: entry_group_data.update({"datasets": [dataset_name for dataset_name in entry_datasets.keys()]})
    group_dict.update({entry_path: entry_group_data})
    output_dict["groups"].update(group_dict)



    # Parse the ancillary group
    if "Ancillary" in entry_subgroups.keys():
        ancillary_group = entry_group["Ancillary"]
        ancillary_path = entry_path + "/Ancillary"
        assert isinstance(ancillary_group, h5py.Group)
        ancillary_group_attrs = get_attributes(ancillary_group)
        axis_datasets = get_datasets(ancillary_group)
        
        ancillary_group_data.update({"path": ancillary_path, "attrs": ancillary_group_attrs, "parent_group": entry_path, "object_type": "group", "datasets": [ancillary_path + "/" + dataset_name for dataset_name in axis_datasets.keys()]})
        group_dict.update({ancillary_path: ancillary_group_data})
        
        for dataset_name, dataset in axis_datasets.items():
            dset_attrs = get_attributes(dataset)
            shape = list(getattr(dataset, "shape", []))
            [dset_attrs.pop(key, None) for key in ["REFERENCE_LIST", "CLASS", "NAME", "DIMENSION_LIST"]]
            units = dset_attrs.get("units", "")
            dset_path = ancillary_path + "/" + dataset_name
            axis_datasets_dict.update({dset_path: {"path": dset_path, "name": dataset_name, "parent_group": ancillary_path, "object_type": "axis dataset", "units": units, "attrs": dset_attrs, "shape": shape}})
            axis_dataset_names.update({dataset_name: dset_path}) # Convenience dict for finding the path from a name later
        
        output_dict["groups"].update(group_dict)
        output_dict["axis_datasets"].update(axis_datasets_dict)



    # Parse the remaining groups (assumed to hold the main datasets)
    for group_name, group in entry_subgroups.items():
        if group_name.lower() == "ancillary": continue
        
        group_path = entry_path + "/" + group_name
        group_attrs = get_attributes(group)
        group_subgroups = get_groups(group)
        group_datasets = get_datasets(group)
        str_values = [value for value in group_attrs.values() if isinstance(value, str)]
        
        if "NX_instrument" in str_values: # The group is an instrument
            instruments_dict.update({group_path: {"path": group_path, "name": group_name, "parent_group": entry_path, "attrs": group_attrs, "object_type": "instrument group"}})
            if len(group_datasets) > 0: instruments_dict[group_path].update({"datasets": [group_path + "/" + dataset_name for dataset_name in group_datasets.keys()]})
            if len(group_subgroups) > 0: instruments_dict[group_path].update({"child_groups": [group_path + "/" + group_name for group_name in group_subgroups.keys()]})
            output_dict["instruments"].update(instruments_dict)
            continue

        if len(group_datasets) < 1: continue # The group has no dataset
        group_dict.update({group_path: {"path": group_path, "attrs": group_attrs, "parent_group": entry_path, "object_type": "group", "datasets": [group_path + "/" + dataset_name for dataset_name in group_datasets.keys()]}})
        output_dict["groups"].update(group_dict)
        
        for dataset_name, dataset in group_datasets.items():
            dset_attrs = get_attributes(dataset)
            shape = list(getattr(dataset, "shape", []))
            [dset_attrs.pop(key, None) for key in ["REFERENCE_LIST", "CLASS", "NAME", "DIMENSION_LIST"]]
            if dset_attrs.get("NX_class", "") == "NXaxis": continue # This tag signifies the dataset is an axis dataset
            
            cleaned_attrs = {}
            for key, value in dset_attrs.items():
                if isinstance(value, Sequence) and not isinstance(value, str): cleaned_attrs.update({key: list(value)})
                elif isinstance(value, int | np.integer): cleaned_attrs.update({key: int(value)}) # type: ignore
                elif isinstance(value, Numeric): cleaned_attrs.update({key: float(value)}) # type: ignore
            
            axes = list(group_attrs.get("axes", [])) # Substitute paths for names of the axis datasets
            for axis_index, axis_name in enumerate(axes):
                axis_path = axis_dataset_names.get(axis_name, axis_name)
                axes[axis_index] = axis_path
            
            units = dset_attrs.get("units", "")
            dset_path = group_path + "/" + dataset_name
            
            main_datasets_dict.update({dset_path: {"path": dset_path, "name": dataset_name, "parent_group": group_path, "object_type": "main dataset", "axes": axes, "units": units, "attrs": cleaned_attrs, "shape": shape}})
            output_dict["main_datasets"].update(main_datasets_dict)

    if not extract_datasets: return output_dict
    
    
    
    # Extract the datasets to SPMH5 dataset object if desired
    for index, target in enumerate([axis_datasets_dict, main_datasets_dict]):
        for dataset_path, dataset in target.items():
            try:
                dataset_data = root[dataset_path][:] # type: ignore
                dataset_name = dataset.get("name", "")
                dataset_units = dataset.get("units", "")
                dataset_attrs = dataset.get("attrs", {})
                
                if isinstance(dataset_data, np.ndarray) and isinstance(dataset_attrs, dict) and isinstance(dataset_units, str) and isinstance(dataset_name, str):
                    dataset_object = SPMH5Dataset(name = dataset_name, data_array = dataset_data, attrs = dataset_attrs, units = dataset_units)
                    if index == 0: axis_datasets_dict[dataset_path].update({"dataset_object": dataset_object})
                    if index == 1: main_datasets_dict[dataset_path].update({"dataset_object": dataset_object})
                else:
                    print(f"Warning: Could not convert dataset {dataset_path} to an SPMH5 dataset")
            except:
                raise Exception(f"Failed to read data from HDF5 file at path {dataset_path}")
    return output_dict

def get_data_grids(root: h5py.File) -> tuple[dict[str, dict[str, dict[str, object]]], list[DataGrid]]:
    output = dict_from_file(root, extract_datasets = True)
    main_datasets = output["main_datasets"]
    axis_datasets = output["axis_datasets"]
    groups = output["groups"]
    
    datagrids = []
    for main_dataset_path, main_dataset in main_datasets.items():
        main_object = main_dataset.get("dataset_object")
        if not isinstance(main_object, SPMH5Dataset): break
        
        parent_group_path = main_dataset.get("parent_group", "")
        if not isinstance(parent_group_path, str) or not parent_group_path in groups.keys():
            print(f"Warning: Could not read the parent group of a dataset at {parent_group_path}.")
            parent_group_attrs = {}
        else:
            parent_group = groups[parent_group_path]
            parent_group_attrs = parent_group.get("attrs", {})
            assert isinstance(parent_group_attrs, dict)
        
        axes = main_dataset.get("axes", [])
        if not isinstance(axes, list) or len(axes) < 1: continue
        
        axis_objects = []
        for dim, axis in enumerate(axes):
            if not axis in axis_datasets.keys():
                print(f"Warning: Failed to find axis dataset {axis}")
                continue
            
            axis_dataset = axis_datasets[axis]
            axis_object = axis_dataset.get("dataset_object")
            if isinstance(axis_object, SPMH5Dataset): axis_objects.append(axis_object)
        
        datagrids.append(DataGrid(dataset = main_object, axes = axis_objects, attrs = parent_group_attrs))
    return output, datagrids

def get_file(file_path: str = ""):
    return SPMH5File.from_file(file_path)



# Extract/filter/find specific h5py types
def get_attributes(h5object: h5py.File | h5py.Group | h5py.Dataset) -> dict:
    return {key: value for key, value in h5object.attrs.items()}

def get_groups(root_or_group: h5py.File | h5py.Group) -> dict:
    return {key: value for key, value in root_or_group.items() if isinstance(value, h5py.Group)}

def get_datasets(root_or_group: h5py.File | h5py.Group) -> dict:
    return {key: value for key, value in root_or_group.items() if isinstance(value, h5py.Dataset)}

def get_items(root_or_group: h5py.File | h5py.Group) -> dict:
    return {key: value for key, value in root_or_group.items()}

def get_root(h5object: h5py.Group | h5py.Dataset | h5py.File) -> h5py.Group:
    try:
        if isinstance(h5object, h5py.File): return h5object
        possible_root = h5object
        
        for _ in range(6):
            if possible_root.name == '/':
                assert isinstance(possible_root, h5py.Group)
                return possible_root
            possible_root = possible_root.parent
        raise Exception(f"Could not locate the HDF5 file root from object {h5object}")
    except Exception as e:
        raise Exception(f"Problem finding the HDF5 file root: {e}")



# Attributes
def create_attributes(h5object: h5py.File | h5py.Group | h5py.Dataset, attributes: dict = {}) -> None:
    for key, value in attributes.items():
        try:
            if isinstance(value, str): h5object.attrs.create(key, value, dtype = h5py.string_dtype(encoding = "utf-8"))
            else: h5object.attrs[key] = value
        except: pass
    return

def create_datetime(date_convention: Literal["US", "world"] = "US") -> dict[str, str]:
    dt = datetime.now()
    date_str = dt.strftime(f"%m/%d/%Y (US)") if date_convention == "US" else dt.strftime(f"%d/%m/%Y (world)")
    time_str = dt.strftime(f"%H:%M:%S")
    return {"creation_date": date_str, "creation_time": time_str}



# Make groups
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



# General and Main datasets
def create_dataset(root_or_group: h5py.File | h5py.Group, name: str = "", units: str = "", attributes: dict = {}, data: np.ndarray | None = None,
                   dtype: np.typing.DTypeLike | None = None, shape: tuple | None = None, resizable_axes: Numeric | Sequence | None = None, maxshape: tuple | int | None = None, **kwargs) -> h5py.Dataset:
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
        
        if isinstance(data, np.ndarray): # Data is passed explicitly. Resizable axes may be provided instead of maxshape for easier declaration.
            shape = data.shape
            
            # Check if resizable axes are provided
            if isinstance(resizable_axes, Numeric): resizable_axes = (resizable_axes,)
            if isinstance(resizable_axes, Sequence):
                new_maxshape = []
                for dim, axis_length in enumerate(shape):
                    new_maxshape.append(None) if dim in resizable_axes else new_maxshape.append(axis_length)
                maxshape = tuple(new_maxshape)            
            
            if parsed_dtype.kind == "U":
                if isinstance(maxshape, tuple): dataset = root_or_group.create_dataset(name, shape = shape, dtype = target_dtype, chunks = True, maxshape = maxshape, **kwargs)
                else: dataset = root_or_group.create_dataset(name, shape = shape, dtype = target_dtype, **kwargs)
                dataset[...] = data.astype("O")
            else:
                if isinstance(maxshape, tuple): dataset = root_or_group.create_dataset(name, data = data, dtype = target_dtype, chunks = True, maxshape = maxshape, **kwargs)
                else: dataset = root_or_group.create_dataset(name, data = data, dtype = target_dtype, **kwargs)
        else: # No data is passed, but a shape is provided. Since there is no data to infer a shape from, maxshape must be provided
            dataset = root_or_group.create_dataset(name, dtype = target_dtype, shape = shape, chunks = True, maxshape = maxshape, *kwargs)
        
        dimension_type, quantity = infer_quantity_from_units(units)
        attributes.update({"title": name, "long_name": name, "units": units, "dimension_type": dimension_type, "quantity": quantity})
        create_attributes(dataset, attributes)
        return dataset
    except Exception as e:
        raise Exception(f"Error encountered while attempting to create a new h5py dataset called {name} under {root_or_group}: {e}")

def add_values(dataset: h5py.Dataset, values: np.ndarray, axis: int = -1) -> None:
    try:
        dset_shape = dataset.shape
        if not axis in range(dataset.ndim):
            resizable_axes = np.where(np.array(dataset.maxshape) == None)[0]
            axis = resizable_axes[0]
        
        values_shape = values.shape
        
        axis_length = dset_shape[axis]
        values_length = values_shape[axis]
        new_axis_length = axis_length + values_length
        
        dataset.resize(new_axis_length, axis = axis)
        match axis:
            case 0: dataset[axis_length:] = values
            case 1: dataset[:, axis_length:] = values
            case 2: dataset[:, :, axis_length:] = values
            case _: raise Exception(f"Unsupported axis {axis}")
        
    except Exception as e:
        try:
            raise Exception(f"Failed to add a data chunk of shape {values_shape} to a dataset of shape {dset_shape} along axis {axis}: {e}") # type: ignore
        except:
            raise Exception(f"Failed to add a data chunk {values} to dataset {dataset} along axis {axis}: {e}")
    return

def create_main_dataset(root: h5py.File, name: str = "", units: str = "", existsok: bool = True, modality: str = "SPM", make_default: bool = True, attributes: dict = {},
                        data: np.ndarray | None = None, dtype: np.typing.DTypeLike | None = None, shape: tuple | None = None, resizable_axes: Numeric | Sequence | None = None, maxshape: tuple | int | None = None, verbose: bool = False) -> h5py.Dataset:
    try:
        # Find or create the entry group
        entry_group = get_entry_group(root, name = "Measurement_000", verbose = verbose)
        entry_subgroups = get_groups(entry_group)
        
        if name in entry_subgroups.keys():
            if existsok:
                print(f"Warning: A dataset with the same name ({name}) was already found in this HDF5 file. Overwriting.")
                data_group = entry_subgroups[name]
                del(data_group[name])
            else:
                raise Exception(f"Error: A dataset with the same name ({name}) was already found in this HDF5 file. Aborting.")
        else:
            data_group_attrs = {"signal": name, "NX_class": "NXdata", "units": units}
            data_group = create_group(entry_group, name, attributes = data_group_attrs)
        
        data_type = "2D_image"
        if isinstance(data, np.ndarray):
            if data.ndim > 2: data_type = "image_stack"
            elif data.ndim < 2: data_type = "graph"
        if isinstance(shape, tuple):
            if len(shape) > 2: data_type = "image_stack"
            elif len(shape) < 2: data_type = "graph"
        
        # Create the dataset attributes
        root_attrs = get_attributes(root)
        nsid_version = root_attrs.get("nsid_version", "0.0.4")
        dset_attributes = {"units": units, "data_type": data_type, "modality": modality, "nsid_version": nsid_version} | attributes
        
        # Create the dataset
        if isinstance(data, np.ndarray): # Data is passed explicitly
            dataset = create_dataset(data_group, name, data = data, resizable_axes = resizable_axes, dtype = dtype, units = units, attributes = dset_attributes)
        elif isinstance(shape, tuple): # The dataset is instantiated with a certain shape            
            dataset = create_dataset(data_group, name, shape = shape, maxshape = maxshape, dtype = dtype, units = units, attributes = dset_attributes)
        else:
            raise Exception("Neither data nor shape were provided when attempting to create a dataset")
        
        if make_default: create_attributes(entry_group, {"default": name})
        return dataset
    
    except Exception as e:
        raise Exception(f"Error encountered while attempting to create a new h5py dataset called {name}: {e}")



# Ancillary / Axis datasets
def create_ancillary_dataset(root: h5py.File, name: str = "", units: str = "", existsok: bool = True, attributes: dict = {},
                             data: np.ndarray | None = None, dtype: np.typing.DTypeLike | None = None, shape: tuple | None = None, verbose: bool = False) -> h5py.Dataset:
    """Create a dataset that will become an axis to a main dataset. It is stored by default in the Ancillary Group, and Softlinked to the main dataset group upon calling attach_axis. Ancillary datasets are 1D and resizable by default.

    Args:
        root (h5py.File): Root.
        name (str, optional): Dataset name. Defaults to "".
        existsok (bool, optional): Allow overwriting. Defaults to True.
        units (str, optional): Units. Defaults to "".
        attributes (dict, optional): Custom attributes. Defaults to {}.
        data (np.ndarray | None, optional): Data. Defaults to None.
        dtype (np.typing.DTypeLike | None, optional): Data type. Defaults to None.
        shape (tuple | None, optional): Shape of dataset. Defaults to None. Passing shape and maxshape instead of data will trigger chunking.
        maxshape (tuple | int | None, optional): Maximum shape. Defaults to None.
        verbose (bool, optional): Whether to output details to terminal. Defaults to False.

    Returns:
        h5py.Dataset: The dataset
    """
    try:
        # Find or create the entry group
        entry_group = get_entry_group(root, name = "Measurement_000", verbose = verbose)
        entry_subgroups = get_groups(entry_group)
        
        # Find or create the Ancillary group (The group that stores the axes)
        if "Ancillary" in entry_subgroups.keys(): ancillary_group = entry_subgroups["Ancillary"]
        else: ancillary_group = create_group(entry_group, name = "Ancillary", attributes = {"NX_class": "NXaxes"})
        
        ancillary_datasets = get_datasets(ancillary_group)
        
        if name in ancillary_datasets.keys():
            if existsok:
                print(f"Warning: A dataset with the same name ({name}) was already found in this HDF5 file. Overwriting.")
                del(ancillary_group[name])
            else:
                raise Exception(f"Error: A dataset with the same name ({name}) was already found in this HDF5 file. Aborting.")

        # Create the dataset
        if isinstance(data, np.ndarray): dataset = create_dataset(ancillary_group, name, data = data, maxshape = (None,), dtype = dtype, units = units, attributes = attributes | {"NX_class": "NXaxis", "interpretation": "spectrum"})
        elif isinstance(shape, tuple): dataset = create_dataset(ancillary_group, name, shape = shape, maxshape = (None,), dtype = dtype, units = units, attributes = attributes | {"NX_class": "NXaxis", "interpretation": "spectrum"})
        else: raise Exception("Neither data nor shape were provided when attempting to create a dataset")
        
        return dataset
    
    except Exception as e:
        raise Exception(f"Error encountered while attempting to create a new h5py dataset called {name}: {e}")

def attach_axis(main_dataset: h5py.Dataset, ancillary_dataset: h5py.Dataset, axis: int = 0) -> None:
    try:
        # Extract all the information from the main dataset and its parent group
        main_dataset_path = main_dataset.name
        main_dataset_group = main_dataset.parent
        assert isinstance(main_dataset_path, str) and isinstance(main_dataset_group, h5py.Group | h5py.File)
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

        # Check if the target name already exists in the destination group (even if it's a broken soft link)
        if axis_name in main_dataset_group: del main_dataset_group[axis_name]

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
        
        if axis_is_strings:
            main_dataset_axes[axis] = "." # NeXus/H5Web compliance: Provide "." as the axis placeholder so it renders as numeric indices
            create_attributes(main_dataset_group, {f"{axis_name}_indices": [axis], "axes": main_dataset_axes}) # Add NeXus attributes
        else:
            main_dataset_axes[axis] = axis_name
            create_attributes(main_dataset_group, {"axes": main_dataset_axes}) # Add NeXus attributes
            
            if axis_dpoints < 2: axis_range = np.zeros(shape = (2,), dtype = axis_dtype) # Empty axis
            else: axis_range = np.array([axis_data[0], axis_data[-1]], dtype = axis_dtype)

            # Attributes for Gwyddion compatibility
            match axis:
                case 0: range_units_attrs = {"X Range": axis_range, "X Units": axis_units, "X No": axis_dpoints}
                case 1: range_units_attrs = {"Y Range": axis_range, "Y Units": axis_units, "Y No": axis_dpoints}
                case 2: range_units_attrs = {"Z Range": axis_range, "Z Units": axis_units, "Z No": axis_dpoints}
                case _: range_units_attrs = {"A Range": axis_range, "A Units": axis_units, "A No": axis_dpoints}
                
            [create_attributes(target, range_units_attrs) for target in [main_dataset, main_dataset_group]]
            create_attributes(ancillary_dataset, {"axis": axis, "main_dataset_path": main_dataset_path})
        
    except Exception as e:
        try:
            print(f"Failed to attach dataset {axis_name} to axis {axis} of {main_dataset_name}: {e}")
        except Exception as e:
            print(f"Failed to attach dataset {ancillary_dataset} to axis {axis} of {main_dataset}: {e}")
    return

def create_linear_axis(main_dataset: h5py.Dataset, axis: int = 0, name: str = "", limits: Sequence = (0, 1), units: str = "", existsok: bool = True, attributes: dict = {}, include_boundary: bool = False, verbose: bool = False) -> h5py.Dataset:
    try:
        root = get_root(main_dataset)
        n_elements = main_dataset.shape[axis]
        
        if include_boundary:
            values = np.linspace(limits[0], limits[1], n_elements)
        else:
            point_size = (limits[1] - limits[0]) / n_elements
            values = np.linspace(limits[0] + point_size / 2, limits[1] - point_size / 2, n_elements)
        
        axis_ds = create_ancillary_dataset(root, name = name, units = units, data = values, existsok = existsok, attributes = attributes, verbose = verbose) # type: ignore
        attach_axis(main_dataset, axis_ds, axis = axis)        
    except Exception as e:
        raise Exception(f"Could not create a linear dataset attached to {main_dataset}: {e}")
    return axis_ds

def create_axes_from_frame(main_dataset: h5py.Dataset, frame: CoordinateFrame, names: list = ["x", "y", "z", "a"], include_boundaries: bool = False) -> list[h5py.Dataset]:
    if not main_dataset.ndim == frame.rank: raise Exception(f"Rank of dataset ({main_dataset.ndim}) does not match dimensionality of frame ({frame.rank})")
    
    dataset_list = []
    for dim, (limits, units, name) in enumerate(zip(frame.ranges, frame.units, names)):
        ds = create_linear_axis(main_dataset, axis = dim, name = name, limits = limits, units = units, include_boundary = include_boundaries) # type: ignore
        dataset_list.append(ds)
    return dataset_list

def update_axis(ancillary_dataset: h5py.Dataset, root: h5py.File | h5py.Group | None = None) -> None:
    try:
        if not isinstance(root, h5py.File): root = get_root(ancillary_dataset)
        
        axis_attrs = get_attributes(ancillary_dataset)
        
        axis_dtype = ancillary_dataset.dtype
        axis_is_strings = (axis_dtype.kind in ('O', 'S', 'U')) or (h5py.check_string_dtype(axis_dtype) is not None)
        
        axis_data = ancillary_dataset[:]
        axis_dpoints = len(axis_data)
        
        if axis_is_strings or axis_dpoints < 2: axis_range = np.empty(shape = (2,), dtype = axis_dtype) # Empty axis
        else: axis_range = np.array([axis_data[0], axis_data[1]], dtype = axis_dtype)
        
        main_dataset_path = axis_attrs.get("main_dataset_path", "")
        axis_of_main_dataset = int(axis_attrs.get("axis", 0))
        
        if main_dataset_path:
            main_dataset = root[main_dataset_path]
            main_dataset_group = main_dataset.parent
            assert isinstance(main_dataset, h5py.Dataset) and isinstance(main_dataset_group, h5py.Group)
            
            match axis_of_main_dataset:
                case 0: range_attrs = {"X Range": axis_range, "X No": axis_dpoints}
                case 1: range_attrs = {"Y Range": axis_range, "Y No": axis_dpoints}
                case 2: range_attrs = {"Z Range": axis_range, "Z No": axis_dpoints}
                case _: range_attrs = {"A Range": axis_range, "A No": axis_dpoints}
            
            [create_attributes(target, range_attrs) for target in [main_dataset, main_dataset_group]]
    
    except Exception as e:
        print(f"Failed to update dataset {ancillary_dataset}: {e}")
    return

def add_values_to_axis(ancillary_dataset: h5py.Dataset, new_values: Numeric | list | np.ndarray = [], root: h5py.File | h5py.Group | None = None) -> None:
    if isinstance(new_values, Numeric): new_values = [new_values]
    n_new_values = len(new_values)
    n_elements = ancillary_dataset.shape[0]
    
    ancillary_dataset.resize(n_elements + n_new_values, axis = 0)
    ancillary_dataset[n_elements:] = new_values
    
    update_axis(ancillary_dataset, root)
    return



# Thumbnail
def create_thumbnail(root: h5py.File, *, attributes: dict = {}) -> h5py.Group:
    try:
        attributes.update({"NX_class": "NXimage"})
        new_group = create_group(root, "thumbnail", attributes = attributes)
        return new_group
    except:
        raise Exception(f"Error encountered while attempting to create a new h5py group called \"thumbnail\" under {root}")



# Misc
def infer_quantity_from_units(units: str = "") -> tuple[str, str]:
    quantity = ""
    dimension_type = "spectral"
    
    if units in {"m", "dm", "cm", "mm", "um", "nm", "pm", "Ang"}:
        quantity = "Length"
        dimension_type = "spatial"
    if units in {"m-1", "dm-1", "cm-1", "mm-1", "um-1", "nm-1", "pm-1", "Ang-1", "/m", "/dm", "/cm", "/mm", "/um", "/nm", "/pm", "/Ang"}:
        quantity = "Length"
        dimension_type = "reciprocal"
    if units in {"eV", "J", "kcal"}:
        quantity = "Energy"
    if units in {"Hz", "s-1", "/s"}:
        quantity = "Frequency"
    if units in {"A", "mA", "uA", "nA", "pA", "fA"}:
        quantity = "Current"
    if units in {"S", "mS", "uS", "nS", "pS", "fS"}:
        quantity = "Conductance"
    if units in {"F", "mF", "uF", "nF", "pF", "fF"}:
        quantity = "Capacitance"

    return dimension_type, quantity

def print_dict(dictionary: dict = {}, indent: int = 4, global_indent: int = 0):
    try:
        yaml.add_representer(SPMH5Dataset, lambda dumper, data: dumper.represent_scalar("tag:yaml.org,002:str", repr(data)))
        
        indent_string = "".join([" " for _ in range(global_indent)])
        yaml_string = yaml.dump(dictionary, default_flow_style = False, sort_keys = False, indent = indent, Dumper = IndentDumper)
        print(textwrap.indent(yaml_string, indent_string))
    except Exception as e:
        pprint.pprint(dictionary)
        print(f"Cannot print this dictionary using pyyaml: {e}")
    return

def file_summary(root_or_path: h5py.File | str = ""):
    if isinstance(root_or_path, h5py.File):
        output = dict_from_file(root_or_path)
    elif isinstance(root_or_path, str):
        if not root_or_path: path = get_file_path_from_dialog(extensions = ["h5", "hdf5"])
        else: path = root_or_path
        with read_file(path) as root:
            assert isinstance(root, h5py.File)
            output = dict_from_file(root)
    else:
        raise IOError("Invalid HDF5 file or path provided")
    
    group_data = output.get("groups", {})
    main_datasets = output.get("main_datasets", {})
    axis_datasets = output.get("axis_datasets", {})
    
    root_data = group_data.get("./", {})
    
    print(f"Summary of HDF5 file {root_data.get("filename", "unknown")}, containing {len(main_datasets)} main datasets and {len(axis_datasets)} ancillary datasets, created on {root_data.get("creation_date", "unknown")} at {root_data.get("creation_time", "unknown")}.\n")
    
    for main_dataset in main_datasets.values():
        print(f"\n\n    Info for main dataset {main_dataset.get("name", "unknown")}:\n")
        print_dict(main_dataset, global_indent = 4)
        
        main_dataset_axes = main_dataset.get("axes", [])
        assert isinstance(main_dataset_axes, list)
        
        print("        Attached to this dataset are the following axis datasets:\n")
        for axis_index, axis in enumerate(main_dataset_axes):
            axis_dataset = axis_datasets.get(axis, {})            
            print_dict({f"axis {axis_index}: {axis_dataset.get("name", "unknown")}": axis_dataset}, global_indent = 8)
    return



# Reading
def get_object(root_or_path: str | h5py.File | h5py.Group, internal_path: str = "") -> h5py.Group | h5py.Dataset | h5py.Datatype | np.ndarray | None:
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
        return obj # type: ignore
    
    except Exception as e:
        print(f"Could not retrieve object from file using internal path {internal_path}")
    
    finally:
        if should_close:
            assert isinstance(root, h5py.File)
            root.close()
    return



class SPMH5File:
    def __init__(self, name: str = "unknown", creator: str = "unknown", date: str = "unknown", time: str = "unknown", file_dict: dict = {}, attrs: dict = {}, data_grids: list[DataGrid] = []):
        self.name = name
        self.creator = creator
        self.date = date
        self.time = time
        self.file_dict = file_dict
        self.attrs = attrs
        self.data_grids = data_grids
    
    def __repr__(self) -> str:
        return self.info()

    def info(self, elaborate: bool = False) -> str:
        output_str_0 = f"SPMH5 file \"{self.name}\" created on {self.date} at {self.time}, containing {len(self.data_grids)} data grids.\n"
        return output_str_0 + f"Use SPMH5File.file_info() for more details"

    def file_info(self) -> None:
        print(f"SPMH5 file \"{self.name}\" created on {self.date} at {self.time}, containing {len(self.data_grids)} data grids:\n")
        [print(data_grid) for data_grid in self.data_grids]
        print_dict(self.file_dict)

    @classmethod
    def from_file(cls, file_path: str = ""):
        with read_file(file_path) as root:
            output, data_grids = get_data_grids(root)
            
            root_group = output["groups"].get("./", {})
            if not isinstance(root_group, dict): raise Exception(f"Invalid root group type {type(root_group)}. Expected a dict")
            
            root_attrs = root_group.get("attrs", {})
            assert isinstance(root_attrs, dict)
            
            [filename, creator, file_time, file_date, default] = [root_attrs.get(key, "unknown") for key in ["filename", "creator", "creation_time", "creation_date", "default"]]
        return cls(name = filename, creator = creator, date = file_date, time = file_time, attrs = root_attrs, file_dict = output, data_grids = data_grids)



class IndentDumper(yaml.Dumper):
    def increase_indent(self, flow: bool = False, indentless: bool = False):
        return super(IndentDumper, self).increase_indent(flow, indentless = False)
