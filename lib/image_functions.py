import numpy as np
from scipy.signal import convolve2d
from scipy.ndimage import gaussian_filter
from scipy.fft import fft2, fftshift
from matplotlib import colors
from scipy.linalg import lstsq
import pint



def apply_gaussian(image, sigma = 2, scan_range = None) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        print("Error. The provided image is not a numpy array.")
        return image

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
            print("Error. Calculating Gaussian kernel failed.")
    
    filtered_image = gaussian_filter(image, sigma = sigma_px)

    return filtered_image



def image_gradient(image, scan_range = None) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        print("Error. The provided image is not a numpy array.")
        return image
    
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
            print("Error. Calculating gradient failed.")
    
    gradient_image = ddx + 1j * ddy

    return gradient_image



def compute_normal(image, scan_range = None) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        print("Error. The provided image is not a numpy array.")
        return image
    
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
            print("Error. Calculating gradient failed.")

    gradient_vec_length = ddx ** 2 + ddy ** 2
    norm_vec_length = 1 + gradient_vec_length
    normals = 1 / np.sqrt(norm_vec_length)

    return normals



def apply_laplace(image, scan_range = None) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        print("Error. The provided image is not a numpy array.")
        return image
    
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
            print("Error. Calculating gradient failed.")
    
    return laplacian



def apply_fft(image, scan_range = None) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        print("Error. The provided image is not a numpy array.")
        return image
    
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
            print("Error. Calculating reciprocal range failed.")

    fft_image = fftshift(fft2(image))

    return fft_image, reciprocal_range



def line_subtract(image) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        print("Error. The provided image is not a numpy array.")
        return image
    
    image_subtracted = []
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

    return image_subtracted



def complex_image_to_colors(image, saturate: bool = False) -> np.ndarray:
    if not isinstance(image, np.ndarray):
        print("Error. The provided image is not a numpy array.")
        return image
    
    magnitude = np.abs(image)
    phase = np.angle(image)
    phase_norm = (phase + np.pi) / (2 * np.pi)
    
    if saturate:
        hsv_matrix = np.dstack((phase_norm, np.ones_like(phase_norm), np.ones_like(phase_norm)))
    else:
        hsv_matrix = np.dstack((phase_norm, np.ones_like(phase_norm), magnitude))
    
    # Convert from HSV color space to RGB
    rgb_array = colors.hsv_to_rgb(hsv_matrix)
    
    return rgb_array



def background_subtract(image, mode: str = "plane") -> np.ndarray:
    if not isinstance(image, np.ndarray):
        print("Error. The provided image is not a numpy array.")
        return image

    try:
        avg_image = np.mean(image.flatten()) # The average value of the image, or the offset
        gradient_image = image_gradient(image) # The (complex) gradient of the image
        avg_gradient = np.mean(gradient_image.flatten()) # The average value of the gradient

        pix_y, pix_x = np.shape(image)
        x_values = np.arange(-(pix_x - 1) / 2, pix_x / 2, 1)
        y_values = np.arange(-(pix_y - 1) / 2, pix_y / 2, 1)

        plane = np.array([[-x * np.real(avg_gradient) - y * np.imag(avg_gradient) for x in x_values] for y in y_values])

        if mode == "plane":
            return image - plane - avg_image
        elif mode == "linewise":
            return line_subtract(image)
        elif mode == "average":
            return image - avg_image
        else:
            return image

    except Exception as e:
        print(f"Error performing the background subtraction: {e}")
        return image



def get_image_statistics(image, pixels_per_bin: int = 200) -> dict:
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
        "standard_deviation": standard_deviation,
        "histogram": histogram
    }

    return image_statistics