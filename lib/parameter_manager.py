import os, yaml
from PyQt6 import QtCore



# Parameter management (getting from hardware, setting, loading from file and saving)
class ParameterManager(QtCore.QObject):    
    def __init__(self, parent):
        super().__init__()
        self.scantelligent = parent # Reference to Scantelligent (parent)



    def get(self, parameter_type: str = "frame") -> None:
        sct = self.scantelligent
        
        if parameter_type in ["feedback", "frame", "grid", "speeds", "gain"]:
            if not hasattr(sct, "nanonis"): return

        match parameter_type:

            case "feedback":
                sct.nanonis.parameters_update(unlink = True)

            case "frame":
                sct.nanonis.frame_update(unlink = True, update_new_frame = True)

            case "grid":
                sct.nanonis.grid_update(unlink = True)

            case "speeds":
                sct.nanonis.frame_update(unlink = True)

            case "gain":
                sct.nanonis.gains_update(unlink = True)
            
            case "lockin":
                sct.nanonis.lockin_update(unlink = True)
            
            case _:
                pass

        return

    def set(self, parameter_type: str = "frame") -> None:
        # It is noted that the nomenclature 'set' causes shadowing of the built-in 'set' method, but I decided to keep this regardless
        sct = self.scantelligent
        
        # Abort if the relevant hardware objects are missing
        if parameter_type in ["feedback", "frame", "grid", "speeds", "gain"]:
            sct.logprint("Cannot set parameters without a Nanonis connection", message_type = "error")
            if not hasattr(sct, "nanonis"): return



        match parameter_type:

            case "feedback":
                parameters = {"dict_name": "feedback"}
                
                for parameter in ["V_nanonis (V)", "V_mla (V)", "I_fb (pA)", "p_gain (pm)", "t_const (us)", "v_fwd (nm/s)", "v_bwd (nm/s)"]:
                    quantity = parameter.split()[0]
                    val = sct.gui.line_edits[quantity].getValue()
                    if isinstance(val, int | float): parameters.update({parameter: val})

                sct.logprint(parameters)
                sct.nanonis.parameters_update(parameters, unlink = True)

            case "frame":
                offset = [sct.gui.line_edits[tag].getValue() for tag in ["frame_x", "frame_y"]]
                scan_range = [sct.gui.line_edits[tag].getValue() for tag in ["frame_width", "frame_height"]]
                angle = sct.gui.line_edits["frame_angle"].getValue()
                
                parameters = {"dict_name": "frame", "offset (nm)": offset, "scan_range (nm)": scan_range, "angle (deg)": angle}
                sct.nanonis.frame_update(parameters, unlink = True)

            case "grid":
                grid = [sct.gui.line_edits[tag].getValue() for tag in ["grid_pixels", "grid_lines"]]                
                sct.nanonis.grid_update(unlink = True)

            case "speeds":
                sct.nanonis.frame_update(unlink = True)

            case "gain":
                sct.nanonis.gains_update(unlink = True)
            
            case "lockin":
                sct.logprint("Setting mod")
                [mod1_on, mod2_on] = [bool(sct.gui.buttons[f"nanonis_mod{i + 1}"].state_index) for i in range(2)]
                mla_mod1_on = bool(sct.gui.buttons[f"mla_mod1"].state_index)
                [mod1_f, mod1_mV, mod1_phi] = [sct.gui.line_edits[f"nanonis_mod1_{quantity}"].getValue() for quantity in ["f", "mV", "phi"]]
                [mod2_f, mod2_mV, mod2_phi] = [sct.gui.line_edits[f"nanonis_mod2_{quantity}"].getValue() for quantity in ["f", "mV", "phi"]]
                [mla1_f, mla1_mV, mla1_phi] = [sct.gui.line_edits[f"mla_mod1_{quantity}"].getValue() for quantity in ["f", "mV", "phi"]]
                
                parameters = {"dict_name": "lockin",
                              "modulator_1": {"on": mod1_on, "frequency (Hz)": mod1_f, "amplitude (mV)": mod1_mV, "phase (deg)": mod1_phi},
                              "modulator_2": {"on": mod2_on, "frequency (Hz)": mod2_f, "amplitude (mV)": mod2_mV, "phase (deg)": mod2_phi},
                              "mla_mod1": {"on": mla_mod1_on, "frequency (Hz)": mla1_f, "amplitude (mV)": mla1_mV, "phase (deg)": mla1_phi}
                              }
                sct.nanonis.lockin_update(parameters, unlink = True)
            
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

            case "nanonis_status":
                status = parameters.get("status")
                match status:
                    case "running": sct.status.update({"nanonis": "running"})
                    case "online" | "idle": sct.status.update({"nanonis": "idle"})
                    case "offline": sct.status.update({"nanonis": "offline"})
                    case _: pass
                try: sct.gui.buttons["nanonis"].setState(status)
                except: pass

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
                    if channel_index < 0 or channel_index > 20: continue

                    sct.gui.channel_checkboxes[f"{channel_index}"].setToolTip(f"channel {channel_index}: {value}")
                    sct.gui.channel_checkboxes[f"{channel_index}"].setChecked(True)
                    line = sct.gui.plot_widget.plot()
                    sct.lines.append(line)

            case "tip_status":
                tip_status = parameters
                sct.status.update({"tip": tip_status})
                
                # Update the slider
                z_limits_nm = tip_status.get("z_limits (nm)")
                z_nm = tip_status.get("z (nm)")
                sct.gui.tip_slider.setMinimum(int(z_limits_nm[0]))
                sct.gui.tip_slider.setMaximum(int(z_limits_nm[1]))
                sct.gui.tip_slider.setValue(int(z_nm))
                sct.gui.tip_slider.changeToolTip(f"Tip height: {z_nm:.2f} nm")
                
                # Update the position visible in the image_view
                sct.gui.image_view.view.removeItem(sct.gui.tip_target)
                x_tip_nm = tip_status.get("x (nm)", 0)
                y_tip_nm = tip_status.get("y (nm)", 0)
                z_tip_nm = tip_status.get("z (nm)", 0)
                sct.gui.tip_target.setPos(x_tip_nm, y_tip_nm)
                sct.gui.tip_target.text_item.setText(f"tip location\n({x_tip_nm:.2f}, {y_tip_nm:.2f}, {z_tip_nm:.2f}) nm")
                if sct.status["view"] == "nanonis": sct.gui.image_view.view.addItem(sct.gui.tip_target)
                
                # Update the tip status button
                withdrawn = tip_status.get("withdrawn")
                feedback = tip_status.get("feedback")
                
                if withdrawn:
                    sct.gui.buttons["tip"].setState("unknown")
                    sct.gui.buttons["withdraw"].setState("withdrawn")
                else:
                    sct.gui.buttons["withdraw"].setState("landed")
                    if feedback: sct.gui.buttons["tip"].setState("feedback")
                    else: sct.gui.buttons["tip"].setState("constant_height")
            
            case "scan_parameters":
                scan_parameters = parameters
                sct.user.scan_parameters[0].update(scan_parameters)

            case "frame":
                frame = parameters
                sct.user.frames[0].update(frame)
            
                [x_0_nm, y_0_nm] = frame.get("offset (nm)", [0, 0])
                [w_nm, h_nm] = frame.get("scan_range (nm)", [100, 100])
                angle_deg = frame.get("angle (deg)", 0)
                aspect_ratio = h_nm / w_nm

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
                frame = parameters
           
                [x_0_nm, y_0_nm] = frame.get("offset (nm)", [0, 0])
                [w_nm, h_nm] = frame.get("scan_range (nm)", [100, 100])
                angle_deg = frame.get("angle (deg)", 0)
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
                grid = parameters

                pixels = grid.get("pixels")
                lines = grid.get("lines")
                pixel_width = grid.get("pixel_width (nm)")
                pixel_height = grid.get("pixel_height (nm)")
                aspect_ratio = lines / pixels

                # Update the fields in the GUI
                [line_edits[name].setValue(parameter) for name, parameter in zip(["grid_pixels", "grid_lines", "grid_aspect", "pixel_width", "pixel_height"], [pixels, lines, aspect_ratio, pixel_width, pixel_height])]

            case "gains":
                gains = parameters
                
                p_gain_ms = gains.get("p_gain (pm)")
                t_const_us = gains.get("t_const (us)")
                i_gain_nm_per_s = p_gain_ms / (1000 * t_const_us)

                # Update the fields in the GUI
                [line_edits[name].setValue(parameter) for name, parameter in zip(["p_gain", "t_const", "i_gain"], [p_gain_ms, t_const_us, i_gain_nm_per_s])]

            case "piezo_range":
                piezo_range = parameters

                piezo_roi = sct.gui.piezo_roi
                try: sct.gui.image_view.view.removeItem(piezo_roi)
                except: pass

                piezo_range_nm = [piezo_range.get("x_range (nm)"), piezo_range.get("y_range (nm)")]
                piezo_lower_left_nm = [piezo_range.get("x_min (nm)"), piezo_range.get("y_min (nm)")]
                piezo_roi.setSize(piezo_range_nm, [0, 0], [0, 0])
                piezo_roi.setPos(piezo_lower_left_nm)

                # Add the frame to the ImageView
                if sct.status["view"] == "nanonis": sct.gui.image_view.addItem(piezo_roi)

            case "scan_metadata":
                scan_metadata = parameters

                # Refresh the recorded channels
                if hasattr(sct, "channels"): channels_old = sct.channels
                else: channels_old = {}
                sct.channels = scan_metadata.get("channel_dict", {})
                
                # Update the channels combobox with the channels that are being recorded if there is a change
                if sct.channels == channels_old:
                    pass
                else:
                    sct.gui.comboboxes["channels"].renewItems(list(sct.channels.keys()))
                    [sct.gui.comboboxes["channels"].selectItem(preferred_channel) for preferred_channel in ["LI Demod 1X (A)", "Current (A)", "Z (m)"]]
                    sct.update_processing_flags()

            case "lockin":
                for i, mod_dict in enumerate([parameters.get("modulator_1"), parameters.get("modulator_2")]):
                    [line_edits[f"nanonis_mod{i + 1}_{quantity}"].setValue(value) for quantity, value in zip(["f", "mV", "phi"], [mod_dict.get("frequency (Hz)"), mod_dict.get("amplitude (mV)"), mod_dict.get("phase (deg)")])]
                    
                    state = "off"
                    if mod_dict.get("on"): state = "on"
                    sct.gui.buttons[f"nanonis_mod{i + 1}"].setState(state)

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


