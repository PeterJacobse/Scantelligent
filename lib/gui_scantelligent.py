import os
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
from . import GUIItems, PJComboBox, PJLineEdit, PJGroupBox



class ScantelligentGUI(QtWidgets.QMainWindow):
    def __init__(self, icons_path):
        super().__init__()
        
        # 1: Read icons from file.
        self.color_list = ["#FFFFFF", "#FFFF20", "#20FFFF", "#FF80FF", "#60FF60", "#FF6060", "#8080FF", "#B0B0B0", "#FFB010", "#A050FF",
                           "#909020", "#00A0A0", "#B030A0", "#40B040", "#B04040", "#5050E0", "#c00000", "#905020", "#707000", "#2020ff"]
        self.icons_path = icons_path
        self.get_icons()
        
        # 2: Create the specific GUI items using the items from the GUIItems class. Requires icons.
        self.gui_items = GUIItems()
        self.labels = self.make_labels()
        self.buttons = self.make_buttons()
        (self.checkboxes, self.channel_checkboxes) = self.make_checkboxes()
        self.comboboxes = self.make_comboboxes()
        self.line_edits = self.make_line_edits()
        self.radio_buttons = self.make_radio_buttons()
        self.lines = self.make_lines()
        self.progress_bars = self.make_progress_bars()
        self.layouts = self.make_layouts()
        self.image_view = self.make_image_view()
        self.plot_widget = self.make_plot_widget()
        self.widgets = self.make_widgets()
        self.consoles = self.make_consoles()
        self.tip_slider = self.make_tip_slider()
        self.shortcuts = self.make_shortcuts()
                
        # 3: Populate layouts with GUI items. Requires GUI items.
        self.populate_layouts()
        
        # 4: Make groupboxes and set their layouts. Requires populated layouts.
        self.groupboxes = self.make_groupboxes()
        
        # 5: Set up the main window layout
        self.setup_main_window()

        # 6: Interconnect mutually interdependent signals and slots
        self.interconnect()



    # 1: Read icons from file.
    def get_icons(self):
        icons_path = self.icons_path
        icon_files = os.listdir(icons_path)
        
        self.icons = {}
        for icon_file in icon_files:
            [icon_name, extension] = os.path.splitext(os.path.basename(icon_file))
            try:
                if extension == ".png": self.icons.update({icon_name: QtGui.QIcon(os.path.join(icons_path, icon_file))})
            except:
                pass



    # 2: Create the specific GUI items using the items from the GUIItems class. Requires icons.
    def make_labels(self) -> dict:
        make_label = self.gui_items.make_label
        
        labels = {
            "session_folder": make_label("Session folder"),
            "statistics": make_label("Statistics"),
            "load_file": make_label("Load file:"),
            "in_folder": make_label("in folder:"),
            "number_of_files": make_label("which contains 1 sxm file"),
            "channel_selected": make_label("Channel selected:"),

            "frame": make_label("frame"),
            "grid": make_label("grid"),

            "scan_control": make_label("Scan channel / direction"),
            "background_subtraction": make_label("Background subtraction"),
            "width": make_label("Width (nm):"),
            "show": make_label("Show", "Select a projection or toggle with (H)"),
            "limits": make_label("Set limits", "Toggle the min and max limits with (-) and (=), respectively"),
            "matrix_operations": make_label("Matrix operations"),

            "z_steps": make_label("steps"),
            "move_horizontally": make_label("< horizontal motion >", "In composite motion, horizontal motion\nis carried out between retract and advance\nSee 'horizontal'"),
            "h_steps": make_label("steps in direction"),
            "steps_and": make_label("steps, and")
        }
        
        # Named groups
        self.steps_labels = [labels[name] for name in ["z_steps", "h_steps", "steps_and"]]
        
        return labels
    
    def make_buttons(self) -> dict:
        make_button = self.gui_items.make_button
        make_toggle_button = self.gui_items.make_toggle_button
        icons = self.icons
        arrow = icons.get("single_arrow")
        arrow45 = icons.get("single_arrow_45")
        mtt = "Move the tip "
        sivr = "Set the image value range "

        buttons = {
            "scanalyzer": make_button("", "Launch Scanalyzer", icon = icons.get("scanalyzer")),
            "nanonis": make_button("", "Nanonis: offline\n(Ctrl + C)", icon = icons.get("nanonis")),
            "mla": make_button("", "Multifrequency Lockin Amplifier: offline\n(Ctrl + C)", icon = icons.get("imp")),
            "camera": make_button("", "Camera: offline\n(Ctrl + C)", icon = icons.get("camera")),
            "exit": make_button("", "Exit scantelligent\n(Esc / X / E)", icon = icons.get("escape")),
            "oscillator": make_button("", "Oscillator on/off\n(O)", icon = icons.get("osc")),
            "view": make_button("", "Toggle the active view\n(V)", icon = icons.get("eye")),
            "session_folder": make_button("", "Open the session folder\n(1)", icon = icons.get("folder_yellow")),
            "info": make_button("", "Info", self.icons.get("i")),
            
            "tip": make_button("", "Tip status\n(Ctrl + Space to toggle feedback)", icon = icons.get("withdrawn")),
            "V_swap": make_button("", "Swap the bias between Nanonis and the MLA", icon = icons.get("swap")),
            
            "set_scan_parameters": make_button("", "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_scan_parameters": make_button("", "Get parameters\n(P)", icon = icons.get("get")),
            "set_coarse_parameters": make_button("", "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_coarse_parameters": make_button("", "Get parameters\n(P)", icon = icons.get("get")),
            "set_gain_parameters": make_button("", "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_gain_parameters": make_button("", "Get parameters\n(P)", icon = icons.get("get")),
            "set_speed_parameters": make_button("", "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_speed_parameters": make_button("", "Get parameters\n(P)", icon = icons.get("get")),
            "set_frame_parameters": make_button("", "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_frame_parameters": make_button("", "Get parameters\n(P)", icon = icons.get("get")),
            "set_grid_parameters": make_button("", "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_grid_parameters": make_button("", "Get parameters\n(P)", icon = icons.get("get")),
            
            "withdraw": make_button("", "Withdraw the tip\n(Ctrl + W)", icon = icons.get("withdraw")),
            "retract": make_button("", "Retract the tip from the surface\n(Ctrl + PgUp)", icon = icons.get("retract")),
            "advance": make_button("", "Advance the tip towards the surface\n(Ctrl + PgDown)", icon = icons.get("advance")),
            "approach": make_button("", "Initiate auto approach\n(Ctrl + A)", icon = icons.get("approach")),
            "set_coarse": make_button("", "Set the new coarse parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get_coarse": make_button("", "Get the coarse parameters\n(P)", icon = icons.get("get")),

            "n": make_button("", mtt + "north\n(Ctrl + ↑ / Ctrl + 8)", icon = arrow, rotate_icon = 270),
            "ne": make_button("", mtt + "northeast\n(Ctrl + 9)", icon = arrow45, rotate_icon = 0),
            "e": make_button("", mtt + "east\n(Ctrl + → / Ctrl + 6)", icon = arrow, rotate_icon = 0),
            "se": make_button("", mtt + "southeast\n(Ctrl + 3)", icon = arrow45, rotate_icon = 90),
            "s": make_button("", mtt + "south\n(Ctrl + ↓ / Ctrl + 2)", icon = arrow, rotate_icon = 90),
            "sw": make_button("", mtt + "southwest\n(Ctrl + 1)", icon = arrow45, rotate_icon = 180),
            "w": make_button("", mtt + "west\n(Ctrl + ← / Ctrl + 4)", icon = arrow, rotate_icon = 180),
            "nw": make_button("", mtt + "northwest\n(Ctrl + 7)", icon = arrow45, rotate_icon = 270),
            
            "bias_pulse": make_button("", "Apply a voltage pulse to the tip", icon = icons.get("bias_pulse")),
            "tip_shape": make_button("", "Shape the tip by poking it into the surface", icon = icons.get("tip_shape")),
            
            "save": make_button("", "Save the experiment results to file", icon = icons.get("floppy")),
            "start_pause": make_button("", "Start experiment", icon = icons.get("start")),
            "stop": make_button("", "Stop experiment", icon = icons.get("stop")),

            "direction": make_toggle_button("", "Change scan direction\n(X)", icon = icons.get("triple_arrow")),
            "fit_to_frame": make_button("", "Snap the view range to the scan frame", icon = icons.get("scan_frame")),
            "fit_to_range": make_button("", "Snap the view range to the total piezo range", icon = icons.get("piezo_range")),
            "full_data_range": make_button("", sivr + "to the full data range\n(U)", icons.get("100")),
            "percentiles": make_button("", sivr + "by percentiles\n(R)", icons.get("percentiles")),
            "standard_deviation": make_button("", sivr + "by standard deviations\n(D)", icons.get("deviation")),
            "absolute_values": make_button("", sivr + "by absolute values\n(A)", icons.get("numbers")),

            "frame_aspect": make_toggle_button("", "Lock the frame aspect ratio", icon = icons.get("lock_aspect")),
            "grid_aspect": make_toggle_button("", "Lock the grid aspect ratio", icon = icons.get("lock_aspect")),
            
            "input": make_button(">>", "Enter command\n(Ctrl + Enter)"),

            "nanonis_mod1": make_button("", "Nanonis Modulation 1 On/Off", icon = icons.get("nanonis_mod1")),
            "nanonis_mod2": make_button("", "Nanonis Modulation 2 On/Off", icon = icons.get("nanonis_mod2")),
            "mla_mod1": make_button("", "MLA Modulation 1 On/Off", icon = icons.get("mla_mod1"))
        }

        for i in range(6):
            buttons.update({f"scan_parameters_{i}": make_button("", f"Load scan parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"coarse_parameters_{i}": make_button("", f"Load coarse parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"gain_parameters_{i}": make_button("", f"Load gain parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"speed_parameters_{i}": make_button("", f"Load speed parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})
            buttons.update({f"grid_parameters_{i}": make_button("", f"Load grid parameter set {i}\n(Ctrl + {i})", icon = icons.get(f"{i}"))})

        #[buttons[name].setCheckable(True) for name in ["direction", "nanonis_mod1", "nanonis_mod2", "frame_aspect", "grid_aspect"]]

        # Named groups
        self.connection_buttons = [buttons[name] for name in ["nanonis", "camera", "mla", "scanalyzer", "view", "session_folder", "info", "exit"]]
        self.arrow_buttons = [buttons[direction] for direction in ["nw", "n", "ne", "w", "n", "e", "sw", "s", "se"]]
        self.action_buttons = [buttons[name] for name in ["withdraw", "retract", "advance", "approach"]]
        
        self.scan_parameter_sets = [buttons[f"scan_parameters_{i + 1}"] for i in range(4)]
        
        self.scale_buttons = [buttons[name] for name in ["full_data_range", "percentiles", "standard_deviation", "absolute_values"]]

        # Add the button handles to the tooltips
        [buttons[name].changeToolTip(f"gui.buttons[\"{name}\"]", line = 10) for name in buttons.keys()]

        return buttons

    def make_checkboxes(self) -> dict:
        make_checkbox = self.gui_items.make_checkbox
        
        checkboxes = {
            "withdraw": make_checkbox("", "Include withdrawing of the tip during a tip move"),
            "retract": make_checkbox("", "Include retracting the tip during a tip move"),
            "advance": make_checkbox("", "Include advancing the tip during a move"),
            "approach": make_checkbox("", "End the tip move with an auto approach"),

            "sobel": make_checkbox("Sobel", "Compute the complex gradient d/dx + i d/dy\n(Shift + S)", self.icons.get("sobel")),
            "laplace": make_checkbox("Laplace", "Compute the Laplacian (d/dx)^2 + (d/dy)^2\n(Shift + C)", self.icons.get("laplacian")),
            "fft": make_checkbox("Fft", "Compute the 2D Fourier transform\n(Shift + F)", self.icons.get("fourier")),
            "normal": make_checkbox("Normal", "Compute the z component of the surface normal\n(Shift + N)", self.icons.get("surface_normal")),
            "gaussian": make_checkbox("Gauss", "Apply a Gaussian blur\n(Shift + G)", self.icons.get("gaussian")),
            
            "rotation": make_checkbox("", "Show the scan frame rotation\n(R)", self.icons.get("rotation")),
            "offset": make_checkbox("", "Show the scan frame offset(O)", self.icons.get("offset")),

            "composite_motion": make_checkbox("", "Composite motion:\nWhen checked, combine all checked vertical motions with the horizontal motion in a composite pattern", icon = self.icons.get("composite_motion"))
        }
        
        channel_checkboxes = {f"{index}": make_checkbox(f"{index}", f"channel {index}") for index in range(20)}
        
        # Named groups
        self.action_checkboxes = [checkboxes[name] for name in ["withdraw", "retract", "advance", "approach"]]
        [checkbox.setChecked(True) for checkbox in self.action_checkboxes]
        checkboxes["advance"].setChecked(False)

        # Add the button handles to the tooltips
        [checkboxes[name].changeToolTip(f"gui.checkboxes[\"{name}\"]", line = 10) for name in checkboxes.keys()]

        return (checkboxes, channel_checkboxes)

    def make_comboboxes(self) -> dict:
        make_combobox = self.gui_items.make_combobox
        
        comboboxes = {
            "channels": make_combobox("Channels", "Available scan channels"),
            "projection": make_combobox("Projection", "Select a projection or toggle with\n(Shift + ↑)", items = ["re", "im", "abs", "arg (b/w)", "arg (hue)", "complex", "abs^2", "log(abs)"]),
            "experiment": make_combobox("Experiment", "Select an experiment", items = ["nanonis_scan", "idling"]),
            "direction": make_combobox("Direction", "Select a scan direction / pattern (X)", items = ["nearest tip", "down", "up", "random"])
        }
        
        # Add the button handles to the tooltips
        [comboboxes[name].changeToolTip(f"gui.comboboxes[\"{name}\"]", line = 10) for name in comboboxes.keys()]
        
        return comboboxes

    def make_line_edits(self) -> dict:
        make_line_edit = self.gui_items.make_line_edit
        buttons = self.buttons
        
        line_edits = {
            # Experiment
            "experiment_filename": PJLineEdit(tooltip = "Base name of the file when saved to png or hdf5"),
            "experiment_0": PJLineEdit(tooltip = "Experiment parameter field 0"),
            "experiment_1": PJLineEdit(tooltip = "Experiment parameter field 1"),
            "experiment_2": PJLineEdit(tooltip = "Experiment parameter field 2"),

            # Coarse
            "z_steps": PJLineEdit(value = 20, tooltip = "Steps in the +Z (retract) direction", unit = "steps up", digits = 0),
            "h_steps": PJLineEdit(value = 100, tooltip = "Steps in the horizontal direction", unit = "steps", digits = 0),
            "minus_z_steps": PJLineEdit(value = 0, tooltip = "Steps in the -Z (advance) direction", unit = "steps down", digits = 0),
            
            "V_hor": PJLineEdit(value = 150, tooltip = "Voltage supplied to the coarse piezos during horizontal movement", unit = "V (xy)", digits = 0),
            "V_ver": PJLineEdit(value = 150, tooltip = "Voltage supplied to the coarse piezos during vertical movement", unit = "V (z)", digits = 0),
            "f_motor": PJLineEdit(value = 1000, tooltip = "Sawtooth wave frequency supplied to the coarse piezos during movement", unit = "Hz", digits = 0),

            # Parameters
            "V_nanonis": PJLineEdit(tooltip = "Nanonis bias\n(Ctrl + P) to set", unit = "V", limits = [-10, 10], digits = 3),
            "V_mla": PJLineEdit(tooltip = "MLA bias\n(Ctrl + P) to set", unit = "V", limits = [-10, 10], digits = 3),
            "V_keithley": PJLineEdit(tooltip = "Keithley bias\n(Ctrl + P) to set", unit = "V", limits = [-200, 200], digits = 3),

            "dV": PJLineEdit(tooltip = "Step size dV when ramping the bias", unit = "mV", limits = [-1000, 1000], digits = 1),
            "dt": PJLineEdit(tooltip = "Step size dt when ramping the bias", unit = "ms", limits = [-1000, 1000], digits = 0),
            "dz": PJLineEdit(tooltip = "Step size dz when ramping the bias\nTemporarily retract the tip by this amount when ramping to a different polarity", unit = "nm", limits = [-200, 200], digits = 1),

            "dV_keithley": PJLineEdit(tooltip = "Step size dV when ramping the Keithley bias", unit = "mV", limits = [-1000, 1000], digits = 1),
            "dt_keithley": PJLineEdit(tooltip = "Step size dt when ramping the Keithley bias", unit = "ms", limits = [-1000, 1000], digits = 0),

            "I_fb": PJLineEdit(tooltip = "Feedback current\n(Ctrl + P) to set", unit = "pA", digits = 0),
            "I_keithley": PJLineEdit(tooltip = "Keithley current", unit = "pA", digits = 0),
            "I_limit": PJLineEdit(tooltip = "Maximum Keithley current", unit = "pA", digits = 0),
            
            "p_gain": PJLineEdit(tooltip = "Proportional gain\n(Ctrl + P) to set", unit = "pm", digits = 0),
            "t_const": PJLineEdit(tooltip = "Time constant\n(Ctrl + P) to set", unit = "us", digits = 0),
            "i_gain": PJLineEdit(tooltip = "Integral gain\n(Ctrl + P) to set"),
            
            "v_fwd": PJLineEdit(tooltip = "Tip forward speed\n(Ctrl + P) to set", unit = "nm/s", digits = 2),
            "v_bwd": PJLineEdit(tooltip = "Tip backward speed\n(Ctrl + P) to set", unit = "nm/s", digits = 2),
            
            # Frame
            "frame_height": PJLineEdit(tooltip = "frame height", unit = "nm", limits = [0, 1000], digits = 1),
            "frame_width": PJLineEdit(tooltip = "frame width", unit = "nm", limits = [0, 1000], digits = 1),
            "frame_x": PJLineEdit(tooltip = "frame offset (x)", unit = "nm", limits = [-1000, 1000], digits = 1),
            "frame_y": PJLineEdit(tooltip = "frame offset (y)", unit = "nm", limits = [-1000, 1000], digits = 1),
            "frame_angle": PJLineEdit(tooltip = "frame angle", unit = "deg", limits = [-180, 360], digits = 1),
            "frame_aspect": PJLineEdit(tooltip = "frame aspect ratio (height / width)", digits = 4),

            # Grid
            "grid_pixels": PJLineEdit(tooltip = "Number of pixels", unit = "px", limits = [1, 10000], digits = 0),
            "grid_lines": PJLineEdit(tooltip = "Number of lines", unit = "px", limits = [1, 10000], digits = 0),
            "grid_aspect": PJLineEdit(tooltip = "grid aspect ratio (lines / pixels)", digits = 4),
            "pixel_width": PJLineEdit(tooltip = "pixel width", unit = "nm", digits = 4),
            "pixel_height": PJLineEdit(tooltip = "pixel height", unit = "nm", digits = 4),
            
            # Tip shaper
            "pulse_voltage": PJLineEdit(tooltip = "Voltage to apply to the tip when pulsing", unit = "V", limits = [-10, 10], digits = 1),
            "pulse_duration": PJLineEdit(tooltip = "Duration of the voltage pulse", unit = "ms", limits = [0, 5000], digits = 0),

            # Image processing
            "min_full": make_line_edit("", "minimum value of scan data range", icon = self.icons.get("0")),
            "max_full": make_line_edit("", "maximum value of scan data range"),
            "min_percentiles": make_line_edit("2", "minimum percentile of data range"),
            "max_percentiles": make_line_edit("98", "maximum percentile of data range"),
            "min_deviations": make_line_edit("2", "minimum = mean - n * standard deviation"),
            "max_deviations": make_line_edit("2", "maximum = mean + n * standard deviation"),
            "min_absolute": make_line_edit("0", "minimum absolute value"),
            "max_absolute": make_line_edit("1", "maximum absolute value"),

            "gaussian_width": PJLineEdit(name = "0", tooltip = "Width in nm for Gaussian blur application", unit = "nm"),
            
            # Console            
            "input": PJLineEdit(tooltip = "Enter a command\n(Enter to evaluate)", block = True)
        }
        
        # Named groups
        self.parameter_line_0 = [buttons["tip"], line_edits["V_nanonis"], buttons["V_swap"], line_edits["V_mla"], line_edits["I_fb"], buttons["set_scan_parameters"], buttons["get_scan_parameters"]]
        self.parameter_line_1 = [line_edits[name] for name in ["p_gain", "t_const", "v_fwd", "v_bwd"]]

        self.experiment_parameter_fields = [line_edits[f"experiment_{i}"] for i in range(3)]

        self.gain_line_edits = [line_edits[name] for name in ["p_gain", "t_const", "i_gain"]]
        
        self.action_line_edits = [line_edits[name] for name in ["z_steps", "h_steps", "minus_z_steps"]]
        self.min_line_edits = [line_edits[name] for name in ["min_full", "min_percentiles", "min_deviations", "min_absolute"]]
        self.max_line_edits = [line_edits[name] for name in ["max_full", "max_percentiles", "max_deviations", "max_absolute"]]
        
        self.tip_prep_widgets = [buttons["bias_pulse"], line_edits["pulse_voltage"], line_edits["pulse_duration"], buttons["tip_shape"]]

        self.frame_widgets = [line_edits[name] for name in ["frame_height", "frame_width", "frame_x", "frame_y", "frame_angle", "frame_aspect"]]
        self.grid_widgets = [line_edits[name] for name in ["grid_lines", "grid_pixels", "grid_aspect"]]
        
        # Aesthetics
        [line_edits[name].setStyleSheet("QLineEdit{ background-color: #101010; }") for name in line_edits.keys()]
        
        # Add the button handles to the tooltips
        [line_edits[name].changeToolTip(f"gui.line_edits[\"{name}\"]", line = 10) for name in line_edits.keys()]
        
        # Initialize
        [line_edits[name].setEnabled(False) for name in ["min_full", "max_full"]]
        
        return line_edits

    def make_radio_buttons(self) -> dict:
        make_radio_button = self.gui_items.make_radio_button
        QGroup = QtWidgets.QButtonGroup
        
        radio_buttons = {
            "bg_none": make_radio_button("", "None\n(0)", self.icons.get("0")),
            "bg_plane": make_radio_button("", "Plane\n(P)", self.icons.get("plane_subtract")),
            "bg_linewise": make_radio_button("", "Linewise\n(W)", self.icons.get("lines")),
            "bg_inferred": make_radio_button("", "None\n(0)", self.icons.get("0")),

            "min_full": make_radio_button("", "set to minimum value of scan data range\n(-) to toggle"),
            "max_full": make_radio_button("", "set to maximum value of scan data range\n(=) to toggle"),
            "min_percentiles": make_radio_button("", "set to minimum percentile of data range\n(-) to toggle"),
            "max_percentiles": make_radio_button("", "set to maximum percentile of data range\n(=) to toggle"),
            "min_deviations": make_radio_button("", "set to minimum = mean - n * standard deviation\n(-) to toggle"),
            "max_deviations": make_radio_button("", "set to maximum = mean + n * standard deviation\n(=) to toggle"),
            "min_absolute": make_radio_button("", "set minimum to an absolute value\n(-) to toggle"),
            "max_absolute": make_radio_button("", "set maximum to an absolute value\n(=) to toggle"),
        }
        
        # Named groups
        self.background_buttons = [radio_buttons[name] for name in ["bg_none", "bg_plane", "bg_linewise"]]
        self.min_radio_buttons = [radio_buttons[name] for name in ["min_full", "min_percentiles", "min_deviations", "min_absolute"]]
        self.max_radio_buttons = [radio_buttons[name] for name in ["max_full", "max_percentiles", "max_deviations", "max_absolute"]]
        
        # Add the button handles to the tooltips
        [radio_buttons[name].changeToolTip(f"gui.radio_buttons[\"{name}\"]", line = 10) for name in radio_buttons.keys()]
        
        # Add buttons to QButtonGroups for exclusive selection and check the defaults
        QGroup = QtWidgets.QButtonGroup
        self.background_button_group = QGroup()
        [self.background_button_group.addButton(button) for button in self.background_buttons]
        
        self.min_button_group = QGroup()
        self.max_button_group = QGroup()
        [self.min_button_group.addButton(button) for button in self.min_radio_buttons]
        [self.max_button_group.addButton(button) for button in self.max_radio_buttons]
        
        # Initialize
        checked_buttons = [radio_buttons[name] for name in ["min_full", "max_full", "bg_none"]]
        [button.setChecked(True) for button in checked_buttons]
        
        return radio_buttons

    def make_lines(self) -> dict:
        make_line = self.gui_items.line_widget
        
        lines = {
            "scan_control": make_line("h"),
            "background": make_line("h"),
            "matrix_operations": make_line("h")
        }
        
        return lines

    def make_progress_bars(self) -> dict:
        make_progress_bar = self.gui_items.make_progress_bar
        
        progress_bars = {
            "experiment": make_progress_bar("", "Experiment progress")
        }
        
        # Named groups
        self.experiment_controls = [progress_bars["experiment"]]
        [self.experiment_controls.append(self.buttons[name]) for name in ["start_pause", "stop", "save"]]
        
        # Add the progress_bar handles to the tooltips
        [progress_bars[name].changeToolTip(f"gui.buttons[\"{name}\"]", line = 10) for name in progress_bars.keys()]
        
        return progress_bars

    def make_layouts(self) -> dict:
        make_layout = self.gui_items.make_layout
        
        layouts = {
            "main": make_layout("h"),
            "left_side": make_layout("v"),
            "toolbar": make_layout("v"),
            
            "parameters_0": make_layout("v"),
            "scan_parameter_sets": make_layout("h"),
            
            "scan_parameters": make_layout("g"),
            
            "gains": make_layout("h"),
            "gain_parameter_sets": make_layout("h"),

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

            "background_buttons": make_layout("h"),
            "matrix_processing": make_layout("g"),
            "limits": make_layout("g"),
            "empty": make_layout("v"),
            
            "input": make_layout("h"),
            "experiment_controls": make_layout("h"),
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

    def make_image_view(self) -> pg.ImageView:
        make_image_view = self.gui_items.make_image_view
        
        image_view = make_image_view()
        
        return image_view

    def make_plot_widget(self) -> pg.PlotWidget:
        plot_widget = pg.PlotWidget()
        
        return plot_widget

    def make_widgets(self) -> dict:
        layouts = self.layouts
        make_sle = self.gui_items.make_slider_line_edit
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
            "lockins": QWgt()
        }
        
        self.coarse_control_widgets = [widgets[name] for name in ["coarse_actions", "arrows"]]     
        self.phase_slider = make_sle("", "Set complex phase phi in deg\n(= multiplication by exp(i * pi * phi rad / (180 deg)))")
        
        return widgets

    def make_consoles(self) -> dict:
        make_console = self.gui_items.make_console
        
        consoles = {
            "output": make_console("", "Output console"),
            "input": make_console("", "Input console")
        }
        
        consoles["output"].setReadOnly(True)
        consoles["input"].setReadOnly(False)
        consoles["input"].setMaximumHeight(30)
        [consoles[name].setStyleSheet("QTextEdit{ background-color: #101010; }") for name in ["output", "input"]]
        
        # Add the handles to the tooltips
        [consoles[name].changeToolTip(f"gui.consoles[\"{name}\"]", line = 10) for name in consoles.keys()]
        
        return consoles

    def make_tip_slider(self) -> QtWidgets.QSlider:
        make_slider = self.gui_items.make_slider
        
        tip_slider = make_slider("", "Tip height (nm)", orientation = "v")
        tip_slider.setEnabled(False)
        
        return tip_slider

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
        [layouts["connections"].addWidget(button, 0, i) for i, button in enumerate(self.connection_buttons)]

        # Experiment
        [layouts["experiment_controls"].addWidget(widget) for widget in self.experiment_controls]
        [layouts["experiment_fields"].addWidget(widget) for widget in self.experiment_parameter_fields]
        e_layout = layouts["experiment"]
        e_layout.addWidget(self.tip_slider, 0, 0, 3, 1)
        e_layout.addWidget(self.comboboxes["experiment"], 0, 1, 1, 2)
        e_layout.addWidget(self.comboboxes["direction"], 0, 3)
        # [e_layout.addWidget(self.comboboxes[name], 0, i + 1) for i, name in enumerate(["experiment", "direction"])]
        e_layout.addLayout(layouts["experiment_controls"], 1, 1, 1, 2)
        e_layout.addWidget(self.line_edits["experiment_filename"], 1, 3)
        e_layout.addLayout(layouts["experiment_fields"], 2, 1, 1, 3)
        
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
        #par_layout = layouts["parameters"]
        #par_layout.addWidget(self.tip_slider, 0, 0, 2, 1)
        #[par_layout.addWidget(box, 0, i) for i, box in enumerate(self.parameter_line_0)]
        #par_layout.addLayout(layouts["scan_parameter_sets"], 0, 1, 1, 3)        
        #[par_layout.addWidget(box, 1, i + 3) for i, box in enumerate(self.parameter_line_1)]

        # Gains
        [layouts["gains"].addWidget(widget) for i, widget in enumerate(self.gain_line_edits)]

        # Frame_grid
        [layouts["frame_grid_parameter_sets"].addWidget(buttons[f"grid_parameters_{i}"]) for i in range(6)]

        fg_layout = layouts["frame_grid"]
        fg_layout.addWidget(labels["frame"], 0, 0, 1, 2)
        fg_layout.addWidget(self.gui_items.line_widget("h"), 1, 0, 1, 2)
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
        fg_layout.addWidget(self.gui_items.line_widget("h"), 1, 2, 1, 2)
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
        
        # Image processing                
        cn_layout = layouts["channel_navigation"]
        cn_layout.addWidget(comboboxes["channels"], 4)
        cn_layout.addWidget(self.buttons["direction"], 1)
        [cn_layout.addWidget(self.buttons[name]) for name in ["fit_to_frame", "fit_to_range", "nanonis_mod1", "nanonis_mod2"]]
        
        [layouts["background_buttons"].addWidget(button) for button in self.background_buttons]
        [layouts["background_buttons"].addWidget(checkboxes[name]) for name in ["rotation", "offset"]]
        p_layout = layouts["matrix_processing"]
        [p_layout.addWidget(checkboxes[checkbox_name], 0, index) for index, checkbox_name in enumerate(["sobel", "normal", "laplace"])]
        p_layout.addWidget(checkboxes["gaussian"], 1, 1)
        p_layout.addWidget(line_edits["gaussian_width"], 1, 2)
        p_layout.addWidget(checkboxes["fft"], 1, 0)
        p_layout.addWidget(comboboxes["projection"], 2, 0)
        p_layout.addWidget(self.phase_slider, 2, 1, 1, 2)
        
        l_layout = layouts["limits"]
        self.limits_columns = [self.min_line_edits, self.min_radio_buttons, self.scale_buttons, self.max_radio_buttons, self.max_line_edits]
        for j, group in enumerate(self.limits_columns): [l_layout.addWidget(item, i, j) for i, item in enumerate(group)]

        ip_layout = layouts["image_processing"]
        ip_layout.addLayout(layouts["channel_navigation"])
        ip_layout.addWidget(labels["background_subtraction"])
        ip_layout.addLayout(layouts["background_buttons"])
        ip_layout.addWidget(self.gui_items.line_widget("h", 1))
        ip_layout.addWidget(labels["matrix_operations"])
        ip_layout.addLayout(p_layout)
        ip_layout.addWidget(self.gui_items.line_widget("h", 1))
        ip_layout.addWidget(labels["limits"])         
        ip_layout.addLayout(l_layout)
        
        #layouts["input"].addWidget(self.buttons["input"], 1)
        layouts["input"].addWidget(self.consoles["input"])
        
        return


    """
    def make_tabs(self) -> dict:
        QTW = QtWidgets.QTabWidget

        tab_widgets = {
            "coarse_control": QTW(),
            "scan_control": QTW()
        }

        [tab_widgets["coarse_conrol"].addTab(self.widgets[name]) for name in ["coarse_vertical", "coarse_horizontal"]]

        return tabs
    """



    # 4: Make widgets and groupboxes and set their layouts. Requires layouts.
    def make_groupboxes(self) -> dict:
        make_groupbox = self.gui_items.make_groupbox
        layouts = self.layouts
        
        groupboxes = {
            "connections": make_groupbox("Connections", "Connections to hardware (push to check/refresh)"),
            "coarse_control": make_groupbox("Coarse control", "Control the tip (use ctrl key to access these functions)"),
            "coarse_vertical": make_groupbox("Vertical", "Vertical coarse motion"),
            "coarse_horizontal": make_groupbox("Horizontal", "Vertical coarse motion"),

            "frame_grid": make_groupbox("Frame / grid", "Frame and grid parameters"),
            "gains": make_groupbox("Feedback gains", "Feedback gains"),

            "tip_prep": make_groupbox("Tip prep", "Tip preparation actions"),
            "parameters": make_groupbox("Scan parameters", "Scan parameters"),
            "image_processing": make_groupbox("Image processing", "Select the background subtraction, matrix operations and set the image range limits (use shift key to access these functions)"),
            "experiment": make_groupbox("Experiment", "Perform experiment"),
            
            "dummy": make_groupbox("Dummy", "Invisible groupbox to swap out layouts to make other groupboxes collapse")
        }

        QTW = QtWidgets.QTabWidget
        self.tab_widget = QTW()

        # Set layouts for the groupboxes
        groupbox_names = ["connections", "coarse_control", "coarse_horizontal", "coarse_vertical", "gains", "frame_grid", "tip_prep", "parameters", "experiment", "image_processing"]
        [groupboxes[name].setLayout(layouts[name]) for name in groupbox_names]

        # Make layouts of several groupboxes
        [layouts["coarse_control"].addWidget(groupboxes[name]) for name in ["coarse_horizontal", "coarse_vertical"]]
        [layouts["parameters"].addWidget(groupboxes[name]) for name in ["gains", "frame_grid"]]
        
        # Make tabs
        tabs = ["coarse_control", "tip_prep", "parameters", "image_processing", "lockins"]
        tab_names = ["Coarse", "Prep", "Parameters", "Processing", "Lock-ins"]
        [self.widgets[name0].setLayout(layouts[name0]) for name0 in tabs]
        [self.tab_widget.addTab(self.widgets[name0], name) for name0, name in zip(tabs, tab_names)]
        
        [self.layouts["toolbar"].addWidget(groupboxes[name]) for name in ["connections", "experiment"]] #, "coarse_control", "tip_prep", "parameters", "experiment", "image_processing"]]
        self.layouts["toolbar"].addWidget(self.tab_widget)

        return groupboxes



    # 5: Set up the main window layout
    def setup_main_window(self) -> None:
        layouts = self.layouts
        widgets = self.widgets

        # Aesthetics
        layouts["left_side"].setContentsMargins(0, 0, 0, 0)
        layouts["toolbar"].setContentsMargins(4, 4, 4, 4)
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



    def interconnect(self) -> None:
        [self.line_edits[name].editingFinished.connect(lambda name_0 = name: self.height_width_aspect(name_0)) for name in ["frame_width", "frame_height", "frame_aspect"]]
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

