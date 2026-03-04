from PyQt6 import QtCore



# Parameter management (getting from hardware, setting, loading from file and saving)
class ParameterManager(QtCore.QObject):
    
    def __init__(self, parent):
        super().__init__()
        self.scantelligent = parent # Reference to Scantelligent class



    def get(self, parameter_type: str = "frame") -> None:
        nanonis = self.scantelligent.nanonis
        gui = self.scantelligent.gui

        match parameter_type:
            case "feedback":
                nanonis.parameters_update(unlink = True)

            case "frame":
                nanonis.frame_update(unlink = True, update_new_frame = True)

            case "grid":
                nanonis.grid_update(unlink = True)

            case "speeds":
                nanonis.frame_update(unlink = True)

            case "gain":
                nanonis.gains_update(unlink = True)
            
            case "lockin":
                nanonis.lockin_update(unlink = True)
            
            case _:
                pass

        return

    def set(self, parameter_type: str = "frame") -> None:
        # It is noted that the nomenclature 'set' causes shadowing of the built-in 'set' method, but I decided to keep this regardless

        nanonis = self.scantelligent.nanonis
        gui = self.scantelligent.gui
        line_edits = gui.line_edits
        buttons = gui.buttons

        match parameter_type:

            case "feedback":
                nanonis.parameters_update(unlink = True)

            case "frame":
                offset = [line_edits["frame_x"].getValue(), line_edits["frame_y"].getValue()]
                scan_range = [line_edits["frame_width"].getValue(), line_edits["frame_height"].getValue()]
                angle = line_edits["frame_angle"].getValue()
                
                parameters = {"dict_name": "frame", "offset (nm)": offset, "scan_range (nm)": scan_range, "angle (deg)": angle}
                nanonis.frame_update(parameters, unlink = True)

            case "grid":                
                grid = [line_edits["grid_pixels"].getValue(), line_edits["grid_lines"].getValue()]
                
                nanonis.grid_update(unlink = True)

            case "speeds":
                nanonis.frame_update(unlink = True)

            case "gain":
                nanonis.gains_update(unlink = True)
            
            case "lockin":
                [mod1_on, mod2_on] = [buttons[f"nanonis_mod{i + 1}"].isChecked() for i in range(2)]
                [mod1_f, mod1_mV, mod1_phi] = [line_edits[f"nanonis_mod1_{quantity}"].getValue() for quantity in ["f", "mV", "phi"]]
                [mod2_f, mod2_mV, mod2_phi] = [line_edits[f"nanonis_mod2_{quantity}"].getValue() for quantity in ["f", "mV", "phi"]]
                parameters = {"dict_name": "lockin",
                              "modulator_1": {"on": mod1_on, "frequency (Hz)": mod1_f, "amplitude (mV)": mod1_mV, "phase (deg)": mod1_phi},
                              "modulator_2": {"on": mod2_on, "frequency (Hz)": mod2_f, "amplitude (mV)": mod2_mV, "phase (deg)": mod2_phi}}
                nanonis.lockin_update(parameters, unlink = True)
            
            case _:
                pass

        """
        for tag in ["V_nanonis", "V_mla", "I_fb", "p_gain", "t_const", "v_fwd", "v_bwd"]:
            str = self.gui.line_edits[tag].text()
            numbers = self.data.extract_numbers_from_str(str)
            if len(numbers) < 1: continue
            flt = numbers[0]
            
            match tag:
                case "V_nanonis": s_p.update({"V_nanonis (V)": flt})
                case "V_mla": s_p.update({"V_mla (V)": flt})
                case "I_fb": s_p.update({"I_fb (pA)": flt})
                case "p_gain": s_p.update({"p_gain (pm)": flt})
                case "t_const": s_p.update({"t_const (us)": flt})
                case "v_fwd": s_p.update({"v_fwd (nm/s)": flt})
                case "v_bwd": s_p.update({"v_bwd (nm/s)": flt})
                case _: pass

        self.nanonis.parameters_update(s_p)
        """

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
                sct.update_buttons()

            case "keithley_status":
                status = parameters.get("status")
                match status:
                    case "running": sct.status.update({"keithley": "running"})
                    case "online" | "idle": sct.status.update({"keithley": "idle"})
                    case "offline": sct.status.update({"keithley": "offline"})
                    case _: pass
                sct.update_buttons()

            case "camera_status":
                status = parameters.get("status")
                match status:
                    case "running": sct.status.update({"camera": "running"})
                    case "online" | "idle": sct.status.update({"camera": "idle"})
                    case "offline": sct.status.update({"camera": "offline"})
                    case _: pass
                sct.update_buttons()

            case "mla_status":
                status = parameters.get("status")
                match status:
                    case "running": sct.status.update({"mla": "running"})
                    case "idle": sct.status.update({"mla": "idle"})
                    case "offline": sct.status.update({"mla": "offline"})
                    case _: pass
                sct.update_buttons()

            case "session_path":
                session_path = parameters.get("path")
                sct.paths.update({"session_path": session_path})

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
                sct.status.update({"tip_status": tip_status})
                
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
                
                sct.update_tip_status()
            
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
                
                p_gain_ms = parameters.get("p_gain (pm)")
                t_const_us = parameters.get("t_const (us)")
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
                    sct.gui.comboboxes["channels"].selectItem("Z (m)")
                    sct.update_processing_flags()
            
            case "lockin":
                for i, mod_dict in enumerate([parameters.get("modulator_1"), parameters.get("modulator_2")]):
                    [line_edits[f"nanonis_mod{i + 1}_{quantity}"].setValue(value) for quantity, value in zip(["f", "mV", "phi"], [mod_dict.get("frequency (Hz)"), mod_dict.get("amplitude (mV)"), mod_dict.get("phase (deg)")])]

            case _:
                pass
