import os, yaml
from PyQt6 import QtCore, QtGui
import numpy as np
from .gui_scantelligent import ScantelligentGUI
from .gui_spectelligent import SpectelligentGUI



# Parameter management (getting from hardware, setting, loading from file and saving)
class ParameterManager(QtCore.QObject):
    def __init__(self, parent):
        super().__init__()
        self.scantelligent = parent # Reference to Scantelligent (parent)



    def get(self, parameter_type: str = "frame") -> None:
        sct = self.scantelligent
        
        if parameter_type in ["feedback", "frame", "grid", "speeds", "gain", "tip_shaper", "bias"] and not hasattr(sct, "nanonis"):
            sct.logprint("Cannot get parameters without a Nanonis connection", message_type = "error")
            return

        match parameter_type:
            case "bias": sct.nanonis.bias_update(unlink = True)
            case "feedback":
                sct.nanonis.feedback_update(unlink = False)
                sct.nanonis.hardware_update(unlink = False)
                sct.nanonis.tip_update(unlink = True)
            case "frame": sct.nanonis.frame_update(unlink = True, update_new_frame = True)
            case "grid": sct.nanonis.grid_update(unlink = True)
            case "speed" | "speeds": sct.nanonis.speeds_update(unlink = True)                
            case "lockin":
                if hasattr(sct, "nanonis"):
                    sct.nanonis.lockin_update(name_lookup = True, unlink = True)
                if hasattr(sct, "mla"):
                    sct.mla.lockin_update(unlink = False)
                    sct.mla.start_lockin()
                    sct.mla.get_pixels(1)
                    sct.mla.stop_lockin()
            case "mla_bias":
                if hasattr(sct, "mla"): sct.mla.bias_update(unlink = False)
            case "tip_shaper": sct.nanonis.tip_shaper_update(unlink = True)
            case "spectroscopy": sct.nanonis.sts_update(unlink = True)
            case _: pass
        return

    def set(self, parameter_type: str = "frame") -> None:
        # It is noted that the nomenclature 'set' causes shadowing of the built-in 'set' method, but I decided to keep this regardless
        sct = self.scantelligent
        sctgui: ScantelligentGUI = sct.gui
        sptgui: SpectelligentGUI = sct.spt.gui
        line_edits = sctgui.line_edits
        
        # Abort if the relevant hardware objects are missing
        if parameter_type in ["feedback", "frame", "grid", "speeds", "gain"] and not hasattr(sct, "nanonis"):
            sct.logprint("Cannot set parameters without a Nanonis connection", message_type = "error")
            return

        match parameter_type:
            case "bias":
                parameters = {"dict_name": "bias"}                
                for parameter in ["V_nanonis (V)", "dV_nanonis (mV)", "dz_nanonis (nm)", "dt_nanonis (ms)"]:
                    quantity = parameter.split()[0]
                    val = line_edits[quantity].getValue()
                    if isinstance(val, int | float): parameters.update({parameter: val})
                parameters.update({"I_fb (pA)": line_edits["fb"].getValue()})

                sct.nanonis.bias_update(parameters, unlink = True)

            case "feedback":
                parameters = {"dict_name": "feedback"}
                parameters.update({"active_controller": sctgui.comboboxes["controller"].currentIndex()})
                for parameter in ["p_gain (pm)", "t_const (us)", "i_gain (nm/s)"]:
                    quantity = parameter.split()[0]
                    val = line_edits[quantity].getValue()
                    if isinstance(val, int | float): parameters.update({parameter: val})
                    
                    val = line_edits["fb"].getValue()
                    parameters.update({"I_fb (pA)": val, "dIdV_fb (nS)": val})
                                
                sct.nanonis.feedback_update(parameters, unlink = False)
                gain = sctgui.comboboxes["tia_gain"].currentText()
                sct.nanonis.hardware_update({"dict_name": "hardware", "gain": gain}, unlink = True)                

            case "frame":
                offset = [line_edits[tag].getValue() for tag in ["frame_x", "frame_y"]]
                scan_range = [line_edits[tag].getValue() for tag in ["frame_width", "frame_height"]]
                angle = line_edits["frame_angle"].getValue()
                
                parameters = {"dict_name": "frame", "center (nm)": offset, "domain (nm)": scan_range, "angle (deg)": angle}
                sct.nanonis.frame_update(parameters, unlink = True)

            case "grid":
                [pixels, lines] = [line_edits[tag].getValue() for tag in ["grid_pixels", "grid_lines"]]
                
                offset = [line_edits[tag].getValue() for tag in ["frame_x", "frame_y"]]
                scan_range = [line_edits[tag].getValue() for tag in ["frame_width", "frame_height"]]
                angle = line_edits["frame_angle"].getValue()
                                
                parameters = {"dict_name": "grid", "center (nm)": offset, "domain (nm)": scan_range, "angle (deg)": angle, "pixels": pixels, "lines": lines}
                sct.nanonis.grid_update(parameters, unlink = True)

            case "speed" | "speeds":
                [v_fwd_nm_per_s, v_bwd_nm_per_s, v_tip_nm_per_s] = [line_edits[tag].getValue() for tag in ["v_fwd", "v_bwd", "v_tip"]]
                
                parameters = {"dict_name": "speeds", "v_fwd (nm/s)": v_fwd_nm_per_s, "v_bwd (nm/s)": v_bwd_nm_per_s, "v_xy (nm/s)": v_tip_nm_per_s, "v_tip (nm/s)": v_tip_nm_per_s}
                sct.nanonis.speeds_update(parameters, unlink = True)
            
            case "mla_bias":
                [port1_V, port2_V] = [line_edits[f"V_mla_port{index}"].getValue() for index in [1, 2]]
                sct.mla.bias_update({"port_1 (V)": port1_V, "port_2 (V)": port2_V})
            
            case "lockin":
                """
                if hasattr(sct, "nanonis"):
                    [mod1_on, mod2_on] = [bool(sct.gui.buttons[f"nanonis_mod{index + 1}"].state_index) for index in range(2)]
                    [mod1_f, mod1_mV, mod1_phi] = [line_edits[f"nanonis_mod1_{quantity}"].getValue() for quantity in ["f", "amp", "phase"]]
                    [mod2_f, mod2_mV, mod2_phi] = [line_edits[f"nanonis_mod2_{quantity}"].getValue() for quantity in ["f", "amp", "phase"]]
                    [mla1_f, mla1_mV, mla1_phi] = [line_edits[f"mla_mod1_{quantity}"].getValue() for quantity in ["f", "amp", "phase"]]
                    
                    parameters = {"dict_name": "lockin",
                                "mod1": {"on": mod1_on, "frequency (Hz)": mod1_f, "amplitude (mV)": mod1_mV, "phase (deg)": mod1_phi},
                                "mod2": {"on": mod2_on, "frequency (Hz)": mod2_f, "amplitude (mV)": mod2_mV, "phase (deg)": mod2_phi}}
                    sct.nanonis.lockin_update(parameters, unlink = True)
                """
                if hasattr(sct, "mla"):
                    df = sptgui.lockin_widget.getdf()
                    frequencies = sptgui.lockin_widget.getFrequencies()
                    amplitudes = sptgui.lockin_widget.getAmplitudes()
                    phases = sptgui.lockin_widget.getPhases()
                    outputs = sptgui.lockin_widget.getOutputs()
                    inputs = sptgui.lockin_widget.getInputs()
                    sct.mla.lockin_update({"df (Hz)": df, "frequencies (Hz)": frequencies, "amplitudes (mV)": amplitudes, "phases (deg)": phases, "output_masks": outputs, "input_mask": inputs}, unlink = False)
                    sct.mla.start_lockin()
                    sct.mla.get_pixels(1)
                    sct.mla.stop_lockin()
            
            case "tip_shaper":
                sct.nanonis.tip_shaper_update(unlink = True)

            case _:
                pass

    def load_from_file(self, parameter_type: str = "scan_parameters", index: int = 0) -> None:
        sct = self.scantelligent

        try:
            match parameter_type:
                case "scan_parameters":
                    params = self.user.scan_parameters[index]
                    
                    parameter_names = ["V_nanonis (V)", "V_mla (V)", "I_fb (pA)", "v_fwd (nm/s)", "v_bwd (nm/s)", "t_const (us)", "p_gain (pm)"]
                    line_edit_names = ["V_nanonis", "V_mla", "I_fb", "v_fwd (nm/s)", "v_bwd", "t_const", "p_gain"]
                    units = ["V", "V", "pA", "nm/s", "nm/s", "us", "pm"]
                    line_edits = [self.gui.line_edits[name] for name in line_edit_names]
                    
                    for name, le, unit in zip(parameter_names, line_edits, units):
                        if name in params.keys(): le.setText(f"{params[name]:.2f} {unit}")
                
                case "tip_prep_parameters":
                    params = self.user.tip_prep_parameters[index]
                    
                    parameter_names = ["pulse_voltage (V)", "pulse_duration (ms)"]
                    line_edit_names = ["pulse_voltage", "pulse_duration"]
                    units = ["V", "ms"]
                    line_edits = [self.gui.line_edits[name] for name in line_edit_names]
                    
                    for name, le, unit in zip(parameter_names, line_edits, units):
                        if name in params.keys(): le.setText(f"{params[name]:.2f} {unit}")
                    
                case _:
                    pass

        except Exception as e:
            sct.logprint(f"Error loading parameters. {e}", message_type = "error")
        
        return



    @QtCore.pyqtSlot(dict)
    def receive(self, parameters: dict) -> None:
        sct = self.scantelligent
        sctgui: ScantelligentGUI = sct.gui
        sptgui: SpectelligentGUI = sct.spt.gui
        line_edits = sctgui.line_edits
        dict_name = parameters.get("dict_name")

        match dict_name:
            case "gui_setup":
                [combobox_setup, line_edits_setup, buttons_setup] = [parameters.get(key, None) for key in ["combobox", "line_edits", "buttons"]]
                if isinstance(line_edits_setup, dict):
                    for key, values in line_edits_setup.items():
                        if isinstance(values, int | float | str): values = [values]
                        if not isinstance(values, list): continue
                        match key:
                            case "tooltips": [line_edits[f"experiment_{index}"].changeToolTip({tooltip}) for index, tooltip in enumerate(values)]
                            case "digits": [line_edits[f"experiment_{index}"].setDigits(digits) for index, digits in enumerate(values)]
                            case "limits": [line_edits[f"experiment_{index}"].setLimits(limits) for index, limits in enumerate(values)]
                            case "values": [line_edits[f"experiment_{index}"].setValue(value) for index, value in enumerate(values)]
                            case "units": [line_edits[f"experiment_{index}"].setUnit(unit) for index, unit in enumerate(values)]
                            case _: pass
                if isinstance(combobox_setup, dict):
                    for key, values in combobox_setup.items():
                        if isinstance(values, int | float | str): values = [values]
                        if not isinstance(values, list): continue
                        match key:
                            case "tooltip": sctgui.comboboxes["direction"].changeToolTip(values)
                            case "items": sctgui.comboboxes["direction"].renewItems(values)
                            case _: pass

            case "nanonis_status":
                status = parameters.get("status")
                match status:
                    case "running": sct.status.update({"nanonis": "running"})
                    case "online" | "idle": sct.status.update({"nanonis": "idle"})
                    case "offline": sct.status.update({"nanonis": "offline"})
                    case _: pass
                try: sct.gui.buttons["nanonis"].setState(status)
                except: pass

            case "mla_status":
                status = parameters.get("status")
                match status:
                    case "running": sct.status.update({"mla": "running"})
                    case "online" | "idle": sct.status.update({"mla": "idle"})
                    case "offline": sct.status.update({"mla": "offline"})
                    case _: pass
                try: sctgui.buttons["mla"].setState(status)
                except: pass

            case "keithley_status":
                status = parameters.get("status")
                match status:
                    case "running": sct.status.update({"keithley": "running"})
                    case "online" | "idle": sct.status.update({"keithley": "idle"})
                    case "offline": sct.status.update({"keithley": "offline"})
                    case _: pass
                try: sctgui.buttons["keithley"].setState(status)
                except: pass

            case "camera_status":
                status = parameters.get("status")
                match status:
                    case "running": sct.status.update({"camera": "running"})
                    case "online" | "idle": sct.status.update({"camera": "idle"})
                    case "offline": sct.status.update({"camera": "offline"})
                    case _: pass
                try: sctgui.buttons["camera"].setState(status)
                except: pass

            case "session_path":
                session_path = parameters.get("path")
                sct.paths.update({"session_path": session_path})
                try: sctgui.buttons["session_folder"].setState("online")
                except: pass
            
            case "view_request":
                new_view = parameters.get("view")
                if new_view in ["none", "camera", "nanonis"]: sct.toggle_view(new_view)
            
            case "array_item":
                [name, shape, dtype, axes, axis_values, frame] = [parameters.get(key, None) for key in ["name", "shape", "dtype", "axes", "axis_values", "frame"]]
                sct.create_array_item(name = name, shape = shape, dtype = dtype, axes = axes, axis_values = axis_values, frame = frame)



            case "mla_bias":
                biases = [parameters.get(f"port_{index + 1} (V)") for index in range(2)]
                [line_edits[f"V_mla_port{index + 1}"].setValue(val, edited_color = False) for index, val in enumerate(biases)]
                sptgui.waveform_widget.setDCBiases(biases)
            case "pixels":
                pixel = parameters.get("pixels")
                if pixel.ndim > 1: pixel = pixel[:, 0]
                abs_values = np.abs(2000 * pixel)
                arg_values = np.rad2deg(np.angle(pixel))                
                sptgui.lockin_widget.setMeasuredAmplitudes(abs_values)
                sptgui.lockin_widget.setMeasuredPhases(arg_values)
                sptgui.waveform_widget.readPixel(pixel)
                sct.amplitudes.emit(100 * abs_values)
            case "frequencies":
                freqs = parameters.get("frequencies (Hz)")
                sptgui.lockin_widget.setFrequencies(freqs)
                sptgui.waveform_widget.setFrequencies(freqs)
                sct.frequencies.emit(freqs) # To be captured by the audio generator
            case "time_constant":
                df_Hz = parameters.get("df (Hz)")
                sptgui.lockin_widget.setdf(df_Hz)
                sptgui.waveform_widget.setdf(df_Hz)
            case "amplitudes":
                amplitudes = parameters.get("amplitudes (mV)")
                sptgui.lockin_widget.setAmplitudes(amplitudes)
                sptgui.waveform_widget.setAmplitudes(amplitudes)
            case "phases":
                sptgui.lockin_widget.setPhases(parameters.get("phases (deg)"))
                sptgui.waveform_widget.setPhases(parameters.get("phases (deg)"), unit = "deg")
            case "outputs":
                output_masks = parameters.get("output_masks")
                sptgui.lockin_widget.setOutputs(output_masks)
                sptgui.waveform_widget.setOutputs(output_masks)
            case "inputs":
                input_mask = parameters.get("input_mask")
                sptgui.lockin_widget.setInputs(input_mask)
                sptgui.waveform_widget.setInputs(input_mask)
    
            case "coarse_parameters":
                sct.user.coarse_parameters[0].update(parameters)
                
                line_edits["V_hor"].setValue(parameters.get("V_motor (V)"))
                line_edits["V_ver"].setValue(parameters.get("V_motor (V)"))
                line_edits["f_motor"].setValue(parameters.get("f_motor (Hz)"))

            case "channels":
                for key, value in parameters.items():
                    if key == "dict_name": continue

                    channel_index = int(key)
                    if channel_index < 0 or channel_index > 39: continue

                    sct.gui.checkboxes[f"channel_{channel_index}"].setToolTip(f"channel {channel_index}: {value}")
                    sct.gui.checkboxes[f"channel_{channel_index}"].setChecked(True)
                    sct.gui.pdis[channel_index].setVisible(True)
                    line = sct.gui.grapher.plot()
                    sct.lines.append(line)

            case "tip_status":
                tip_status = parameters
                sct.status.update({"tip": tip_status})
                
                # Update the tip position visible in the image_view
                if "feedback" in tip_status.keys():
                    feedback = tip_status.get("feedback")
                    if feedback:
                        sct.gui.tip_target.setPen(sct.gui.colors["green"])
                        sct.gui.current_height_widget.feedback_button.setState("feedback")
                        sct.gui.buttons["withdraw"].setState("landed")
                        sct.gui.buttons["withdraw_2"].setState("landed")
                    else:
                        withdrawn = tip_status.get("withdrawn")
                        if withdrawn:
                            sct.gui.tip_target.setPen(sct.gui.colors["red"])
                            sct.gui.current_height_widget.feedback_button.setState("unknown")
                            sct.gui.buttons["withdraw"].setState("withdrawn")
                            sct.gui.buttons["withdraw_2"].setState("withdrawn")
                        else:
                            sct.gui.tip_target.setPen(sct.gui.colors["orange"])
                            sct.gui.current_height_widget.feedback_button.setState("constant_height")
                    
                    # Update the tip height widget
                    z_limits_nm = tip_status.get("z_limits (nm)")
                    sct.gui.current_height_widget.setHeightLimits(z_limits_nm)

                # Update the target location in the ImageView
                [x_tip_nm, y_tip_nm, z_tip_nm, I_pA] = [tip_status.get(dim, 0) for dim in ["x (nm)", "y (nm)", "z (nm)", "I (pA)"]]
                sct.gui.tip_target.setPos(x_tip_nm, y_tip_nm)
                sct.gui.tip_target.text_item.setText(f"tip location\n({x_tip_nm:.2f}, {y_tip_nm:.2f}, {z_tip_nm:.2f}) nm")
                
                #sct.gui.current_height_widget.changeToolTip(f"Tip height: {z_tip_nm:.2f} nm")
                sct.gui.current_height_widget.setCurrent(I_pA)
                sct.gui.current_height_widget.setHeight(z_tip_nm)

            case "bias":
                [line_edits[name].setValue(parameter) for name, parameter in zip(["V_nanonis", "dV_nanonis", "dt_nanonis", "dz_nanonis"],
                                                                                 [parameters.get(name) for name in ["V_nanonis (V)", "dV_nanonis (mV)", "dt_nanonis (ms)", "dz_nanonis (nm)"]])]
                if sct.gui.buttons["voltage_lock"].isChecked() and hasattr(sct, "mla") and hasattr(sct.mla, "mla") and hasattr(sct.mla.mla, "lockin"):
                    try:
                        V_nanonis = parameters.get("V_nanonis (V)")
                        sct.mla.bias_update({"port_1 (V)": V_nanonis, "port_2 (V)": V_nanonis})
                    except:
                        pass

            case "feedback":
                [line_edits[name].setValue(parameter) for name, parameter in zip(["p_gain", "i_gain", "t_const"], [parameters.get(name) for name in ["p_gain (pm)", "i_gain (nm/s)", "t_const (us)"]])]
                [I_fb_pA, dIdV_fb_nS] = [parameters.get(key, None) for key in ["I_fb (pA)", "dIdV (nS)"]]
                if I_fb_pA:
                    line_edits["fb"].setUnit("pA")
                    line_edits["fb"].setValue(I_fb_pA)
                if dIdV_fb_nS:
                    line_edits["fb"].setUnit("nS")
                    line_edits["fb"].setValue(dIdV_fb_nS)
                sct.gui.current_height_widget.setCurrentTick(I_fb_pA)
                
                # Display the controllers
                controllers = parameters.get("controllers")
                active_controller = parameters.get("active_controller")
                sctgui.comboboxes["controller"].renewItems(controllers)
                sctgui.comboboxes["controller"].selectItem(active_controller)

            case "frame":
                sct.user.frames[0].update(parameters)
            
                [x_0_nm, y_0_nm] = parameters.get("center (nm)", [0, 0])
                scan_range = parameters.get("domain (nm)", [100, 100])
                sct.data.scan_processing_flags.update({"domain (nm)": scan_range})
                [w_nm, h_nm] = scan_range
                
                angle_deg = parameters.get("angle (deg)", 0)
                aspect_ratio = h_nm / w_nm
                
                # Update the fields in the GUI
                [line_edits[name].setValue(parameter) for name, parameter in zip(["frame_height", "frame_width", "frame_x", "frame_y", "frame_angle", "frame_aspect"], [h_nm, w_nm, x_0_nm, y_0_nm, angle_deg, aspect_ratio])]

                # Update the frame in the ImageView                
                """
                sct.gui.frame.setSize([w_nm, h_nm])
                sct.gui.frame.setPos([0, 0])
                sct.gui.frame.setAngle(angle = -angle_deg)

                bounding_rect = sct.gui.frame.boundingRect()
                local_center = bounding_rect.center()
                abs_center = sct.gui.frame.mapToParent(local_center)                
                sct.gui.frame.setPos(x_0_nm - abs_center.x(), y_0_nm - abs_center.y())
                """
                sct.gui.frame.setFrame(parameters)

            case "new_frame":
                [x_0_nm, y_0_nm] = parameters.get("center (nm)", [0, 0])
                [w_nm, h_nm] = parameters.get("domain (nm)", [100, 100])
                angle_deg = parameters.get("angle (deg)", 0)
                aspect_ratio = h_nm / w_nm

                # Update the fields in the GUI
                [line_edits[name].setValue(parameter) for name, parameter in zip(["frame_height", "frame_width", "frame_x", "frame_y", "frame_angle", "frame_aspect"], [h_nm, w_nm, x_0_nm, y_0_nm, angle_deg, aspect_ratio])]
                
                # Update the frame in the ImageView
                if sct.gui.buttons["view"].state_name == "nanonis":
                    sct.gui.new_frame.blockSignals(True)
                    
                    sct.gui.new_frame.setFrame(parameters)
                    """
                    new_frame.setSize([w_nm, h_nm])
                    new_frame.setPos([0, 0])
                    new_frame.setAngle(angle = -angle_deg)
                    
                    bounding_rect = new_frame.boundingRect()
                    local_center = bounding_rect.center()
                    abs_center = new_frame.mapToParent(local_center)
                    
                    new_frame.setPos(x_0_nm - abs_center.x(), y_0_nm - abs_center.y())
                    """
                    sct.gui.new_frame.blockSignals(False)

            case "grid":
                sct.user.frames[0].update(parameters)

                [pixels, lines, pixel_width, pixel_height] = [parameters.get(parameter, None) for parameter in ["pixels", "lines", "pixel_width (nm)", "pixel_height (nm)"]]
                aspect_ratio = lines / pixels

                # Update the fields in the GUI
                [line_edits[name].setValue(parameter) for name, parameter in zip(["grid_pixels", "grid_lines", "grid_aspect", "pixel_width", "pixel_height"], [pixels, lines, aspect_ratio, pixel_width, pixel_height])]
                
                # Frame is embedded in grid. Update the frame parameters as well
                [x_0_nm, y_0_nm] = parameters.get("center (nm)", [0, 0])
                scan_range = parameters.get("domain (nm)", [100, 100])
                sct.data.scan_processing_flags.update({"domain (nm)": scan_range})
                [w_nm, h_nm] = scan_range
                
                angle_deg = parameters.get("angle (deg)", 0)
                aspect_ratio = h_nm / w_nm

                # Update the fields in the GUI
                [line_edits[name].setValue(parameter) for name, parameter in zip(["frame_height", "frame_width", "frame_x", "frame_y", "frame_angle", "frame_aspect"], [h_nm, w_nm, x_0_nm, y_0_nm, angle_deg, aspect_ratio])]
                
                # Update the frame in the ImageView
                sct.gui.frame.setFrame(parameters)
                sct.gui.new_frame.setFrame(parameters)
                
                if not hasattr(sct.gui, "active_item"): return
                try: sct.gui.activeItem.setFrame(parameters)
                except: pass
                
                """
                sct.gui.frame.setSize([w_nm, h_nm])
                sct.gui.frame.setPos([0, 0])
                sct.gui.frame.setAngle(angle = -angle_deg)

                bounding_rect = sct.gui.frame.boundingRect()
                local_center = bounding_rect.center()
                abs_center = sct.gui.frame.mapToParent(local_center)
                sct.gui.frame.setPos(x_0_nm - abs_center.x(), y_0_nm - abs_center.y())
                
                # Update the new frame 'roi' in the ImageView
                sct.gui.new_frame.setSize([w_nm, h_nm])
                sct.gui.new_frame.setPos([0, 0])
                sct.gui.new_frame.setAngle(angle = -angle_deg)

                bounding_rect = sct.gui.new_frame.boundingRect()
                local_center = bounding_rect.center()
                abs_center = sct.gui.new_frame.mapToParent(local_center)
                sct.gui.new_frame.setPos(x_0_nm - abs_center.x(), y_0_nm - abs_center.y())

                # Refresh the transformations on the scan_item
                if sct.gui.buttons["view"].state_name == "nanonis": sct.gui.scan_item.setGrid(parameters)
                """
            
            case "path":
                [coords, visible] = [parameters.get(key, None) for key in ["coordinates (nm)", "hidden"]]
                if isinstance(coords, np.ndarray): sct.gui.path_pdi.setData(coords[:, 0], coords[:, 1])
                if isinstance(visible, bool): sct.gui.path_pdi.setVisible(visible)

            case "signal":
                if "Current (A)" in parameters.keys():
                    current_value = parameters["Current (A)"]

            case "gains":
                [p_gain_ms, t_const_us, i_gain_nm_per_s] = [parameters.get(parameter) for parameter in ["p_gain (pm)", "t_const (us)", "i_gain (nm/s)"]]

                # Update the fields in the GUI
                [line_edits[name].setValue(parameter) for name, parameter in zip(["p_gain", "t_const", "i_gain"], [p_gain_ms, t_const_us, i_gain_nm_per_s])]

            case "hardware":
                piezo_range_nm = [parameters.get(dim) for dim in ["x_range (nm)", "y_range (nm)"]]
                piezo_lower_left_nm = [parameters.get(dim) for dim in ["x_min (nm)", "y_min (nm)"]]
                sct.gui.piezo_frame.setSize(piezo_range_nm, [0, 0], [0, 0])
                sct.gui.piezo_frame.setPos(piezo_lower_left_nm)
                
                gains = parameters.get("gains", None)
                if gains: sct.gui.comboboxes["tia_gain"].renewItems(gains)
                current_gain = parameters.get("current_gain", None)
                if current_gain: sct.gui.comboboxes["tia_gain"].selectItem(current_gain)

            case "scan_metadata":
                signals = parameters.get("signal_dict", None)
                if isinstance(signals, dict): [sct.gui.comboboxes[f"nanonis_mod{index + 1}"].renewItems(list(signals.keys())) for index in range(2)]

                # Refresh the recorded channels
                old_channels = sct.data.scan_processing_flags.get("channels")
                new_channels = parameters.get("channel_dict", {})
                
                # Update the channels combobox with the channels that are being recorded if there is a change
                if not old_channels == new_channels:
                    sct.data.scan_processing_flags.update({"channels": new_channels})
                    #sct.gui.comboboxes["slice"].renewItems(list(new_channels.keys()))
                    #[sct.gui.comboboxes["slice"].selectItem(preferred_channel) for preferred_channel in ["Current (A)", "LI Demod 1 X (A)", "Z (m)"]]
                    sct.update_processing_flags()

            case "lockin":
                for i, mod_dict in enumerate([parameters.get("mod1"), parameters.get("mod2")]):
                    
                    mod_values = [mod_dict.get(key) for key in ["frequency (Hz)", "amplitude (mV)", "phase (deg)", "time_constant (ms)"]]                    
                    [line_edits[f"nanonis_mod{i + 1}_{quantity}"].setValue(value) for quantity, value in zip(["f", "amp", "phase"], mod_values)]
                    
                    if i == 0:
                        df_Hz = mod_values[0] # Measurement resolution is a single cycle of modulator 1
                        tm_ms = 1000 / df_Hz
                        [line_edits[f"nanonis_{quantity}"].setValue(val) for quantity, val in zip(["df", "t"], [df_Hz, tm_ms])]
                    
                    line_edits[f"nanonis_mod{i + 1}_n"].setValue(mod_values[0] / df_Hz)
                    
                    state = "off"
                    if mod_dict.get("on"):
                        state = "on"
                        f1 = mod_dict.get("frequency (Hz)", None)
                        if isinstance(f1, float | int):
                            # sct.frequencies.emit(f1)
                            [line_edits[f"demod_frequency_{i}"].setValue(i * f1) for i in range(32)]
                    sct.gui.buttons[f"nanonis_mod{i + 1}"].setState(state)
                    
                    if "signal_name" in mod_dict.keys():
                        try: sct.gui.comboboxes[f"nanonis_mod{i + 1}"].setCurrentText(mod_dict["signal_name"])
                        except: pass

            case "speed" | "speeds":
                [v_fwd, v_bwd, v_tip] = [parameters.get(quantity) for quantity in ["v_fwd (nm/s)", "v_bwd (nm/s)", "v_tip (nm/s)"]]
                [line_edits[name].setValue(value) for name, value in zip(["v_fwd", "v_bwd", "v_tip"], [v_fwd, v_bwd, v_tip])]
            
            case "tip_shaper":
                [poke_depth, poke_time, poke_bias, lift_height, lift_time, lift_bias] = [parameters.get(quantity) for quantity in
                                                                                         ["poke_depth (nm)", "poke_time (s)", "poke_bias (V)", "lift_height (nm)", "lift_time (s)", "lift_bias (V)"]]
                [line_edits[name].setValue(value) for name, value in zip(["poke_depth", "poke_time", "poke_voltage", "lift_height", "lift_time", "lift_voltage"],
                                                                         [poke_depth, poke_time, poke_bias, lift_height, lift_time, lift_bias])]
            
            case _:
                pass



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
        yaml_data = {}
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


