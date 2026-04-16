import os, sys
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
from . import STWidgets, rotate_icon, make_layout, make_line



class ScantelligentGUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.color_list = ["#FFFFFF", "#FFFF20", "#20FFFF", "#FF80FF", "#60FF60", "#FF6060", "#8080FF", "#B0B0B0", "#FFB010", "#A050FF",
                           "#909020", "#00A0A0", "#B030A0", "#40B040", "#B04040", "#5050E0", "#c00000", "#905020", "#707000", "#2020ff"]
        self.colors = {"red": "#ff5050", "dark_red": "#800000", "green": "#00ff00", "dark_green": "#005000", "light_blue": "#30d0ff",
                  "white": "#ffffff", "blue": "#2090ff", "orange": "#FFA000","dark_orange": "#A05000", "black": "#000000", "purple": "#700080"}
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
        (self.checkboxes, self.channel_checkboxes) = self.make_checkboxes()
        self.comboboxes = self.make_comboboxes()
        self.line_edits = self.make_line_edits()
        self.radio_buttons = self.make_radio_buttons()
        self.progress_bars = self.make_progress_bars()
        self.layouts = self.make_layouts()
        self.image_view = self.make_image_view()
        (self.piezo_roi, self.frame_roi, self.new_frame_roi) = self.make_rois()
        (self.plot_widget, self.graphs) = self.make_plot_widget()
        self.widgets = self.make_widgets()
        self.consoles = self.make_consoles()
        self.tip_slider = self.make_tip_slider()
        self.demod_audio_sliders = self.make_demod_audio_sliders()
        self.shortcuts = self.make_shortcuts()
        self.dialogs = self.make_dialogs()
        (self.info_box, self.message_box) = self.make_boxes()
                
        # 3: Populate layouts with GUI items. Requires GUI items.
        self.populate_layouts()
        
        # 4: Make groupboxes and set their layouts. Requires populated layouts.
        self.groupboxes = self.make_groupboxes()
        
        # 5: Make the tab widget
        self.tab_widget = self.make_tab_widget()
        
        # 5: Set up the main window layout
        self.setup_main_window()

        # 6: Interconnect mutually interdependent signals and slots
        self.interconnect()



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
        LB = STWidgets.Label
        
        labels = {
            "session_folder": LB("Session folder"),
            "statistics": LB("Statistics"),
            "load_file": LB("Load file:"),
            "in_folder": LB("in folder:"),
            "number_of_files": LB("which contains 1 sxm file"),
            "channel_selected": LB("Channel selected:"),

            "frame": LB("frame"),
            "grid": LB("grid"),

            "scan_control": LB("Scan channel / direction"),
            "background_subtraction": LB("Background subtraction"),
            "width": LB("Width (nm):"),
            "show": LB("Show", "Select a projection or toggle with (H)"),
            "limits": LB("Set limits", "Toggle the min and max limits with (-) and (=), respectively"),
            "matrix_operations": LB("Matrix operations"),

            "z_steps": LB("steps"),
            "move_horizontally": LB("< horizontal motion >", "In composite motion, horizontal motion\nis carried out between retract and advance\nSee 'horizontal'"),
            "h_steps": LB("steps in direction"),
            "steps_and": LB("steps, and")
        }
        
        # Named groups
        self.steps_labels = [labels[name] for name in ["z_steps", "h_steps", "steps_and"]]
        
        return labels
    
    def make_buttons(self) -> dict:
        MSB = STWidgets.MultiStateButton
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
                                     {"name": "running", "color": self.colors["blue"], "tooltip": "Nanonis: running"}]),
            "mla": MSB(icon = icons.get("imp"), click_to_toggle = False,
                       states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Multifrequency Lockin Amplifier: offline"},
                                 {"name": "online", "color": self.colors["dark_green"], "tooltip": "Multifrequency Lockin Amplifier: online (idle)"},
                                 {"name": "idle", "color": self.colors["dark_green"], "tooltip": "Multifrequency Lockin Amplifier: online (idle)"},
                                 {"name": "running", "color": self.colors["blue"], "tooltip": "Multifrequency Lockin Amplifier: running"}]),
            "keithley": MSB(icon = icons.get("keithley"), click_to_toggle = False,
                            states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Keithley source meter: offline"},
                                      {"name": "online", "color": self.colors["dark_green"], "tooltip": "Keithley source meter: online (idle)"},
                                      {"name": "idle", "color": self.colors["dark_green"], "tooltip": "Keithley source meter: online (idle)"},
                                      {"name": "running", "color": self.colors["blue"], "tooltip": "Keithley source meter: running"}]),
            "camera": MSB(icon = icons.get("camera"), click_to_toggle = False,
                          states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Camera: offline"},
                                    {"name": "online", "color": self.colors["dark_green"], "tooltip": "Camera: online (idle)"},
                                    {"name": "idle", "color": self.colors["dark_green"], "tooltip": "Camera: online (idle)"},
                                    {"name": "running", "color": self.colors["blue"], "tooltip": "Camera: running"}]),
            "view": MSB(click_to_toggle = True, size = 28,
                        states = [{"name": "None", "tooltip": "Toggle the active view", "icon": icons.get("eye")},
                                  {"name": "Camera", "tooltip": "Active view: Camera", "icon": icons.get("camera")},
                                  {"name": "Nanonis", "tooltip": "Active view: Nanonis", "icon": icons.get("nanonis")}]),
            "exit": MSB(tooltip = "Exit scantelligent\n(Esc / X / E)", icon = icons.get("escape"), size = 28),
            "session_folder": MSB(icon = icons.get("folder_yellow"), click_to_toggle = False,
                                  states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Session folder unknown"},
                                            {"name": "online", "color": self.colors["dark_green"], "tooltip": "Open the session folder"}]),
            "info": MSB(tooltip = "Info", icon = self.icons.get("i")),
            
            # Experiment
            "save": MSB(tooltip = "Save the experiment results to file", icon = icons.get("floppy")),
            "start_pause": MSB(icon = icons.get("start"), click_to_toggle = False, size = 28,
                               states = [{"name": "load", "color": self.colors["dark_red"], "tooltip": "Load experiment"},
                                         {"name": "ready", "color": self.colors["dark_green"], "tooltip": "Start experiment"},
                                         {"name": "running", "color": self.colors["blue"], "tooltip": "Experiment running"}]),
            "stop": MSB(tooltip = "Stop experiment", icon = icons.get("stop"), size = 28),
            
            # Parameters
            "frame_aspect": MSB(tooltip = "Lock the frame aspect ratio", icon = icons.get("lock_aspect"), states = [{"color": "#101010"}, {"color": "#2020C0"}]),
            "grid_aspect": MSB(tooltip = "Lock the grid aspect ratio", icon = icons.get("lock_aspect"), states = [{"color": "#101010"}, {"color": "#2020C0"}]),
            
            "tip": MSB(tooltip = "Tip status\n(Ctrl + Space to toggle feedback)", icon = icons.get("withdrawn")),
            "V_swap": MSB(tooltip = "Swap the bias between Nanonis and the MLA", icon = icons.get("swap")),
            
            # Parameters: getters and setters
            "set_scan_parameters": MSB(tooltip = "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_scan_parameters": MSB(tooltip = "Get parameters\n(P)", icon = icons.get("get")),
            "set_coarse_parameters": MSB(tooltip = "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_coarse_parameters": MSB(tooltip = "Get parameters\n(P)", icon = icons.get("get")),
            "set_gain_parameters": MSB(tooltip = "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_gain_parameters": MSB(tooltip = "Get parameters\n(P)", icon = icons.get("get")),
            "set_speed_parameters": MSB(tooltip = "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_speed_parameters": MSB(tooltip = "Get parameters\n(P)", icon = icons.get("get")),
            "set_frame_parameters": MSB(tooltip = "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_frame_parameters": MSB(tooltip = "Get parameters\n(P)", icon = icons.get("get")),
            "set_grid_parameters": MSB(tooltip = "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_grid_parameters": MSB(tooltip = "Get parameters\n(P)", icon = icons.get("get")),
            "set_lockin_parameters": MSB(tooltip = "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_lockin_parameters": MSB(tooltip = "Get parameters\n(P)", icon = icons.get("get")),
            
            # Coarse vertical
            "withdraw": MSB(tooltip = "Withdraw the tip\n(Ctrl + W)", icon = icons.get("withdraw")),
            "retract": MSB(tooltip = "Retract the tip from the surface\n(Ctrl + PgUp)", icon = icons.get("retract")),
            "advance": MSB(tooltip = "Advance the tip towards the surface\n(Ctrl + PgDown)", icon = icons.get("advance")),
            "approach": MSB(tooltip = "Initiate auto approach\n(Ctrl + A)", icon = icons.get("approach")),
            "set_coarse": MSB(tooltip = "Set the new coarse parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_coarse": MSB(tooltip = "Get the coarse parameters\n(P)", icon = icons.get("get")),

            # Coarse horizontal
            "n": MSB(tooltip = mtt + "north\n(Ctrl + ↑ / Ctrl + 8)", icon = rotate_icon(arrow, angle = 270)),
            "ne": MSB(tooltip = mtt + "northeast\n(Ctrl + 9)", icon = rotate_icon(arrow45, angle = 0)),
            "e": MSB(tooltip = mtt + "east\n(Ctrl + → / Ctrl + 6)", icon = rotate_icon(arrow, angle = 0)),
            "se": MSB(tooltip = mtt + "southeast\n(Ctrl + 3)", icon = rotate_icon(arrow45, angle = 90)),
            "s": MSB(tooltip = mtt + "south\n(Ctrl + ↓ / Ctrl + 2)", icon = rotate_icon(arrow, angle = 90)),
            "sw": MSB(tooltip = mtt + "southwest\n(Ctrl + 1)", icon = rotate_icon(arrow45, angle = 270)),
            "w": MSB(tooltip = mtt + "west\n(Ctrl + ← / Ctrl + 4)", icon = rotate_icon(arrow, angle = 180)),
            "nw": MSB(tooltip = mtt + "northwest\n(Ctrl + 7)", icon = rotate_icon(arrow45, angle = 270)),
            
            # Tip prep
            "bias_pulse": MSB(tooltip = "Apply a voltage pulse to the tip", icon = icons.get("bias_pulse")),
            "tip_shape": MSB(tooltip = "Shape the tip by poking it into the surface", icon = icons.get("tip_shape")),
            
            # Lockins
            "nanonis_mod1": MSB(icon = icons.get("nanonis_mod1"), states = [{"tooltip": "Nanonis modulator 1 OFF", "color": "#101010"}, {"tooltip": "Nanonis modulator 1 ON", "color": "#2020C0"}]),
            "nanonis_mod2": MSB(icon = icons.get("nanonis_mod2"), states = [{"tooltip": "Nanonis modulator 2 OFF", "color": "#101010"}, {"tooltip": "Nanonis modulator 2 ON", "color": "#2020C0"}]),
            "mla_mod1": MSB(icon = icons.get("mla_oscillator"), states = [{"tooltip": "MLA modulator 1 OFF", "color": "#101010"}, {"tooltip": "MLA modulator 1 ON", "color": "#2020C0"}]),

            # Processing
            "direction": MSB(tooltip = "Change scan direction\n(X)", states = [{"icon": icons.get("triple_arrow"), "color": "#101010"}, {"icon": rotate_icon(icons.get("triple_arrow"), angle = 180), "color": "#2020C0"}]),
            "fit_to_frame": MSB(tooltip = "Snap the view range to the scan frame", icon = icons.get("scan_frame")),
            "fit_to_range": MSB(tooltip = "Snap the view range to the total piezo range", icon = icons.get("piezo_range")),
            "full_data_range": MSB(tooltip = sivr + "to the full data range\n(U)", icon = icons.get("100")),
            "percentiles": MSB(tooltip = sivr + "by percentiles\n(R)", icon = icons.get("percentiles")),
            "standard_deviation": MSB(tooltip = sivr + "by standard deviations\n(D)", icon = icons.get("deviation")),
            "absolute_values": MSB(tooltip = sivr + "by absolute values\n(A)", icon = icons.get("numbers")),
            
            "bg_none": MSB(states = [{"tooltip": "None\n(0)", "icon": self.icons.get("0_2"), "color": "#101010"}, {"color": "#2020C0"}]),
            "bg_plane": MSB(states = [{"tooltip": "Plane\n(0)", "icon": self.icons.get("plane_subtract"), "color": "#101010"}, {"color": "#2020C0"}]),
            "bg_linewise": MSB(states = [{"tooltip": "Linewise\n(0)", "icon": self.icons.get("lines"), "color": "#101010"}, {"color": "#2020C0"}]),
            "bg_inferred": MSB(states = [{"tooltip": "None\n(0)", "icon": self.icons.get("0_2"), "color": "#101010"}, {"color": "#2020C0"}]),
            
            "sobel": MSB(text = "Sobel", tooltip = "Compute the complex gradient d/dx + i d/dy\n(Shift + S)", icon = self.icons.get("sobel"), states = [{"color": "#101010"}, {"color": "#2020C0"}]),
            "laplace": MSB(text = "Laplace", tooltip = "Compute the Laplacian (d/dx)^2 + (d/dy)^2\n(Shift + L)", icon = self.icons.get("laplacian"), states = [{"color": "#101010"}, {"color": "#2020C0"}]),
            "fft": MSB(text = "Fft", tooltip = "Compute the 2D Fourier transform\n(Shift + F)", icon = self.icons.get("fourier"), states = [{"color": "#101010"}, {"color": "#2020C0"}]),
            "normal": MSB(text = "Normal", tooltip = "Compute the z component of the surface normal\n(Shift + N)", icon = self.icons.get("surface_normal"), states = [{"color": "#101010"}, {"color": "#2020C0"}]),
            "gaussian": MSB(text = "Gauss", tooltip = "Gaussian blur applied\n(Shift + G) or provide a width to toggle", icon = self.icons.get("gaussian"), states = [{"color": "#101010"}, {"color": "#2020C0"}]),
            "rot_trans": MSB(tooltip = "Show the scan in the scan window coordinates\nwith rotation and translation\n(R)", icon = self.icons.get("rot_trans"), states = [{"color": "#101010"}, {"color": "#2020C0"}]),
        }

        for i in range(6):
            buttons.update({f"scan_parameters_{i}": MSB(tooltip = f"Load scan parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"coarse_parameters_{i}": MSB(tooltip = f"Load coarse parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"gain_parameters_{i}": MSB(tooltip = f"Load gain parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"speed_parameters_{i}": MSB(tooltip = f"Load speed parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"grid_parameters_{i}": MSB(tooltip = f"Load grid parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"parameters_{i}": MSB(tooltip = f"Parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})

        # Increase size of important buttons        
        buttons["frame_aspect"].setChecked(True)

        # Named groups
        self.connection_buttons = [buttons[name] for name in ["nanonis", "camera", "mla", "keithley", "scanalyzer", "session_folder", "info"]]
        self.arrow_buttons = [buttons[direction] for direction in ["nw", "n", "ne", "w", "n", "e", "sw", "s", "se"]]
        self.action_buttons = [buttons[name] for name in ["withdraw", "retract", "advance", "approach"]]        
        self.scan_parameter_sets = [buttons[f"scan_parameters_{i + 1}"] for i in range(4)]
        self.scale_buttons = [buttons[name] for name in ["full_data_range", "percentiles", "standard_deviation", "absolute_values"]]
        
        self.background_buttons = [buttons[name] for name in ["bg_none", "bg_plane", "bg_linewise"]]

        # Add the button handles to the tooltips
        [buttons[name].changeToolTip(f"gui.buttons[\"{name}\"]", line = 10) for name in buttons.keys()]

        return buttons

    def make_checkboxes(self) -> tuple[dict, dict]:
        CB = STWidgets.CheckBox
        
        checkboxes = {
            "withdraw": CB(tooltip = "Include withdrawing of the tip during a tip move"),
            "retract": CB(tooltip = "Include retracting the tip during a tip move"),
            "advance": CB(tooltip = "Include advancing the tip during a move"),
            "approach": CB(tooltip = "End the tip move with an auto approach"),

            "composite_motion": CB(tooltip = "Composite motion:\nWhen checked, combine all checked vertical motions with the horizontal motion in a composite pattern", icon = self.icons.get("composite_motion"))
        }
        
        channel_checkboxes = {f"{index}": CB(tooltip = f"channel {index}") for index in range(20)}
        
        # Named groups
        self.action_checkboxes = [checkboxes[name] for name in ["withdraw", "retract", "advance", "approach"]]
        [checkbox.setChecked(True) for checkbox in self.action_checkboxes]
        checkboxes["advance"].setChecked(False)

        # Add the button handles to the tooltips
        [checkboxes[name].changeToolTip(f"gui.checkboxes[\"{name}\"]", line = 10) for name in checkboxes.keys()]

        return (checkboxes, channel_checkboxes)

    def make_comboboxes(self) -> dict:
        CB = STWidgets.ComboBox
        
        comboboxes = {
            "channels": CB(name = "Channels", tooltip = "Available scan channels"),
            "projection": CB(name = "Projection", tooltip = "Select a projection or toggle with\n(Shift + ↑)", items = ["re", "im", "abs", "arg (b/w)", "arg (hue)", "complex", "abs^2", "log(abs)"]),
            "experiment": CB(name = "Experiment", tooltip = "Select an experiment"),
            "direction": CB(name = "Direction", tooltip = "Select a scan direction / pattern", items = ["nearest tip", "down", "up", "random"]),
            
            "voltage_current": CB(name = "voltage / current", tooltip = "Load voltage / current parameters"),
            "gains": CB(name = "gains", tooltip = "Load gains parameters"),
            "frame": CB(name = "frame", tooltip = "Load frame parameters"),
            "grid": CB(name = "grid", tooltip = "Load grid parameters"),
        }
        
        # Add the button handles to the tooltips
        [comboboxes[name].changeToolTip(f"gui.comboboxes[\"{name}\"]", line = 10) for name in comboboxes.keys()]
        
        return comboboxes

    def make_line_edits(self) -> dict:
        buttons = self.buttons
        LE = STWidgets.PhysicsLineEdit
        
        line_edits = {
            # Experiment
            "experiment_filename": LE(tooltip = "Base name of the file when saved to png or hdf5"),
            "experiment_0": LE(tooltip = "Experiment parameter field 0"),
            "experiment_1": LE(tooltip = "Experiment parameter field 1"),
            "experiment_2": LE(tooltip = "Experiment parameter field 2"),

            # Coarse
            "z_steps": LE(value = 20, tooltip = "Steps in the +Z (retract) direction", unit = "steps up", limits = [0, 100000], digits = 0),
            "h_steps": LE(value = 100, tooltip = "Steps in the horizontal direction", unit = "steps", limits = [0, 100000], digits = 0),
            "minus_z_steps": LE(value = 0, tooltip = "Steps in the -Z (advance) direction", unit = "steps down", limits = [0, 100000], digits = 0),
            
            "V_hor": LE(value = 150, tooltip = "Voltage supplied to the coarse piezos during horizontal movement", unit = "V (xy)", digits = 0),
            "V_ver": LE(value = 150, tooltip = "Voltage supplied to the coarse piezos during vertical movement", unit = "V (z)", digits = 0),
            "f_motor": LE(value = 1000, tooltip = "Sawtooth wave frequency supplied to the coarse piezos during movement", unit = "Hz", digits = 0),

            # Parameters
            "V_nanonis": LE(tooltip = "Nanonis bias\n(Ctrl + P) to set", unit = "V", limits = [-10, 10], digits = 3),
            "V_mla": LE(tooltip = "MLA bias\n(Ctrl + P) to set", unit = "V", limits = [-10, 10], digits = 3),
            "V_keithley": LE(tooltip = "Keithley bias\n(Ctrl + P) to set", unit = "V", limits = [-200, 200], digits = 3),

            "dV": LE(tooltip = "Step size dV when ramping the bias", unit = "mV", limits = [-1000, 1000], digits = 1),
            "dt": LE(tooltip = "Step size dt when ramping the bias", unit = "ms", limits = [-1000, 1000], digits = 0),
            "dz": LE(tooltip = "Step size dz when ramping the bias\nTemporarily retract the tip by this amount when ramping to a different polarity", unit = "nm", limits = [-200, 200], digits = 1),

            "dV_keithley": LE(tooltip = "Step size dV when ramping the Keithley bias", unit = "mV", limits = [-1000, 1000], digits = 1),
            "dt_keithley": LE(tooltip = "Step size dt when ramping the Keithley bias", unit = "ms", limits = [-1000, 1000], digits = 0),

            "I_fb": LE(tooltip = "Feedback current\n(Ctrl + P) to set", unit = "pA", digits = 0),
            "I_keithley": LE(tooltip = "Keithley current", unit = "pA", digits = 0),
            "I_limit": LE(tooltip = "Maximum Keithley current", unit = "pA", digits = 0),
            
            "p_gain": LE(tooltip = "Proportional gain", unit = "pm", digits = 0),
            "t_const": LE(tooltip = "Time constant", unit = "us", digits = 0),
            "i_gain": LE(tooltip = "Integral gain", unit = "nm/s", digits = 0),
            
            "v_fwd (nm/s)": LE(tooltip = "Tip forward speed", unit = "nm/s", digits = 2),
            "v_bwd (nm/s)": LE(tooltip = "Tip backward speed", unit = "nm/s", digits = 2),
            
            # Frame
            "frame_height": LE(tooltip = "frame height", unit = "nm", limits = [0, 1000], digits = 1),
            "frame_width": LE(tooltip = "frame width", unit = "nm", limits = [0, 1000], digits = 1),
            "frame_x": LE(tooltip = "frame offset (x)", unit = "nm", limits = [-1000, 1000], digits = 1),
            "frame_y": LE(tooltip = "frame offset (y)", unit = "nm", limits = [-1000, 1000], digits = 1),
            "frame_angle": LE(tooltip = "frame angle", unit = "deg", limits = [-180, 360], digits = 1),
            "frame_aspect": LE(value = 1, tooltip = "frame aspect ratio (height / width)", digits = 4),

            # Grid
            "grid_pixels": LE(tooltip = "Number of pixels", unit = "px", limits = [1, 10000], digits = 0),
            "grid_lines": LE(tooltip = "Number of lines", unit = "px", limits = [1, 10000], digits = 0),
            "grid_aspect": LE(tooltip = "grid aspect ratio (lines / pixels)", digits = 4),
            "pixel_width": LE(tooltip = "pixel width", unit = "nm", digits = 4),
            "pixel_height": LE(tooltip = "pixel height", unit = "nm", digits = 4),
            
            # Tip shaper
            "pulse_voltage": LE(tooltip = "Voltage to apply to the tip when pulsing", unit = "V", limits = [-10, 10], digits = 1),
            "pulse_duration": LE(tooltip = "Duration of the voltage pulse", unit = "ms", limits = [0, 5000], digits = 0),
            
            # Lockins
            "nanonis_mod1_f": LE(tooltip = "Nanonis modulator 1 frequency", unit = "Hz", limits = [0, 10000], digits = 1),
            "nanonis_mod1_mV": LE(tooltip = "Nanonis modulator 1 amplitude", unit = "mV", limits = [0, 5000], digits = 1),
            "nanonis_mod1_phi": LE(tooltip = "Nanonis modulator 1 phase", unit = "deg", limits = [-180, 360], digits = 1),
            "nanonis_mod2_f": LE(tooltip = "Nanonis modulator 2 frequency", unit = "Hz", limits = [0, 10000], digits = 1),
            "nanonis_mod2_mV": LE(tooltip = "Nanonis modulator 2 amplitude", unit = "mV", limits = [0, 5000], digits = 1),
            "nanonis_mod2_phi": LE(tooltip = "Nanonis modulator 2 phase", unit = "deg", limits = [-180, 360], digits = 1),
            
            "mla_mod1_f": LE(tooltip = "MLA modulator 1 frequency", unit = "Hz", limits = [0, 10000], digits = 1),
            "mla_mod1_V": LE(tooltip = "MLA modulator 1 amplitude", unit = "V", limits = [0, 10], digits = 1),
            "mla_mod1_phi": LE(tooltip = "MLA modulator 1 phase", unit = "deg", limits = [-180, 360], digits = 1),

            # Image processing
            "min_full": LE(tooltip = "minimum value of scan data range", digits = 3),
            "max_full": LE(tooltip = "maximum value of scan data range", digits = 3),
            "min_percentiles": LE(value = 1.0, tooltip = "minimum percentile of data range", unit = "%", digits = 1),
            "max_percentiles": LE(value = 99.0, tooltip = "maximum percentile of data range", unit = "%", digits = 1),
            "min_deviations": LE(value = 2.0, tooltip = "minimum = mean - n * standard deviation", unit = "\u03C3", digits = 1),
            "max_deviations": LE(value = 2.0, tooltip = "maximum = mean + n * standard deviation", unit = "\u03C3", digits = 1),
            "min_absolute": LE(value = 0, tooltip = "minimum absolute value", digits = 3),
            "max_absolute": LE(value = 1, tooltip = "maximum absolute value", digits = 3),

            "gaussian_width": LE(value = 0.000, tooltip = "Width for Gaussian blur application", unit = "nm", digits = 3),
            "file_name": LE(tooltip = "Base name of the file when saved to png or hdf5"),
            
            # Console            
            "input": LE(tooltip = "Enter a command\n(Enter to evaluate)", block = True)
        }
        
        # Named groups
        self.parameter_line_0 = [buttons["tip"], line_edits["V_nanonis"], buttons["V_swap"], line_edits["V_mla"], line_edits["I_fb"], buttons["set_scan_parameters"], buttons["get_scan_parameters"]]
        self.parameter_line_1 = [line_edits[name] for name in ["p_gain", "t_const", "v_fwd (nm/s)", "v_bwd (nm/s)"]]

        self.experiment_parameter_fields = [line_edits[f"experiment_{i}"] for i in range(3)]

        self.gain_line_edits = [line_edits[name] for name in ["p_gain", "t_const", "i_gain"]]
        
        self.action_line_edits = [line_edits[name] for name in ["z_steps", "h_steps", "minus_z_steps"]]
        self.min_line_edits = [line_edits[name] for name in ["min_full", "min_percentiles", "min_deviations", "min_absolute"]]
        self.max_line_edits = [line_edits[name] for name in ["max_full", "max_percentiles", "max_deviations", "max_absolute"]]
        
        self.tip_prep_widgets = [buttons["bias_pulse"], line_edits["pulse_voltage"], line_edits["pulse_duration"], buttons["tip_shape"]]

        self.frame_widgets = [line_edits[name] for name in ["frame_height", "frame_width", "frame_x", "frame_y", "frame_angle", "frame_aspect"]]
        self.grid_widgets = [line_edits[name] for name in ["grid_lines", "grid_pixels", "grid_aspect"]]
        
        self.modulator_widgets = [buttons["nanonis_mod1"], line_edits["nanonis_mod1_f"], line_edits["nanonis_mod1_mV"], line_edits["nanonis_mod1_phi"],
                                  buttons["nanonis_mod2"], line_edits["nanonis_mod2_f"], line_edits["nanonis_mod2_mV"], line_edits["nanonis_mod2_phi"],
                                  buttons["mla_mod1"], line_edits["mla_mod1_f"], line_edits["mla_mod1_V"], line_edits["mla_mod1_phi"]]        
        
        # Add the button handles to the tooltips
        [line_edits[name].changeToolTip(f"gui.line_edits[\"{name}\"]", line = 10) for name in line_edits.keys()]
        
        # Initialize
        [line_edits[name].setEnabled(False) for name in ["min_full", "max_full"]]
        
        return line_edits

    def make_radio_buttons(self) -> dict:
        RBN = STWidgets.RadioButton
        QGroup = QtWidgets.QButtonGroup
        
        radio_buttons = {
            "min_full": RBN(tooltip = "set to minimum value of scan data range\n(-) to toggle"),
            "max_full": RBN(tooltip = "set to maximum value of scan data range\n(=) to toggle"),
            "min_percentiles": RBN(tooltip = "set to minimum percentile of data range\n(-) to toggle"),
            "max_percentiles": RBN(tooltip = "set to maximum percentile of data range\n(=) to toggle"),
            "min_deviations": RBN(tooltip = "set to minimum = mean - n * standard deviation\n(-) to toggle"),
            "max_deviations": RBN(tooltip = "set to maximum = mean + n * standard deviation\n(=) to toggle"),
            "min_absolute": RBN(tooltip = "set minimum to an absolute value\n(-) to toggle"),
            "max_absolute": RBN(tooltip = "set maximum to an absolute value\n(=) to toggle"),
        }
        
        # Add the button handles to the tooltips
        [radio_buttons[name].changeToolTip(f"gui.radio_buttons[\"{name}\"]", line = 10) for name in radio_buttons.keys()]
        
        # Named groups
        min_names = ["min_full", "min_percentiles", "min_deviations", "min_absolute"]
        max_names = ["max_full", "max_percentiles", "max_deviations", "max_absolute"]
        self.min_radio_buttons = [radio_buttons[name] for name in min_names]
        self.max_radio_buttons = [radio_buttons[name] for name in max_names]
                
        # Add buttons to QButtonGroups for exclusive selection and check the defaults        
        self.min_button_group = QGroup()
        self.max_button_group = QGroup()
        [self.min_button_group.addButton(button) for button in self.min_radio_buttons]
        [self.max_button_group.addButton(button) for button in self.max_radio_buttons]
        
        # Initialize
        checked_buttons = [radio_buttons[name] for name in ["min_full", "max_full"]]
        [button.setChecked(True) for button in checked_buttons]
        
        return radio_buttons

    def make_progress_bars(self) -> dict:
        PB = STWidgets.ProgressBar
        
        progress_bars = {
            "experiment": PB(tooltip = "Experiment progress")
        }
        
        # Named groups
        self.experiment_controls = [progress_bars["experiment"]]
        [self.experiment_controls.append(self.buttons[name]) for name in ["start_pause", "stop", "save"]]
        
        # Add the progress_bar handles to the tooltips
        [progress_bars[name].changeToolTip(f"gui.progress_bars[\"{name}\"]", line = 10) for name in progress_bars.keys()]
        
        return progress_bars

    def make_layouts(self) -> dict:
        
        layouts = {
            "main": make_layout("h"),
            "left_side": make_layout("v"),
            "toolbar": make_layout("v"),
            
            "parameters_0": make_layout("v"),
            "scan_parameter_sets": make_layout("h"),
            
            "scan_parameters": make_layout("g"),
            
            "gains_line_edits": make_layout("h"),
            "gains_set_get": make_layout("h"),
            "gains": make_layout("v"),

            "speeds": make_layout("h"),
            "speeds_parameter_sets": make_layout("h"),
            
            "frame_grid": make_layout("g"),
            "frame": make_layout("g"),
            "grid": make_layout("g"),
            "frame_grid_parameter_sets": make_layout("h"),

            "lockins": make_layout("g"),
            "lockin_parameter_sets": make_layout("h"),

            "channel_navigation": make_layout("h"),

            "bias_buttons": make_layout("h"),

            "coarse_vertical": make_layout("g"),
            "coarse_horizontal": make_layout("g"),
            
            "modulators": make_layout("g"),
            "mod_set_get": make_layout("h"),
            "demodulators": make_layout("h"),
            "demod_sliders": make_layout("h"),

            "background_buttons": make_layout("h"),
            "matrix_processing": make_layout("g"),
            "limits": make_layout("g"),
            "empty": make_layout("v"),
            
            "input": make_layout("h"),
            "experiment_controls_0": make_layout("v"),
            "experiment_controls_1": make_layout("h"),
            "experiment_fields": make_layout("h"),
            
            "graph": make_layout("h"),
            "channels": make_layout("g"),

            "connections": make_layout("g"),
            "coarse_control": make_layout("h"),
            "tip_prep": make_layout("h"),
            "parameters": make_layout("g"),            
            "image_processing": make_layout("v"),
            "experiment": make_layout("g")            
        }
        
        return layouts

    def make_image_view(self) -> STWidgets.ImageView:
        pg.setConfigOptions(imageAxisOrder = "row-major", antialias = True)
        
        plot_item = pg.PlotItem()
        im_view = STWidgets.ImageView(view = plot_item)
        im_view.view.invertY(False)
        
        # Make a tip target item in the image_view
        self.tip_target = STWidgets.TargetItem(pos = [0, 0], size = 10, tip_text = f"tip location\n(0, 0, 0) nm", movable = True)
        im_view.view.addItem(self.tip_target)        
        
        return im_view

    def make_rois(self) -> tuple[pg.ROI, pg.ROI, pg.ROI]:
        piezo_roi = pg.ROI([-50, -50], [100, 100], pen = pg.mkPen(color = self.colors["orange"], width = 2), movable = False, resizable = False, rotatable = False)
        frame_roi = pg.ROI([-50, -50], [100, 100], pen = pg.mkPen(color = self.colors["blue"], width = 2), movable = False, resizable = False, rotatable = False)
        new_frame_roi = pg.ROI([-50, -50], [100, 100], pen = pg.mkPen(color = self.colors["light_blue"], width = 2), movable = True, resizable = True, rotatable = True)
        
        new_frame_roi.addScaleHandle([1, 0], [0, 1])
        new_frame_roi.addRotateHandle([0.5, 0], [0.5, 0.5])
        
        return (piezo_roi, frame_roi, new_frame_roi)

    def make_plot_widget(self) -> pg.PlotWidget:
        plot_widget = pg.PlotWidget()

        graphs = []
        for i in range(20):
            pen = pg.mkPen(self.color_list[i])
            
            graphs.append(plot_widget.plot(x_data = [], y_data = [], pen = pen))
        
        return (plot_widget, graphs)

    def make_widgets(self) -> dict:
        QWgt = QtWidgets.QWidget
        
        widgets = {
            "central": QWgt(),
            "left_side": QWgt(),
            "coarse_actions": QWgt(),
            "arrows": QWgt(),
            "graph": QWgt(),

            "connections": QWgt(),
            "coarse_control": QWgt(),
            "frame_grid": QWgt(),
            "tip_prep": QWgt(),
            "parameters": QWgt(),
            "image_processing": QWgt(),
            "experiment": QWgt(),
            "lockins": QWgt(),
        }

        self.phase_slider = STWidgets.SliderLineEdit(tooltip = "Set complex phase phi in deg\n(= multiplication by exp(i * pi * phi rad / (180 deg)))", orientation = "h")
        
        return widgets

    def make_consoles(self) -> dict:        
        consoles = {
            "output": STWidgets.Console(tooltip = "Output console"),
            "input": STWidgets.Console(tooltip = "Input console")
        }
        
        consoles["output"].setReadOnly(True)
        consoles["input"].setReadOnly(False)
        consoles["input"].setMaximumHeight(30)
        [consoles[name].setStyleSheet("QTextEdit{ background-color: #101010; }") for name in ["output", "input"]]
        
        # Add the handles to the tooltips
        [consoles[name].changeToolTip(f"gui.consoles[\"{name}\"]", line = 10) for name in consoles.keys()]
        
        return consoles

    def make_tip_slider(self) -> STWidgets.Slider:
        tip_slider = STWidgets.Slider(tooltip = "Tip height (nm)", orientation = "v")        
        return tip_slider

    def make_demod_audio_sliders(self) -> dict:
        SLE = STWidgets.SliderLineEdit
        demod_audio_sliders = {}
        
        for harmonic in range(1, 20):
            sle = SLE(tooltip = "relative volume of harmonic {i}", orientation = "v", limits = [0, 100], initial_val = 100, digits = 0, unit = "%", minmax_buttons = True)
            sle.min_button.setIcon(self.icons.get("0"))
            sle.max_button.setIcon(self.icons.get("1"))
            demod_audio_sliders.update({f"f{harmonic}": sle})

        return demod_audio_sliders

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
        dialogs = {"parameters": QtWidgets.QInputDialog(), "info": QtWidgets.QInputDialog()}
        return dialogs

    def make_boxes(self) -> tuple[QtWidgets.QMessageBox, QtWidgets.QMessageBox]:
        info_box = QtWidgets.QMessageBox(self)
        info_box.setWindowTitle("Info")
        info_box.setText("Scanalyzer (2026)\nby Peter H. Jacobse\nRice University; Lawrence Berkeley National Lab")
        info_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        info_box.setWindowIcon(self.icons.get("i"))
        
        message_box = QtWidgets.QMessageBox(self)
        message_box.setWindowTitle("Success")
        message_box.setText("png file saved")
        return (info_box, message_box)



    # 3: Populate layouts with GUI items. Requires GUI items.
    def populate_layouts(self) -> None:
        layouts = self.layouts
        checkboxes = self.checkboxes
        buttons = self.buttons
        line_edits = self.line_edits
        labels = self.labels
        comboboxes = self.comboboxes
        
        # Graphing
        [layouts["channels"].addWidget(self.channel_checkboxes[f"{i}"], i % 5, int(i / 5)) for i in range(len(self.channel_checkboxes))]
        
        layouts["graph"].addWidget(self.plot_widget, 5)
        layouts["graph"].addLayout(layouts["channels"], 1)
        self.widgets["graph"].setLayout(layouts["graph"])
        
        # Toolbar
        # Connections
        layouts["connections"].addWidget(buttons["view"], 0, 0, 2, 1)
        [layouts["connections"].addWidget(button, 0, i + 1) for i, button in enumerate(self.connection_buttons[:4])]
        [layouts["connections"].addWidget(button, 1, i + 1) for i, button in enumerate(self.connection_buttons[4:])]
        layouts["connections"].addWidget(buttons["exit"], 0, 5, 2, 1)

        # Experiment
        [layouts["experiment_controls_0"].addWidget(buttons[name]) for name in ["stop", "start_pause"]]
        [layouts["experiment_controls_1"].addWidget(widget) for widget in [self.progress_bars["experiment"], buttons["save"], line_edits["experiment_filename"]]]
        [layouts["experiment_fields"].addWidget(widget) for widget in self.experiment_parameter_fields]
        e_layout = layouts["experiment"]
        e_layout.addLayout(layouts["experiment_controls_0"], 0, 0, 3, 1)
        e_layout.addWidget(self.tip_slider, 0, 1, 3, 1)
        e_layout.addWidget(self.comboboxes["experiment"], 0, 2, 1, 2)
        e_layout.addWidget(self.comboboxes["direction"], 0, 4)
        # [e_layout.addWidget(self.comboboxes[name], 0, i + 1) for i, name in enumerate(["experiment", "direction"])]
        e_layout.addLayout(layouts["experiment_controls_1"], 1, 2, 1, 3)
        e_layout.addWidget(self.line_edits["experiment_filename"], 2, 3)
        e_layout.addLayout(layouts["experiment_fields"], 2, 2, 1, 3)
        
        # Coarse
        cv_layout = layouts["coarse_vertical"]
        cv_layout.addWidget(line_edits["V_ver"], 0, 0, 1, 3)
        cv_layout.addWidget(line_edits["f_motor"], 1, 0, 1, 3)
        [cv_layout.addWidget(checkbox, 2 + i + int(i / 2), 0) for i, checkbox in enumerate(self.action_checkboxes)]
        [cv_layout.addWidget(button, 2 + i + int(i / 2), 1) for i, button in enumerate(self.action_buttons)]
        cv_layout.addWidget(line_edits["z_steps"], 3, 2)
        cv_layout.addWidget(labels["move_horizontally"], 4, 0, 1, 3)
        cv_layout.addWidget(line_edits["minus_z_steps"], 5, 2)
        cv_layout.setRowStretch(cv_layout.rowCount(), 1)
        
        ch_layout = layouts["coarse_horizontal"]
        ch_layout.addWidget(line_edits["V_hor"], 0, 0, 1, 3)
        ch_layout.addWidget(line_edits["f_motor"], 1, 0, 1, 3)
        ch_layout.addWidget(line_edits["h_steps"], 2, 0, 1, 3)
        [ch_layout.addWidget(button, 3 + int(i / 3), i % 3) for i, button in enumerate(self.arrow_buttons)]
        ch_layout.addWidget(checkboxes["composite_motion"], 6, 0, 1, 3)
        ch_layout.setRowStretch(ch_layout.rowCount(), 1)
        
        # Parameters
        [layouts["scan_parameter_sets"].addWidget(button) for button in self.scan_parameter_sets]

        # Gains
        [layouts["gains_line_edits"].addWidget(widget) for widget in self.gain_line_edits]
        [layouts["gains_set_get"].addWidget(widget) for widget in [buttons["get_gain_parameters"], buttons["set_gain_parameters"], comboboxes["gains"]]]
        layouts["gains"].addLayout(layouts["gains_line_edits"])
        layouts["gains"].addLayout(layouts["gains_set_get"])
        
        # Frame_grid
        [layouts["frame_grid_parameter_sets"].addWidget(buttons[f"grid_parameters_{i}"]) for i in range(6)]

        fg_layout = layouts["frame_grid"]
        fg_layout.addWidget(labels["frame"], 0, 0, 1, 2)
        fg_layout.addWidget(make_line("h", 1), 1, 0, 1, 2)
        fg_layout.addWidget(buttons["frame_aspect"], 2, 0)
        fg_layout.addWidget(line_edits["frame_height"], 2, 1)
        fg_layout.addWidget(line_edits["frame_width"], 3, 0)
        fg_layout.addWidget(line_edits["frame_aspect"], 3, 1)
        fg_layout.addWidget(line_edits["frame_x"], 4, 0)
        fg_layout.addWidget(line_edits["frame_y"], 4, 1)
        fg_layout.addWidget(line_edits["frame_angle"], 5, 0, 1, 2)

        fg_layout.addWidget(buttons["get_frame_parameters"], 6, 0)
        fg_layout.addWidget(buttons["set_frame_parameters"], 6, 1)

        fg_layout.addWidget(labels["grid"], 0, 2, 1, 2)
        fg_layout.addWidget(make_line("h", 1), 1, 2, 1, 2)
        fg_layout.addWidget(buttons["grid_aspect"], 2, 2)
        fg_layout.addWidget(line_edits["grid_lines"], 2, 3)
        fg_layout.addWidget(line_edits["grid_pixels"], 3, 2)
        fg_layout.addWidget(line_edits["grid_aspect"], 3, 3)
        fg_layout.addWidget(line_edits["pixel_width"], 4, 2)
        fg_layout.addWidget(line_edits["pixel_height"], 4, 3)

        fg_layout.addWidget(buttons["get_grid_parameters"], 6, 2)
        fg_layout.addWidget(buttons["set_grid_parameters"], 6, 3)

        fg_layout.addLayout(layouts["frame_grid_parameter_sets"], 7, 0, 1, 4)
        
        # Tip prep
        [layouts["tip_prep"].addWidget(widget) for widget in self.tip_prep_widgets]
        
        # Lockins
        [layouts["mod_set_get"].addWidget(buttons[name]) for name in ["get_lockin_parameters", "set_lockin_parameters"]]
        [layouts["modulators"].addWidget(widget, int(i / 4), i % 4) for i, widget in enumerate(self.modulator_widgets)]
        layouts["modulators"].addLayout(layouts["mod_set_get"], 3, 0, 1, 4)
        [layouts["demod_sliders"].addWidget(self.demod_audio_sliders[f"f{i}"]) for i in range(1, 8)]
        layouts["demodulators"].addLayout(layouts["demod_sliders"])
        
        # Image processing                
        cn_layout = layouts["channel_navigation"]
        cn_layout.addWidget(comboboxes["channels"], 4)
        cn_layout.addWidget(self.buttons["direction"], 1)
        [cn_layout.addWidget(self.buttons[name]) for name in ["fit_to_frame", "fit_to_range"]]
        
        [layouts["background_buttons"].addWidget(button) for button in self.background_buttons]
        layouts["background_buttons"].addWidget(buttons["rot_trans"])
        p_layout = layouts["matrix_processing"]
        [p_layout.addWidget(buttons[name], 0, index) for index, name in enumerate(["sobel", "normal", "laplace"])]
        p_layout.addWidget(buttons["gaussian"], 1, 1)
        p_layout.addWidget(line_edits["gaussian_width"], 1, 2)
        p_layout.addWidget(buttons["fft"], 1, 0)
        p_layout.addWidget(comboboxes["projection"], 2, 0)
        p_layout.addWidget(self.phase_slider, 2, 1, 1, 2)
        
        l_layout = layouts["limits"]
        self.limits_columns = [self.min_line_edits, self.min_radio_buttons, self.scale_buttons, self.max_radio_buttons, self.max_line_edits]
        for j, group in enumerate(self.limits_columns): [l_layout.addWidget(item, i, j) for i, item in enumerate(group)]

        ip_layout = layouts["image_processing"]
        ip_layout.addLayout(layouts["channel_navigation"])
        ip_layout.addWidget(labels["background_subtraction"])
        ip_layout.addLayout(layouts["background_buttons"])
        ip_layout.addWidget(make_line("h", 1))
        ip_layout.addWidget(labels["matrix_operations"])
        ip_layout.addLayout(p_layout)
        ip_layout.addWidget(make_line("h", 1))
        ip_layout.addWidget(labels["limits"])         
        ip_layout.addLayout(l_layout)
        
        #layouts["input"].addWidget(self.buttons["input"], 1)
        layouts["input"].addWidget(self.consoles["input"])
        
        return



    # 4: Make widgets and groupboxes and set their layouts. Requires layouts.
    def make_groupboxes(self) -> dict:
        SGB = STWidgets.GroupBox
        layouts = self.layouts
        
        groupboxes = {
            # Connections
            "connections": SGB(title = "Connections", tooltip = "Connections to hardware (push to check/refresh)"),
            
            # Coarse
            "coarse_control": SGB(title = "Coarse control", tooltip = "Control the tip (use ctrl key to access these functions)"),
            "coarse_vertical": SGB(title = "Vertical", tooltip = "Vertical coarse motion"),
            "coarse_horizontal": SGB(title = "Horizontal", tooltip = "Vertical coarse motion"),

            "frame_grid": SGB(title = "Frame / grid", tooltip = "Frame and grid parameters"),
            "gains": SGB(title = "Feedback gains", tooltip = "Feedback gains"),
            "modulators": SGB(title = "Modulators", tooltip = "Modulators"),
            "demodulators": SGB(title = "Demodulators", tooltip = "Demodulators"),

            "tip_prep": SGB(title = "Tip prep", tooltip = "Tip preparation actions"),
            "parameters": SGB(title = "Scan parameters", tooltip = "Scan parameters"),
            "image_processing": SGB(title = "Image processing", tooltip = "Select the background subtraction, matrix operations and set the image range limits (use shift key to access these functions)"),
            "experiment": SGB(title = "Experiment", tooltip = "Perform experiment"),
            
            "dummy": SGB(title = "Dummy", tooltip = "Invisible groupbox to swap out layouts to make other groupboxes collapse")
        }

        # Set layouts for the groupboxes
        groupbox_names = ["connections", "coarse_control", "coarse_horizontal", "coarse_vertical", "gains", "frame_grid", "tip_prep", "parameters", "modulators", "demodulators", "experiment", "image_processing"]
        [groupboxes[name].setLayout(layouts[name]) for name in groupbox_names]

        # Make layouts of several groupboxes
        [layouts["coarse_control"].addWidget(groupboxes[name]) for name in ["coarse_horizontal", "coarse_vertical"]]
        [layouts["parameters"].addWidget(groupboxes[name]) for name in ["gains", "frame_grid"]]
        [layouts["lockins"].addWidget(groupboxes[name]) for name in ["modulators", "demodulators"]]

        return groupboxes



    # 5: Make the tab widget
    def make_tab_widget(self) -> QtWidgets.QTabWidget:
        tab_widget = QtWidgets.QTabWidget()
        
        tabs = ["coarse_control", "tip_prep", "parameters", "image_processing", "lockins"]
        tab_names = ["Coarse", "Prep", "Parameters", "Processing", "Lock-ins"]
        [self.widgets[name0].setLayout(self.layouts[name0]) for name0 in tabs]
        [tab_widget.addTab(self.widgets[name0], name) for name0, name in zip(tabs, tab_names)]

        return tab_widget



    # 5: Set up the main window layout
    def setup_main_window(self) -> None:
        layouts = self.layouts
        widgets = self.widgets
        groupboxes = self.groupboxes

        # Aesthetics
        layouts["left_side"].setContentsMargins(0, 0, 0, 0)
        layouts["toolbar"].setContentsMargins(4, 4, 4, 4)
        
        # Create the toolbar
        [self.layouts["toolbar"].addWidget(groupboxes[name]) for name in ["connections", "experiment"]]
        self.layouts["toolbar"].addWidget(self.tab_widget)
        layouts["toolbar"].addStretch(1)
        
        # Compose the image_view plus consoles layout
        layouts["left_side"].addWidget(self.image_view, stretch = 4)
        layouts["left_side"].addWidget(widgets["graph"], stretch = 1)
        layouts["left_side"].addWidget(self.consoles["output"], stretch = 1)
        layouts["left_side"].addWidget(self.line_edits["input"])
        self.widgets["left_side"].setLayout(layouts["left_side"])
        
        # Attach the toolbar
        layouts["main"].addWidget(self.widgets["left_side"], stretch = 4)
        layouts["main"].addLayout(layouts["toolbar"], 1)
        
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
    def interconnect(self) -> None:
        self.new_frame_roi.sigRegionChangeFinished.connect(self.update_fields_from_frame_change)
        [self.line_edits[name].editingFinished.connect(lambda name_0 = name: self.height_width_aspect(name_0)) for name in ["frame_width", "frame_height", "frame_aspect"]]
        [self.line_edits[name].editingFinished.connect(self.update_frame_from_fields) for name in ["frame_x", "frame_y", "frame_width", "frame_height", "frame_angle", "frame_aspect"]]
        
        [self.line_edits[name].editingFinished.connect(lambda name_0 = name: self.gains_changed(name_0)) for name in ["p_gain", "t_const", "i_gain"]]
        
        self.buttons["bg_none"].clicked.connect(lambda: self.background_mutex("none"))
        self.buttons["bg_plane"].clicked.connect(lambda: self.background_mutex("plane"))
        self.buttons["bg_linewise"].clicked.connect(lambda: self.background_mutex("linewise"))
        
        return

    def background_mutex(self, method: str = "none") -> None:
        [none, plane, linewise] = [self.buttons[name] for name in ["bg_none", "bg_plane", "bg_linewise"]]
        match method:
            case "none":
                [button.setState(0) for button in [plane, linewise]]
                none.setState(1)
            case "plane":
                [button.setState(0) for button in [none, linewise]]
                plane.setState(1)
            case _:
                [button.setState(0) for button in [none, plane]]
                linewise.setState(1)
        return



    def height_width_aspect(self, line_edit_name: str = "frame_width") -> None:
        [self.line_edits[name].blockSignals(True) for name in ["frame_width", "frame_height", "frame_aspect"]]

        match line_edit_name:

            case "frame_width":
                frame_width = self.line_edits["frame_width"].getValue()
                if not isinstance(frame_width, float) and not isinstance(frame_width, int): return

                if self.buttons["frame_aspect"].isChecked():
                    frame_aspect = self.line_edits["frame_aspect"].getValue()

                    if isinstance(frame_aspect, float) or isinstance(frame_aspect, int):
                        frame_height = frame_width * frame_aspect
                        self.line_edits["frame_height"].setValue(frame_height)
                else:
                    frame_height = self.line_edits["frame_height"].getValue()

                    print(f"Frame height = {frame_height}")

                    if isinstance(frame_height, float) or isinstance(frame_height, int):
                        frame_aspect = frame_height / frame_width
                        self.line_edits["frame_aspect"].setValue(frame_aspect)

            case "frame_height":
                frame_height = self.line_edits["frame_height"].getValue()
                if not isinstance(frame_height, float) and not isinstance(frame_height, int): return

                if self.buttons["frame_aspect"].isChecked():
                    frame_aspect = self.line_edits["frame_aspect"].getValue()

                    if isinstance(frame_aspect, float) or isinstance(frame_aspect, int):
                        frame_width = frame_height / frame_aspect
                        self.line_edits["frame_width"].setValue(frame_width)
                else:
                    frame_width = self.line_edits["frame_width"].getValue()
                    
                    if isinstance(frame_width, float) or isinstance(frame_width, int):
                        frame_aspect = frame_height / frame_width
                        self.line_edits["frame_aspect"].setValue(frame_aspect)

            case "frame_aspect":
                frame_aspect = self.line_edits["frame_aspect"].getValue()
                if not isinstance(frame_aspect, float) and not isinstance(frame_aspect, int): return

                frame_width = self.line_edits["frame_width"].getValue()
                if isinstance(frame_width, float) or isinstance(frame_width, int):
                    frame_height = frame_width * frame_aspect
                    self.line_edits["frame_height"].setValue(frame_height)

            case _:
                pass

        [self.line_edits[name].blockSignals(False) for name in ["frame_width", "frame_height", "frame_aspect"]]
        return

    def update_fields_from_frame_change(self) -> None:        
        [self.line_edits[name].blockSignals(True) for name in ["frame_x", "frame_y", "frame_width", "frame_height", "frame_angle"]]
        
        new_width = self.new_frame_roi.size().x()
        self.line_edits["frame_width"].setValue(new_width)
        
        if self.buttons["frame_aspect"].isChecked():
            new_height = new_width * self.line_edits["frame_aspect"].getValue()
            
            self.new_frame_roi.blockSignals(True)
            self.new_frame_roi.setSize([new_width, new_height])
            self.new_frame_roi.blockSignals(False)
        else:
            new_height = self.new_frame_roi.size().y()
            self.line_edits["frame_aspect"].setValue(new_height / new_width)
        
        self.line_edits["frame_height"].setValue(new_height)
                
        bounding_rect = self.new_frame_roi.boundingRect()
        local_center = bounding_rect.center()
        abs_center = self.new_frame_roi.mapToParent(local_center)
        
        self.line_edits["frame_x"].setValue(abs_center.x())
        self.line_edits["frame_y"].setValue(abs_center.y())
        
        self.line_edits["frame_angle"].setValue(-self.new_frame_roi.angle())
        
        [self.line_edits[name].blockSignals(False) for name in ["frame_x", "frame_y", "frame_width", "frame_height", "frame_angle"]]
        return

    def update_frame_from_fields(self) -> None:
        self.new_frame_roi.blockSignals(True)
        
        new_width = self.line_edits["frame_width"].getValue()
        new_height = self.line_edits["frame_height"].getValue()
        new_angle = self.line_edits["frame_angle"].getValue()
        new_x = self.line_edits["frame_x"].getValue()
        new_y = self.line_edits["frame_y"].getValue()
        
        self.new_frame_roi.setPos([0, 0])
        self.new_frame_roi.setSize([new_width, new_height])
        self.new_frame_roi.setAngle(-new_angle)
        
        bounding_rect = self.new_frame_roi.boundingRect()
        local_center = bounding_rect.center()
        abs_center = self.new_frame_roi.mapToParent(local_center)

        self.new_frame_roi.setPos(new_x - abs_center.x(), new_y - abs_center.y())
        
        self.new_frame_roi.blockSignals(False)        
        
        return

    def gains_changed(self, line_edit_name: str = "p_gain") -> None:
        match line_edit_name:
            case "i_gain":
                i_gain = self.line_edits["i_gain"].getValue()
                if not isinstance(i_gain, float) and not isinstance(i_gain, int): return
                
                p_gain = self.line_edits["p_gain"].getValue()
                if not isinstance(i_gain, float) and not isinstance(i_gain, int): return
                
                print(p_gain, i_gain)
            case _:
                pass
        
        return



    # Helper function to read parameters from the gui
    def read(self, parameter_type: str = "frame") -> dict:
        
        return



if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    logic_app = ScantelligentGUI()
    sys.exit(app.exec())
