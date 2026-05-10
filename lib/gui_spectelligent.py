import os, sys
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
from . import SCTWidgets, rotate_icon, make_layout, make_line



class SpectelligentGUI(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        
        self.color_list = ["#FFFFFF", "#FFFF20", "#20FFFF", "#FF80FF", "#60FF60", "#FF6060", "#8080FF", "#B0B0B0", "#FFB010", "#A050FF",
                           "#909020", "#00A0A0", "#B030A0", "#40B040", "#B04040", "#5050E0", "#C00000", "#905020", "#707000", "#2020ff",
                           "#CFCFCF", "#CFCF20", "#20CFCF", "#CF60CF", "#60CF60", "#CF6060", "#8080CF", "#909090", "#CFB010", "#C050FF",
                           "#606020", "#00C0C0", "#B030C0", "#409040", "#904040", "#505090", "#900000", "#605020", "#404000", "#2020Cf"]
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
        self.checkboxes = self.make_checkboxes()
        self.comboboxes = self.make_comboboxes()
        self.line_edits = self.make_line_edits()
        self.progress_bars = self.make_progress_bars()
        self.layouts = self.make_layouts()
        self.image_view = self.make_image_view()
        (self.piezo_roi, self.frame_roi, self.new_frame_roi) = self.make_rois()
        (self.waveform_widget, self.waveforms, self.plot_widget, self.pdis) = self.make_plot_widgets()
        self.limits_widget = self.make_limits_widget()
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

            "scan_control": LB(text = "Navigation"),
            "limits": LB(text = "Limits"),
            "background_subtraction": LB(text = "Background subtraction"),
            "matrix_operations": LB(text = "Matrix operations"),

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
                        states = [{"name": "none", "tooltip": "Toggle the active view", "icon": icons.get("eye"), "color": sct_black},
                                  {"name": "camera", "tooltip": "Active view: Camera", "icon": icons.get("view_camera"), "color": sct_black},
                                  {"name": "nanonis", "tooltip": "Active view: Nanonis", "icon": icons.get("view_nanonis"), "color": sct_black}]),
            "exit": MSB(tooltip = "Exit scantelligent\n(Esc / X / E)", icon = icons.get("escape"), size = 28),
            "session_folder": MSB(icon = icons.get("folder_yellow"), click_to_toggle = False,
                                  states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Session folder unknown"},
                                            {"name": "online", "color": self.colors["dark_green"], "tooltip": "Open the session folder"}]),
            "info": MSB(tooltip = "Info", icon = icons.get("i")),
            
            # Experiment
            "save": MSB(tooltip = "Save the experiment results to file", icon = icons.get("floppy")),
            "start_stop": MSB(click_to_toggle = False, size = 28,
                              states = [{"name": "load", "color": self.colors["dark_red"], "tooltip": "Load/reset experiment", "icon": icons.get("start")},
                                        {"name": "ready", "color": self.colors["dark_green"], "tooltip": "Start experiment", "icon": icons.get("start")},
                                        {"name": "running", "color": sct_blue, "tooltip": "Experiment running", "icon": icons.get("stop")},
                                        {"name": "aborted", "color": self.colors["orange"], "tooltip": "Abort requested", "icon": icons.get("stop")}]),
            "stop": MSB(tooltip = "Stop experiment", icon = icons.get("stop"), size = 28),
            
            # Parameters
            "frame_aspect": MSB(tooltip = "Lock the frame aspect ratio", icon = icons.get("lock_aspect"), states = [{"color": sct_black}, {"color": sct_blue}]),
            "grid_aspect": MSB(tooltip = "Lock the grid aspect ratio", icon = icons.get("lock_aspect"), states = [{"color": sct_black}, {"color": sct_blue}]),
            
            "tip": MSB(click_to_toggle = False, size = 28,
                       states = [{"name": "unknown", "tooltip": "Tip status\nUnknown / withdrawn", "icon": icons.get("tip_unknown"), "color": sct_black},
                                 {"name": "feedback", "tooltip": "Tip status\nIn feedback", "icon": icons.get("constant_current"), "color": self.colors["dark_green"]},
                                 {"name": "constant_height", "tooltip": "Tip status\nConstant height", "icon": icons.get("constant_height"), "color": self.colors["orange"]}]),
            "V_swap": MSB(tooltip = "Swap the bias between Nanonis and the MLA", icon = icons.get("swap")),
            
            # Coarse vertical
            "withdraw": MSB(click_to_toggle = False, states = [{"name": "landed", "tooltip": "Withdraw the tip\n(Ctrl + W)", "icon": icons.get("withdraw"), "color": sct_blue},
                                                               {"name": "withdrawn", "tooltip": "Land the tip\n(Ctrl + W)", "icon": self.icons.get("approach"), "color": sct_black}]),
            "retract": MSB(tooltip = "Retract the tip from the surface\n(Ctrl + PgUp)", icon = icons.get("retract")),
            "advance": MSB(tooltip = "Advance the tip towards the surface\n(Ctrl + PgDown)", icon = icons.get("advance")),
            "approach": MSB(size = 28,
                            states = [{"name": "idle", "tooltip": "Initiate auto approach", "icon": icons.get("start_approach"), "color": sct_black},
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
            "nanonis_mla": MSB(states = [{"name": "mla", "icon": icons.get("imp"), "tooltip": "Use the MLA for spectroscopy"},
                                         {"name": "nanonis", "icon": icons.get("nanonis"), "tooltip": "Use Nanonis for spectroscopy"}]),            
            "nanonis_mod1": MSB(icon = icons.get("nanonis_mod1"),
                                states = [{"name": "off", "tooltip": "Nanonis modulator 1 OFF", "color": sct_black},
                                          {"name": "on", "tooltip": "Nanonis modulator 1 ON", "color": sct_blue}]),
            "nanonis_mod2": MSB(icon = icons.get("nanonis_mod2"),
                                states = [{"name": "off", "tooltip": "Nanonis modulator 2 OFF", "color": sct_black},
                                          {"name": "on", "tooltip": "Nanonis modulator 2 ON", "color": sct_blue}]),
            "mla_mod0": MSB(icon = icons.get("mla_oscillator"),
                            states = [{"name": "off", "tooltip": "MLA modulator 0 OFF", "color": sct_black},
                                      {"name": "on", "tooltip": "MLA modulator 0 ON", "color": sct_blue}]),
            "mla_mod1": MSB(icon = icons.get("mla_oscillator"),
                            states = [{"name": "off", "tooltip": "MLA modulator 1 OFF", "color": sct_black},
                                      {"name": "on", "tooltip": "MLA modulator 1 ON", "color": sct_blue}]),
            "mla_mod2": MSB(icon = icons.get("mla_oscillator"),
                            states = [{"name": "off", "tooltip": "MLA modulator 2 OFF", "color": sct_black},
                                      {"name": "on", "tooltip": "MLA modulator 2 ON", "color": sct_blue}]),
            "mla_mod3": MSB(icon = icons.get("mla_oscillator"),
                            states = [{"name": "off", "tooltip": "MLA modulator 3 OFF", "color": sct_black},
                                      {"name": "on", "tooltip": "MLA modulator 3 ON", "color": sct_blue}]),

            "start_scan": MSB(tooltip = "Start scan", icon = icons.get("start_scan"), size = 28),
            "start_spectrum": MSB(tooltip = "Acquire spectrum", icon = icons.get("start_spectrum"), size = 28),
            
            "sts_V": MSB(states = [{"name": "off", "tooltip": "Check to include a voltage sweep", "color": sct_black, "icon": icons.get("V")},
                                   {"name": "x", "tooltip": "Voltage sweep selected for the x-axis (fast/primary axis)", "color": sct_blue, "icon": icons.get("V_x")},
                                   {"name": "y", "tooltip": "Voltage sweep selected for the y-axis (slow/secondary axis)", "color": sct_blue, "icon": icons.get("V_y")}]),
            "sts_f": MSB(states = [{"name": "off", "tooltip": "Check to include a frequency sweep", "color": sct_black, "icon": icons.get("f")},
                                   {"name": "x", "tooltip": "Frequency sweep selected for the x-axis (fast/primary axis)", "color": sct_blue, "icon": icons.get("f_x")},
                                   {"name": "y", "tooltip": "Frequency sweep selected for the y-axis (slow/secondary axis)", "color": sct_blue, "icon": icons.get("f_y")}]),
            "sts_amp": MSB(states = [{"name": "off", "tooltip": "Check to include an amplitude sweep", "color": sct_black, "icon": icons.get("A")},
                                     {"name": "x", "tooltip": "Amplitude sweep selected for the x-axis (fast/primary axis)", "color": sct_blue, "icon": self.icons.get("A_x")},
                                     {"name": "y", "tooltip": "Amplitude sweep selected for the y-axis (slow/secondary axis)", "color": sct_blue, "icon": self.icons.get("A_y")}]),
            "sts_z": MSB(states = [{"name": "off", "tooltip": "Check to include a height sweep", "color": sct_black, "icon": icons.get("z")},
                                   {"name": "x", "tooltip": "Height sweep selected for the x-axis (fast/primary axis)", "color": sct_blue, "icon": icons.get("z_x")},
                                   {"name": "y", "tooltip": "Height sweep selected for the y-axis (slow/secondary axis)", "color": sct_blue, "icon": icons.get("z_y")}]),
            "sts_V_keithley": MSB(states = [{"name": "off", "tooltip": "Check to include a Keithley voltage sweep", "color": sct_black, "icon": icons.get("V")},
                                            {"name": "x", "tooltip": "Keithley voltage sweep selected for the x-axis (fast/primary axis)", "color": sct_blue, "icon": icons.get("V_x")},
                                            {"name": "y", "tooltip": "Keithley voltage sweep selected for the y-axis (slow/secondary axis)", "color": sct_blue, "icon": icons.get("V_y")}]),
            
            "get_pixel_nanonis": MSB(tooltip = "Click to receive a pixel from Nanonis", icon = icons.get("nanonis")),
            "get_pixel_mla": MSB(tooltip = "Click to receive a pixel from the MLA", icon = icons.get("imp")),
            
            # Processing
            "direction": MSB(tooltip = "Change scan direction\n(X)",
                             states = [{"name": "forward", "icon": icons.get("triple_arrow"), "color": sct_black},
                                       {"name": "backward", "icon": rotate_icon(icons.get("triple_arrow"), angle = 180), "color": sct_blue}]),
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
            "zero_volumes": MSB(icon = icons.get("0"), tooltip = "Zero all relative volumes")
        }
        
        for parameter_type in ["bias", "coarse", "gain", "speed", "frame", "grid", "feedback", "lockin", "tip_shaper", "spectroscopy"]:
            buttons.update({f"get_{parameter_type}_parameters": MSB(tooltip = "Get parameters", icon = icons.get("get"))})
            buttons.update({f"set_{parameter_type}_parameters": MSB(tooltip = "Set the new parameters", icon = icons.get("set"))})
        [buttons.update({f"experiment_{i}": MSB(tooltip = f"experiment button {i}", icon = icons.get(f"{i}"))}) for i in range(6)]

        # Initialize
        [buttons[name].setState(1) for name in ["frame_aspect", "grid_aspect", "bg_none"]]

        # Named groups
        self.connection_buttons = [buttons[name] for name in ["nanonis", "camera", "mla", "keithley", "scanalyzer", "session_folder", "info"]]
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
            "composite_motion": CB(tooltip = "Composite motion:\nWhen checked, combine all checked vertical motions with the horizontal motion in a composite pattern", icon = self.icons.get("composite_motion")),
            
            # STS
            "voltage_sweep": CB(tooltip = "Perform STS in voltage sweep mode"),
            "frequency_sweep": CB(tooltip = "Perform STS in frequency sweep mode"),
            "height_sweep": CB(tooltip = "Perform STS in height sweep mode"),
            
            "single_sweep": CB(tooltip = "Perform single sweep"),
            "amplitude_sweep": CB(tooltip = "Perform iterative STS in amplitude sweep mode"),
            "line_spectroscopy": CB(tooltip = "Perform iterative STS over a line"),
            
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
        [checkboxes.update({f"channel_{index}": CB(tooltip = f"channel {index}", color = self.color_list[index])}) for index in range(40)] # Channels

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
            "channels": BG(exclusive = False, keep_one_checked = False),
            "spec_axes": BG(keep_one_checked = False)
        }
        limit_methods = ["full", "percentiles", "deviations", "absolute"]        
        [self.button_groups["min"].addButton(checkboxes[f"min_{method}"], f"min_{method}") for method in limit_methods]
        [self.button_groups["max"].addButton(checkboxes[f"max_{method}"], f"max_{method}") for method in limit_methods]
        [self.button_groups["background"].addButton(self.buttons[f"bg_{method}"], f"bg_{method}") for method in ["none", "plane", "linewise"]]
        [self.button_groups["channels"].addButton(checkboxes[f"channel_{index}"], f"{index}") for index in range(40)]
        [self.button_groups["spec_axes"].addButton(self.buttons[f"sts_{quantity}"], quantity) for quantity in ["V", "z", "f", "amp", "V_keithley"]]
        
        # Initialize
        checked_buttons = [checkboxes[name] for name in ["min_full", "max_full"]]
        [button.setChecked(True) for button in checked_buttons]

        return checkboxes

    def make_comboboxes(self) -> dict:
        CB = SCTWidgets.ComboBox
        
        comboboxes = {
            "channels": CB(tooltip = "Available scan channels"),
            "projection": CB(tooltip = "Select a projection or toggle with\n(Shift + ↑)", items = ["re", "im", "abs", "arg (b/w)", "arg (hue)", "complex", "abs^2", "log(abs)"]),
            "experiment": CB(tooltip = "Select an experiment"),
            "direction": CB(tooltip = "Select a scan direction / pattern"),
            
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
        }
        
        # Add the button handles to the tooltips
        [comboboxes[name].changeToolTip(f"gui.comboboxes[\"{name}\"]", line = 10) for name in comboboxes.keys()]
        
        comboboxes["experiment"].setSizeAdjustPolicy(CB.SizeAdjustPolicy.AdjustToContents)
        
        return comboboxes

    def make_line_edits(self) -> dict:
        LE = SCTWidgets.PhysicsLineEdit
        ILE = SCTWidgets.InputLineEdit
        RG = SCTWidgets.ReciprocalGroup

        scanalyzer_blue = "#2020C0"
        
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

            "dV_keithley": LE(tooltip = "voltage step dV when ramping the Keithley bias", unit = "mV", limits = [-1000, 1000], digits = 1, edited_color = scanalyzer_blue),
            "dt_keithley": LE(tooltip = "time step dt when ramping the Keithley bias", unit = "ms", limits = [-1000, 1000], digits = 0, edited_color = scanalyzer_blue),
            
            # Feedback
            "I_fb": LE(tooltip = "feedback current", unit = "pA", digits = 0, edited_color = scanalyzer_blue),
            "I_keithley": LE(tooltip = "keithley current", unit = "pA", digits = 0, edited_color = scanalyzer_blue),
            "I_keithley_limit": LE(tooltip = "maximum Keithley current", unit = "pA", digits = 0, edited_color = scanalyzer_blue),
            "I_pA": LE(tooltip = "most recent current measurement", unit = "pA", digits = 0),

            "p_gain": LE(tooltip = "proportional gain", unit = "pm", digits = 0, edited_color = scanalyzer_blue),
            "t_const": LE(tooltip = "time constant", unit = "us", digits = 0, edited_color = scanalyzer_blue),
            "i_gain": LE(tooltip = "integral gain", unit = "nm/s", digits = 0, edited_color = scanalyzer_blue),
            
            "v_fwd": LE(tooltip = "forward scan speed", unit = "nm/s", digits = 2, edited_color = scanalyzer_blue),
            "v_bwd": LE(tooltip = "backward scan speed", unit = "nm/s", digits = 2, edited_color = scanalyzer_blue),
            "v_tip": LE(tooltip = "tip move speed", unit = "nm/s", digits = 2, edited_color = scanalyzer_blue),
            
            # Frame
            "frame_height": LE(tooltip = "frame height", unit = "nm", limits = [0, 1000], digits = 1, edited_color = scanalyzer_blue),
            "frame_width": LE(tooltip = "frame width", unit = "nm", limits = [0, 1000], digits = 1, edited_color = scanalyzer_blue),
            "frame_x": LE(tooltip = "frame offset (x)", unit = "nm", limits = [-2000, 2000], digits = 1, edited_color = scanalyzer_blue),
            "frame_y": LE(tooltip = "frame offset (y)", unit = "nm", limits = [-2000, 2000], digits = 1, edited_color = scanalyzer_blue),
            "frame_angle": LE(tooltip = "frame angle", unit = "deg", limits = [-180, 360], digits = 1, edited_color = scanalyzer_blue),
            "frame_aspect": LE(tooltip = "frame aspect ratio (height / width)", digits = 4, edited_color = scanalyzer_blue),

            # Grid
            "grid_pixels": LE(tooltip = "number of pixels", unit = "px", limits = [1, 10000], digits = 0, edited_color = scanalyzer_blue),
            "grid_lines": LE(tooltip = "number of lines", unit = "px", limits = [1, 10000], digits = 0, edited_color = scanalyzer_blue),
            "grid_aspect": LE(tooltip = "grid aspect ratio (lines / pixels)", digits = 4, edited_color = scanalyzer_blue),
            "pixel_width": LE(tooltip = "pixel width", unit = "nm", digits = 4, edited_color = scanalyzer_blue),
            "pixel_height": LE(tooltip = "pixel height", unit = "nm", digits = 4, edited_color = scanalyzer_blue),
            
            # Tip shaper
            "pulse_voltage": LE(value = 6, tooltip = "voltage to apply to the tip when pulsing", unit = "V", limits = [-10, 10], digits = 1),
            "pulse_duration": LE(value = 300, tooltip = "duration of the voltage pulse", unit = "ms", limits = [0, 5000], digits = 0),
            
            "poke_voltage": LE(tooltip = "poke voltage (bias to apply during poking)", unit = "V", limits = [-10, 10], digits = 2, edited_color = scanalyzer_blue),
            "poke_depth": LE(tooltip = "poke depth (height relative to setpoint)", unit = "nm", limits = [-1000, 1000], digits = 2, edited_color = scanalyzer_blue),
            "poke_time": LE(tooltip = "poke time (duration of the poke)", unit = "s", limits = [0, 10000], digits = 2, edited_color = scanalyzer_blue),
            
            "lift_voltage": LE(tooltip = "lift voltage (bias to apply during lifting)", unit = "V", limits = [-10, 10], digits = 2, edited_color = scanalyzer_blue),
            "lift_height": LE(tooltip = "lift height (height relative to setpoint)", unit = "nm", limits = [-1000, 1000], digits = 2, edited_color = scanalyzer_blue),
            "lift_time": LE(tooltip = "lift time (duration of the lift)", unit = "s", limits = [0, 10000], digits = 2, edited_color = scanalyzer_blue),
            
            # STS
            "sts_t_int": LE(tooltip = "integration time per data point in units\nof the modulator time constant", value = 10, unit = "t", limits = [0, 10000], digits = 2, edited_color = scanalyzer_blue),
            "sts_t_settle": LE(tooltip = "settling time per data point in units\nof the modulator time constant\nRecommended value: 2", value = 2, unit = "t", limits = [0, 10000], digits = 2, edited_color = scanalyzer_blue),
            
            "sts_V_start": LE(value = -1, tooltip = "start bias", unit = "V", limits = [-10, 10], digits = 3, edited_color = scanalyzer_blue),
            "sts_V_end": LE(value = 1, tooltip = "end bias", unit = "V", limits = [-10, 10], digits = 3, edited_color = scanalyzer_blue),
            "sts_dV": LE(value = 10, tooltip = "bias step value", unit = "mV", limits = [0, 10000], digits = 2, edited_color = scanalyzer_blue),
            "sts_V_points": LE(value = 201, tooltip = "number of data points in sweep", unit = "pts", limits = [1, 100000], digits = 0, edited_color = scanalyzer_blue),
            
            "sts_f_start": LE(value = 10, tooltip = "start frequency", unit = "Hz", limits = [0, 100000], digits = 1, edited_color = scanalyzer_blue),
            "sts_f_end": LE(value = 10000, tooltip = "end frequency", unit = "Hz", limits = [0, 100000], digits = 1, edited_color = scanalyzer_blue),
            "sts_df": LE(value = 10, tooltip = "frequency step value", unit = "Hz", limits = [0, 100], digits = 2, edited_color = scanalyzer_blue),
            "sts_f_points": LE(value = 1001, tooltip = "number of data points in sweep", unit = "pts", limits = [1, 100000], digits = 0, edited_color = scanalyzer_blue),
            
            "sts_z_start": LE(value = 0, tooltip = "start height", unit = "nm", limits = [-200, 200], digits = 2, edited_color = scanalyzer_blue),
            "sts_z_end": LE(value = 2, tooltip = "end height", unit = "nm", limits = [-200, 200], digits = 2, edited_color = scanalyzer_blue),
            "sts_dz": LE(value = .01, tooltip = "height step value", unit = "nm", limits = [0, 200], digits = 2, edited_color = scanalyzer_blue),
            "sts_z_points": LE(value = 201, tooltip = "number of data points in sweep", unit = "pts", limits = [1, 100000], digits = 0, edited_color = scanalyzer_blue),            

            "sts_amp_start": LE(value = 0, tooltip = "start amplitude", unit = "mV", limits = [0, 100000], digits = 1, edited_color = scanalyzer_blue),
            "sts_amp_end": LE(value = 1000, tooltip = "end amplitude", unit = "mV", limits = [0, 100000], digits = 1, edited_color = scanalyzer_blue),
            "sts_damp": LE(value = 10, tooltip = "amplitude step value", unit = "mV", limits = [0, 1000], digits = 2, edited_color = scanalyzer_blue),
            "sts_amp_points": LE(value = 101, tooltip = "number of data points in sweep", unit = "pts", limits = [1, 100000], digits = 0, edited_color = scanalyzer_blue),

            "sts_V_keithley_start": LE(tooltip = "start frequency", unit = "Hz", limits = [0, 100000], digits = 1),
            "sts_V_keithley_end": LE(tooltip = "end frequency", unit = "Hz", limits = [0, 100000], digits = 1),
            "sts_dV_keithley": LE(tooltip = "frequency step value", unit = "Hz", limits = [0, 100], digits = 2),
            "sts_V_keithley_points": LE(tooltip = "number of data points in sweep", unit = "pts", limits = [1, 100000], digits = 0),
            
            # Lockins
            "nanonis_t": LE(tooltip = "Nanonis time constant (measurement window)", unit = "ms", limits = [0, 10000], digits = 3, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_df": LE(tooltip = "Nanonis frequency resolution", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            
            "nanonis_mod1_f": LE(tooltip = "Nanonis modulator 1 frequency", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_mod1_amp": LE(tooltip = "Nanonis modulator 1 amplitude", unit = "mV", limits = [0, 5000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_mod1_phase": LE(tooltip = "Nanonis modulator 1 phase", unit = "deg", limits = [-180, 360], digits = 2, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_mod1_n": LE(tooltip = "Nanonis modulator 1 number of oscillations in measurement window", limits = [0, 10000], digits = 2, min_width = 70, edited_color = scanalyzer_blue, max_width = 70),
            "nanonis_mod2_f": LE(tooltip = "Nanonis modulator 2 frequency", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_mod2_amp": LE(tooltip = "Nanonis modulator 2 amplitude", unit = "mV", limits = [0, 5000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_mod2_phase": LE(tooltip = "Nanonis modulator 2 phase", unit = "deg", limits = [-180, 360], digits = 2, min_width = 70, edited_color = scanalyzer_blue),
            "nanonis_mod2_n": LE(tooltip = "Nanonis modulator 2 number of oscillations in measurement window", limits = [0, 10000], digits = 2, min_width = 70, edited_color = scanalyzer_blue, max_width = 70),

            "mla_t": LE(tooltip = "MLA time constant (measurement window)", unit = "ms", limits = [0, 10000], digits = 3, min_width = 70, edited_color = scanalyzer_blue),
            "mla_df": LE(tooltip = "MLA frequency resolution", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            
            "mla_mod0_f": LE(tooltip = "MLA modulator 0 frequency", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "mla_mod0_amp": LE(tooltip = "MLA modulator 0 amplitude", unit = "mV", limits = [0, 5000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "mla_mod0_phase": LE(tooltip = "MLA modulator 0 phase", unit = "deg", limits = [-180, 360], digits = 2, min_width = 70, edited_color = scanalyzer_blue),
            "mla_mod0_n": LE(tooltip = "MLA modulator 0 number of oscillations n in measurement window", limits = [0, 10000], digits = 2, min_width = 70, edited_color = scanalyzer_blue, warning_color = self.colors["dark_orange"], max_width = 70),
            
            "mla_mod1_f": LE(tooltip = "MLA modulator 1 frequency", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "mla_mod1_amp": LE(tooltip = "MLA modulator 1 amplitude", unit = "mV", limits = [0, 5000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "mla_mod1_phase": LE(tooltip = "MLA modulator 1 phase", unit = "deg", limits = [-180, 360], digits = 2, min_width = 70, edited_color = scanalyzer_blue),
            "mla_mod1_n": LE(tooltip = "MLA modulator 1 number of oscillations n in measurement window", limits = [0, 10000], digits = 2, min_width = 70, edited_color = scanalyzer_blue, warning_color = self.colors["dark_orange"], max_width = 70),
            
            "mla_mod2_f": LE(tooltip = "MLA modulator 2 frequency", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "mla_mod2_amp": LE(tooltip = "MLA modulator 2 amplitude", unit = "mV", limits = [0, 5000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "mla_mod2_phase": LE(tooltip = "MLA modulator 2 phase", unit = "deg", limits = [-180, 360], digits = 2, min_width = 70, edited_color = scanalyzer_blue),
            "mla_mod2_n": LE(tooltip = "MLA modulator 2 number of oscillations n in measurement window", limits = [0, 10000], digits = 2, min_width = 70, edited_color = scanalyzer_blue, warning_color = self.colors["dark_orange"], max_width = 70),
            
            "mla_mod3_f": LE(tooltip = "MLA modulator 3 frequency", unit = "Hz", limits = [0, 10000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "mla_mod3_amp": LE(tooltip = "MLA modulator 3 amplitude", unit = "mV", limits = [0, 5000], digits = 1, min_width = 70, edited_color = scanalyzer_blue),
            "mla_mod3_phase": LE(tooltip = "MLA modulator 3 phase", unit = "deg", limits = [-180, 360], digits = 2, min_width = 70, edited_color = scanalyzer_blue),
            "mla_mod3_n": LE(tooltip = "MLA modulator 3 number of oscillations n in measurement window", limits = [0, 10000], digits = 2, min_width = 70, edited_color = scanalyzer_blue, warning_color = self.colors["dark_orange"], max_width = 70),

            "gaussian_width": LE(value = 0.000, tooltip = "width for Gaussian blur application", unit = "nm", digits = 3, max_width = 70),
            
            # Console
            "input": ILE(tooltip = "Enter a command\n(Enter to evaluate)")
        }
        
        # Reciprocal pairs and rang-steps groups (inter-line-edit update logic)
        self.sts_V_rg = RG(product = [line_edits["sts_V_start"], line_edits["sts_V_end"]], factors = [line_edits["sts_V_points"], line_edits["sts_dV"]], factor = 1000,
                           lock = "product", try_to_retain = "factor0", factor0_enforce_integer = True, factor0_include_endpoint = True)
        self.nanonis_rg = RG(product = 1000, factors = [line_edits["nanonis_t"], line_edits["nanonis_df"]])
        self.mla_rg = RG(product = 1000, factors = [line_edits["mla_t"], line_edits["mla_df"]])
        self.sts_z_rg = RG(product = [line_edits["sts_z_start"], line_edits["sts_z_end"]], factors = [line_edits["sts_z_points"], line_edits["sts_dz"]],
                           lock = "product", try_to_retain = "factor0", factor0_enforce_integer = True, factor0_include_endpoint = True)
        self.sts_f_rg = RG(product = [line_edits["sts_f_start"], line_edits["sts_f_end"]], factors = [line_edits["sts_f_points"], line_edits["sts_df"]],
                           lock = "product", try_to_retain = "factor0", factor0_enforce_integer = True, factor0_include_endpoint = True)
        self.sts_amp_rg = RG(product = [line_edits["sts_amp_start"], line_edits["sts_amp_end"]], factors = [line_edits["sts_amp_points"], line_edits["sts_damp"]],
                             lock = "product", try_to_retain = "factor0", factor0_enforce_integer = True, factor0_include_endpoint = True)        
        self.tone_rgs = [RG(product = line_edits[f"mla_mod{index}_f"], factors = [line_edits["mla_df"], line_edits[f"mla_mod{index}_n"]],
                            lock = "factor0", try_to_retain = "product", factor1_warn_if_not_integer = True) for index in range(4)]
        self.frame_rg = RG(product = line_edits["frame_height"], factors = [line_edits["frame_width"], line_edits["frame_aspect"]], lock = "factor1", try_to_retain = "product")
        self.grid_rg = RG(product = line_edits["grid_lines"], factors = [line_edits["grid_pixels"], line_edits["grid_aspect"]], lock = "factor1", try_to_retain = "product",
                          factor0_constraint = lambda value: int(round(value / 16) * 16))
        
        # Extra line edits
        [line_edits.update({f"demod_frequency_{i}": LE(value = 100 * i, tooltip = f"frequency of tone {i}", unit = "Hz", digits = 2, min_width = 80)}) for i in range(32)]
        [line_edits.update({f"demod_amplitude_{i}": LE(value = 100 * i, tooltip = f"amplitude of tone {i}", unit = "mV", digits = 2, min_width = 80)}) for i in range(32)]
        [line_edits.update({f"experiment_{i}": LE(tooltip = f"Experiment parameter field {i}", digits = 2)}) for i in range(9)]

        # Named groups
        self.action_line_edits = [line_edits[name] for name in ["z_steps", "h_steps", "minus_z_steps"]]
        
        # Add the button handles to the tooltips
        [line_edits[name].changeToolTip(f"gui.line_edits[\"{name}\"]", line = 10) for name in line_edits.keys()]
        
        return line_edits

    def make_progress_bars(self) -> dict:
        PB = SCTWidgets.ProgressBar
        
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
            # Main
            "main": make_layout("h"),
            "left_side": make_layout("v"),
            "toolbar": make_layout("v"),
            "empty": make_layout("v"),            
            "input": make_layout("h"),            
            "graph": make_layout("h"),
            "channels": make_layout("g"),
            "connections": make_layout("g"),
            
            # Experiment
            "experiment": make_layout("g"),
            "experiment_controls_0": make_layout("v"),
            "experiment_controls_1": make_layout("h"),
            "experiment_fields": make_layout("g"),
            "experiment_buttons": make_layout("h"),
            
            # Parameters; Rename feedback to bias. Rename gains to feedback
            "parameters": make_layout("v"),
            "parameters_0": make_layout("v"),
            "scan_parameter_sets": make_layout("h"),
            
            # Bias            
            "bias": make_layout("g"),
            "bias_getset": make_layout("h"),
            
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
            "quick_scan": make_layout("h"),
            "navigation": make_layout("h"),
            "background": make_layout("h"),
            "operations": make_layout("g"),
            "background_buttons": make_layout("h"),
            "limits": make_layout("g"),
                        
            # STS
            "osc": make_layout("v"),
            "sts": make_layout("v"),
            "spectroscopy": make_layout("g"),
            "spectroscopy_getset": make_layout("h"),
            
            "waveforms": make_layout("h"),
            
            "lockin_parameter_sets": make_layout("h"),
            "modulators": make_layout("g"),
            "mod_set_get": make_layout("h"),
            "pixel": make_layout("h"),
            "demodulators": make_layout("v"),
            "volume": make_layout("h"),
            "demod_sliders": make_layout("h")
        }
        
        return layouts

    def make_image_view(self) -> SCTWidgets.ImageView:
        pg.setConfigOptions(imageAxisOrder = "row-major", antialias = True)
        
        plot_item = pg.PlotItem()
        im_view = SCTWidgets.ImageView(view = plot_item)
        im_view.view.invertY(False)
        hist_widget = im_view.getHistogramWidget()
        self.hist_item = hist_widget.item
        
        # Make a tip target item in the image_view
        self.tip_target = SCTWidgets.TargetItem(pos = [0, 0], size = 10, tip_text = f"tip location\n(0, 0, 0) nm", movable = True)
        im_view.view.addItem(self.tip_target)
        
        return im_view

    def make_rois(self) -> tuple[pg.ROI, pg.ROI, pg.ROI]:
        piezo_roi = pg.ROI([-50, -50], [100, 100], pen = pg.mkPen(color = self.colors["orange"], width = 2), movable = False, resizable = False, rotatable = False)
        frame_roi = pg.ROI([-50, -50], [100, 100], pen = pg.mkPen(color = self.colors["blue"], width = 2), movable = False, resizable = False, rotatable = False)
        new_frame_roi = pg.ROI([-50, -50], [100, 100], pen = pg.mkPen(color = self.colors["light_blue"], width = 2), movable = True, resizable = True, rotatable = True)
        
        new_frame_roi.addScaleHandle([1, 0], [0, 1])
        new_frame_roi.addRotateHandle([0.5, 0], [0.5, 0.5])
        new_frame_roi.sigRegionChanged.connect(self.limit_roi_angle)
        
        return (piezo_roi, frame_roi, new_frame_roi)

    def make_plot_widgets(self) -> tuple[pg.PlotWidget, list[pg.PlotDataItem], pg.PlotWidget, list[pg.PlotDataItem]]:
        plot_widget = pg.PlotWidget()
        waveform_widget = pg.PlotWidget()

        pdis = [] # PlotDataItems
        for i in range(40):
            pen = pg.mkPen(self.color_list[i])
            pdi = plot_widget.plot(x_data = [], y_data = [], pen = pen)
            
            pdis.append(pdi)
        
        waveforms = [] # PlotDataItems
        for i in range(4):
            pen = pg.mkPen(self.color_list[i])
            waveform = waveform_widget.plot(x_data = [], y_data = [], pen = pen)
            
            waveforms.append(waveform)
        
        return (waveform_widget, waveforms, plot_widget, pdis)

    def make_limits_widget(self) -> SCTWidgets.MinMaxMethods:
        sivr = "Set the image value range "
        limits_widget = SCTWidgets.MinMaxMethods()

        limits_widget.addMethod("full", 0, 1, digits = 4, unit = "nm", icon = self.icons.get("100"), tooltip = sivr + "to the full data range")
        limits_widget.addMethod("percentiles", 1, 99, digits = 1, limits = [0, 100], unit = "%", icon = self.icons.get("percentiles"), tooltip = sivr + "by percentiles")
        limits_widget.addMethod("deviations", 2, 2, digits = 1, limits = [0, 100], unit = "\u03C3", icon = self.icons.get("deviation"), tooltip = sivr + "by standard deviations")
        limits_widget.addMethod("absolute", 0, 1, digits = 4, limits = [-10000, 10000], unit = "nm", icon = self.icons.get("numbers"), tooltip = sivr + "by absolute values")
        
        return limits_widget

    def make_widgets(self) -> dict:
        QWgt = QtWidgets.QWidget
        
        widgets = {
            "central": QWgt(),
            "left_side": QWgt(),
            "coarse_actions": QWgt(),
            "arrows": QWgt(),
            "graph": QWgt(),
            "osc": QWgt(),
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
            "demodulators": QWgt()
        }
        
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
        
        # Add the handles to the tooltips
        [consoles[name].changeToolTip(f"gui.consoles[\"{name}\"]", line = 10) for name in consoles.keys()]
        
        return consoles

    def make_sliders(self) -> dict:
        SL = SCTWidgets.Slider
        PS = SCTWidgets.PhaseSlider
        SLE = SCTWidgets.SliderLineEdit
        
        sliders = {
            "tip": SL(tooltip = "tip height (nm)", orientation = "v"),
            "volume": SLE(tooltip = "volume", orientation = "h", limits = [0, 100], value = 20, unit = "%", minmax_buttons = True, min_button_icon = self.icons.get("0"), max_button_icon = self.icons.get("100")),
            "phase": PS(tooltip = "Set complex phase phi\n(= multiplication by exp(i * pi * phi rad / (180 deg)))", unit = "deg", phase_0_icon = self.icons.get("0"), phase_180_icon = self.icons.get("180"))
        }

        for tone in range(32):
            value = 100 if tone == 0 else 0
            sle = SLE(tooltip = f"relative volume of tone {tone}", orientation = "v", limits = [0, 100], value = value, digits = 0, unit = "%",
                      minmax_buttons = True, min_button_icon = self.icons.get("0"), max_button_icon = self.icons.get("100"))
            
            self.labels[f"demod_index_{tone}"].setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.line_edits[f"demod_frequency_{tone}"].setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.line_edits[f"demod_amplitude_{tone}"].setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            
            sle.widget_layout.insertWidget(0, self.line_edits[f"demod_amplitude_{tone}"])
            sle.widget_layout.insertWidget(0, self.line_edits[f"demod_frequency_{tone}"])
            sle.widget_layout.insertWidget(0, self.labels[f"demod_index_{tone}"])
            sle.widget_layout.setContentsMargins(0, 0, 0, 0)

            sliders.update({f"f{tone}": sle})

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
        [layouts["channels"].addWidget(self.checkboxes[f"channel_{i}"], i % 8, int(i / 8)) for i in range(40)]
        
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
        [layouts["experiment_fields"].addWidget(widget, int(index / 3), index % 3) for index, widget in enumerate([line_edits[f"experiment_{i}"] for i in range(9)])] # Grid of experiment fields
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


        
        # Bias
        [layouts["bias_getset"].addWidget(widget) for widget in [buttons["get_bias_parameters"], buttons["set_bias_parameters"], comboboxes["bias"]]]
        b_layout = layouts["bias"]
        [b_layout.addWidget(labels[name], 0, index) for index, name in enumerate(["nanonis", "mla", "keithley"])]
        b_layout.addWidget(make_line("h", 1), 1, 0, 1, 3)
        [b_layout.addWidget(line_edits[name], 2, index) for index, name in enumerate(["V_nanonis", "V_mla_port1", "V_keithley"])]
        buttons["V_swap"].setFixedWidth(50)
        b_layout.addWidget(buttons["V_swap"], 3, 0, 1, 1, align_center)
        b_layout.addWidget(line_edits["V_mla_port2"], 3, 1)
        [b_layout.addWidget(line_edits[name], 4 + index, 0) for index, name in enumerate(["dV_nanonis", "dt_nanonis"])]
        [b_layout.addWidget(line_edits[name], 4 + index, 1) for index, name in enumerate(["dz_nanonis"])]
        [b_layout.addWidget(line_edits[name], 4 + index, 2) for index, name in enumerate(["dV_keithley", "dt_keithley"])]
        b_layout.addLayout(layouts["bias_getset"], 6, 0, 1, 3)
        
        # Feedback
        [layouts["currents"].addWidget(line_edits[name]) for name in ["I_fb", "I_pA", "I_keithley_limit"]]
        [layouts["feedback_gains"].addWidget(line_edits[name]) for name in ["p_gain", "t_const", "i_gain"]]
        layouts["feedback_gains"].addWidget(comboboxes["tia_gain"])
        [layouts["feedback_getset"].addWidget(widget) for widget in [buttons["get_feedback_parameters"], buttons["set_feedback_parameters"], comboboxes["feedback"]]]
        
        layouts["feedback"].addLayout(layouts["currents"])
        layouts["feedback"].addLayout(layouts["feedback_gains"])
        layouts["feedback"].addLayout(layouts["feedback_getset"])

        # Speeds
        [layouts["speeds_getset"].addWidget(widget) for widget in [buttons["get_speed_parameters"], buttons["set_speed_parameters"], comboboxes["speeds"]]]
        [layouts["speeds"].addWidget(labels[name], 0, index) for index, name in enumerate(["forward", "backward", "tip"])]
        [layouts["speeds"].addWidget(make_line("h", 1), 1, index) for index in range(3)]
        [layouts["speeds"].addWidget(line_edits[name], 2, index) for index, name in enumerate(["v_fwd", "v_bwd", "v_tip"])]
        layouts["speeds"].addLayout(layouts["speeds_getset"], 3, 0, 1, 3)


        
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
        
        # STS
        [layouts["spectroscopy_getset"].addWidget(widget) for widget in [buttons["get_spectroscopy_parameters"], buttons["set_spectroscopy_parameters"], comboboxes["spectroscopy"]]]        
        
        layouts["spectroscopy"].addWidget(buttons["start_spectrum"], 0, 0, 1, 2, align_center)
        layouts["spectroscopy"].addWidget(buttons["nanonis_mla"], 0, 2, 1, 1, align_center)
        [layouts["spectroscopy"].addWidget(buttons[f"sts_{parameter}"], 2 + 2 * index, 0, 2, 1) for index, parameter in enumerate(["V", "z", "f", "amp", "V_keithley"])]
        [layouts["spectroscopy"].addWidget(line_edits[name], 1, 1 + index) for index, name in enumerate(["sts_t_int", "sts_t_settle"])]
        for number, quantity in enumerate(["V", "z", "f", "amp", "V_keithley"]):
            [layouts["spectroscopy"].addWidget(line_edits[name], 2 + int(index / 2) + 2 * number, 1 + index % 2) for index, name in enumerate([f"sts_{quantity}_start", f"sts_{quantity}_end", f"sts_d{quantity}", f"sts_{quantity}_points"])]
        
        # layouts["spectroscopy"].addLayout(layouts["spectroscopy_getset"], 11, 0, 1, 3)

        # Modulators
        [layouts["mod_set_get"].addWidget(buttons[name]) for name in ["get_lockin_parameters", "set_lockin_parameters"]]

        [layouts["modulators"].addWidget(line_edits[f"nanonis_{quantity}"], 0, 2 * index, 1, 2) for index, quantity in enumerate(["t", "df"])]
        [layouts["modulators"].addWidget(buttons[f"nanonis_mod{index + 1}"], 1 + 2 * index, 0, 2, 1) for index in range(2)]
        [[layouts["modulators"].addWidget(line_edits[f"nanonis_mod{number + 1}_{quantity}"], 1 + 2 * number, 1 + index) for index, quantity in enumerate(["n", "f", "phase"])] for number in range(2)]
        [[layouts["modulators"].addWidget(widget, 2 + 2 * number, 1 + index, 1, 1 + index) for index, widget in enumerate([line_edits[f"nanonis_mod{number + 1}_amp"], comboboxes[f"nanonis_mod{number + 1}"]])] for number in range(2)]
        
        [layouts["modulators"].addWidget(line_edits[f"mla_{quantity}"], 5, 2 * index, 1, 2) for index, quantity in enumerate(["t", "df"])]
        [layouts["modulators"].addWidget(buttons[f"mla_mod{index}"], 6 + 2 * index, 0, 2, 1) for index in range(4)]
        [[layouts["modulators"].addWidget(line_edits[f"mla_mod{number}_{quantity}"], 6 + 2 * number, 1 + index) for index, quantity in enumerate(["n", "f", "phase"])] for number in range(4)]
        [[layouts["modulators"].addWidget(widget, 7 + 2 * number, 1 + index, 1, 1 + index) for index, widget in enumerate([line_edits[f"mla_mod{number}_amp"], comboboxes[f"mla_mod{number}"]])] for number in range(4)]
        
        layouts["modulators"].addLayout(layouts["mod_set_get"], 16, 0, 1, 4)        
        layouts["waveforms"].addWidget(self.waveform_widget)



        # Demodulators
        [layouts["pixel"].addWidget(widget) for widget in [buttons["get_pixel_nanonis"], buttons["get_pixel_mla"]]]
        [layouts["volume"].addWidget(widget) for widget in [buttons["audio"], self.sliders["volume"], buttons["zero_volumes"]]]
        layouts["demodulators"].addLayout(layouts["pixel"])
        layouts["demodulators"].addLayout(layouts["volume"])
        [layouts["demod_sliders"].addWidget(self.sliders[f"f{i}"]) for i in range(32)]
        self.widgets["demodulators"].setLayout(layouts["demod_sliders"])
        self.demod_scroller.setWidget(self.widgets["demodulators"])
        layouts["demodulators"].addWidget(self.demod_scroller)
        
        # Scan
        layouts["quick_scan"].addWidget(buttons["start_scan"])
        
        n_layout = layouts["navigation"]
        n_layout.addWidget(comboboxes["channels"], 4)
        n_layout.addWidget(self.buttons["direction"], 1)
        [n_layout.addWidget(self.buttons[name], 1) for name in ["fit_to_frame", "fit_to_range"]]
        
        # Operations
        [layouts["background_buttons"].addWidget(buttons[f"bg_{method}"]) for method in ["none", "plane", "linewise"]]
        layouts["background_buttons"].addWidget(buttons["rot_trans"])
        o_layout = layouts["operations"]
        o_layout.addLayout(layouts["background_buttons"], 0, 0, 1, 5)        
        [o_layout.addWidget(buttons[name], 1, index) for index, name in enumerate(["sobel", "normal", "laplace", "fft", "gaussian"])]
        o_layout.addWidget(line_edits["gaussian_width"], 1, 5)
        o_layout.addWidget(comboboxes["projection"], 2, 0, 1, 2)
        o_layout.addWidget(self.sliders["phase"], 2, 2, 1, 4)

        layouts["limits"].addWidget(self.limits_widget)
        
        # Input console
        layouts["input"].addWidget(self.consoles["input"])
        return



    # 4: Make widgets and groupboxes and set their layouts. Requires layouts.
    def make_groupboxes(self) -> dict:
        SGB = SCTWidgets.GroupBox
        layouts = self.layouts
        
        groupboxes = {
            # Connections
            "connections": SGB(title = "connections", tooltip = "connections to hardware (push to check/refresh)"),
            
            # Coarse
            "coarse_vertical": SGB(title = "vertical", tooltip = "vertical coarse motion"),
            "coarse_horizontal": SGB(title = "horizontal", tooltip = "horizontal coarse motion"),
            
            "tip_prep": SGB(title = "tip prep", tooltip = "tip preparation tools"),

            "frame_grid": SGB(title = "frame / grid", tooltip = "frame and grid parameters"),
            "bias": SGB(title = "bias", tooltip = "bias and ramp parameters"),
            "feedback": SGB(title = "feedback", tooltip = "feedback and gains"),
            "spectroscopy": SGB(title = "spectroscopy", tooltip = "spectroscopy"),
            "modulators": SGB(title = "modulators", tooltip = "modulators"),
            "waveforms": SGB(title = "waveforms", tooltip = "waveforms"),
            "demodulators": SGB(title = "demodulators", tooltip = "demodulators"),
            
            "quick_scan": SGB(title = "quick scan", tooltip = "quick scan"),
            "navigation": SGB(title = "navigation", tooltip = "navigation"),
            "background": SGB(title = "background subtraction", tooltip = "background subtraction"),
            "operations": SGB(title = "image processing operations", tooltip = "image processing operations"),
            "limits": SGB(title = "limits", tooltip = "limits"),

            "speeds": SGB(title = "speeds", tooltip = "speeds"),
            "experiment": SGB(title = "experiment", tooltip = "Perform experiment")
        }

        # Set layouts for the groupboxes
        #groupbox_names = ["connections", "coarse_horizontal", "coarse_vertical", "bias", "feedback", "speeds", "frame_grid", "tip_prep", "spectroscopy", "modulators", "demodulators", "experiment", "limits"]
        [layouts[name].setContentsMargins(2, 0, 2, 0) for name in groupboxes.keys()]
        [groupboxes[name].setLayout(layouts[name]) for name in groupboxes.keys()]

        # Make layouts of several groupboxes
        [layouts["coarse_control"].addWidget(groupboxes[name], 1) for name in ["coarse_horizontal", "coarse_vertical"]]
        layouts["coarse_prep"].addLayout(layouts["coarse_control"])
        layouts["coarse_prep"].addWidget(groupboxes["tip_prep"])
        
        [layouts["parameters"].addWidget(groupboxes[name]) for name in ["bias", "feedback", "speeds", "frame_grid"]]
        [layouts["osc"].addWidget(groupboxes[name]) for name in ["modulators", "waveforms"]]
        [layouts["sts"].addWidget(groupboxes[name]) for name in ["spectroscopy", "demodulators"]]
        [layouts["scan"].addWidget(groupboxes[name]) for name in ["quick_scan", "navigation", "operations", "limits"]]
        [layouts[name].addStretch(1) for name in ["parameters", "sts", "osc", "coarse_prep", "scan"]]

        return groupboxes



    # 5: Make the tab widget
    def make_tab_widget(self) -> QtWidgets.QTabWidget:
        tab_widget = QtWidgets.QTabWidget()
        
        tabs = ["parameters", "coarse_prep", "scan", "osc", "sts"]
        [self.widgets[name].setLayout(self.layouts[name]) for name in tabs]
        tab_widget.addTab(self.widgets["parameters"], "params")
        [tab_widget.addTab(self.widgets[name], name) for name in tabs if not name == "parameters"]

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
        #self.line_edits["grid_pixels"].editingFinished.connect(lambda: self.line_edits["grid_pixels"].setValue(int(round(self.line_edits["grid_pixels"].getValue() / 16) * 16)))
        self.line_edits["grid_pixels"].editingFinished.connect(self.set_pixels_to_multiple_of_16)
        self.buttons["frame_aspect"].clicked.connect(lambda: self.update_lock("frame"))
        self.buttons["grid_aspect"].clicked.connect(lambda: self.update_lock("grid"))
        
        self.new_frame_roi.sigRegionChangeFinished.connect(self.update_fields_from_frame_change)
        [self.line_edits[f"frame_{key}"].editingFinished.connect(self.update_frame_from_fields) for key in ["x", "y", "width", "height", "angle", "aspect"]]
        return

    def update_lock(self, name: str = "frame") -> None:
        if bool(self.buttons[f"{name}_aspect"].state_index): self.frame_rg.setLock("factor1") # Lock the aspect ratio
        else: self.frame_rg.setLock("factor0") # Lock the width
        return

    def set_pixels_to_multiple_of_16(self) -> None:
        value = self.line_edits["grid_pixels"].getValue()
        new_value = int(16 * round(value / 16))
        
        self.line_edits["grid_pixels"].setValue(new_value, edited_color = True)
        
        if bool(self.buttons["grid_aspect"].state_index):
            grid_aspect = self.line_edits["grid_aspect"].getValue()
            lines = int(grid_aspect * new_value)
            self.line_edits["grid_lines"].setValue(lines, edited_color = True)
        else:
            lines = self.line_edits["grid_lines"].getValue()
            grid_aspect = lines / new_value
            self.line_edits["grid_aspect"].setValue(grid_aspect)        
        return

    def limit_roi_angle(self, roi) -> None:
        angle = roi.angle()
        new_angle = (angle + 180) % 360 - 180

        roi.blockSignals(True)
        roi.setAngle(new_angle)
        roi.blockSignals(False)
        return

    def height_width_aspect(self, line_edit_name: str = "frame_width") -> None:
        """
        [self.line_edits[name].blockSignals(True) for name in ["frame_width", "frame_height", "frame_aspect", "grid_pixels", "grid_lines", "grid_aspect"]]

        match line_edit_name:
            case "grid_pixels":
                pixels = self.line_edits["grid_pixels"].getValue()
                if not isinstance(pixels, float) and not isinstance(pixels, int): return

                if bool(self.buttons["grid_aspect"].state_index):
                    grid_aspect = self.line_edits["grid_aspect"].getValue()

                    if isinstance(grid_aspect, float) or isinstance(grid_aspect, int):
                        lines = int(pixels * grid_aspect)
                        self.line_edits["grid_lines"].setValue(lines, edited_color = True)
                else:
                    lines = self.line_edits["grid_lines"].getValue()

                    if isinstance(lines, float) or isinstance(lines, int):
                        grid_aspect = lines / pixels
                        self.line_edits["grid_aspect"].setValue(grid_aspect, edited_color = True)

            case "grid_lines":
                lines = self.line_edits["grid_lines"].getValue()
                if not isinstance(lines, float) and not isinstance(lines, int): return

                if bool(self.buttons["grid_aspect"].state_index):
                    grid_aspect = self.line_edits["grid_aspect"].getValue()

                    if isinstance(grid_aspect, float) or isinstance(frame_aspect, int):
                        pixels = int(lines / grid_aspect)
                        self.line_edits["grid_pixels"].setValue(pixels, edited_color = True)
                else:
                    pixels = self.line_edits["grid_pixels"].getValue()
                    
                    if isinstance(pixels, float) or isinstance(pixels, int):
                        grid_aspect = lines / pixels
                        self.line_edits["grid_aspect"].setValue(grid_aspect, edited_color = True)

            case "grid_aspect":
                grid_aspect = self.line_edits["grid_aspect"].getValue()
                if not isinstance(grid_aspect, float) and not isinstance(grid_aspect, int): return

                pixels = self.line_edits["grid_pixels"].getValue()
                if isinstance(pixels, float) or isinstance(pixels, int):
                    lines = int(pixels * grid_aspect)
                    self.line_edits["grid_lines"].setValue(lines, edited_color = True)

            case _:
                pass

        [self.line_edits[name].blockSignals(False) for name in ["frame_width", "frame_height", "frame_aspect", "grid_pixels", "grid_lines", "grid_aspect"]]
        """
        return

    def update_fields_from_frame_change(self) -> None:
        [self.line_edits[name].blockSignals(True) for name in ["frame_x", "frame_y", "frame_width", "frame_height", "frame_angle"]]
        
        new_width = self.new_frame_roi.size().x()
        self.line_edits["frame_width"].setValue(new_width, edited_color = True)
        
        if bool(self.buttons["frame_aspect"].state_index):
            new_height = new_width * self.line_edits["frame_aspect"].getValue()
            
            self.new_frame_roi.blockSignals(True)
            self.new_frame_roi.setSize([new_width, new_height])
            self.new_frame_roi.blockSignals(False)
        else:
            new_height = self.new_frame_roi.size().y()
            self.line_edits["frame_aspect"].setValue(new_height / new_width, edited_color = True)
        
        self.line_edits["frame_height"].setValue(new_height, edited_color = True)
                
        bounding_rect = self.new_frame_roi.boundingRect()
        local_center = bounding_rect.center()
        abs_center = self.new_frame_roi.mapToParent(local_center)
        
        self.line_edits["frame_x"].setValue(abs_center.x(), edited_color = True)
        self.line_edits["frame_y"].setValue(abs_center.y(), edited_color = True)
        
        self.line_edits["frame_angle"].setValue(-self.new_frame_roi.angle(), edited_color = True)
        
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

