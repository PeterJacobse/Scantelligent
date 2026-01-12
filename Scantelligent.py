import os, sys, re, html, yaml, cv2, pint, socket
import numpy as np
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton, QWidget, QLineEdit
from PyQt6 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg
from lib.image_functions import apply_gaussian, apply_fft, image_gradient, compute_normal, apply_laplace, complex_image_to_colors, background_subtract, get_image_statistics
from lib.functions import Experiments, CameraWorker, NanonisFunctions, TaskWorker
from lib.gui_functions import GUIFunctions
from time import sleep, time
from scipy.interpolate import griddata
from datetime import datetime

colors = {"red": "#ff4040", "darkred": "#800000", "green": "#00ff00", "darkgreen": "#005000", "white": "#ffffff", "blue": "#1090ff"}



class StreamRedirector(QtCore.QObject):
    output_written = QtCore.pyqtSignal(str)
    def __init__(self, parent = None):
        super().__init__(parent)
        self._buffer = ""

    def write(self, text):
        if not text:
            return
        # Accumulate text and only emit complete lines. This avoids
        # emitting lone "\n" chunks which caused extra blank lines
        # in the QTextEdit when using `append` for each write call.
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self.output_written.emit(line)

    def flush(self):
        # Emit any remaining partial line (no trailing newline)
        if self._buffer:
            self.output_written.emit(self._buffer)
            self._buffer = ""



class AppWindow(QtWidgets.QMainWindow):
    request_start = QtCore.pyqtSignal(str, int, int)
    start_tracking = QtCore.pyqtSignal(float, int, int) # sampling time, chunk_size, timeout
    request_stop = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        # Make the app window
        self.setWindowTitle("Scantelligent by Peter H. Jacobse")
        self.setGeometry(100, 100, 1400, 800) # x, y, width, height
        
        # Initialize parameters
        self.parameters_init()
        self.make_gui_items()

        # Create a central widget and main horizontal layout
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QtWidgets.QHBoxLayout(central_widget) # Main layout is horizontal

        # Left Section: Graphic and Console (grouped vertically)
        left_v_container = QtWidgets.QWidget()
        left_v_layout = QtWidgets.QVBoxLayout(left_v_container)
        left_v_layout.setContentsMargins(0, 0, 0, 0)

        # Create the pyqtgraph PlotWidget (Top of left section)
        pg.setConfigOption("imageAxisOrder", "row-major")
        self.image_view = pg.ImageView(view = pg.PlotItem())
        left_v_layout.addWidget(self.image_view, stretch = 4) 

        # Initialize the console
        self.console_output = QtWidgets.QTextEdit()
        self.console_output.setReadOnly(False)
        left_v_layout.addWidget(self.console_output, stretch = 1)

        # Redirect output to the console
        self.stdout_redirector = StreamRedirector()
        self.stdout_redirector.output_written.connect(self.append_to_console)
        sys.stdout = self.stdout_redirector
        now = datetime.now()
        self.logprint(now.strftime("Opening Scantelligent on %Y-%m-%d %H:%M:%S"), color = "white")

        # Ensure the central widget can receive keyboard focus
        central_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        central_widget.setFocus()
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.activateWindow()
        
        # Add the left container to the main horizontal layout, then add the buttons/controls to the right
        main_layout.addWidget(left_v_container, stretch = 4)
        main_layout.addLayout(self.draw_toolbar(), 1)

        # Activate buttons and keys
        self.connect_keys()

        # Check / set up hardware connections
        self.connect_nanonis()
        if hasattr(self, "nanonis_functions"): self.nanonis_functions.disconnect()

        # Set up the Experiments class and thread and connect signals and slots
        self.thread_pool = QtCore.QThreadPool()
        self.experiment_thread = QtCore.QThread()
        self.timer = QtCore.QTimer()

        self.logprint("Hello", "red")



    def parameters_init(self):
        self.paths = {
            "script": os.path.abspath(__file__), # The full path of Scanalyzer.py
            "parent_folder": os.path.dirname(os.path.abspath(__file__)),            
        }
        self.paths["lib"] = os.path.join(self.paths["parent_folder"], "lib")
        self.paths["sys"] = os.path.join(self.paths["parent_folder"], "sys")
        self.paths["config_file"] = os.path.join(self.paths["sys"], "config.yml")
        self.paths["icon_folder"] = os.path.join(self.paths["parent_folder"], "icons")

        icon_files = os.listdir(self.paths["icon_folder"])
        self.icons = {}
        for icon_file in icon_files:
            [icon_name, extension] = os.path.splitext(os.path.basename(icon_file))
            try:
                if extension == ".png": self.icons.update({icon_name: QtGui.QIcon(os.path.join(self.paths["icon_folder"], icon_file))})
            except:
                pass
        self.setWindowIcon(self.icons.get("scanalyzer"))

        # Some attributes
        self.channels = []
        self.channel = ""
        self.channel_index = 0
        self.max_channel_index = 0
        self.scale_toggle_index = 0
        self.ureg = pint.UnitRegistry()
        self.nanonis_online = False
        self.view_index = 0
        self.experiment_status = "idle"
        self.process = QtCore.QProcess(self)
        self.gui_functions = GUIFunctions()

        # Image processing flags
        self.processing_flags = {
            "direction": "forward",
            "background_subtraction": "none",
            "sobel": False,
            "gaussian": False,
            "laplace": False,
            "fft": False,
            "normal": False,
            "min_selection": 0,
            "max_selection": 0,
            "spec_locations": False
        }

        # Read the config file
        try:
            with open(self.paths.get("config_file"), "r") as file:
                config = yaml.safe_load(file)
                try:
                    scanalyzer_path = config["scanalyzer_path"]
                    scanalyzer_exists = os.path.exists(scanalyzer_path)
                    if scanalyzer_exists:
                        self.paths["scanalyzer_path"] = scanalyzer_path
                        self.logprint("Scanalyzer found and linked", "green")
                    else:
                        self.logprint("Warning: config file has a scanalyzer_path entry, but it doesn't point to an existing file.", "red")
                except Exception as e:
                    self.logprint("Warning: scanalyzer path could not be read. {e}", color = "red")
                
                try:
                    nanonis_settings = config["nanonis"]
                    tcp_ip = nanonis_settings.get("tcp_ip", "127.0.0.1")
                    tcp_port = nanonis_settings.get("tcp_port", 6501)
                    version_number = nanonis_settings.get("version_number", 13520)

                    camera_settings = config.get("camera")
                    camera_argument = camera_settings.get("argument", 0)

                    self.hardware = {
                        "nanonis_ip": tcp_ip,
                        "nanonis_port": tcp_port,
                        "nanonis_version": version_number,
                        "camera_argument": camera_argument
                    }
                    self.logprint("I found the config.yml file and was able to set up a dictionary called 'hardware'", color = "green")
                    self.logprint(f"  hardware.keys() = {self.hardware.keys()}", color = "blue")
                    self.logprint(f"  hardware.values() = {self.hardware.values()}", color = "blue")
                    
                except Exception as e:
                    self.logprint("Error: could not retrieve the Nanonis TCP settings.", color = "red")
        except Exception as e:
            self.logprint(f"Error: problem loading config.yml: {e}", color = "red")



    # GUI
    def make_gui_items(self) -> None:
        make_button = lambda *args, **kwargs: self.gui_functions.make_button(*args, parent = self, **kwargs)
        make_label = self.gui_functions.make_label
        make_radio_button = self.gui_functions.make_radio_button
        make_checkbox = self.gui_functions.make_checkbox
        make_combobox = self.gui_functions.make_combobox
        make_line_edit = self.gui_functions.make_line_edit
        make_layout = self.gui_functions.make_layout
        make_groupbox = self.gui_functions.make_groupbox
        QKey = QtCore.Qt.Key

        self.buttons = {
            "direction": make_button("", self.on_exit, "Change scan direction (X)", icon = self.icons.get("triple_arrow"), key_shortcut = QKey.Key_X),
            
            "scanalyzer": make_button("", self.launch_scanalyzer, "Launch Scanalyzer", self.icons.get("scanalyzer")),
            "nanonis": make_button("", self.update_icons, "Connect to Nanonis", self.icons.get("nanonis")),
            "mla": make_button("", self.update_icons, "Connect to the Multifrequency Lockin Amplifier", self.icons.get("imp")),
            "exit": make_button("", self.on_exit, "Exit scantelligent (Esc/X/E)", self.icons.get("escape")),

            "n": make_button("", self.update_icons, "Move the tip north", icon = self.icons.get("single_arrow"), key_shortcut = QKey.Key_Up, rotate_degrees = 270),
            "ne": make_button("", self.update_icons, "Move the tip northeast", icon = self.icons.get("single_arrow"), rotate_degrees = 315),
            "e": make_button("", self.update_icons, "Move the tip east", icon = self.icons.get("single_arrow"), key_shortcut = QKey.Key_Right, rotate_degrees = 0),
            "se": make_button("", self.update_icons, "Move the tip southeast", icon = self.icons.get("single_arrow"), rotate_degrees = 45),
            "s": make_button("", self.update_icons, "Move the tip south", icon = self.icons.get("single_arrow"), key_shortcut = QKey.Key_Down, rotate_degrees = 90),
            "sw": make_button("", self.update_icons, "Move the tip southwest", icon = self.icons.get("single_arrow"), rotate_degrees = 135),
            "w": make_button("", self.update_icons, "Move the tip west", icon = self.icons.get("single_arrow"), key_shortcut = QKey.Key_Left, rotate_degrees = 180),
            "nw": make_button("", self.update_icons, "Move the tip northwest", icon = self.icons.get("single_arrow"), rotate_degrees = 225),

            "full_data_range": make_button("", self.update_icons, "Set the image value range to the full data range (U)", self.icons.get("100"), key_shortcut = QKey.Key_U),
            "percentiles": make_button("", self.update_icons, "Set the image value range by percentiles (R)", self.icons.get("percentiles"), key_shortcut = QKey.Key_R),
            "standard_deviation": make_button("", self.update_icons, "Set the image value range by standard deviations (D)", self.icons.get("deviation"), key_shortcut = QKey.Key_D),
            "absolute_values": make_button("", self.update_icons, "Set the image value range by absolute values (A)", self.icons.get("numbers"), key_shortcut = QKey.Key_A),
        }
        print(self.buttons.keys())

        """
        self.buttons["direction"].setCheckable(True)
        self.buttons["spec_locations"].setCheckable(True)
        exit_shortcuts = [QtGui.QShortcut(QtGui.QKeySequence(keystroke), self) for keystroke in [QKey.Key_Q, QKey.Key_E, QKey.Key_Escape]]
        [exit_shortcut.activated.connect(self.on_exit) for exit_shortcut in exit_shortcuts]
        """
        self.labels = {
            "scan_summary": make_label("Scanalyzer by Peter H. Jacobse"),
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

            "in_output_folder": make_label("In output folder")
        }
        self.radio_buttons = {
            "bg_none": make_radio_button("", "None (0)", self.icons.get("0")),
            "bg_plane": make_radio_button("", "Plane (P)", self.icons.get("plane_subtract")),
            "bg_linewise": make_radio_button("", "Linewise (W)", self.icons.get("lines")),
            "bg_inferred": make_radio_button("", "None (0)", self.icons.get("0")),

            "min_full": make_radio_button("", "set to minimum value of scan data range; (-) to toggle"),
            "max_full": make_radio_button("", "set to maximum value of scan data range; (=) to toggle"),
            "min_percentiles": make_radio_button("", "set to minimum percentile of data range; (-) to toggle"),
            "max_percentiles": make_radio_button("", "set to maximum percentile of data range; (=) to toggle"),
            "min_deviations": make_radio_button("", "set to minimum = mean - n * standard deviation; (-) to toggle"),
            "max_deviations": make_radio_button("", "set to maximum = mean + n * standard deviation; (=) to toggle"),
            "min_absolute": make_radio_button("", "set minimum to an absolute value; (-) to toggle"),
            "max_absolute": make_radio_button("", "set maximum to an absolute value; (=) to toggle"),
        }
        self.radio_buttons["bg_none"].setChecked(True)
        # self.radio_buttons["min_full"].toggled.connect(self.load_process_display)

        self.checkboxes = {
            "sobel": make_checkbox("Sobel", "Compute the complex gradient d/dx + i d/dy; (B)", self.icons.get("derivative")),
            "laplace": make_checkbox("Laplace", "Compute the Laplacian (d/dx)^2 + (d/dy)^2; (C)", self.icons.get("laplacian")),
            "fft": make_checkbox("Fft", "Compute the 2D Fourier transform; (F)", self.icons.get("fourier")),
            "normal": make_checkbox("Normal", "Compute the z component of the surface normal (N)", self.icons.get("surface_normal")),
            "gauss": make_checkbox("Gauss", "Apply a Gaussian blur (G)", self.icons.get("gaussian")),
        }
        self.line_edits = {
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
        # self.line_edits["gaussian_width"].editingFinished.connect(self.load_process_display)
        
        self.comboboxes = {
            "channels": make_combobox("Channels", "Available scan channels", self.update_icons),
            "projection": make_combobox("Projection", "Select a projection or toggle with (H)", self.update_icons, items = ["re", "im", "abs", "arg (b/w)", "arg (hue)", "complex", "abs^2", "log(abs)"]),
            "experiments": make_combobox("Experiments", "Select an experiment", self.update_icons, items = ["simple_scan", "grid_sampling"]),
            "direction": make_combobox("Direction", "Select a scan direction / pattern", self.update_icons, items = ["nearest tip", "down", "up", "random"])
        }
        
        projection_toggle_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QKey.Key_H), self)
        projection_toggle_shortcut.activated.connect(self.update_icons)
        self.layouts = {
            "toolbar": make_layout("v"),
            "connections": make_layout("g"),
            "parameters": make_layout("g"),
            "file_channel_direction": make_layout("v"),
            "file_navigation": make_layout("h"),
            "channel_navigation": make_layout("h"),

            "bias_buttons": make_layout("h"),

            "coarse_actions": make_layout("g"),
            "coarse_motion": make_layout("h"),
            "arrow_keys": make_layout("g"),

            "experiments": make_layout("g"),
            "start_stop": make_layout("h"),

            "image_processing": make_layout("v"),
            "background_buttons": make_layout("h"),
            "matrix_processing": make_layout("g"),
            "limits": make_layout("g"),
            "spectra": make_layout("h"),
            "i/o": make_layout("g"),
            "empty": make_layout("v")
        }        
        self.groupboxes = {
            "connections": make_groupbox("Connections", "Connections to hardware (push to check/refresh)"),
            "parameters": make_groupbox("Scan parameters", "Scan parameters"),
            "coarse_motion": make_groupbox("Coarse motion", "Control the tip"),
            "image_processing": make_groupbox("Image processing", "Select the background subtraction, matrix operations and set the image range limits"),
            "experiments": make_groupbox("Experiment", "Perform experiments")
        }
        self.expanded_groups = {
            "scan_summary": True,
            "file_chan_dir": True,
            "image_processing": True,
            "associated_spectra": True,
            "i/o": True
        }
        
        return

    def draw_toolbar(self) -> QtWidgets.QVBoxLayout:

        def draw_connections_group() -> QtWidgets.QGroupBox:
            connections_layout = self.layouts["connections"]

            [self.tip_status_button, self.oscillation_on_button, self.camera_online_button, self.view_swap_button, session_folder_label, self.session_folder_button] = [
                QPushButton("Tip status: withdrawn"), QPushButton("MLA oscillation: off"), QPushButton("Camera: offline"), QPushButton("Active view: scan"), QLabel("Session folder:    "), QPushButton()
                ]
            session_folder_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignBottom)
            self.buttons["nanonis"].setStyleSheet("background-color: darkred;")
            self.buttons["mla"].setStyleSheet("background-color: darkred;")
            
            connections_layout.addWidget(self.buttons["scanalyzer"], 0, 0)
            connections_layout.addWidget(self.buttons["exit"], 0, 1)
            connections_layout.addWidget(self.buttons["nanonis"], 1, 0)
            connections_layout.addWidget(self.tip_status_button, 1, 1)
            connections_layout.addWidget(self.buttons["mla"], 2, 0)
            connections_layout.addWidget(self.oscillation_on_button, 2, 1)
            connections_layout.addWidget(self.camera_online_button, 3, 0)
            connections_layout.addWidget(self.view_swap_button, 3, 1)
            connections_layout.addWidget(session_folder_label, 4, 0)
            connections_layout.addWidget(self.session_folder_button, 4, 1)

            self.groupboxes["connections"].setLayout(connections_layout)

            return self.groupboxes["connections"]

        def draw_parameters_group() -> QtWidgets.QGroupBox:
            parameters_layout = self.layouts["parameters"]

            [self.nanonis_bias_box, self.swap_bias_button, self.mla_bias_box, self.I_fb_box] = self.parameter_boxes = [
                QLineEdit(), QPushButton("<swap>"), QLineEdit(), QLineEdit()
                ]
            [self.nanonis_bias_button, self.mla_bias_button, self.I_fb_button] = self.parameter_buttons = [
                QPushButton("V_Nanonis"), QPushButton("V_MLA"), QPushButton("I_fb")
                ]
            self.parameters_button = QPushButton("scan\nparameters")
            
            
            [self.layouts["bias_buttons"].addWidget(box, 1) for box in self.parameter_buttons[:2]]

            [parameters_layout.addWidget(self.parameter_boxes[i], 0, i) for i in range(len(self.parameter_boxes))]
            parameters_layout.addLayout(self.layouts["bias_buttons"], 1, 0, 1, 3)
            parameters_layout.addWidget(self.I_fb_button, 1, 3)
            parameters_layout.addWidget(self.parameters_button, 0, len(self.parameter_boxes), 2, 1)

            self.groupboxes["parameters"].setLayout(parameters_layout)

            return self.groupboxes["parameters"]

        def draw_coarse_motion_group():
            coarse_motion_layout = self.layouts["coarse_motion"]
            
            # Coarse actions
            coarse_actions_layout = self.layouts["coarse_actions"]
            [self.withdraw_button, self.retract_button, self.z_steps_box, self.h_steps_box, self.advance_button, self.minus_z_steps_box, self.approach_button] = self.action_buttons = [
                QPushButton("Withdraw,"), QPushButton("Retract"), QLineEdit("10"), QLineEdit("30"), QPushButton("adVance"), QLineEdit("2"), QPushButton("Auto approach")
                ]
            [self.withdraw_checkbox, self.retract_checkbox, self.move_checkbox, self.advance_checkbox, self.approach_checkbox] = self.action_checkboxes = [QtWidgets.QCheckBox() for _ in range(5)]
            [checkbox.setChecked(True) for checkbox in self.action_checkboxes]
            self.advance_checkbox.setChecked(False)
            
            # Checkboxes
            [coarse_actions_layout.addWidget(self.action_checkboxes[i], i, 0) for i in range(len(self.action_checkboxes))]
            
            # Buttons ans line edits
            coarse_actions_layout.addWidget(self.withdraw_button, 0, 1)
            coarse_actions_layout.addWidget(self.retract_button, 1, 1)
            coarse_actions_layout.addWidget(self.z_steps_box, 1, 2)
            coarse_actions_layout.addWidget(self.h_steps_box, 2, 2)
            coarse_actions_layout.addWidget(self.advance_button, 3, 1)
            coarse_actions_layout.addWidget(self.minus_z_steps_box, 3, 2)
            coarse_actions_layout.addWidget(self.approach_button, 4, 1)

            # Labels
            steps_label = QLabel("steps")
            move_label = QLabel("move")
            steps_in_direction_label = QLabel("steps in direction")
            steps_and_label = QLabel("steps, and")
            [label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter) for label in [steps_label, move_label, steps_in_direction_label, steps_and_label]]
            coarse_actions_layout.addWidget(steps_label, 1, 3)
            coarse_actions_layout.addWidget(move_label, 2, 1)            
            coarse_actions_layout.addWidget(steps_in_direction_label, 2, 3)
            coarse_actions_layout.addWidget(steps_and_label, 3, 3)

            coarse_motion_layout.addLayout(coarse_actions_layout)
            
            # Arrows
            arrow_keys = QWidget()
            arrow_keys_layout = self.layouts["arrow_keys"]
            self.arrow_buttons = [self.buttons["nw"], self.buttons["n"], self.buttons["ne"], self.buttons["w"], self.buttons["n"],
                                  self.buttons["e"], self.buttons["sw"], self.buttons["s"], self.buttons["se"]]
            [arrow_keys_layout.addWidget(self.arrow_buttons[i], 0, i) for i in range(3)]
            [arrow_keys_layout.addWidget(self.arrow_buttons[i + 3], 1, i) for i in range(3)]
            [arrow_keys_layout.addWidget(self.arrow_buttons[i + 6], 2, i) for i in range(3)]
            arrow_keys.setLayout(arrow_keys_layout)

            coarse_motion_layout.addWidget(arrow_keys)
            self.groupboxes["coarse_motion"].setLayout(coarse_motion_layout)

            return self.groupboxes["coarse_motion"]

        def draw_experiments_group():
            experiments_layout = self.layouts["experiments"]
            
            points_label = QLabel("Points:")
            points_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            self.points_box = QLineEdit("200")
            save_to_label = QLabel("Save data to:    ")
            save_to_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            self.save_to_button = QPushButton()

            start_stop_layout = self.layouts["start_stop"]
            self.progress_bar = QtWidgets.QProgressBar()
            self.progress_bar.setMinimum(0)
            self.progress_bar.setMaximum(100)
            self.progress_bar.setValue(0)

            self.start_stop_button = QtWidgets.QToolButton()
            self.start_stop_button.setIconSize(QtCore.QSize(20, 20))
            self.pause_button = QtWidgets.QToolButton()
            pause_icon = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPause)
            self.pause_button.setIcon(pause_icon)
            self.pause_button.setIconSize(QtCore.QSize(20, 20))
            start_stop_layout.addWidget(self.progress_bar)
            start_stop_layout.addWidget(self.start_stop_button)
            start_stop_layout.addWidget(self.pause_button)
            self.update_icons()

            experiments_layout.addWidget(self.comboboxes["experiments"], 0, 0)
            experiments_layout.addWidget(self.comboboxes["direction"], 0, 1)
            #experiments_layout.addWidget(self.experiment_status, 0, 2)
            experiments_layout.addWidget(points_label, 1, 0)
            experiments_layout.addWidget(self.points_box, 1, 1)
            experiments_layout.addWidget(save_to_label, 2, 0)
            experiments_layout.addWidget(self.save_to_button, 2, 1)
            experiments_layout.addLayout(start_stop_layout, 3, 0, 3, 1)
            self.groupboxes["experiments"].setLayout(experiments_layout)

            return self.groupboxes["experiments"]
       
        def draw_image_processing_group() -> QtWidgets.QGroupBox: # Image processing group
            self.layouts["image_processing"].addWidget(self.labels["background_subtraction"])
            
            # Background subtraction group
            self.bg_button_group = QtWidgets.QButtonGroup(self)
            background_buttons = [self.radio_buttons[button_name] for button_name in ["bg_none", "bg_plane", "bg_linewise", "bg_inferred"]]
            [self.bg_button_group.addButton(button) for button in background_buttons] # Add buttons to the QButtonGroup for exclusive selection
            [self.layouts["background_buttons"].addWidget(button) for button in background_buttons]
            self.radio_buttons["bg_none"].setChecked(True)
            self.layouts["image_processing"].addLayout(self.layouts["background_buttons"])
            self.layouts["image_processing"].addWidget(self.gui_functions.line_widget("h", 1))

            # Matrix operations
            self.layouts["image_processing"].addWidget(self.labels["matrix_operations"])
            matrix_layout = self.layouts["matrix_processing"]
            [matrix_layout.addWidget(self.checkboxes[checkbox_name], 0, index) for index, checkbox_name in enumerate(["sobel", "normal", "laplace"])]
            matrix_layout.addWidget(self.checkboxes["gauss"], 1, 0)
            matrix_layout.addWidget(self.labels["width"], 1, 1)
            matrix_layout.addWidget(self.line_edits["gaussian_width"], 1, 2)
            matrix_layout.addWidget(self.checkboxes["fft"], 2, 0)
            matrix_layout.addWidget(self.labels["show"], 2, 1)
            matrix_layout.addWidget(self.comboboxes["projection"], 2, 2)
            self.layouts["image_processing"].addLayout(matrix_layout)
            self.layouts["image_processing"].addWidget(self.gui_functions.line_widget("h", 1))

            # Limits control group
            self.layouts["image_processing"].addWidget(self.labels["limits"])
            limits_layout = self.layouts["limits"]
            min_line_edits = [self.line_edits[line_edit_name] for line_edit_name in ["min_full", "min_percentiles", "min_deviations", "min_absolute"]]
            min_radio_buttons = [self.radio_buttons[button_name] for button_name in ["min_full", "min_percentiles", "min_deviations", "min_absolute"]]
            scale_buttons = [self.buttons[button_name] for button_name in ["full_data_range", "percentiles", "standard_deviation", "absolute_values"]]            
            max_radio_buttons = [self.radio_buttons[button_name] for button_name in ["max_full", "max_percentiles", "max_deviations", "max_absolute"]]
            max_line_edits = [self.line_edits[line_edit_name] for line_edit_name in ["max_full", "max_percentiles", "max_deviations", "max_absolute"]]
            [self.line_edits[line_edit_name].setEnabled(False) for line_edit_name in ["min_full", "max_full"]]
            [self.min_button_group, self.max_button_group] = [QtWidgets.QButtonGroup(self), QtWidgets.QButtonGroup(self)]
            [self.min_button_group.addButton(button) for button in min_radio_buttons] # Min and max buttons are exclusive
            [self.max_button_group.addButton(button) for button in max_radio_buttons]
            [limits_layout.addWidget(line_edit, index, 0) for index, line_edit in enumerate(min_line_edits)]
            [limits_layout.addWidget(line_edit, index, 1) for index, line_edit in enumerate(min_radio_buttons)]
            [limits_layout.addWidget(line_edit, index, 2) for index, line_edit in enumerate(scale_buttons)]
            [limits_layout.addWidget(line_edit, index, 3) for index, line_edit in enumerate(max_radio_buttons)]
            [limits_layout.addWidget(line_edit, index, 4) for index, line_edit in enumerate(max_line_edits)]
            self.layouts["image_processing"].addLayout(limits_layout)

            # The startup default is 100%; set the buttons accordingly (without triggering the redrawing of the scan image)
            for button in [self.radio_buttons["min_full"], self.radio_buttons["max_full"]]:
                button.blockSignals(True)
                button.setChecked(True)
                button.blockSignals(False)

            self.groupboxes["image_processing"].setLayout(self.layouts["image_processing"])
            return self.groupboxes["image_processing"]

        # Make the toolbar. Overal layout is a QVBoxLayout
        self.layouts["toolbar"].setContentsMargins(4, 4, 4, 4)
        [self.layouts["toolbar"].addWidget(group) for group in [draw_connections_group(), draw_coarse_motion_group(), draw_parameters_group(), draw_experiments_group(), draw_image_processing_group()]]
        self.layouts["toolbar"].addStretch(1) # Add a stretch at the end to push buttons up

        return self.layouts["toolbar"]

    def connect_keys(self):
        # Open folder in file explorer
        QKey = QtCore.Qt.Key

        open_session_folder_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QKey.Key_1), self)
        open_session_folder_shortcut.activated.connect(self.open_session_folder)

        # Direction
        direction_toggle_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QKey.Key_X), self)
        direction_toggle_shortcut.activated.connect(self.on_toggle_direction)

        withdraw_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QKey.Key_W), self)
        withdraw_shortcut.activated.connect(self.toggle_withdraw)

        """
        # Image processing group
        # Background subtraction toggle buttons
        background_none_shortcut = QShortcut(QKeySequence(Qt.Key.Key_0), self)
        background_none_shortcut.activated.connect(lambda: self.on_bg_change("none"))
        background_plane_shortcut = QShortcut(QKeySequence(Qt.Key.Key_P), self)
        background_plane_shortcut.activated.connect(lambda: self.on_bg_change("plane"))
        background_inferred_shortcut = QShortcut(QKeySequence(Qt.Key.Key_I), self)
        background_inferred_shortcut.activated.connect(lambda: self.on_bg_change("inferred"))
        background_linewise_shortcut = QShortcut(QKeySequence(Qt.Key.Key_W), self)
        background_linewise_shortcut.activated.connect(lambda: self.on_bg_change("linewise"))

        # Matrix operations
        sobel_shortcut = QShortcut(QKeySequence(Qt.Key.Key_B), self)
        sobel_shortcut.activated.connect(lambda: self.toggle_matrix_processing("sobel", not self.sobel_button.isChecked()))
        normal_shortcut = QShortcut(QKeySequence(Qt.Key.Key_N), self)
        normal_shortcut.activated.connect(lambda: self.toggle_matrix_processing("normal", not self.normal_button.isChecked()))
        gauss_shortcut = QShortcut(QKeySequence(Qt.Key.Key_G), self)
        gauss_shortcut.activated.connect(lambda: self.toggle_matrix_processing("gaussian", not self.gauss_button.isChecked()))
        laplace_shortcut = QShortcut(QKeySequence(Qt.Key.Key_C), self)
        laplace_shortcut.activated.connect(lambda: self.toggle_matrix_processing("laplace", not self.laplace_button.isChecked()))
        fft_shortcut = QShortcut(QKeySequence(Qt.Key.Key_F), self)
        fft_shortcut.activated.connect(lambda: self.toggle_matrix_processing("fft", not self.fft_button.isChecked()))
        toggle_projections_shortcut = QShortcut(QKeySequence(Qt.Key.Key_H), self)
        toggle_projections_shortcut.activated.connect(self.toggle_projections)

        # Limits control group
        full_scale_shortcut = QShortcut(QKeySequence(Qt.Key.Key_U), self)
        full_scale_shortcut.activated.connect(lambda: self.on_full_scale("both"))
        percentile_shortcut = QShortcut(QKeySequence(Qt.Key.Key_R), self)
        percentile_shortcut.activated.connect(lambda: self.on_percentiles("both"))
        std_dev_shortcut = QShortcut(QKeySequence(Qt.Key.Key_D), self)
        std_dev_shortcut.activated.connect(lambda: self.on_standard_deviations("both"))
        abs_val_shortcut = QShortcut(QKeySequence(Qt.Key.Key_A), self)
        abs_val_shortcut.activated.connect(lambda: self.on_absolute_values("both"))

        toggle_min_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Minus), self)
        toggle_min_shortcut.activated.connect(lambda: self.toggle_limits("min"))
        toggle_max_shortcut = QShortcut(QKeySequence(Qt.Key.Key_Equal), self)
        toggle_max_shortcut.activated.connect(lambda: self.toggle_limits("max"))

        # Associated spectra group
        open_spectrum_shortcut = QShortcut(QKeySequence(Qt.Key.Key_O), self)
        open_spectrum_shortcut.activated.connect(self.load_spectroscopy_window)
        """
        # I/O group
        exit_shortcuts = [QtGui.QShortcut(QtGui.QKeySequence(keystroke), self) for keystroke in [QtCore.Qt.Key.Key_Q, QtCore.Qt.Key.Key_E, QtCore.Qt.Key.Key_Escape]]
        [exit_shortcut.activated.connect(self.on_exit) for exit_shortcut in exit_shortcuts]
        session_folder_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QKey.Key_T), self)
        session_folder_shortcut.activated.connect(self.open_session_folder)

    def logprint(self, message, timestamp: bool = True, color: str = "white"):
        """Print a timestamped message to the redirected stdout.

        Parameters:
        - message: text to print
        - timestamp: whether to prepend HH:MM:SS timestamp
        - color: optional CSS color name or hex (e.g. 'red' or '#ff0000')
        """
        current_time = datetime.now().strftime("%H:%M:%S")
        if color == "blue": timestamp = False
        if timestamp:
            timestamped_message = current_time + f">>  {message}"
        else:
            timestamped_message = f"{message}"

        # Escape HTML to avoid accidental tag injection, then optionally
        # wrap in a colored span so QTextEdit renders it in color.
        escaped = html.escape(timestamped_message)
        final = escaped
        
        if type(color) == str:
            if color in colors.keys():
                color = colors[color]
        
        if timestamp:
            final = f"<span style=\"color:{color}\">{escaped}</span></pre>"
        else:
            final = f"<pre><span style=\"color:{color}\">        {escaped}</span></pre>"

        # Print HTML text (QTextEdit.append will render it as rich text).
        print(final, flush = True)

    def append_to_console(self, text):
        self.console_output.append(text)

    def update_buttons(self):
        if self.nanonis_online:
            self.tip_status_button.setEnabled(True)
            self.buttons["nanonis"].setText("Nanonis: online")
            self.buttons["nanonis"].setStyleSheet(f"background-color: {colors["darkgreen"]};")
            
            [button.setEnabled(True) for button in self.action_buttons]
            [button.setEnabled(True) for button in self.arrow_buttons]
            [button.setEnabled(True) for button in self.parameter_buttons]
        else:
            self.buttons["nanonis"].setToolTip("Nanonis: offline")
            self.buttons["nanonis"].setStyleSheet(f"background-color: {colors["darkred"]};")
            
            [button.setEnabled(False) for button in self.action_buttons]
            [button.setEnabled(False) for button in self.arrow_buttons]
            [button.setEnabled(False) for button in self.parameter_buttons]
            
            if hasattr(self, "tip_status"): delattr(self, "tip_status")
            if hasattr(self, "nanonis_functions"): delattr(self, "nanonis_functions")
            if hasattr(self, "parameters"): delattr(self, "parameters")

        if not hasattr(self, "tip_status"):
            self.tip_status_button.setEnabled(False)
            self.logprint("Error: tip status unknown.", "red")
            self.tip_status_button.setText("Tip status: unknown")
            return False

        if self.tip_status["withdrawn"]:
            self.retract_button.setEnabled(True)
            self.advance_button.setEnabled(True)
            self.approach_button.setEnabled(True)

            self.tip_status_button.setText("Tip status: withdrawn")
            self.tip_status_button.setStyleSheet("background-color: darkred;")
            self.withdraw_button.setText("land (W)")
            self.withdraw_checkbox.setEnabled(False)

        else:
            self.retract_button.setEnabled(False)
            self.advance_button.setEnabled(False)
            self.approach_button.setEnabled(False)
        
            if self.tip_status["feedback"]:
                self.tip_status_button.setText("Tip status: in feedback")
                self.tip_status_button.setStyleSheet(f"background-color: {colors["darkgreen"]};")
                self.withdraw_button.setText("Withdraw,")
                self.withdraw_checkbox.setEnabled(True)
            else:
                self.tip_status_button.setText("Tip status: constant height")
                self.tip_status_button.setStyleSheet("background-color: darkorange;")
                self.withdraw_button.setText("Withdraw,")
                self.withdraw_checkbox.setEnabled(True)

        if not hasattr(self, "parameters"):
            self.logprint("Error: parameters could not be retrieved.")
            return False

        self.nanonis_bias_box.setText(f"{np.round(self.parameters["bias"], 3)}")
        self.I_fb_box.setText(f"{np.round(self.parameters["I_fb"] * 1E12, 3)}") # In pA
        #self.p_gain_box.setText(f"{np.round(self.parameters["p_gain"] * 1E12, 3)}") # In pm
        #self.t_const_box.setText(f"{np.round(self.parameters["t_const"] * 1E6, 3)}") # In us

    def on_next_chan(self):
        pass

    def on_previous_chan(self):
        pass

    def on_toggle_direction(self):
        if hasattr(self, "scan_direction") and self.scan_direction == "forward": self.scan_direction = "backward"
        else: self.scan_direction = "forward"

        self.direction_button.disconnect()
        self.direction_button.setChecked(self.scan_direction == "backward")
        self.direction_button.setText(f"direXion: {self.scan_direction}")
        self.direction_button.clicked.connect(self.on_toggle_direction)

        try:
            if hasattr(self, 'image_files') and len(self.image_files) > 0:
                self.load_process_display(new_scan = True)
        except Exception as e:
            print("Error toggling the scan direction")
            pass

    def get_next_indexed_filename(self, folder_path, base_name, extension):
        # Pattern to match files with the base name and exactly 3 digits for the index
        # \d{3} matches exactly three digits
        pattern = rf"^{re.escape(base_name)}_(\d{{3}}){re.escape(extension)}$"
        
        # List all files in the directory
        try:
            files = os.listdir(folder_path)
        except FileNotFoundError:
            # If the folder doesn't exist, the first file will be index 000
            return f"{base_name}_000{extension}"

        matching_indices = []
        for filename in files:
            match = re.match(pattern, filename)
            if match:
                # Extract the index and convert to int (int() handles leading zeros automatically)
                index = int(match.group(1))
                matching_indices.append(index)
        
        if matching_indices:
            # If files were found, find the highest index
            max_index = max(matching_indices)
            next_index = max_index + 1
        else:
            # If no matching files were found, start with index 0
            next_index = 0
            
        # Format the next index to be a 3-digit string with leading zeros if necessary
        formatted_index = f"{next_index:03d}"
        
        return f"{base_name}_{formatted_index}{extension}"

    def update_icons(self):
        try:
            match self.experiment_status:
                case "running":
                    start_stop_icon = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaStop)
                    self.pause_button.setEnabled(True)
                    [box.setEnabled(False) for box in [self.comboboxes["experiments"], self.comboboxes["direction"]]]
                case "idle":
                    start_stop_icon = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay)
                    self.pause_button.setEnabled(False)
                    [box.setEnabled(True) for box in [self.comboboxes["experiments"], self.comboboxes["direction"]]]
                case "paused":
                    start_stop_icon = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaStop)
                    self.pause_button.setEnabled(True)
                    self.pause_button.setChecked(True)
                    [box.setEnabled(False) for box in [self.comboboxes["experiments"], self.comboboxes["direction"]]]
                case _:
                    pass
            self.start_stop_button.setIcon(start_stop_icon)
        except Exception as e:
            self.logprint(e, color = "red")
            pass

    def view_toggle(self):
        # Toggle view between camera and scan
        print(f"View index is {self.view_index}")

        self.view_index = 1 - self.view_index
        
        if self.view_index == 1:
            self.view_swap_button.setText("View: camera")
            self.start_camera()
        else:
            self.view_swap_button.setText("View: scan")
            self.stop_camera()
        print(f"View index is {self.view_index}")

    def launch_scanalyzer(self):
        if hasattr(self, "paths") and "scanalyzer_path" in list(self.paths.keys()):
            try:
                scanalyzer_path = self.paths["scanalyzer_path"]
                python_executable = sys.executable
                self.logprint(f"Executing command: {python_executable} {scanalyzer_path}", color = "white")
                self.process.start(python_executable, [self.paths["scanalyzer_path"]])
            except Exception as e:
                self.logprint(f"Failed to launch Scanalyzer: {e}", color = "red")
        else:
            self.logprint("Error. Scanalyzer path unknown.", color = "red")

    def open_session_folder(self):
        if hasattr(self, "paths") and "session_path" in list(self.paths.keys()):
            try:
                session_path = self.paths["session_path"]
                self.logprint("Opening the session folder", color = "white")
                os.startfile(session_path)
            except Exception as e:
                self.logprint(f"Failed to open session folder: {e}", color = "red")
        else:
            self.logprint("Error. Session folder unknown.", color = "red")
        return

    def on_exit(self):
        """Ensures the thread is stopped when the window is closed."""
        #if self.is_camera_running:
        #    self.stop_camera()
        #event.accept()
        """
        self.experiments.stop() # Set stop flag
        self.experiment_thread.quit() # Quit the thread's event loop
        self.experiment_thread.wait() # Wait for the thread to actually finish
        """
        self.logprint("Thank you for using Scantelligent!", color = "green")
        QApplication.instance().quit()

    def closeEvent(self, event):
        self.on_exit()



    # Nanonis
    # Connect
    def connect_nanonis(self):
        self.logprint("Connecting to Nanonis", color = "white")
        try:
            # This is a low-level TCP-IP connection attempt
            self.logprint(f"  sock.connect(({self.hardware["nanonis_ip"]}, {self.hardware["nanonis_port"]}))", color = "blue")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.hardware["nanonis_ip"], self.hardware["nanonis_port"]))
            sock.close()
            sleep(.2) # Short delay is necessary to avoid having the hardware refuse the next connection request
            self.nanonis_online = True
    
        except socket.timeout:
            self.nanonis_online = False
        except Exception:
            self.nanonis_online = False
        
        finally:
            if self.nanonis_online:
                self.nanonis_functions = NanonisFunctions(hardware = self.hardware) # Make the NanonisFunctions available
                self.logprint("Success! I also created an instance of NanonisFunctions() called 'nanonis_functions'", color = "green")
                self.on_parameters_request()
                self.on_frame_request()
            else:
                self.logprint("Error: Failed to connect!", color = "red")
            self.update_buttons()

    def on_parameters_request(self):
        try:
            self.logprint("  tip_status = nanonis_functions.tip()", color = "blue")
            tip_status = self.nanonis_functions.tip()
            if tip_status == False:
                self.logprint("Error retrieving the tip status.", color = "red")
                self.nanonis_online = False
            else:
                self.tip_status = tip_status
            
            self.logprint("  parameters = nanonis_functions.get_parameters()", color = "blue")
            parameters = self.nanonis_functions.get_parameters()

            if parameters == False:
                self.logprint("Error retrieving the scan parameters.", color = "red")
                self.nanonis_online = False
            else:
                self.parameters = parameters
                self.paths["session_path"] = parameters["session_path"]
                self.session_folder_button.setText(self.paths["session_path"])

                experiment = self.experiment_box.currentText()
                self.paths["experiment_file"] = self.get_next_indexed_filename(self.paths["session_path"], experiment, ".hdf5")
                self.save_to_button.setText(self.paths["experiment_file"])

                self.logprint("I was able to retrieve the tip status and scan parameters and saved them to dictionaries called 'tip_status' and 'parameters'", color = "green")
                self.logprint(f"  tip_status.keys() = {tip_status.keys()};", color = "blue")
                self.logprint(f"  tip_status.values() = {tip_status.values()}", color = "blue")
                self.logprint(f"  parameters.keys() = {parameters.keys()};", color = "blue")
                self.logprint("The session_path that I obtained from Nanonis was added to the 'paths' dictionary", color = "white")

        except Exception as e:
            self.logprint("{e}", color = "red")
            return False

    def on_frame_request(self):
        try:
            if hasattr(self, "nanonis_functions"):
                self.logprint(f"  frame = nanonis_functions.get_frame()", color = "blue")
                frame = self.nanonis_functions.get_frame()

            if type(frame) == dict:
                self.frame = frame
                channels = frame["channel_names"]
                if type(channels) == list:
                    self.channel_select_box.clear()
                    self.channel_select_box.addItems(channels)
                
                self.logprint("I was able to read the scan frame data from Nanonis and saved it in a dictionary called 'frame'", color = "green")
                self.logprint(f"  frame.keys() = {self.frame.keys()}", color = "blue")
        except Exception as e:
            self.logprint({e}, color = "red")

    def on_nanonis_scan_request(self):
        direction = 0
        try:
            if hasattr(self, "frame"):
                channel_indices = self.frame["channel_indices"]
                channel_index = channel_indices[self.channel_select_box.currentIndex()]
                
                selected_scan = self.nanonis_functions.get_scan(channel_index, direction)
                if type(selected_scan) == np.ndarray:
                    self.selected_scan = selected_scan

                    # Check if scan is complete
                    nan_mask = np.isnan(selected_scan)
                    num_nans = np.count_nonzero(nan_mask)
                    num_values = np.count_nonzero(~nan_mask)

                    if self.experiment_status == "running":
                        if num_nans == 0: # Scan is finished because there were no NaN values found
                            self.logprint("Experiment completed!", color = "green")
                            self.change_experiment_status(request = "stop")
                        self.progress_bar.setValue(int(100 * num_values / (num_nans + num_values)))
                    

                    self.image_view.setImage(self.selected_scan)
                    self.image_view.autoRange()
            else:
                self.logprint("No dictionary 'frame' found", color = "red")
        except Exception as e:
            self.logprint(f"{e}", color = "red")

    # Simple Nanonis functions
    def toggle_withdraw(self):
        if not hasattr(self, "tip_status"):
            self.logprint("Error: tip status unknown.")
            return False
        
        if self.tip_status.get("withdrawn", True):
            self.logprint("  [dict] tip_status = nanonis_functions.tip(feedback = True)", color = "blue")
            tip_status = self.nanonis_functions.tip(feedback = True)
            if type(tip_status) == dict: self.tip_status = tip_status
        else:
            self.logprint("  [dict] tip_status = nanonis_functions.tip(withdraw = True)", color = "blue")
            tip_status = self.nanonis_functions.tip(withdraw = True)
            if type(tip_status) == dict: self.tip_status = tip_status

        self.update_buttons()
        return True

    def change_tip_status(self):
        if not hasattr(self, "tip_status"):
            self.logprint("Error: tip status unknown.", color = "red")
            return False
        
        if self.tip_status.get("withdrawn", True): # Land if withdrawn
            self.logprint("  [dict] tip_status = nanonis_functions.tip(feedback = True)", color = "blue")
            tip_status = self.nanonis_functions.tip(feedback = True)
            if type(tip_status) == dict: self.tip_status = tip_status
        else: # Toggle the feedback
            self.logprint("  [dict] tip_status = nanonis_functions.tip(feedback = not tip_status[\"feedback\"])", color = "blue")
            tip_status = self.nanonis_functions.tip(feedback = not self.tip_status["feedback"])
            if type(tip_status) == dict: self.tip_status = tip_status
        
        self.update_buttons()
        return True

    def on_bias_change(self, target: str = "Nanonis"):
        # Extract the target bias from the QLineEdit textbox
        V_new = float(self.nanonis_bias_box.text())

        self.logprint(f"  [float] V_old = nanonis_functions.change_bias({V_new})", color = "blue")

        #V_old = self.nanonis_functions.change_bias(V_new)
        # ^ This is the old-fashioned, non-threaded way
        self.task_worker = TaskWorker(self.nanonis_functions.change_bias, V_new)
        self.thread_pool.start(self.task_worker)
        self.parameters["bias"] = V_new

        return True

    def on_setpoint_change(self):
        I_fb = float(self.I_fb_box.text())
        I_fb *= 1E-12

        self.logprint(f"  [float] I_old = nanonis_functions.change_setpoint({I_fb})", color = "blue")
        I_old = self.nanonis_functions.change_feedback(I_fb)

        self.parameters["I_fb"] = I_fb

        return True

    # Experiments and thread management
    def on_experiment_change(self):
        self.experiment = self.experiment_box.currentText()
        self.paths["experiment_filename"] = self.get_next_indexed_filename(self.paths["session_path"], self.experiment, ".hdf5")
        self.save_to_button.setText(self.paths["experiment_filename"])
        return

    def change_experiment_status(self, request: str = "stop"):
        self.logprint(f"Request = {request}", color = "white")
        match request:
            case "pause":
                if self.experiment_status == "running":
                    self.nanonis_functions.scan_control(action = "pause")
                    self.experiment_status = "paused"
                    self.update_icons()
                    return
                else:
                    return
            case "stop":
                self.logprint(f"{self.timer}", color = "white")
                if hasattr(self, "timer"):
                    self.timer.stop()
                if self.experiment_status in ["idle", "paused", "running"]:
                    self.experiment_status = "idle"
                    self.nanonis_functions.scan_control(action = "stop")
                    self.update_icons()
                return
            case "resume":
                if self.experiment_status == "paused":
                    self.nanonis_functions.scan_control(action = "resume")
                    self.experiment_status = "running"
                    self.update_icons()
                return
            case _: # This is start
                if self.experiment_status == "running":
                    self.nanonis_functions.scan_control(action = "stop")
                    self.experiment_status = "idle"
                    if hasattr(self, "timer"):
                        self.timer.stop()
                    self.update_icons()
                    return
                else: # Only when no experiment is running and a start is requested will the code below be evaluated
                    pass

        # First, check if the TCP connection is okay
        if not self.nanonis_online:
            self.connect_nanonis()
            if not self.nanonis_online:
                self.logprint("Error! Could not establish a connection to Nanonis", color = "red")
                self.update_buttons()
                return False

        # Read the experiment type and parameters
        self.experiment = self.experiment_box.currentText()
        self.direction = self.direction_box.currentText()
        self.paths["experiment_filename"] = self.experiment
        self.paths["experiment_file"] = os.path.join(self.paths["session_path"], self.paths["experiment_filename"])

        # Choose the experiment
        match self.experiment:
            case "simple_scan":
                self.start_simple_scan()
            case "grid_sampling":
                self.start_grid_sampling()
            case _:
                self.logprint("Sorry, I don't know this experiment yet.", color = "red")
                return False

    def start_simple_scan(self):
        self.logprint(f"Starting experiment {self.experiment}")
        self.logprint(f"The experiment will be saved to {self.paths["experiment_file"]}")

        # Initialize the experiment
        self.frame = self.nanonis_functions.get_frame()
        self.x_grid = self.frame["x_grid"]
        self.y_grid = self.frame["y_grid"]

        # Read the direction
        dirxn = "down"
        match self.direction_box.currentText():
            case "down":
                dirxn = "down"
            case "up":
                dirxn = "up"
            case "nearest tip":
                # Retrieve the tip position
                self.nanonis_functions.connect_log()
                tip_position = self.nanonis_functions.get_xy()
                self.nanonis_functions.disconnect()
                sleep(.1)

                bottom_left_corner = self.frame["bottom_left_corner"]
                top_left_corner = self.frame["top_left_corner"]

                dx_bottom = tip_position[0] - bottom_left_corner[0]
                dy_bottom = tip_position[1] - bottom_left_corner[1]
                dx_top = tip_position[0] - top_left_corner[0]
                dy_top = tip_position[1] - top_left_corner[1]
                dist_bottom2 = dx_bottom ** 2 + dy_bottom ** 2
                dist_top2 = dx_top ** 2 + dy_top ** 2

                if dist_bottom2 < dist_top2: # Tip is closer to the bottom
                    dirxn = "up"
                else:
                    dirxn = "down"
            case _:
                self.logprint("I haven't learned how to do this direction yet", "red")
                dirxn = "down"
        
        self.experiment_status = "running"
        self.progress_bar.setValue(0)
        self.experiment_status = "running"
        [box.setEnabled(False) for box in [self.experiment_box, self.direction_box]]
        self.update_icons()

        self.channels = ["t (s)", "V (V)", "x (m)", "y (m)", "z (m)", "I (A)"]
        self.data_array = np.empty((100000, len(self.channels)), dtype = float)
        self.current_index = 0
        
        self.nanonis_functions.scan_control(action = "start", direction = dirxn)
        if not hasattr(self, "timer"):
            self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.on_nanonis_scan_request)
        self.timer.start(3000)

        """
        sampling_time = 1
        chunk_size = 12
        timeout = 100

        # Set up the threading connections
        self.worker = Experiments(self.hardware)
        self.experiment_thread = QThread()
        self.worker.moveToThread(self.experiment_thread)

        # Connect the start_tracking signal to the worker's tip_tracker slot

        self.start_tracking.connect(lambda: self.worker.tip_tracker(sampling_time, chunk_size, timeout))
        self.request_stop.connect(self.worker.stop)
        self.worker.data.connect(self.receive_data)
        self.worker.message.connect(self.receive_message)
        self.worker.progress.connect(self.receive_progress)
        self.worker.finished.connect(self.experiment_finished)
        self.worker.finished.connect(self.worker.deleteLater)
        self.experiment_thread.finished.connect(self.experiment_thread.deleteLater)

        self.experiment_thread.start()
        # Emit the signal after the thread has started, so it runs in the worker thread
        self.start_tracking.emit(sampling_time, chunk_size, timeout)

        self.worker.finished.connect(self.experiment_finished)
        self.experiment_thread.finished.connect(self.experiments.deleteLater)
        self.experiment_thread.finished.connect(self.experiment_thread.deleteLater)
        self.experiment_thread.start()
        """

    def start_grid_sampling(self):
        self.logprint(f"Starting experiment {self.experiment}")
        self.logprint(f"The experiment will be saved to {self.paths["experiment_file"]}")
        return False
        """
        self.logprint(f"Starting experiment {self.experiment}", color = "white")
        self.logprint(f"The experiment will be saved to {self.paths["experiment_file"]}", color = "white")

        points = int(self.points_box.text())
        self.grid = self.helper_functions.get_grid()
        [self.x_grid, self.y_grid] = [self.grid.x_grid, self.grid.y_grid]

        # Connect the correct experiment
        try:
            self.request_start.disconnect()
        except:
            pass
        self.request_start.connect(self.experiments.sample_grid)

        # Start the experiment
        self.experiment_status = "running"
        self.update_icons()
        
        self.data_array = np.empty((points, 71), dtype = float) # Initialize an empty numpy array for storing data
        self.current_index = 0
        chunk_size = 30
        self.request_start.emit(self.experiment_file, points, chunk_size)
        """

    def receive_data(self, data_chunk):
        chunk_size = data_chunk.shape[0]
        self.data_array[self.current_index : self.current_index + chunk_size] = data_chunk
        self.current_index += chunk_size

        xy_points = self.data_array[: self.current_index, 2:4]
        z_points = self.data_array[: self.current_index, 4]

        try:
            z_grid = np.flip(griddata(xy_points, z_points, (self.x_grid, self.y_grid), method = "linear"), axis = 1)
        except:
            z_grid = np.zeros_like(self.x_grid)
        
        processed_z_grid = z_grid

        self.image_view.setImage(processed_z_grid, autoRange = True)

    def receive_message(self, message_text, color_string):
        if color_string in colors.keys():
            self.logprint(message_text, color = color_string)
        else:
            self.logprint(message_text, color = "white")

    def receive_progress(self, progress):
        self.progress_bar.setValue(progress)

    def experiment_finished(self):
        self.logprint("Experiment finished", color = "green")
        self.nanonis_functions.scan_control(action = "stop")
        if hasattr(self, "experiment_thread"): self.experiment_thread.quit
        self.experiment_status = "idle"
        self.update_icons()
        self.paths["experiment_filename"] = self.get_next_indexed_filename(self.paths["session_path"], self.experiment, ".hdf5")
        self.save_to_button.setText(self.paths["experiment_filename"])
        self.nanonis_functions.scan_control(action = "stop")

        return True



    # Camera
    def check_camera_connection(self, argument):
        try:
            cap = cv2.VideoCapture(argument)
        except:
            self.camera_online = False

        if not cap.isOpened(): # Check if the camera opened successfully
            self.logprint("Error: Could not open camera.", color = "red")
            self.camera_online = False
        else:
            cap.release()
            self.camera_online = True
        
        if self.camera_online:
            self.camera_online_button.setText("Camera: online")
            self.camera_online_button.setStyleSheet(f"background-color: {colors["darkgreen"]};")
        else:
            self.camera_online_button.setText("Camera: offline")
            self.camera_online_button.setStyleSheet(f"background-color: {colors["darkred"]};")

    def update_image_display(self, frame):
        """Slot to receive the RGB frame and update the ImageView."""
        # pyqtgraph efficiently handles the NumPy array.
        # We set autoRange and autoLevels to False to prevent flicker.
        self.image_view.setImage(frame, autoRange = False, autoLevels = False)

    def start_camera(self):
        """Initializes and starts a NEW worker thread."""
        if self.is_camera_running:
            return
        
        self.image_view.setLevels(0, 255)
        self.image_view.ui.histogram.hide()
        self.image_view.ui.roiBtn.hide()
        self.image_view.ui.roiPlot.hide()

        # 1. Instantiate NEW Thread and Worker
        self.thread = QtCore.QThread()
        self.worker = CameraWorker(camera_index = 0) 
        self.worker.moveToThread(self.thread)

        # 2. Define ALL Connections HERE (Crucial Step)
        
        # Management Connections
        self.thread.started.connect(self.worker.start_capture)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        
        # NEW: Final cleanup connection, triggered AFTER the thread safely quits
        self.thread.finished.connect(self._post_camera_stop_cleanup)
        self.thread.finished.connect(self.thread.deleteLater)
        
        # Data Connection
        self.worker.frameCaptured.connect(self.update_image_display)

        # 3. Start Thread and Update UI State
        self.thread.start()
        self.is_camera_running = True
        self.camera_start_button.setEnabled(False)
        self.camera_stop_button.setEnabled(True)

    def stop_camera(self):
        """Signals the worker to stop and updates the button state immediately."""
        if not self.is_camera_running or not self.worker:
            return

        # 1. Signal the worker to stop its loop (non-blocking)
        self.worker.stop_capture() 
        
        # 2. Immediately disable buttons until cleanup is complete
        self.camera_start_button.setEnabled(False)
        self.camera_stop_button.setEnabled(False)
        
        # The final cleanup will be handled by the _post_thread_stop_cleanup slot
        # which is connected to self.thread.finished.

    def _post_camera_stop_cleanup(self):
        """Executes safely in the main thread after QThread.finished is emitted."""
        self.is_camera_running = False
        self.camera_start_button.setEnabled(True) 
        self.camera_stop_button.setEnabled(False)



# Main program
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())