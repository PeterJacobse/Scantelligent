import os, re, time
import numpy as np
from PyQt6 import QtCore
import pylablib
from pylablib.devices import Andor
from typing import Literal
from lib import NanonisAPI # For type checking
from concurrent.futures import ThreadPoolExecutor



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
        
        self.experiments = AndorExperiments(parent = self)



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

        cam.set_acquisition_mode("single") # We want to acquire single spectra
        cam.set_exposure(3.0) # Targeted exposure time in seconds
        
        self.cam = cam
        self.spec = spec
        self.cam.set_cooler(on = False)
        if cooldown: self.cooldown(T_setpoint = T_setpoint)
        
        print(f"Initialization successful. The camera and spectrograph are accessible as attributes 'cam' and 'spec', respectively.")
        return

    def shutdown(self, cooler_off: bool = False, wait_for_warmup: bool = False) -> None:
        camera = self.cam
        spectrograph = self.spec
        if wait_for_warmup: cooler_off = True
        
        camera.setup_shutter("closed") # Close the shutter
        camera.set_cooler(on = not cooler_off)
        spectrograph.close()
        print(f"Andor spectrograph is closed")
        
        if not wait_for_warmup:
            camera.set_fan_mode("off")
            camera.close()
            print(f"Andor camera is closed")
            return
        
        if cooler_off:
            T_camera = camera.get_temperature()
            while T_camera < -20:
                print(f"Waiting for camera to warm up to above -20 C. Current camera temperature: {T_camera} C")
                T_camera = camera.get_temperature()
                time.sleep(5)
        
        camera.set_fan_mode("off")
        camera.close()
        print(f"Andor camera is closed")
        return
    
    def unlink(self, cooler_off: bool = False, wait_for_warmup: bool = False) -> None:
        return self.shutdown(cooler_off = cooler_off, wait_for_warmup = wait_for_warmup)



    def set_cooler(self, on: bool = True) -> None:
        self.cam.set_cooler(on = on)
        return

    def set_fan(self, mode: str = "high") -> None:
        if not mode in {"high", "low", "off"}:
            print(f"Unknown fan mode {mode}")
            return
        self.cam.set_fan_mode(mode)
        return

    def cooldown(self, T_setpoint: float | int | None = None) -> None:
        if isinstance(T_setpoint, float | int): self.cam.set_temperature(T_setpoint, enable_cooler = False)
        self.cam.set_fan_mode("full")
        self.cam.set_cooler(on = True)
        T_camera = self.cam.get_temperature()
        T_setpoint_measured = self.cam.get_temperature_setpoint()
        print(f"Cooldown started. Current temperature: {T_camera = } C; T_setpoint = {T_setpoint_measured} C.")
        return

    def warmup(self) -> None:
        self.cam.set_cooler(on = False)
        self.cam.set_fan_mode("off")
        T_camera = self.cam.get_temperature()
        print(f"Warmup started. Current temperature: {T_camera = } C.")
        return

    def get_fan(self) -> str:
        return str(self.cam.get_fan_mode())

    def fan(self) -> str:
        return self.get_fan()

    def get_cooler(self) -> str:
        if self.cam.is_cooler_on(): return "on"
        else: return "off"

    def cooler(self) -> str:
        return self.get_cooler()

    def set_temperature_setpoint(self, T_setpoint: float | int | None = None) -> None:
        if not isinstance(T_setpoint, float | int): return
        self.cam.set_temperature(T_setpoint, enable_cooler = False)
        return

    def get_temperature(self) -> float:
        return self.cam.get_temperature()

    def temperature(self) -> float:
        return self.get_temperature()

    def get_temperature_setpoint(self) -> float | None:
        return self.cam.get_temperature_setpoint()



    def set_exposure_time(self, time_s: float = 3) -> None:
        self.cam.set_exposure(time_s)
        return

    def get_shutter(self) -> str:
        return self.cam.get_shutter()
    
    def shutter(self) -> str:
        return self.get_shutter()
    
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
        else:
            if not shutter == "open": print(f"Warning. Acquiring a spectrum with the shutter closed.")    
            self.cam.set_exposure(time_s)
            intensities = camera.snap(timeout = time_s + 1.)[0]
        
        spectrum = np.array([wavelengths_nm, intensities], dtype = np.float32)
        return spectrum



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

    def flipper(self, side: int | str) -> str:
        return self.get_flipper(side)

    def get_flippers(self) -> dict[str, str]:
        """Get the states of the flipper mirrors

        Returns:
            dict[str, str]: {"input": input_mirror_state, "output": output_mirror_state}
        """
        input_flipper_state = self.get_flipper("input")
        output_flipper_state = self.get_flipper("output")        
        return {"input": input_flipper_state, "output": output_flipper_state}
    
    def flippers(self) -> dict[str, str]:
        return self.get_flippers()

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
        
        print("Current grating:")
        try: self.get_grating()
        except: pass
        return

    def grating(self) -> None:
        return self.get_gratings()

    def set_grating(self, grating_number: int | None = None) -> None:
        if not isinstance(grating_number, int): return
        try: self.spec.set_grating(grating_number)
        except Exception as e: print(f"Unable to set grating to {grating_number}: {e}")
        return

    def set_mode(self, mode: Literal["acquisition", "alignment"]) -> None:
        """Convenience function that stores our specific parameters for the setup to toggle between acquisition and laser alignment"""
        
        match mode:
            case "acquisition":
                self.cooldown()
                self.set_flippers({'input': 'direct', 'output': 'direct'})
                self.set_grating(1)
                self.open_shutter()
            case _:
                self.close_shutter()
                self.set_flippers({"input": "direct", "output": "side"})
                self.set_grating(4)
                self.warmup()
        return



class AndorExperiments:
    def __init__(self, parent):
        self.parent: AndorAPI = parent
        
    def get_spectra_at_feedback(self, nanonis: NanonisAPI, V: float | int = 3.7, I_fb_pA: float | int = 8000., p_gain_pm: float | int = .2, t_const_us: float | int = 167., t_acquisition_s: float | int = 3., t_settle_s: float | int = 3., verbose: bool = True) -> dict[str, object]:
        andor = self.parent
        output_dict = {}
        tip_is_stable = True
        n_measurements = 100
        stability_measurement_dark = np.zeros((n_measurements, 3), dtype = np.float32)
        stability_measurement_bright = np.zeros((n_measurements, 3), dtype = np.float32)
        
        try:
            # Read parameters from Nanonis
            bias_dict, error = nanonis.update.bias()
            if error: raise Exception(error)
            feedback_dict, error = nanonis.update.feedback()
            if error: raise Exception(error)
            
            V_start = bias_dict["V (V)"]
            [I_fb_start, p_gain_start, t_const_start] = [feedback_dict.get(key, None) for key in ["I_fb (pA)", "p_gain (pm)", "t_const (us)"]]
            
            # Acquire a background spectrum using non-emission parameters while analyzing the tip height stability / current peaks            
            with ThreadPoolExecutor() as executor:
                if verbose: print("Acquiring emission background spectrum.")
                # Submit spectrum acquisition
                future = executor.submit(andor.get_spectrum, t_acquisition_s)
                
                # Tip stability analysis: measure the tip height stability / current peaks
                t_start = time.time()
                for iter in range(n_measurements):
                    tip_parameters, error = nanonis.update.tip(z_rel_nm = 0., fast_mode = True)
                    t_s = time.time() - t_start
                    [I_pA, z_nm] = [tip_parameters.get(key) for key in ["I (pA)", "z (nm)"]]
                    stability_measurement_dark[iter] = [t_s, I_pA, z_nm]
                output_dict.update({"stability_measurement_dark": stability_measurement_dark})
    
                I_pA_avg = np.average(stability_measurement_dark[:, 1])
                z_nm_avg = np.average(stability_measurement_dark[:, 2])
                z_nm_std = np.sqrt(np.var(stability_measurement_dark[:, 2]))
                I_pA_std = np.sqrt(np.var(stability_measurement_dark[:, 1]))
                if z_nm_std > .1 or I_pA_std > 40: tip_is_stable = False
                word = "stable" if tip_is_stable else "unstable"
                if verbose: print(f"Tip heights are distributed at z = ({z_nm_avg:.4f} +- {z_nm_std:.4f}) nm; Measured currents are I = ({I_pA_avg:.4f} +- {I_pA_std:.4f}) pA\nThe tip seems to be {word}")        
                output_dict.update({"I_pA_avg": I_pA_avg, "I_pA_std": I_pA_std, "z_nm_avg": z_nm_avg, "z_nm_std": z_nm_std, "tip_is_stable": tip_is_stable})
                
                # Retrieve the spectrum
                bg_spectrum = future.result()
            
            
            
            # Go into emission mode (bright mode)
            nanonis.update.tip(feedback = False, z_rel_nm = 0.)
            time.sleep(.2)
            nanonis.update.tip(feedback = False, z_rel_nm = 1.)
            nanonis.update.bias(V = V, dV_mV = 40)
            nanonis.update.feedback(I_fb_pA = I_fb_pA, p_gain_pm = p_gain_pm, t_const_us = t_const_us)
            nanonis.update.tip(feedback = True, z_rel_nm = 0.)
            if verbose: print("Tip is in emission mode. Checking stability.")
            time.sleep(t_settle_s)
                        
            # Acquiring the spectrum in bright mode while analyzing the tip height stability / current peaks            
            with ThreadPoolExecutor() as executor:
                # Submit spectrum acquisition
                if verbose: print("Acquiring emission spectrum.")
                future = executor.submit(andor.get_spectrum, t_acquisition_s)
                
                # Tip stability analysis: measure the tip height stability / current peaks
                t_start = time.time()
                for iter in range(n_measurements):
                    tip_parameters, error = nanonis.update.tip(z_rel_nm = 0., fast_mode = True)
                    t_s = time.time() - t_start
                    [I_pA, z_nm] = [tip_parameters.get(key) for key in ["I (pA)", "z (nm)"]]
                    stability_measurement_bright[iter] = [t_s, I_pA, z_nm]
                output_dict.update({"stability_measurement_bright": stability_measurement_bright})
    
                I_pA_avg = np.average(stability_measurement_bright[:, 1])
                z_nm_avg = np.average(stability_measurement_bright[:, 2])
                z_nm_std = np.sqrt(np.var(stability_measurement_bright[:, 2]))
                I_pA_std = np.sqrt(np.var(stability_measurement_bright[:, 1]))
                if z_nm_std > .1 or I_pA_std > 40: tip_is_stable = False
                word = "stable" if tip_is_stable else "unstable"
                if verbose: print(f"Tip heights are distributed at z = ({z_nm_avg:.4f} +- {z_nm_std:.4f}) nm; Measured currents are I = ({I_pA_avg:.4f} +- {I_pA_std:.4f}) pA\nThe tip seems to be {word}")        
                output_dict.update({"I_pA_avg": I_pA_avg, "I_pA_std": I_pA_std, "z_nm_avg": z_nm_avg, "z_nm_std": z_nm_std, "tip_is_stable": tip_is_stable})
                
                # Retrieve the spectrum
                spectrum = future.result()
            
            diff_spectrum = np.array([spectrum[0], spectrum[1] - bg_spectrum[1]], dtype = np.float32)
            combined_spectra = np.array([spectrum[0], bg_spectrum[1], spectrum[1], diff_spectrum[1]], dtype = np.float32)
            output_dict.update({"combined_spectra": combined_spectra})
            
            if max(diff_spectrum[1]) > 200:
                print("The difference spectrum has a peak at over 200 counts. That seems interesting.")

        except Exception as e:
            print(f"Error running get_spectra_at_feedback: {e}")
        
        finally:
            # Return to the start settings
            try:
                nanonis.update.feedback(I_fb_pA = I_fb_start, p_gain_pm = p_gain_start, t_const_us = t_const_start)
                nanonis.update.bias(V = V_start, dV_mV = 40)
            except Exception as e:
                print(f"Error returning to start feedback settings: {e}")
        return output_dict

