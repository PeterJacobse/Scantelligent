import os, sys
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
from .sct_widgets import SCTWidgets, ModulatorWidget, LockinWidget, WaveFormWidget, rotate_icon, make_layout, make_line



class SpectelligentGUI(QtWidgets.QMainWindow):
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
        self.buttons = self.make_buttons()
        self.checkboxes = self.make_checkboxes()
        self.comboboxes = self.make_comboboxes()
        self.line_edits = self.make_line_edits()
        self.layouts = self.make_layouts()
        (self.parameter_space_plot, self.waveform_widget) = self.make_plot_widgets()
        self.widgets = self.make_widgets()
                
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
    def make_buttons(self) -> dict:
        MSB = SCTWidgets.MultiStateButton
        
        sct_blue = self.colors["blue"]
        sct_black = self.colors["off-black"]
        icons = self.icons

        buttons = {
            "session_folder": MSB(icon = icons.get("folder_yellow"), click_to_toggle = False,
                                  states = [{"name": "offline", "color": self.colors["dark_red"], "tooltip": "Session folder unknown"},
                                            {"name": "online", "color": self.colors["dark_green"], "tooltip": "Open the session folder"}]),
            "exit": MSB(tooltip = "Exit Spectelligent\n(Esc / X / E)", icon = icons.get("escape"), size = 28),
            
            # Experiment
            "save": MSB(tooltip = "Save the experiment results to file", icon = icons.get("floppy"), click_to_toggle = False,
                        states = [{"name": "idle", "color": sct_black, "tooltip": "Click this button to save experiment data"},
                                  {"name": "data_present", "color": sct_blue, "tooltip": "Experiment data is present. Click to save"},
                                  {"name": "data_saved", "color": self.colors["dark_green"], "tooltip": "Experiment data was saved"}]),

            # Lockins
            "nanonis_mla": MSB(size = 28, states = [{"name": "mla", "icon": icons.get("imp"), "tooltip": "Use the MLA for spectroscopy"},
                                                    {"name": "nanonis", "icon": icons.get("nanonis"), "tooltip": "Use Nanonis for spectroscopy"}]),

            "start_spectroscopy": MSB(tooltip = "Acquire spectrum", size = 28, click_to_toggle = False, states = [{"name": "idle", "color": sct_black, "icon": icons.get("start_spectrum")},
                                                                                                                  {"name": "running", "color": sct_blue, "icon": icons.get("stop_spectrum")}]),
            "tia_correct": MSB(icon = icons.get("tia_response"), size = 28, states = [{"name": "off", "color": sct_black, "tooltip": "Do not correct for the tia response"},
                                                                                      {"name": "on", "color": sct_blue, "tooltip": "Correct for the tia response"}]),
            
            "sts_V": MSB(states = [{"name": "off", "tooltip": "Check to include a voltage sweep", "color": sct_black, "icon": icons.get("V")},
                                   {"name": "x", "tooltip": "Voltage sweep selected for the x-axis (fast/primary axis)", "color": sct_blue, "icon": icons.get("V_x")},
                                   {"name": "y", "tooltip": "Voltage sweep selected for the y-axis (slow/secondary axis)", "color": sct_blue, "icon": icons.get("V_y")}], click_to_toggle = False),
            "sts_f": MSB(states = [{"name": "off", "tooltip": "Check to include a frequency sweep", "color": sct_black, "icon": icons.get("f")},
                                   {"name": "x", "tooltip": "Frequency sweep selected for the x-axis (fast/primary axis)", "color": sct_blue, "icon": icons.get("f_x")},
                                   {"name": "y", "tooltip": "Frequency sweep selected for the y-axis (slow/secondary axis)", "color": sct_blue, "icon": icons.get("f_y")}], click_to_toggle = False),
            "sts_amp": MSB(states = [{"name": "off", "tooltip": "Check to include an amplitude sweep", "color": sct_black, "icon": icons.get("A")},
                                     {"name": "x", "tooltip": "Amplitude sweep selected for the x-axis (fast/primary axis)", "color": sct_blue, "icon": self.icons.get("A_x")},
                                     {"name": "y", "tooltip": "Amplitude sweep selected for the y-axis (slow/secondary axis)", "color": sct_blue, "icon": self.icons.get("A_y")}], click_to_toggle = False),
            "sts_z": MSB(states = [{"name": "off", "tooltip": "Check to include a height sweep", "color": sct_black, "icon": icons.get("z")},
                                   {"name": "x", "tooltip": "Height sweep selected for the x-axis (fast/primary axis)", "color": sct_blue, "icon": icons.get("z_x")},
                                   {"name": "y", "tooltip": "Height sweep selected for the y-axis (slow/secondary axis)", "color": sct_blue, "icon": icons.get("z_y")}], click_to_toggle = False),
            "sts_V_keithley": MSB(states = [{"name": "off", "tooltip": "Check to include a Keithley voltage sweep", "color": sct_black, "icon": icons.get("V_keithley")},
                                            {"name": "x", "tooltip": "Keithley voltage sweep selected for the x-axis (fast/primary axis)", "color": sct_blue, "icon": icons.get("V_x")},
                                            {"name": "y", "tooltip": "Keithley voltage sweep selected for the y-axis (slow/secondary axis)", "color": sct_blue, "icon": icons.get("V_y")}], click_to_toggle = False),
            
            "V_retrace": MSB(states = [{"name": "off", "tooltip": "Do not include a backward sweep", "color": sct_black, "icon": icons.get("fwd")},
                                       {"name": "on", "tooltip": "Include a backward sweep", "color": sct_blue, "icon": icons.get("fwd_bwd")}]),
            "f_retrace": MSB(states = [{"name": "off", "tooltip": "Do not include a backward sweep", "color": sct_black, "icon": icons.get("fwd")},
                                       {"name": "on", "tooltip": "Include a backward sweep", "color": sct_blue, "icon": icons.get("fwd_bwd")}]),
            "amp_retrace": MSB(states = [{"name": "off", "tooltip": "Do not include a backward sweep", "color": sct_black, "icon": icons.get("fwd")},
                                         {"name": "on", "tooltip": "Include a backward sweep", "color": sct_blue, "icon": icons.get("fwd_bwd")}]),
            "z_retrace": MSB(states = [{"name": "off", "tooltip": "Do not include a backward sweep", "color": sct_black, "icon": icons.get("fwd")},
                                       {"name": "on", "tooltip": "Include a backward sweep", "color": sct_blue, "icon": icons.get("fwd_bwd")}]),
            "V_keithley_retrace": MSB(states = [{"name": "off", "tooltip": "Do not include a backward sweep", "color": sct_black, "icon": icons.get("fwd")},
                                                {"name": "on", "tooltip": "Include a backward sweep", "color": sct_blue, "icon": icons.get("fwd_bwd")}]),
            
            "sts_x_axis": MSB(size = 28, states = [{"name": "V", "icon": icons.get("V"), "tooltip": "Perform a voltage sweep on the x axis (fast axis)"},
                                                   {"name": "amp", "icon": icons.get("A"), "tooltip": "Perform an amplitude sweep on the x axis (fast axis)"},
                                                   {"name": "z", "icon": icons.get("z"), "tooltip": "Perform a tip height sweep on the x axis (fast axis)"},
                                                   {"name": "f", "icon": icons.get("f"), "tooltip": "Perform a frequency sweep on the x axis (fast axis)"},
                                                   {"name": "V_keithley", "icon": icons.get("V_keithley"), "tooltip": "Perform a Keithley voltage sweep on the x axis (fast axis)"}]),
            "sts_y_axis": MSB(size = 28, states = [{"name": "none", "icon": icons.get("0"), "tooltip": "Sweep on the x axis (fast axis) only"},
                                                   {"name": "V", "icon": icons.get("V"), "tooltip": "Perform a voltage sweep on the y axis (slow axis)"},
                                                   {"name": "amp", "icon": icons.get("A"), "tooltip": "Perform an amplitude sweep on the y axis (slow axis)"},
                                                   {"name": "z", "icon": icons.get("z"), "tooltip": "Perform a tip height sweep on the y axis (slow axis)"},
                                                   {"name": "f", "icon": icons.get("f"), "tooltip": "Perform a frequency sweep on the y axis (slow axis)"},
                                                   {"name": "V_keithley", "icon": icons.get("V_keithley"), "tooltip": "Perform a Keithley voltage sweep on the y axis (slow axis)"}]),

            "get_pixel_nanonis": MSB(tooltip = "Click to receive a pixel from Nanonis", icon = icons.get("nanonis")),
            "get_pixel_mla": MSB(tooltip = "Click to receive a pixel from the MLA", icon = icons.get("imp")),
            
            "blank_modulators": MSB(size = 28, states = [{"name": "off", "tooltip": "Do not switch off modulators between sweeps", "icon": icons.get("continue_osc"), "color": sct_black},
                                                         {"name": "on", "tooltip": "Blank all modulators between sweeps", "icon": icons.get("stop_osc"), "color": sct_blue}]),
            "audio": MSB(icon = icons.get("audio"), states = [{"name": "off", "tooltip": "Auditory feedback of current signal\nOFF", "color": self.colors["dark_red"]},
                                                              {"name": "on", "tooltip": "Auditory feedback of current signal\nOFF", "color": sct_blue}]),
            "mla_zero_volumes": MSB(icon = icons.get("0"), tooltip = "Zero all relative volumes"),
            "nanonis_zero_volumes": MSB(icon = icons.get("0"), tooltip = "Zero all relative volumes"),
            "spectroscopy_feedback": MSB(size = 28, states = [{"name": "off", "tooltip": "Feedback switched OFF while performing spectroscopy", "icon": icons.get("constant_height"), "color": self.colors["orange"]},
                                                              {"name": "on", "tooltip": "Feedback switched ON while performing spectroscopy", "icon": icons.get("constant_current"), "color": self.colors["dark_green"]},
                                                              {"name": "unchanged", "tooltip": "Feedback left unchanged while performing spectroscopy", "icon": icons.get("tip_unknown"), "color": sct_black}]),
            "intermediate_feedback": MSB(size = 28, states = [{"name": "off", "tooltip": "Do not go into intermediate feedback", "icon": icons.get("constant_height"), "color": sct_black},
                                                              {"name": "on", "tooltip": "Return to intermediate feedback\nbefore every sweep in x", "icon": icons.get("constant_current"), "color": sct_blue}]),
            "intermediate_blank": MSB(size = 28, states = [{"name": "off", "tooltip": "Do not blank the lockin output during intemediate feedback", "icon": icons.get("imp"), "color": sct_blue},
                                                           {"name": "on", "tooltip": "Blank the lockin output during intemediate feedback", "icon": icons.get("constant_current"), "color": sct_black}]),
            "z_adjust": MSB(size = 28, states = [{"name": "off", "tooltip": "Do not adjust the tip height relative to the feedback setpoint", "icon": icons.get("constant_height"), "color": sct_black},
                                                 {"name": "on", "tooltip": "Adjust the tip height relative to the feedback setpoint before each sweep", "icon": icons.get("constant_current"), "color": sct_blue}]),
            
            "no_modulators": MSB(size = 28, tooltip = "Click to uncheck all modulators", icon = icons.get("0")),
            "all_modulators": MSB(size = 28, tooltip = "Click to check all modulators", icon = icons.get("100")),
            "expose_dIdV": MSB(size = 28, tooltip = "Expose the MLA in-phase dIdV to analog output A", icon = icons.get("expose_dIdV"))
        }
        
        for parameter_type in ["lockin", "parameter_space", "spectroscopy"]:
            buttons.update({f"get_{parameter_type}_parameters": MSB(tooltip = "Get parameters", icon = icons.get("get"))})
            buttons.update({f"set_{parameter_type}_parameters": MSB(tooltip = "Set the new parameters", icon = icons.get("set"))})
        
        for mod_number in range (2):
            buttons.update({f"nanonis_mod{mod_number + 1}": MSB(icon = icons.get("mla_oscillator"),
                                                                states = [{"name": "off", "tooltip": f"Nanonis modulator {mod_number + 1} OFF", "color": sct_black}, {"name": "on", "tooltip": f"Nanonis modulator {mod_number + 1} ON", "color": sct_blue}])})
        
        for mod_number in range (32):
            buttons.update({f"mla_mod{mod_number}": MSB(icon = icons.get("mla_oscillator"),
                                                        states = [{"name": "off", "tooltip": f"MLA modulator {mod_number} OFF", "color": sct_black}, {"name": "on", "tooltip": f"MLA modulator {mod_number} ON", "color": sct_blue}]),
                            f"mla_mod{mod_number}_input": MSB(states = [{"name": f"{port_index + 1}", "tooltip": f"input port {port_index + 1}", "icon": self.icons.get(f"{port_index + 1}")} for port_index in range(4)]),
                            f"mla_mod{mod_number}_output": MSB(states = [{"name": f"{port_index + 1}", "tooltip": f"output port {port_index + 1}", "icon": self.icons.get(f"{port_index + 1}")} for port_index in range(2)]),
                            f"mla_mod{mod_number}_extrapolate_f": MSB(tooltip = "click to extrapolate frequencies to successive modulator\nbased on this modulator and the previous one"),
                            f"mla_mod{mod_number}_extrapolate_input": MSB(tooltip = "click to extrapolate inputs to successive modulator\nbased on this modulator and the previous one"),
                            f"mla_mod{mod_number}_extrapolate_output": MSB(tooltip = "click to extrapolate inputs to successive modulator\nbased on this modulator and the previous one")})

        for parameter_type in ["bias", "coarse", "gain", "speed", "frame", "grid", "feedback", "lockin", "tip_shaper", "spectroscopy"]:
            buttons.update({f"get_{parameter_type}_parameters": MSB(tooltip = "Get parameters", icon = icons.get("get"))})
            buttons.update({f"set_{parameter_type}_parameters": MSB(tooltip = "Set the new parameters", icon = icons.get("set"))})
        [buttons.update({f"experiment_{i}": MSB(tooltip = f"experiment button {i}", icon = icons.get(f"{i}"))}) for i in range(6)]
        
        # Add the button handles to the tooltips
        [buttons[name].changeToolTip(f"gui.buttons[\"{name}\"]", line = 10) for name in buttons.keys()]
        
        [buttons[key].setState(1) for key in ["V_retrace", "tia_correct", "intermediate_feedback", "intermediate_blank"]]
        return buttons

    def make_checkboxes(self) -> tuple[dict, dict]:
        CB = SCTWidgets.CheckBox
        BG = SCTWidgets.ButtonGroup
        
        checkboxes = {f"modulator_{index}": CB(tooltip = f"Use modulator {index} during the experiment") for index in range(32)}

        # Add the button handles to the tooltips
        [checkboxes[name].changeToolTip(f"gui.checkboxes[\"{name}\"]", line = 10) for name in checkboxes.keys()]
        
        checkboxes["modulator_0"].setState(1)
        
        return checkboxes

    def make_comboboxes(self) -> dict:
        CB = SCTWidgets.ComboBox
        
        comboboxes = {
            "x": CB(tooltip = "Select which parameter to sweep on the x axis (fast axis) of the measurement", items = ["V (V)", "amp (mV)", "z (nm)", "r (nm)", "f (Hz)", "V_keithley (V)"]),
            "y": CB(tooltip = "Select which parameter to sweep on the y axis (slow axis) of the measurement", items = ["", "V (V)", "amp (mV)", "z (nm)", "r (nm)", "f (Hz)", "V_keithley (V)"]),
            
            "tia_gain": CB(tooltip = "Transimpedance amplifier gain setting"),
                       
            "nanonis_mod1": CB(tooltip = "Add Nanonis modulator 1 to this channel"),
            "nanonis_mod2": CB(tooltip = "Add Nanonis modulator 2 to this channel")
        }
        
        # Add the button handles to the tooltips
        [comboboxes[name].changeToolTip(f"gui.comboboxes[\"{name}\"]", line = 10) for name in comboboxes.keys()]
        
        return comboboxes

    def make_line_edits(self) -> dict:
        LE = SCTWidgets.PhysicsLineEdit
        RG = SCTWidgets.ReciprocalGroup
        
        scanalyzer_blue = "#2020C0"
        
        line_edits = {
            # STS
            "sts_V_feedback": LE(tooltip = "bias voltage", unit = "V", digits = 3, lmits = [-10, 10], max_width = 80),
            "sts_I_feedback": LE(tooltip = "feedback current", unit = "pA", digits = 1, limits = [0, 10000], max_width = 80),
            "sts_p_feedback": LE(tooltip = "proportional gain", unit = "pm", digits = 0, max_width = 80),
            "sts_t_const_feedback": LE(tooltip = "feedback time constant", unit = "us", digits = 0, max_width = 80),
            "sts_z_feedback": LE(tooltip = "tip height step relative to feedback setpoint", value = 0.0, unit = "nm", digits = 2, limits = [-1000, 1000], max_width = 80),
            
            "sts_V_start": LE(value = -1, tooltip = "start bias", unit = "V", limits = [-10, 10], digits = 3, max_width = 80),
            "sts_V_end": LE(value = 1, tooltip = "end bias", unit = "V", limits = [-10, 10], digits = 3, max_width = 80),
            "sts_dV": LE(value = 10, tooltip = "bias step value", unit = "mV", limits = [-10000, 10000], digits = 2, max_width = 80),
            "sts_V_points": LE(value = 201, tooltip = "number of data points in sweep", unit = "pts", limits = [1, 100000], digits = 0, max_width = 80),
            
            "sts_f_start": LE(value = 10, tooltip = "start frequency", unit = "Hz", limits = [0, 100000], digits = 1, max_width = 80),
            "sts_f_end": LE(value = 10000, tooltip = "end frequency", unit = "Hz", limits = [0, 100000], digits = 1, max_width = 80),
            "sts_df": LE(value = 10, tooltip = "frequency step value", unit = "Hz", limits = [-100, 100], digits = 2, max_width = 80),
            "sts_f_points": LE(value = 1000, tooltip = "number of data points in sweep", unit = "pts", limits = [1, 100000], digits = 0, max_width = 80),
            
            "sts_z_start": LE(value = 0, tooltip = "start height", unit = "nm", limits = [-200, 200], digits = 2, max_width = 80),
            "sts_z_end": LE(value = 2, tooltip = "end height", unit = "nm", limits = [-200, 200], digits = 2, max_width = 80),
            "sts_dz": LE(value = .01, tooltip = "height step value", unit = "nm", limits = [-200, 200], digits = 2, max_width = 80),
            "sts_z_points": LE(value = 201, tooltip = "number of data points in sweep", unit = "pts", limits = [1, 100000], digits = 0, max_width = 80),

            "sts_amp_start": LE(value = 0, tooltip = "start amplitude", unit = "mV", limits = [0, 100000], digits = 1, max_width = 80),
            "sts_amp_end": LE(value = 1000, tooltip = "end amplitude", unit = "mV", limits = [0, 100000], digits = 1, max_width = 80),
            "sts_damp": LE(value = 10, tooltip = "amplitude step value", unit = "mV", limits = [-1000, 1000], digits = 2, max_width = 80),
            "sts_amp_points": LE(value = 101, tooltip = "number of data points in sweep", unit = "pts", limits = [1, 100000], digits = 0, max_width = 80),

            "sts_V_keithley_start": LE(value = -60, tooltip = "start frequency", unit = "Hz", limits = [0, 100000], digits = 1, max_width = 80),
            "sts_V_keithley_end": LE(value = 60, tooltip = "end frequency", unit = "Hz", limits = [0, 100000], digits = 1, max_width = 80),
            "sts_dV_keithley": LE(value = 1, tooltip = "frequency step value", unit = "Hz", limits = [-100, 100], digits = 2, max_width = 80),
            "sts_V_keithley_points": LE(value = 121, tooltip = "number of data points in sweep", unit = "pts", limits = [1, 100000], digits = 0, max_width = 80),
            
            # X and Y axes will have copies of the selected parameters
            "sts_x_start": LE(tooltip = "start value", unit = "Hz", limits = [-100000, 100000], digits = 1, max_width = 80),
            "sts_x_end": LE(tooltip = "end value", unit = "Hz", limits = [-100000, 100000], digits = 1, max_width = 80),
            "sts_dx": LE(tooltip = "step value", unit = "Hz", limits = [-100, 100], digits = 2, max_width = 80),
            "sts_x_points": LE(tooltip = "number of data points in sweep", unit = "pts", limits = [1, 100000], digits = 0, max_width = 80),

            "sts_y_start": LE(tooltip = "start value", unit = "Hz", limits = [-100000, 100000], digits = 1, max_width = 80),
            "sts_y_end": LE(tooltip = "end value", unit = "Hz", limits = [-100000, 100000], digits = 1, max_width = 80),
            "sts_dy": LE(tooltip = "step value", unit = "Hz", limits = [-100, 100], digits = 2, max_width = 80),
            "sts_y_points": LE(tooltip = "number of data points in sweep", unit = "pts", limits = [1, 100000], digits = 0, max_width = 80),

            # Lockin
            "sts_t_int": LE(tooltip = "integration time per data point in units\nof the modulator time constant", value = 10, unit = "t", limits = [1, 10000], digits = 0, trigger_warnings = [lambda value: value < 3], max_width = 80),
            "sts_t_settle": LE(tooltip = "settling time per data point in units\nof the modulator time constant\nRecommended value: 2", value = 2, unit = "t", limits = [0, 10000], digits = 0, trigger_warnings = [lambda value: value < 2], max_width = 80),
            "sts_t_feedback": LE(tooltip = "feedback dwell time in between measurements\nin units of the modulator time constant", value = 4, unit = "t", limits = [0, 10000], digits = 0, trigger_warnings = [lambda value: value < 2], max_width = 80),
            
            "sts_t_int_ms": LE(tooltip = "integration time per data point", value = 1, unit = "ms", limits = [0, 100000], digits = 2, max_width = 80),
            "sts_t_settle_ms": LE(tooltip = "settling time per data point", value = 1, unit = "ms", limits = [0, 100000], digits = 2, max_width = 80),
            "sts_t_feedback_ms": LE(tooltip = "feedback dwell time in between measurements", value = 1, unit = "ms", limits = [0, 100000], digits = 2, max_width = 80),

            "mla_t": LE(tooltip = "MLA time constant (measurement window)", unit = "ms", limits = [0, 10000], digits = 3, min_width = 70, max_width = 80),
            "mla_df": LE(tooltip = "MLA frequency resolution", unit = "Hz", limits = [0, 100000], digits = 1, min_width = 70, max_width = 80)
        }
        
        for mod_number in range(32):
            line_edits.update({
                f"mla_mod{mod_number}_f": LE(tooltip = f"MLA modulator {mod_number} frequency", unit = "Hz", limits = [0, 100000], digits = 1, min_width = 70, max_width = 80),
                f"mla_mod{mod_number}_n": LE(tooltip = f"MLA modulator {mod_number} number of oscillations n in measurement window", limits = [0, 10000], digits = 2, min_width = 50, max_width = 50, warning_triggers = [lambda value: (value * 1000) % 1000 != 0]),
                f"mla_mod{mod_number}_amp": LE(tooltip = f"MLA modulator {mod_number} amplitude", unit = "mV", limits = [0, 10000], digits = 1, min_width = 70, max_width = 80),
                f"mla_demod{mod_number}_amp": LE(tooltip = f"MLA demodulator {mod_number} measured amplitude", unit = "mV", limits = [0, 10000], digits = 1, min_width = 70, max_width = 80),
                f"mla_mod{mod_number}_phase": LE(tooltip = f"MLA modulator {mod_number} phase", unit = "deg", limits = [-180, 360], digits = 2, min_width = 70, max_width = 80),
                f"mla_demod{mod_number}_phase": LE(tooltip = f"MLA demodulator {mod_number} measured phase", unit = "deg", limits = [-180, 360], digits = 2, min_width = 70, max_width = 80)
                })
        
        for mod_number in range(2):
            line_edits.update({
                f"nanonis_mod{mod_number + 1}_f": LE(tooltip = f"Nanonis modulator {mod_number} frequency", unit = "Hz", limits = [0, 100000], digits = 1, min_width = 70, max_width = 80),
                f"nanonis_mod{mod_number + 1}_n": LE(tooltip = f"Nanonis modulator {mod_number} number of oscillations n in measurement window", limits = [0, 10000], digits = 2, min_width = 50, max_width = 50, warning_triggers = [lambda value: (value * 1000) % 1000 != 0]),
                f"nanonis_mod{mod_number + 1}_amp": LE(tooltip = f"Nanonis modulator {mod_number} amplitude", unit = "mV", limits = [0, 10000], digits = 1, min_width = 70, max_width = 80),
                f"nanonis_demod{mod_number}_amp": LE(tooltip = f"Nanonis demodulator {mod_number} measured amplitude", unit = "mV", limits = [0, 10000], digits = 1, min_width = 70, max_width = 80),
                f"nanonis_mod{mod_number}_phase": LE(tooltip = f"Nanonis modulator {mod_number} phase", unit = "deg", limits = [-180, 360], digits = 2, min_width = 70, max_width = 80),
                f"nanonis_demod{mod_number}_phase": LE(tooltip = f"Nanonis demodulator {mod_number} measured phase", unit = "deg", limits = [-180, 360], digits = 2, min_width = 70, max_width = 80)
                })
        
        # Add the button handles to the tooltips
        [line_edits[name].changeToolTip(f"gui.line_edits[\"{name}\"]", line = 10) for name in line_edits.keys()]
        
        # Reciprocal groups (inter-line-edit update logic)
        self.sts_V_rg = RG(product = [line_edits["sts_V_start"], line_edits["sts_V_end"]], factors = [line_edits["sts_V_points"], line_edits["sts_dV"]], factor = 1000,
                           lock = "product", try_to_retain = "factor0", factor0_include_endpoint = True)
        self.sts_z_rg = RG(product = [line_edits["sts_z_start"], line_edits["sts_z_end"]], factors = [line_edits["sts_z_points"], line_edits["sts_dz"]],
                           lock = "product", try_to_retain = "factor0", factor0_enforce_integer = True, factor0_include_endpoint = True)
        self.sts_f_rg = RG(product = [line_edits["sts_f_start"], line_edits["sts_f_end"]], factors = [line_edits["sts_f_points"], line_edits["sts_df"]],
                           lock = "product", try_to_retain = "factor0", factor0_include_endpoint = True)
        self.sts_amp_rg = RG(product = [line_edits["sts_amp_start"], line_edits["sts_amp_end"]], factors = [line_edits["sts_amp_points"], line_edits["sts_damp"]],
                             lock = "product", try_to_retain = "factor0", factor0_enforce_integer = True, factor0_include_endpoint = True)
        self.t_settle_rg = RG(product = line_edits["sts_t_settle_ms"], factors = [line_edits["mla_t"], line_edits["sts_t_settle"]], lock = "factor0")
        self.t_int_rg = RG(product = line_edits["sts_t_int_ms"], factors = [line_edits["mla_t"], line_edits["sts_t_int"]], lock = "factor0")
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
            
            # Lockin
            "left_column": make_layout("v"),
            "lockin": make_layout("v"),
            "waveforms": make_layout("h"),

            # STS
            "modulators": make_layout("g"),
            "right_column": make_layout("v"),
            "spectroscopy_controls": make_layout("h"),
            "spectroscopy_settings": make_layout("g"),
            "parameter_space": make_layout("v"),
            "parameter_space_line_edits": make_layout("g"),
            "parameter_space_getset": make_layout("h"),
            
            "xy_plot": make_layout("g"),
            "xy_plot_x": make_layout("h"),
            "xy_plot_y": make_layout("v"),
            
            "spectroscopy": make_layout("g"),
            "spectroscopy_getset": make_layout("h"),
            
            ##            
            "lockin_parameter_sets": make_layout("h"),
            "modulators": make_layout("g"),
            "mod_set_get": make_layout("h"),
            "pixel": make_layout("h")
        }        
        return layouts

    def make_plot_widgets(self) -> tuple[SCTWidgets.PlotWidget, SCTWidgets.PlotWidget, SCTWidgets.PlotWidget, list[pg.PlotDataItem]]:
        parameter_space_plot = SCTWidgets.PlotWidget(colors = self.color_list, buffer_size = 0, n_channels = 0)
        
        self.grid_item = SCTWidgets.GridItem()
        parameter_space_plot.addItem(self.grid_item)
        
        waveform_widget = WaveFormWidget(colors = self.color_list, orientation = "h", n_outputs = 2, n_inputs = 4, n_modulators = 32)
        waveform_widget.wave_plot.setYRange(-2000, 2000)
        return (parameter_space_plot, waveform_widget)

    def make_widgets(self) -> dict:
        QWgt = QtWidgets.QWidget
        
        widgets = {
            "central": QWgt(),
            "left_side": QWgt(),
            "osc": QWgt(),
            "sts": QWgt(),

            "parameters": QWgt(),
            "scan": QWgt(),
            "experiment": QWgt(),
            "lockins": QWgt()
        }
        
        self.mla_mod = []
                
        for idx in range(32):
            volume = SCTWidgets.SliderLineEdit(layout_orientation = "v", slider_orientation = "h", limits = [0, 100], unit = "%", minmax_buttons = True, min_button_icon = self.icons.get("0"), max_button_icon = self.icons.get("100"))
            [mod_amp, demod_amp, mod_phase, demod_phase, freq, num] = [self.line_edits[f"mla_{key}"] for key in [f"mod{idx}_amp", f"demod{idx}_amp", f"mod{idx}_phase", f"demod{idx}_phase", f"mod{idx}_f", f"mod{idx}_n"]]
            [state_button, input_button, output_button] = [self.buttons[f"mla_mod{idx}{key}"] for key in ["", "_input", "_output"]]
            self.mla_mod.append(ModulatorWidget(state_button = state_button, input = input_button, output = output_button, volume = volume,
                                                mod_amplitude_le = mod_amp, demod_amplitude_le = demod_amp, mod_phase_le = mod_phase, demod_phase_le = demod_phase, frequency_le = freq, number_le = num))
        
        self.lockin_widget = LockinWidget(modulators = self.mla_mod, df_line_edit = self.line_edits["mla_df"], t_line_edit = self.line_edits["mla_t"], audio_button = self.buttons["audio"],
                                          zero_volumes_button = self.buttons["mla_zero_volumes"], get_button = self.buttons["get_lockin_parameters"], set_button = self.buttons["set_lockin_parameters"],
                                          min_button_icon = self.icons.get("0"), max_button_icon = self.icons.get("100"), extrapolate_icon = self.icons.get("extrapolate"))
        return widgets

    def make_sliders(self) -> dict:
        PS = SCTWidgets.PhaseSlider
        SLE = SCTWidgets.SliderLineEdit
        
        sliders = {
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



    # 3: Populate layouts with GUI items. Requires GUI items.
    def populate_layouts(self) -> None:
        layouts = self.layouts
        align_center = QtCore.Qt.AlignmentFlag.AlignCenter
        buttons = self.buttons
        line_edits = self.line_edits
        
        # Lockin
        layouts["lockin"].addWidget(self.lockin_widget)
        layouts["lockin"].addStretch(1)
        layouts["waveforms"].addWidget(self.waveform_widget)
        
        # STS controls
        [layouts["spectroscopy_controls"].addWidget(buttons[name]) for name in ["start_spectroscopy", "nanonis_mla", "expose_dIdV", "exit"]]
        
        # Settings
        layouts["spectroscopy_settings"].addWidget(buttons["tia_correct"], 0, 0, 2, 1)
        layouts["spectroscopy_settings"].addWidget(buttons["spectroscopy_feedback"], 0, 1, 2, 1)
        [layouts["spectroscopy_settings"].addWidget(line_edits[name], index % 2, 2 + int(index / 2)) for index, name in enumerate(["sts_t_int", "sts_t_settle", "sts_t_int_ms", "sts_t_settle_ms"])]
        [layouts["spectroscopy_settings"].addWidget(buttons[key], 0, 4 + index, 2, 1) for index, key in enumerate(["blank_modulators", "intermediate_feedback"])]
        [layouts["spectroscopy_settings"].addWidget(line_edits[f"sts_{key}_feedback"], index % 2, 6 + int(index / 2)) for index, key in enumerate(["V", "I", "p", "t_const", "t", "z"])]
        layouts["spectroscopy_settings"].addWidget(line_edits[f"sts_t_feedback_ms"], 0, 9)
        
        layouts["modulators"].addWidget(self.buttons[f"no_modulators"], 0, 0, 2, 1)
        [layouts["modulators"].addWidget(self.checkboxes[f"modulator_{index}"], int(index / 16), 1 + index % 16) for index in range(32)]
        layouts["modulators"].addWidget(self.buttons[f"all_modulators"], 0, 17, 2, 1)
        layouts["spectroscopy_settings"].addLayout(layouts["modulators"], 2, 0, 1, 10)
        
        [layouts["spectroscopy_getset"].addWidget(buttons[f"{key}et_spectroscopy_parameters"]) for key in ["g", "s"]]
        layouts["spectroscopy_settings"].addLayout(layouts["spectroscopy_getset"], 3, 0, 1, 10)
        
        # Parameter space
        for qindex, quantity in enumerate(["V", "z"]):
            layouts["parameter_space_line_edits"].addWidget(buttons[f"sts_{quantity}"], 0, 4 * qindex, 2, 1)
            [layouts["parameter_space_line_edits"].addWidget(line_edits[key], int(index / 2), 1 + 4 * qindex + index % 2) for index, key in enumerate([f"sts_{quantity}_start", f"sts_{quantity}_end", f"sts_d{quantity}", f"sts_{quantity}_points"])]
            layouts["parameter_space_line_edits"].addWidget(buttons[f"{quantity}_retrace"], 0, 3 + 4 * qindex, 2, 1)
        for qindex, quantity in enumerate(["f", "amp"]):
            layouts["parameter_space_line_edits"].addWidget(buttons[f"sts_{quantity}"], 2, 4 * qindex, 2, 1)
            [layouts["parameter_space_line_edits"].addWidget(line_edits[key], 2 + int(index / 2), 1 + 4 * qindex + index % 2) for index, key in enumerate([f"sts_{quantity}_start", f"sts_{quantity}_end", f"sts_d{quantity}", f"sts_{quantity}_points"])]
            layouts["parameter_space_line_edits"].addWidget(buttons[f"{quantity}_retrace"], 2, 3 + 4 * qindex, 2, 1)
        for qindex, quantity in enumerate(["V_keithley"]):
            layouts["parameter_space_line_edits"].addWidget(buttons[f"sts_{quantity}"], 4, 4 * qindex, 2, 1)
            [layouts["parameter_space_line_edits"].addWidget(line_edits[key], 4 + int(index / 2), 1 + 4 * qindex + index % 2) for index, key in enumerate([f"sts_{quantity}_start", f"sts_{quantity}_end", f"sts_d{quantity}", f"sts_{quantity}_points"])]
            layouts["parameter_space_line_edits"].addWidget(buttons[f"{quantity}_retrace"], 4, 3 + 4 * qindex, 2, 1)
        layouts["parameter_space"].addLayout(layouts["parameter_space_line_edits"])
        
        [layouts["parameter_space_getset"].addWidget(buttons[f"{key}et_parameter_space_parameters"]) for key in ["g", "s"]]
        layouts["parameter_space"].addLayout(layouts["parameter_space_getset"])
                
        [layouts["xy_plot_y"].addWidget(widget) for widget in [line_edits["sts_y_end"], buttons["sts_y_axis"], line_edits["sts_y_points"], line_edits["sts_y_start"]]]
        [layouts["xy_plot_x"].addWidget(widget) for widget in [line_edits["sts_x_start"], buttons["sts_x_axis"], line_edits["sts_x_points"], line_edits["sts_x_end"]]]
        layouts["xy_plot"].addLayout(layouts["xy_plot_y"], 0, 0)
        layouts["xy_plot"].addWidget(self.parameter_space_plot, 0, 1)
        layouts["xy_plot"].addLayout(layouts["xy_plot_x"], 1, 1)
        
        layouts["parameter_space"].addLayout(layouts["xy_plot"])
        return



    # 4: Make widgets and groupboxes and set their layouts. Requires layouts.
    def make_groupboxes(self) -> dict:
        SGB = SCTWidgets.GroupBox
        layouts = self.layouts
        
        groupboxes = {
            "lockin": SGB(title = "lockin controls", tooltip = "Set up the lockin amplifiers"),
            "waveforms": SGB(title = "waveforms", tooltip = "Check the outputted modulations waveforms"),
            
            "spectroscopy": SGB(title = "spectroscopy", tooltip = "spectroscopy"),
            "spectroscopy_controls": SGB(title = "spectroscopy controls", tooltip = "spectroscopy controls"),
            "spectroscopy_settings": SGB(title = "spectroscopy settings", tooltip = "spectroscopy settings"),
            "parameter_space": SGB(title = "parameter space", tooltip = "parameter space")
        }
        
        [layouts[name].setContentsMargins(2, 0, 2, 0) for name in groupboxes.keys()]
        [groupboxes[name].setLayout(layouts[name]) for name in groupboxes.keys()]
        
        [layouts["left_column"].addWidget(groupboxes[name]) for name in ["lockin", "waveforms"]]
        [layouts["right_column"].addWidget(groupboxes[name]) for name in ["spectroscopy_controls", "spectroscopy_settings", "parameter_space"]]
        return groupboxes



    # 5: Set up the main window layout
    def setup_main_window(self) -> None:
        layouts = self.layouts
        widgets = self.widgets
        groupboxes = self.groupboxes

        # Aesthetics
        #layouts["left_side"].setContentsMargins(0, 0, 0, 0)
        #layouts["toolbar"].setContentsMargins(4, 4, 4, 4)
        
        # Create the toolbar
        #[self.layouts["toolbar"].addWidget(groupboxes[name]) for name in ["connections", "experiment"]]
        #self.layouts["toolbar"].addWidget(self.tab_widget)
        #layouts["toolbar"].addStretch(1)
        
        # Compose the image_view plus consoles layout
        #layouts["left_side"].addWidget(self.image_view, stretch = 4)
        #layouts["left_side"].addWidget(widgets["graph"], stretch = 1)
        #layouts["left_side"].addWidget(self.consoles["output"], stretch = 1)
        #layouts["left_side"].addWidget(self.line_edits["input"])
        #self.widgets["left_side"].setLayout(layouts["left_side"])
        
        # Attach the toolbar
        #layouts["main"].addWidget(self.widgets["left_side"], stretch = 4)
        #layouts["main"].addLayout(layouts["toolbar"], 1)
        
        [layouts["main"].addLayout(layouts[f"{side}_column"]) for side in ["left", "right"]]
        
        # Set the central widget of the QMainWindow
        widgets["central"].setLayout(layouts["main"])
        widgets["central"].setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        widgets["central"].setFocus()
        
        # Finish the setup
        self.setCentralWidget(widgets["central"])
        self.setWindowTitle("Spectelligent @ Scantelligent")
        self.setGeometry(100, 50, 1400, 800) # x, y, width, height
        self.setWindowIcon(self.icons.get("scanalyzer"))
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.activateWindow()
        
        return

