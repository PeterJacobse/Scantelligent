import os, yaml
from PyQt6 import QtCore



# Parameter management (getting from hardware, setting, loading from file and saving)
class ParameterManager(QtCore.QObject):    
    def __init__(self, parent):
        super().__init__()
        self.scantelligent = parent # Reference to Scantelligent (parent)



    def get(self, parameter_type: str = "frame") -> None:
        sct = self.scantelligent
        
        if parameter_type in ["feedback", "frame", "grid", "speeds", "gain", "tip_shaper"]:
            if not hasattr(sct, "nanonis"):
                sct.logprint("Cannot get parameters without a Nanonis connection", message_type = "error")
                return

        match parameter_type:
            case "bias": sct.nanonis.bias_update(unlink = True)
            case "feedback": sct.nanonis.feedback_update(unlink = True)
            case "frame": sct.nanonis.frame_update(unlink = True, update_new_frame = True)
            case "grid": sct.nanonis.grid_update(unlink = True)
            case "speed" | "speeds": sct.nanonis.speeds_update(unlink = True)
            case "gain": sct.nanonis.gains_update(unlink = True)            
            case "lockin": sct.nanonis.lockin_update(unlink = True)
            case "tip_shaper": sct.nanonis.tip_shaper_update(unlink = True)
            case "spectroscopy": sct.nanonis.sts_update(unlink = True)
            case _: pass
        return

    def set(self, parameter_type: str = "frame") -> None:
        # It is noted that the nomenclature 'set' causes shadowing of the built-in 'set' method, but I decided to keep this regardless
        sct = self.scantelligent
        
        # Abort if the relevant hardware objects are missing
        if parameter_type in ["feedback", "frame", "grid", "speeds", "gain"]:
            if not hasattr(sct, "nanonis"):
                sct.logprint("Cannot set parameters without a Nanonis connection", message_type = "error")
                return

        match parameter_type:
            case "bias":
                parameters = {"dict_name": "bias"}
                
                for parameter in ["V_nanonis (V)", "V_mla (V)", "I_fb (pA)", "dV_nanonis (mV)", "dz_nanonis (nm)", "dt_nanonis (ms)"]:
                    quantity = parameter.split()[0]
                    val = sct.gui.line_edits[quantity].getValue()
                    if isinstance(val, int | float): parameters.update({parameter: val})

                sct.nanonis.bias_update(parameters, unlink = True)

            case "feedback":
                parameters = {"dict_name": "feedback"}
                
                for parameter in ["I_fb (pA)", "p_gain (pm)", "t_const (us)", "i_gain (nm/s)"]:
                    quantity = parameter.split()[0]
                    val = sct.gui.line_edits[quantity].getValue()
                    if isinstance(val, int | float): parameters.update({parameter: val})

                sct.nanonis.feedback_update(parameters, unlink = True)

            case "frame":
                offset = [sct.gui.line_edits[tag].getValue() for tag in ["frame_x", "frame_y"]]
                scan_range = [sct.gui.line_edits[tag].getValue() for tag in ["frame_width", "frame_height"]]
                angle = sct.gui.line_edits["frame_angle"].getValue()
                
                parameters = {"dict_name": "frame", "offset (nm)": offset, "scan_range (nm)": scan_range, "angle (deg)": angle}
                sct.nanonis.frame_update(parameters, unlink = True)

            case "grid":
                [pixels, lines] = [sct.gui.line_edits[tag].getValue() for tag in ["grid_pixels", "grid_lines"]]
                
                offset = [sct.gui.line_edits[tag].getValue() for tag in ["frame_x", "frame_y"]]
                scan_range = [sct.gui.line_edits[tag].getValue() for tag in ["frame_width", "frame_height"]]
                angle = sct.gui.line_edits["frame_angle"].getValue()
                                
                parameters = {"dict_name": "grid", "offset (nm)": offset, "scan_range (nm)": scan_range, "angle (deg)": angle, "pixels": pixels, "lines": lines}
                sct.nanonis.grid_update(parameters, unlink = True)

            case "speed" | "speeds":
                [v_fwd_nm_per_s, v_bwd_nm_per_s, v_tip_nm_per_s] = [sct.gui.line_edits[tag].getValue() for tag in ["v_fwd", "v_bwd", "v_tip"]]
                
                parameters = {"dict_name": "speeds", "v_fwd (nm/s)": v_fwd_nm_per_s, "v_bwd (nm/s)": v_bwd_nm_per_s, "v_xy (nm/s)": v_tip_nm_per_s, "v_tip (nm/s)": v_tip_nm_per_s}
                sct.nanonis.speeds_update(parameters, unlink = True)
            
            case "lockin":
                if not hasattr(sct, "nanonis"):
                    sct.logprint("Cannot set parameters without a Nanonis connection", message_type = "error")
                    return
            
                [mod1_on, mod2_on] = [bool(sct.gui.buttons[f"nanonis_mod{i + 1}"].state_index) for i in range(2)]
                mla_mod1_on = bool(sct.gui.buttons[f"mla_mod1"].state_index)
                [mod1_f, mod1_mV, mod1_phi] = [sct.gui.line_edits[f"nanonis_mod1_{quantity}"].getValue() for quantity in ["f", "mV", "phi"]]
                [mod2_f, mod2_mV, mod2_phi] = [sct.gui.line_edits[f"nanonis_mod2_{quantity}"].getValue() for quantity in ["f", "mV", "phi"]]
                [mla1_f, mla1_mV, mla1_phi] = [sct.gui.line_edits[f"mla_mod1_{quantity}"].getValue() for quantity in ["f", "mV", "phi"]]
                
                parameters = {"dict_name": "lockin",
                              "mod1": {"on": mod1_on, "frequency (Hz)": mod1_f, "amplitude (mV)": mod1_mV, "phase (deg)": mod1_phi},
                              "mod2": {"on": mod2_on, "frequency (Hz)": mod2_f, "amplitude (mV)": mod2_mV, "phase (deg)": mod2_phi},
                              "mla_mod1": {"on": mla_mod1_on, "frequency (Hz)": mla1_f, "amplitude (mV)": mla1_mV, "phase (deg)": mla1_phi}
                              }
                sct.nanonis.lockin_update(parameters, unlink = True)
            
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
        line_edits = sct.gui.line_edits
        dict_name = parameters.get("dict_name")

        match dict_name:
            case "keithley_status":
                status = parameters.get("status")
                match status:
                    case "running": sct.status.update({"keithley": "running"})
                    case "online" | "idle": sct.status.update({"keithley": "idle"})
                    case "offline": sct.status.update({"keithley": "offline"})
                    case _: pass
                try: sct.gui.buttons["keithley"].setState(status)
                except: pass

            case "camera_status":
                status = parameters.get("status")
                match status:
                    case "running": sct.status.update({"camera": "running"})
                    case "online" | "idle": sct.status.update({"camera": "idle"})
                    case "offline": sct.status.update({"camera": "offline"})
                    case _: pass
                try: sct.gui.buttons["camera"].setState(status)
                except: pass

            case "mla_status":
                status = parameters.get("status")
                match status:
                    case "running": sct.status.update({"mla": "running"})
                    case "idle": sct.status.update({"mla": "idle"})
                    case "offline": sct.status.update({"mla": "offline"})
                    case _: pass
                try: sct.gui.buttons["mla"].setState(status)
                except: pass

            case "session_path":
                session_path = parameters.get("path")
                sct.paths.update({"session_path": session_path})
                try: sct.gui.buttons["session_folder"].setState("online")
                except: pass



            case "coarse_parameters":
                sct.user.coarse_parameters[0].update(parameters)
                
                line_edits["V_hor"].setValue(parameters.get("V_motor (V)"))
                line_edits["V_ver"].setValue(parameters.get("V_motor (V)"))
                line_edits["f_motor"].setValue(parameters.get("f_motor (Hz)"))

            case "channels":
                for key, value in parameters.items():
                    if key == "dict_name": continue

                    channel_index = int(key)
                    if channel_index < 0 or channel_index > 40: continue

                    sct.gui.checkboxes[f"channel_{channel_index}"].setToolTip(f"channel {channel_index}: {value}")
                    sct.gui.checkboxes[f"channel_{channel_index}"].setChecked(True)
                    sct.gui.pdis[channel_index].setVisible(True)
                    line = sct.gui.plot_widget.plot()
                    sct.lines.append(line)

            case "tip_status":
                tip_status = parameters
                sct.status.update({"tip": tip_status})
                
                # Update the position visible in the image_view
                # sct.gui.image_view.view.removeItem(sct.gui.tip_target)
                if "feedback" in tip_status.keys():
                    feedback = tip_status.get("feedback")
                    if feedback:
                        sct.gui.tip_target.setPen(sct.gui.colors["green"])
                        sct.gui.buttons["tip"].setState("feedback")
                        sct.gui.buttons["withdraw"].setState("landed")
                    else:
                        withdrawn = tip_status.get("withdrawn")
                        if withdrawn:
                            sct.gui.tip_target.setPen(sct.gui.colors["red"])
                            sct.gui.buttons["tip"].setState("unknown")
                            sct.gui.buttons["withdraw"].setState("withdrawn")
                        else:
                            sct.gui.tip_target.setPen(sct.gui.colors["orange"])
                            sct.gui.buttons["tip"].setState("constant_height")
                    
                    # Update the slider
                    z_limits_nm = tip_status.get("z_limits (nm)")
                    sct.gui.sliders["tip"].setMinimum(int(z_limits_nm[0]))
                    sct.gui.sliders["tip"].setMaximum(int(z_limits_nm[1]))

                [x_tip_nm, y_tip_nm, z_tip_nm] = [tip_status.get(dim, 0) for dim in ["x (nm)", "y (nm)", "z (nm)"]]
                sct.gui.tip_target.setPos(x_tip_nm, y_tip_nm)
                sct.gui.tip_target.text_item.setText(f"tip location\n({x_tip_nm:.2f}, {y_tip_nm:.2f}, {z_tip_nm:.2f}) nm")
                sct.gui.sliders["tip"].setValue(int(z_tip_nm))
                sct.gui.sliders["tip"].changeToolTip(f"Tip height: {z_tip_nm:.2f} nm")

            case "bias":
                [line_edits[name].setValue(parameter) for name, parameter in zip(["V_nanonis", "dV_nanonis", "dt_nanonis", "dz_nanonis"],
                                                                                 [parameters.get(name) for name in ["V_nanonis (V)", "dV_nanonis (mV)", "dt_nanonis (ms)", "dz_nanonis (nm)"]])]

            case "feedback":
                [line_edits[name].setValue(parameter) for name, parameter in zip(["p_gain", "i_gain", "t_const"], [parameters.get(name) for name in ["p_gain (pm)", "i_gain (nm/s)", "t_const (us)"]])]
                line_edits["I_fb"].setValue(parameters.get("I_fb (pA)"))

            case "frame":
                sct.user.frames[0].update(parameters)
            
                [x_0_nm, y_0_nm] = parameters.get("offset (nm)", [0, 0])
                [w_nm, h_nm] = parameters.get("scan_range (nm)", [100, 100])
                angle_deg = parameters.get("angle (deg)", 0)
                aspect_ratio = h_nm / w_nm
                
                # Update the fields in the GUI
                [line_edits[name].setValue(parameter) for name, parameter in zip(["frame_height", "frame_width", "frame_x", "frame_y", "frame_angle", "frame_aspect"], [h_nm, w_nm, x_0_nm, y_0_nm, angle_deg, aspect_ratio])]

                # Update the frame 'roi' in the ImageView
                frame_roi = sct.gui.frame_roi
                try: sct.gui.image_view.view.removeItem(frame_roi)
                except: pass
                
                if sct.status["view"] == "nanonis":
                    frame_roi.setSize([w_nm, h_nm])
                    frame_roi.setPos([0, 0])
                    frame_roi.setAngle(angle = -angle_deg)

                    sct.gui.image_view.addItem(frame_roi)

                    bounding_rect = frame_roi.boundingRect()
                    local_center = bounding_rect.center()
                    abs_center = frame_roi.mapToParent(local_center)
                    
                    frame_roi.setPos(x_0_nm - abs_center.x(), y_0_nm - abs_center.y())

            case "new_frame":
                [x_0_nm, y_0_nm] = parameters.get("offset (nm)", [0, 0])
                [w_nm, h_nm] = parameters.get("scan_range (nm)", [100, 100])
                angle_deg = parameters.get("angle (deg)", 0)
                aspect_ratio = h_nm / w_nm

                # Update the fields in the GUI
                [line_edits[name].setValue(parameter) for name, parameter in zip(["frame_height", "frame_width", "frame_x", "frame_y", "frame_angle", "frame_aspect"], [h_nm, w_nm, x_0_nm, y_0_nm, angle_deg, aspect_ratio])]
                
                # Update the frame 'roi' in the ImageView
                new_frame_roi = sct.gui.new_frame_roi
                try: sct.gui.image_view.view.removeItem(new_frame_roi)
                except: pass
                
                if sct.status["view"] == "nanonis":
                    new_frame_roi.blockSignals(True)
                    
                    new_frame_roi.setSize([w_nm, h_nm])
                    new_frame_roi.setPos([0, 0])
                    new_frame_roi.setAngle(angle = -angle_deg)

                    sct.gui.image_view.addItem(new_frame_roi)
                    
                    bounding_rect = new_frame_roi.boundingRect()
                    local_center = bounding_rect.center()
                    abs_center = new_frame_roi.mapToParent(local_center)
                    
                    new_frame_roi.setPos(x_0_nm - abs_center.x(), y_0_nm - abs_center.y())
                    
                    new_frame_roi.blockSignals(False)

            case "grid":
                sct.user.frames[0].update(parameters)

                [pixels, lines, pixel_width, pixel_height] = [parameters.get(parameter, None) for parameter in ["pixels", "lines", "pixel_width (nm)", "pixel_height (nm)"]]
                aspect_ratio = lines / pixels

                # Update the fields in the GUI
                [line_edits[name].setValue(parameter) for name, parameter in zip(["grid_pixels", "grid_lines", "grid_aspect", "pixel_width", "pixel_height"], [pixels, lines, aspect_ratio, pixel_width, pixel_height])]
                
                # Frame is embedded in grid. Update the frame parameters as well
                [x_0_nm, y_0_nm] = parameters.get("offset (nm)", [0, 0])
                [w_nm, h_nm] = parameters.get("scan_range (nm)", [100, 100])
                angle_deg = parameters.get("angle (deg)", 0)
                aspect_ratio = h_nm / w_nm

                # Update the fields in the GUI
                [line_edits[name].setValue(parameter) for name, parameter in zip(["frame_height", "frame_width", "frame_x", "frame_y", "frame_angle", "frame_aspect"], [h_nm, w_nm, x_0_nm, y_0_nm, angle_deg, aspect_ratio])]
                
                # Update the frame 'roi' in the ImageView
                new_frame_roi = sct.gui.new_frame_roi
                try: sct.gui.image_view.view.removeItem(new_frame_roi)
                except: pass
                
                if sct.status["view"] == "nanonis":
                    new_frame_roi.blockSignals(True)
                    
                    new_frame_roi.setSize([w_nm, h_nm])
                    new_frame_roi.setPos([0, 0])
                    new_frame_roi.setAngle(angle = -angle_deg)

                    sct.gui.image_view.addItem(new_frame_roi)
                    
                    bounding_rect = new_frame_roi.boundingRect()
                    local_center = bounding_rect.center()
                    abs_center = new_frame_roi.mapToParent(local_center)
                    
                    new_frame_roi.setPos(x_0_nm - abs_center.x(), y_0_nm - abs_center.y())
                    
                    new_frame_roi.blockSignals(False)

            case "signal":
                if "Current (A)" in parameters.keys():
                    current_value = parameters["Current (A)"]

            case "sts":
                [V_start, V_end] = parameters.get("limits (V)")
                if V_start: [sct.gui.line_edits[name].setValue(value) for name, value in zip(["V_start_STS", "V_end_STS"], [V_start, V_end])]
                
                [n_points, t_int_s, t_settle_s] = [parameters.get(key) for key in ["num_points", "t_integration (s)", "t_settle (s)"]]
                t_int_ms = t_int_s * 1000
                t_settle_s = t_settle_s * 1000
                [sct.gui.line_edits[name].setValue(value) for name, value in zip(["points_STS", "t_integration", "t_settle"], [n_points, t_int_s, t_settle_s])]
                sct.gui.points_dV("points_STS") # Calculate the dV

            case "gains":
                [p_gain_ms, t_const_us, i_gain_nm_per_s] = [parameters.get(parameter) for parameter in ["p_gain (pm)", "t_const (us)", "i_gain (nm/s)"]]

                # Update the fields in the GUI
                [line_edits[name].setValue(parameter) for name, parameter in zip(["p_gain", "t_const", "i_gain"], [p_gain_ms, t_const_us, i_gain_nm_per_s])]

            case "piezo_range":
                piezo_roi = sct.gui.piezo_roi
                try: sct.gui.image_view.view.removeItem(piezo_roi)
                except: pass

                piezo_range_nm = [parameters.get(dim) for dim in ["x_range (nm)", "y_range (nm)"]]
                piezo_lower_left_nm = [parameters.get(dim) for dim in ["x_min (nm)", "y_min (nm)"]]
                piezo_roi.setSize(piezo_range_nm, [0, 0], [0, 0])
                piezo_roi.setPos(piezo_lower_left_nm)

                # Add the frame to the ImageView
                if sct.status["view"] == "nanonis": sct.gui.image_view.addItem(piezo_roi)

            case "scan_metadata":
                signals = parameters.get("signal_dict")
                signals.pop("dict_name")
                [sct.gui.comboboxes[f"nanonis_mod{index + 1}"].renewItems(list(signals.keys())) for index in range(2)]

                # Refresh the recorded channels
                old_channels = sct.data.scan_processing_flags.get("channels")
                new_channels = parameters.get("channel_dict", {})
                
                # Update the channels combobox with the channels that are being recorded if there is a change
                if not old_channels == new_channels:
                    sct.data.scan_processing_flags.update({"channels": new_channels})
                    sct.gui.comboboxes["channels"].renewItems(list(new_channels.keys()))
                    [sct.gui.comboboxes["channels"].selectItem(preferred_channel) for preferred_channel in ["Current (A)", "LI Demod 1 X (A)", "Z (m)"]]
                    sct.update_processing_flags()

            case "lockin":
                for i, mod_dict in enumerate([parameters.get("mod1"), parameters.get("mod2")]):
                    
                    mod_values = [mod_dict.get(key) for key in ["frequency (Hz)", "amplitude (mV)", "phase (deg)", "time_constant (ms)"]]                    
                    [line_edits[f"nanonis_mod{i + 1}_{quantity}"].setValue(value) for quantity, value in zip(["f", "mV", "phi"], mod_values)]
                    
                    state = "off"
                    if mod_dict.get("on"):
                        state = "on"
                        f1 = mod_dict.get("frequency (Hz)", None)
                        if isinstance(f1, float | int):
                            sct.frequency.emit(f1)
                            [line_edits[f"demod_frequency_{i}"].setValue(i * f1) for i in range(32)]
                    sct.gui.buttons[f"nanonis_mod{i + 1}"].setState(state)

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


