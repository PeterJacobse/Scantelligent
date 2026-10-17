import matplotlib.figure as plt_fig
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
from typing import Any, Literal
from collections.abc import Sequence
Numeric = float | int | complex | np.integer | np.floating



def complex_to_rgba(input_array: np.ndarray = np.zeros((2, 2)), phase_shift: float = 0., alpha: float = 1.) -> np.ndarray:
    phase = np.angle(input_array) + phase_shift
    hue = (phase + np.pi) / (2 * np.pi) % 1
    mag = np.abs(input_array)
    
    flat_order = np.argsort(mag, axis = None)
    rows, cols = np.unravel_index(flat_order, mag.shape)
    sorted = np.array(list(zip(rows, cols)))
    maximum = np.sum([mag[sorted[-idx, 0], sorted[-idx, 1]] for idx in range(1, 120)]) / 120
    for idx in range(1, 120): mag[sorted[-idx, 0], sorted[-idx, 1]] = maximum
    
    value = mag / maximum # np.max(mag)
    saturation = np.ones_like(hue)
    hsv = np.stack((hue, saturation, value), axis = -1)
    rgb = np.clip(mcolors.hsv_to_rgb(hsv), 0, 1)
    rgba = np.concatenate((rgb, np.full_like(rgb, alpha)), axis = 2)[:, :, :4]
    return rgba

def complex_plot(array: np.ndarray, figsize: tuple = (8, 6), phase_shift: float = 0.) -> plt_fig.Figure:
    """Convenience function for plotting a complex array

    Args:
        array (np.ndarray): Numpy array
        phase_shift (float, optional): Phase shift. Defaults to 0..
    """
    rgba_array = complex_to_rgba(array, phase_shift = phase_shift)
    fig, ax = plt.subplots(figsize = figsize)
    ax.imshow(rgba_array)
    return fig



class SPMH5Dataset:
    def __init__(self, data: list | np.ndarray = np.empty((0,), dtype = np.float32), attrs: dict = {}, units: str = "", name: str = ""):
        self.set_name(name)
        self.set_data(data)
        self.set_attrs(attrs)
        self.set_units(units)
        
        self.shape = self.data.shape
        self.rank = self.data.ndim
        self.ndim = self.rank
        self.dtype = self.data.dtype
        self.get_data_range()

    def __getitem__(self, key):
        return self.data[key]
    
    def __repr__(self) -> str:
        output_str_0 = f"SPMH5 dataset \"{self.name}\" holding a rank-{self.rank} numpy array of shape {self.shape}, dtype numpy.{self.dtype},"
        output_str_1 = f" with values in the range [{self.min:.4f} {self.units} to {self.max:.4f} {self.units}],"
        output_str_2 = f" and {len(self.attrs)} attributes stored at self.attrs"
        if self.units: return output_str_0 + output_str_1 + output_str_2
        else: return output_str_0 + output_str_2
    
    def set_name(self, name: str) -> None:
        self.name = name
        return
    
    def set_data(self, data: list | np.ndarray) -> None:
        if isinstance(data, list): self.data = np.array(data)
        else: self.data = data
        return
    
    def del_data(self) -> None:
        self.data = np.empty((0,), dtype = np.float32)
        return
    
    def set_attrs(self, attrs: dict) -> None:
        self.attrs = attrs
        return
    
    def del_attrs(self) -> None:
        self.attrs = {}
        return
    
    def add_attrs(self, attrs: dict) -> None:
        self.attrs.update(attrs)
        return
    
    def set_units(self, units: str) -> None:
        self.units = units

    def get_data_range(self) -> tuple[float, float] | tuple[complex, complex] | tuple[np.dtypes.VoidDType, np.dtypes.VoidDType]:
        arr = np.asarray(self.data)
        
        if arr.dtype.kind in {'U', 'S', 'O'}:
            try:
                if any('j' in str(x).lower() for x in arr.ravel()):
                    arr = arr.astype(np.complex128)
                else:
                    arr = arr.astype(np.float64)
            except ValueError as e:
                self.min = np.nan
                self.max = np.nan
                self.data_range = self.max - self.min
                return np.nan, np.nan    
        
        if np.issubdtype(arr.dtype, np.inexact) and np.all(np.isnan(arr)):
            self.min = np.nan
            self.max = np.nan
            self.data_range = self.max - self.min
            return np.nan, np.nan

        if np.issubdtype(arr.dtype, np.complexfloating):
            magnitudes = np.abs(arr)
            min_idx_flat = np.nanargmin(magnitudes)
            max_idx_flat = np.nanargmax(magnitudes)
            
            flat_arr = arr.ravel()
            self.min = complex(flat_arr[min_idx_flat])
            self.max = complex(flat_arr[max_idx_flat])
            self.data_range = self.max - self.min
            return self.min, self.max

        else:
            self.min = float(np.nanmin(arr))
            self.max = float(np.nanmax(arr))
            self.data_range = self.max - self.min
            return self.min, self.max

    def show_data(self, data: np.ndarray | None = None, figsize: tuple = (8, 6), extent: tuple[tuple] | None = None) -> plt_fig.Figure:
        if isinstance(data, np.ndarray): arr = data
        else: arr = self.data
        
        match self.rank:
            case 1:
                if np.issubdtype(self.dtype, np.complexfloating):
                    fig = plt.figure(figsize = figsize)
                    ax = fig.add_subplot(projection = "3d")
                    x_values = np.arange(len(arr))
                    y_values = np.real(arr)
                    z_values = np.imag(arr)
                    
                    ax.plot3D(x_values, y_values, z_values)
                else:
                    fig, ax = plt.subplots(figsize = figsize)
                    ax.plot(arr)
                    
            case 2:
                if np.issubdtype(self.dtype, np.complexfloating):
                    fig = complex_plot(arr, figsize = figsize, phase_shift = .3)
                    ax = fig.get_axes()[0]
                else:
                    fig, ax = plt.subplots(figsize = figsize)
                    try: ax.imshow(arr, extent = extent) # type: ignore
                    except: ax.imshow(arr)
                return fig
            
            case 3: # Improve slicing later
                data_slice = arr[0]
                if np.issubdtype(self.dtype, np.complexfloating):
                    fig = complex_plot(data_slice, figsize = figsize, phase_shift = .3)
                    ax = fig.get_axes()[0]
                else:
                    fig, ax = plt.subplots(figsize = figsize)
                    ax.imshow(data_slice)
            case _:
                raise Exception("I do not know yet how to represent these data")
        
        ax.set_title(self.name)
        return fig



class CoordinateFrame:
    def __init__(self, x_range: Numeric | Sequence[Numeric] | None = 10, y_range: Numeric | Sequence[Numeric] | None = 10, z_range: Numeric | Sequence[Numeric] | None = None,
                 ranges: Sequence[Numeric] | Sequence[Sequence[Numeric]] | None = None, units: str | Sequence[str] = "nm", offset: Numeric | Sequence[Numeric] = 0, angles: Numeric | Sequence[Numeric] = 0, angle_units: Literal["degree", "rad"] = "degree"):
        self.rank: int = 0
        
        if ranges: self.set_range(ranges)
        if x_range: self.set_range(x_range, axis = 0)
        if y_range: self.set_range(y_range, axis = 1)
        if z_range: self.set_range(z_range, axis = 2)
        
        self.set_units(units)
        self.set_offset(offset)
        self.set_angle(angles)
        self.set_angle_units(angle_units)
    
    def set_range(self, value: Numeric | Sequence[Numeric] | Sequence[Sequence[Numeric]], axis: int = -1) -> None:
        if isinstance(value, Numeric): value = [-.5 * value, .5 * value]
        if isinstance(value[0], Sequence): self.ranges = list(value)
        
        if isinstance(value[0], Numeric):
            if hasattr(self, "ranges") and axis > -1:
                assert isinstance(self.ranges, list)
                if axis > len(self.ranges) - 1: self.ranges.append([value[0], value[1]]) # type: ignore
                else: self.ranges[axis] = [value[0], value[1]]
            else: self.ranges = [[value[0], value[1]]]
        
        self.x_range = None
        self.y_range = None
        self.z_range = None
        if not hasattr(self, "ranges"): return
        for dim, values in enumerate(self.ranges):
            if dim == 0: self.x_range = values
            if dim == 1: self.y_range = values
            if dim == 2: self.z_range = values
        
        self.rank = len(self.ranges)
        self.ndim = self.rank
        if not hasattr(self, "units"): self.units = ["" for _ in range(self.rank)]
        if not hasattr(self, "offset"): self.offset = [0 for _ in range(self.rank)]
        if not hasattr(self, "angles"): self.angles = [0 for _ in range(self.rank)]        
        return
    
    def set_units(self, value: str | Sequence[str], axis: int = -1) -> None:
        if isinstance(value, str):
            if axis > -1 and axis < self.rank: self.units[axis] = value
            else: self.units = [value for _ in range(self.rank)]
            return
        if isinstance(value, list | tuple | np.ndarray): self.units = list(value)
        return
    
    def set_offset(self, value: Numeric | Sequence[Numeric], axis: int = -1) -> None:
        if isinstance(value, Numeric) and axis > -1 and axis < self.rank: self.offset[axis] = value # type: ignore
        if isinstance(value, Sequence): self.offset = list(value)
        return

    def set_angle(self, value: Numeric | Sequence[Numeric], axis: int = -1) -> None:
        if isinstance(value, Numeric) and axis > -1 and axis < self.rank: self.angles[axis] = value # type: ignore
        if isinstance(value, Sequence): self.angles = list(value)
        return
        
    def set_angle_units(self, value: Literal["degree", "rad"]) -> None:
        self.angle_units = value
        return



class DataGrid:
    def __init__(self, frame: CoordinateFrame = CoordinateFrame(), dataset: SPMH5Dataset = SPMH5Dataset(), axes: list[SPMH5Dataset] = [], attrs: dict = {}):
        self.set_frame(frame)
        self.set_dataset(dataset)
        self.set_axes(axes)
        self.set_attrs(attrs)
        
        self.name = self.dataset.name
        self.units = self.dataset.units
        self.shape = self.dataset.shape
        self.rank = self.dataset.rank
        self.dtype = self.dataset.dtype
        self.ndim = self.rank
        self.data_range = self.dataset.data_range
        self.data = self.dataset.data
        self.min = self.dataset.min
        self.max = self.dataset.max

    def __repr__(self) -> str:
        axis_dataset_names = ", ".join([axis.name for axis in self.axes])
        output_str_0 = f"SPMH5 datagrid \"{self.name}\" holding a rank-{self.rank} numpy array of shape {self.shape}, dtype numpy.{self.dtype},"
        output_str_1 = f" with values in the range [{self.min:.4f} {self.units} to {self.max:.4f} {self.units}],"
        output_str_2 = f" {len(self.attrs)} attributes stored at self.attrs and {len(self.dataset.attrs)} attributes stored at self.dataset.attrs.\n"
        output_str_3 = f"Attached to this datagrid are {len(self.axes)} datasets ({axis_dataset_names}) representing the axes:\n"
        axis_strings = "\n".join(["    " + repr(axis) for axis in self.axes])
        if self.units: return output_str_0 + output_str_1 + output_str_2 + output_str_3 + axis_strings + "\n"
        else: return output_str_0 + output_str_2 + axis_strings + "\n"

    def set_dataset(self, dataset: SPMH5Dataset) -> None:
        self.dataset = dataset
        return
    
    def set_frame(self, frame: CoordinateFrame) -> None:
        self.frame = frame
        return
    
    def set_axes(self, axes: list[SPMH5Dataset]) -> None:
        self.axes = axes
        return
    
    def set_attrs(self, attrs: dict) -> None:
        self.attrs = attrs
        return

    def show_data(self, figsize: tuple = (8, 6)) -> plt_fig.Figure:
        try:
            extent = (self.axes[0].min, self.axes[0].max, self.axes[1].min, self.axes[1].max)
            fig = self.dataset.show_data(figsize = figsize, extent = extent) # type: ignore
        except:
            fig = self.dataset.show_data(figsize = figsize) # type: ignore
        return fig

