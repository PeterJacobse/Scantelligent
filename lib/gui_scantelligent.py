import os, sys
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
from .sct_widgets import SCTWidgets, CurrentHeightIndicatorWidget, MinMaxMethods, rotate_icon, make_layout, make_line
import numpy as np



class ScantelligentGUI(SCTWidgets.MainWindow):
    def __init__(self):
        super().__init__()
        
        self.color_list = ["#FFFFFF", "#FF0000", "#00FF00", "#0066FF", "#FFFF00", "#00FFFF", "#FF00FF", "#FF9900", "#99FF00", "#00FFCC", "#FF0066", "#CCFF00", "#CC00FF",
                           "#FF5500", "#33FF00", "#0099FF", "#FF00AA", "#66FF66", "#3300FF", "#FFCC00", "#00FF66", "#9900FF", "#FF3333", "#A8FF33", "#00CCFF",
                           "#FF8888", "#88FF88", "#8888FF", "#FFBB55", "#D4FF88", "#88FFFF", "#FF88FF", "#FFCC99", "#99FFCC", "#CC99FF"]
        self.colors = {"red": "#ff5050", "dark_red": "#800000", "green": "#00ff00", "dark_green": "#005000", "light_blue": "#30d0ff", "off-black": "#101010",
                       "white": "#ffffff", "blue": "#2090ff", "orange": "#FFA000","dark_orange": "#A05000", "black": "#000000", "purple": "#700080", "dark_gray": "#606060"}
        self.style_sheets = {
            "neutral": f"background-color: {self.colors["black"]};",
            "connected": f"background-color: {self.colors["dark_green"]};",
            "disconnected": f"background-color: {self.colors["dark_red"]};",
            "running": f"background-color: {self.colors["blue"]};",
            "hold": f"background-color: {self.colors["dark_orange"]};",
            "idle": f"background-color: {self.colors["purple"]};"
            }

        # 1: Read icons from file.
        self.icons = self.get_icons()
        
        # 2: Create the specific GUI items using the items from the GUIItems class. Requires icons.
        self.labels = self.make_labels()
        self.buttons = self.make_buttons()
        self.checkboxes = self.make_checkboxes()
        self.comboboxes = self.make_comboboxes()
        self.line_edits = self.make_line_edits()
        self.progress_bars = self.make_progress_bars()
        self.layouts = self.make_layouts()
        (self.image_view, self.camera_view) = self.make_views()
        (self.piezo_roi, self.frame_roi, self.new_frame_roi, self.tip_target, self.target0, self.path_pdi) = self.make_image_view_widgets()
        self.grapher = self.make_plot_widget()
        self.widgets = self.make_custom_widgets()
        self.consoles = self.make_consoles()
        self.sliders = self.make_sliders()
        self.shortcuts = self.make_shortcuts()
        self.dialogs = self.make_dialogs()
        (self.info_box, self.message_box) = self.make_boxes()
                
        # 3: Populate layouts with GUI items. Requires GUI items.
        self.populate_layouts()
        
        # 4: Make groupboxes and set their layouts. Requires populated layouts.
        self.groupboxes = self.make_groupboxes()
                
        # 5: Set up the main window layout
        self.setup_main_window()



    # 1: Read icons from file.
    def get_icons(self) -> dict:
        lib_folder = os.path.dirname(os.path.abspath(__file__))
        project_folder = os.path.dirname(lib_folder)
        sys_folder = os.path.join(project_folder, "sys")
        splash_screen_path = os.path.join(sys_folder, "splash_screen.png")
        icon_folder = os.path.join(project_folder, "icons")
        icon_files = os.listdir(icon_folder)
        
        self.paths = {
            "scantelligent_folder": project_folder,
            "lib_folder": lib_folder,
            "sys_folder": sys_folder,
            "icon_folder": icon_folder,
            "splash_screen": splash_screen_path
        }
        
        icons = {}
        for icon_file in icon_files:
            [icon_name, extension] = os.path.splitext(os.path.basename(icon_file))
            try:
                if extension == ".png": icons.update({icon_name: QtGui.QIcon(os.path.join(icon_folder, icon_file))})
            except:
                pass
        
        return icons



    # 2: Create the specific GUI items using the items from the GUIItems class. Requires icons.
    def make_labels(self) -> dict:
        LB = SCTWidgets.Label
        
        labels = {
            "session_folder": LB(text = "Session folder"),
            "statistics": LB(text = "Statistics"),
            "load_file": LB(text = "Load file:"),
            "in_folder": LB(text = "in folder:"),
            "number_of_files": LB(text = "which contains 1 sxm file"),
            
            "current": LB(text = "current"),
            "gain": LB(text = "gain"),

            "frame": LB(text = "frame"),
            "grid": LB(text = "grid"),
            "empty": LB(text = " "),
            
            "forward": LB(text = "forward"),
            "backward": LB(text = "backward"),
            "tip": LB(text = "tip"),
            
            "pulse": LB(text = "pulse"),
            "shape": LB(text = "shape"),
            
            "nanonis": LB(text = "Nanonis"),
            "mla": LB(text = "MLA"),
            "keithley": LB(text = "Keithley"),
            
            "quick_experiment": LB(text = "quick"),
            "custom_experiment": LB(text = "custom"),
            "experiment_settings": LB(text = "settings"),

            "move_horizontally": LB(text = "< horizontal motion >", tooltip = "In composite motion, horizontal motion\nis carried out between retract and advance\nSee 'horizontal'"),
        }
        
        [labels.update({f"demod_index_{i}": LB(text = f"#{i}", tooltip = f"demodulator index {i}")}) for i in range(32)]
        
        return labels

    def make_buttons(self) -> dict:
        MSB = SCTWidgets.MultiStateButton
        
        sct_blue = self.colors["blue"]
        sct_black = self.colors["off-black"]
        icons = self.icons
        arrow = icons.get("single_arrow")
        arrow45 = icons.get("single_arrow_45")
        mtt = "Move the tip "
        sivr = "Set the image value range "

        buttons = {
            # Connections
            "scanalyzer": MSB(icon = icons.get("scanalyzer"), click_to_toggle = False,
                              states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Scanalyzer: not found"},
                                        {"name": "online", "color": self.colors["dark_green"], "tooltip": "Launch Scanalyzer"}]),
            "nanonis": MSB(icon = icons.get("nanonis"), click_to_toggle = False,
                           states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Nanonis: offline"},
                                     {"name": "online", "color": self.colors["dark_green"], "tooltip": "Nanonis: online (idle)"},
                                     {"name": "idle", "color": self.colors["dark_green"], "tooltip": "Nanonis: online (idle)"},
                                     {"name": "running", "color": sct_blue, "tooltip": "Nanonis: running"}]),
            "mla": MSB(icon = icons.get("imp"), click_to_toggle = False,
                       states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Multifrequency Lockin Amplifier: offline"},
                                 {"name": "online", "color": self.colors["dark_green"], "tooltip": "Multifrequency Lockin Amplifier: online (idle)"},
                                 {"name": "idle", "color": self.colors["dark_green"], "tooltip": "Multifrequency Lockin Amplifier: online (idle)"},
                                 {"name": "running", "color": sct_blue, "tooltip": "Multifrequency Lockin Amplifier: running"}]),
            "keithley": MSB(icon = icons.get("keithley"), click_to_toggle = False,
                            states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Keithley source meter: offline"},
                                      {"name": "online", "color": self.colors["dark_green"], "tooltip": "Keithley source meter: online (idle)"},
                                      {"name": "idle", "color": self.colors["dark_green"], "tooltip": "Keithley source meter: online (idle)"},
                                      {"name": "running", "color": sct_blue, "tooltip": "Keithley source meter: running"}]),
            "camera": MSB(icon = icons.get("camera"), click_to_toggle = False,
                          states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Camera: offline"},
                                    {"name": "online", "color": self.colors["dark_green"], "tooltip": "Camera: online (idle)"},
                                    {"name": "idle", "color": self.colors["dark_green"], "tooltip": "Camera: online (idle)"},
                                    {"name": "running", "color": sct_blue, "tooltip": "Camera: running"}]),
            "view": MSB(click_to_toggle = False, size = 28,
                        states = [{"name": "none", "tooltip": "toggle the active view", "icon": icons.get("view"), "color": sct_black},
                                  {"name": "camera", "tooltip": "active view: Camera", "icon": icons.get("view_camera"), "color": sct_black},
                                  {"name": "nanonis", "tooltip": "active view: Nanonis", "icon": icons.get("view_nanonis"), "color": sct_black},
                                  {"name": "graph", "tooltip": "active view: graph", "icon": icons.get("view_graph"), "color": sct_black}]),
            "exit": MSB(tooltip = "Exit Scantelligent\n(Esc / X / E)", icon = icons.get("escape"), size = 28),
            "session_folder": MSB(icon = icons.get("folder_yellow"), click_to_toggle = False,
                                  states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Session folder unknown"},
                                            {"name": "online", "color": self.colors["dark_green"], "tooltip": "Open the session folder"}]),
            "info": MSB(tooltip = "Info", icon = icons.get("i")),
            "spectelligent": MSB(tooltip = "Open Spectelligent", icon = icons.get("start_spectrum")),
            "spectelligent_2": MSB(tooltip = "Open Spectelligent", icon = icons.get("start_spectrum"), size = 28),
            
            # Experiment
            "save": MSB(tooltip = "Save the experiment results to file", icon = icons.get("floppy"), click_to_toggle = True,
                        states = [{"name": "idle", "color": sct_black, "tooltip": "Click this button to save experiment data"},
                                  {"name": "data_present", "color": sct_blue, "tooltip": "Experiment data is present. Click to save"},
                                  {"name": "data_saved", "color": self.colors["dark_green"], "tooltip": "Experiment data was saved"}]),
            "start_stop": MSB(click_to_toggle = False, size = 28,
                              states = [{"name": "load", "color": self.colors["dark_red"], "tooltip": "Load/reset experiment", "icon": icons.get("start")},
                                        {"name": "ready", "color": self.colors["dark_green"], "tooltip": "Start experiment", "icon": icons.get("start")},
                                        {"name": "running", "color": sct_blue, "tooltip": "Experiment running", "icon": icons.get("stop")},
                                        {"name": "aborted", "color": self.colors["orange"], "tooltip": "Abort requested", "icon": icons.get("stop")}]),
            "scan_direction": MSB(click_to_toggle = True, size = 28, states = [{"name": "nearest_tip", "color": sct_black, "tooltip": "Scan from corner\nnearest the tip", "icon": icons.get("nearest_tip")},
                                                                               {"name": "up", "color": sct_black, "tooltip": "Grid scan up", "icon": icons.get("grid_up")},
                                                                               {"name": "down", "color": sct_black, "tooltip": "Grid scan down", "icon": icons.get("grid_down")},
                                                                               {"name": "gaussian_process", "color": sct_black, "tooltip": "Gaussian Process Regression scan", "icon": icons.get("gaussian_process")}]),
            
            # Locks
            "frame_aspect": MSB(tooltip = "Lock the frame aspect ratio", states = [{"name": "unlocked", "color": sct_black, "icon": icons.get("unlock_aspect")}, {"name": "locked", "color": sct_blue, "icon": icons.get("lock_aspect")}]),
            "grid_aspect": MSB(tooltip = "Lock the grid aspect ratio", states = [{"name": "unlocked", "color": sct_black, "icon": icons.get("unlock_aspect")}, {"name": "locked", "color": sct_blue, "icon": icons.get("lock_aspect")}]),
            "speed_lock": MSB(tooltip = "Lock the scan speed ratio", states = [{"name": "unlocked", "color": sct_black, "icon": icons.get("unlock_aspect")}, {"name": "locked", "color": sct_blue, "icon": icons.get("lock_aspect")}]),
            "voltage_lock": MSB(tooltip = "Tie the MLA voltage to the Nanonis bias", states = [{"name": "unlocked", "color": sct_black, "icon": icons.get("unlock_aspect")}, {"name": "locked", "color": sct_blue, "icon": icons.get("lock_aspect")}]),
            
            # Parameters
            "tip": MSB(click_to_toggle = False, size = 28,
                       states = [{"name": "unknown", "tooltip": "Tip status\nUnknown / withdrawn", "icon": icons.get("tip_unknown"), "color": sct_black},
                                 {"name": "feedback", "tooltip": "Tip status\nIn feedback", "icon": icons.get("constant_current"), "color": self.colors["dark_green"]},
                                 {"name": "constant_height", "tooltip": "Tip status\nConstant height", "icon": icons.get("constant_height"), "color": self.colors["orange"]}]),
            "intermediate_feedback": MSB(click_to_toggle = False, size = 28,
                                         states = [{"name": "off", "tooltip": "Do not go into intermediate feedback", "icon": icons.get("constant_height"), "color": sct_black},
                                                   {"name": "on", "tooltip": "Return to intermediate feedback\nafter every sweep in x", "icon": icons.get("constant_current"), "color": self.colors["dark_green"]}]),
            "reference_height": MSB(click_to_toggle = False, size = 28,
                                    states = [{"name": "off", "tooltip": "Do not use a different height\nrelative to the feedback setpoint", "icon": icons.get("constant_height"), "color": sct_black},
                                              {"name": "on", "tooltip": "After intermediate feedback,\nadjust the tip height", "icon": icons.get("constant_current"), "color": self.colors["dark_green"]}]),
            
            # Coarse vertical
            "withdraw": MSB(click_to_toggle = False, states = [{"name": "landed", "tooltip": "Withdraw the tip\n(Ctrl + W)", "icon": icons.get("withdraw"), "color": sct_blue},
                                                               {"name": "withdrawn", "tooltip": "Land the tip\n(Ctrl + W)", "icon": self.icons.get("approach"), "color": sct_black}]),
            "withdraw_2": MSB(click_to_toggle = False, states = [{"name": "landed", "tooltip": "Withdraw the tip\n(Ctrl + W)", "icon": icons.get("withdraw"), "color": sct_blue},
                                                                 {"name": "withdrawn", "tooltip": "Land the tip\n(Ctrl + W)", "icon": self.icons.get("approach"), "color": sct_black}]),
            "retract": MSB(tooltip = "Retract the tip from the surface\n(Ctrl + PgUp)", icon = icons.get("retract")),
            "advance": MSB(tooltip = "Advance the tip towards the surface\n(Ctrl + PgDown)", icon = icons.get("advance")),
            "approach": MSB(size = 28, states = [{"name": "idle", "tooltip": "Initiate auto approach", "icon": icons.get("start_approach"), "color": sct_black},
                                                 {"name": "running", "tooltip": "Stop auto approach", "icon": icons.get("stop_approach"), "color": sct_blue}]),
            "approach_2": MSB(size = 28, states = [{"name": "idle", "tooltip": "Initiate auto approach", "icon": icons.get("start_approach"), "color": sct_black},
                                                   {"name": "running", "tooltip": "Stop auto approach", "icon": icons.get("stop_approach"), "color": sct_blue}]),

            # Coarse horizontal
            "n": MSB(tooltip = mtt + "north\n(Ctrl + ↑ / Ctrl + 8)", icon = rotate_icon(arrow, angle = 270)),
            "ne": MSB(tooltip = mtt + "northeast\n(Ctrl + 9)", icon = rotate_icon(arrow45, angle = 0)),
            "e": MSB(tooltip = mtt + "east\n(Ctrl + → / Ctrl + 6)", icon = rotate_icon(arrow, angle = 0)),
            "se": MSB(tooltip = mtt + "southeast\n(Ctrl + 3)", icon = rotate_icon(arrow45, angle = 90)),
            "s": MSB(tooltip = mtt + "south\n(Ctrl + ↓ / Ctrl + 2)", icon = rotate_icon(arrow, angle = 90)),
            "sw": MSB(tooltip = mtt + "southwest\n(Ctrl + 1)", icon = rotate_icon(arrow45, angle = 180)),
            "w": MSB(tooltip = mtt + "west\n(Ctrl + ← / Ctrl + 4)", icon = rotate_icon(arrow, angle = 180)),
            "nw": MSB(tooltip = mtt + "northwest\n(Ctrl + 7)", icon = rotate_icon(arrow45, angle = 270)),
            
            "composite_motion": MSB(icon = self.icons.get("composite_motion"), size = 28,
                                    states = [{"tooltip": "Composite motion OFF\nThe horizontal motion is carried out without vertical motion", "color": sct_black},
                                              {"tooltip": "Composite motion ON\nAll checked vertical motions are combined with the horizontal motion in a composite pattern", "color": sct_blue}]),

            # Tip prep
            "bias_pulse": MSB(tooltip = "Apply a voltage pulse to the tip", icon = icons.get("bias_pulse"), size = 28),
            "tip_shape": MSB(tooltip = "Shape the tip by poking it into the surface", icon = icons.get("tip_shape"), size = 28),
            
            # Lockins         
            "nanonis_mod1": MSB(icon = icons.get("nanonis_mod1"),
                                states = [{"name": "off", "tooltip": "Nanonis modulator 1 OFF", "color": sct_black},
                                          {"name": "on", "tooltip": "Nanonis modulator 1 ON", "color": sct_blue}]),
            "nanonis_mod2": MSB(icon = icons.get("nanonis_mod2"),
                                states = [{"name": "off", "tooltip": "Nanonis modulator 2 OFF", "color": sct_black},
                                          {"name": "on", "tooltip": "Nanonis modulator 2 ON", "color": sct_blue}]),

            "start_scan": MSB(size = 28, states = [{"name": "idle", "tooltip": "Start scan", "icon": icons.get("start_scan"), "color": sct_black},
                                                   {"name": "running", "tooltip": "Stop scan", "icon": icons.get("stop_scan"), "color": sct_blue}]),
            "auto_paste": MSB(tooltip = "Auto paste scans when finished", icon = icons.get("paste"), states = [{"color": sct_black}, {"color": sct_blue}]),
            
            # Speeds
            "v_fwd": MSB(icon = icons.get("v_forward")),
            "v_bwd": MSB(icon = icons.get("v_backward")),
            "v_tip": MSB(icon = icons.get("v_tip")),
            
            # Processing
            "direction": MSB(tooltip = "Change scan direction\n(X)",
                             states = [{"name": "forward", "icon": icons.get("double_arrow"), "color": sct_black},
                                       {"name": "backward", "icon": rotate_icon(icons.get("double_arrow"), angle = 180), "color": sct_blue}]),
            "fit_to_frame": MSB(tooltip = "Snap the view range to the scan frame", icon = icons.get("scan_frame")),
            "fit_to_range": MSB(tooltip = "Snap the view range to the total piezo range", icon = icons.get("piezo_range")),
            
            "full_data_range": MSB(tooltip = sivr + "to the full data range\n(U)", icon = icons.get("100")),
            "percentiles": MSB(tooltip = sivr + "by percentiles\n(R)", icon = icons.get("percentiles")),
            "standard_deviation": MSB(tooltip = sivr + "by standard deviations\n(D)", icon = icons.get("deviation")),
            "absolute_values": MSB(tooltip = sivr + "by absolute values\n(A)", icon = icons.get("numbers")),
            
            "bg_none": MSB(states = [{"tooltip": "None\n(0)", "icon": self.icons.get("0_2"), "color": sct_black}, {"color": sct_blue}]),
            "bg_plane": MSB(states = [{"tooltip": "Plane\n(0)", "icon": self.icons.get("plane_subtract"), "color": sct_black}, {"color": sct_blue}]),
            "bg_linewise": MSB(states = [{"tooltip": "Linewise\n(0)", "icon": self.icons.get("lines"), "color": sct_black}, {"color": sct_blue}]),
            "bg_inferred": MSB(states = [{"tooltip": "None\n(0)", "icon": self.icons.get("0_2"), "color": sct_black}, {"color": sct_blue}]),
            
            "sobel": MSB(tooltip = "Compute the complex gradient d/dx + i d/dy\n(Shift + S)", icon = self.icons.get("sobel"), states = [{"color": sct_black}, {"color": sct_blue}]),
            "laplace": MSB(tooltip = "Compute the Laplacian (d/dx)^2 + (d/dy)^2\n(Shift + L)", icon = self.icons.get("laplacian"), states = [{"color": sct_black}, {"color": sct_blue}]),
            "fft": MSB(tooltip = "Compute the 2D Fourier transform\n(Shift + F)", icon = self.icons.get("fourier"), states = [{"color": sct_black}, {"color": sct_blue}]),
            "normal": MSB(tooltip = "Compute the z component of the surface normal\n(Shift + N)", icon = self.icons.get("surface_normal"), states = [{"color": sct_black}, {"color": sct_blue}]),
            "gaussian": MSB(tooltip = "Gaussian blur applied\n(Shift + G) or provide a width to toggle", icon = self.icons.get("gaussian"), states = [{"color": sct_black}, {"color": sct_blue}]),
            "rot_trans": MSB(tooltip = "Show the scan in the scan window coordinates\nwith rotation and translation\n(R)", icon = self.icons.get("rot_trans"), states = [{"color": sct_black}, {"color": sct_blue}]),
            
            "audio": MSB(icon = icons.get("audio"), states = [{"name": "off", "tooltip": "Auditory feedback of current signal\nOFF", "color": self.colors["dark_red"]},
                                                              {"name": "on", "tooltip": "Auditory feedback of current signal\nOFF", "color": sct_blue}]),
            
            "frame": MSB(icon = icons.get("guide_frame"), states = [{"name": "off", "tooltip": "Click to show the guide frame\nMouse wheel click confirms the frame", "color": sct_black},
                                                                    {"name": "on", "tooltip": "Click to hide the guide frame\nMouse wheel click confirms the frame", "color": sct_blue}]),
            "path": MSB(icon = icons.get("path"), states = [{"name": "off", "tooltip": "Click to show the tip path", "color": sct_black},
                                                                    {"name": "on", "tooltip": "Click to hide the tip path", "color": sct_blue}]),
            
            "slice": MSB(icon = icons.get("slice_xy"), tooltip = "Select which plane to slice the scan over"),
            "set_dz": MSB(icon = icons.get("set_dz"), tooltip = "Push to set delta_z\nSee value below"),
            "trash": MSB(icon = icons.get("trash"), tooltip = "Discard the currently selected scan_item")
        }
        self.limits_button = QtWidgets.QPushButton("limits")
        
        for parameter_type in ["bias", "mla_bias", "keithley_bias", "coarse", "gain", "speed", "frame", "grid", "feedback", "lockin", "tip_shaper", "spectroscopy"]:
            buttons.update({f"get_{parameter_type}_parameters": MSB(tooltip = "Get parameters", icon = icons.get("get"))})
            buttons.update({f"set_{parameter_type}_parameters": MSB(tooltip = "Set the new parameters", icon = icons.get("set"))})
        [buttons.update({f"experiment_{i}": MSB(tooltip = f"experiment button {i}", icon = icons.get(f"{i}"))}) for i in range(6)]

        # Initialize
        [buttons[name].setState(1) for name in ["frame_aspect", "grid_aspect", "bg_none", "auto_paste", "view", "voltage_lock", "speed_lock", "frame", "path"]]
        buttons["frame_aspect"].clicked.connect(lambda: self.update_lock("frame"))
        buttons["grid_aspect"].clicked.connect(lambda: self.update_lock("grid"))

        # Named groups
        self.arrow_buttons = [buttons[direction] for direction in ["nw", "n", "ne", "w", "n", "e", "sw", "s", "se"]]
        self.action_buttons = [buttons[name] for name in ["withdraw", "retract", "advance", "approach"]]

        # Add the button handles to the tooltips
        [buttons[name].changeToolTip(f"gui.buttons[\"{name}\"]", line = 10) for name in buttons.keys()]

        return buttons

    def make_checkboxes(self) -> tuple[dict, dict]:
        CB = SCTWidgets.CheckBox
        BG = SCTWidgets.ButtonGroup

        checkboxes = {
            # Coarse
            "withdraw": CB(tooltip = "Include withdrawing of the tip during a tip move"),
            "retract": CB(tooltip = "Include retracting the tip during a tip move"),
            "advance": CB(tooltip = "Include advancing the tip during a move"),
            "approach": CB(tooltip = "End the tip move with an auto approach"),
            
            # Limits
            "min_full": CB(tooltip = "Set to minimum value of scan data range"),
            "max_full": CB(tooltip = "Set to maximum value of scan data range"),
            "min_percentiles": CB(tooltip = "Set to minimum percentile of data range"),
            "max_percentiles": CB(tooltip = "Set to maximum percentile of data range"),
            "min_deviations": CB(tooltip = "Set to minimum = mean - n * standard deviation"),
            "max_deviations": CB(tooltip = "Set to maximum = mean + n * standard deviation"),
            "min_absolute": CB(tooltip = "Set minimum to an absolute value"),
            "max_absolute": CB(tooltip = "Set maximum to an absolute value"),
        }        
        [checkboxes.update({f"channel_{index}": CB(tooltip = f"channel {index}", color = self.color_list[index])}) for index in range(35)] # Channels

        # Named groups
        self.action_checkboxes = [checkboxes[name] for name in ["withdraw", "retract", "advance", "approach"]]
        [checkbox.setChecked(True) for checkbox in self.action_checkboxes]
        checkboxes["advance"].setChecked(False)

        # Add the button handles to the tooltips
        [checkboxes[name].changeToolTip(f"gui.checkboxes[\"{name}\"]", line = 10) for name in checkboxes.keys()]
        
        # Add buttons to QButtonGroups for exclusive selection and check the defaults
        self.button_groups = {
            "min": BG(),
            "max": BG(),
            "background": BG(),
            "channels": BG(exclusive = False, keep_one_checked = False)
        }
        limit_methods = ["full", "percentiles", "deviations", "absolute"]        
        [self.button_groups["min"].addButton(checkboxes[f"min_{method}"], f"min_{method}") for method in limit_methods]
        [self.button_groups["max"].addButton(checkboxes[f"max_{method}"], f"max_{method}") for method in limit_methods]
        [self.button_groups["background"].addButton(self.buttons[f"bg_{method}"], f"bg_{method}") for method in ["none", "plane", "linewise"]]
        [self.button_groups["channels"].addButton(checkboxes[f"channel_{index}"], f"{index}") for index in range(35)]
        
        # Initialize
        checked_buttons = [checkboxes[name] for name in ["min_full", "max_full"]]
        [button.setChecked(True) for button in checked_buttons]

        return checkboxes

    def make_comboboxes(self) -> dict:
        CB = SCTWidgets.ComboBox
        
        comboboxes = {
            "projection": CB(tooltip = "Select a projection or toggle with\n(Shift + ↑)", items = ["re", "im", "abs", "arg (b/w)", "arg (hue)", "complex", "abs^2", "log(abs)"]),
            "experiment": CB(tooltip = "Select an experiment"),
            "direction": CB(tooltip = "Select a scan direction / pattern"),
            "axis": CB(tooltip = "Select the view axis", items = ["(x, y)", "(x, channel)", "(channel, y)"]),
            "slice": CB(tooltip = "Select the slice"),
            
            "tia_gain": CB(tooltip = "Transimpedance amplifier gain setting"),
            
            "bias": CB(tooltip = "Load bias parameters"),
            "feedback": CB(tooltip = "Load feedback parameters"),
            "speeds": CB(tooltip = "Load speed parameters"),
            "frame_grid": CB(tooltip = "Load frame/grid parameters"),
            "spectroscopy": CB(tooltip = "Load spectroscopy parameters"),
            "spectroscopy_parameter": CB(tooltip = "Load spectroscopy parameters", items = ["V_nanonis", "V_mla", "V_keithley", "f_mla", "z_nanonis"]),
            
            "approach_fb_parameters": CB(tooltip = "What feedback parameter set to use transiently during tip approach"),
                        
            "nanonis_mod1": CB(tooltip = "Add Nanonis modulator 1 to this channel"),
            "nanonis_mod2": CB(tooltip = "Add Nanonis modulator 2 to this channel"),
            "mla_mod0": CB(tooltip = "Add MLA modulator 0 to this output port", items = ["port 1", "port 2"]),
            "mla_mod1": CB(tooltip = "Add MLA modulator 1 to this output port", items = ["port 1", "port 2"]),
            "mla_mod2": CB(tooltip = "Add MLA modulator 1 to this output port", items = ["port 1", "port 2"]),
            "mla_mod3": CB(tooltip = "Add MLA modulator 1 to this output port", items = ["port 1", "port 2"]),
            
            "scan_items": CB(tooltip = "Scan items"),
            "graph_x_axis": CB(tooltip = "Channel to use for the x axis")
        }
        
        # Add the button handles to the tooltips
        [comboboxes[name].changeToolTip(f"gui.comboboxes[\"{name}\"]", line = 10) for name in comboboxes.keys()]        
        return comboboxes

    def make_line_edits(self) -> dict:
        LE = SCTWidgets.PhysicsLineEdit
        ILE = SCTWidgets.InputLineEdit
        RG = SCTWidgets.ReciprocalGroup
        
        scanalyzer_blue = "#2020C0"
        sct_black = self.colors["off-black"]
        
        line_edits = {
            # Experiment
            "experiment_filename": LE(tooltip = "base name of the file when saved to png or hdf5"),

            # Coarse
            "z_steps": LE(value = 20, tooltip = "steps in the +z (retract) direction", unit = "↑", limits = [0, 100000], digits = 0, max_width = 100),
            "h_steps": LE(value = 100, tooltip = "steps in the horizontal direction", unit = "← →", limits = [0, 100000], digits = 0, max_width = 100),
            "minus_z_steps": LE(value = 0, tooltip = "steps in the -z (advance) direction", unit = "↓", limits = [0, 100000], digits = 0, max_width = 100),
            
            "V_hor": LE(value = 150, tooltip = "voltage supplied to the coarse piezos during horizontal movement", unit = "V (xy)", digits = 0, max_width = 100),
            "V_ver": LE(value = 150, tooltip = "voltage supplied to the coarse piezos during vertical movement", unit = "V (z)", digits = 0, max_width = 100),
            "f_motor": LE(value = 1000, tooltip = "sawtooth wave frequency supplied to the coarse piezos during movement", unit = "Hz", digits = 0, max_width = 100),
            
            "approach_min_percentile": LE(value = 40, tooltip = "minimum percentile of the piezo range\nWithdraw and coarse adjust if the tip lands below this value", unit = "%", digits = 0),
            "approach_max_percentile": LE(value = 60, tooltip = "maximum percentile of the piezo range\nWithdraw and coarse adjust if the tip lands above this value", unit = "%", digits = 0),

            # Parameters
            # Bias
            "V_nanonis": LE(tooltip = "Nanonis bias", unit = "V", limits = [-10, 10], digits = 3, edited_color = scanalyzer_blue),
            "V_mla_port1": LE(tooltip = "MLA bias on port 1", unit = "V", limits = [-10, 10], digits = 3, edited_color = scanalyzer_blue),
            "V_mla_port2": LE(tooltip = "MLA bias on port 2", unit = "V", limits = [-10, 10], digits = 3, edited_color = scanalyzer_blue),
            "V_keithley": LE(tooltip = "Keithley bias", unit = "V", limits = [-200, 200], digits = 3, edited_color = scanalyzer_blue),

            "dV_nanonis": LE(tooltip = "voltage step dV when ramping the bias", unit = "mV", limits = [-1000, 1000], digits = 1),
            "dt_nanonis": LE(tooltip = "time step dt when ramping the bias", unit = "ms", limits = [-1000, 1000], digits = 0),
            "dz_nanonis": LE(tooltip = "height step dz when ramping the bias\nTemporarily retract the tip by this amount when ramping to a different polarity", unit = "nm", limits = [-200, 200], digits = 1),

            "dV_keithley": LE(tooltip = "voltage step dV when ramping the Keithley bias", unit = "mV", limits = [-1000, 1000], digits = 1),
            "dt_keithley": LE(tooltip = "time step dt when ramping the Keithley bias", unit = "ms", limits = [-1000, 1000], digits = 0, edited_color = scanalyzer_blue),
            
            "I": LE(tooltip = "most recent current measurement", unit = "pA", digits = 1, edited_color = sct_black),
            "z": LE(tooltip = "most recent tip height measurement", unit = "nm", digits = 2, edited_color = sct_black),
            "z_rel": LE(tooltip = "relative tip height setpoint", value = 1, unit = "nm", digits = 2, edited_color = sct_black, min_width = 70, max_width = 70),
            
            # Feedback
            "I_fb": LE(tooltip = "feedback current", unit = "pA", digits = 0),
            "I_keithley": LE(tooltip = "keithley current", unit = "pA", digits = 0),
            "I_keithley_limit": LE(tooltip = "maximum Keithley current", unit = "pA", digits = 0),

            "p_gain": LE(tooltip = "proportional gain", unit = "pm", digits = 0),
            "t_const": LE(tooltip = "time constant", unit = "us", digits = 0),
            "i_gain": LE(tooltip = "integral gain", unit = "nm/s", digits = 0),
            
            "v_fwd": LE(tooltip = "forward scan speed", unit = "nm/s", digits = 2, min_width = 90),
            "v_bwd": LE(tooltip = "backward scan speed", unit = "nm/s", digits = 2, min_width = 90),
            "v_tip": LE(tooltip = "tip move speed", unit = "nm/s", digits = 2, min_width = 90),
            
            # Frame
            "frame_height": LE(tooltip = "frame height", unit = "nm", limits = [0, 1000], digits = 1, edited_color = scanalyzer_blue),
            "frame_width": LE(tooltip = "frame width", unit = "nm", limits = [0, 1000], digits = 1, edited_color = scanalyzer_blue),
            "frame_x": LE(tooltip = "frame offset (x)", unit = "nm", limits = [-2000, 2000], digits = 1, edited_color = scanalyzer_blue),
            "frame_y": LE(tooltip = "frame offset (y)", unit = "nm", limits = [-2000, 2000], digits = 1, edited_color = scanalyzer_blue),
            "frame_angle": LE(tooltip = "frame angle", unit = "deg", limits = [-180, 360], digits = 1, edited_color = scanalyzer_blue),
            "frame_aspect": LE(tooltip = "frame aspect ratio\n(height / width)", digits = 4, edited_color = scanalyzer_blue),

            # Grid
            "grid_pixels": LE(tooltip = "number of pixels", unit = "px", limits = [1, 10000], digits = 0, edited_color = scanalyzer_blue),
            "grid_lines": LE(tooltip = "number of lines", unit = "px", limits = [1, 10000], digits = 0, edited_color = scanalyzer_blue),
            "grid_aspect": LE(tooltip = "grid aspect ratio\n(lines / pixels)", digits = 4, edited_color = scanalyzer_blue),
            "pixel_width": LE(tooltip = "pixel width", unit = "nm", digits = 4, edited_color = scanalyzer_blue),
            "pixel_height": LE(tooltip = "pixel height", unit = "nm", digits = 4, edited_color = scanalyzer_blue),
            
            # Tip shaper
            "pulse_voltage": LE(value = 6, tooltip = "voltage to apply to the tip when pulsing", unit = "V", limits = [-10, 10], digits = 1, edited_color = sct_black),
            "pulse_duration": LE(value = 300, tooltip = "duration of the voltage pulse", unit = "ms", limits = [0, 5000], digits = 0, edited_color = sct_black),
            
            "poke_voltage": LE(tooltip = "poke voltage\n(bias to apply during poking)", unit = "V", limits = [-10, 10], digits = 2, edited_color = scanalyzer_blue),
            "poke_depth": LE(tooltip = "poke depth\n(height relative to setpoint)", unit = "nm", limits = [-1000, 1000], digits = 2, edited_color = scanalyzer_blue),
            "poke_time": LE(tooltip = "poke time\n(duration of the poke)", unit = "s", limits = [0, 10000], digits = 2, edited_color = scanalyzer_blue),
            
            "lift_voltage": LE(tooltip = "lift voltage\n(bias to apply during lifting)", unit = "V", limits = [-10, 10], digits = 2, edited_color = scanalyzer_blue),
            "lift_height": LE(tooltip = "lift height\n(height relative to setpoint)", unit = "nm", limits = [-1000, 1000], digits = 2, edited_color = scanalyzer_blue),
            "lift_time": LE(tooltip = "lift time\n(duration of the lift)", unit = "s", limits = [0, 10000], digits = 2, edited_color = scanalyzer_blue),
            
            # Processing
            "gaussian_width": LE(value = 0.000, tooltip = "width for Gaussian blur application", unit = "nm", digits = 3, max_width = 70, edited_color = sct_black),
            "graph_buffer_size": LE(value = 4000, tooltip = "graph buffer size", digits = 0, max_width = 70, edited_color = sct_black),
            
            # Lockins
            "nanonis_t": LE(tooltip = "Nanonis time constant (measurement window)", unit = "ms", limits = [0, 10000], digits = 3, min_width = 70),
            "nanonis_df": LE(tooltip = "Nanonis frequency resolution", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            
            "nanonis_mod1_f": LE(tooltip = "Nanonis modulator 1 frequency", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_mod1_amp": LE(tooltip = "Nanonis modulator 1 amplitude", unit = "mV", limits = [0, 5000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_mod1_phase": LE(tooltip = "Nanonis modulator 1 phase", unit = "deg", limits = [-180, 360], digits = 2, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_mod1_n": LE(tooltip = "Nanonis modulator 1 number of oscillations in measurement window", limits = [0, 10000], digits = 2, min_width = 70, max_width = 70,
                                 warning_triggers = [lambda value: (value * 1000) % 1000 != 0]),
            "nanonis_mod2_f": LE(tooltip = "Nanonis modulator 2 frequency", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_mod2_amp": LE(tooltip = "Nanonis modulator 2 amplitude", unit = "mV", limits = [0, 5000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_mod2_phase": LE(tooltip = "Nanonis modulator 2 phase", unit = "deg", limits = [-180, 360], digits = 2, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_mod2_n": LE(tooltip = "Nanonis modulator 2 number of oscillations in measurement window", limits = [0, 10000], digits = 2, min_width = 70, edited_color = scanalyzer_blue, max_width = 70),
            
            # Console
            "input": ILE(tooltip = "Enter a command\n(Enter to evaluate)")
        }
        
        # Reciprocal groups (inter-line-edit update logic)
        self.nanonis_rg = RG(product = 1000, factors = [line_edits["nanonis_t"], line_edits["nanonis_df"]])
        self.frame_rg = RG(product = line_edits["frame_height"], factors = [line_edits["frame_width"], line_edits["frame_aspect"]], lock = "factor1", try_to_retain = "factor0")
        self.grid_rg = RG(product = line_edits["grid_lines"], factors = [line_edits["grid_pixels"], line_edits["grid_aspect"]], lock = "factor1", try_to_retain = "factor0",
                          factor0_constraint = lambda value: int(round(value / 16) * 16))
        
        # Extra line edits
        [line_edits.update({f"demod_frequency_{i}": LE(value = 100 * i, tooltip = f"frequency of tone {i}", unit = "Hz", digits = 2, min_width = 80)}) for i in range(32)]
        [line_edits.update({f"demod_amplitude_{i}": LE(value = 100 * i, tooltip = f"amplitude of tone {i}", unit = "mV", digits = 2, min_width = 80)}) for i in range(32)]
        [line_edits.update({f"experiment_{i}": LE(tooltip = f"Experiment parameter field {i}", digits = 2, edited_color = sct_black)}) for i in range(9)]

        # Named groups
        self.action_line_edits = [line_edits[name] for name in ["z_steps", "h_steps", "minus_z_steps"]]
        
        # Add the button handles to the tooltips
        [line_edits[name].changeToolTip(f"gui.line_edits[\"{name}\"]", line = 10) for name in line_edits.keys()]
        
        # Frame
        [line_edits[f"frame_{key}"].editingFinished.connect(self.update_frame_from_fields) for key in ["x", "y", "width", "height", "angle", "aspect"]]
        return line_edits

    def make_progress_bars(self) -> dict:
        PB = SCTWidgets.ProgressBar
        
        progress_bars = {
            "task": PB(tooltip = "Task progress"),
            "experiment": PB(tooltip = "Experiment progress")
        }
        
        [progress_bars[name].setMinimumWidth(90) for name in progress_bars.keys()]
        [progress_bars[name].setMaximumWidth(90) for name in progress_bars.keys()]
        
        # Add the progress_bar handles to the tooltips
        [progress_bars[name].changeToolTip(f"gui.progress_bars[\"{name}\"]", line = 10) for name in progress_bars.keys()]
        
        return progress_bars

    def make_layouts(self) -> dict:
        layouts = {
            # Main
            "main": make_layout("h"),
            "left_side": make_layout("v"),
            "toolbar": make_layout("g"),
            "empty": make_layout("v"),            
            "input": make_layout("h"),            
            "graph": make_layout("h"),
            "channels": make_layout("g"),
            "connections": make_layout("g"),
            "image_view_controls": make_layout("h"),
            
            "tip": make_layout("v"),
            "tip_deltaz": make_layout("h"),
            
            # Experiment
            "experiment": make_layout("v"),
            "quick_experiments": make_layout("h"),
            "experiment_progress": make_layout("h"),
            "experiment_control": make_layout("h"),
            "experiment_direction": make_layout("h"),
            "experiment_io": make_layout("h"),
            "experiment_fields": make_layout("g"),
            "experiment_buttons": make_layout("h"),
            
            # Parameters; Rename feedback to bias. Rename gains to feedback
            "parameters": make_layout("v"),
            "parameters_0": make_layout("v"),
            "scan_parameter_sets": make_layout("h"),
            
            # Bias            
            "bias": make_layout("g"),
            "bias_getset": make_layout("h"),
            "bias_speeds": make_layout("h"),
            
            # Feedback
            "feedback": make_layout("v"),
            "currents": make_layout("h"),
            "feedback_gains": make_layout("h"),
            "feedback_getset": make_layout("h"),

            # Speeds
            "speeds": make_layout("g"),
            "speeds_getset": make_layout("h"),
            
            # Frame / grid
            "frame_grid": make_layout("g"),
            "frame": make_layout("g"),
            "grid": make_layout("g"),
            "frame_grid_getset": make_layout("h"),
            
            # Coarse / Prep
            "coarse_control": make_layout("h"),
            "coarse_prep": make_layout("v"),
            "coarse_vertical": make_layout("g"),
            "coarse_horizontal": make_layout("g"),
            "approach_percentiles": make_layout("h"),
            "tip_prep": make_layout("g"),
            "shaper_getset": make_layout("h"),
            
            # Scan
            "scan": make_layout("v"),
            "scan_control": make_layout("g"),
            "paste_scan": make_layout("h"),
            "navigation": make_layout("h"),
            "background": make_layout("h"),
            "operations": make_layout("g"),
            "background_buttons": make_layout("h"),
            "limits": make_layout("g"),
                        
            # STS
            "osc": make_layout("v"),
            
            "lockin_parameter_sets": make_layout("h"),
            "modulators": make_layout("g"),
            "mod_set_get": make_layout("h"),
        }
        return layouts

    def make_views(self) -> tuple[SCTWidgets.ImageView, pg.RawImageWidget]:
        pg.setConfigOptions(imageAxisOrder = "row-major", antialias = True)
        
        camera_item = SCTWidgets.ScanItem(name = "camera")
        camera_item.setImage(np.empty((2, 2), dtype = np.float16))
        plot_item = pg.PlotItem()
        plot_item.addItem(camera_item)
        
        image_view = SCTWidgets.ImageView(view = plot_item, imageItem = camera_item)
        image_view.addWidget(self.limits_button)
        
        view = image_view.getView()
        hist_widget = image_view.getHistogramWidget()
        hist_widget.setMaximumWidth(70)
        view.invertY(False) # y increases towards the top of the screen
        self.view = view.getViewBox() # Since view = pg.PlotItem instead of ViewBox, the ViewBox is actually accessed by view.getViewBox()
        self.camera_item = image_view.imageItem
        self.hist_item = hist_widget.item
        
        camera_view = pg.RawImageWidget()
        
        self.saved_items = []
        return (image_view, camera_view)

    def make_image_view_widgets(self) -> tuple[pg.ROI, pg.ROI, pg.ROI]:
        # ROIs (frames)
        piezo_roi = pg.ROI([-50, -50], [100, 100], pen = pg.mkPen(color = self.colors["orange"], width = 2), movable = False, resizable = False, rotatable = False)
        frame_roi = pg.ROI([-50, -50], [100, 100], pen = pg.mkPen(color = self.colors["blue"], width = 2), movable = False, resizable = False, rotatable = False)
        new_frame_roi = pg.ROI([-50, -50], [100, 100], pen = pg.mkPen(color = self.colors["light_blue"], width = 2), movable = True, resizable = True, rotatable = True)
        new_frame_roi.addScaleHandle([1, 0], [0, 1])
        new_frame_roi.addRotateHandle([0.5, 0], [0.5, 0.5])
        new_frame_roi.sigRegionChangeFinished.connect(self.update_fields_from_frame_change)
        
        # Target items
        tip_target = SCTWidgets.TargetItem(pos = [0, 0], size = 10, tip_text = f"tip location\n(0, 0, 0) nm", movable = False)
        target0 = SCTWidgets.TargetItem(pos = [0, 0], size = 10, tip_text = f"target location\n(0, 0, 0) nm", movable = True)
        
        # Path
        path_pdi = pg.PlotDataItem(pen = pg.mkPen(self.colors["orange"], width = 2))
        
        return (piezo_roi, frame_roi, new_frame_roi, tip_target, target0, path_pdi)

    def make_plot_widget(self) -> SCTWidgets.PlotWidget:
        grapher = SCTWidgets.PlotWidget(colors = self.color_list)
        grapher.setVLines(0) # Create axes through the origin
        grapher.setHLines(0)        
        return grapher

    def make_custom_widgets(self) -> dict:
        QWgt = QtWidgets.QWidget
        
        widgets = {
            "central": QWgt(),
            "left_side": QWgt(),
            "coarse_actions": QWgt(),
            "arrows": QWgt(),
            "graph": QWgt(),
            "sts": QWgt(),

            "connections": QWgt(),
            "coarse_control": QWgt(),
            "coarse_prep": QWgt(),
            "frame_grid": QWgt(),
            "tip_prep": QWgt(),
            "parameters": QWgt(),
            "scan": QWgt(),
            "experiment": QWgt(),
            "lockins": QWgt(),
            "osc": QWgt(),
            "image_view_controls": QWgt(),
            "toolbar": QWgt()
        }
               
        self.current_height_widget = CurrentHeightIndicatorWidget(feedback_button = self.buttons["tip"], current_le = self.line_edits["I"], height_le = self.line_edits["z"],
                                                                  fill_color = self.colors["blue"], background_color = self.colors["dark_gray"], warning_color = self.colors["orange"])
        
        sivr = "Set the image value range "
        self.limits_widget = MinMaxMethods()

        self.limits_widget.addMethod("full", 0, 1, digits = 4, unit = "nm", icon = self.icons.get("100"), tooltip = sivr + "to the full data range")
        self.limits_widget.addMethod("percentiles", 1, 99, digits = 1, limits = [0, 100], unit = "%", icon = self.icons.get("percentiles"), tooltip = sivr + "by percentiles")
        self.limits_widget.addMethod("deviations", 2, 2, digits = 1, limits = [0, 100], unit = "\u03C3", icon = self.icons.get("deviation"), tooltip = sivr + "by standard deviations")
        self.limits_widget.addMethod("absolute", 0, 1, digits = 4, limits = [-10000, 10000], unit = "nm", icon = self.icons.get("numbers"), tooltip = sivr + "by absolute values")
        return widgets

    def make_consoles(self) -> dict:
        consoles = {
            "output": SCTWidgets.Console(tooltip = "Output console"),
            "input": SCTWidgets.Console(tooltip = "Input console")
        }
        
        consoles["output"].setReadOnly(True)
        consoles["input"].setReadOnly(False)
        consoles["input"].setMaximumHeight(30)
        [consoles[name].setStyleSheet("QTextEdit{ background-color: #101010; }") for name in ["output", "input"]]
        consoles["output"].setMinimumHeight(150)
        
        # Add the handles to the tooltips
        [consoles[name].changeToolTip(f"gui.consoles[\"{name}\"]", line = 10) for name in consoles.keys()]
        
        return consoles

    def make_sliders(self) -> dict:
        PS = SCTWidgets.PhaseSlider
        sliders = {"phase": PS(tooltip = "Set complex phase phi\n(= multiplication by exp(i * pi * phi rad / (180 deg)))", unit = "deg", phase_0_icon = self.icons.get("0"), phase_180_icon = self.icons.get("180"))}
        return sliders

    def make_shortcuts(self) -> dict:
        QKey = QtCore.Qt.Key
        QMod = QtCore.Qt.Modifier
        QSeq = QtGui.QKeySequence
        
        shortcuts = {
            "scanalyzer": QSeq(QKey.Key_S),
            "nanonis": QSeq(QMod.CTRL | QKey.Key_C),
            "oscillator": QSeq(QKey.Key_O),
            "view": QSeq(QKey.Key_V),
            "exit": QSeq(QKey.Key_Escape),
            
            "withdraw": QSeq(QMod.CTRL | QKey.Key_W),
            "retract": QSeq(QMod.CTRL | QKey.Key_PageUp),
            "advance": QSeq(QMod.CTRL | QKey.Key_PageDown),
            "approach": QSeq(QMod.CTRL | QKey.Key_A),
            
            "tip": QSeq(QMod.CTRL | QKey.Key_Space),
            "set": QSeq(QMod.CTRL | QKey.Key_P),
            "get": QSeq(QKey.Key_P),
            "scan_parameters_0": QSeq(QMod.CTRL | QKey.Key_0),
            "scan_parameters_1": QSeq(QMod.CTRL | QKey.Key_1),
            "scan_parameters_2": QSeq(QMod.CTRL | QKey.Key_2),
            "scan_parameters_3": QSeq(QMod.CTRL | QKey.Key_3),            
            
            "direction": QSeq(QKey.Key_X),            
            "full_data_range": QSeq(QMod.SHIFT | QKey.Key_U),
            "percentiles": QSeq(QMod.SHIFT | QKey.Key_R),
            "standard_deviation": QSeq(QMod.SHIFT | QKey.Key_D),
            "absolute_values": QSeq(QMod.SHIFT | QKey.Key_A)
        }
        
        # Add keys for moving in directions
        direction_keys = {"n": QKey.Key_Up, "e": QKey.Key_Right, "s": QKey.Key_Down, "w": QKey.Key_Left}
        [shortcuts.update({direction: QSeq(QMod.CTRL | keystroke)}) for direction, keystroke in direction_keys.items()]
        
        return shortcuts

    def make_dialogs(self) -> dict:
        dialogs = {
            "parameters": QtWidgets.QInputDialog(),
            "info": QtWidgets.QInputDialog(),
            "open_file": QtWidgets.QFileDialog(),
            "limits": QtWidgets.QDialog()
                   }
        
        dialogs["limits"].setLayout(self.layouts["limits"])
        dialogs["limits"].setWindowTitle("limits")
        dialogs["limits"].setWindowIcon(self.icons["deviation"])
        return dialogs

    def make_boxes(self) -> tuple[QtWidgets.QMessageBox, QtWidgets.QMessageBox]:
        info_box = QtWidgets.QMessageBox(self)
        info_box.setWindowTitle("Info")
        info_box.setText("Scantelligent (2026)\nby Peter H. Jacobse\nRice University; Lawrence Berkeley National Lab")
        info_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        info_box.setWindowIcon(self.icons.get("i"))
        
        message_box = QtWidgets.QMessageBox(self)
        message_box.setWindowTitle("Success")
        message_box.setText("png file saved")
        return (info_box, message_box)



    # 3: Populate layouts with GUI items. Requires GUI items.
    def populate_layouts(self) -> None:
        layouts = self.layouts
        align_center = QtCore.Qt.AlignmentFlag.AlignCenter
        buttons = self.buttons
        line_edits = self.line_edits
        labels = self.labels
        comboboxes = self.comboboxes
        
        # Graphing
        layouts["channels"].addWidget(line_edits["graph_buffer_size"], 1, 0, 1, 5)
        [layouts["channels"].addWidget(self.checkboxes[f"channel_{i}"], 2 + i % 7, int(i / 7)) for i in range(35)]
        layouts["channels"].addWidget(comboboxes["graph_x_axis"], 9, 0, 1, 5)
        layouts["channels"].setRowStretch(0, 1)
        
        layouts["graph"].addWidget(self.grapher, 5)
        layouts["graph"].addLayout(layouts["channels"], 1)
        self.widgets["graph"].setLayout(layouts["graph"])
        
        # Toolbar
        # Connections
        layouts["connections"].addWidget(buttons["view"], 0, 0, 2, 1)
        [layouts["connections"].addWidget(buttons[name], 0, index + 1) for index, name in enumerate(["nanonis", "camera", "mla", "keithley"])]
        [layouts["connections"].addWidget(buttons[name], 1, index + 1) for index, name in enumerate(["scanalyzer", "session_folder", "info", "spectelligent"])]
        layouts["connections"].addWidget(buttons["exit"], 0, 5, 2, 1)
        layouts["connections"].addWidget(self.current_height_widget, 2, 0, 1, 2)

        # Tip
        [layouts["tip_deltaz"].addWidget(self.buttons[name]) for name in ["withdraw_2", "set_dz"]]
        layouts["tip"].addLayout(layouts["tip_deltaz"])
        layouts["tip"].addWidget(self.line_edits["z_rel"], QtCore.Qt.AlignmentFlag.AlignHCenter)
        layouts["tip"].addWidget(self.current_height_widget,)

        # Experiment
        e_layout = layouts["experiment"]
        [layouts["experiment_progress"].addWidget(self.progress_bars[name]) for name in ["task", "experiment"]]
        e_layout.addLayout(layouts["experiment_progress"])
        
        [layouts["experiment_io"].addWidget(widget) for widget in [line_edits["experiment_filename"], buttons["save"]]]
        e_layout.addLayout(layouts["experiment_io"])
        
        e_layout.addWidget(labels["quick_experiment"])
        e_layout.addWidget(make_line("h", 1))
        [layouts["quick_experiments"].addWidget(self.buttons[name]) for name in ["start_scan", "spectelligent_2", "approach_2"]]
        e_layout.addLayout(layouts["quick_experiments"])
        
        e_layout.addWidget(labels["custom_experiment"])
        e_layout.addWidget(make_line("h", 1))        
        [layouts["experiment_control"].addWidget(widget) for widget in [comboboxes["experiment"], buttons["start_stop"]]]
        e_layout.addLayout(layouts["experiment_control"])
        
        e_layout.addWidget(labels["experiment_settings"])
        e_layout.addWidget(make_line("h", 1))        
        [layouts["experiment_direction"].addWidget(widget) for widget in [buttons["scan_direction"], comboboxes["direction"]]]
        e_layout.addLayout(layouts["experiment_direction"])
        
        [layouts["experiment_fields"].addWidget(widget, int(index / 3), index % 3) for index, widget in enumerate([line_edits[f"experiment_{i}"] for i in range(3)])] # Grid of experiment fields
        [layouts["experiment_buttons"].addWidget(buttons[f"experiment_{i}"]) for i in range(6)] # Grid of experiment buttons

        e_layout.addLayout(layouts["experiment_fields"])
        e_layout.addLayout(layouts["experiment_buttons"])
        
        # Coarse
        [layouts["approach_percentiles"].addWidget(line_edits[f"approach_{name}_percentile"]) for name in ["min", "max"]]

        ch_layout = layouts["coarse_horizontal"]
        ch_layout.addWidget(line_edits["V_hor"], 0, 0, 1, 3, alignment = align_center)
        ch_layout.addWidget(line_edits["f_motor"], 1, 0, 1, 3, alignment = align_center)
        ch_layout.addWidget(line_edits["h_steps"], 2, 0, 1, 3, alignment = align_center)
        [ch_layout.addWidget(button, 3 + int(i / 3), i % 3) for i, button in enumerate(self.arrow_buttons)]
        ch_layout.addWidget(buttons["composite_motion"], 6, 0, 1, 3, alignment = align_center)
        ch_layout.setRowStretch(ch_layout.rowCount(), 1)

        cv_layout = layouts["coarse_vertical"]
        cv_layout.addWidget(line_edits["V_ver"], 0, 0, 1, 3, alignment = align_center)
        cv_layout.addWidget(line_edits["f_motor"], 1, 0, 1, 3, alignment = align_center)
        [cv_layout.addWidget(checkbox, 2 + i + int(i / 2), 0) for i, checkbox in enumerate(self.action_checkboxes)]
        [cv_layout.addWidget(button, 2 + i + int(i / 2), 2) for i, button in enumerate(self.action_buttons)]
        cv_layout.addWidget(line_edits["z_steps"], 3, 1)
        cv_layout.addWidget(labels["move_horizontally"], 4, 0, 1, 3)
        cv_layout.addWidget(line_edits["minus_z_steps"], 5, 1)
        cv_layout.addWidget(comboboxes["approach_fb_parameters"], 7, 0, 1, 3)
        cv_layout.addLayout(layouts["approach_percentiles"], 8, 0, 1, 3, alignment = align_center)
        cv_layout.setRowStretch(cv_layout.rowCount(), 1)


        
        # Bias
        [layouts["bias_getset"].addWidget(buttons[f"{key}_bias_parameters"]) for key in ["get", "set", "get_mla", "set_mla", "get_keithley", "set_keithley"]]
        b_layout = layouts["bias"]
        b_layout.addWidget(labels["nanonis"])
        [b_layout.addWidget(labels[name], 0, index + 2) for index, name in enumerate(["mla", "keithley"])]
        b_layout.addWidget(make_line("h", 1), 1, 0, 1, 4)
        
        
        [b_layout.addWidget(widget, 2, index) for index, widget in enumerate([line_edits["V_nanonis"], buttons["voltage_lock"], line_edits["V_mla_port1"], line_edits["V_keithley"]])]
        b_layout.addWidget(line_edits["V_mla_port2"], 3, 2)
        [b_layout.addWidget(line_edits[name], 4 + index, 0) for index, name in enumerate(["dV_nanonis", "dt_nanonis"])]
        b_layout.addWidget(line_edits["dz_nanonis"], 5, 2)
        [b_layout.addWidget(line_edits[name], 4 + index, 3) for index, name in enumerate(["dV_keithley", "dt_keithley"])]
        b_layout.addLayout(layouts["bias_getset"], 6, 0, 1, 4)
        
        # Feedback
        [layouts["currents"].addWidget(line_edits[name]) for name in ["I_fb", "I_keithley_limit"]]
        [layouts["feedback_gains"].addWidget(line_edits[name]) for name in ["p_gain", "t_const", "i_gain"]]
        layouts["feedback_gains"].addWidget(comboboxes["tia_gain"])
        [layouts["feedback_getset"].addWidget(widget) for widget in [buttons["get_feedback_parameters"], buttons["set_feedback_parameters"], comboboxes["feedback"]]]
        
        layouts["feedback"].addLayout(layouts["currents"])
        layouts["feedback"].addLayout(layouts["feedback_gains"])
        layouts["feedback"].addLayout(layouts["feedback_getset"])

        # Speeds
        [layouts["speeds_getset"].addWidget(widget) for widget in [buttons["get_speed_parameters"], buttons["set_speed_parameters"]]]
        #layouts["speeds"].addWidget(labels["forward"])
        #[layouts["speeds"].addWidget(labels[name], 0, index + 2) for index, name in enumerate(["backward", "tip"])]
        #[layouts["speeds"].addWidget(make_line("h", 1), 1, index) for index in range(4)]
        #[layouts["speeds"].addWidget(widget, 2, index) for index, widget in enumerate([line_edits["v_fwd"], buttons["speed_lock"], line_edits["v_bwd"], line_edits["v_tip"]])]
        for index, name in enumerate(["v_fwd", "v_bwd", "v_tip"]):
            layouts["speeds"].addWidget(buttons[name], index, 0)
            layouts["speeds"].addWidget(line_edits[name], index, 1)
        layouts["speeds"].addLayout(layouts["speeds_getset"], 3, 0, 1, 2)


        
        # Frame_grid
        [layouts["frame_grid_getset"].addWidget(widget) for widget in [buttons["get_grid_parameters"], buttons["set_grid_parameters"], comboboxes["frame_grid"]]]        
        fg_layout = layouts["frame_grid"]
        fg_layout.addWidget(labels["frame"], 0, 0, 1, 2)
        fg_layout.addWidget(make_line("h", 1), 1, 0, 1, 2)
        fg_layout.addWidget(buttons["frame_aspect"], 2, 0, 1, 1, align_center)
        fg_layout.addWidget(line_edits["frame_height"], 2, 1)
        [fg_layout.addWidget(line_edits[name], 3 + int(index / 2), index % 2) for index, name in enumerate(["frame_width", "frame_aspect", "frame_x", "frame_y"])]
        fg_layout.addWidget(line_edits["frame_angle"], 5, 0, 1, 2)
        fg_layout.addWidget(labels["empty"], 0, 2)
        
        fg_layout.addWidget(labels["grid"], 0, 3, 1, 2)
        fg_layout.addWidget(make_line("h", 1), 1, 3, 1, 2)
        fg_layout.addWidget(buttons["grid_aspect"], 2, 3, 1, 1, align_center)
        fg_layout.addWidget(line_edits["grid_lines"], 2, 4)
        [fg_layout.addWidget(line_edits[name], 3 + int(index / 2), 3 + index % 2) for index, name in enumerate(["grid_pixels", "grid_aspect", "pixel_width", "pixel_height"])]
        fg_layout.addLayout(layouts["frame_grid_getset"], 6, 0, 1, 5)
        
        # Tip prep
        [layouts["shaper_getset"].addWidget(buttons[f"{letter}et_tip_shaper_parameters"]) for letter in ["g", "s"]]
        tp_layout = layouts["tip_prep"]
        [tp_layout.addWidget(widget, index, 0, 1, 2) for index, widget in enumerate([labels["pulse"], make_line("h", 1)])]
        [tp_layout.addWidget(widget, index, 2, 1, 3) for index, widget in enumerate([labels["shape"], make_line("h", 1)])]
        
        tp_layout.addWidget(buttons["bias_pulse"], 3, 0, 3, 1, align_center)
        tp_layout.addWidget(buttons["tip_shape"], 3, 4, 3, 1, align_center)
        
        [tp_layout.addWidget(line_edits[name], 4 + index, 1) for index, name in enumerate(["pulse_voltage", "pulse_duration"])]
        [tp_layout.addWidget(line_edits[name], 3 + index, 2) for index, name in enumerate(["poke_depth", "poke_voltage", "poke_time"])]
        [tp_layout.addWidget(line_edits[name], 3 + index, 3) for index, name in enumerate(["lift_height", "lift_voltage", "lift_time"])]
        tp_layout.addLayout(layouts["shaper_getset"], 6, 2, 1, 3)
        
        # Modulators
        [layouts["mod_set_get"].addWidget(buttons[name]) for name in ["get_lockin_parameters", "set_lockin_parameters"]]

        [layouts["modulators"].addWidget(line_edits[f"nanonis_{quantity}"], 0, 2 * index, 1, 2) for index, quantity in enumerate(["t", "df"])]
        [layouts["modulators"].addWidget(buttons[f"nanonis_mod{index + 1}"], 1 + 2 * index, 0, 2, 1) for index in range(2)]
        [[layouts["modulators"].addWidget(line_edits[f"nanonis_mod{number + 1}_{quantity}"], 1 + 2 * number, 1 + index) for index, quantity in enumerate(["n", "f", "phase"])] for number in range(2)]
        [[layouts["modulators"].addWidget(widget, 2 + 2 * number, 1 + index, 1, 1 + index) for index, widget in enumerate([line_edits[f"nanonis_mod{number + 1}_amp"], comboboxes[f"nanonis_mod{number + 1}"]])] for number in range(2)]

        layouts["limits"].addWidget(self.limits_widget)
        
        # Image_view
        layouts["image_view_controls"].addWidget(buttons["auto_paste"])
        
        #[layouts["navigation"].addWidget(comboboxes[name], 2 + 2 * index) for index, name in enumerate(["axis", "slice"])]
        layouts["navigation"].addWidget(self.comboboxes["scan_items"])
        layouts["navigation"].addWidget(self.buttons["slice"])
        layouts["navigation"].addWidget(self.comboboxes["slice"])
        [layouts["navigation"].addWidget(self.buttons[name], 1) for name in ["direction", "fit_to_frame", "fit_to_range", "frame", "path"]]        
        layouts["image_view_controls"].addLayout(layouts["navigation"])
        
        [layouts["background_buttons"].addWidget(buttons[f"bg_{method}"]) for method in ["none", "plane", "linewise"]]
        layouts["image_view_controls"].addLayout(layouts["background_buttons"])
        
        #layouts["background_buttons"].addWidget(buttons["rot_trans"])
        o_layout = layouts["operations"]
        [o_layout.addWidget(buttons[name], 0, index) for index, name in enumerate(["sobel", "normal", "laplace", "fft", "gaussian"])]
        o_layout.addWidget(line_edits["gaussian_width"], 0, 5)
        o_layout.addWidget(comboboxes["projection"], 0, 6)
        o_layout.addWidget(self.sliders["phase"], 0, 7)
        layouts["image_view_controls"].addLayout(o_layout)
        
        # Input console
        layouts["input"].addWidget(self.consoles["input"])
        return



    # 4: Make widgets and groupboxes and set their layouts. Requires layouts.
    def make_groupboxes(self) -> dict:
        SGB = SCTWidgets.GroupBox
        layouts = self.layouts
        
        groupboxes = {
            # Connections
            "connections": SGB(title = "connections", tooltip = "connections to hardware (push to check/refresh)", checkable = True),            
            "tip": SGB(title = "tip", tooltip = "tip status and current", checkable = True),
            
            # Coarse
            "coarse_vertical": SGB(title = "vertical", tooltip = "vertical coarse motion", checkable = True),
            "coarse_horizontal": SGB(title = "horizontal", tooltip = "horizontal coarse motion", checkable = True),
            
            "tip_prep": SGB(title = "tip prep", tooltip = "tip preparation tools", checkable = True),
            "modulators": SGB(title = "modulators", tooltip = "modulators", checkable = True),

            "frame_grid": SGB(title = "frame / grid", tooltip = "frame and grid parameters", checkable = True),
            "bias": SGB(title = "bias", tooltip = "bias and ramp parameters", checkable = True),
            "feedback": SGB(title = "feedback", tooltip = "feedback and gains", checkable = True),
            "speeds": SGB(title = "speeds", tooltip = "speeds", checkable = True),
            "experiment": SGB(title = "experiments", tooltip = "Perform experiments", checkable = True)
        }

        # Set layouts for the groupboxes
        #groupbox_names = ["connections", "coarse_horizontal", "coarse_vertical", "bias", "feedback", "speeds", "frame_grid", "tip_prep", "spectroscopy", "modulators", "demodulators", "experiment", "limits"]
        #[layouts[name].setContentsMargins(2, 0, 2, 0) for name in groupboxes.keys()]
        [groupboxes[name].setLayout(layouts[name]) for name in groupboxes.keys()]

        # Make layouts of several groupboxes
        [layouts["coarse_control"].addWidget(groupboxes[name], 1) for name in ["coarse_horizontal", "coarse_vertical"]]
        #layouts["coarse_prep"].addLayout(layouts["coarse_control"])
        #layouts["coarse_prep"].addWidget(groupboxes["tip_prep"])        
        [layouts[name].addStretch(1) for name in ["parameters", "osc", "coarse_prep", "tip"]]
        return groupboxes



    # 5: Set up the main window layout
    def setup_main_window(self) -> None:
        layouts = self.layouts
        widgets = self.widgets
        groupboxes = self.groupboxes

        # Aesthetics
        layouts["left_side"].setContentsMargins(0, 0, 0, 0)
        layouts["toolbar"].setContentsMargins(2, 2, 2, 2)
        
        # Create the toolbar        
        layouts["toolbar"].addWidget(groupboxes["connections"], 0, 0, 1, 2)
        layouts["toolbar"].addWidget(groupboxes["tip"], 1, 0)
        layouts["toolbar"].addWidget(groupboxes["experiment"], 1, 1)
        [layouts["bias_speeds"].addWidget(groupboxes[name]) for name in ["bias", "speeds"]]
        layouts["toolbar"].addLayout(layouts["bias_speeds"], 2, 0, 1, 2)
        [layouts["toolbar"].addWidget(groupboxes[name], 3 + index, 0, 1, 2) for index, name in enumerate(["feedback", "frame_grid"])]
        layouts["toolbar"].addLayout(layouts["coarse_control"], 5, 0, 1, 2)
        layouts["toolbar"].addWidget(groupboxes["tip_prep"], 6, 0, 1, 2)
        layouts["toolbar"].addWidget(groupboxes["modulators"], 7, 0, 1, 2)
        layouts["toolbar"].setRowStretch(8, 1)
        layouts["toolbar"].setColumnStretch(2, 1)
        widgets["toolbar"].setLayout(layouts["toolbar"])
        
        self.tool_scroller = QtWidgets.QScrollArea()
        self.tool_scroller.setContentsMargins(0, 0, 0, 0)
        self.tool_scroller.setWidgetResizable(True)
        self.tool_scroller.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.tool_scroller.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.tool_scroller.setWidget(widgets["toolbar"])
        
        # Compose the image_view plus consoles layout
        self.splitters = {"image_graph": QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical), "camera_nanonis": QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)}
        self.splitters["image_graph"].addWidget(self.image_view)
        self.splitters["image_graph"].addWidget(widgets["graph"])
        self.splitters["image_graph"].addWidget(self.consoles["output"])
        self.splitters["image_graph"].setStretchFactor(0, 4)
        self.splitters["image_graph"].setStretchFactor(1, 1)
        self.splitters["image_graph"].setStretchFactor(2, 1)
        
        layouts["left_side"].addLayout(layouts["image_view_controls"])
        layouts["left_side"].addWidget(self.splitters["image_graph"])
        #layouts["left_side"].addWidget(widgets["graph"], stretch = 1)
        #layouts["left_side"].addWidget(self.consoles["output"], stretch = 1)
        layouts["left_side"].addWidget(self.line_edits["input"])
        self.widgets["left_side"].setLayout(layouts["left_side"])
        
        # Attach the toolbar
        layouts["main"].addWidget(self.widgets["left_side"], stretch = 3)
        layouts["main"].addWidget(self.tool_scroller, 1)
        
        # Set the central widget of the QMainWindow
        widgets["central"].setLayout(layouts["main"])
        widgets["central"].setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        widgets["central"].setFocus()
        
        # Finish the setup
        self.setCentralWidget(widgets["central"])
        self.setWindowTitle("Scantelligent")
        self.setGeometry(100, 50, 1400, 800) # x, y, width, height
        self.setWindowIcon(self.icons.get("scanalyzer"))
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.activateWindow()
        return



    # 6: Interconnect interdependent widgets
    def update_lock(self, name: str = "frame") -> None:
        if bool(self.buttons[f"{name}_aspect"].state_index): self.frame_rg.setLock("factor1") # Lock the aspect ratio
        else: self.frame_rg.setLock("factor0") # Lock the width
        return

    def limit_roi_angle(self) -> None:
        angle = self.new_frame_roi.angle()
        new_angle = (angle + 180) % 360 - 180

        self.new_frame_roi.blockSignals(True)
        self.new_frame_roi.setAngle(new_angle)
        self.new_frame_roi.blockSignals(False)
        return

    def update_fields_from_frame_change(self) -> None:
        [self.line_edits[name].blockSignals(True) for name in ["frame_x", "frame_y", "frame_width", "frame_height", "frame_angle"]]
        
        self.limit_roi_angle()
        
        new_width = self.new_frame_roi.size().x()
        self.line_edits["frame_width"].setValue(new_width, edited_color = False)
        
        if bool(self.buttons["frame_aspect"].state_index):
            new_height = new_width * self.line_edits["frame_aspect"].getValue()
            
            self.new_frame_roi.blockSignals(True)
            self.new_frame_roi.setSize([new_width, new_height])
            self.new_frame_roi.blockSignals(False)
        else:
            new_height = self.new_frame_roi.size().y()
            self.line_edits["frame_aspect"].setValue(new_height / new_width, edited_color = False)
        
        self.line_edits["frame_height"].setValue(new_height, edited_color = False)
                
        bounding_rect = self.new_frame_roi.boundingRect()
        local_center = bounding_rect.center()
        abs_center = self.new_frame_roi.mapToParent(local_center)
        
        self.line_edits["frame_x"].setValue(abs_center.x(), edited_color = False)
        self.line_edits["frame_y"].setValue(abs_center.y(), edited_color = False)
        
        self.line_edits["frame_angle"].setValue(-self.new_frame_roi.angle(), edited_color = False)
        
        [self.line_edits[name].blockSignals(False) for name in ["frame_x", "frame_y", "frame_width", "frame_height", "frame_angle"]]
        return

    def update_frame_from_fields(self) -> None:
        self.new_frame_roi.blockSignals(True)
        
        [new_width, new_height, new_angle, new_x, new_y] = [self.line_edits[f"frame_{key}"].getValue() for key in ["width", "height", "angle", "x", "y"]]

        self.new_frame_roi.setPos([0, 0])
        self.new_frame_roi.setSize([new_width, new_height])
        self.new_frame_roi.setAngle(-new_angle)
        
        bounding_rect = self.new_frame_roi.boundingRect()
        local_center = bounding_rect.center()
        abs_center = self.new_frame_roi.mapToParent(local_center)

        self.new_frame_roi.setPos(new_x - abs_center.x(), new_y - abs_center.y())
        self.new_frame_roi.blockSignals(False)
        return

