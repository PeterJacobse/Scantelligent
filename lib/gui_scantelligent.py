import os, sys
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
from . import STWidgets, rotate_icon, make_layout, make_line



class ScantelligentGUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.color_list = ["#FFFFFF", "#FFFF20", "#20FFFF", "#FF80FF", "#60FF60", "#FF6060", "#8080FF", "#B0B0B0", "#FFB010", "#A050FF",
                           "#909020", "#00A0A0", "#B030A0", "#40B040", "#B04040", "#5050E0", "#c00000", "#905020", "#707000", "#2020ff"]
        self.colors = {"red": "#ff5050", "dark_red": "#800000", "green": "#00ff00", "dark_green": "#005000", "light_blue": "#30d0ff", "off-black": "#101010",
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
        self.sliders = self.make_sliders()
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
            "session_folder": LB(text = "Session folder"),
            "statistics": LB(text = "Statistics"),
            "load_file": LB(text = "Load file:"),
            "in_folder": LB(text = "in folder:"),
            "number_of_files": LB(text = "which contains 1 sxm file"),

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

            "scan_control": LB(text = "Navigation"),
            "limits": LB(text = "Limits"),
            "background_subtraction": LB(text = "Background subtraction"),
            "matrix_operations": LB(text = "Matrix operations"),

            "move_horizontally": LB(text = "< horizontal motion >", tooltip = "In composite motion, horizontal motion\nis carried out between retract and advance\nSee 'horizontal'"),
        }
        
        [labels.update({f"demod_harmonic_{i}": LB(text = f"#{i}", tooltip = f"harmonic {i}")}) for i in range(32)]
        
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
            "view": MSB(click_to_toggle = False, size = 28,
                        states = [{"name": "None", "tooltip": "Toggle the active view", "icon": icons.get("eye"), "color": self.colors["off-black"]},
                                  {"name": "Camera", "tooltip": "Active view: Camera", "icon": icons.get("view_camera"), "color": self.colors["off-black"]},
                                  {"name": "Nanonis", "tooltip": "Active view: Nanonis", "icon": icons.get("view_nanonis"), "color": self.colors["off-black"]}]),
            "exit": MSB(tooltip = "Exit scantelligent\n(Esc / X / E)", icon = icons.get("escape"), size = 28),
            "session_folder": MSB(icon = icons.get("folder_yellow"), click_to_toggle = False,
                                  states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Session folder unknown"},
                                            {"name": "online", "color": self.colors["dark_green"], "tooltip": "Open the session folder"}]),
            "info": MSB(tooltip = "Info", icon = self.icons.get("i")),
            
            # Experiment
            "save": MSB(tooltip = "Save the experiment results to file", icon = icons.get("floppy")),
            "start_stop": MSB(click_to_toggle = False, size = 28,
                              states = [{"name": "load", "color": self.colors["dark_red"], "tooltip": "Load/reset experiment", "icon": icons.get("start")},
                                        {"name": "ready", "color": self.colors["dark_green"], "tooltip": "Start experiment", "icon": icons.get("start")},
                                        {"name": "running", "color": self.colors["blue"], "tooltip": "Experiment running", "icon": icons.get("stop")},
                                        {"name": "aborted", "color": self.colors["orange"], "tooltip": "Abort requested", "icon": icons.get("stop")}]),
            "stop": MSB(tooltip = "Stop experiment", icon = icons.get("stop"), size = 28),
            
            # Parameters
            "frame_aspect": MSB(tooltip = "Lock the frame aspect ratio", icon = icons.get("lock_aspect"), states = [{"color": self.colors["off-black"]}, {"color": self.colors["blue"]}]),
            "grid_aspect": MSB(tooltip = "Lock the grid aspect ratio", icon = icons.get("lock_aspect"), states = [{"color": self.colors["off-black"]}, {"color": self.colors["blue"]}]),
            
            "tip": MSB(click_to_toggle = False, size = 28,
                       states = [{"name": "unknown", "tooltip": "Tip status\nUnknown / withdrawn", "icon": icons.get("tip_unknown"), "color": self.colors["off-black"]},
                                 {"name": "feedback", "tooltip": "Tip status\nIn feedback", "icon": icons.get("constant_current"), "color": self.colors["dark_green"]},
                                 {"name": "constant_height", "tooltip": "Tip status\nConstant height", "icon": icons.get("constant_height"), "color": self.colors["orange"]}]),
            "V_swap": MSB(tooltip = "Swap the bias between Nanonis and the MLA", icon = icons.get("swap")),
            
            # Coarse vertical
            "withdraw": MSB(click_to_toggle = False, states = [{"name": "landed", "tooltip": "Withdraw the tip\n(Ctrl + W)", "icon": icons.get("withdraw"), "color": self.colors["blue"]},
                                                               {"name": "withdrawn", "tooltip": "Land the tip\n(Ctrl + W)", "icon": self.icons.get("approach"), "color": self.colors["off-black"]}]),
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
            "sw": MSB(tooltip = mtt + "southwest\n(Ctrl + 1)", icon = rotate_icon(arrow45, angle = 180)),
            "w": MSB(tooltip = mtt + "west\n(Ctrl + ← / Ctrl + 4)", icon = rotate_icon(arrow, angle = 180)),
            "nw": MSB(tooltip = mtt + "northwest\n(Ctrl + 7)", icon = rotate_icon(arrow45, angle = 270)),
            
            "composite_motion": MSB(icon = self.icons.get("composite_motion"), size = 28,
                                    states = [{"tooltip": "Composite motion OFF\nThe horizontal motion is carried out without vertical motion", "color": self.colors["off-black"]},
                                              {"tooltip": "Composite motion ON\nAll checked vertical motions are combined with the horizontal motion in a composite pattern", "color": self.colors["blue"]}]),

            # Tip prep
            "bias_pulse": MSB(tooltip = "Apply a voltage pulse to the tip", icon = icons.get("bias_pulse"), size = 28),
            "tip_shape": MSB(tooltip = "Shape the tip by poking it into the surface", icon = icons.get("tip_shape"), size = 28),
            
            # Lockins
            "nanonis_mod1": MSB(icon = icons.get("nanonis_mod1"),
                                states = [{"name": "off", "tooltip": "Nanonis modulator 1 OFF", "color": self.colors["off-black"]},
                                          {"name": "on", "tooltip": "Nanonis modulator 1 ON", "color": self.colors["blue"]}]),
            "nanonis_mod2": MSB(icon = icons.get("nanonis_mod2"),
                                states = [{"name": "off", "tooltip": "Nanonis modulator 2 OFF", "color": self.colors["off-black"]},
                                          {"name": "on", "tooltip": "Nanonis modulator 2 ON", "color": self.colors["blue"]}]),
            "mla_mod1": MSB(icon = icons.get("mla_oscillator"),
                            states = [{"name": "off", "tooltip": "MLA modulator 1 OFF", "color": self.colors["off-black"]},
                                      {"name": "on", "tooltip": "MLA modulator 1 ON", "color": self.colors["blue"]}]),

            # Processing
            "direction": MSB(tooltip = "Change scan direction\n(X)",
                             states = [{"name": "forward", "icon": icons.get("triple_arrow"), "color": self.colors["off-black"]},
                                       {"name": "backward", "icon": rotate_icon(icons.get("triple_arrow"), angle = 180), "color": self.colors["blue"]}]),
            "fit_to_frame": MSB(tooltip = "Snap the view range to the scan frame", icon = icons.get("scan_frame")),
            "fit_to_range": MSB(tooltip = "Snap the view range to the total piezo range", icon = icons.get("piezo_range")),
            "full_data_range": MSB(tooltip = sivr + "to the full data range\n(U)", icon = icons.get("100")),
            "percentiles": MSB(tooltip = sivr + "by percentiles\n(R)", icon = icons.get("percentiles")),
            "standard_deviation": MSB(tooltip = sivr + "by standard deviations\n(D)", icon = icons.get("deviation")),
            "absolute_values": MSB(tooltip = sivr + "by absolute values\n(A)", icon = icons.get("numbers")),
            
            "bg_none": MSB(states = [{"tooltip": "None\n(0)", "icon": self.icons.get("0_2"), "color": self.colors["off-black"]}, {"color": self.colors["blue"]}]),
            "bg_plane": MSB(states = [{"tooltip": "Plane\n(0)", "icon": self.icons.get("plane_subtract"), "color": self.colors["off-black"]}, {"color": self.colors["blue"]}]),
            "bg_linewise": MSB(states = [{"tooltip": "Linewise\n(0)", "icon": self.icons.get("lines"), "color": self.colors["off-black"]}, {"color": self.colors["blue"]}]),
            "bg_inferred": MSB(states = [{"tooltip": "None\n(0)", "icon": self.icons.get("0_2"), "color": self.colors["off-black"]}, {"color": self.colors["blue"]}]),
            
            "sobel": MSB(tooltip = "Compute the complex gradient d/dx + i d/dy\n(Shift + S)", icon = self.icons.get("sobel"), states = [{"color": self.colors["off-black"]}, {"color": self.colors["blue"]}]),
            "laplace": MSB(tooltip = "Compute the Laplacian (d/dx)^2 + (d/dy)^2\n(Shift + L)", icon = self.icons.get("laplacian"), states = [{"color": self.colors["off-black"]}, {"color": self.colors["blue"]}]),
            "fft": MSB(tooltip = "Compute the 2D Fourier transform\n(Shift + F)", icon = self.icons.get("fourier"), states = [{"color": self.colors["off-black"]}, {"color": self.colors["blue"]}]),
            "normal": MSB(tooltip = "Compute the z component of the surface normal\n(Shift + N)", icon = self.icons.get("surface_normal"), states = [{"color": self.colors["off-black"]}, {"color": self.colors["blue"]}]),
            "gaussian": MSB(tooltip = "Gaussian blur applied\n(Shift + G) or provide a width to toggle", icon = self.icons.get("gaussian"), states = [{"color": self.colors["off-black"]}, {"color": self.colors["blue"]}]),
            "rot_trans": MSB(tooltip = "Show the scan in the scan window coordinates\nwith rotation and translation\n(R)", icon = self.icons.get("rot_trans"), states = [{"color": self.colors["off-black"]}, {"color": self.colors["blue"]}]),
            
            "audio": MSB(icon = icons.get("audio"), states = [{"name": "off", "tooltip": "Auditory feedback of current signal\nOFF", "color": self.colors["dark_red"]},
                                                              {"name": "on", "tooltip": "Auditory feedback of current signal\nOFF", "color": self.colors["blue"]}])
        }
        
        [buttons.update({f"get_{parameter_type}_parameters": MSB(tooltip = "Get parameters", icon = icons.get("get"))}) for parameter_type in ["scan", "coarse", "gain", "speed", "frame", "grid", "feedback", "lockin"]]
        [buttons.update({f"set_{parameter_type}_parameters": MSB(tooltip = "Set the new parameters", icon = icons.get("set"))}) for parameter_type in ["scan", "coarse", "gain", "speed", "frame", "grid", "feedback", "lockin"]]
        [buttons.update({f"experiment_{i}": MSB(tooltip = f"experiment button {i}", icon = icons.get(f"{i}"))}) for i in range(6)]

        for i in range(6):
            buttons.update({f"scan_parameters_{i}": MSB(tooltip = f"Load scan parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"coarse_parameters_{i}": MSB(tooltip = f"Load coarse parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"gain_parameters_{i}": MSB(tooltip = f"Load gain parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"speed_parameters_{i}": MSB(tooltip = f"Load speed parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"grid_parameters_{i}": MSB(tooltip = f"Load grid parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"parameters_{i}": MSB(tooltip = f"Parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})

        # Initialize
        buttons["frame_aspect"].setState(1)

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
        CB = STWidgets.STCheckBox
        
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
            
            "approach_fb_parameters": CB(name = "approach_fb_parameters", tooltip = "What feedback parameter set to use transiently during tip approach")
        }
        
        # Add the button handles to the tooltips
        [comboboxes[name].changeToolTip(f"gui.comboboxes[\"{name}\"]", line = 10) for name in comboboxes.keys()]
        
        comboboxes["experiment"].setSizeAdjustPolicy(CB.SizeAdjustPolicy.AdjustToContents)
        
        return comboboxes

    def make_line_edits(self) -> dict:
        buttons = self.buttons
        LE = STWidgets.PhysicsLineEdit
        
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
            "V_nanonis": LE(tooltip = "Nanonis bias\n(Ctrl + P) to set", unit = "V", limits = [-10, 10], digits = 3),
            "V_mla": LE(tooltip = "MLA bias\n(Ctrl + P) to set", unit = "V", limits = [-10, 10], digits = 3),
            "V_keithley": LE(tooltip = "Keithley bias\n(Ctrl + P) to set", unit = "V", limits = [-200, 200], digits = 3),

            "dV_nanonis": LE(tooltip = "voltage step dV when ramping the bias", unit = "mV", limits = [-1000, 1000], digits = 1),
            "dt_nanonis": LE(tooltip = "time step dt when ramping the bias", unit = "ms", limits = [-1000, 1000], digits = 0),
            "dz_nanonis": LE(tooltip = "height step dz when ramping the bias\nTemporarily retract the tip by this amount when ramping to a different polarity", unit = "nm", limits = [-200, 200], digits = 1),

            "dV_keithley": LE(tooltip = "voltage step dV when ramping the Keithley bias", unit = "mV", limits = [-1000, 1000], digits = 1),
            "dt_keithley": LE(tooltip = "time step dt when ramping the Keithley bias", unit = "ms", limits = [-1000, 1000], digits = 0),

            "I_fb": LE(tooltip = "feedback current\n(Ctrl + P) to set", unit = "pA", digits = 0),
            "I_keithley": LE(tooltip = "keithley current", unit = "pA", digits = 0),
            "I_limit": LE(tooltip = "maximum Keithley current", unit = "pA", digits = 0),

            "p_gain": LE(tooltip = "proportional gain", unit = "pm", digits = 0),
            "t_const": LE(tooltip = "time constant", unit = "us", digits = 0),
            "i_gain": LE(tooltip = "integral gain", unit = "nm/s", digits = 0),
            
            "v_fwd": LE(tooltip = "forward scan speed", unit = "nm/s", digits = 2),
            "v_bwd": LE(tooltip = "backward scan speed", unit = "nm/s", digits = 2),
            "v_tip": LE(tooltip = "tip move speed", unit = "nm/s", digits = 2),
            
            # Frame
            "frame_height": LE(tooltip = "frame height", unit = "nm", limits = [0, 1000], digits = 1),
            "frame_width": LE(tooltip = "frame width", unit = "nm", limits = [0, 1000], digits = 1),
            "frame_x": LE(tooltip = "frame offset (x)", unit = "nm", limits = [-1000, 1000], digits = 1),
            "frame_y": LE(tooltip = "frame offset (y)", unit = "nm", limits = [-1000, 1000], digits = 1),
            "frame_angle": LE(tooltip = "frame angle", unit = "deg", limits = [-180, 360], digits = 1),
            "frame_aspect": LE(value = 1, tooltip = "frame aspect ratio (height / width)", digits = 4),

            # Grid
            "grid_pixels": LE(tooltip = "number of pixels", unit = "px", limits = [1, 10000], digits = 0),
            "grid_lines": LE(tooltip = "number of lines", unit = "px", limits = [1, 10000], digits = 0),
            "grid_aspect": LE(tooltip = "grid aspect ratio (lines / pixels)", digits = 4),
            "pixel_width": LE(tooltip = "pixel width", unit = "nm", digits = 4),
            "pixel_height": LE(tooltip = "pixel height", unit = "nm", digits = 4),
            
            # Tip shaper
            "pulse_voltage": LE(tooltip = "voltage to apply to the tip when pulsing", unit = "V", limits = [-10, 10], digits = 1),
            "pulse_duration": LE(tooltip = "duration of the voltage pulse", unit = "ms", limits = [0, 5000], digits = 0),
            
            # STS
            "V_min_STS": LE(tooltip = "starting bias", unit = "V", limits = [-10, 10], digits = 3),
            "V_max_STS": LE(tooltip = "end bias", unit = "V", limits = [-10, 10], digits = 3),
            "dV_STS": LE(tooltip = "bias step value", unit = "mV", limits = [0, 10000], digits = 1),
            "points_STS": LE(tooltip = "number of data points in sweep", unit = "pts", limits = [1, 10000], digits = 0),
            "t_integration": LE(tooltip = "integration time per data point", unit = "ms", limits = [0, 10000], digits = 0),
            "t_settle": LE(tooltip = "settling time per data point", unit = "ms", limits = [0, 10000], digits = 0),
            
            # Lockins
            "nanonis_mod1_f": LE(tooltip = "Nanonis modulator 1 frequency", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70),
            "nanonis_mod1_mV": LE(tooltip = "Nanonis modulator 1 amplitude", unit = "mV", limits = [0, 5000], digits = 1, min_width = 70),
            "nanonis_mod1_phi": LE(tooltip = "Nanonis modulator 1 phase", unit = "deg", limits = [-180, 360], digits = 1, min_width = 70),
            "nanonis_mod1_t": LE(tooltip = "Nanonis modulator 1 time constant", unit = "ms", limits = [0, 10000], digits = 2, min_width = 70),
            "nanonis_mod2_f": LE(tooltip = "Nanonis modulator 2 frequency", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70),
            "nanonis_mod2_mV": LE(tooltip = "Nanonis modulator 2 amplitude", unit = "mV", limits = [0, 5000], digits = 1, min_width = 70),
            "nanonis_mod2_phi": LE(tooltip = "Nanonis modulator 2 phase", unit = "deg", limits = [-180, 360], digits = 1, min_width = 70),
            "nanonis_mod2_t": LE(tooltip = "Nanonis modulator 2 time constant", unit = "ms", limits = [0, 10000], digits = 2, min_width = 70),

            "mla_mod1_f": LE(tooltip = "MLA modulator 1 frequency", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70),
            "mla_mod1_mV": LE(tooltip = "MLA modulator 1 amplitude", unit = "mV", limits = [0, 5000], digits = 1, min_width = 70),
            "mla_mod1_phi": LE(tooltip = "MLA modulator 1 phase", unit = "deg", limits = [-180, 360], digits = 1, min_width = 70),
            "mla_mod1_t": LE(tooltip = "MLA modulator 1 time constant", unit = "ms", limits = [0, 10000], digits = 2, min_width = 70),

            # Image processing
            "min_full": LE(tooltip = "minimum value of scan data range", digits = 3, max_width = 70),
            "max_full": LE(tooltip = "maximum value of scan data range", digits = 3, max_width = 70),
            "min_percentiles": LE(value = 1.0, tooltip = "minimum percentile of data range", unit = "%", digits = 1, max_width = 70),
            "max_percentiles": LE(value = 99.0, tooltip = "maximum percentile of data range", unit = "%", digits = 1, max_width = 70),
            "min_deviations": LE(value = 2.0, tooltip = "minimum = mean - n * standard deviation", unit = "\u03C3", digits = 1, max_width = 70),
            "max_deviations": LE(value = 2.0, tooltip = "maximum = mean + n * standard deviation", unit = "\u03C3", digits = 1, max_width = 70),
            "min_absolute": LE(value = 0, tooltip = "minimum absolute value", digits = 3, max_width = 70),
            "max_absolute": LE(value = 1, tooltip = "maximum absolute value", digits = 3, max_width = 70),

            "gaussian_width": LE(value = 0.000, tooltip = "width for Gaussian blur application", unit = "nm", digits = 3, max_width = 70),
            "file_name": LE(tooltip = "base name of the file when saved to png or hdf5"),
            
            # Console            
            "input": LE(tooltip = "Enter a command\n(Enter to evaluate)", block = True)
        }
        
        [line_edit.setEditedColor(self.colors["dark_green"]) for name, line_edit in line_edits.items() if name not in ["input", "gaussian_width", "file_name", "experiment_filename"]]
        
        # Extra line edits
        [line_edits.update({f"demod_frequency_{i}": LE(value = 100 * i, tooltip = f"frequency of harmonic {i}", unit = "Hz", digits = 2)}) for i in range(32)]
        [line_edits.update({f"experiment_{i}": LE(tooltip = f"Experiment parameter field {i}")}) for i in range(9)]
        
        # Named groups
        self.parameter_line_0 = [buttons["tip"], line_edits["V_nanonis"], buttons["V_swap"], line_edits["V_mla"], line_edits["I_fb"], buttons["set_scan_parameters"], buttons["get_scan_parameters"]]
        self.parameter_line_1 = [line_edits[name] for name in ["p_gain", "t_const", "v_fwd", "v_bwd"]]

        self.experiment_parameter_fields = [line_edits[f"experiment_{i}"] for i in range(9)]

        self.gain_line_edits = [line_edits[name] for name in ["p_gain", "t_const", "i_gain"]]
        
        self.action_line_edits = [line_edits[name] for name in ["z_steps", "h_steps", "minus_z_steps"]]
        self.min_line_edits = [line_edits[name] for name in ["min_full", "min_percentiles", "min_deviations", "min_absolute"]]
        self.max_line_edits = [line_edits[name] for name in ["max_full", "max_percentiles", "max_deviations", "max_absolute"]]

        self.frame_widgets = [line_edits[name] for name in ["frame_height", "frame_width", "frame_x", "frame_y", "frame_angle", "frame_aspect"]]
        self.grid_widgets = [line_edits[name] for name in ["grid_lines", "grid_pixels", "grid_aspect"]]
        
        self.modulator_widgets = [buttons["nanonis_mod1"], line_edits["nanonis_mod1_mV"], line_edits["nanonis_mod1_phi"], line_edits["nanonis_mod1_f"], line_edits["nanonis_mod1_t"],
                                  buttons["nanonis_mod2"], line_edits["nanonis_mod2_mV"], line_edits["nanonis_mod2_phi"], line_edits["nanonis_mod2_f"], line_edits["nanonis_mod2_t"],
                                  buttons["mla_mod1"], line_edits["mla_mod1_mV"], line_edits["mla_mod1_phi"], line_edits["mla_mod1_f"], line_edits["mla_mod1_t"]]
        
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
            "task": PB(tooltip = "Task progress"),
            "experiment": PB(tooltip = "Experiment progress")
        }
        
        [progress_bars[name].setMinimumWidth(60) for name in progress_bars.keys()]
        [progress_bars[name].setMaximumWidth(60) for name in progress_bars.keys()]
        
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
            
            "feedback": make_layout("g"),
            "feedback_getset": make_layout("h"),
            
            "gains_line_edits": make_layout("h"),
            "gains": make_layout("v"),
            "gains_getset": make_layout("h"),

            "speeds": make_layout("g"),
            "speeds_getset": make_layout("h"),
            "speeds_parameter_sets": make_layout("h"),
            
            "frame_grid": make_layout("g"),
            "frame": make_layout("g"),
            "grid": make_layout("g"),
            "frame_grid_parameter_sets": make_layout("h"),

            "lockins": make_layout("g"),
            "lockin_parameter_sets": make_layout("h"),

            "channel_navigation": make_layout("h"),

            "coarse_vertical": make_layout("g"),
            "coarse_horizontal": make_layout("g"),
            "approach_percentiles": make_layout("h"),
            
            "modulators": make_layout("g"),
            "mod_set_get": make_layout("h"),
            "demodulators": make_layout("v"),
            "volume": make_layout("h"),
            "demod_sliders": make_layout("h"),

            "background_buttons": make_layout("h"),
            "matrix_processing": make_layout("g"),
            "limits": make_layout("g"),
            "empty": make_layout("v"),
            
            "input": make_layout("h"),
            "experiment_controls_0": make_layout("v"),
            "experiment_controls_1": make_layout("h"),
            "experiment_fields": make_layout("g"),
            "experiment_buttons": make_layout("h"),
            
            "graph": make_layout("h"),
            "channels": make_layout("g"),

            "connections": make_layout("g"),
            "coarse_control": make_layout("h"),
            "coarse_prep": make_layout("v"),
            "tip_prep": make_layout("g"),
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
            "coarse_prep": QWgt(),
            "frame_grid": QWgt(),
            "tip_prep": QWgt(),
            "parameters": QWgt(),
            "image_processing": QWgt(),
            "experiment": QWgt(),
            "lockins": QWgt(),
            "demodulators": QWgt()
        }
        
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

    def make_sliders(self) -> dict:
        SL = STWidgets.Slider
        PS = STWidgets.PhaseSlider
        SLE = STWidgets.SliderLineEdit
        
        sliders = {
            "tip": SL(tooltip = "tip height (nm)", orientation = "v"),
            "volume": SLE(tooltip = "volume", orientation = "h", limits = [0, 100], unit = "%", minmax_buttons = True, min_button_icon = self.icons.get("0"), max_button_icon = self.icons.get("100")),
            "phase": PS(tooltip = "Set complex phase phi\n(= multiplication by exp(i * pi * phi rad / (180 deg)))", unit = "deg", phase_0_icon = self.icons.get("0"), phase_180_icon = self.icons.get("180"))
        }

        for harmonic in range(32):
            initial_val = 100 if harmonic > 0 else 0
            sle = SLE(tooltip = f"relative volume of harmonic {harmonic}", orientation = "v", limits = [0, 100], initial_val = initial_val, digits = 0, unit = "%",
                      minmax_buttons = True, min_button_icon = self.icons.get("0"), max_button_icon = self.icons.get("100"))
            
            self.labels[f"demod_harmonic_{harmonic}"].setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.line_edits[f"demod_frequency_{harmonic}"].setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            
            sle.widget_layout.insertWidget(0, self.line_edits[f"demod_frequency_{harmonic}"])
            sle.widget_layout.insertWidget(0, self.labels[f"demod_harmonic_{harmonic}"])

            sliders.update({f"f{harmonic}": sle})

        [widget.setEnabled(False) for widget in [sliders["f0"].slider, sliders["f0"].line_edit, sliders["f0"].min_button, sliders["f0"].max_button, self.line_edits[f"demod_frequency_0"]]]
        
        self.demod_scroller = QtWidgets.QScrollArea()
        self.demod_scroller.setWidgetResizable(True)

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
            "open_file": QtWidgets.QFileDialog()
                   }
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
        align_center = QtCore.Qt.AlignmentFlag.AlignCenter
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
        layouts["experiment_controls_0"].addWidget(buttons["start_stop"])
        [layouts["experiment_controls_0"].addWidget(self.progress_bars[name]) for name in ["task", "experiment"]]
        
        [layouts["experiment_controls_1"].addWidget(widget) for widget in [buttons["save"], line_edits["experiment_filename"]]]
        [layouts["experiment_fields"].addWidget(widget, int(index / 3), index % 3) for index, widget in enumerate(self.experiment_parameter_fields)] # Grid of experiment fields
        [layouts["experiment_buttons"].addWidget(buttons[f"experiment_{i}"]) for i in range(6)] # Grid of experiment fields
        e_layout = layouts["experiment"]
        e_layout.addLayout(layouts["experiment_controls_0"], 0, 0, 4, 1)
        e_layout.addWidget(self.sliders["tip"], 0, 1, 4, 1)
        e_layout.addWidget(self.comboboxes["experiment"], 0, 2)
        e_layout.addWidget(self.comboboxes["direction"], 0, 3)
        e_layout.addLayout(layouts["experiment_controls_1"], 1, 2, 1, 2)
        e_layout.addWidget(self.line_edits["experiment_filename"], 2, 3)
        e_layout.addWidget(buttons["tip"], 0, 4, 2, 1)
        e_layout.addLayout(layouts["experiment_fields"], 2, 2, 1, 3)
        e_layout.addLayout(layouts["experiment_buttons"], 3, 2, 1, 3)
        
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
        
        # Feedback
        [layouts["feedback_getset"].addWidget(buttons[name]) for name in ["get_feedback_parameters", "set_feedback_parameters"]]
        
        fb_layout = layouts["feedback"]
        [fb_layout.addWidget(labels[name], 0, index) for index, name in enumerate(["nanonis", "mla", "keithley"])]
        fb_layout.addWidget(make_line("h", 1), 1, 0, 1, 3)
        [fb_layout.addWidget(line_edits[name], 2, index) for index, name in enumerate(["V_nanonis", "V_mla", "V_keithley"])]
        buttons["V_swap"].setFixedWidth(50)
        fb_layout.addWidget(buttons["V_swap"], 3, 0, 1, 2, align_center)
        
        [fb_layout.addWidget(line_edits[name], 4 + index, 0) for index, name in enumerate(["dV_nanonis", "dt_nanonis"])]
        [fb_layout.addWidget(line_edits[name], 4 + index, 1) for index, name in enumerate(["dz_nanonis", "I_fb"])]
        [fb_layout.addWidget(line_edits[name], 4 + index, 2) for index, name in enumerate(["dV_keithley", "dt_keithley"])]
        fb_layout.addLayout(layouts["feedback_getset"], 6, 0, 1, 3)

        # Gains
        [layouts["gains_line_edits"].addWidget(widget) for widget in self.gain_line_edits]
        [layouts["gains_getset"].addWidget(widget) for widget in [buttons["get_gain_parameters"], buttons["set_gain_parameters"], comboboxes["gains"]]]
        layouts["gains"].addLayout(layouts["gains_line_edits"])
        layouts["gains"].addLayout(layouts["gains_getset"])
        
        # Frame_grid
        [layouts["frame_grid_parameter_sets"].addWidget(buttons[f"grid_parameters_{i}"]) for i in range(6)]
        
        fg_layout = layouts["frame_grid"]
        fg_layout.addWidget(labels["frame"], 0, 0, 1, 2)
        fg_layout.addWidget(make_line("h", 1), 1, 0, 1, 2)
        fg_layout.addWidget(buttons["frame_aspect"], 2, 0, 1, 1, align_center)
        fg_layout.addWidget(line_edits["frame_height"], 2, 1)
        [fg_layout.addWidget(line_edits[name], 3 + int(index / 2), index % 2) for index, name in enumerate(["frame_width", "frame_aspect", "frame_x", "frame_y"])]
        fg_layout.addWidget(line_edits["frame_angle"], 5, 0, 1, 2)
        fg_layout.addWidget(buttons["get_frame_parameters"], 6, 0, 1, 1, align_center)
        fg_layout.addWidget(buttons["set_frame_parameters"], 6, 1, 1, 1, align_center)
        
        fg_layout.addWidget(labels["empty"], 0, 2)
        
        fg_layout.addWidget(labels["grid"], 0, 3, 1, 2)
        fg_layout.addWidget(make_line("h", 1), 1, 3, 1, 2)
        fg_layout.addWidget(buttons["grid_aspect"], 2, 3, 1, 1, align_center)
        fg_layout.addWidget(line_edits["grid_lines"], 2, 4)
        [fg_layout.addWidget(line_edits[name], 3 + int(index / 2), 3 + index % 2) for index, name in enumerate(["grid_pixels", "grid_aspect", "pixel_width", "pixel_height"])]
        fg_layout.addWidget(buttons["get_grid_parameters"], 6, 3, 1, 1, align_center)
        fg_layout.addWidget(buttons["set_grid_parameters"], 6, 4, 1, 1, align_center)
        
        # Tip prep
        tp_layout = layouts["tip_prep"]
        [tp_layout.addWidget(labels[name], 0, 2 * index, 1, 2) for index, name in enumerate(["pulse", "shape"])]
        [tp_layout.addWidget(make_line("h", 1), 1, 2 * index, 1, 2) for index in range(2)]
        [tp_layout.addWidget(widget, 2, index, 1, 1, align_center) for index, widget in enumerate([buttons["bias_pulse"], line_edits["pulse_voltage"], line_edits["pulse_duration"], buttons["tip_shape"]])]
        
        # Lockins
        [layouts["mod_set_get"].addWidget(buttons[name]) for name in ["get_lockin_parameters", "set_lockin_parameters"]]
        [layouts["modulators"].addWidget(widget, int(i / 5), i % 5) for i, widget in enumerate(self.modulator_widgets)]
        layouts["modulators"].addLayout(layouts["mod_set_get"], 3, 0, 1, 4)
        
        [layouts["volume"].addWidget(widget) for widget in [buttons["audio"], self.sliders["volume"]]]
        layouts["demodulators"].addLayout(layouts["volume"])
        [layouts["demod_sliders"].addWidget(self.sliders[f"f{i}"]) for i in range(32)]
        self.widgets["demodulators"].setLayout(layouts["demod_sliders"])
        self.demod_scroller.setWidget(self.widgets["demodulators"])
        layouts["demodulators"].addWidget(self.demod_scroller)
        
        # Image processing                
        cn_layout = layouts["channel_navigation"]
        cn_layout.addWidget(comboboxes["channels"], 4)
        cn_layout.addWidget(self.buttons["direction"], 1)
        [cn_layout.addWidget(self.buttons[name], 1) for name in ["fit_to_frame", "fit_to_range"]]
        
        [layouts["background_buttons"].addWidget(button) for button in self.background_buttons]
        layouts["background_buttons"].addWidget(buttons["rot_trans"])
        p_layout = layouts["matrix_processing"]
        [p_layout.addWidget(buttons[name], 0, index) for index, name in enumerate(["sobel", "normal", "laplace", "fft", "gaussian"])]
        p_layout.addWidget(line_edits["gaussian_width"], 0, 5)
        p_layout.addWidget(comboboxes["projection"], 1, 0, 1, 2)
        p_layout.addWidget(self.sliders["phase"], 1, 2, 1, 4)
        
        l_layout = layouts["limits"]
        l_layout.setAlignment(align_center)
        self.limits_columns = [self.min_line_edits, self.min_radio_buttons, self.scale_buttons, self.max_radio_buttons, self.max_line_edits]
        for j, group in enumerate(self.limits_columns): [l_layout.addWidget(item, i, j) for i, item in enumerate(group)]

        ip_layout = layouts["image_processing"]
        ip_layout.addWidget(labels["scan_control"])
        ip_layout.addLayout(layouts["channel_navigation"])
        ip_layout.addWidget(make_line("h", 1))
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
            "coarse_vertical": SGB(title = "Vertical", tooltip = "Vertical coarse motion"),
            "coarse_horizontal": SGB(title = "Horizontal", tooltip = "Horizontal coarse motion"),
            
            "tip_prep": SGB(title = "Tip prep", tooltip = "Tip preparation tools"),

            "frame_grid": SGB(title = "Frame / grid", tooltip = "Frame and grid parameters"),
            "feedback": SGB(title = "Bias / current", tooltip = "Bias and current"),
            "gains": SGB(title = "Feedback gains", tooltip = "Feedback gains"),
            "modulators": SGB(title = "Modulators", tooltip = "Modulators"),
            "demodulators": SGB(title = "Demodulators", tooltip = "Demodulators"),

            "speeds": SGB(title = "Speeds", tooltip = "Speeds"),
            "parameters": SGB(title = "Scan parameters", tooltip = "Scan parameters"),
            "image_processing": SGB(title = "Image processing", tooltip = "Select the background subtraction, matrix operations and set the image range limits (use shift key to access these functions)"),
            "experiment": SGB(title = "Experiment", tooltip = "Perform experiment"),
            
            "dummy": SGB(title = "Dummy", tooltip = "Invisible groupbox to swap out layouts to make other groupboxes collapse")
        }

        # Set layouts for the groupboxes
        groupbox_names = ["connections", "coarse_horizontal", "coarse_vertical", "feedback", "gains", "speeds", "frame_grid", "tip_prep", "parameters", "modulators", "demodulators", "experiment", "image_processing"]
        [groupboxes[name].setLayout(layouts[name]) for name in groupbox_names]

        # Make layouts of several groupboxes
        [layouts["coarse_control"].addWidget(groupboxes[name], 1) for name in ["coarse_horizontal", "coarse_vertical"]]
        layouts["coarse_prep"].addLayout(layouts["coarse_control"])
        layouts["coarse_prep"].addWidget(groupboxes["tip_prep"])
        
        [layouts["parameters"].addWidget(groupboxes[name]) for name in ["feedback", "gains", "speeds", "frame_grid"]]
        [layouts["lockins"].addWidget(groupboxes[name]) for name in ["modulators", "demodulators"]]

        return groupboxes



    # 5: Make the tab widget
    def make_tab_widget(self) -> QtWidgets.QTabWidget:
        tab_widget = QtWidgets.QTabWidget()
        
        tabs = ["parameters", "coarse_prep", "image_processing", "lockins"]
        tab_names = ["Parameters", "Coarse/Prep", "Processing", "Lock-ins"]
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
        
        [self.line_edits[name].editingFinished.connect(lambda name_0 = name: self.update_reciprocals(name_0)) for name in ["nanonis_mod1_f", "nanonis_mod2_f", "mla_mod1_f", "nanonis_mod1_t", "nanonis_mod2_t", "mla_mod1_t"]]
        
        return

    def update_reciprocals(self, target: str = "mla_mod1_f"):
        match target:
            case "nanonis_mod1_f":
                f_Hz = self.line_edits["nanonis_mod1_f"].getValue()
                t_ms = 1000 / f_Hz
                self.line_edits["nanonis_mod1_t"].setValue(t_ms)
            case "nanonis_mod2_f":
                f_Hz = self.line_edits["nanonis_mod2_f"].getValue()
                t_ms = 1000 / f_Hz
                self.line_edits["nanonis_mod2_t"].setValue(t_ms)
            case "mla_mod1_f":
                f_Hz = self.line_edits["mla_mod1_f"].getValue()
                t_ms = 1000 / f_Hz
                self.line_edits["mla_mod1_t"].setValue(t_ms)

            case "nanonis_mod1_t":
                t_ms = self.line_edits["nanonis_mod1_t"].getValue()
                f_Hz = 1000 / t_ms
                self.line_edits["nanonis_mod1_f"].setValue(f_Hz)
            case "nanonis_mod2_t":
                t_ms = self.line_edits["nanonis_mod2_t"].getValue()
                f_Hz = 1000 / t_ms
                self.line_edits["nanonis_mod2_f"].setValue(f_Hz)
            case "mla_mod1_f":
                t_ms = self.line_edits["mla_mod1_t"].getValue()
                f_Hz = 1000 / t_ms
                self.line_edits["mla_mod1_f"].setValue(f_Hz)
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

                if bool(self.buttons["frame_aspect"].state_index):
                    frame_aspect = self.line_edits["frame_aspect"].getValue()

                    if isinstance(frame_aspect, float) or isinstance(frame_aspect, int):
                        frame_height = frame_width * frame_aspect
                        self.line_edits["frame_height"].setValue(frame_height)
                        self.line_edits["frame_height"].setColor()
                else:
                    frame_height = self.line_edits["frame_height"].getValue()

                    print(f"Frame height = {frame_height}")

                    if isinstance(frame_height, float) or isinstance(frame_height, int):
                        frame_aspect = frame_height / frame_width
                        self.line_edits["frame_aspect"].setValue(frame_aspect)
                        self.line_edits["frame_aspect"].setColor()

            case "frame_height":
                frame_height = self.line_edits["frame_height"].getValue()
                if not isinstance(frame_height, float) and not isinstance(frame_height, int): return

                if self.buttons["frame_aspect"].isChecked():
                    frame_aspect = self.line_edits["frame_aspect"].getValue()

                    if isinstance(frame_aspect, float) or isinstance(frame_aspect, int):
                        frame_width = frame_height / frame_aspect
                        self.line_edits["frame_width"].setValue(frame_width)
                        self.line_edits["frame_width"].setColor()
                else:
                    frame_width = self.line_edits["frame_width"].getValue()
                    
                    if isinstance(frame_width, float) or isinstance(frame_width, int):
                        frame_aspect = frame_height / frame_width
                        self.line_edits["frame_aspect"].setValue(frame_aspect)
                        self.line_edits["frame_aspect"].setColor()

            case "frame_aspect":
                frame_aspect = self.line_edits["frame_aspect"].getValue()
                if not isinstance(frame_aspect, float) and not isinstance(frame_aspect, int): return

                frame_width = self.line_edits["frame_width"].getValue()
                if isinstance(frame_width, float) or isinstance(frame_width, int):
                    frame_height = frame_width * frame_aspect
                    self.line_edits["frame_height"].setValue(frame_height)
                    self.line_edits["frame_height"].setColor()

            case _:
                pass

        [self.line_edits[name].blockSignals(False) for name in ["frame_width", "frame_height", "frame_aspect"]]
        return

    def update_fields_from_frame_change(self) -> None:
        [self.line_edits[name].blockSignals(True) for name in ["frame_x", "frame_y", "frame_width", "frame_height", "frame_angle"]]
        
        new_width = self.new_frame_roi.size().x()
        self.line_edits["frame_width"].setValue(new_width)
        self.line_edits["frame_width"].setColor()
        
        if bool(self.buttons["frame_aspect"].state_index):
            new_height = new_width * self.line_edits["frame_aspect"].getValue()
            
            self.new_frame_roi.blockSignals(True)
            self.new_frame_roi.setSize([new_width, new_height])
            self.new_frame_roi.blockSignals(False)
        else:
            new_height = self.new_frame_roi.size().y()
            self.line_edits["frame_aspect"].setValue(new_height / new_width)
            self.line_edits["frame_aspect"].setColor()
        
        self.line_edits["frame_height"].setValue(new_height)
        self.line_edits["frame_height"].setColor()
                
        bounding_rect = self.new_frame_roi.boundingRect()
        local_center = bounding_rect.center()
        abs_center = self.new_frame_roi.mapToParent(local_center)
        
        self.line_edits["frame_x"].setValue(abs_center.x())
        self.line_edits["frame_y"].setValue(abs_center.y())
        
        self.line_edits["frame_x"].setColor()
        self.line_edits["frame_y"].setColor()
        
        self.line_edits["frame_angle"].setValue(-self.new_frame_roi.angle())
        self.line_edits["frame_angle"].setColor()
        
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
