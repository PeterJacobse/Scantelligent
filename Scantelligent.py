import os, sys, re, html, yaml, cv2, pint, socket, atexit
import numpy as np
from PyQt6 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg
from lib import ScantelligentGUI, StreamRedirector, NanonisAPI, DataProcessing, UserData, PJTargetItem
from time import sleep
from scipy.interpolate import griddata
from datetime import datetime
from experiments import Experiment1, Experiment



colors = {"red": "#ff5050", "dark_red": "#800000", "green": "#00ff00", "dark_green": "#005000", "light_blue": "#30d0ff",
          "white": "#ffffff", "blue": "#2090ff", "orange": "#FFA000","dark_orange": "#A05000", "black": "#000000", "purple": "#700080"}
style_sheets = {
    "neutral": f"background-color: {colors["black"]};",
    "connected": f"background-color: {colors["dark_green"]};",
    "disconnected": f"background-color: {colors["dark_red"]};",
    "running": f"background-color: {colors["blue"]};",
    "hold": f"background-color: {colors["dark_orange"]};",
    "idle": f"background-color: {colors["purple"]};"
    }
text_colors = {"message": colors["white"], "error": colors["red"], "code": colors["blue"], "result": colors["light_blue"], "success": colors["green"], "warning": colors["orange"]}



class Scantelligent(QtCore.QObject):
    abort = QtCore.pyqtSignal()
    parameters = QtCore.pyqtSignal(dict)
    image_request = QtCore.pyqtSignal(int, bool) #, name='image_request'

    def __init__(self):
        super().__init__()
        icon_folder = self.parameters_init()
        self.gui = ScantelligentGUI(icon_folder)
        self.setup_connections() # Initialize the console, the button-slot, and keystroke-slot connections        
        
        self.hardware = self.config_init() # Read the hardware configuration and parameters from the configuration files in the sys folder
        self.data = DataProcessing() # Class for data processing and analysis
        self.timer = QtCore.QTimer()
        self.thread = QtCore.QThread()
        self.nanonis = NanonisAPI(hardware = self.hardware) # Class for simple Nanonis functions
        
        self.connect_hardware() # Test and set up all connections, and request parameters from the hardware components
        self.gui.show()



    def parameters_init(self) -> None:
        atexit.register(self.cleanup)
        
        self.paths = {
            "script": os.path.abspath(__file__), # The full path of Scanalyzer.py
            "parent_folder": os.path.dirname(os.path.abspath(__file__)),            
        }
        self.paths["lib"] = os.path.join(self.paths["parent_folder"], "lib")
        self.paths["sys"] = os.path.join(self.paths["parent_folder"], "sys")
        self.paths["config_file"] = os.path.join(self.paths["sys"], "config.yml")
        self.paths["parameters_file"] = os.path.join(self.paths["sys"], "user_parameters.yml")
        self.paths["icon_folder"] = os.path.join(self.paths["parent_folder"], "icons")

        icon_files = os.listdir(self.paths["icon_folder"])
        self.icons = {}
        for icon_file in icon_files:
            [icon_name, extension] = os.path.splitext(os.path.basename(icon_file))
            try:
                if extension == ".png": self.icons.update({icon_name: QtGui.QIcon(os.path.join(self.paths["icon_folder"], icon_file))})
            except:
                pass

        self.ureg = pint.UnitRegistry()
        self.user = UserData()
        self.lines = [] # Lines for plotting in the graph

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
        
        return self.paths["icon_folder"]

    def setup_connections(self) -> None:
        """
        Initialize the console, the button-slot, and keystroke-slot connections
        """

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
                        ["oscillator", self.toggle_withdraw], ["view", self.toggle_withdraw], ["session_folder", self.open_session_folder], ["info", self.on_info],
                        
                        ["withdraw", self.toggle_withdraw], ["retract", lambda: self.on_coarse_move("up")], ["advance", lambda: self.on_coarse_move("down")], ["approach", self.on_approach],
                        
                        ["tip", self.change_tip_status], ["V_swap", self.on_scan_data_request], ["set", self.set_parameters], ["get", self.get_parameters],
                        
                        ["bias_pulse", lambda: self.tip_prep("pulse")], ["tip_shape", lambda: self.tip_prep("shape")], ["fit_to_frame", lambda: self.set_view_range("frame")], ["fit_to_range", lambda: self.set_view_range("piezo_range")],

                        ["nanonis_mod1", lambda: self.modulator_control(modulator_number = 1)], ["nanonis_mod2", lambda: self.modulator_control(modulator_number = 2)],

                        ["start_pause", lambda action: self.on_experiment_control(action = "start_pause")], ["stop", lambda action: self.on_experiment_control(action = "stop")],
                        ]

            # for direction in ["n", "ne", "e", "se", "s", "sw", "w", "nw"]:
            #    buttons[direction].clicked.connect(lambda drxn = direction: self.on_coarse_move(drxn))
            buttons["n"].clicked.connect(lambda: self.on_coarse_move("n"))
            buttons["ne"].clicked.connect(lambda: self.on_coarse_move("ne"))
            buttons["e"].clicked.connect(lambda: self.on_coarse_move("e"))
            buttons["se"].clicked.connect(lambda: self.on_coarse_move("se"))
            buttons["s"].clicked.connect(lambda: self.on_coarse_move("s"))
            buttons["sw"].clicked.connect(lambda: self.on_coarse_move("sw"))
            buttons["w"].clicked.connect(lambda: self.on_coarse_move("w"))
            buttons["nw"].clicked.connect(lambda: self.on_coarse_move("nw"))

            connections.append([f"scan_parameters_0", lambda: self.load_parameters_from_file("scan_parameters", 0)])
            connections.append([f"scan_parameters_1", lambda: self.load_parameters_from_file("scan_parameters", 1)])
            connections.append([f"scan_parameters_2", lambda: self.load_parameters_from_file("scan_parameters", 2)])
            connections.append([f"scan_parameters_3", lambda: self.load_parameters_from_file("scan_parameters", 3)])
            
            #for direction in ["n", "ne", "e", "se", "s", "sw", "w", "nw"]:
            #    buttons[direction].clicked.connect(lambda drxn = direction: self.on_coarse_move(drxn))
            
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
            self.gui.comboboxes["channels"].currentIndexChanged.connect(self.request_nanonis_update)
            self.gui.comboboxes["experiment"].currentIndexChanged.connect(self.on_experiment_change)
            
            # Instantiate process for CLI-style commands (opening folders and other programs)
            self.process = QtCore.QProcess(self.gui)
            
            self.gui.image_view.position_signal.connect(self.receive_double_click)

            return
        
        connect_console()
        connect_buttons()    
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

                    hardware = {
                        "nanonis_ip": tcp_ip,
                        "nanonis_port": tcp_port,
                        "nanonis_version": version_number,
                        "camera_argument": camera_argument
                    }
                    self.logprint("I found the config.yml file and was able to set up a dictionary called 'hardware'", message_type = "success")
                    self.logprint(f"[dict] hardware = {hardware}", message_type = "result")
                    
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
      
        [self.gui.buttons[f"scan_parameters_{i}"].changeToolTip(f"Load scan parameter set {i} ({self.user.scan_parameters[i].get("name")})") for i in range(len(self.user.scan_parameters))]
        
        
        
        # Initialize the scan parameters in the gui as parameter set 0, until a connection to Nanonis is made
        self.load_parameters_from_file("scan_parameters", index = 0)
        self.load_parameters_from_file("tip_prep_parameters", index = 0)
        
        # Make a tip target item in the image_view
        self.tip_target = PJTargetItem(pos = [0, 0], size = 10, tip_text = f"tip location\n({0}, {0}) nm", movable = True)
        self.gui.image_view.view.addItem(self.tip_target)
        
        return hardware

    def connect_hardware(self) -> None:
        """
        Test and set up all connections, and request parameters from the hardware components
        """

        def connect_camera() -> None:            
            argument = self.hardware.get("camera_argument")
            
            try:
                self.logprint(f"cap = cv2.VideoCapture({argument})", message_type = "code")
                cap = cv2.VideoCapture(argument)
                
                if not cap.isOpened(): # Check if the camera opened successfully
                    raise
                else:
                    cap.release()
                    self.status["camera"] = "online"
                    
                    self.logprint("Success! Camera stream received.", message_type = "success")

            except Exception as e:
                self.logprint("Warning. Failed to connect to the camera.", message_type = "warning")
            
            return    

        def connect_mla() -> None:
            self.status["mla"] = "offline"
            
            self.logprint("Warning. Failed to connect to the MLA.", message_type = "warning")
            
            return

        def connect_nanonis() -> None:
            # Initialize signal-slot connections
            
            # Scantelligent -> Nanonis
            self.parameters.connect(self.nanonis.receive_parameters)
            self.image_request.connect(self.nanonis.receive_image_request)
            self.abort.connect(self.nanonis.abort)

            # Nanonis -> Scantelligent
            self.nanonis.connection.connect(self.receive_nanonis_status)
            self.nanonis.progress.connect(self.receive_progress)
            self.nanonis.message.connect(self.receive_message)
            self.nanonis.parameters.connect(self.receive_parameters)
            self.nanonis.image.connect(self.receive_image)
            self.nanonis.finished.connect(self.experiment_finished)
            self.nanonis.data_array.connect(self.receive_data)
            
            match self.status["nanonis"]:
                case "idle": # Nanonis was already online. Create an active TCP-IP connection
                    try: self.nanonis.connect()
                    except: pass
                
                case "running": # Nanonis is currently running. Close the TCP-IP connection
                    try: self.nanonis.disconnect()
                    except: pass
                
                case _: # Nanonis was offline, either not yet initizialized or flagged offline due to an error
                    try: self.nanonis.initialize(auto_disconnect = True)
                    except: pass

            return

        def populate_completer() -> None:
            # Populate the command input completer with all attributes and methods of self and self.gui
            self.all_attributes = dir(self)
            gui_attributes = ["gui." + attr for attr in self.gui.__dict__ if not attr.startswith('__')]
            nanonis_attributes = ["nanonis." + attr for attr in self.nanonis.__dict__ if not attr.startswith('__')]
            nanonis_hw_attributes = ["nanonis.nanonis_hardware." + attr for attr in self.nanonis.nanonis_hardware.__dict__ if not attr.startswith('__')]
            data_attributes = ["data." + attr for attr in self.data.__dict__ if not attr.startswith('__')]
            
            [self.all_attributes.extend(attributes) for attributes in [gui_attributes, nanonis_attributes, nanonis_hw_attributes, data_attributes]]
            completer = QtWidgets.QCompleter(self.all_attributes, self.gui)
            completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
            completer.setCompletionMode(QtWidgets.QCompleter.CompletionMode.PopupCompletion)
            self.gui.line_edits["input"].setCompleter(completer)

        self.logprint("Attempting to connect to hardware", message_type = "message")
        connect_camera()
        connect_mla()
        connect_nanonis()
        
        # Update the buttons in the gui and populate the autocomplete suggestions in the command input
        self.update_buttons()
        populate_completer()
        return



    # PyQt slots
    @QtCore.pyqtSlot(float, float)
    def receive_double_click(self, x: float, y: float) -> None:
        self.nanonis.tip_update({"x (nm)": x, "y (nm)": y})
        self.logprint(f"nanonis.tip_update({{\"x (nm)\": {x}, \"y (nm)\": {y}}})", message_type = "code")
        return
    
    @QtCore.pyqtSlot(str)
    def receive_nanonis_status(self, status: str) -> None:
        # Nanonis emits the 'running' flag when it connects and the 'online' flag when it disconnects.
        # These flags are used to update the corresponding status in Scantelligent and provide logic for blocking - preventing the collision of multiple simultaneous TCP code executions
        match status:
            case "running":
                self.status.update({"nanonis": "running"})
                self.update_buttons()
            case "idle":
                self.status.update({"nanonis": "idle"})
                self.update_buttons()
            case "offline":
                self.status.update({"nanonis": "offline"})
                self.update_buttons()
            case _:
                pass
        return

    @QtCore.pyqtSlot(int)
    def receive_progress(self, progress: int) -> None:
        self.gui.progress_bars["experiment"].setValue(progress)
        return

    @QtCore.pyqtSlot(str, str)
    def receive_message(self, text: str, mtype: str) -> None:
        self.logprint(text, message_type = mtype)
        return

    @QtCore.pyqtSlot(dict)
    def receive_parameters(self, parameters: dict) -> None:
        # Read the name of the dict to determine what type of parameters are in there
        dict_name = parameters.get("dict_name")
        self.logprint(dict_name, message_type = "code")
        
        match dict_name:
            
            case "coarse_parameters":
                self.user.coarse_parameters[0].update(parameters)
                
                # Remove this once a 'set' and 'get' are implemented
                self.gui.line_edits["V_hor"].setText(str(parameters.get("V_motor (V)")))
                self.gui.line_edits["V_ver"].setText(str(parameters.get("V_motor (V)")))
                self.gui.line_edits["f_motor"].setText(str(parameters.get("f_motor (Hz)")))
            
            case "channels":
                for key, value in parameters.items():
                    if key == "dict_name": continue

                    channel_index = int(key)
                    if channel_index < 0 or channel_index > 20: continue

                    self.gui.channel_checkboxes[f"{channel_index}"].setToolTip(f"Channel {channel_index}: {value}")
                    line = self.gui.plot_widget.plot()
                    self.lines.append(line)

            case "tip_status":
                tip_status = parameters
                self.status.update({"tip_status": tip_status})
                
                # Update the slider
                z_limits_nm = tip_status.get("z_limits (nm)")
                z_nm = tip_status.get("z (nm)")
                self.gui.tip_slider.setMinimum(int(z_limits_nm[0]))
                self.gui.tip_slider.setMaximum(int(z_limits_nm[1]))
                self.gui.tip_slider.setValue(int(z_nm))
                self.gui.tip_slider.changeToolTip(f"Tip height: {z_nm:.2f} nm")
                
                # Update the position visible in the image_view
                self.gui.image_view.view.removeItem(self.tip_target)
                x_tip_nm = tip_status.get("x (nm)", 0)
                y_tip_nm = tip_status.get("y (nm)", 0)
                self.tip_target.setPos(x_tip_nm, y_tip_nm)
                self.tip_target.text_item.setText(f"tip location\n({x_tip_nm:.2f}, {y_tip_nm:.2f}) nm")
                self.gui.image_view.view.addItem(self.tip_target)
                
                self.update_tip_status()
            
            case "scan_parameters":
                scan_parameters = parameters
                self.user.scan_parameters[0].update(scan_parameters)

            case "frame":
                frame = parameters
                self.user.frames[0].update(frame)
                
                if hasattr(self, "frame_roi"): self.gui.image_view.view.removeItem(self.frame_roi)
                
                [x_0_nm, y_0_nm] = frame.get("offset (nm)", [0, 0])
                [w_nm, h_nm] = frame.get("scan_range (nm)", [100, 100])
                angle_deg = frame.get("angle (deg)", 0)
                
                # Add the frame to the ImageView
                self.frame_roi = pg.ROI([0, 0], [w_nm, h_nm], pen = pg.mkPen(color = colors["blue"], width = 2), movable = True, resizable = False, rotatable = True)
                self.frame_roi.addRotateHandle([0, 0.5], [0.5, 0.5])
                
                self.gui.image_view.addItem(self.frame_roi)
                self.frame_roi.setAngle(angle = -angle_deg)
                
                bounding_rect = self.frame_roi.boundingRect()
                local_center = bounding_rect.center()
                frame_roi_center = self.frame_roi.mapToParent(local_center)
                self.frame_roi.setPos(x_0_nm - frame_roi_center.x(), y_0_nm - frame_roi_center.y())
            
            case "grid":
                grid = parameters
            
            case "piezo_range":
                piezo_range = parameters
                
                if hasattr(self, "piezo_roi"): self.gui.image_view.view.removeItem(self.piezo_roi)
                
                piezo_range_nm = [piezo_range.get("x_range (nm)"), piezo_range.get("y_range (nm)")]
                piezo_lower_left_nm = [piezo_range.get("x_min (nm)"), piezo_range.get("y_min (nm)")]
                self.piezo_roi = pg.ROI(piezo_lower_left_nm, piezo_range_nm, pen = pg.mkPen(color = colors["orange"], width = 2), movable = False, resizable = False, rotatable = False)
                
                # Add the frame to the ImageView
                self.gui.image_view.addItem(self.piezo_roi)
            
            case "scan_metadata":
                scan_metadata = parameters

                # Refresh the recorded channels
                if hasattr(self, "channels"): channels_old = self.channels
                else: channels_old = {}
                self.channels = scan_metadata.get("channel_dict", {})
                
                # Update the channels combobox with the channels that are being recorded if there is a change
                if self.channels == channels_old:
                    pass
                else:
                    self.gui.comboboxes["channels"].renewItems(list(self.channels.keys()))
                    self.gui.comboboxes["channels"].selectItem("Z (m)")

            case _:
                pass
        
        return

    @QtCore.pyqtSlot(np.ndarray)
    def receive_image(self, image: np.ndarray) -> None:
        try:                
            # Save the current state and clear the image, then set a new one
            #current_state = self.gui.image_view.view.autoRange
            self.gui.image_view.clear()
            try:
                self.gui.image_view.setImage(np.fliplr(np.flipud(image)).T, autoRange = False)
            except:
                pass
            
            # Use the frame to update the imageitem box
            frame = self.user.frames[0]
            
            scan_range_nm = frame.get("scan_range (nm)", [100, 100])
            angle_deg = frame.get("angle (deg)", 0)
            offset_nm = frame.get("offset (nm)", [0, 0])
        
            w = scan_range_nm[0]
            h = scan_range_nm[1]
            x = offset_nm[0]
            y = offset_nm[1]
        
            image_item = self.gui.image_view.getImageItem()
            box = QtCore.QRectF(- w / 2, - h / 2, w, h)
            image_item.setRect(box)
            
            center = image_item.boundingRect().center()
            image_item.setTransformOriginPoint(center)
            image_item.setRotation(90 - angle_deg)
            image_item.setPos(x, y)

        except Exception as e:
            self.logprint(f"Error: {e}")
            
        return

    @QtCore.pyqtSlot(np.ndarray)
    def receive_data(self, data_array: np.ndarray) -> None:
        
        self.logprint(f"Data: {data_array}")
        
        for plot_number in range(len(data_array[0])):
            pen = pg.mkPen(color = self.gui.color_list[plot_number])
            
            y_data = data_array[:, plot_number]
            x_data = range(len(y_data))
            
            self.lines[plot_number].setData(x_data, y_data)

        return



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
        return

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

    def set_view_range(self, obj: str) -> None:
        imv = self.gui.image_view
        
        match obj:

            case "frame":
                if hasattr(self, "piezo_roi"):                    
                    imv.removeItem(self.piezo_roi)
                    imv.autoRange()
                    imv.addItem(self.piezo_roi)

            case "piezo_range":                
                imv.autoRange()

            case _:
                pass
        
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
            case "idle":
                self.timer.blockSignals(False)
                nn_button.setStyleSheet(style_sheets["connected"])
                nn_button.changeToolTip("Nanonis: idle")
                nn_button.repaint()
                            
            case "running":
                nn_button.setStyleSheet(style_sheets["running"])
                nn_button.changeToolTip("Nanonis: active TCP connection")
                nn_button.repaint()
                    
            case _:
                self.timer.blockSignals(True)
                nn_button.setStyleSheet(style_sheets["disconnected"])
                nn_button.changeToolTip("Nanonis: offline")
                nn_button.repaint()
                          
                buttons["tip"].changeToolTip("Tip status: unknown")
                buttons["tip"].setStyleSheet(style_sheets["disconnected"])

        style = nn_button.styleSheet()
        nn_button.setStyleSheet(style)
        [button.update for button in [cam_button, mla_button, nn_button]]
        
        return

    def update_tip_status(self) -> None:
        buttons = self.gui.buttons
        tip_button = buttons["tip"]
        
        if self.status["nanonis"] in ["idle", "running"]:
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

    def load_parameters_from_file(self, parameters_type: str = "scan_parameters", index: int = 0) -> None:
        try:
            match parameters_type:
                case "scan_parameters":
                    params = self.user.scan_parameters[index]
                    
                    parameter_names = ["V_nanonis (V)", "V_mla (V)", "I_fb (pA)", "v_fwd (nm/s)", "v_bwd (nm/s)", "t_const (us)", "p_gain (pm)"]
                    line_edit_names = ["V_nanonis", "V_mla", "I_fb", "v_fwd", "v_bwd", "t_const", "p_gain"]
                    units = ["V", "V", "pA", "nm/s", "nm/s", "us", "pm"]
                    line_edits = [self.gui.line_edits[name] for name in line_edit_names]
                    
                    for name, le, unit in zip(parameter_names, line_edits, units):
                        if name in params.keys(): le.setText(f"{params[name]:.2f} {unit}")
                
                case "tip_prep_parameters":
                    params = self.user.tip_prep_parameters[index]
                    
                    parameter_names = ["pulse_voltage (V)", "pulse_duration (ms)"]
                    line_edit_names = ["pulse_voltage", "pulse_duration"]
                    units = ["V", "ms"]
                    line_edits = [self.gui.line_edits[name] for name in line_edit_names]
                    
                    for name, le, unit in zip(parameter_names, line_edits, units):
                        if name in params.keys(): le.setText(f"{params[name]:.2f} {unit}")
                    
                case _:
                    pass

        except Exception as e:
            self.logprint(f"Error loading parameters. {e}", message_type = "error")
        
        return

    def on_experiment_change(self) -> None:
        self.experiment_name = self.gui.comboboxes["experiment"].currentText()
        if "session_path" in self.paths.keys():
            self.paths["experiment_filename"] = self.get_next_indexed_filename(self.paths["session_path"], self.experiment_name, ".hdf5")
            self.gui.line_edits["experiment_filename"].setText(self.paths["experiment_filename"])
        else: return
        self.logprint(self.paths["experiment_filename"])
        return



    # Simple Nanonis requests
    def get_parameters(self) -> None:
        le = self.gui.line_edits
        nanonis = self.nanonis
        # Request a parameter update from Nanonis, and wait to receive
        # The received parameters are stored in self.user.scan_parameters[0] by default
        nanonis.parameters_update(auto_disconnect = False)
        nanonis.frame_update(auto_disconnect = False)
        nanonis.tip_update(auto_disconnect = True)
        sleep(.2)
        scan_parameters = self.user.scan_parameters[0]

        self.gui.plot_widget.plot(np.linspace(0, 2, 20), np.random.rand(20))
        
        # Enter the scan parameters into the fields        
        for key, value in scan_parameters.items():
            match key:
                case "V_nanonis (V)": le["V_nanonis"].setText(f"{value:.2f} V")
                case "V_mla (V)": le["V_mla"].setText(f"{value:.2f} V")
                case "I_fb (pA)": le["I_fb"].setText(f"{value:.0f} pA")
                case "p_gain (pm)": le["p_gain"].setText(f"{value:.0f} pm")
                case "t_const (us)": le["t_const"].setText(f"{value:.0f} us")
                case "v_fwd (nm/s)": le["v_fwd"].setText(f"{value:.1f} nm/s")
                case "v_bwd (nm/s)": le["v_bwd"].setText(f"{value:.1f} nm/s")
        
        return

    def set_parameters(self) -> None:
        # Update Nanonis according to the parameters that were set in the GUI
        s_p = self.user.scan_parameters[0]
        
        for tag in ["V_nanonis", "V_mla", "I_fb", "p_gain", "t_const", "v_fwd", "v_bwd"]:
            str = self.gui.line_edits[tag].text()
            numbers = self.data.extract_numbers_from_str(str)
            if len(numbers) < 1: continue
            flt = numbers[0]
            
            match tag:
                case "V_nanonis": s_p.update({"V_nanonis (V)": flt})
                case "V_mla": s_p.update({"V_mla (V)": flt})
                case "I_fb": s_p.update({"I_fb (pA)": flt})
                case "p_gain": s_p.update({"p_gain (pm)": flt})
                case "t_const": s_p.update({"t_const (us)": flt})
                case "v_fwd": s_p.update({"v_fwd (nm/s)": flt})
                case "v_bwd": s_p.update({"v_bwd (nm/s)": flt})
                case _: pass

        self.nanonis.parameters_update(s_p)
        
        return

    def request_nanonis_update(self) -> None:
        try:
            channel_name = self.gui.comboboxes["channels"].currentText()
            backward = self.gui.buttons["direction"].isChecked()
            channel_index = self.channels.get(channel_name)

            if self.status["nanonis"] == "idle":
                self.image_request.emit(channel_index, backward)
            else:
                pass
        except:
            pass
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
            compile(command, "<string>", "eval")

            result = eval(command)
            self.logprint(f"{result}", message_type = "result")
        except SyntaxError:
            try:
                compile(command, "<string>", "exec")
                
                assignment = command.split("=")
                assignment = [part.strip() for part in assignment]
                
                if assignment[1].startswith("nanonis") or assignment[1].startswith("data") or assignment[1].startswith("file_functions") or assignment[1].startswith("user"):
                    command = f"{assignment[0]} = self.{assignment[1]}"

                exec(command)
            except SyntaxError:
                self.logprint("Invalid code.", message_type = "error")
            except Exception as e:
                self.logprint(f"{e}", message_type = "error")
        except Exception as e:
            self.logprint(f"{e}", message_type = "error")
        
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



    # Information popup
    def on_info(self) -> None:
        msg_box = QtWidgets.QMessageBox(self.gui)
        
        msg_box.setWindowTitle("Info")
        msg_box.setText("Scantelligent (2026)\nby Peter H. Jacobse\nRice University; Lawrence Berkeley National Lab")
        msg_box.setStandardButtons(QtWidgets.QMessageBox.StandardButton.Ok)
        msg_box.setIcon(QtWidgets.QMessageBox.Icon.Information)

        #QtCore.QTimer.singleShot(5000, msg_box.close)
        retval = msg_box.exec()
        
        return

    def cleanup(self) -> None:
        self.user.save_parameter_sets()
        try: self.nanonis.disconnect()
        except: pass
        try:
            self.timer.stop()
            self.timer.disconnect()
            self.timer.deleteLater()
        except:
            pass
        if hasattr(self, "nanonis"): delattr(self, "nanonis")
        if hasattr(self, "measurements"): delattr(self, "measurements")

    def exit(self) -> None:
        self.cleanup()
        self.logprint("Thank you for using Scantelligent!", message_type = "success")
        QtWidgets.QApplication.instance().quit()

    def closeEvent(self, event) -> None:
        self.exit()



    # Nanonis functions 
    # Simple data requests over TCP-IP
    def tip_prep(self, action: str):
        try:
            match action:
            
                case "pulse":
                    str = self.gui.line_edits["pulse_voltage"].text()
                    numbers = self.data.extract_numbers_from_str(str)
                    if len(numbers) < 1: return
                    else: V_pulse_V = numbers[0]
                    
                    str = self.gui.line_edits["pulse_duration"].text()
                    numbers = self.data.extract_numbers_from_str(str)
                    if len(numbers) < 1: return
                    else: t_pulse_ms = numbers[0]
                    
                    self.user.tip_prep_parameters[0].update({"V_pulse (V)": V_pulse_V, "t_pulse (ms)": t_pulse_ms})
                    
                    action_dict = {"action": "pulse", "V_pulse (V)": V_pulse_V, "t_pulse (ms)": t_pulse_ms}
                    self.nanonis.tip_prep(action_dict)
                
                case "shape":
                    self.nanonis.tip_prep({"action": "shape"})
                
                case _:
                    pass
        except:
            pass

        return

    # Deprecated
    def on_parameters_request(self):
        logp = self.logprint
        
        if self.status["initialization"]: logp("Attempting to retrieve information from Nanonis", message_type = "message")

        try:
            # Get tip status
            if self.status["initialization"]: logp("(tip_status, error) = nanonis.tip_update()", message_type = "code")
            (tip_status, error) = self.nanonis.tip_update(auto_disconnect = False)
            
            if error:
                logp(f"Error retrieving the tip status: {error}", message_type = "error")
                raise
            else:
                self.status["tip"] = tip_status
            
            # Get scan parameters
            if self.status["initialization"]: logp("(parameters, error) = nanonis.parameters_update()", message_type = "code")
            (parameters, error) = self.nanonis.parameters_update(auto_disconnect = False)
            
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
                logp("(frame, error) = nanonis.frame_update()", message_type = "code")
                logp("(grid, error) = nanonis.grid_update()", message_type = "code")
            (frame, error) = self.nanonis.frame_update(auto_disconnect = False)
            (grid, error) = self.nanonis.grid_update(auto_disconnect = False)
            
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
        try: self.nanonis.disconnect()
        except: pass
        
        self.status["initialization"] = False
                    
        self.update_buttons()
        self.update_tip_status()
        
        return

    # Deprecated
    def on_scan_data_request(self):
        logp = self.logprint
        
        try:            
            # Get scan metadata
            if self.status["initialization"]: logp("(scan_metadata, error) = nanonis.scan_metadata_update()", message_type = "code")
            (scan_metadata, error) = self.nanonis.scan_metadata_update()
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
            (scan_image, error) = self.nanonis.scan_update(selected_channel_index, backward = False)
            
            # All operations successful: release the Nanonis connection
            self.status["nanonis"] = "idle"
            
            if self.status["initialization"]: logp("Successfully updated the following dictionaries: 'status[\"tip\"]', 'scan_parameters[0]', 'grid', 'scan_metadata'", message_type = "success")

        except:
            self.status["nanonis"] = "offline"
            logp("[str] status[\"nanonis\"] = \"offline\"", message_type = "result")
        """
        try:
            if type(scan_image) == np.ndarray:
                self.gui.image_view.setImage(scan_image)
                image_item = self.gui.image_view.getImageItem()
                
                (frame, error) = self.nanonis.frame_update()                
                width = self.frame.get("width (nm)")
                height = self.frame.get("height (nm)")
                
                image_item.setRect(QtCore.QRectF(self.frame.get("x (nm)") - 0.5 * width, self.frame.get("y (nm)") - 0.5 * height, width, height))
                image_item.setRotation(self.frame.get("angle_deg"))
                self.gui.image_view.autoRange()
        except Exception as e:
            self.logprint(f"Error: {e}")
        
        finally: # Switch off the initialization flag after the first successful parameter retrieval
            if hasattr(self, "frame") and hasattr(self, "grid") and hasattr(self, "scan_metadata"): self.status["initialization"] = False
        """

        return



    # Simple Nanonis functions; typically return either True if successful or an old parameter value when it is changed
    def toggle_withdraw(self) -> bool:
        error = False

        try:
            tip_status = self.status["tip"]
            tip_withdrawn = tip_status.get("withdrawn")
            
            if tip_withdrawn:
                (tip_status, error) = self.nanonis.tip_update({"feedback": True})
                if error: raise
                elif type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("nanonis.tip_update({\"feedback\": True})", message_type = "code")
            else:
                (tip_status, error) = self.nanonis.tip_update({"withdraw": True})
                if error: raise
                elif type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint("nanonis.tip_update({\"withdraw\": True})", message_type = "code")

        except Exception as e:
            if error: self.logprint(f"Error toggling the tip status: {error}", message_type = "error")
            else: self.logprint(f"Error toggling the tip status: {e}", message_type = "error")

        self.update_buttons()
        self.update_tip_status()

        return True

    def change_tip_status(self) -> bool:
        try:
            tip_status = self.status["tip"]
            tip_withdrawn = tip_status.get("withdrawn")
            tip_in_feedback = tip_status.get("feedback")
            
            if tip_withdrawn: # Tip is withdrawn: land it
                (tip_status, error) = self.nanonis.tip_update({"feedback": True})
                if error:
                    self.logprint(f"Error: {e}")
                elif type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint(f"nanonis.tip_update({{\"feedback\": True}})", message_type = "code")
            
            else: # Toggle the feedback
                self.logprint(f"status[\"tip\"].get(\"feedback\"] = {tip_in_feedback}", message_type = "result")
                
                (tip_status, error) = self.nanonis.tip_update({"feedback": not tip_in_feedback})
                if error:
                    self.logprint(f"Error. {e}")
                if type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint(f"nanonis.tip_update({{\"feedback\": {not tip_in_feedback}}})", message_type = "code")

        except Exception as e:
            self.logprint(f"Error toggling the tip status: {e}", message_type = "error")
            return False

        self.update_buttons()
        self.update_tip_status()

        return True

    def on_coarse_move(self, direction: str = "n") -> bool:
        checkboxes = self.gui.checkboxes
        line_edits = self.gui.line_edits
        motions = {}

        if direction not in ["n", "ne", "e", "se", "s", "sw", "w", "nw", "up", "down"]:
            self.logprint("Error. Unknown tip direction requested.", message_type = "error")
            return False

        try:
            # Retrieve the checkbox states
            withdraw = checkboxes["withdraw"].isChecked()
            retract = checkboxes["retract"].isChecked()
            move = checkboxes["move"].isChecked()
            advance = checkboxes["advance"].isChecked()
            approach = checkboxes["approach"].isChecked()

            # Frequency and amplitude
            numbers = self.data.extract_numbers_from_str(line_edits["V_hor"].text())
            if len(numbers) > 0: V_hor = float(numbers[0])
            else: V_hor = None
            numbers = self.data.extract_numbers_from_str(line_edits["V_ver"].text())
            if len(numbers) > 0: V_ver = float(numbers[0])
            else: V_ver = None
            numbers = self.data.extract_numbers_from_str(line_edits["f_motor"].text())
            if len(numbers) > 0: f_motor = float(numbers[0])
            else: f_motor = None

            # Retrieve the line_edit values
            # The number of steps up
            numbers = self.data.extract_numbers_from_str(line_edits["z_steps"].text())
            if len(numbers) > 0: z_steps = int(numbers[0])
            else: z_steps = 0
            if z_steps < 1: retract = False
           
            # The number of steps horizontally
            numbers = self.data.extract_numbers_from_str(line_edits["h_steps"].text())
            if len(numbers) > 0: h_steps = int(numbers[0])
            else: h_steps = 0
            if h_steps < 1: move = False

            # The number of steps down
            numbers = self.data.extract_numbers_from_str(line_edits["minus_z_steps"].text())
            if len(numbers) > 0: minus_z_steps = int(numbers[0])
            else: minus_z_steps = 0
            if minus_z_steps < 1: advance = False

            # Perform simple vertical motions if requested
            match direction:
                case "up":
                    if z_steps > 0:
                        motions = {"withdraw": withdraw, "direction": "up", "z_steps": z_steps, "V_motor (V)": V_ver, "f_motor (Hz)": f_motor}           
                        self.nanonis.coarse_move(motions)
                        return True
                    else:
                        return False
                case "down":
                    if minus_z_steps > 0:
                        motions = {"withdraw": withdraw, "direction": "down", "minus_z_steps": minus_z_steps, "V_motor (V)": V_ver, "f_motor (Hz)": f_motor}           
                        self.nanonis.coarse_move(motions)
                        return True
                    else:
                        return False
                case _:
                    pass



            # Horizontal (composite) motion
            motions = {
                "withdraw": withdraw,
                "approach": approach,
                "V_hor (V)": V_hor,
                "V_ver (V)": V_ver,
                "f_motor (Hz)": f_motor
            }
            
            if retract and (z_steps > 0): motions.update({"z_steps": z_steps})
            if advance and (minus_z_steps > 0): motions.update({"minus_z_steps": minus_z_steps})
            if move and (h_steps > 0): motions.update({"h_steps": h_steps, "direction": direction})
            
            self.nanonis.coarse_move(motions)
            
            return True
        
        except Exception as e:
            self.logprint("Error. Unable to execute tip move.", message_type = "error")

            return False

    def on_approach(self) -> None:
        numbers = self.data.extract_numbers_from_str(self.gui.line_edits["V_ver"].text())
        if len(numbers) > 0: V_ver = float(numbers[0])
        else: V_ver = None

        self.nanonis.auto_approach(True, V_motor = V_ver)
        return



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
                        # self.nanonis.scan_control({"action": action})

                    case "paused":
                        action = "resume"
                        self.status["experiment"] = "running"
                        sp_button.setIcon(self.icons.get("pause"))
                        # self.nanonis.scan_control({"action": action})

                    case _:
                        self.start_new_experiment()

            
            elif action == "stop":
                self.abort_experiment()
            
        except Exception as e:
            self.logprint(f"Error. Could not send experiment control command to Nanonis: {e}", message_type = "error")
        return

    def start_new_experiment(self):
        sp_button = self.gui.buttons["start_pause"]
        experiment_name = self.gui.comboboxes["experiment"].currentText()
        self.logprint(experiment_name)

        action = "start"
        self.status["experiment"] = "running"
        sp_button.setIcon(self.icons.get("pause"))
        
        if 2 == 2: return

        match experiment_name:
            
            case "nanonis_scan":
                self.timer.timeout.connect(self.request_nanonis_update)
                self.timer.start(1000)
                self.nanonis.scan_control({"action": action})

            case "demo_experiment":
                self.experiment = Experiment1(self.hardware)

                # Set up the PyQt signal-slot connections
                # Scantelligent -> Experiment
                self.parameters.connect(self.experiment.receive_parameters)
                self.abort.connect(self.experiment.abort)

                # Experiment -> Scantelligent
                self.experiment.connection.connect(self.receive_nanonis_status)
                self.experiment.progress.connect(self.receive_progress)
                self.experiment.message.connect(self.receive_message)
                self.experiment.parameters.connect(self.receive_parameters)
                self.experiment.image.connect(self.receive_image)

                # Create a thread and move the experiment to the thread
                self.experiment.moveToThread(self.thread)
                self.thread.started.connect(self.experiment.run)
                self.experiment.finished.connect(self.thread.quit)
                # Ensure the thread is deleted only after the worker finished
                self.experiment.finished.connect(self.thread.deleteLater)
                self.experiment.finished.connect(self.experiment.deleteLater)
                self.thread.start()

            case "capacitive_walk":
                self.experiment = Experiment(self.hardware)

                # Set up the PyQt signal-slot connections
                # Scantelligent -> Experiment
                self.parameters.connect(self.experiment.receive_parameters)
                self.abort.connect(self.experiment.abort)

                # Experiment -> Scantelligent
                self.experiment.connection.connect(self.receive_nanonis_status)
                self.experiment.progress.connect(self.receive_progress)
                self.experiment.message.connect(self.receive_message)
                self.experiment.parameters.connect(self.receive_parameters)
                self.experiment.image.connect(self.receive_image)
                self.experiment.data_array.connect(self.receive_data)

                # Create a thread and move the experiment to the thread
                self.experiment.moveToThread(self.thread)
                self.thread.started.connect(self.experiment.run)
                self.experiment.finished.connect(self.thread.quit)
                # Ensure the thread is deleted only after the worker finished
                self.experiment.finished.connect(self.thread.deleteLater)
                self.experiment.finished.connect(self.experiment.deleteLater)
                self.thread.start()
            case _:
                pass
        
        return
               
    def abort_experiment(self):
        #self.timer.stop()
        #self.timer.disconnect()

        self.status["experiment"] = "idle"
        self.gui.buttons["start_pause"].setIcon(self.icons.get("start"))
        
        # self.nanonis.scan_control({"action": "stop"})
        self.abort.emit()

        if hasattr(self, "thread") and self.thread.isRunning():
            try:
                self.thread.quit()
            except Exception:
                pass

        return

    def experiment_finished(self):
        self.timer.stop()
        self.timer.disconnect(self.request_nanonis_update)

        self.status["experiment"] = "idle"
        self.gui.buttons["start_pause"].setIcon(self.icons.get("start"))
        self.gui.progress_bar.setValue(0)
        self.logprint(f"Experiment {self.experiment} finished.", message_type = "success")
        if hasattr(self, "thread") and self.thread.isRunning():
            try:
                self.thread.quit()
            except Exception:
                pass

        return

    def modulator_control(self, modulator_number: int = 1) -> None:
        try:
            mod1_on = self.gui.buttons["nanonis_mod1"].isChecked()
            mod2_on = self.gui.buttons["nanonis_mod2"].isChecked()
            self.gui.buttons["nanonis_mod1"].setStyleSheet(style_sheets["running"] if mod1_on else style_sheets["neutral"])
            self.gui.buttons["nanonis_mod2"].setStyleSheet(style_sheets["running"] if mod2_on else style_sheets["neutral"])

            self.nanonis.lockin_update({"modulator_1": {"on": mod1_on}, "modulator_2": {"on": mod2_on}})
            
        except Exception as e:
            self.logprint(f"Error controlling modulator {modulator_number}: {e}", message_type = "error")
        
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
        self.gui.progress_bar.setValue(0)
        self.experiment_status = "running"
        [box.setEnabled(False) for box in [self.experiment_box, self.direction_box]]

        # self.channels = ["t (s)", "V (V)", "x (m)", "y (m)", "z (m)", "I (A)"]
        # self.data_array = np.empty((100000, len(self.channels)), dtype = float)
        self.current_index = 0
        
        self.nanonis.scan_control(action = "start", direction = dirxn)

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



# Main program
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    logic_app = Scantelligent()
    sys.exit(app.exec())
