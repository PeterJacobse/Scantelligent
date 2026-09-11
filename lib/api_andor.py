import os, re
import numpy as np
from PyQt6 import QtCore
import pylablib
from pylablib.devices import Andor



class AndorAPI(QtCore.QObject):
    """
    API for communicating with the Andor camera and spectrometer.
    Will work when paths to validly configured dlls are provided.
    Will not work if another stream to Andor is set up (e.g. if Solis is open)
    """
    def __init__(self, sdk_path: str = "", shamrock_path: str = ""):
        if os.path.isdir(sdk_path) or os.path.isfile(sdk_path):
            self.sdk_path = sdk_path
        else:
            print("Invalid path for Andor SDK. Attempting fallback to default path")
            self.sdk_path = "C:\\Program Files\\Andor SDK"
        if os.path.isdir(shamrock_path) or os.path.isfile(shamrock_path):
            self.shamrock_path = shamrock_path
        else:
            print("Invalid path for Andor SDK 64 bit Shamrock dll. Attempting fallback to default path")
            self.shamrock_path = os.path.join(sdk_path, "Shamrock64")

        pylablib.par["devices/dlls/show_load_errors"] = True
        pylablib.par["devices/dlls/andor_sdk2"] = os.path.join(self.sdk_path, "atmcd64.dll")
        pylablib.par["devices/dlls/andor_shamrock"] = self.shamrock_path
        os.add_dll_directory(sdk_path)
        os.add_dll_directory(shamrock_path)
        super().__init__()



    def link(self, cooldown: bool = True, T_setpoint: float = -85.) -> None:
        """Instantiates the 'cam' and 'spec' handles to communicate with the Andor camera and spectrograph, respectively

        Args:
            cooldown (bool, optional): Whether or not to cool the camera down. Defaults to True.
            T_setpoint (float): Camera temperature setpoint in deg C. Defaults to -85.
        """
        spectrographs = Andor.list_shamrock_spectrographs()
        if len(spectrographs) < 1:
            print("Error! I could not find any spectrographs")
            return
        
        print(f"I found the following spectrographs: {spectrographs}\nNow attempting to instantiate the 'cam' and 'spec' attributes.")
        
        cam = Andor.AndorSDK2Camera(idx = 0, ini_path = self.sdk_path) # Instantiate the camera
        spec = Andor.ShamrockSpectrograph(idx = 0) # Instantiate the peripherals
        spec.setup_pixels_from_camera(cam) # Set up the calibrations

        # Make sure the camera is cooled and the shutter is closed
        cam.setup_shutter(mode = "closed")
        if cooldown: self.cooldown(T_setpoint = T_setpoint)

        cam.set_acquisition_mode("single") # We want to acquire single spectra
        cam.set_exposure(3.0) # Targeted exposure time in seconds
        
        self.cam = cam
        self.spec = spec
        print(f"Initialization successful. The camera and spectrograph are accessible as attributes 'cam' and 'spec', respectively.")
        return

    def cooldown(self, T_setpoint: float | int | None = None) -> None:
        if isinstance(T_setpoint, float | int): self.cam.set_temperature(T_setpoint, enable_cooler = True)
        self.cam.set_fan_mode("full")
        T_camera = self.cam.get_temperature()
        T_setpoint_measured = self.cam.get_temperature_setpoint()
        print(f"Cooldown started. Current temperature: {T_camera = } C; T_setpoint = {T_setpoint_measured} C.")
        return

    def warmup(self) -> None:
        self.cam.set_fan_mode("off")
        T_camera = self.cam.get_temperature()
        print(f"Warmup started. Current temperature: {T_camera = } C.")
        return

    def shutdown(self, cooler_off: bool = False, wait_for_warmup: bool = False) -> None:
        camera = self.cam
        spectrograph = self.spec
        
        camera.setup_shutter("closed") # Close the shutter
        camera.set_cooler(on = not cooler_off)
        if cooler_off: camera.set_fan_mode("off")
        spectrograph.close()
        print(f"Andor spectrograph is closed")
        
        if not wait_for_warmup:
            camera.close()
            print(f"Andor camera is closed")
            return
        
        if cooler_off:
            T_camera = camera.get_temperature()
            while T_camera < -20:
                print(f"Waiting for camera to warm up to above -20 C. Current camera temperature: {T_camera} C")
                T_camera = camera.get_temperature()
                time.sleep(5)
        
        camera.close()
        print(f"Andor camera is closed")
        return
    
    def get_temperature(self) -> float:
        return self.cam.get_temperature()

    def get_temperature_setpoint(self) -> float | None:
        return self.cam.get_temperature_setpoint()

    def set_exposure_time(self, time_s: float = 3) -> None:
        self.cam.set_exposure(time_s)
        return

    def get_spectrum(self, time_s: float = 3, max_temperature_difference: float = 8) -> np.ndarray:
        """Acquire a spectrum from the Andor camera. A spectrum will not be acquired if the camera is too warm.

        Args:
            time_s (float, optional): Exposure time in seconds. Defaults to 3.
            max_temperature_difference (float, optional): Threshold temperature difference in deg C or K between actual and setpoint temperature before permitting acquisition. Defaults to 8.

        Returns:
            np.ndarray: Spectrum, with first row the wavelengths and the second row the intensities.
        """
        camera = self.cam
        spectrograph = self.spec

        camera.set_read_mode("fvb")
        T_camera = camera.get_temperature()
        T_setpoint = camera.get_temperature_setpoint()
        shutter = camera.get_shutter()
        wavelengths_nm = spectrograph.get_calibration() * 1E9
        
        if abs(T_camera - T_setpoint) > max_temperature_difference:
            print(f"The camera temperature ({T_camera = } C) is too far from the setpoint temperature ({T_setpoint = } C). Aborting the acquisition.")
            intensities = np.zeros_like(wavelengths_nm)
            return np.empty((2, 2))
        else:
            if not shutter == "open": print(f"Warning. Acquiring a spectrum with the shutter closed.")    
            self.cam.set_exposure(time_s)
            intensities = camera.snap(timeout = time_s + 1.)[0]
        
        spectrum = np.array([wavelengths_nm, intensities], dtype = np.float32)
        return spectrum
    
    def open_shutter(self, open: bool = True) -> None:
        """Opens the camera shutter

        Args:
            close (bool, optional): Defaults to True. Passing False closes the shutter instead.
        """
        if open: self.cam.setup_shutter("open")
        else: self.cam.setup_shutter("closed")

    def close_shutter(self, close: bool = True) -> None:
        """Closes the camera shutter

        Args:
            close (bool, optional): Defaults to True. Passing False opens the shutter instead.
        """
        if close: self.cam.setup_shutter("closed")
        else: self.cam.setup_shutter("open")

    def get_flipper(self, side: int | str) -> str:
        """Get the state of a flipper mirror

        Args:
            side (int | str): Could be an index (1 or 2) or "input" or "output".

        Returns:
            str: "direct" or "side" or "unknown".
        """
        flipper_state = "unknown"
        if self.spec.is_flipper_present(side): flipper_state = self.spec.get_flipper_port(side)
        return flipper_state

    def get_flippers(self) -> dict[str, str]:
        """Get the states of the flipper mirrors

        Returns:
            dict[str, str]: {"input": input_mirror_state, "output": output_mirror_state}
        """
        input_flipper_state = self.get_flipper("input")
        output_flipper_state = self.get_flipper("output")        
        return {"input": input_flipper_state, "output": output_flipper_state}

    def set_flipper(self, flipper: int | str = "input", state: str | None = None) -> None:
        if not flipper in {"input", "output", 1, 2}:
            print(f"Invalid value '{flipper = }' in AndorAPI.set_flipper. Valid input values are \"input\", \"output\", 1, and 2")
            return
        if not state in {"direct", "side"}:
            print(f"Invalid value '{state = }' in AndorAPI.set_flipper. Valid input values are \"side\", \"direct\"")
            return
        try: self.spec.set_flipper_port(flipper, state)
        except Exception as e: print(f"Unable to set flipper: {e}")
        return

    def set_flippers(self, values: list | dict | None = None) -> None:
        if isinstance(values, dict): [self.set_flipper(key, value) for key, value in values.items()]
        elif isinstance(values, list): [self.set_flipper(number, value) for number, value in enumerate(values)]
        return

    def get_grating(self, grating_number: int | None = None, print_info: bool = True) -> int:
        if isinstance(grating_number, int) and 0 < grating_number < 5:
            tgi = self.spec.get_grating_info(grating_number)
            output_str = f"Grating information for grating number {grating_number}:\tLines = {tgi.lines}\tBlaze wavelength = {tgi.blaze_wavelength}\tHome = {tgi.home}\tOffset = {tgi.offset}"
        else:
            grating_number = self.spec.get_grating()
            tgi = self.spec.get_grating_info()
            output_str = f"Grating information for current grating:\tIndex = {grating_number}\tLines = {tgi.lines}\tBlaze wavelength = {tgi.blaze_wavelength}\tHome = {tgi.home}\tOffset = {tgi.offset}"        
        
        if print_info: print(output_str)
        assert isinstance(grating_number, int)
        return grating_number

    def get_gratings(self) -> None:
        for index in range(1, 5):
            try: self.get_grating(index)
            except: pass
        return

    def set_grating(self, grating_number: int | None = None) -> None:
        if not isinstance(grating_number, int): return
        try: self.spec.set_grating(grating_number)
        except Exception as e: print(f"Unable to set grating to {grating_number}: {e}")
        return



# andor = AndorAPI(sdk_path = "C:\\Program Files\\Andor SDK", shamrock_path = "C:\\Program Files\\Andor SDK\\Shamrock64")


