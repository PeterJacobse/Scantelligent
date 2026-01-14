import os, sys, re, html, yaml, cv2, pint, socket
import numpy as np
from PyQt6 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg
from lib.functions import Experiments, CameraWorker, TaskWorker
from lib import GUIItems, GUI, Nanonis, ImageFunctions
from time import sleep, time
from scipy.interpolate import griddata
from datetime import datetime



colors = {"red": "#ff5050", "dark_red": "#800000", "green": "#00ff00", "dark_green": "#005000",
          "white": "#ffffff", "blue": "#20a0ff", "dark_orange": "#A05000", "black": "#000000", "purple": "#700080"}
style_sheets = {
    "neutral": f"background-color: {colors["black"]};",
    "connected": f"background-color: {colors["dark_green"]};",
    "disconnected": f"background-color: {colors["dark_red"]};",
    "running": f"background-color: {colors["blue"]};",
    "hold": f"background-color: {colors["dark_orange"]};",
    "idle": f"background-color: {colors["purple"]};"
    }



class StreamRedirector(QtCore.QObject):
    output_written = QtCore.pyqtSignal(str)
    def __init__(self, parent = None):
        super().__init__(parent)
        self._buffer = ""

    def write(self, text: str) -> None:
        if not text:
            return
        # Accumulate text and only emit complete lines. This avoids
        # emitting lone "\n" chunks which caused extra blank lines
        # in the QTextEdit when using `append` for each write call.
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self.output_written.emit(line)
        
        return

    def flush(self) -> None:
        # Emit any remaining partial line (no trailing newline)
        if self._buffer:
            self.output_written.emit(self._buffer)
            self._buffer = ""
        
        return



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
        self.gui_items_init()

        # Create a central widget and main horizontal layout, then a left_side_widget as a container for the ImageView and console
        central_widget = QtWidgets.QWidget()
        self.setCentralWidget(central_widget)
        left_side_widget = QtWidgets.QWidget()

        # Create the pyqtgraph PlotWidget (Top of left section)
        pg.setConfigOption("imageAxisOrder", "row-major")
        self.image_view = pg.ImageView(view = pg.PlotItem())
        self.layouts["left_side"].setContentsMargins(0, 0, 0, 0)
        self.layouts["left_side"].addWidget(self.image_view, stretch = 4) 
        
        # Left Section: Graphic and Console (grouped vertically)
        left_side_widget.setLayout(self.layouts["left_side"])
        self.layouts["main"].addWidget(left_side_widget, stretch = 4)
        self.layouts["main"].addLayout(self.draw_toolbar(), 1)
        central_widget.setLayout(self.layouts["main"])

        # Initialize the console, then activate keys and buttons
        self.console_init()
        self.config_init()
        self.connect_keys()

        # Ensure the central widget can receive keyboard focus
        central_widget.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        central_widget.setFocus()
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.activateWindow()

        # Check / set up hardware connections
        self.connect_nanonis()
        if hasattr(self, "nanonis"): self.nanonis.disconnect()

        # Set up the Experiments class and thread and connect signals and slots
        self.thread_pool = QtCore.QThreadPool()
        self.experiment_thread = QtCore.QThread()
        self.timer = QtCore.QTimer()



    def parameters_init(self) -> None:
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
        self.gui_functions = GUIItems()

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

        # Dict to keep track of the hardware and experiment status
        self.status = {
            "nanonis": "offline",
            "mla": "offline",
            "camera": "offline",
            "tip": "offline",
            "experiment": "idle"
        }

        return

    def gui_items_init(self) -> None:
        # Create the items that will be placed in the GUI
        QKey = QtCore.Qt.Key
        QMod = QtCore.Qt.Modifier

        #make_button = lambda *args, **kwargs: self.gui_functions.make_button(*args, parent = self, **kwargs)
        make_label = self.gui_functions.make_label
        make_radio_button = self.gui_functions.make_radio_button
        make_checkbox = self.gui_functions.make_checkbox
        make_combobox = self.gui_functions.make_combobox
        make_line_edit = self.gui_functions.make_line_edit
        make_layout = self.gui_functions.make_layout
        make_groupbox = self.gui_functions.make_groupbox
        
        self.gui = GUI(self.paths["icon_folder"])        
        buttons = self.gui.buttons
        shortcuts = self.gui.shortcuts
        
        # Connect the buttons to their respective functions
        connections = [["scanalyzer", self.launch_scanalyzer], ["nanonis", self.connect_nanonis], ["mla", self.update_icons],
                       ["camera", self.update_icons], ["exit", self.on_exit], ["tip_status", self.update_icons],
                       ["oscillator", self.update_icons], ["view", self.update_icons], ["session_folder", self.update_icons],
                       
                       ["nanonis_bias", self.update_icons], ["mla_bias", self.update_icons], ["swap_bias", self.update_icons],
                       ["set", self.connect_nanonis], ["get", self.update_icons], ["withdraw", self.toggle_withdraw],
                       ["retract", self.update_icons], ["advance", self.update_icons], ["approach", self.update_icons]
                       ]
        for connection in connections:
            name = connection[0]
            connected_function = connection[1]
            buttons[name].clicked.connect(connected_function)
            
            if name in shortcuts.keys():
                shortcut = QtGui.QShortcut(shortcuts[name], self)
                shortcut.activated.connect(connected_function)           

        # Add tooltips that include the button handle
        for button_name in buttons.keys():
            description = buttons[button_name].toolTip().split("\n")
            buttons[button_name].setToolTip(f"{description[0]}\ngui.buttons[\"{button_name}\"]")
            if len(description) > 1:
                if description[1] != "":
                    buttons[button_name].setToolTip(f"{description[0]}\n{description[1]}\ngui.buttons[\"{button_name}\"]")
        
        """
        self.buttons.update({
            #"scanalyzer": make_button("", self.launch_scanalyzer, "Launch Scanalyzer", self.icons.get("scanalyzer")),
            #"nanonis": make_button("", self.connect_nanonis, "Nanonis: offline\n(click to reconnect)", self.icons.get("nanonis")),
            #"mla": make_button("", self.update_icons, "Connect to the Multifrequency Lockin Amplifier\n()", self.icons.get("imp")),
            #"camera": make_button("", self.update_icons, "Camera on/off\n()", self.icons.get("scanalyzer")),
            #"exit": make_button("", self.on_exit, "Exit scantelligent\n(Esc / X / E)", self.icons.get("escape")),
            #"tip_status": make_button("Tip", self.update_icons, "Tip status\n(Space to toggle feedback on/off)"),
            #"oscillator": make_button("Osc", self.update_icons, "Oscillator on/off\n(Ctrl + O)"),
            #"view": make_button("Active view", self.update_icons, "Toggle the active view\n(V)"),
            #"session_folder": make_button("Session folder", self.update_icons, "Open the session folder\n(1)"),

            "nanonis_bias": make_button("V_nn", self.update_icons, "Nanonis bias\n()"),
            "mla_bias": make_button("V_mla", self.update_icons, "MLA bias\n()"),
            "swap_bias": make_button("<>", self.update_icons, "Swap the bias between Nanonis and the MLA\n()"),
            "set": make_button("Set", self.update_icons, "Set the new parameters\n(Ctrl + P)"),
            "get": make_button("Get", self.update_icons, "Get parameters\n(P)"),

            "withdraw": make_button("Withdraw", self.toggle_withdraw, "Withdraw the tip\n(Ctrl + W)",
                                   key_shortcut = QKey.Key_W, modifier = QMod.CTRL),
            "retract": make_button("Retract", self.update_icons, "Retract the tip from the surface\n(Ctrl + PgUp)",
                                   key_shortcut = QKey.Key_PageUp, modifier = QMod.CTRL),
            "advance": make_button("Advance", self.update_icons, "Advance the tip towards the surface\n(Ctrl + PgDown)",
                                   key_shortcut = QKey.Key_PageUp, modifier = QMod.CTRL),
            "approach": make_button("Approach", self.update_icons, "Initiate auto approach\n(Ctrl + A)",
                                    key_shortcut = QKey.Key_A, modifier = QMod.CTRL),

            "n": make_button("", lambda: self.on_coarse_move("n"), "Move the tip north\n(Ctrl + ↑ / Ctrl + 8)", icon = self.icons.get("single_arrow"),
                             key_shortcut = QKey.Key_Up, modifier = QMod.CTRL, rotate_degrees = 270),
            "ne": make_button("", lambda: self.on_coarse_move("ne"), "Move the tip northeast\n(Ctrl + 9)", icon = self.icons.get("single_arrow"),
                             key_shortcut = QKey.Key_9, modifier = QMod.CTRL, rotate_degrees = 315),
            "e": make_button("", lambda: self.on_coarse_move("e"), "Move the tip east\n(Ctrl + → / Ctrl + 6)", icon = self.icons.get("single_arrow"),
                             key_shortcut = QKey.Key_Right, modifier = QMod.CTRL, rotate_degrees = 0),
            "se": make_button("", lambda: self.on_coarse_move("se"), "Move the tip southeast\n(Ctrl + 3)", icon = self.icons.get("single_arrow"),
                             key_shortcut = QKey.Key_3, modifier = QMod.CTRL, rotate_degrees = 45),
            "s": make_button("", lambda: self.on_coarse_move("s"), "Move the tip south\n(Ctrl + ↓ / Ctrl + 2)", icon = self.icons.get("single_arrow"),
                             key_shortcut = QKey.Key_Down, modifier = QMod.CTRL, rotate_degrees = 90),
            "sw": make_button("", lambda: self.on_coarse_move("sw"), "Move the tip southwest\n(Ctrl + 1)", icon = self.icons.get("single_arrow"),
                             key_shortcut = QKey.Key_1, modifier = QMod.CTRL, rotate_degrees = 135),
            "w": make_button("", lambda: self.on_coarse_move("w"), "Move the tip west\n(Ctrl + ← / Ctrl + 4)", icon = self.icons.get("single_arrow"),
                             key_shortcut = QKey.Key_Left, modifier = QMod.CTRL, rotate_degrees = 180),
            "nw": make_button("", lambda: self.on_coarse_move("nw"), "Move the tip northwest\n(Ctrl + 7)", icon = self.icons.get("single_arrow"),
                             key_shortcut = QKey.Key_7, modifier = QMod.CTRL, rotate_degrees = 225),

            "direction": make_button("", self.on_exit, "Change scan direction (X)", icon = self.icons.get("triple_arrow"), key_shortcut = QKey.Key_X),

            "full_data_range": make_button("", self.update_icons, "Set the image value range to the full data range\n(U)", self.icons.get("100"), key_shortcut = QKey.Key_U),
            "percentiles": make_button("", self.update_icons, "Set the image value range by percentiles\n(R)", self.icons.get("percentiles"), key_shortcut = QKey.Key_R),
            "standard_deviation": make_button("", self.update_icons, "Set the image value range by standard deviations\n(D)", self.icons.get("deviation"), key_shortcut = QKey.Key_D),
            "absolute_values": make_button("", self.update_icons, "Set the image value range by absolute values\n(A)", self.icons.get("numbers"), key_shortcut = QKey.Key_A),
        })
        """

        self.buttons = buttons
        
        self.labels = {
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
            "withdraw": make_checkbox("", "Include withdrawing of the tip during a tip move"),
            "retract": make_checkbox("", "Include retracting the tip during a tip move"),
            "move": make_checkbox("", "Allow horizontal tip motion"),
            "advance": make_checkbox("", "Include advancing the tip during a move"),
            "approach": make_checkbox("", "End the tip move with an auto approach"),

            "sobel": make_checkbox("Sobel", "Compute the complex gradient d/dx + i d/dy; (B)", self.icons.get("derivative")),
            "laplace": make_checkbox("Laplace", "Compute the Laplacian (d/dx)^2 + (d/dy)^2; (C)", self.icons.get("laplacian")),
            "fft": make_checkbox("Fft", "Compute the 2D Fourier transform; (F)", self.icons.get("fourier")),
            "normal": make_checkbox("Normal", "Compute the z component of the surface normal (N)", self.icons.get("surface_normal")),
            "gauss": make_checkbox("Gauss", "Apply a Gaussian blur (G)", self.icons.get("gaussian")),
        }
        self.line_edits = {
            "z_steps": make_line_edit("20", "Steps in the +Z (retract) direction"),
            "h_steps": make_line_edit("100", "Steps in the horizontal direction"),
            "minus_z_steps": make_line_edit("0", "Steps in the -Z (advance) direction"),

            "nanonis_bias": make_line_edit("", "Nanonis bias (ctrl + P to get)"),
            "mla_bias": make_line_edit("", "MLA bias (ctrl + P to get)"),
            "I_fb": make_line_edit("", "Feedback current in pA (ctrl + P to get)"),

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
        
        self.layouts = {
            "main": make_layout("h"),
            "left_side": make_layout("v"),

            "toolbar": make_layout("v"),
            "connections": make_layout("g"),
            "parameters": make_layout("g"),
            "file_channel_direction": make_layout("v"),
            "file_navigation": make_layout("h"),
            "channel_navigation": make_layout("h"),

            "bias_buttons": make_layout("h"),

            "coarse_actions": make_layout("g"),
            "coarse_control": make_layout("h"),
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
            "coarse_control": make_groupbox("Coarse control", "Control the tip (use ctrl key to access these functions)"),
            "image_processing": make_groupbox("Image processing", "Select the background subtraction, matrix operations and set the image range limits (use shift key to access these functions)"),
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

    def console_init(self) -> None:
        # Initialize the console
        self.console_output = QtWidgets.QTextEdit()
        self.console_output.setReadOnly(True)
        self.layouts["left_side"].addWidget(self.console_output, stretch = 1)

        # Redirect output to the console
        self.stdout_redirector = StreamRedirector()
        self.stdout_redirector.output_written.connect(lambda text: self.console_output.append(text))
        sys.stdout = self.stdout_redirector
        now = datetime.now()
        self.logprint(now.strftime("Opening Scantelligent on %Y-%m-%d %H:%M:%S"), color = "white")

        return

    def config_init(self) -> None:
        # Read the config file and instantiate hardware configurations

        try:
            with open(self.paths.get("config_file"), "r") as file:
                config = yaml.safe_load(file)
                try:
                    scanalyzer_path = config["scanalyzer_path"]
                    scanalyzer_exists = os.path.exists(scanalyzer_path)
                    if scanalyzer_exists:
                        self.paths["scanalyzer_path"] = scanalyzer_path
                        self.logprint("Scanalyzer found and linked", color = "green")
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
                    self.logprint(f"  [dict] hardware = {self.hardware}", color = "blue")
                    
                except Exception as e:
                    self.logprint("Error: could not retrieve the Nanonis TCP settings.", color = "red")
        except Exception as e:
            self.logprint(f"Error: problem loading config.yml: {e}", color = "red")
        
        return



    # Miscellaneous
    def logprint(self, message: str, timestamp: bool = True, color: str = "white") -> None:
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

        # Escape HTML to avoid accidental tag injection, then optionally wrap in a colored span so QTextEdit renders it in color.
        escaped = html.escape(timestamped_message)
        final = escaped
        
        if type(color) == str:
            if color in colors.keys():
                color = colors[color]
        
        if timestamp:
            final = f"<span style=\"color:{color}\">{escaped}</span>"
        else:
            final = f"<pre><span style=\"color:{color}\">        {escaped}</span></pre>"

        # Print HTML text (QTextEdit.append will render it as rich text).
        print(final, flush = True)

    def get_next_indexed_filename(self, folder_path, base_name, extension) -> str:
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

    # GUI setup
    def draw_toolbar(self) -> QtWidgets.QVBoxLayout:

        def draw_connections_group() -> QtWidgets.QGroupBox:
            buttons = self.gui.buttons
            layout = self.layouts["connections"]
            
            layout.addWidget(buttons["scanalyzer"], 0, 0)
            layout.addWidget(buttons["exit"], 0, 4)
            layout.addWidget(buttons["nanonis"], 0, 1)
            layout.addWidget(buttons["tip_status"], 1, 1)
            layout.addWidget(buttons["mla"], 0, 2)
            layout.addWidget(buttons["oscillator"], 1, 2)
            layout.addWidget(buttons["camera"], 0, 3)
            layout.addWidget(buttons["view"], 1, 3)
            layout.addWidget(self.labels["session_folder"], 1, 0)
            layout.addWidget(buttons["session_folder"], 1, 4)

            self.groupboxes["connections"].setLayout(layout)

            return self.groupboxes["connections"]

        def draw_parameters_group() -> QtWidgets.QGroupBox:
            buttons = self.gui.buttons
            line_edits = self.line_edits
            layout = self.layouts["parameters"]

            self.parameter_boxes = [line_edits["nanonis_bias"], buttons["swap_bias"], line_edits["mla_bias"], line_edits["I_fb"], buttons["set"], buttons["get"]]
             
            #[self.layouts["bias_buttons"].addWidget(box, 1) for box in self.parameter_buttons[:2]]
            [layout.addWidget(self.parameter_boxes[i], 0, i) for i in range(len(self.parameter_boxes))]
            #parameters_layout.addLayout(self.layouts["bias_buttons"], 1, 0, 1, 3)
            #parameters_layout.addWidget(self.I_fb_button, 1, 3)
            #parameters_layout.addWidget(self.parameters_button, 0, len(self.parameter_boxes), 2, 1)

            self.groupboxes["parameters"].setLayout(layout)

            return self.groupboxes["parameters"]

        def draw_coarse_control_group() -> QtWidgets.QGroupBox:
            buttons = self.gui.buttons
            layout = self.layouts["coarse_control"]
            
            # Coarse actions
            coarse_actions_layout = self.layouts["coarse_actions"]
            self.action_buttons = [buttons[name] for name in ["withdraw", "retract", "advance", "approach"]]
            self.action_checkboxes = [self.checkboxes[name] for name in ["withdraw", "retract", "move", "advance", "approach"]]
            [checkbox.setChecked(True) for checkbox in self.action_checkboxes]
            self.checkboxes["advance"].setChecked(False)
            
            [coarse_actions_layout.addWidget(self.action_checkboxes[i], i, 0) for i in range(len(self.action_checkboxes))]
            coarse_actions_layout.addWidget(buttons["withdraw"], 0, 1)
            coarse_actions_layout.addWidget(buttons["retract"], 1, 1)
            coarse_actions_layout.addWidget(self.line_edits["z_steps"], 1, 2)
            coarse_actions_layout.addWidget(self.line_edits["h_steps"], 2, 2)
            coarse_actions_layout.addWidget(buttons["advance"], 3, 1)
            coarse_actions_layout.addWidget(self.line_edits["minus_z_steps"], 3, 2)
            coarse_actions_layout.addWidget(buttons["approach"], 4, 1)

            # Labels
            [coarse_actions_layout.addWidget(self.labels[name], index + 1, 3) for index, name in enumerate(["z_steps", "h_steps", "steps_and"])]
            coarse_actions_layout.addWidget(self.labels["move"], 2, 1)
            layout.addLayout(coarse_actions_layout)
            
            # Arrows
            arrow_keys = QtWidgets.QWidget()
            arrow_keys_layout = self.layouts["arrow_keys"]
            self.arrow_buttons = [buttons[direction] for direction in ["nw", "n", "ne", "w", "n", "e", "sw", "s", "se"]]
            [arrow_keys_layout.addWidget(self.arrow_buttons[i], 0, i) for i in range(3)]
            [arrow_keys_layout.addWidget(self.arrow_buttons[i + 3], 1, i) for i in range(3)]
            [arrow_keys_layout.addWidget(self.arrow_buttons[i + 6], 2, i) for i in range(3)]
            arrow_keys.setLayout(arrow_keys_layout)

            layout.addWidget(arrow_keys)
            self.groupboxes["coarse_control"].setLayout(layout)

            return self.groupboxes["coarse_control"]

        def draw_experiments_group() -> QtWidgets.QGroupBox:
            experiments_layout = self.layouts["experiments"]
            
            save_to_label = QtWidgets.QLabel("Save data to:    ")
            save_to_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight)
            self.save_to_button = QtWidgets.QPushButton()

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
            #experiments_layout.addWidget(points_label, 1, 0)
            #experiments_layout.addWidget(self.points_box, 1, 1)
            experiments_layout.addWidget(save_to_label, 2, 0)
            experiments_layout.addWidget(self.save_to_button, 2, 1)
            experiments_layout.addLayout(start_stop_layout, 3, 0, 3, 1)
            self.groupboxes["experiments"].setLayout(experiments_layout)

            return self.groupboxes["experiments"]
       
        def draw_image_processing_group() -> QtWidgets.QGroupBox: # Image processing group
            buttons = self.gui.buttons
            layout = self.layouts["image_processing"]
            layout.addWidget(self.labels["background_subtraction"])
            
            # Background subtraction group
            self.bg_button_group = QtWidgets.QButtonGroup(self)
            background_buttons = [self.radio_buttons[button_name] for button_name in ["bg_none", "bg_plane", "bg_linewise", "bg_inferred"]]
            [self.bg_button_group.addButton(button) for button in background_buttons] # Add buttons to the QButtonGroup for exclusive selection
            [self.layouts["background_buttons"].addWidget(button) for button in background_buttons]
            self.radio_buttons["bg_none"].setChecked(True)
            layout.addLayout(self.layouts["background_buttons"])
            layout.addWidget(self.gui_functions.line_widget("h", 1))

            # Matrix operations
            layout.addWidget(self.labels["matrix_operations"])
            matrix_layout = self.layouts["matrix_processing"]
            [matrix_layout.addWidget(self.checkboxes[checkbox_name], 0, index) for index, checkbox_name in enumerate(["sobel", "normal", "laplace"])]
            matrix_layout.addWidget(self.checkboxes["gauss"], 1, 0)
            matrix_layout.addWidget(self.labels["width"], 1, 1)
            matrix_layout.addWidget(self.line_edits["gaussian_width"], 1, 2)
            matrix_layout.addWidget(self.checkboxes["fft"], 2, 0)
            matrix_layout.addWidget(self.labels["show"], 2, 1)
            matrix_layout.addWidget(self.comboboxes["projection"], 2, 2)
            layout.addLayout(matrix_layout)
            layout.addWidget(self.gui_functions.line_widget("h", 1))

            # Limits control group
            self.layouts["image_processing"].addWidget(self.labels["limits"])
            limits_layout = self.layouts["limits"]
            min_line_edits = [self.line_edits[name] for name in ["min_full", "min_percentiles", "min_deviations", "min_absolute"]]
            min_radio_buttons = [self.radio_buttons[name] for name in ["min_full", "min_percentiles", "min_deviations", "min_absolute"]]
            scale_buttons = [buttons[name] for name in ["full_data_range", "percentiles", "standard_deviation", "absolute_values"]]            
            max_radio_buttons = [self.radio_buttons[name] for name in ["max_full", "max_percentiles", "max_deviations", "max_absolute"]]
            max_line_edits = [self.line_edits[name] for name in ["max_full", "max_percentiles", "max_deviations", "max_absolute"]]
            [self.line_edits[name].setEnabled(False) for name in ["min_full", "max_full"]]
            [self.min_button_group, self.max_button_group] = [QtWidgets.QButtonGroup(self), QtWidgets.QButtonGroup(self)]
            [self.min_button_group.addButton(button) for button in min_radio_buttons] # Min and max buttons are exclusive
            [self.max_button_group.addButton(button) for button in max_radio_buttons]
            [limits_layout.addWidget(line_edit, index, 0) for index, line_edit in enumerate(min_line_edits)]
            [limits_layout.addWidget(line_edit, index, 1) for index, line_edit in enumerate(min_radio_buttons)]
            [limits_layout.addWidget(line_edit, index, 2) for index, line_edit in enumerate(scale_buttons)]
            [limits_layout.addWidget(line_edit, index, 3) for index, line_edit in enumerate(max_radio_buttons)]
            [limits_layout.addWidget(line_edit, index, 4) for index, line_edit in enumerate(max_line_edits)]
            layout.addLayout(limits_layout)

            # The startup default is 100%; set the buttons accordingly (without triggering the redrawing of the scan image)
            for button in [self.radio_buttons["min_full"], self.radio_buttons["max_full"]]:
                button.blockSignals(True)
                button.setChecked(True)
                button.blockSignals(False)

            self.groupboxes["image_processing"].setLayout(layout)
            
            return self.groupboxes["image_processing"]

        layout = self.layouts["toolbar"]
        # Make the toolbar. Overal layout is a QVBoxLayout
        layout.setContentsMargins(4, 4, 4, 4)
        [layout.addWidget(group) for group in [draw_connections_group(), draw_coarse_control_group(), draw_parameters_group(), draw_experiments_group(), draw_image_processing_group()]]
        layout.addStretch(1) # Add a stretch at the end to push buttons up

        return layout

    def connect_keys(self) -> None:
        QKey = QtCore.Qt.Key

        projection_toggle_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QKey.Key_H), self)
        projection_toggle_shortcut.activated.connect(self.update_icons)

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

    # Update GUI according to hardware status
    def update_buttons(self) -> None:
        buttons = self.gui.buttons
        # Activate/deactivate and color buttons according to hardware status

        if self.status["nanonis"] == "online":
            buttons["tip_status"].setEnabled(True)
            buttons["nanonis"].changeToolTip("Nanonis: online")
            buttons["nanonis"].setStyleSheet(style_sheets["connected"])
            
            [button.setEnabled(True) for button in self.action_buttons]
            [button.setEnabled(True) for button in self.arrow_buttons]
        
        elif self.status["nanonis"] == "running":
            buttons["tip_status"].setEnabled(False)
            buttons["nanonis"].changeToolTip("Nanonis: active TCP connection")
            buttons["nanonis"].setStyleSheet(style_sheets["running"])
            
            [button.setEnabled(False) for button in self.action_buttons]
            [button.setEnabled(False) for button in self.arrow_buttons]
    
        else:
            buttons["tip_status"].setEnabled(False)
            buttons["tip_status"].changeToolTip("Tip status: unknown")
            buttons["tip_status"].setStyleSheet(style_sheets["disconnected"])

            buttons["nanonis"].changeToolTip("Nanonis: offline")
            buttons["nanonis"].setStyleSheet(style_sheets["disconnected"])
            
            [button.setEnabled(False) for button in self.action_buttons]
            [button.setEnabled(False) for button in self.arrow_buttons]
            
            # If Nanonis is offline, proceed with cleanup and make sure the nanonis and measurements attributes are deleted
            if hasattr(self, "nanonis"): delattr(self, "nanonis")
            if hasattr(self, "measurements"): delattr(self, "measurements")
            self.status["nanonis"] = "offline"
            self.logprint("  status[\"nanonis\"] = \"offline\"", color = "blue")



        if not self.status["tip"] == "online": #.get("withdrawn", False)
            buttons["retract"].setEnabled(True)
            buttons["advance"].setEnabled(True)
            buttons["approach"].setEnabled(True)

            buttons["tip_status"].changeToolTip("Tip status: withdrawn")
            buttons["tip_status"].setStyleSheet(style_sheets["idle"])
            buttons["withdraw"].changeToolTip("land")
            self.checkboxes["withdraw"].setEnabled(False)

        else:
            buttons["retract"].setEnabled(False)
            buttons["advance"].setEnabled(False)
            buttons["approach"].setEnabled(False)
        
            if self.status["tip"] == "feedback":
                buttons["tip_status"].changeToolTip("Tip status: in feedback")
                buttons["tip_status"].setStyleSheet(style_sheets["connected"])
                buttons["withdraw"].setText("Withdraw,")
                self.checkboxes["withdraw"].setEnabled(True)
            else:
                buttons["tip_status"].changeToolTip("Tip status: constant height")
                buttons["tip_status"].setStyleSheet(style_sheets["hold"])
                buttons["withdraw"].setText("Withdraw,")
                self.checkboxes["withdraw"].setEnabled(True)

        if not hasattr(self, "parameters"):
            self.logprint("Error. Parameters could not be retrieved.", color = "red")
            return False
        
        nanonis_bias = self.parameters.get("bias", None)
        mla_bias = self.parameters.get("mla_bias", None)
        I_fb = self.parameters.get("I_fb", None)

        self.line_edits["nanonis_bias"].setText(f"{nanonis_bias:.3f}" if nanonis_bias is not None else "")
        self.line_edits["mla_bias"].setText(f"{mla_bias:.3f}" if mla_bias is not None else "")
        self.line_edits["I_fb"].setText(f"{I_fb:.3f}" if I_fb is not None else "")
        #self.p_gain_box.setText(f"{np.round(self.parameters["p_gain"] * 1E12, 3)}") # In pm
        #self.t_const_box.setText(f"{np.round(self.parameters["t_const"] * 1E6, 3)}") # In us

        return

    # Button callbacks
    def on_next_chan(self):
        pass

    def on_previous_chan(self):
        pass

    def on_toggle_direction(self) -> None:
        buttons = self.gui.buttons

        if hasattr(self, "scan_direction") and self.scan_direction == "forward": self.scan_direction = "backward"
        else: self.scan_direction = "forward"

        buttons["direction"].blockSignals(True)
        buttons["direction"].setChecked(self.scan_direction == "backward")
        buttons["direction"].setText(f"direXion: {self.scan_direction}")
        buttons["direction"].blockSignals(False)

        return

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
                self.logprint("Attempting to launch scanalyzer by executing CLI command:", color = "white")
                self.logprint(f"  {sys.executable} {scanalyzer_path}", color = "blue")
                self.process.start(sys.executable, [self.paths["scanalyzer_path"]])
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
        QtWidgets.QApplication.instance().quit()

    def closeEvent(self, event):
        self.on_exit()



    # Hardware connections
    def connect_camera(self, argument) -> None:
        buttons = self.gui.buttons
        
        self.status["camera"] = "offline"
        buttons["camera"].setText("Camera: offline")
        buttons["camera"].setStyleSheet(style_sheets["disconnected"])

        try:
            cap = cv2.VideoCapture(argument)
            
            if not cap.isOpened(): # Check if the camera opened successfully
                raise
            else:
                cap.release()
                self.status["camera"] = "online"

                buttons["camera"].changeToolTip("Camera: online")
                buttons["camera"].setStyleSheet(style_sheets["connected"])

        except Exception as e:
            self.logprint("Could not connect the camera.")
        
        return    

    def connect_mla(self) -> None:
        pass

    def connect_nanonis(self) -> None:
        # Verify that Nanonis is online (responds to TCP-IP)
        # If it is, objects representing the classes Measurements and Nanonis will be instantiated
        
        if hasattr(self, "nanonis"): delattr(self, "nanonis")
        if hasattr(self, "measurements"): delattr(self, "measurements")
        self.status["nanonis"] = "offline"

        self.logprint("Attempting to connect to Nanonis", color = "white")
        try:
            # This is a low-level TCP-IP connection attempt
            self.logprint(f"  sock.connect({self.hardware["nanonis_ip"]}, {self.hardware["nanonis_port"]})", color = "blue")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.hardware["nanonis_ip"], self.hardware["nanonis_port"]))
            sock.close()
            sleep(.2) # Short delay is necessary to avoid having the hardware refuse the next connection request
            
            self.status["nanonis"] = "online"
            self.nanonis = Nanonis(hardware = self.hardware) # Make the Nanonis class available
            self.logprint("  status[\"nanonis\"] = \"online\"", color = "blue")
            self.logprint("Success! I also instantiated NanonisFunctions() as nanonis", color = "green")

            self.on_parameters_request()
    
        except socket.timeout:
            self.logprint("Failed to connect!", color = "red")
        except Exception:
            self.logprint("Failed to connect!", color = "red")
        
        self.update_buttons()

        return



    # Camera functions
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



    # Nanonis functions 
    # Simple data requests over TCP-IP
    def on_parameters_request(self):
        try:
            self.logprint("  status[\"tip\"] = nanonis.tip()", color = "blue")
            tip_status = self.nanonis.tip(error_callback = self.logprint)
            if not tip_status:
                self.logprint("Error retrieving the tip status.", color = "red")
                self.status["nanonis"] = "offline"
                self.logprint("  status[\"nanonis\"] = \"offline\"", color = "blue")
            else:
                self.status["tip"] = tip_status
            
            self.logprint("  parameters = nanonis.get_parameters()", color = "blue")
            parameters = self.nanonis.get_parameters()

            if not parameters:
                self.logprint("Error retrieving the scan parameters.", color = "red")
                self.status["nanonis"] = "offline"
                self.logprint("  status[\"nanonis\"] = \"offline\"", color = "blue")
            else:
                self.parameters = parameters
                self.paths["session_path"] = parameters.get("session_path")
                self.buttons["session_folder"].setToolTip(f"Open session folder {self.paths['session_path']} (1)")

                # experiment = self.experiment_box.currentText()
                self.paths["experiment_file"] = self.get_next_indexed_filename(self.paths["session_path"], "experiment", ".hdf5")
                #self.buttons["save"].setText(self.paths["experiment_file"])

                self.logprint("I was able to retrieve the tip status and scan parameters and saved them to dictionaries called 'tip_status' and 'parameters'", color = "green")
                self.logprint(f"  [dict] status[\"tip\"] = {tip_status}", color = "blue")
                self.logprint(f"  parameters.keys() = {parameters.keys()};", color = "blue")
                self.logprint(f"The session_path that I obtained from Nanonis ({self.paths['session_path']}) was added to the 'paths' dictionary", color = "white")

        except Exception as e:
            self.logprint(f"Error: {e}", color = "red")
            return False

    def on_frame_request(self):
        try:
            if hasattr(self, "nanonis"):
                self.logprint(f"  frame = nanonis.get_frame()", color = "blue")
                frame = self.nanonis.get_frame()

            if type(frame) == dict:
                self.frame = frame
                channels = frame["channel_names"]
                if type(channels) == list:
                    self.channel_select_box.clear()
                    self.channel_select_box.addItems(channels)
                
                self.logprint("I was able to read the scan frame data from Nanonis and save it in a dictionary called frame", color = "green")
                self.logprint(f"  frame = {self.frame}", color = "blue")
        except Exception as e:
            self.logprint({e}, color = "red")

    def on_nanonis_scan_request(self):
        direction = 0
        try:
            if hasattr(self, "frame"):
                channel_indices = self.frame["channel_indices"]
                channel_index = channel_indices[self.channel_select_box.currentIndex()]
                
                selected_scan = self.nanonis.get_scan(channel_index, direction)
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

    # Simple Nanonis functions; typically return either True if successful or an old parameter value when it is changed
    def toggle_withdraw(self) -> bool:
        try:
            if self.status["tip"] == "withdrawn":
                tip_status = self.nanonis.tip(feedback = True)
                if type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("  [dict] status[\"tip\"] = nanonis.tip(feedback = True)", color = "blue")
            else:
                tip_status = self.nanonis.tip(withdraw = True)
                if type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("  [dict] status[\"tip\"] = nanonis.tip(withdraw = True)", color = "blue")

        except Exception as e:
            pass

        self.update_buttons()

        return True

    def change_tip_status(self) -> bool:
        try:
            if self.status["tip"] == "withdrawn":
                tip_status = self.nanonis.tip(feedback = True)
                if type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("  [dict] status[\"tip\"] = nanonis.tip(feedback = True)", color = "blue")
            else: # Toggle the feedback
                tip_status = self.nanonis.tip(feedback = not self.tip_status["feedback"])
                if type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("  [dict] status[\"tip\"] = nanonis.tip(feedback = not tip_status[\"feedback\"])", color = "blue")

        except Exception as e:
            pass

        self.update_buttons()

        return True

    def on_bias_change(self, target: str = "Nanonis"):
        # Extract the target bias from the QLineEdit textbox
        V_new = float(self.line_edits["nanonis_bias"].text())

        self.logprint(f"  [float] V_old = nanonis.change_bias({V_new})", color = "blue")

        #V_old = self.nanonis.change_bias(V_new)
        # ^ This is the old-fashioned, non-threaded way
        self.task_worker = TaskWorker(self.nanonis.change_bias, V_new)
        self.thread_pool.start(self.task_worker)
        self.parameters["bias"] = V_new

        return True

    def on_setpoint_change(self):
        I_fb = float(self.I_fb_box.text())
        I_fb *= 1E-12

        self.logprint(f"  [float] I_old = nanonis.change_setpoint({I_fb})", color = "blue")
        I_old = self.nanonis.change_feedback(I_fb)

        self.parameters["I_fb"] = I_fb

        return True

    def on_coarse_move(self, direction: str = "n") -> bool:
        if direction not in ["n", "ne", "e", "se", "s", "sw", "w", "nw", "0"]:
            self.logprint("Error. Unknown tip direction requested.", color = "red")
            return False
        
        try:
            z_steps = float(self.line_edits["z_steps"].text())
            h_steps = float(self.line_edits["h_steps"].text())
            minus_z_steps = float(self.line_edits["minus_z_steps"].text())
            move_flags = {
                "withdraw": self.checkboxes["withdraw"].isChecked(),
                "retract": self.checkboxes["retract"].isChecked(),
                "move": self.checkboxes["move"].isChecked(),
                "advance": self.checkboxes["advance"].isChecked(),
                "approach": self.checkboxes["approach"].isChecked(),
                "direction": direction,
                "z_steps": z_steps,
                "h_steps": h_steps,
                "minus_z_steps": minus_z_steps
            }

            if not self.status["nanonis"] == "online":
                self.connect_nanonis()
            
            if not hasattr(self, "nanonis"):
                raise
            
            self.logprint(f"  move_flags.keys() = {move_flags.keys()}", color = "blue")
            self.logprint("  nanonis.move_over(move_flags)", color = "blue")

            return True
        
        except Exception as e:
            self.logprint("Error. Unable to execute tip move.", color = "red")

            return False



    # Experiments and thread management
    def on_experiment_change(self):
        self.experiment = "test" #self.experiment_box.currentText()
        self.paths["experiment_filename"] = self.get_next_indexed_filename(self.paths["session_path"], "experiment", ".hdf5")
        self.save_to_button.setText(self.paths["experiment_filename"])
        return

    def change_experiment_status(self, request: str = "stop"):
        self.logprint(f"Request = {request}", color = "white")
        match request:
            case "pause":
                if self.experiment_status == "running":
                    self.nanonis.scan_control(action = "pause")
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
                    self.nanonis.scan_control(action = "stop")
                    self.update_icons()
                return
            case "resume":
                if self.experiment_status == "paused":
                    self.nanonis.scan_control(action = "resume")
                    self.experiment_status = "running"
                    self.update_icons()
                return
            case _: # This is start
                if self.experiment_status == "running":
                    self.nanonis.scan_control(action = "stop")
                    self.experiment_status = "idle"
                    if hasattr(self, "timer"):
                        self.timer.stop()
                    self.update_icons()
                    return
                else: # Only when no experiment is running and a start is requested will the code below be evaluated
                    pass

        # First, check if the TCP connection is okay
        if not self.status["nanonis"] == "online":
            self.connect_nanonis()

            if not self.status["nanonis"] == "online":
                self.logprint("Error! Could not establish a connection to Nanonis. Aborting.", color = "red")
                self.update_buttons()
                return False

        # Read the experiment type and parameters
        #self.experiment = self.experiment_box.currentText()
        #self.direction = self.direction_box.currentText()
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
        self.frame = self.nanonis.get_frame()
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
                self.nanonis.connect_log()
                tip_position = self.nanonis.get_xy()
                self.nanonis.disconnect()
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
        
        self.nanonis.scan_control(action = "start", direction = dirxn)
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
        self.nanonis.scan_control(action = "stop")
        if hasattr(self, "experiment_thread"): self.experiment_thread.quit
        self.experiment_status = "idle"
        self.update_icons()
        self.paths["experiment_filename"] = self.get_next_indexed_filename(self.paths["session_path"], self.experiment, ".hdf5")
        self.save_to_button.setText(self.paths["experiment_filename"])
        self.nanonis.scan_control(action = "stop")

        return True



# Main program
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())