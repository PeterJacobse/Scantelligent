import os
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
from . import GUIItems



class ScantelligentGUI:
    def __init__(self, icons_path):
        
        # 1: Read icons from file.
        self.icons_path = icons_path
        self.get_icons()
        
        # 2: Create the specific GUI items using the items from the GUIItems class. Requires icons.
        self.gui_items = GUIItems()
        self.labels = self.make_labels()
        self.buttons = self.make_buttons()
        self.checkboxes = self.make_checkboxes()
        self.comboboxes = self.make_comboboxes()
        self.line_edits = self.make_line_edits()
        self.radio_buttons = self.make_radio_buttons()
        self.lines = self.make_lines()
        
        # 3: Set up layouts and populate them with GUI items. Requires GUI items.
        self.layouts = self.make_layouts()
        
        # 4: Make widgets and set their layouts. Requires layouts.
        self.widgets = self.make_widgets()
        self.groupboxes = self.make_groupboxes()
        
        # 5: Define key shortcuts
        self.shortcuts = self.make_shortcuts()

        # 6: Create the pyqtgraph imageview
        self.image_view = self.make_image_view()



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

            "background_subtraction": make_label("Background subtraction"),
            "width": make_label("Width (nm):"),
            "show": make_label("Show", "Select a projection or toggle with (H)"),
            "limits": make_label("Set limits", "Toggle the min and max limits with (-) and (=), respectively"),
            "matrix_operations": make_label("Matrix operations"),

            "z_steps": make_label("steps"),
            "move": make_label("move"),
            "h_steps": make_label("steps in direction"),
            "steps_and": make_label("steps, and")
        }
        
        # Named groups
        self.steps_labels = [labels[name] for name in ["z_steps", "h_steps", "steps_and"]]
        
        return labels
    
    def make_buttons(self) -> dict:
        make_button = self.gui_items.make_button
        icons = self.icons
        arrow = icons.get("single_arrow")
        mtt = "Move the tip "
        sivr = "Set the image value range "

        buttons = {
            "scanalyzer": make_button("", "Launch Scanalyzer", icon = icons.get("scanalyzer")),
            "nanonis": make_button("", "Nanonis: offline\n(click to reconnect)", icon = icons.get("nanonis")),
            "mla": make_button("", "Connect to the Multifrequency Lockin Amplifier\n(M)", icon = icons.get("imp")),
            "camera": make_button("", "Camera on/off\n(C)", icon = icons.get("camera")),
            "exit": make_button("", "Exit scantelligent\n(Esc / X / E)", icon = icons.get("escape")),
            "oscillator": make_button("", "Oscillator on/off\n(O)", icon = icons.get("osc")),
            "view": make_button("", "Toggle the active view\n(V)", icon = icons.get("eye")),
            "session_folder": make_button("", "Open the session folder\n(1)", icon = icons.get("folder")),
            
            "tip": make_button("", "Tip status\n(Ctrl + Space to toggle feedback)", icon = icons.get("withdrawn")),
            "swap_bias": make_button("<>", "Swap the bias between Nanonis and the MLA"),
            "set": make_button("", "Set the new parameters\n(Ctrl + P)", icon = icons.get("set")),
            "get": make_button("", "Get parameters\n(P)", icon = icons.get("get")),
            "default_parameters_0": make_button("", "Load default parameter set 0", icon = icons.get("0")),
            "default_parameters_1": make_button("", "Load default parameter set 1", icon = icons.get("1")),
            "default_parameters_2": make_button("", "Load default parameter set 2", icon = icons.get("2")),
            
            "withdraw": make_button("", "Withdraw the tip\n(Ctrl + W)", icon = icons.get("withdraw")),
            "retract": make_button("", "Retract the tip from the surface\n(Ctrl + PgUp)", icon = icons.get("retract")),
            "advance": make_button("", "Advance the tip towards the surface\n(Ctrl + PgDown)", icon = icons.get("advance")),
            "approach": make_button("", "Initiate auto approach\n(Ctrl + A)", icon = icons.get("approach")),

            "n": make_button("", mtt + "north\n(Ctrl + ↑ / Ctrl + 8)", icon = arrow, rotate_icon = 270),
            "ne": make_button("", mtt + "northeast\n(Ctrl + 9)", icon = arrow, rotate_icon = 315),
            "e": make_button("", mtt + "east\n(Ctrl + → / Ctrl + 6)", icon = arrow, rotate_icon = 0),
            "se": make_button("", mtt + "southeast\n(Ctrl + 3)", icon = arrow, rotate_icon = 45),
            "s": make_button("", mtt + "south\n(Ctrl + ↓ / Ctrl + 2)", icon = arrow, rotate_icon = 90),
            "sw": make_button("", mtt + "southwest\n(Ctrl + 1)", icon = arrow, rotate_icon = 135),
            "w": make_button("", mtt + "west\n(Ctrl + ← / Ctrl + 4)", icon = arrow, rotate_icon = 180),
            "nw": make_button("", mtt + "northwest\n(Ctrl + 7)", icon = arrow, rotate_icon = 225),
            
            "save": make_button("", "Save the experiment results to file", icon = icons.get("floppy")),
            "start": make_button("", "Start experiment"),

            "direction": make_button("", "Change scan direction (X)", icon = icons.get("triple_arrow")),
            "full_data_range": make_button("", sivr + "to the full data range\n(U)", icons.get("100")),
            "percentiles": make_button("", sivr + "by percentiles\n(R)", icons.get("percentiles")),
            "standard_deviation": make_button("", sivr + "by standard deviations\n(D)", icons.get("deviation")),
            "absolute_values": make_button("", sivr + "by absolute values\n(A)", icons.get("numbers")),
        }
        
        # Named groups
        self.connection_buttons = [buttons[name] for name in ["nanonis", "camera", "mla", "exit", "scanalyzer", "view", "oscillator", "session_folder"]]
        self.arrow_buttons = [buttons[direction] for direction in ["nw", "n", "ne", "w", "n", "e", "sw", "s", "se"]]
        self.action_buttons = [buttons[name] for name in ["withdraw", "retract", "advance", "approach"]]
        self.scale_buttons = [buttons[name] for name in ["full_data_range", "percentiles", "standard_deviation", "absolute_values"]]

        # Add the button handles to the tooltips
        [buttons[name].changeToolTip(f"gui.buttons[\"{name}\"]", line = 10) for name in buttons.keys()]

        return buttons

    def make_checkboxes(self) -> dict:
        make_checkbox = self.gui_items.make_checkbox
        
        checkboxes = {
            "withdraw": make_checkbox("", "Include withdrawing of the tip during a tip move"),
            "retract": make_checkbox("", "Include retracting the tip during a tip move"),
            "move": make_checkbox("", "Allow horizontal tip motion"),
            "advance": make_checkbox("", "Include advancing the tip during a move"),
            "approach": make_checkbox("", "End the tip move with an auto approach"),

            "sobel": make_checkbox("Sobel", "Compute the complex gradient d/dx + i d/dy\n(Shift + S)", self.icons.get("derivative")),
            "laplace": make_checkbox("Laplace", "Compute the Laplacian (d/dx)^2 + (d/dy)^2\n(Shift + C)", self.icons.get("laplacian")),
            "fft": make_checkbox("Fft", "Compute the 2D Fourier transform\n(Shift + F)", self.icons.get("fourier")),
            "normal": make_checkbox("Normal", "Compute the z component of the surface normal\n(Shift + N)", self.icons.get("surface_normal")),
            "gauss": make_checkbox("Gauss", "Apply a Gaussian blur\n(Shift + G)", self.icons.get("gaussian")),
        }
        
        # Named groups
        self.action_checkboxes = [checkboxes[name] for name in ["withdraw", "retract", "move", "advance", "approach"]]
        [checkbox.setChecked(True) for checkbox in self.action_checkboxes]
        checkboxes["advance"].setChecked(False)

        # Add the button handles to the tooltips
        [checkboxes[name].changeToolTip(f"gui.checkboxes[\"{name}\"]", line = 10) for name in checkboxes.keys()]

        return checkboxes

    def make_comboboxes(self) -> dict:
        make_combobox = self.gui_items.make_combobox
        
        comboboxes = {
            "channels": make_combobox("Channels", "Available scan channels"),
            "projection": make_combobox("Projection", "Select a projection or toggle with\n(Shift + ↑)", items = ["re", "im", "abs", "arg (b/w)", "arg (hue)", "complex", "abs^2", "log(abs)"]),
            "experiments": make_combobox("Experiments", "Select an experiment", items = ["simple_scan", "grid_sampling"]),
            "direction": make_combobox("Direction", "Select a scan direction / pattern (X)", items = ["nearest tip", "down", "up", "random"])
        }
        
        # Add the button handles to the tooltips
        [comboboxes[name].changeToolTip(f"gui.comboboxes[\"{name}\"]", line = 10) for name in comboboxes.keys()]
        
        return comboboxes

    def make_line_edits(self) -> dict:
        make_line_edit = self.gui_items.make_line_edit
        buttons = self.buttons
        
        line_edits = {
            "z_steps": make_line_edit("20", "Steps in the +Z (retract) direction"),
            "h_steps": make_line_edit("100", "Steps in the horizontal direction"),
            "minus_z_steps": make_line_edit("0", "Steps in the -Z (advance) direction"),

            "nanonis_bias": make_line_edit("", "Nanonis bias\n(Ctrl + P) to set"),
            "mla_bias": make_line_edit("", "MLA bias\n(Ctrl + P) to set"),
            "I_fb": make_line_edit("", "Feedback current in pA\n(Ctrl + P) to set"),
            "p_gain": make_line_edit("", "Proportional gain in pm\n(Ctrl + P) to set"),
            "t_const": make_line_edit("", "Time constant in pm\n(Ctrl + P) to set"),

            "min_full": make_line_edit("", "minimum value of scan data range"),
            "max_full": make_line_edit("", "maximum value of scan data range"),
            "min_percentiles": make_line_edit("2", "minimum percentile of data range"),
            "max_percentiles": make_line_edit("98", "maximum percentile of data range"),
            "min_deviations": make_line_edit("2", "minimum = mean - n * standard deviation"),
            "max_deviations": make_line_edit("2", "maximum = mean + n * standard deviation"),
            "min_absolute": make_line_edit("0", "minimum absolute value"),
            "max_absolute": make_line_edit("1", "maximum absolute value"),

            "gaussian_width": make_line_edit("0", "Width in nm for Gaussian blur application"),
            "file_name": make_line_edit("", "Base name of the file when saved to png or hdf5")
        }
        
        # Named groups
        self.parameter_line_0 = [buttons["tip"], line_edits["nanonis_bias"], buttons["swap_bias"], line_edits["mla_bias"], line_edits["I_fb"], buttons["set"], buttons["get"]]
        self.parameter_line_1 = [buttons["default_parameters_0"], buttons["default_parameters_1"], buttons["default_parameters_2"], line_edits["p_gain"], line_edits["t_const"]]
        
        self.action_line_edits = [line_edits[name] for name in ["z_steps", "h_steps", "minus_z_steps"]]
        self.min_line_edits = [line_edits[name] for name in ["min_full", "min_percentiles", "min_deviations", "min_absolute"]]
        self.max_line_edits = [line_edits[name] for name in ["max_full", "max_percentiles", "max_deviations", "max_absolute"]]
        
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
        # self.background_button_group = QGroup(self)
        self.background_buttons = [radio_buttons[name] for name in ["bg_none", "bg_plane", "bg_linewise", "bg_inferred"]]
        #[self.background_button_group.addButton(button) for button in self.background_buttons]
        self.min_radio_buttons = [radio_buttons[name] for name in ["min_full", "min_percentiles", "min_deviations", "min_absolute"]]
        self.max_radio_buttons = [radio_buttons[name] for name in ["max_full", "max_percentiles", "max_deviations", "max_absolute"]]
        
        # Add the button handles to the tooltips
        [radio_buttons[name].changeToolTip(f"gui.radio_buttons[\"{name}\"]", line = 10) for name in radio_buttons.keys()]
        
        # Initialize
        radio_buttons["bg_none"].setChecked(True)
        
        return radio_buttons

    def make_lines(self) -> dict:
        make_line = self.gui_items.line_widget
        
        lines = {
            "background": make_line("h"),
            "matrix_operations": make_line("h")            
        }
        
        return lines



    # 3: Set up layouts and populate them with GUI items. Requires GUI items.
    def make_layouts(self) -> dict:
        make_layout = self.gui_items.make_layout
        
        layouts = {
            "main": make_layout("h"),
            "left_side": make_layout("v"),

            "toolbar": make_layout("v"),
            "connections": make_layout("g"),
            "parameters": make_layout("g"),
            "channel_navigation": make_layout("h"),

            "bias_buttons": make_layout("h"),

            "coarse_actions": make_layout("g"),
            "coarse_control": make_layout("h"),
            "arrows": make_layout("g"),

            "experiments": make_layout("g"),
            "start_stop": make_layout("h"),

            "image_processing": make_layout("v"),
            "background_buttons": make_layout("h"),
            "matrix_processing": make_layout("g"),
            "limits": make_layout("g"),
            "empty": make_layout("v")
        }
        
        # Add items to the layouts        
        [layouts["connections"].addWidget(button, int(i / 4), i % 4) for i, button in enumerate(self.connection_buttons)]
        
        ca_layout = layouts["coarse_actions"]
        [ca_layout.addWidget(checkbox, i, 0) for i, checkbox in enumerate(self.action_checkboxes)]
        [ca_layout.addWidget(button, i + int(i / 2), 1) for i, button in enumerate(self.action_buttons)]
        [ca_layout.addWidget(line_edit, i + 1, 2) for i, line_edit in enumerate(self.action_line_edits)]
        [ca_layout.addWidget(label, i + 1, 3) for i, label in enumerate(self.steps_labels)]
        
        [layouts["arrows"].addWidget(button, int(i / 3), i % 3) for i, button in enumerate(self.arrow_buttons)]
        [layouts["parameters"].addWidget(box, 0, i) for i, box in enumerate(self.parameter_line_0)]
        [layouts["parameters"].addWidget(box, 1, i) for i, box in enumerate(self.parameter_line_1)]
        [layouts["background_buttons"].addWidget(button) for button in self.background_buttons]
        
        p_layout = layouts["matrix_processing"]
        [p_layout.addWidget(self.checkboxes[name], 0, i) for i, name in enumerate(["sobel", "normal", "laplace"])]
        [p_layout.addWidget(self.checkboxes[name], i + 1, 0) for i, name in enumerate(["gauss", "fft"])]
        [p_layout.addWidget(self.labels[name], i + 1, 1) for i, name in enumerate(["width", "show"])]
        p_layout.addWidget(self.line_edits["gaussian_width"], 1, 2)
        p_layout.addWidget(self.comboboxes["projection"], 2, 2)        
        
        l_layout = layouts["limits"]
        [l_layout.addWidget(item, i, 0) for i, item in enumerate(self.min_line_edits)]
        [l_layout.addWidget(item, i, 1) for i, item in enumerate(self.min_radio_buttons)]
        [l_layout.addWidget(item, i, 2) for i, item in enumerate(self.scale_buttons)]
        [l_layout.addWidget(item, i, 3) for i, item in enumerate(self.max_radio_buttons)]
        [l_layout.addWidget(item, i, 4) for i, item in enumerate(self.max_line_edits)]
        
        ip_layout = layouts["image_processing"]
        ip_layout.addWidget(self.labels["background_subtraction"])
        ip_layout.addLayout(layouts["background_buttons"])
        ip_layout.addWidget(self.lines["background"])
        ip_layout.addWidget(self.labels["matrix_operations"])
        ip_layout.addLayout(layouts["matrix_processing"])
        ip_layout.addWidget(self.lines["matrix_operations"])
        ip_layout.addWidget(self.labels["limits"])            
        ip_layout.addLayout(layouts["limits"])
        
        layouts["coarse_control"].addLayout(ca_layout)
        layouts["coarse_control"].addLayout(layouts["arrows"])
        
        # Aesthetics
        layouts["toolbar"].setContentsMargins(4, 4, 4, 4)
        layouts["toolbar"].addStretch(1)
        
        return layouts



    # 4: Make widgets and set their layouts. Requires layouts.
    def make_widgets(self) -> dict:
        layouts = self.layouts
        QWgt = QtWidgets.QWidget
        
        widgets = {
            "central": QWgt(),
            "left_side": QWgt(),
            "coarse_actions": QWgt(),
            "arrows": QWgt()
        }
        
        # Set layouts to widgets
        #widgets["coarse_actions"].setLayout(layouts["coarse_actions"])
        #widgets["arrows"].setLayout(layouts["arrows"])
        
        # Set layouts that are assembled from widgets
        self.coarse_control_widgets = [widgets[name] for name in ["coarse_actions", "arrows"]]
        #[layouts["coarse_control"].addWidget(widget) for widget in [self.coarse_control_widgets]]        
        
        return widgets

    def make_groupboxes(self) -> dict:
        make_groupbox = self.gui_items.make_groupbox
        layouts = self.layouts
        
        groupboxes = {
            "connections": make_groupbox("Connections", "Connections to hardware (push to check/refresh)"),
            "parameters": make_groupbox("Scan parameters", "Scan parameters"),
            "coarse_control": make_groupbox("Coarse control", "Control the tip (use ctrl key to access these functions)"),
            "image_processing": make_groupbox("Image processing", "Select the background subtraction, matrix operations and set the image range limits (use shift key to access these functions)"),
            "experiments": make_groupbox("Experiments", "Perform experiments")
        }
        
        # Set layouts for the groupboxes
        [groupboxes[name].setLayout(layouts[name]) for name in ["connections", "coarse_control", "parameters", "image_processing"]]
        
        return groupboxes



    # 5: Define key shortcuts
    def make_shortcuts(self) -> dict:
        QKey = QtCore.Qt.Key
        QMod = QtCore.Qt.Modifier
        QSeq = QtGui.QKeySequence
        
        shortcuts = {
            "scanalyzer": QSeq(QKey.Key_S),
            "nanonis": QSeq(QKey.Key_N),
            "mla": QSeq(QKey.Key_M),
            "camera": QSeq(QKey.Key_C),
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
            
            "direction": QSeq(QKey.Key_X),            
            "full_data_range": QSeq(QMod.SHIFT | QKey.Key_U),
            "percentiles": QSeq(QMod.SHIFT | QKey.Key_R),
            "standard_deviation": QSeq(QMod.SHIFT | QKey.Key_D),
            "absolute_values": QSeq(QMod.SHIFT | QKey.Key_A)
        }
        
        # Add keys for moving in directions
        direction_keys = {"n": QKey.Key_Up, "ne": QKey.Key_9, "e": QKey.Key_Right, "se": QKey.Key_3, "s": QKey.Key_Down, "sw": QKey.Key_1, "w": QKey.Key_Left, "nw": QKey.Key_7}
        [shortcuts.update({direction: QSeq(QMod.CTRL | keystroke)}) for direction, keystroke in direction_keys.items()]
        
        return shortcuts



    # 6: Create the pyqtgraph imageview
    def make_image_view(self) -> pg.ImageView:
        pg.setConfigOption("imageAxisOrder", "row-major")
        
        return pg.ImageView(view = pg.PlotItem())
