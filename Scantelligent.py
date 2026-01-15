import os, sys, re, html, yaml, cv2, pint, socket
import numpy as np
from PyQt6 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg
from lib.functions import Experiments, CameraWorker, TaskWorker
from lib import GUIItems, ScantelligentGUI, Nanonis, ImageFunctions
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
text_colors = {"message": colors["white"], "error": colors["red"], "code": colors["blue"], "success": colors["green"]}



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
        self.initialization = True
        self.parameters_init()
        self.gui_init()

        # Create a central widget and main horizontal layout, then a left_side_widget as a container for the ImageView and console
        self.setCentralWidget(self.gui.widgets["central"])

        self.gui.layouts["left_side"].setContentsMargins(0, 0, 0, 0)
        self.gui.layouts["left_side"].addWidget(self.gui.image_view, stretch = 4) 
        
        # Left Section: Graphic and Console (grouped vertically)
        self.gui.widgets["left_side"].setLayout(self.gui.layouts["left_side"])
        self.gui.layouts["main"].addWidget(self.gui.widgets["left_side"], stretch = 4)
        self.gui.layouts["main"].addLayout(self.gui.layouts["toolbar"], 1)
        self.gui.widgets["central"].setLayout(self.gui.layouts["main"])

        # Initialize the console, then activate keys and buttons
        self.console_init()
        self.config_init()
        self.connect_keys()

        # Ensure the central widget can receive keyboard focus
        self.gui.widgets["central"].setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.gui.widgets["central"].setFocus()
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.activateWindow()

        # Check / set up hardware connections
        self.connect_camera()
        self.connect_mla()
        self.connect_nanonis()
        if hasattr(self, "nanonis"): self.nanonis.disconnect()
        self.initialization = False

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
        self.experiment_status = "idle"
        self.process = QtCore.QProcess(self)

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
            "tip": {"withdrawn": True, "feedback": False},
            "experiment": "idle",
            "view": "none"
        }

        return

    def gui_init(self) -> None:
        self.gui = ScantelligentGUI(self.paths["icon_folder"])
        buttons = self.gui.buttons
        shortcuts = self.gui.shortcuts
        
        # Connect the buttons to their respective functions
        connections = [["scanalyzer", self.launch_scanalyzer], ["nanonis", self.connect_nanonis], ["mla", self.update_icons], ["camera", self.update_icons], ["exit", self.on_exit],
                       ["oscillator", self.toggle_withdraw], ["view", self.update_icons], ["session_folder", self.update_icons],
                       
                       ["withdraw", self.toggle_withdraw], ["retract", self.update_icons], ["advance", self.update_icons], ["approach", self.update_icons],
                       
                       ["tip", self.change_tip_status], ["swap_bias", self.update_icons], ["set", self.on_parameters_set], ["get", self.on_parameters_request],
                       ["retract", self.update_icons], ["advance", self.update_icons], ["approach", self.update_icons]
                       ]
        [connections.append([direction, lambda: self.on_coarse_move(direction)]) for direction in ["n", "ne", "e", "se", "s", "sw", "w", "nw"]]
        
        for connection in connections:
            name = connection[0]
            connected_function = connection[1]
            buttons[name].clicked.connect(connected_function)
            
            if name in shortcuts.keys():
                shortcut = QtGui.QShortcut(shortcuts[name], self)
                shortcut.activated.connect(connected_function)
        
        # Add buttons to QButtonGroups for exclusive selection and check the defaults
        QGroup = QtWidgets.QButtonGroup
        self.gui.background_button_group = QGroup(self)
        [self.gui.background_button_group.addButton(button) for button in self.gui.background_buttons]
        
        [self.gui.min_button_group, self.gui.max_button_group] = [QGroup(self), QGroup(self)]
        [self.gui.min_button_group.addButton(button) for button in self.gui.min_radio_buttons]
        [self.gui.max_button_group.addButton(button) for button in self.gui.max_radio_buttons]
        
        checked_buttons = [self.gui.radio_buttons[name] for name in ["min_full", "max_full", "bg_none"]]
        [button.setChecked(True) for button in checked_buttons]



        # Draw experiments group: to be absorbed in gui_scantelligent.py
        experiments_layout = self.gui.layouts["experiments"]

        start_stop_layout = self.gui.layouts["start_stop"]
        self.progress_bar = QtWidgets.QProgressBar()
        self.progress_bar.setMinimum(0)
        self.progress_bar.setMaximum(100)
        self.progress_bar.setValue(0)

        self.start_stop_button = QtWidgets.QToolButton()
        self.start_stop_button.setIconSize(QtCore.QSize(20, 20))
        pause_icon = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPause)
        start_stop_layout.addWidget(self.progress_bar)
        start_stop_layout.addWidget(self.start_stop_button)
        self.update_icons()

        experiments_layout.addWidget(self.gui.comboboxes["experiments"], 0, 0)
        experiments_layout.addWidget(self.gui.comboboxes["direction"], 0, 1)
        experiments_layout.addWidget(self.gui.buttons["save"], 2, 1)
        self.gui.groupboxes["experiments"].setLayout(experiments_layout)
        
        [self.gui.layouts["toolbar"].addWidget(self.gui.groupboxes[name]) for name in ["connections", "coarse_control", "parameters", "experiments", "image_processing"]]

        return

    def console_init(self) -> None:
        # Initialize the console
        self.console_output = QtWidgets.QTextEdit()
        self.console_output.setReadOnly(True)
        self.gui.layouts["left_side"].addWidget(self.console_output, stretch = 1)

        # Redirect output to the console
        self.stdout_redirector = StreamRedirector()
        self.stdout_redirector.output_written.connect(lambda text: self.console_output.append(text))
        sys.stdout = self.stdout_redirector
        now = datetime.now()
        self.logprint(now.strftime("Opening Scantelligent on %Y-%m-%d %H:%M:%S"), message_type = "message")

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
                        self.logprint("Scanalyzer found and linked", message_type = "success")
                    else:
                        self.logprint("Warning: config file has a scanalyzer_path entry, but it doesn't point to an existing file.", "red")
                except Exception as e:
                    self.logprint("Warning: scanalyzer path could not be read. {e}", message_type = "error")
                
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
                    self.logprint("I found the config.yml file and was able to set up a dictionary called 'hardware'", message_type = "success")
                    self.logprint(f"[dict] hardware = {self.hardware}", message_type = "code")
                    
                except Exception as e:
                    self.logprint("Error: could not retrieve the Nanonis TCP settings.", message_type = "error")
        except Exception as e:
            self.logprint(f"Error: problem loading config.yml: {e}", message_type = "error")
        
        return



    # Miscellaneous
    def logprint(self, message: str = "", timestamp: bool = True, message_type: str = "message") -> None:
        """Print a (timestamped) message to the redirected stdout.

        Parameters:
        - message: text to print
        - timestamp: whether to prepend HH:MM:SS timestamp
        - type: type of message. The style of the message will be selected according to its type
        """
        current_time = datetime.now().strftime("%H:%M:%S")
        match message_type:
            case "error":
                color = text_colors["error"]
            case "code":
                timestamp = False
                color = text_colors["code"]
            case "success":
                color = text_colors["success"]
            case _:
                color = text_colors["message"]
        
        if timestamp: timestamped_message = current_time + f">>  {message}"
        else: timestamped_message = f"{message}"

        # Escape HTML to avoid accidental tag injection, then optionally wrap in a colored span so QTextEdit renders it in color.
        escaped = html.escape(timestamped_message)        
        if message_type == "code": final = f"<pre><span style=\"color:{color}\">          {escaped}</span></pre>"
        else: final = f"<span style=\"color:{color}\">{escaped}</span>"

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

    def connect_keys(self) -> None:
        QKey = QtCore.Qt.Key

        projection_toggle_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QKey.Key_H), self)
        projection_toggle_shortcut.activated.connect(self.update_icons)

        open_session_folder_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QKey.Key_1), self)
        open_session_folder_shortcut.activated.connect(self.open_session_folder)

        # Direction
        direction_toggle_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QKey.Key_X), self)
        direction_toggle_shortcut.activated.connect(self.on_toggle_direction)
        
        # I/O group
        exit_shortcuts = [QtGui.QShortcut(QtGui.QKeySequence(keystroke), self) for keystroke in [QKey.Key_Q, QKey.Key_E]]
        [exit_shortcut.activated.connect(self.on_exit) for exit_shortcut in exit_shortcuts]
        session_folder_shortcut = QtGui.QShortcut(QtGui.QKeySequence(QKey.Key_T), self)
        session_folder_shortcut.activated.connect(self.open_session_folder)

    # Update GUI according to hardware status
    def update_buttons(self) -> None:
        buttons = self.gui.buttons
        # Activate/deactivate and color buttons according to hardware status

        if self.status["nanonis"] == "online":
            buttons["tip"].setEnabled(True)
            buttons["nanonis"].changeToolTip("Nanonis: online")
            buttons["nanonis"].setStyleSheet(style_sheets["connected"])
            
            [button.setEnabled(True) for button in self.gui.action_buttons]
            [button.setEnabled(True) for button in self.gui.arrow_buttons]
        
        elif self.status["nanonis"] == "running":
            #buttons["tip"].setEnabled(False)
            buttons["nanonis"].changeToolTip("Nanonis: active TCP connection")
            buttons["nanonis"].setStyleSheet(style_sheets["running"])
            
            [button.setEnabled(False) for button in self.gui.action_buttons]
            [button.setEnabled(False) for button in self.gui.arrow_buttons]
    
        else:
            #buttons["tip"].setEnabled(False)
            buttons["tip"].changeToolTip("Tip status: unknown")
            buttons["tip"].setStyleSheet(style_sheets["disconnected"])

            buttons["nanonis"].changeToolTip("Nanonis: offline")
            buttons["nanonis"].setStyleSheet(style_sheets["disconnected"])
            
            [button.setEnabled(False) for button in self.gui.action_buttons]
            [button.setEnabled(False) for button in self.gui.arrow_buttons]
            
            # If Nanonis is offline, proceed with cleanup and make sure the nanonis and measurements attributes are deleted
            if hasattr(self, "nanonis"): delattr(self, "nanonis")
            if hasattr(self, "measurements"): delattr(self, "measurements")
            self.status["nanonis"] = "offline"
            self.logprint("[str] status[\"nanonis\"] = \"offline\"", message_type = "code")
            
            buttons["tip"].blockSignals(False)
            buttons["nanonis"].blockSignals(False)
            
            return
        
        # Tip status
        if self.status["tip"].get("withdrawn"):
            buttons["tip"].changeToolTip("Tip withdrawn; click to land")
            buttons["tip"].setIcon(self.icons.get("withdrawn"))
            buttons["tip"].setStyleSheet(style_sheets["idle"])
            buttons["withdraw"].setIcon(self.icons.get("approach"))
            buttons["withdraw"].changeToolTip("Land")
            self.gui.checkboxes["withdraw"].setEnabled(False)

        else:
            [button.setEnabled(False) for button in self.gui.action_buttons[1:]]
            buttons["tip"].setIcon(self.icons.get("contact"))
            buttons["withdraw"].setEnabled(True)
            buttons["withdraw"].setIcon(self.icons.get("withdraw"))
            buttons["withdraw"].changeToolTip("Withdraw")
            self.gui.checkboxes["withdraw"].setEnabled(True)
        
            if self.status["tip"].get("feedback"):
                buttons["tip"].changeToolTip("Tip in feedback; click to toggle feedback off")
                buttons["tip"].setStyleSheet(style_sheets["connected"])                
            else:
                buttons["tip"].changeToolTip("Tip in constant height: click to toggle feedback on")
                buttons["tip"].setStyleSheet(style_sheets["hold"])
        
        if not hasattr(self, "parameters"): return
        
        nanonis_bias = self.parameters.get("bias", None)
        mla_bias = self.parameters.get("mla_bias", None)
        I_fb = self.parameters.get("I_fb", None)
        p_gain = self.parameters.get("p_gain", None)
        t_const = self.parameters.get("t_const", None)
        
        I_fb_pA = I_fb * 1E12 if I_fb is not None else None
        p_gain_pm = p_gain * 1E12 if p_gain is not None else None
        t_const_us = t_const * 1E6 if t_const is not None else None

        self.gui.line_edits["nanonis_bias"].setText(f"{nanonis_bias:.2f} V" if nanonis_bias is not None else "")
        self.gui.line_edits["mla_bias"].setText(f"{mla_bias:.2f} V" if mla_bias is not None else "")
        self.gui.line_edits["I_fb"].setText(f"{I_fb_pA:.0f} pA" if I_fb_pA is not None else "")
        self.gui.line_edits["p_gain"].setText(f"{p_gain_pm:.0f} pm" if p_gain_pm is not None else "") # In pm
        self.gui.line_edits["t_const"].setText(f"{t_const_us:.0f} us" if t_const_us is not None else "") # In us

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
        self.logprint("Not implemented yet", message_type = "messsage")
        try:
            match self.experiment_status:
                case "running":
                    start_stop_icon = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaStop)
                    #self.pause_button.setEnabled(True)
                    #[box.setEnabled(False) for box in [self.comboboxes["experiments"], self.comboboxes["direction"]]]
                case "idle":
                    start_stop_icon = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay)
                    #self.pause_button.setEnabled(False)
                    #[box.setEnabled(True) for box in [self.comboboxes["experiments"], self.comboboxes["direction"]]]
                case "paused":
                    start_stop_icon = QtWidgets.QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaStop)
                    #self.pause_button.setEnabled(True)
                    #self.pause_button.setChecked(True)
                    #[box.setEnabled(False) for box in [self.comboboxes["experiments"], self.comboboxes["direction"]]]
                case _:
                    pass
            self.start_stop_button.setIcon(start_stop_icon)
        except Exception as e:
            self.logprint(e, message_type = "error")
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
                self.logprint("Attempting to launch scanalyzer by executing CLI command:", message_type = "message")
                self.logprint(f"{sys.executable} {scanalyzer_path}", message_type = "code")
                self.process.start(sys.executable, [self.paths["scanalyzer_path"]])
            except Exception as e:
                self.logprint(f"Failed to launch Scanalyzer: {e}", message_type = "error")
        else:
            self.logprint("Error. Scanalyzer path unknown.", message_type = "error")

    def open_session_folder(self):
        if hasattr(self, "paths") and "session_path" in list(self.paths.keys()):
            try:
                session_path = self.paths["session_path"]
                self.logprint("Opening the session folder", message_type = "message")
                os.startfile(session_path)
            except Exception as e:
                self.logprint(f"Failed to open session folder: {e}", message_type = "error")
        else:
            self.logprint("Error. Session folder unknown.", message_type = "error")
        return

    def on_exit(self):
        try: self.nanonis.disconnect()
        except: pass
        if hasattr(self, "nanonis"): delattr(self, "nanonis")
        if hasattr(self, "measurements"): delattr(self, "measurements")
            
        self.logprint("Thank you for using Scantelligent!", message_type = "success")
        QtWidgets.QApplication.instance().quit()

    def closeEvent(self, event):
        self.on_exit()



    # Hardware connections
    def connect_camera(self) -> None:
        self.status["camera"] = "offline"
        
        self.gui.buttons["camera"].changeToolTip("Camera: offline")
        self.gui.buttons["camera"].setStyleSheet(style_sheets["disconnected"])
        
        argument = self.hardware.get("argument")
        
        if 2 == 2:
            return
        else:
    
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
        self.status["mla"] = "offline"
        
        self.gui.buttons["mla"].changeToolTip("Multifrequency Lockin Amplifier: offline")
        self.gui.buttons["mla"].setStyleSheet(style_sheets["disconnected"])
        
        return

    def connect_nanonis(self) -> None:
        # Verify that Nanonis is online (responds to TCP-IP)
        # If it is, objects representing the classes Measurements and Nanonis will be instantiated
        # If Nanonis was already online or running, the connection will be reset
        
        # Start with deleting spurious objects
        try: self.nanonis.disconnect()
        except: pass
        if hasattr(self, "nanonis"): delattr(self, "nanonis")
        if hasattr(self, "measurements"): delattr(self, "measurements")

        self.logprint("Attempting to connect to Nanonis", message_type = "message")
        try:
            # This is a low-level TCP-IP connection attempt
            self.logprint(f"sock.connect({self.hardware["nanonis_ip"]}, {self.hardware["nanonis_port"]})", message_type = "code")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((self.hardware["nanonis_ip"], self.hardware["nanonis_port"]))
            sock.close()
            sleep(.2) # Short delay is necessary to avoid having the hardware refuse the next connection request
            
            self.status["nanonis"] = "online"
            self.nanonis = Nanonis(hardware = self.hardware) # Make the Nanonis class available
            self.logprint("[str] status[\"nanonis\"] = \"online\"", message_type = "code")
            self.logprint("Success! I also instantiated Nanonis() as nanonis", message_type = "success")

            # If Nanonis is online, proceed to request all parameters
            self.on_parameters_request()
    
        except socket.timeout:
            self.logprint("Failed to connect!", message_type = "error")
        except Exception:
            self.logprint("Failed to connect!", message_type = "error")
        
        self.update_buttons()

        return



    # Camera functions
    def update_image_display(self, frame):
        """Slot to receive the RGB frame and update the ImageView."""
        # pyqtgraph efficiently handles the NumPy array.
        # We set autoRange and autoLevels to False to prevent flicker.
        self.gui.image_view.setImage(frame, autoRange = False, autoLevels = False)

    def start_camera(self):
        """Initializes and starts a NEW worker thread."""
        if self.is_camera_running:
            return
        
        self.gui.image_view.setLevels(0, 255)
        self.gui.image_view.ui.histogram.hide()
        self.gui.image_view.ui.roiBtn.hide()
        self.gui.image_view.ui.roiPlot.hide()

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
        self.status["nanonis"] = "running"
        self.gui.buttons["nanonis"].setStyleSheet(style_sheets["running"])
        
        try:
            if self.initialization: self.logprint("status[\"tip\"] = nanonis.tip()", message_type = "code")
            tip_status = self.nanonis.tip()
            if not tip_status:
                self.logprint("Error retrieving the tip status.", message_type = "error")
                self.status["nanonis"] = "offline"
                self.logprint("[str] status[\"nanonis\"] = \"offline\"", message_type = "code")
            else:
                self.status["tip"] = tip_status
            
            if self.initialization: self.logprint("parameters = nanonis.get_parameters()", message_type = "code")
            parameters = self.nanonis.get_parameters()

            if not parameters:
                self.logprint("Error retrieving the scan parameters.", message_type = "error")
                self.status["nanonis"] = "offline"
                self.logprint("[str] status[\"nanonis\"] = \"offline\"", message_type = "code")
            else:
                self.parameters = parameters
                self.paths["session_path"] = parameters.get("session_path")
                self.gui.buttons["session_folder"].setToolTip(f"Open session folder {self.paths['session_path']} (1)")

                # experiment = self.experiment_box.currentText()
                self.paths["experiment_file"] = self.get_next_indexed_filename(self.paths["session_path"], "experiment", ".hdf5")
                #self.buttons["save"].setText(self.paths["experiment_file"])

                if self.initialization:
                    self.logprint("I was able to retrieve the tip status and scan parameters and saved them to dictionaries called 'status' and 'parameters'", message_type = "success")
                    self.logprint(f"[dict] status[\"tip\"] = {tip_status}", message_type = "code")
                    self.logprint(f"parameters.keys() = {parameters.keys()};", message_type = "code")
                    self.logprint(f"The session_path that I obtained from Nanonis ({self.paths['session_path']}) was added to the 'paths' dictionary", message_type = "success")
                
                self.grid = self.nanonis.get_grid()
                if self.initialization: 
                    self.logprint(f"I obtained frame/grid and scan metadata from nanonis, which is available in the 'grid' dictionary", message_type = "message")
                    self.logprint(f"grid.keys() = {self.grid.keys()}", message_type = "code")

        except Exception as e:
            self.logprint(f"Error: {e}", message_type = "error")
        
        finally:
            self.nanonis.disconnect()
            sleep(.1)
            self.status["nanonis"] = "online"
            self.gui.buttons["nanonis"].setStyleSheet(style_sheets["connected"])
            self.update_buttons()

        return

    def on_frame_request(self):
        try:
            if hasattr(self, "nanonis"):
                self.logprint(f"Attempting to get the scan frame data", message_type = "message")
                self.logprint(f"frame = nanonis.get_frame()", message_type = "code")
                frame = self.nanonis.get_frame()

            if type(frame) == dict:
                self.frame = frame
                channels = frame["channel_names"]
                if type(channels) == list:
                    self.channel_select_box.clear()
                    self.channel_select_box.addItems(channels)
                
                self.logprint("I was able to read the scan frame data from Nanonis", message_type = "success")
                self.logprint(f"[dict] frame = {self.frame}", message_type = "code")
        except Exception as e:
            self.logprint({e}, message_type = "error")

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
                            self.logprint("Experiment completed!", message_type = "success")
                            self.change_experiment_status(request = "stop")
                        self.progress_bar.setValue(int(100 * num_values / (num_nans + num_values)))
                    

                    self.gui.image_view.setImage(self.selected_scan)
                    self.gui.image_view.autoRange()
            else:
                self.logprint("No dictionary 'frame' found", message_type = "error")
        except Exception as e:
            self.logprint(f"{e}", message_type = "error")

    # Simple Nanonis functions; typically return either True if successful or an old parameter value when it is changed
    def on_parameters_set(self) -> bool:
        try:
            # Extract the numbers
            number_matches = re.findall(r"-?\d+\.?\d*", self.gui.line_edits["nanonis_bias"].text())
            self.logprint(f"{number_matches}", message_type = "error")
            numbers = [float(x) for x in number_matches]
            self.logprint(f"{numbers}", message_type = "error")
            new_V = numbers[0]
            self.logprint(f"I will try to set the bias to {new_V}")
            self.nanonis.change_bias(new_V)
        except:
            pass
        finally:
            self.on_parameters_request()     
        
        return

    def toggle_withdraw(self) -> bool:
        if not hasattr(self, "nanonis"): return False
        
        self.status["nanonis"] = "running"
        self.update_buttons()
        
        try:
            if self.status["tip"].get("withdrawn"):
                tip_status = self.nanonis.tip(feedback = True)
                if type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("[dict] status[\"tip\"] = nanonis.tip(feedback = True)", message_type = "code")
            else:
                tip_status = self.nanonis.tip(withdraw = True)
                if type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("[dict] status[\"tip\"] = nanonis.tip(withdraw = True)", message_type = "code")

        except Exception as e:
            self.logprint(f"Error toggling the tip status: {e}", message_type = "error")
            return False
        
        self.status["nanonis"] = "online"
        self.update_buttons()

        return True

    def change_tip_status(self) -> bool:
        try:
            if self.status["tip"].get("withdrawn"):
                tip_status = self.nanonis.tip(feedback = True)
                if type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("[dict] status[\"tip\"] = nanonis.tip(feedback = True)", message_type = "code")
            else: # Toggle the feedback
                tip_status = self.nanonis.tip(feedback = not self.status["tip"].get("feedback"))
                if type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("[dict] status[\"tip\"] = nanonis.tip(feedback = not status[\"tip\"].get(\"feedback\"])", message_type = "code")

        except Exception as e:
            self.logprint(f"Error toggling the tip status: {e}", message_type = "error")
            return False

        self.update_buttons()

        return True

    def on_bias_change(self, target: str = "Nanonis"):
        # Extract the target bias from the QLineEdit textbox
        V_new = float(self.line_edits["nanonis_bias"].text())

        self.logprint(f"[float] V_old = nanonis.change_bias({V_new})", message_type = "code")

        #V_old = self.nanonis.change_bias(V_new)
        # ^ This is the old-fashioned, non-threaded way
        self.task_worker = TaskWorker(self.nanonis.change_bias, V_new)
        self.thread_pool.start(self.task_worker)
        self.parameters["bias"] = V_new

        return True

    def on_setpoint_change(self):
        I_fb = float(self.I_fb_box.text())
        I_fb *= 1E-12

        self.logprint(f"[float] I_old = nanonis.change_setpoint({I_fb})", message_type = "code")
        I_old = self.nanonis.change_feedback(I_fb)

        self.parameters["I_fb"] = I_fb

        return True

    def on_coarse_move(self, direction: str = "n") -> bool:
        if direction not in ["n", "ne", "e", "se", "s", "sw", "w", "nw", "0"]:
            self.logprint("Error. Unknown tip direction requested.", message_type = "error")
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
            
            self.logprint("Executing a tip move by passing the dictionary 'move_flags' to nanonis.move_over")
            self.logprint(f"[dict] move_flags = {move_flags}", message_type = "code")
            self.logprint("nanonis.move_over(move_flags)", message_type = "code")

            return True
        
        except Exception as e:
            self.logprint("Error. Unable to execute tip move.", message_type = "error")

            return False



    # Experiments and thread management
    def on_experiment_change(self):
        self.experiment = "test" #self.experiment_box.currentText()
        self.paths["experiment_filename"] = self.get_next_indexed_filename(self.paths["session_path"], "experiment", ".hdf5")
        self.save_to_button.setText(self.paths["experiment_filename"])
        return

    def change_experiment_status(self, request: str = "stop"):
        self.logprint(f"Request = {request}", message_type = "message")
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
                self.logprint(f"{self.timer}", message_type = "message")
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
                self.logprint("Error! Could not establish a connection to Nanonis. Aborting.", message_type = "error")
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
                self.logprint("Sorry, I don't know this experiment yet.", message_type = "error")
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
        self.logprint(f"Starting experiment {self.experiment}", message_type = "message")
        self.logprint(f"The experiment will be saved to {self.paths["experiment_file"]}", message_type = "message")

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

        self.gui.image_view.setImage(processed_z_grid, autoRange = True)

    def receive_message(self, message_text, color_string):
        if color_string in colors.keys():
            self.logprint(message_text, color = color_string)
        else:
            self.logprint(message_text, message_type = "message")

    def receive_progress(self, progress):
        self.progress_bar.setValue(progress)

    def experiment_finished(self):
        self.logprint("Experiment finished", message_type = "success")
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