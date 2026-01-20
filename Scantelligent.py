import os, sys, re, html, yaml, cv2, pint, socket, atexit
import numpy as np
from PyQt6 import QtWidgets, QtGui, QtCore
from lib import ScantelligentGUI, StreamRedirector, Nanonis
from time import sleep, time
from scipy.interpolate import griddata
from datetime import datetime



colors = {"red": "#ff5050", "dark_red": "#800000", "green": "#00ff00", "dark_green": "#005000", "lightblue": "#30d0ff",
          "white": "#ffffff", "blue": "#2090ff", "orange": "#FFA000","dark_orange": "#A05000", "black": "#000000", "purple": "#700080"}
style_sheets = {
    "neutral": f"background-color: {colors["black"]};",
    "connected": f"background-color: {colors["dark_green"]};",
    "disconnected": f"background-color: {colors["dark_red"]};",
    "running": f"background-color: {colors["blue"]};",
    "hold": f"background-color: {colors["dark_orange"]};",
    "idle": f"background-color: {colors["purple"]};"
    }
text_colors = {"message": colors["white"], "error": colors["red"], "code": colors["blue"], "result": colors["lightblue"], "success": colors["green"], "warning": colors["orange"]}



class App:
    #request_start = QtCore.pyqtSignal(str, int, int)
    #start_tracking = QtCore.pyqtSignal(float, int, int) # sampling time, chunk_size, timeout
    #request_stop = QtCore.pyqtSignal()

    def __init__(self):
        self.parameters_init()
        self.gui = ScantelligentGUI(self.paths["icon_folder"])
        
        self.setup_connections()
        self.config_init()
        self.connect_hardware()
        self.gui.show()

        # Set up the Experiments class and thread and connect signals and slots
        #self.thread_pool = QtCore.QThreadPool()
        #self.experiment_thread = QtCore.QThread()
        #self.timer = QtCore.QTimer()



    def parameters_init(self) -> None:
        atexit.register(self.cleanup)
        
        self.paths = {
            "script": os.path.abspath(__file__), # The full path of Scanalyzer.py
            "parent_folder": os.path.dirname(os.path.abspath(__file__)),            
        }
        self.paths["lib"] = os.path.join(self.paths["parent_folder"], "lib")
        self.paths["sys"] = os.path.join(self.paths["parent_folder"], "sys")
        self.paths["config_file"] = os.path.join(self.paths["sys"], "config.yml")
        self.paths["parameters_file"] = os.path.join(self.paths["sys"], "parameters.yml")
        self.paths["icon_folder"] = os.path.join(self.paths["parent_folder"], "icons")

        icon_files = os.listdir(self.paths["icon_folder"])
        self.icons = {}
        for icon_file in icon_files:
            [icon_name, extension] = os.path.splitext(os.path.basename(icon_file))
            try:
                if extension == ".png": self.icons.update({icon_name: QtGui.QIcon(os.path.join(self.paths["icon_folder"], icon_file))})
            except:
                pass

        # Some attributes
        self.channels = []
        self.channel = ""
        self.channel_index = 0
        self.max_channel_index = 0
        self.scale_toggle_index = 0
        self.ureg = pint.UnitRegistry()

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
            "initialization": True,
            "nanonis": "offline",
            "mla": "offline",
            "camera": "offline",
            "tip": {"withdrawn": True, "feedback": False},
            "experiment": "idle",
            "view": "none"
        }
        
        return

    def setup_connections(self) -> None:
        
        def connect_console() -> None:
            # Redirect output to the console
            self.stdout_redirector = StreamRedirector()
            self.stdout_redirector.output_written.connect(lambda text: self.gui.consoles["output"].append(text))
            sys.stdout = self.stdout_redirector
            #sys.stderr = self.stdout_redirector
            now = datetime.now()
            self.logprint(now.strftime("Opening Scantelligent on %Y-%m-%d %H:%M:%S"), message_type = "message")

            return
        
        def connect_buttons() -> None:
            buttons = self.gui.buttons
            shortcuts = self.gui.shortcuts        
            
            # Connect the buttons to their respective functions
            connections = [["scanalyzer", self.launch_scanalyzer], ["nanonis", self.connect_hardware], ["mla", self.connect_hardware], ["camera", self.connect_hardware], ["exit", self.exit],
                        ["oscillator", self.update_icons], ["view", self.update_icons], ["session_folder", self.open_session_folder],
                        
                        ["withdraw", self.toggle_withdraw], ["retract", self.update_icons], ["advance", self.update_icons], ["approach", self.update_icons],
                        
                        ["tip", self.change_tip_status], ["V_swap", self.on_scan_data_request], ["set", self.on_parameters_set], ["get", self.on_parameters_request],

                        ["start_pause", lambda action: self.on_experiment_control(action = "start_pause")], ["stop", lambda action: self.on_experiment_control(action = "stop")],
                        ]
            [connections.append([direction, lambda: self.on_coarse_move(direction)]) for direction in ["n", "ne", "e", "se", "s", "sw", "w", "nw"]]
            connections.append([f"scan_parameters_0", lambda: self.load_parameters(0)])
            connections.append([f"scan_parameters_0", lambda: self.load_parameters(1)])
            connections.append([f"scan_parameters_0", lambda: self.load_parameters(2)])
            connections.append([f"scan_parameters_0", lambda: self.load_parameters(3)])
            
            for connection in connections:
                name = connection[0]
                connected_function = connection[1]
                buttons[name].clicked.connect(connected_function)
                
                if name in shortcuts.keys():
                    shortcut = QtGui.QShortcut(shortcuts[name], self.gui)
                    shortcut.activated.connect(connected_function)
            
            # Line edits
            self.gui.line_edits["input"].editingFinished.connect(self.execute_command)
            
            # Comboboxes
            self.gui.comboboxes["channels"].currentIndexChanged.connect(self.on_scan_data_request)
            self.gui.comboboxes["experiment"].currentIndexChanged.connect(self.on_experiment_change)
            
            # Populate the command input completer with all attributes and methods of self and self.gui
            self.all_attributes = dir(self)
            gui_attributes = ["gui." + attr for attr in self.gui.__dict__ if not attr.startswith('__')]
            self.all_attributes.extend(gui_attributes)
            completer = QtWidgets.QCompleter(self.all_attributes, self.gui)
            completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
            completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
            self.gui.line_edits["input"].setCompleter(completer)
            
            self.process = QtCore.QProcess(self.gui)
            
            return
        
        def connect_keys() -> None:
            """
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
            """

            return
        
        connect_console()
        connect_buttons()
        connect_keys()
        self.update_buttons()
        
        return
  
    def config_init(self) -> None:
        
        # Read the config file to get the hardware configuration parameters
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
                        self.logprint("Warning: config file has a scanalyzer_path entry, but it doesn't point to an existing file.", message_type = "error")
                except Exception as e:
                    self.logprint("Warning: scanalyzer path could not be read. {e}", message_type = "error")
                
                try:
                    nanonis_settings = config.get("nanonis")
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
                    self.logprint(f"[dict] hardware = {self.hardware}", message_type = "result")
                    
                except Exception as e:
                    self.logprint("Error: could not retrieve the Nanonis TCP settings.", message_type = "error")
        except Exception as e:
            self.logprint(f"Error: problem loading config.yml: {e}", message_type = "error")
        
        # Read the scan parameters from the parameters file
        try:
            with open(self.paths.get("parameters_file"), "r") as file:
                parameters = yaml.safe_load(file)
        except Exception as e:
            self.logprint(f"Error reading the parameters from the parameters.yml file. {e}")
            
        scan_parameters = parameters.get("scan_parameters")
        coarse_parameters = parameters.get("coarse_parameters")
        
        self.scan_parameters = [scan_parameters.get(i) for i in range(4)]
        [self.gui.buttons[f"scan_parameters_{i}"].changeToolTip(f"Load scan parameter set {i} ({self.scan_parameters[i].get("name")})") for i in range(4)]
        
        # Initialize the scan parameters in the gui as parameter set 0, until a connection to Nanonis is made
        self.load_parameters(0)
        
        return

    def connect_hardware(self) -> None:

        def connect_camera() -> None:
            self.status["camera"] = "offline"
            
            self.gui.buttons["camera"].changeToolTip("Camera: offline")
            self.gui.buttons["camera"].setStyleSheet(style_sheets["disconnected"])
            
            argument = self.hardware.get("argument")
            
            self.logprint("Warning. No camera found.", message_type = "warning")
            
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

        def connect_mla() -> None:
            self.status["mla"] = "offline"
            
            self.gui.buttons["mla"].changeToolTip("Multifrequency Lockin Amplifier: offline")
            self.gui.buttons["mla"].setStyleSheet(style_sheets["disconnected"])
            
            self.logprint("Warning. MLA not found.", message_type = "warning")
            
            return

        def connect_nanonis() -> None:
            self.nanonis = Nanonis(hardware = self.hardware)
            self.nanonis.connection_flag.connect(self.receive_nanonis_status)

            try:
                # This is a low-level TCP-IP connection attempt
                self.logprint(f"sock.connect({self.hardware["nanonis_ip"]}, {self.hardware["nanonis_port"]})", message_type = "code")
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((self.hardware["nanonis_ip"], self.hardware["nanonis_port"]))
                sock.close()
                sleep(.2) # Short delay is necessary to avoid having the hardware refuse the next connection request
                
                self.status["nanonis"] = "online"
        
            except socket.timeout:
                self.logprint("Warning. Failed to connect to Nanonis.", message_type = "warning")
                raise
            except Exception:
                self.logprint("Warning. Failed to connect to Nanonis.", message_type = "warning")
                raise

            # If Nanonis is online, proceed with getting parameters and scan data
            if self.status["nanonis"] == "online": self.on_parameters_request()
            
            # Add nanonis attributes and methods to the command input completer
            nanonis_attributes = ["nanonis." + attr for attr in self.nanonis.__dict__ if not attr.startswith('__')]
            self.all_attributes.extend(nanonis_attributes)
            completer = QtWidgets.QCompleter(self.all_attributes, self.gui)
            completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
            completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
            self.gui.line_edits["input"].setCompleter(completer)

            return

        self.logprint("Attempting to connect to hardware", message_type = "message")
        connect_camera()
        connect_mla()
        connect_nanonis()
        
        return

    def cleanup(self) -> None:
        try: self.nanonis.disconnect()
        except: pass
        if hasattr(self, "nanonis"): delattr(self, "nanonis")
        if hasattr(self, "measurements"): delattr(self, "measurements")



    # Miscellaneous
    def logprint(self, message: str = "", message_type: str = "error", timestamp: bool = True) -> None:
        """Print a (timestamped) message to the redirected stdout.

        Parameters:
        - message: text to print
        - timestamp: whether to prepend HH:MM:SS timestamp
        - type: type of message. The style of the message will be selected according to its type
        """
        current_time = datetime.now().strftime("%H:%M:%S")
        
        color = text_colors["error"]
        if message_type in ["message", "code", "result", "success", "warning"]: color = text_colors[message_type]
        if message_type == "code" or message_type == "result": timestamp = False
        
        if timestamp: timestamped_message = current_time + f">>  {message}"
        else: timestamped_message = f"{message}"

        # Escape HTML to avoid accidental tag injection, then optionally wrap in a colored span so QTextEdit renders it in color.
        escaped = html.escape(timestamped_message)        
        if message_type == "code" or message_type == "result": final = f"<pre><span style=\"color:{color}\">          {escaped}</span></pre>"
        else: final = f"<span style=\"color:{color}\">{escaped}</span>"

        # Print HTML text (QTextEdit.append will render it as rich text).
        print(final, flush = True)

    def extract_number_from_string(self, text: str) -> float | None:
        number_matches = re.findall(r"-?\d+\.?\d*", text)
        numbers = [float(x) for x in number_matches]
        
        if len(numbers) > 0: number = numbers[0]
        else: number = None
        
        return number

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



    # Dynamic GUI updates
    def receive_nanonis_status(self, status: str) -> None:
        match status:
            case "running":
                self.status.update({"nanonis": "running"})
                self.update_buttons()
            case "idle":
                self.status.update({"nanonis": "online"})
                self.update_buttons()
        return

    def update_buttons(self) -> None:
        buttons = self.gui.buttons
        
        cam_button = buttons["camera"]
        mla_button = buttons["mla"]
        nn_button = buttons["nanonis"]
        # Activate/deactivate and color buttons according to hardware status

        match self.status["camera"]:
            case "online":
                cam_button.changeToolTip("Camera: online")
                cam_button.setStyleSheet(style_sheets["connected"])
            case "running":
                cam_button.changeToolTip("Camera: active USB connection")
                cam_button.setStyleSheet(style_sheets["running"])
            case _:
                cam_button.changeToolTip("Camera: offline")
                cam_button.setStyleSheet(style_sheets["disconnected"])

        match self.status["mla"]:
            case "online":
                mla_button.changeToolTip("Multifrequency Lockin Amplifier: online")
                mla_button.setStyleSheet(style_sheets["connected"])
                
                buttons["oscillator"].setEnabled(True)
            
            case "running":
                mla_button.changeToolTip("Multifrequency Lockin Amplifier: active TCP connection")
                mla_button.setStyleSheet(style_sheets["running"])
                
                buttons["oscilator"].setEnabled(False)
            
            case _:
                mla_button.changeToolTip("Nanonis: offline")
                mla_button.setStyleSheet(style_sheets["disconnected"])
                
                buttons["oscillator"].setEnabled(False)

        match self.status["nanonis"]:
            case "online":
                nn_button.setStyleSheet(style_sheets["connected"])
                nn_button.changeToolTip("Nanonis: online")
                nn_button.update()
                nn_button.repaint()
                
                [button.setEnabled(True) for button in self.gui.action_buttons]
                [button.setEnabled(True) for button in self.gui.arrow_buttons]
                buttons["tip"].setEnabled(True)
            
            case "running":
                nn_button.setStyleSheet(style_sheets["running"])
                nn_button.changeToolTip("Nanonis: active TCP connection")
                nn_button.repaint()
                
                [button.setEnabled(False) for button in self.gui.action_buttons]
                [button.setEnabled(False) for button in self.gui.arrow_buttons]
                buttons["tip"].setEnabled(False)
    
            case _:
                nn_button.setStyleSheet(style_sheets["disconnected"])
                nn_button.changeToolTip("Nanonis: offline")
                nn_button.repaint()
                
                [button.setEnabled(False) for button in self.gui.action_buttons]
                [button.setEnabled(False) for button in self.gui.arrow_buttons]
                buttons["tip"].setEnabled(False)                
                buttons["tip"].changeToolTip("Tip status: unknown")
                buttons["tip"].setStyleSheet(style_sheets["disconnected"])
                
                # If Nanonis is offline, proceed with cleanup and make sure the nanonis and measurements attributes are deleted

        style = nn_button.styleSheet()
        nn_button.setStyleSheet(style)
        [button.update for button in [cam_button, mla_button, nn_button]]
        
        return

    def update_tip_status(self) -> None:
        buttons = self.gui.buttons
        tip_button = buttons["tip"]
        
        if self.status["nanonis"] in ["online", "running"]:
            if self.status["tip"].get("withdrawn"):
                tip_button.changeToolTip("Tip withdrawn; click to land")
                tip_button.setIcon(self.icons.get("withdrawn"))
                tip_button.setStyleSheet(style_sheets["idle"])
                buttons["withdraw"].setIcon(self.icons.get("approach"))
                buttons["withdraw"].changeToolTip("Land")
                self.gui.checkboxes["withdraw"].setEnabled(False)

            else:
                [button.setEnabled(False) for button in self.gui.action_buttons[1:]]
                tip_button.setIcon(self.icons.get("contact"))
                buttons["withdraw"].setEnabled(True)
                buttons["withdraw"].setIcon(self.icons.get("withdraw"))
                buttons["withdraw"].changeToolTip("Withdraw")
                self.gui.checkboxes["withdraw"].setEnabled(True)
            
                if self.status["tip"].get("feedback"):
                    tip_button.changeToolTip("Tip in feedback; click to toggle feedback off")
                    tip_button.setStyleSheet(style_sheets["connected"])                
                else:
                    tip_button.changeToolTip("Tip in constant height: click to toggle feedback on")
                    tip_button.setStyleSheet(style_sheets["hold"])
        
        return

    def update_parameter_fields(self) -> None:
        # Enter the scan parameters into the fields
        line_edits = self.gui.line_edits
        comboboxes = self.gui.comboboxes
        
        parameters = self.scan_parameters[0]
        
        for key, value in parameters.items():
            if key in ["V", "bias", "V_nanonis"]:
                self.gui.line_edits["V_nanonis"].setText(f"{value:.2f} V")
            if key == "V_mla":
                self.gui.line_edits["V_mla"].setText(f"{value:.2f} V")
            if key == "I_fb_pA":
                self.gui.line_edits["I_fb"].setText(f"{value:.0f} pA")
            if key == "p_gain_pm":
                self.gui.line_edits["p_gain"].setText(f"{value:.0f} pm")
            if key == "t_const_us":
                self.gui.line_edits["t_const"].setText(f"{value:.0f} us")
            if key == "v_fwd_nm_per_s":
                self.gui.line_edits["v_fwd"].setText(f"{value:.1f} nm/s")
            if key == "v_bwd_nm_per_s":
                self.gui.line_edits["v_bwd"].setText(f"{value:.1f} nm/s")

        return

    def load_parameters(self, index) -> None:
        try:
            params = self.scan_parameters[index]
            
            parameter_names = ["V_nanonis", "V_mla", "I_fb", "v_fwd", "v_bwd", "t_const", "p_gain"]
            #for tag in parameter_names:
            #    if tag in params.keys():
            
            [self.gui.line_edits[tag].setText(f"{params[tag]}") for tag in parameter_names if tag in params.keys()]
        except Exception as e:
            self.logprint(f"Error. {e}", message_type = "error")
        
        return

    def on_experiment_change(self) -> None:
        self.experiment_name = self.gui.comboboxes["experiment"].currentText()
        self.paths["experiment_filename"] = self.get_next_indexed_filename(self.paths["session_path"], self.experiment_name, ".hdf5")
        self.logprint(self.paths["experiment_filename"])
        return



    # Command executions
    def execute_command(self) -> None:
        input_le = self.gui.line_edits["input"]
        input_le.blockSignals(True)
        text = input_le.text()
        input_le.clear()
        input_le.blockSignals(False)
        command = f"self.{text}"
        
        try:
            self.logprint(f"{text}", message_type = "code")
            result = eval(command)
            self.logprint(f"{result}", message_type = "result")
        except Exception as e:
            self.logprint(f"Error: {e}", message_type = "error")
        
        return



    # Button slots
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

    def update_icons(self) -> None:
        self.logprint("Not implemented yet", message_type = "message")
        return

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

    def launch_scanalyzer(self) -> None:
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
        return

    def open_session_folder(self) -> None:        
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

    def exit(self):
        self.cleanup()            
        self.logprint("Thank you for using Scantelligent!", message_type = "success")
        QtWidgets.QApplication.instance().quit()

    def closeEvent(self, event):
        self.exit()



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
        logp = self.logprint
        
        if self.status["initialization"]: logp("Attempting to retrieve information from Nanonis", message_type = "message")

        try:
            # Get tip status
            if self.status["initialization"]: logp("(tip_status, error) = nanonis.tip()", message_type = "code")
            (tip_status, error) = self.nanonis.tip()
            
            if error:
                logp(f"Error retrieving the tip status: {error}", message_type = "error")
                raise
            else:
                self.status["tip"] = tip_status
            
            # Get scan parameters
            if self.status["initialization"]: logp("(parameters, error) = nanonis.parameters()", message_type = "code")
            (parameters, error) = self.nanonis.parameters()
            
            if error:
                logp(f"Error retrieving the scan parameters: {error}", message_type = "error")
                raise
            else:
                self.scan_parameters[0].update(parameters)
                self.paths["session_path"] = parameters.get("session_path")
                name = self.scan_parameters[0].get("name")
                
                self.gui.buttons["session_folder"].setToolTip(f"Open session folder {self.paths['session_path']} (1)")
                self.paths["experiment_file"] = self.get_next_indexed_filename(self.paths["session_path"], "experiment", ".hdf5")

                if self.status["initialization"]:
                    logp(f"I was able to retrieve the tip status and scan parameters and save them to dictionaries called 'status' and 'scan_parameters[0]' (\"{name}\")", message_type = "success")
                    logp(f"[dict] status[\"tip\"] = tip_status = {tip_status}", message_type = "result")
                    logp(f"[dict] scan_parameters[0] = parameters", message_type = "result")
                    logp(f"scan_parameters[0].keys() = {self.scan_parameters[0].keys()}", message_type = "result")



            # Get grid parameters
            if self.status["initialization"]:
                logp("(frame, error) = nanonis.frame()", message_type = "code")
                logp("(grid, error) = nanonis.grid()", message_type = "code")
            (frame, error) = self.nanonis.frame()
            (grid, error) = self.nanonis.grid()
            
            if error:
                logp(f"Error retrieving the scan frame / grid: {error}", message_type = "error")
                raise
            else:
                self.frame = frame
                self.grid = grid
                
                if self.status["initialization"]:
                    logp(f"I obtained frame/grid and scan metadata from nanonis, now available in the dictionaries 'grid' and 'scan_metadata'", message_type = "success")
                    logp(f"frame.keys() = {self.frame.keys()}", message_type = "result")
                    logp(f"grid.keys() = {self.grid.keys()}", message_type = "result")
                    logp(f"scan_metadata.keys() = {self.scan_metadata.keys()}", message_type = "result")
        
        except:
            self.status["nanonis"] = "offline"
            logp("[str] status[\"nanonis\"] = \"offline\"", message_type = "result")
        
        # Continue with requesting the scan metadadata and finally the scan data
        self.on_scan_data_request()
        
        self.update_buttons()
        self.update_tip_status()
        self.update_parameter_fields()
        
        return

    def on_scan_data_request(self):
        logp = self.logprint
        
        try:            
            # Get scan metadata
            if self.status["initialization"]: logp("(scan_metadata, error) = nanonis.scan_metadata()", message_type = "code")
            (scan_metadata, error) = self.nanonis.scan_metadata()
            if error:
                logp("Error retrieving the scan metadata.", message_type = "error")
                raise
            else:
                self.scan_metadata = scan_metadata
                
                # Refresh the recorded channels
                if hasattr(self, "channels"): 
                    recorded_channels_old = self.channels
                else:
                    recorded_channels_old = {}

                self.channels = self.scan_metadata.get("recorded_channels")
                
                # Update the channels combobox with the channels that are being recorded if there is a change
                if self.channels == recorded_channels_old:
                    pass
                else:
                    self.gui.comboboxes["channels"].renewItems(list(self.channels.values()))
                    self.gui.comboboxes["channels"].selectItem("Z (m)")
            
            # Find the channel index from the channels combobox, then get the scan data from nanonis
            selected_channel_name = self.gui.comboboxes["channels"].currentText()
            for key, value in self.channels.items():
                if value == selected_channel_name:
                    selected_channel_index = int(key)
                    break
            
            if self.status["initialization"]: logp("(scan_data, error) = nanonis.get_scan()", message_type = "code")
            (scan_image, error) = self.nanonis.get_scan(selected_channel_index, backward = False)
            
            # All operations successful: release the Nanonis connection
            self.status["nanonis"] = "online"
            
            if self.status["initialization"]: logp("Successfully updated the following dictionaries: 'status[\"tip\"]', 'scan_parameters[0]', 'grid', 'scan_metadata'", message_type = "success")

        except:
            self.status["nanonis"] = "offline"
            logp("[str] status[\"nanonis\"] = \"offline\"", message_type = "result")
            
        try:
            if type(scan_image) == np.ndarray:
                self.gui.image_view.setImage(scan_image)
                image_item = self.gui.image_view.getImageItem()
                
                (frame, error) = self.nanonis.frame()                
                width = self.frame.get("width_nm")
                height = self.frame.get("height_nm")
                
                image_item.setRect(QtCore.QRectF(self.frame.get("x_nm") - 0.5 * width, self.frame.get("y_nm") - 0.5 * height, width, height))
                image_item.setRotation(self.frame.get("angle_deg"))
                self.gui.image_view.autoRange()
        except Exception as e:
            self.logprint(f"Error: {e}")
        
        finally: # Switch off the initialization flag after the first successful parameter retrieval
            if hasattr(self, "frame") and hasattr(self, "grid") and hasattr(self, "scan_metadata"): self.status["initialization"] = False

        return

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
            self.nanonis.bias(new_V)
        except:
            pass
        finally:
            self.on_parameters_request()     
        
        return

    def toggle_withdraw(self) -> bool:
        # Return if Nanonis is not online
        if not hasattr(self, "nanonis"): return False

        self.status["nanonis"] = "running"
        self.gui.buttons["nanonis"].setStyleSheet(style_sheets["running"])
        
        try:
            if self.status["tip"].get("withdrawn"):
                (tip_status, error) = self.nanonis.tip({"feedback": True})
                if error: raise
                elif type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("(status[\"tip\"], error = False) = nanonis.tip({feedback: True})", message_type = "code")
            else:
                (tip_status, error) = self.nanonis.tip({"withdraw": True})
                if error: raise
                elif type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("(status[\"tip\"], error = False) = nanonis.tip({withdraw: True})", message_type = "code")
            
            self.status["nanonis"] = "running"

        except Exception as e:
            if error: self.logprint(f"Error toggling the tip status: {error}", message_type = "error")
            else: self.logprint(f"Error toggling the tip status: {e}", message_type = "error")
            self.status["nanonis"] = "offline"

        self.update_buttons()

        return True

    def change_tip_status(self) -> bool:
        if not hasattr(self, "nanonis"): return False
        
        self.status["nanonis"] = "running"
        self.buttons["nanonis"].setStyleSheet(style_sheets["running"])
        
        try:
            if self.status["tip"].get("withdrawn"):
                (tip_status, error) = self.nanonis.tip(feedback = True)
                if error:
                    self.logprint(f"Error. {e}")
                elif type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("[tuple] ([dict] status[\"tip\"] | [bool] False) = nanonis.tip(feedback = True)", message_type = "code")
            else: # Toggle the feedback
                (tip_status, error) = self.nanonis.tip(feedback = not self.status["tip"].get("feedback"))
                if error:
                    self.logprint(f"Error. {e}")
                if type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("[tuple] ([dict] status[\"tip\"], [bool] False) = nanonis.tip(feedback = not status[\"tip\"].get(\"feedback\"])", message_type = "code")

        except Exception as e:
            self.logprint(f"Error toggling the tip status: {e}", message_type = "error")
            return False

        self.buttons["nanonis"].setStyleSheet(style_sheets["online"])
        self.update_buttons()

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
            
            #if not hasattr(self, "nanonis"): raise
            
            self.logprint("Executing a tip move by passing the dictionary 'move_flags' to nanonis.move")
            self.logprint(f"[dict] move_flags = {move_flags}", message_type = "code")
            self.logprint("nanonis.move(move_flags)", message_type = "code")

            return True
        
        except Exception as e:
            self.logprint("Error. Unable to execute tip move.", message_type = "error")

            return False



    # Experiments and thread management
    def on_experiment_control(self, action: str = "start_pause") -> None:
        sp_button = self.gui.buttons["start_pause"]
        
        if not hasattr(self, "nanonis"): return
        try:
            if action == "start_pause":
                
                match self.status["experiment"]:
                    case "running":
                        action = "pause"
                        self.status["experiment"] = f"{action}d"
                        sp_button.setIcon(self.icons.get("start"))
                        self.nanonis.scan_control({"action": action})
                    case "paused":
                        action = "resume"
                        self.status["experiment"] = "running"
                        sp_button.setIcon(self.icons.get("pause"))
                        self.nanonis.scan_control({"action": action})
                    case _:
                        action = "start"
                        self.status["experiment"] = "running"
                        sp_button.setIcon(self.icons.get("pause"))
                        
                        # Start a timer to connect scan updates to the GUI
                        self.timer = QtCore.QTimer()
                        self.timer.timeout.connect(self.on_scan_data_request)
                        self.timer.start(2000)
                        
                        self.nanonis.scan_control({"action": "start"})
            
            elif action == "stop":
                self.status["experiment"] = "idle"
                sp_button.setIcon(self.icons.get("start"))
                self.nanonis.scan_control({"action": "stop"})
                
                # Kill the timer
                self.timer.stop()
                self.timer.disconnect()
                self.timer.deleteLater()
            
        except Exception as e:
            self.logprint(f"Error. Could not send experiment control command to Nanonis: {e}", message_type = "error")
        
        return



    # Deprecate:
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
    logic_app = App()
    sys.exit(app.exec())
