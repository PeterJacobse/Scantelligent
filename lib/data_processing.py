import numpy as np
from scipy.signal import convolve2d
from scipy.ndimage import gaussian_filter
from scipy.fft import fft2, fftshift
from matplotlib import colors
from scipy.linalg import lstsq
import pint, re, yaml, os
from dataclasses import dataclass



class DataProcessing():
    def __init__(self):
        self.processing_flags = self.create_scan_processing_flage()
        self.spec_processing_flags = self.create_spec_processing_flags()
        
    def create_scan_processing_flage(self) -> dict:
        processing_flags = {
            "dict_name": "processing_flags", # Self reference to facilitate the app recognizing what kind of dictionary this is
            "direction": "forward", # Forward is the left-to-right (trace) part of the scan; backward is right-to-left (retrace) part of the scan
            "up_or_down": "up", # Scan direction. Terminology 'direction' is avoided for up or down to avoid confusion
            "channel": "Z", # Scan channel
            "background": "none", # Method for background subtraction. Can be 'none', 'plane', or 'linewise'
            "rotation": False, # Flag that determines whether the rotation of the scan frame should be shown
            "offset": False,
            "sobel": False,
            "gaussian": False,
            "gaussian_width_nm": 0,
            "gaussian_width (nm)": 0,
            "laplace": False,
            "fft": False,
            "normal": False,
            "projection": "re",
            "phase": 0,
            "min_method": "full", # Method to determine the lower limit of the data. Can be 'full', 'absolute', 'percentiles' or 'deviations'
            "min_method_value": 0, # Argument to calculate the min_limit on the basis of the provided min_method
            "min_limit": 0, # This key will hold the numerical value of the limit as determined by applying the min_method to the data using the min_method_value
            "max_method": "full", # See explanation for min_method, min_method_value and min_limit
            "max_method_value": 1,
            "max_limit": 1,
            "spec_locations": False, # Flag whether or not to display spectroscopy locations in the scan
            "scan_range_nm": [0, 0], # Will be deprecated
            "file_name": "",
            "frame": { # A frame dict is embedded in processing flags so that the location, rotation and scan range parameters can be accessed immediately
                "dict_name": "frame",
                "offset (nm)": [0, 0],
                "scan_range (nm)": [0, 0],
                "angle (deg)" : 0
            }
        }
        
        return processing_flags
    
    def create_spec_processing_flags(self) -> dict:
        processing_flags = {
            "line_width": 2,
            "opacity": 1,
            "offset_0": 0,
            "offset_1": 0,
            "direction": "fwd_bwd",
            "log_abs_0": False,
            "differentiate_0": False,
            "log_abs_1": False,
            "differentiate_1": False,
            "moving_average": False,
            "moving_average_window": 1
        }
        
        return processing_flags



    # Misc
    def extract_numbers_from_str(self, text: str) -> list[float] | None:
        # Extract the numeric part
        if text.startswith("."): text = "0" + text
        regex_pattern = r"[-+]?(?:[0-9]*\.)?[0-9]+(?:[eE][-+]?[0-9]+)?"
        number_matches = re.findall(regex_pattern, text)
        numbers = [float(x) for x in number_matches]
        
        return numbers
    
    def add_tags_to_file_name(self, bare_name: str = "") -> str:
        flags = self.processing_flags
        
        tagged_name = bare_name
        if flags["sobel"]: tagged_name += "_sobel"
        if flags["fft"]: tagged_name += "_FFT"
        if flags["laplace"]: tagged_name += "_laplace"
        if flags["normal"]: tagged_name += "_normal"
        if flags["direction"] == "backward": tagged_name += "_bwd"
        else: tagged_name += "_fwd"
        
        projection_tag = "_" + flags["projection"]
        if projection_tag != "_re": tagged_name += projection_tag
        
        return tagged_name

    def pick_image_from_scan_object(self, scan_object) -> tuple[np.ndarray, str, dict, bool | str]:
        error = False

        try:
            scan_tensor = scan_object.tensor
            channels = scan_object.channels
            frame = scan_object.frame
            
            requested_channel = self.processing_flags.get("channel")
            
            # Initialize to fail and update to success if the requested channel is found
            selected_channel = channels[0]
            tensor_slice = scan_tensor[0]
            for index in range(len(channels)):
                if channels[index] == requested_channel:
                    selected_channel = requested_channel
                    tensor_slice = scan_tensor[index]
                    break
            image = tensor_slice[int(self.processing_flags.get("direction") == "backward")]
            
            # Update the frame to the processing flags
            self.processing_flags.update({"frame": frame})
            
        except Exception as e:
            error = e

        return (image, selected_channel, frame, error)



    # Spectrum operations
    def process_spectrum(self, spectrum: dict, index: int = 0) -> tuple[dict, bool | str]:
        error = False
        flags = self.spec_processing_flags
                
        try:
            (spectrum, error) = self.crop_unfinished_spectrum(spectrum)
            if error: raise Exception(error)

            if flags.get("moving_average"): (spectrum, error) = self.moving_average(spectrum, flags.get("moving_average_window", 1))
            if error: raise Exception(error)
           
            if flags.get(f"differentiate_{index}"): (spectrum, error) = self.differentiate(spectrum)
            if error: raise Exception(error)
            
            if flags.get(f"log_abs_{index}"): (spectrum, error) = self.apply_log_abs(spectrum)
            if error: raise Exception(error)
            
            (spectrum, error) = self.choose_direction(spectrum)
            if error: raise Exception(error)

        except Exception as e:
            error = e
        
        return (spectrum, error)

    def crop_unfinished_spectrum(self, spectrum: dict) -> tuple[dict, bool | str]:
        error = False
        
        try:
            x_data = spectrum.get("x_data")
            y_data = spectrum.get("y_data")
            
            mask = np.isfinite(x_data) & np.isfinite(y_data)
            if np.all(mask): first_nan_index = len(x_data)
            else: first_nan_index = np.argmax(~mask)

            # Slice both arrays up to the first NaN index
            x_data_cropped = x_data[:first_nan_index]
            y_data_cropped = y_data[:first_nan_index]
            
            spectrum.update({"x_data": x_data_cropped, "y_data": y_data_cropped})
            
            if "y_bwd_data" in spectrum.keys():
                y_data = spectrum.get("y_bwd_data")
   
                mask = np.isfinite(x_data) & np.isfinite(y_data)
                if np.all(mask): first_nan_index = len(x_data)
                else: first_nan_index = np.argmax(~mask)

                # Slice both arrays up to the first NaN index
                x_data_cropped = x_data[:first_nan_index]
                y_data_cropped = y_data[:first_nan_index]
                
                spectrum.update({"x_bwd_data": x_data_cropped, "y_bwd_data": y_data_cropped})
                
        except Exception as e:
            error = e
        
        return (spectrum, error)

    def choose_direction(self, spectrum: dict) -> tuple[dict, bool | str]:
        error = False
        
        try:
            spec_direction = self.spec_processing_flags.get("direction")
            match spec_direction:
                case "fwd":
                    spectrum.pop("y_bwd_data")
                case "bwd":
                    x_bwd_data = spectrum.get("x_bwd_data")
                    y_bwd_data = spectrum.get("y_bwd_data")
                    spectrum.update({"y_data": y_bwd_data, "x_data": x_bwd_data})
                    spectrum.pop("x_bwd_data")
                    spectrum.pop("y_bwd_data")
                case "average":
                    x_fwd_data = spectrum.get("x_data")
                    x_bwd_data = spectrum.get("x_bwd_data")
                    y_fwd_data = spectrum.get("y_data")
                    y_bwd_data = spectrum.get("y_bwd_data")
                    
                    if isinstance(x_bwd_data, np.ndarray):
                        len_data = min(len(y_fwd_data), len(y_bwd_data))
                        y_data = [0.5 * y_fwd_data[index] + 0.5 * y_bwd_data[index] for index in range(len_data)]
                        x_data = [0.5 * x_fwd_data[index] + 0.5 * x_bwd_data[index] for index in range(len_data)]
                    else:
                        y_data = y_fwd_data
                    spectrum.update({"y_data": y_data})
                    spectrum.update({"x_data": x_data})
                    spectrum.pop("x_bwd_data")
                    spectrum.pop("y_bwd_data")
                case "fwd_bwd":
                    pass
                case _:
                    pass
        except Exception as e:
            error = e
        
        return (spectrum, error)
    
    def apply_log_abs(self, spectrum: dict) -> tuple[dict, bool | str]:
        error = False
        
        try:
            y_fwd_data = spectrum.get("y_data")
            y_fwd_abs = np.abs(y_fwd_data)
            y_fwd_abs_log = np.log10(y_fwd_abs)
            spectrum.update({"y_data": y_fwd_abs_log})
                        
            y_bwd_data = spectrum.get("y_bwd_data")
            if isinstance(y_bwd_data, np.ndarray):
                y_bwd_abs = np.abs(y_bwd_data)
                y_bwd_abs_log = np.log10(y_bwd_abs)
                spectrum.update({"y_bwd_data": y_bwd_abs_log})
        except Exception as e:
            error = e
        
        return (spectrum, error)

    def differentiate(self, spectrum: dict) -> tuple[dict, bool | str]:
        error = False

        try:
            y_data = spectrum.get("y_data")
            x_data = spectrum.get("x_data")
            
            dx = x_data[1] - x_data[0]
            dy = np.diff(y_data)
            dydx = dy / dx
            x_avg = np.convolve(x_data, np.array([0.5, 0.5]), mode = "valid")
            
            spectrum.update({"x_data": x_avg, "y_data": dydx})

            x_bwd_data = spectrum.get("x_bwd_data")
            y_bwd_data = spectrum.get("y_bwd_data")
            
            if isinstance(x_bwd_data, np.ndarray) and isinstance(y_bwd_data, np.ndarray):
                x_avg = np.convolve(x_bwd_data, np.array([0.5, 0.5]), mode = "valid")
                
                dy_bwd = np.diff(y_bwd_data)
                dy_bwddx = dy_bwd / dx
                
                spectrum.update({"y_bwd_data": x_avg, "y_bwd_data": dy_bwddx})
    
        except Exception as e:
            error = e
        
        return (spectrum, error)

    def moving_average(self, spectrum: dict, window: int) -> tuple[dict, bool | str]:
        error = False
        
        try:            
            kernel = np.ones(shape = window, dtype = float)
            kernel /= np.sum(kernel)
                                    
            x_data = spectrum.get("x_data")
            y_data = spectrum.get("y_data")
            
            smooth_x_data = np.convolve(x_data, kernel, mode = "valid")
            smooth_y_data = np.convolve(y_data, kernel, mode = "valid")                        
            spectrum.update({"x_data": smooth_x_data, "y_data": smooth_y_data})
            
            if "x_bwd_data" in spectrum.keys():
                x_data = spectrum.get("x_bwd_data")
                y_data = spectrum.get("y_bwd_data")
                
                smooth_x_data = np.convolve(x_data, kernel, mode = "valid")
                smooth_y_data = np.convolve(y_data, kernel, mode = "valid")
                spectrum.update({"x_bwd_data": smooth_x_data, "y_bwd_data": smooth_y_data})
        
        except Exception as e:
            error = e
        
        return (spectrum, error)



    # Image operations
    def process_scan(self, image: np.ndarray) -> tuple[np.ndarray, dict, list, bool | str]:
        error = False
        statistics = False
        limits = [0, 1]

        try:
            # Apply matrix operations
            (processed_scan, error) = self.operate_scan(image)
            if error: raise Exception(error)

            # Calculate the image statistics and display them
            (statistics, error) = self.get_image_statistics(processed_scan)
            if error: raise Exception(error)
        
            # Calculate the limits
            (limits, error) = self.calculate_limits(processed_scan)
            self.processing_flags["min_limit"] = limits[0]
            self.processing_flags["max_limit"] = limits[1]
            if error: raise Exception(error)
        
        except Exception as e:
            error = e
        
        return (processed_scan, statistics, limits, error)

    def operate_scan(self, image: np.ndarray) -> tuple[np.ndarray, bool | str]:
        error = False
        flags = self.processing_flags
        gaussian_sigma = flags["gaussian_width (nm)"]
        scan_range_nm = flags["scan_range (nm)"]
        
        # Background subtraction
        (image, error) = self.subtract_background(image)
        if error: return (image, error)
        
        # Matrix operations
        if flags["sobel"]: (image, error) = self.image_gradient(image, scan_range_nm)
        if error: return (image, error)
        
        if flags["normal"]: (image, error) = self.compute_normal(image, scan_range_nm)
        if error: return (image, error)
        
        if flags["laplace"]: (image, error) = self.apply_laplace(image, scan_range_nm)
        if error: return (image, error)
        
        if flags["gaussian"]: (image, error) = self.apply_gaussian(image, gaussian_sigma, scan_range_nm)
        if error: return (image, error)
        
        if flags["fft"]: (image, error) = self.apply_fft(image, scan_range_nm)
        if error: return (image, error)
        
        # Set phase
        (image, error) = self.apply_phase(image)
        if error:
            return (image, error)

        # Perform the correct projection
        try:
            match flags["projection"]:
                case "im": image = np.imag(image)
                case "abs": image = np.abs(image)
                case "abs^2": image = np.abs(image) ** 2
                case "arg (b/w)": image = np.angle(image)
                case "arg (hue)": (image, error) = self.complex_image_to_colors(image, saturate = True)
                case "complex": (image, error) = self.complex_image_to_colors(image, saturate = False)
                case "log(abs)": image = np.log(np.abs(image))
                case _: image = np.real(image)
        except:
            pass    
        return (image, error)
 
    def calculate_limits(self, image: np.ndarray) -> tuple[list, bool | str]:
        error = False
        limits = [0, 1]
        min_value = 0
        max_value = 0
        min_limit = 0
        max_limit = 0
        
        flags = self.processing_flags
        
        try:
            (statistics, error) = self.get_image_statistics(image)
            if error:
                print(f"Something went awry: {error}")
                raise
            data_sorted = statistics.get("data_sorted")
            min_method = flags.get("min_method")
            max_method = flags.get("max_method")
            min_value = float(flags.get("min_method_value"))
            max_value = float(flags.get("max_method_value"))
            
            match min_method:
                case "full":
                    min_limit = statistics.get("min")
                case "absolute":
                    min_limit = min_value
                case "percentiles":
                    min_limit = data_sorted[int(.01 * min_value * len(data_sorted))]
                case "deviations":
                    min_limit = statistics.get("mean") - min_value * statistics.get("standard_deviation")
                case _:
                    min_limit = min_value

            match max_method:
                case "full":
                    max_limit = statistics.get("max")
                case "absolute":
                    max_limit = max_value
                case "percentiles":
                    max_limit = data_sorted[int(.01 * max_value * len(data_sorted))]
                case "deviations":
                    max_limit = statistics.get("mean") + max_value * statistics.get("standard_deviation")
                case _:
                    max_limit = max_value

            limits = [min_limit, max_limit]
        except Exception as e:
            error = e

        return (limits, error)



    def apply_phase(self, image: np.ndarray) -> tuple[np.ndarray, bool | str]:
        error = False
        phase_shifted_image = image
        
        if not isinstance(image, np.ndarray):
            error = "Error. The provided image is not a numpy array."
            return (image, error)

        try:
            phase = self.processing_flags.get("phase", 0)
            if phase == 0: return(image, error)
            phase_factor = np.exp(1j * phase * np.pi / 180)
            phase_shifted_image = phase_factor * image
            
            return(phase_shifted_image, error)

        except Exception as e:
            error = e
            return(image, error)
    
    def apply_gaussian(self, image: np.ndarray, sigma: float = 2, scan_range = None) -> tuple[np.ndarray, bool | str]:
        error = False

        if not isinstance(image, np.ndarray):
            error = "Error. The provided image is not a numpy array."
            return (image, error)

        sigma_px = sigma
        
        # If a scan range is provided, the Gaussian sigma will be in units of x instead of in units of pixels
        if isinstance(scan_range, np.ndarray) or isinstance(scan_range, list):
            grid_size = np.shape(image)

            try:
                x_range = scan_range[0]

                # Convert the x range to a numerical value (of the length in nm) if it is a pint quantity
                if isinstance(x_range, pint.Quantity): x_range = x_range.to("nm").magnitude

                px_per_dx = grid_size[0] / x_range
                sigma_px = sigma * px_per_dx
            except:
                error = "Error. Calculating Gaussian kernel failed."
                return (image, error)
        
        filtered_image = gaussian_filter(image, sigma = sigma_px)

        return (filtered_image, error)

    def image_gradient(self, image: np.ndarray, scan_range = None) -> tuple[np.ndarray, bool | str]:
        error = False

        if not isinstance(image, np.ndarray):
            error = "Error. The provided image is not a numpy array."
            return (image, error)
                
        sobel_x = .125 * np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype = float)
        sobel_y = .125 * np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype = float)
        try:
            ddx = convolve2d(image, sobel_x, mode = "valid") # These are the gradients computed using normalized sobel kernels
            ddy = convolve2d(image, sobel_y, mode = "valid")
        except:
            error = "Error. Calculating gradient failed."
            return (image, error)

        if isinstance(scan_range, np.ndarray) or isinstance(scan_range, list):
            # If a scan range is provided, the gradients will be calculated as derivatives wrt to x and y rather than wrt pixel index
            grid_size = np.shape(image)

            try:
                x_range = scan_range[0]
                y_range = scan_range[1]

                # Convert the range to numerical value (of the length in nm) if it is a pint quantity
                if isinstance(x_range, pint.Quantity): x_range = x_range.to("nm").magnitude
                if isinstance(y_range, pint.Quantity): y_range = y_range.to("nm").magnitude

                dx_per_px = x_range / grid_size[0]
                dy_per_px = y_range / grid_size[1]
                ddx /= dx_per_px
                ddy /= dy_per_px
            except:
                error = "Error. Calculating gradient failed."
        
        gradient_image = ddx + 1j * ddy

        return (gradient_image, error)

    def compute_normal(self, image: np.ndarray, scan_range = None) -> tuple[np.ndarray, bool | str]:
        error = False

        if not isinstance(image, np.ndarray):
            error = "Error. The provided image is not a numpy array."
            return (image, error)
        
        sobel_x = .125 * np.array([[-1, 0, 1], [-2, 0, 2], [-1, 0, 1]], dtype = float)
        sobel_y = .125 * np.array([[-1, -2, -1], [0, 0, 0], [1, 2, 1]], dtype = float)
        ddx = convolve2d(image, sobel_x, mode = "valid") # These are the gradients computed using normalized sobel kernels
        ddy = convolve2d(image, sobel_y, mode = "valid")

        if isinstance(scan_range, np.ndarray) or isinstance(scan_range, list):
            # If a scan range is provided, the gradients will be calculated as derivatives wrt to x and y rather than wrt pixel index
            grid_size = np.shape(image)

            try:
                x_range = scan_range[0]
                y_range = scan_range[1]

                # Convert the range to numerical value (of the length in nm) if it is a pint quantity
                if isinstance(x_range, pint.Quantity): x_range = x_range.to("nm").magnitude
                if isinstance(y_range, pint.Quantity): y_range = y_range.to("nm").magnitude

                dx_per_px = x_range / grid_size[0]
                dy_per_px = y_range / grid_size[1]
                ddx /= dx_per_px
                ddy /= dy_per_px

            except:
                error = "Error. Calculating gradient failed."
                return (image, error)

        gradient_vec_length = ddx ** 2 + ddy ** 2
        norm_vec_length = 1 + gradient_vec_length
        normals_image = 1 / np.sqrt(norm_vec_length)

        return (normals_image, error)

    def apply_laplace(self, image: np.ndarray, scan_range = None) -> tuple[np.ndarray, bool | str]:
        error = False

        if not isinstance(image, np.ndarray):
            error = "Error. The provided image is not a numpy array."
            return (image, error)
        
        laplace_kernel = np.array([[0, 1, 0], [1, -4, 1], [0, 1, 0]], dtype = float)
        laplacian = convolve2d(image, laplace_kernel, mode = "valid")

        if isinstance(scan_range, np.ndarray) or isinstance(scan_range, list):
            # If a scan range is provided, the gradients will be calculated as derivatives wrt to x and y rather than wrt pixel index
            grid_size = np.shape(image)

            try:
                x_range = scan_range[0]
                
                # Convert the x range to a numerical value (of the length in nm) if it is a pint quantity
                if isinstance(x_range, pint.Quantity): x_range = x_range.to("nm").magnitude

                dx2_per_px = x_range ** 2 / grid_size[0]
                laplacian /= dx2_per_px
            
            except:
                error = "Error. Calculating gradient failed."
                return (image, error)
        
        return (laplacian, error)

    def apply_fft(self, image: np.ndarray, scan_range = None) -> tuple[np.ndarray, bool | str]:
        error = False
        
        if not isinstance(image, np.ndarray):
            error = "Error. The provided image is not a numpy array."
            return (image, error)
        
        grid_size = np.shape(image)
        
        # If no scan range units are provided, the reciprocal range is also unitless
        x_range = grid_size[0]
        y_range = grid_size[1]
        reciprocal_range = [1 / x_range, 1 / y_range]

        if isinstance(scan_range, np.ndarray) or isinstance(scan_range, list):
            # If a scan range is provided, the reciprocal range can be calculated in terms of nm-1
            
            try:
                ureg = pint.UnitRegistry()
                x_range = scan_range[0]
                y_range = scan_range[1]

                # Convert the range to numerical value (of the length in nm) if it is a pint quantity
                if isinstance(x_range, pint.Quantity): x_range = x_range.to("nm").magnitude
                if isinstance(y_range, pint.Quantity): y_range = y_range.to("nm").magnitude

                px_per_nm_x = grid_size[0] / x_range
                px_per_nm_y = grid_size[1] / y_range
                reciprocal_range = [ureg.Quantity(px_per_nm_y, "1/nm"), ureg.Quantity(px_per_nm_y, "1/nm")]

            except:
                error = "Error. Calculating reciprocal range failed."
                return (image, error)

        fft_image = fftshift(fft2(image))

        return (fft_image, error)

    def line_subtract(self, image: np.ndarray) -> tuple[np.ndarray, bool | str]:
        error = False

        if not isinstance(image, np.ndarray):
            error = "Error. The provided image is not a numpy array."
            return (image, error)
        
        image_subtracted = []
        try:
            for line in image:
                x = range(len(line))
                # Construct the design matrix A for a linear fit (y = mx + c)
                # The first column is x, the second is a column of ones for the intercept
                A = np.vstack([x, np.ones(len(x))]).T

                # Perform the least squares fit
                coefficients, residuals, rank, singular_values = lstsq(A, line)
                y_fit = coefficients[1] + coefficients[0] * x
                line_subtracted = line - y_fit

                image_subtracted.append(line_subtracted)

            image_subtracted = np.array(image_subtracted, dtype = float)
        
        except:
            error = "Error. Line subtraction algorithm failed."
            return (image, error)

        return (image_subtracted, error)

    def complex_image_to_colors(self, image: np.ndarray, saturate: bool = False) -> tuple[np.ndarray, bool | str]:
        error = False

        if not isinstance(image, np.ndarray):
            error = "Error. The provided image is not a numpy array."
            return (image, error)
        
        try:
            magnitude = np.abs(image)
            phase = np.angle(image)
            phase_norm = (phase + np.pi) / (2 * np.pi)
            
            if saturate:
                hsv_matrix = np.dstack((phase_norm, np.ones_like(phase_norm), np.ones_like(phase_norm)))
            else:
                hsv_matrix = np.dstack((phase_norm, np.ones_like(phase_norm), magnitude))
            
            # Convert from HSV color space to RGB
            rgb_array = colors.hsv_to_rgb(hsv_matrix)
        
        except:
            error = "Error. Computing the colorized complex image failed."
            return (image, error)
        
        return (rgb_array, error)

    def subtract_background(self, image: np.ndarray) -> tuple[np.ndarray, bool | str]:
        error = False
        input_image = image
        mode = self.processing_flags.get("background", "none")

        if not isinstance(image, np.ndarray):
            error = "Error. The provided image is not a numpy array."
            return (image, error)
        
        try:
            # Unfinished scans: remove NaN rows
            num_rows = len(image)
            nan_mask = np.isnan(image).any(axis = 1)
            image = image[~nan_mask]
            non_nan_rows = len(image)

            if non_nan_rows < 3: # Do not perform data processing if the scan is all NaNs
                return (input_image, error)

            avg_image = np.mean(image.flatten()) # The average value of the image, or the offset
            (gradient_image, error) = self.image_gradient(image) # The (complex) gradient of the image
            if error: return (image, error)
            avg_gradient = np.mean(gradient_image.flatten()) # The average value of the gradient
            if not isinstance(avg_gradient, complex):
                error = "Error. Could not compute average gradient for background subtraction."
                return (input_image, error)

            pix_y, pix_x = np.shape(image)
            x_values = np.arange(-(pix_x - 1) / 2, pix_x / 2, 1)
            y_values = np.arange(-(pix_y - 1) / 2, pix_y / 2, 1)

            plane = np.array([[-x * np.real(avg_gradient) - y * np.imag(avg_gradient) for x in x_values] for y in y_values])

            match mode:
                case "plane":
                    processed_image = image - plane - avg_image
                case "linewise":
                    (processed_image, error) = self.line_subtract(image)
                case "average":
                    processed_image = image - avg_image
                case _:
                    processed_image = image
            
            # Pad the NaN rows back
            if num_rows - non_nan_rows > 0: processed_image = np.pad(processed_image, ((0, num_rows - non_nan_rows), (0, 0)), mode = 'constant', constant_values = np.nan)
    
            return (processed_image, error)
        
        except Exception as e:
            error = f"Error. Failed to perform the background subtraction: {e}"
            return (input_image, error)



    # Statistics
    def get_image_statistics(self, image: np.ndarray, pixels_per_bin: int = 200) -> tuple[dict, bool | str]:
        error = False

        try:
            data_sorted_c = np.sort(image.flatten())
            data_sorted = np.real(data_sorted_c)
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

            image_statistics = {
                "data_sorted": data_sorted,
                "n_pixels": n_pixels,
                "min": range_min,
                "Q1": Q1,
                "mean": range_mean,
                "average": range_mean,
                "Q2": Q2,
                "median": Q2,
                "Q3": Q3,
                "max": range_max,
                "range_total": range_total,
                "standard_deviation": standard_deviation
            }
        except:
            error = "Error. Image statistics could not be calculated."
            return ({}, error)
        
        try:
            n_bins = int(np.floor(n_pixels / pixels_per_bin))
            counts, bounds = np.histogram(data_sorted, bins = n_bins)
            binsize = bounds[1] - bounds[0]
            padded_counts = np.pad(counts, 1, mode = "constant")
            bincenters = np.concatenate([[bounds[0] - .5 * binsize], np.convolve(bounds, [.5, .5], mode = "valid"), [bounds[-1] + .5 * binsize]])
            histogram = np.array([bincenters, padded_counts])

            image_statistics.update({"histogram": histogram})
        except:
            error = "Error. Histogram could not be calculated."
            return (image_statistics, error)

        return (image_statistics, error)



class UserData:
    def __init__(self):
        script_path = os.path.abspath(__file__)
        lib_folder = os.path.dirname(script_path)
        scantelligent_folder = os.path.dirname(lib_folder)
        sys_folder = os.path.join(scantelligent_folder, "sys")
        self.parameters_file = os.path.join(sys_folder, "user_parameters.yml")

        self.frames = [
            {}, {}, {}
        ]
        (self.scan_parameters, self.tip_prep_parameters, self.coarse_parameters) = self.load_parameter_sets()
        self.windows = [{}, {}, {}]
        self.coarse_parameters = [{}, {}, {}]


    
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
        
        try: # Read the last scan file from the config yaml file
            with open(path, "r") as file:
                yaml_data = yaml.safe_load(file)
        except Exception as e:
            error = e

        return (yaml_data, error)
    
    def load_parameter_sets(self):
        (yaml_data, error) = self.load_yaml(self.parameters_file)
        
        scan_parameters = []
        tip_prep_parameters = []
        coarse_parameters = []
        
        for parameter_set_type, dicts_set in yaml_data.items():
            
            match parameter_set_type:
                case "scan_parameters":
                    for key, parameters_dict in dicts_set.items():
                        scan_parameters.append(parameters_dict)
                
                case "tip_prep_parameters":
                    for key, parameters_dict in dicts_set.items():
                        tip_prep_parameters.append(parameters_dict)
                
                case "coarse_parameters":
                    for key, parameters_dict in dicts_set.items():
                        coarse_parameters.append(parameters_dict)
                
                case _:
                    pass

        return (scan_parameters, tip_prep_parameters, coarse_parameters)
    
    def save_parameter_sets(self):
        output_dict = {"scan_parameters": {}, "other_parameters": {}, "tip_prep_parameters": {}}
        
        for index, set in enumerate(self.scan_parameters):
            output_dict["scan_parameters"].update({index: set})
        
        for index, set in enumerate(self.tip_prep_parameters):
            output_dict["tip_prep_parameters"].update({index: set})

        self.save_yaml(output_dict, self.parameters_file)
        return

