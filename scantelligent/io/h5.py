import os, h5py
from contextlib import contextmanager
import numpy as np
from datetime import datetime, timezone
from .file_picker import get_file_path_from_dialog
from typing import Literal



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



# Extract/filter specific h5py types
def get_attributes(h5object: h5py.File | h5py.Group | h5py.Dataset) -> dict:
    return {key: value for key, value in h5object.attrs.items()}

def get_groups(root_or_group: h5py.File | h5py.Group) -> dict:
    return {key: value for key, value in root_or_group.items() if isinstance(value, h5py.Group)}

def get_datasets(root_or_group: h5py.File | h5py.Group) -> dict:
    return {key: value for key, value in root_or_group.items() if isinstance(value, h5py.Dataset)}

def get_items(root_or_group: h5py.File | h5py.Group) -> dict:
    return {key: value for key, value in root_or_group.items()}



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



# Datasets
def create_dataset(root_or_group: h5py.File | h5py.Group, name: str = "", units: str = "", attributes: dict = {}, data: np.ndarray | None = None,
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
        
        dimension_type, quantity = infer_quantity_from_units(units)
        attributes.update({"title": name, "long_name": name, "units": units, "dimension_type": dimension_type, "quantity": quantity})
        create_attributes(dataset, attributes)
        return dataset
    except Exception as e:
        raise Exception(f"Error encountered while attempting to create a new h5py dataset called {name} under {root_or_group}: {e}")

def create_main_dataset(root: h5py.File, name: str = "", units: str = "", existsok: bool = True, modality: str = "SPM", make_default: bool = True, attributes: dict = {},
                        data: np.ndarray | None = None, dtype: np.typing.DTypeLike | None = None, shape: tuple | None = None, maxshape: tuple | int | None = None, verbose: bool = False) -> h5py.Dataset:
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
        if isinstance(data, np.ndarray): dataset = create_dataset(data_group, name, data = data, dtype = dtype, units = units, attributes = dset_attributes)
        elif isinstance(shape, tuple): dataset = create_dataset(data_group, name, shape = shape, maxshape = maxshape, dtype = dtype, units = units, attributes = dset_attributes)
        else:
            raise Exception("Neither data nor shape were provided when attempting to create a dataset")
        
        if make_default: create_attributes(entry_group, {"default": name})
        return dataset
    
    except Exception as e:
        raise Exception(f"Error encountered while attempting to create a new h5py dataset called {name}: {e}")

def create_ancillary_dataset(root: h5py.File, name: str = "", units: str = "", existsok: bool = True, attributes: dict = {},
                             data: np.ndarray | None = None, dtype: np.typing.DTypeLike | None = None, shape: tuple | None = None, maxshape: tuple | int | None = None, verbose: bool = False) -> h5py.Dataset:
    """Create a dataset that will become an axis to a main dataset. It is stored by default in the Ancillary Group, and Softlinked to the main dataset group upon calling attach_axis

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
        if isinstance(data, np.ndarray): dataset = create_dataset(ancillary_group, name, data = data, dtype = dtype, units = units, attributes = attributes | {"NX_class": "NXaxis"})
        elif isinstance(shape, tuple): dataset = create_dataset(ancillary_group, name, shape = shape, maxshape = maxshape, dtype = dtype, units = units, attributes = attributes | {"NX_class": "NXaxis"})
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
        [create_attributes(target, nexus_attributes) for target in [main_dataset, main_dataset_group]]
    
    except Exception as e:
        print(f"Failed to attach dataset {axis_name} to axis {axis} of {main_dataset_name}: {e}")
    return

def create_linear_axis(root: h5py.File, main_dataset: h5py.Dataset, axis: int = 0, name: str = "", limits: tuple | list = [0, 1], units: str = "", existsok: bool = True, attributes: dict = {}, verbose: bool = False) -> h5py.Dataset:
    try:
        n_elements = main_dataset.shape[axis]
        values = np.linspace(limits[0], limits[1], n_elements)
        
        axis_ds = create_ancillary_dataset(root, name = name, units = units, data = values, existsok = existsok, attributes = attributes, verbose = verbose)
        attach_axis(main_dataset, axis_ds, axis = axis)        
    except Exception as e:
        raise Exception(f"Could not create a linear dataset attached to {main_dataset}: {e}")
    return axis_ds



# Thumbnail
def create_thumbnail(root: h5py.File, *, attributes: dict = {}) -> h5py.Group:
    try:
        attributes.update({"NX_class": "NXimage"})
        new_group = create_group(root, "thumbnail", attributes = attributes)
        return new_group
    except:
        raise Exception(f"Error encountered while attempting to create a new h5py group called \"thumbnail\" under {root}")



# File creation
def create_file(file_path: str, close: bool = True, existsok: bool = False, nsid_version: str = "0.0.4", creator: str = "spmh5") -> None | h5py.File:
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
    def __init__(self, root_data: dict = {}, entry_group_data: dict = {}, ancillary_group_data: dict = {}, main_datasets: dict = {}, axis_datasets: dict = {}, file_tree: dict = {}):
        self.root_data = root_data
        self.entry_group_data = entry_group_data
        self.ancillary_group_data = ancillary_group_data
        self.main_datasets = main_datasets
        self.axis_datasets = axis_datasets
        self.file_tree = file_tree
        
        self.main_dataset_paths = list(main_datasets.keys())
        self.axis_dataset_paths = list(axis_datasets.keys())
        
        root_attrs = self.root_data.get("attributes", {})
        self.filename = root_attrs.get("filename", "unknown")
        self.date = root_attrs.get("creation_date", "unknown")
        self.time = root_attrs.get("creation_time", "unknown")
        pass
    
    def __repr__(self) -> str:
        return self.info()

    def info(self) -> str:
        return f"SPMH5File object {self.filename}, created on {self.date} at {self.time}, containing {len(self.main_datasets)} main datasets and {len(self.axis_datasets)} axis datasets."

    @classmethod
    def from_file(cls, path: str = "", lazy: bool = True):
        if not path: path = get_file_path_from_dialog(extensions = ["h5", "h5py"])
        output_dict: dict[str, object] = {}
        nx_entries: list[str] = []
        
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
            with read_file(path) as root:
                assert isinstance(root, h5py.File)
                
                # Instantiate dicts
                root_data = {}
                entry_group_data = {}
                ancillary_group_data = {}
                main_datasets_data = {}
                axis_datasets_data = {}
                
                # Parse the root
                root_attrs = get_attributes(root)
                root_groups = get_groups(root)
                root_data.update({"path": "./", "attributes": root_attrs, "groups": root_groups})
                
                # Parse the entry group
                entry_path = root_attrs.get("default", "")
                if entry_path:
                    entry_group = root[entry_path]
                    assert isinstance(entry_group, h5py.Group)
                    entry_group_attrs = get_attributes(entry_group)
                    entry_subgroups = get_groups(entry_group)
                    entry_group_data.update({"path": entry_path, "attributes": entry_group_attrs, "subgroups": entry_subgroups})
                
                    # Parse the ancillary group
                    if "Ancillary" in entry_subgroups.keys():
                        ancillary_group = entry_group["Ancillary"]
                        ancillary_path = entry_path + "/Ancillary"
                        assert isinstance(ancillary_group, h5py.Group)
                        ancillary_group_attrs = get_attributes(ancillary_group)
                        ancillary_group_data.update({"path": ancillary_path, "attributes": ancillary_group_attrs})
                        
                        axis_datasets = get_datasets(ancillary_group)
                        for dataset_name, dataset in axis_datasets.items():
                            dset_attrs = get_attributes(dataset)
                            
                            units = dset_attrs.get("units", [])
                            dset_path = ancillary_path + "/" + dataset_name
                            
                            axis_datasets_data.update({dset_path: {"name": dataset_name, "dataset": dataset, "type": "axis", "attributes": dset_attrs, "group_attributes": ancillary_group_attrs}})
                    
                    # Parse the main dataset groups
                    for group_name, group in entry_subgroups.items():
                        if group_name.lower() == "ancillary": continue
                        main_datasets = get_datasets(group)
                        if len(main_datasets) < 1: continue # The group has no dataset
                        
                        group_path = entry_path + "/" + group_name
                        group_attrs = get_attributes(group)
                        
                        for dataset_name, dataset in main_datasets.items():
                            dset_attrs = get_attributes(dataset)
                            if dset_attrs.get("NX_class", "") == "NXaxis": continue # This tag signifies the dataset is an axis dataset
                            
                            axes = dset_attrs.get("axes", [])
                            units = dset_attrs.get("units", [])
                            dset_path = group_path + "/" + dataset_name
                            
                            main_datasets_data.update({dset_path: {"name": dataset_name, "dataset": dataset, "type": "main", "axes": axes, "units": units, "attributes": dset_attrs, "group_attributes": group_attrs}})

                file_tree = recurse(root)
                output_dict.update({"./": file_tree, "NXdata": nx_entries})

        except Exception as e:
            print(f"Problem encountered while reading HDF5 file: {e}")

        return cls(root_data, entry_group_data, ancillary_group_data, main_datasets_data, axis_datasets_data, file_tree = output_dict) # type: ignore


