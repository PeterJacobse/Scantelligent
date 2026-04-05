import os, sys, html, pint, atexit, importlib
from PIL import Image
import numpy as np
from PyQt6 import QtWidgets, QtGui, QtCore
import pyqtgraph as pg
from lib import STWidgets, ScantelligentGUI
from lib import DataProcessing, UserData, FileFunctions, ParameterManager
from lib import NanonisAPI, KeithleyAPI, CameraAPI, MLAAPI
from datetime import datetime



# Main class
class Scantelligent(QtCore.QObject):
    abort = QtCore.pyqtSignal()
    parameter_dict = QtCore.pyqtSignal(dict)
    image_request = QtCore.pyqtSignal(int, bool)

    def __init__(self):
        super().__init__()
        self.parameters_init()
        self.gui = ScantelligentGUI()
        self.connect_console() # Initialize the console, the button-slot, and keystroke-slot connections
        self.connect_buttons()
    
        self.connect_hardware() # Test and set up all connections, and request parameters from the hardware components
        self.gui.show()
        self.toggle_view("none")



    def parameters_init(self) -> None:
        # Cleanup
        atexit.register(self.cleanup)
        
        # Paths
        self.paths = {
            "script": os.path.abspath(__file__), # The full path of Scanalyzer.py
            "parent_folder": os.path.dirname(os.path.abspath(__file__)),            
        }
        self.paths["lib"] = os.path.join(self.paths["parent_folder"], "lib")
        self.paths["sys"] = os.path.join(self.paths["parent_folder"], "sys")
        self.paths["config_file"] = os.path.join(self.paths["sys"], "config.yml")
        self.paths["parameters_file"] = os.path.join(self.paths["sys"], "user_parameters.yml")
        self.paths["icon_folder"] = os.path.join(self.paths["parent_folder"], "icons")
        self.paths["experiments_folder"] = os.path.join(self.paths["parent_folder"], "experiments")

        # Icons
        icon_files = os.listdir(self.paths["icon_folder"])
        self.icons = {}
        for icon_file in icon_files:
            [icon_name, extension] = os.path.splitext(os.path.basename(icon_file))
            try:
                if extension == ".png": self.icons.update({icon_name: QtGui.QIcon(os.path.join(self.paths["icon_folder"], icon_file))})
            except:
                pass

        # Important classes and objects
        self.ureg = pint.UnitRegistry()
        self.user = UserData()
        self.file_functions = FileFunctions()
        self.data = DataProcessing() # Class for data processing and analysis
        self.timer = QtCore.QTimer()
        self.lines = [] # Lines for plotting in the graph
        self.splash_screen = np.flipud(np.array(Image.open(os.path.join(self.paths["sys"], "splash_screen.png"))))
        self.parameters = ParameterManager(parent = self) # Intantiate the ParameterManger, which implements easy parameter getting, setting, loading and saving
        
        # Dict to keep track of the hardware and experiment status
        self.status = {
            "initialization": True,
            "nanonis": "offline",
            "mla": "offline",
            "camera": "offline",
            "keithley": "offline",
            "tip": {"withdrawn": True, "feedback": False},
            "experiment": {"name": None, "status": "idle"},
            "view": "none"
        }
        
        return

    def connect_console(self) -> None:
        # Redirect output to the console
        self.stdout_redirector = STWidgets.StreamRedirector()
        self.stdout_redirector.output_written.connect(lambda text: self.gui.consoles["output"].append(text))
        sys.stdout = self.stdout_redirector
        #sys.stderr = self.stdout_redirector
        now = datetime.now()
        self.logprint(now.strftime("Opening Scantelligent on %Y-%m-%d %H:%M:%S"), message_type = "message")

        return
    
    def connect_buttons(self) -> None:
        buttons = self.gui.buttons
        shortcuts = self.gui.shortcuts        
        
        # Connect the buttons to their respective functions
        connections = [["scanalyzer", self.launch_scanalyzer], ["nanonis", lambda: self.dis_reconnect(target = "nanonis")], ["mla", lambda: self.dis_reconnect(target = "mla")], ["camera", self.connect_hardware], ["exit", self.exit],
                    ["view", self.toggle_view], ["session_folder", self.open_session_folder], ["info", self.gui.info_box.exec],
                    
                    # Experiment
                    ["start_pause", lambda checked: self.control_experiment(action = "start_pause")], ["stop", lambda checked: self.control_experiment(action = "stop")],
                    
                    # Coarse motion
                    ["withdraw", self.toggle_withdraw], ["retract", lambda: self.on_coarse_move("up")], ["advance", lambda: self.on_coarse_move("down")], ["approach", self.on_approach],

                    # Parameters                    
                    ["tip", self.change_tip_status],

                    # Tip prep
                    ["bias_pulse", lambda: self.tip_prep("pulse")], ["tip_shape", lambda: self.tip_prep("shape")],
                    
                    # Processing
                    ["fit_to_frame", lambda: self.set_view_range("frame")], ["fit_to_range", lambda: self.set_view_range("piezo_range")],
                    ["bg_none", self.update_processing_flags], ["bg_plane", self.update_processing_flags], ["bg_linewise", self.update_processing_flags]
                    ]

        [connections.append([f"get_{parameter_type}_parameters", lambda checked, param_type = parameter_type: self.parameters.get(f"{param_type}")]) for parameter_type in ["frame", "grid", "gain", "lockin"]]
        [connections.append([f"set_{parameter_type}_parameters", lambda checked, param_type = parameter_type: self.parameters.set(f"{param_type}")]) for parameter_type in ["frame", "grid", "gain", "lockin"]]

        connections.append([f"scan_parameters_0", lambda: self.load_parameters_from_file("scan_parameters", 0)])
        connections.append([f"scan_parameters_1", lambda: self.load_parameters_from_file("scan_parameters", 1)])
        connections.append([f"scan_parameters_2", lambda: self.load_parameters_from_file("scan_parameters", 2)])
        connections.append([f"scan_parameters_3", lambda: self.load_parameters_from_file("scan_parameters", 3)])

        for connection in connections:
            name = connection[0]
            connected_function = connection[1]
            buttons[name].clicked.connect(connected_function)
            
            if name in shortcuts.keys():
                shortcut = QtGui.QShortcut(shortcuts[name], self.gui)
                shortcut.activated.connect(connected_function)
        
        # for direction in ["n", "ne", "e", "se", "s", "sw", "w", "nw"]:
        [buttons[direction].clicked.connect(lambda checked, drxn = direction: self.on_coarse_move(drxn)) for direction in ["n", "ne", "e", "se", "s", "sw", "w", "nw"]]
        # buttons["n"].clicked.connect(lambda: self.on_coarse_move("n"))
        # buttons["ne"].clicked.connect(lambda: self.on_coarse_move("ne"))
        # buttons["e"].clicked.connect(lambda: self.on_coarse_move("e"))
        # buttons["se"].clicked.connect(lambda: self.on_coarse_move("se"))
        # buttons["s"].clicked.connect(lambda: self.on_coarse_move("s"))
        # buttons["sw"].clicked.connect(lambda: self.on_coarse_move("sw"))
        # buttons["w"].clicked.connect(lambda: self.on_coarse_move("w"))
        # buttons["nw"].clicked.connect(lambda: self.on_coarse_move("nw"))

        # Line edits
        self.gui.line_edits["input"].editingFinished.connect(self.execute_command)
        
        # Comboboxes
        self.gui.comboboxes["channels"].currentIndexChanged.connect(self.update_processing_flags)
        self.experiments = self.file_functions.find_experiment_files(self.paths["experiments_folder"])
        self.gui.comboboxes["experiment"].addItems(self.experiments)
        self.gui.comboboxes["experiment"].currentIndexChanged.connect(self.change_experiment)
        
        # Checkboxes and radio buttons
        [self.gui.radio_buttons[name].clicked.connect(self.update_processing_flags) for name in ["min_absolute", "min_deviations", "min_percentiles", "min_full", "max_absolute", "max_deviations", "max_percentiles", "max_full"]]

        return

    def connect_hardware(self, target: str = "all") -> None:
        """
        Set up and test hardware connections, and request parameters from the hardware components
        """

        self.logprint(f"Attempting to connect to the following hardware: {target}", message_type = "message")

        # Read hardware configurations from file
        (hw_config, error) = self.file_functions.load_yaml(self.paths.get("config_file"))
        if error:
            self.logprint("Problem loading the hardware configurations from file", message_type = "error")
            return
        self.hw_config = hw_config

        # MLA (library)
        mla_config = hw_config.get("mla")
        if isinstance(mla_config, dict):
            mla_path = mla_config.get("library_path")
            if os.path.isdir(mla_path):
                self.paths.update({"mla": mla_path})
                sys.path.insert(0, self.paths.get("mla"))



        # Scanalyzer
        if target.lower() == "scanalyzer" or target.lower() == "all":
            scanalyzer_path = hw_config.get("scanalyzer_path")
            if os.path.isfile(scanalyzer_path):
                self.paths.update({"scanalyzer": scanalyzer_path})
                self.logprint("Scanalyzer found and linked", message_type = "success")
                self.gui.buttons["scanalyzer"].setState("online")
            else:
                self.logprint("Warning: Scanalyzer path could not be read", message_type = "error")
                self.gui.buttons["scanalyzer"].setState("offline")

        # Keithley
        if target.lower() == "keithley" or target.lower() == "all":
            try:
                # Instantiate
                self.keithley = KeithleyAPI(hw_config = self.hw_config)
                
                # Set up signal-slot connections
                # Keithley -> Scantelligent
                self.keithley.parameters.connect(self.parameters.receive)
                
                # Get parameters from Keithley
                self.keithley.initialize()            
                self.logprint("Found the Keithley source meter and instantiated KeithleyAPI as keithley", "success")
                self.gui.buttons["keithley"].setState("online")
            except Exception as e:
                self.logprint(f"Unable to connect to the Keithley source meter: {e}", "warning")
                self.gui.buttons["keithley"].setState("offline")

        # Camera
        if target.lower() == "camera" or target.lower() == "all":
            try:
                # Instantiate
                self.camera = CameraAPI(hw_config = self.hw_config)
                
                # Set up signal-slot connections
                self.camera.parameters.connect(self.parameters.receive)
                
                # Initialize
                self.camera.initialize()
                self.logprint("Found the camera and instantiated CameraAPI as camera", "success")
                self.gui.buttons["camera"].setState("online")
            except Exception as e:
                self.logprint(f"Unable to connect to camera: {e}", "warning")
                self.gui.buttons["keithley"].setState("offline")

        # MLA
        if target.lower() == "mla" or target.lower() == "all":
            try:
                # Instantiate
                self.mla = MLAAPI(mla_path = mla_path).unwrap()

                self.logprint("Found the MLA", "success")
                self.status.update({"mla": "online"})
                self.gui.buttons["mla"].setState("online")
            except Exception as e:
                self.logprint(f"Unable to connect to the MLA: {e}", "warning")
                self.gui.buttons["mla"].setState("offline")

        # Nanonis
        if target.lower() == "nanonis" or target.lower() == "all":
            try:
                # Instantiate
                self.nanonis = NanonisAPI(parent = self, hw_config = self.hw_config)
                
                # Set up signal-slot connections
                # Scantelligent -> Nanonis
                self.gui.image_view.position_signal.connect(lambda x, y: self.nanonis.tip_update({"x (nm)": x, "y (nm)": y}, unlink = True))

                # Nanonis -> Scantelligent
                self.nanonis.progress.connect(self.receive_progress)
                self.nanonis.message.connect(self.receive_message)
                self.nanonis.parameters.connect(self.parameters.receive) # Parameter dictionaries are received in the ParameterManager class, instantiated as self.parameters
                self.nanonis.image.connect(self.receive_image)
                self.nanonis.data_array.connect(self.receive_data)
                
                # Get parameters from Nanonis
                self.nanonis.initialize()
                
                self.logprint(f"Successfully connected to Nanonis, and instantiated NanonisAPI as nanonis", "success")
                self.gui.buttons["nanonis"].setState("online")
            except Exception as e:
                self.logprint(f"Unable to connect to Nanonis: {e}", "error")
                self.gui.buttons["camera"].setState("offline")


        
        # Populate the autocomplete suggestions in the command input
        self.process = QtCore.QProcess(self.gui) # Instantiate process for CLI-style commands (opening folders and other programs)
        self.populate_completer()

        return

    def dis_reconnect(self, target: str = "nanonis") -> None:
        match target:
            case "nanonis":
                if self.status["nanonis"] == "running":
                    try: self.nanonis.unlink()
                    except: pass
                elif self.status["nanonis"] == "idle" or self.status["nanonis"] == "online":
                    try: self.nanonis.link()
                    except: pass
                else:
                    self.connect_hardware()
                return
            
            case "mla":
                if self.status["mla"] == "running":
                    try:
                        self.mla.disconnect()
                        self.status.update({"mla": "idle"})
                        self.gui.buttons["mla"].setState("online")
                    except:
                        self.status.update({"mla": "offline"})
                        self.gui.buttons["mla"].setState("offline")
                elif self.status["mla"] == "idle" or self.status["mla"] == "online":
                    try:
                        self.mla.connect()
                        self.status.update({"mla": "running"})
                        self.gui.buttons["mla"].setState("running")
                    except:
                        pass
                else:
                    self.connect_hardware()
                return

            
            case _:
                pass
        
        return



    # PyQt slots
    @QtCore.pyqtSlot(int)
    def receive_progress(self, progress: int) -> None:
        self.gui.progress_bars["experiment"].setValue(progress)
        return

    @QtCore.pyqtSlot(str, str)
    def receive_message(self, text: str, mtype: str) -> None:
        self.logprint(text, message_type = mtype)
        return

    @QtCore.pyqtSlot(np.ndarray)
    def receive_image(self, image: np.ndarray) -> None:
        if self.status["view"] == "none": return

        try:
            """
            view_box = self.gui.image_view.getView()
            for item in view_box.allChildItems():
                if isinstance(item, (pg.ROI, pg.TargetItem)): view_box.removeItem(item)
            """
            
            if self.status["view"] == "nanonis":
                self.gui.image_view.setImage(np.fliplr(np.flipud(image)).T, autoRange = False)

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
            
            if self.status["view"] == "camera":

                self.gui.image_view.setImage(np.flipud(image), autoRange = False)

                image_item = self.gui.image_view.getImageItem()
                identity_transform = QtGui.QTransform()
                image_item.setTransform(identity_transform)
                
                view_box = self.gui.image_view.getView()
                view_box.autoRange()

        except Exception as e:
            self.logprint(f"Error: {e}", "error")
            
        return

    @QtCore.pyqtSlot(np.ndarray)
    def receive_data(self, data_array: np.ndarray, max_length: int = 1000) -> None:

        for index in range(min(len(data_array[0]), 20)):            
            new_data = data_array[:, index]
            
            plot_data_item = self.gui.graphs[index]
            old_data = plot_data_item.getData()[1]
            
            if isinstance(old_data, np.ndarray):
                total_length = len(old_data) + len(new_data)
                if total_length < max_length:
                    data = np.concatenate([old_data, new_data])
                else:
                    crop_length = total_length - max_length
                    data = np.concatenate([old_data[crop_length:], new_data])
            else: data = new_data
            
            if self.gui.channel_checkboxes[f"{index}"].isChecked(): plot_data_item.setAlpha(1, False)
            else: plot_data_item.setAlpha(0, False)
            plot_data_item.setData(data)

        return



    # Miscellaneous
    def logprint(self, message: str = "", message_type: str = "error", timestamp: bool = True) -> None:
        """Print a (timestamped) message to the redirected stdout.

        Parameters:
        - message: text to print
        - timestamp: whether to prepend HH:MM:SS timestamp
        - type: type of message. The style of the message will be selected according to its type
        """
        colors = self.gui.colors
        text_colors = {"message": colors["white"], "error": colors["red"], "code": colors["blue"], "result": colors["light_blue"], "success": colors["green"], "warning": colors["orange"]}

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

    def populate_completer(self) -> None:
        # Populate the command input completer with all attributes and methods of self and self.gui
        self.all_attributes = dir(self)
        gui_attributes = ["gui." + attr for attr in self.gui.__dict__ if not attr.startswith('__')]
        
        nanonis_attributes = []
        nanonis_hw_attributes = []
        keithley_attributes = []
        camera_attributes = []
        mla_attributes = []
        mla_analog_attributes = []
        mla_osc_attributes = []
        mla_lockin_attributes = []
        user_attributes = []
        parameters_attributes = []

        if hasattr(self, "nanonis"):
            nanonis_attributes = ["nanonis." + attr for attr in self.nanonis.__dict__ if not attr.startswith("_")]
            try:
                nanonis_hw_attributes = ["nanonis.nanonis_hardware." + attr for attr in self.nanonis.nanonis_hardware.__dict__ if not attr.startswith("_")]
            except:
                pass
        if hasattr(self, "mla"):
            mla_attributes = ["mla." + attr for attr in self.mla.__dict__ if not attr.startswith("_")]
            try:
                mla_lockin_attributes = ["mla.lockin." + attr for attr in self.mla.lockin.__dict__ if not attr.startswith("_")]
                mla_osc_attributes = ["mla.osc." + attr for attr in self.mla.osc.__dict__ if not attr.startswith("_")]
                mla_analog_attributes = ["mla.analog." + attr for attr in self.mla.analog.__dict__ if not attr.startswith("_")]
            except:
                pass
        if hasattr(self, "parameters"): parameters_attributes = ["parameters." + attr for attr in self.parameters.__dict__ if not attr.startswith("_")]
        if hasattr(self, "user"): user_attributes = ["user." + attr for attr in self.user.__dict__ if not attr.startswith("_")]
        if hasattr(self, "data"): data_attributes = ["data." + attr for attr in self.data.__dict__ if not attr.startswith("_")]
        if hasattr(self, "file_functions"): file_function_attributes = ["file_functions." + attr for attr in self.file_functions.__dict__ if not attr.startswith("_")]
        if hasattr(self, "keithley"): keithley_attributes = ["keithley." + attr for attr in self.keithley.__dict__ if not attr.startswith("_")]
        if hasattr(self, "camera"): camera_attributes = ["camera." + attr for attr in self.keithley.__dict__ if not attr.startswith("_")]
        
        [self.all_attributes.extend(attributes) for attributes in [gui_attributes, nanonis_attributes, nanonis_hw_attributes, data_attributes, file_function_attributes, parameters_attributes, user_attributes, mla_analog_attributes, mla_lockin_attributes, mla_osc_attributes, mla_attributes, keithley_attributes, camera_attributes]]
        completer = STWidgets.Completer(self.all_attributes, self.gui)
        completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(STWidgets.Completer.CompletionMode.PopupCompletion)
        self.gui.line_edits["input"].setCompleter(completer)
        return

    def set_view_range(self, obj: str) -> None:
        imv = self.gui.image_view
        
        match obj:

            case "frame":
                roi_rect = self.gui.frame_roi.boundingRect()
                mapped_rect = self.gui.frame_roi.mapRectToParent(roi_rect)
                imv.view.setRange(mapped_rect)

            case "piezo_range":                
                imv.autoRange()

            case _:
                pass
        
        return

    def update_tip_status(self) -> None:
        style_sheets = self.gui.style_sheets
        buttons = self.gui.buttons
        tip_button = buttons["tip"]
        
        if self.status["nanonis"] in ["idle", "running"]:
            if self.status["tip"].get("withdrawn"):
                tip_button.changeToolTip("Tip withdrawn; click to land")
                tip_button.setIcon(self.icons.get("withdrawn"))
                tip_button.setStyleSheet(style_sheets["idle"])
                buttons["withdraw"].setIcon(self.icons.get("approach"))
                buttons["withdraw"].changeToolTip("Land")

            else:
                tip_button.setIcon(self.icons.get("contact"))
                buttons["withdraw"].setIcon(self.icons.get("withdraw"))
                buttons["withdraw"].changeToolTip("Withdraw")
            
                if self.status["tip"].get("feedback"):
                    tip_button.changeToolTip("Tip in feedback; click to toggle feedback off")
                    tip_button.setStyleSheet(style_sheets["connected"])                
                else:
                    tip_button.changeToolTip("Tip in constant height: click to toggle feedback on")
                    tip_button.setStyleSheet(style_sheets["hold"])
        
        return

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

    def toggle_view(self, view: str = None):
        new_view = "none"
        
        self.logprint(f"The current view is {self.gui.buttons["view"].state_name}")
        if 3 == 3: return
        
        # Determine the new view mode
        if isinstance(view, str) and view in ["nanonis", "camera", "none"]:
            new_view = view
        else:
            match self.status["view"]:
                # Set to Camera
                case "none": new_view = "camera"
                case "camera": new_view = "nanonis"
                case "nanonis": new_view = "none"
                case _: pass

        # Clean up old processes and the imageview
        if hasattr(self, "camera_thread"):
            try: self.camera_thread.requestInterruption()
            except: pass

        view_box = self.gui.image_view.getView()
        for item in view_box.allChildItems():
            if isinstance(item, (pg.ROI, pg.TargetItem)): view_box.removeItem(item)

        if new_view == "nanonis" and not hasattr(self, "nanonis"): new_view = "none"



        match new_view:
            case "camera":
                self.status.update({"view": "camera"})
                self.gui.buttons["view"].setState("camera")

                image_item = self.gui.image_view.getImageItem()
                image_item.setImage(np.zeros((2, 2)))
                image_item.setRotation(0)
                image_item.setPos(0, 0)

                try:
                    # Instantiate
                    self.camera = CameraAPI({"argument": "rtsp://admin:CT108743@192.168.236.108"})
                    self.camera_thread = QtCore.QThread()
                    self.camera.moveToThread(self.camera_thread)
                    
                    # Set up signal-slot connections
                    # Camera -> Scantelligent
                    self.camera.frame_captured.connect(self.receive_image)
                    self.camera.message.connect(self.receive_message)
                    self.camera.finished.connect(self.camera_thread.quit)
                    
                    self.camera_thread.started.connect(self.camera.run)
                    self.camera_thread.finished.connect(self.camera_thread.deleteLater)                    
                    self.camera_thread.destroyed.connect(self.camera_finished)
                    
                    self.camera_thread.start()
                except:
                    pass

            case "nanonis":
                self.status.update({"view": "nanonis"})
                self.gui.buttons["view"].setIcon(self.icons.get("view_nanonis"))

                image_item = self.gui.image_view.getImageItem()
                image_item.setImage(np.zeros((2, 2)))
                
                [self.gui.image_view.addItem(roi) for roi in [self.gui.new_frame_roi, self.gui.frame_roi, self.gui.piezo_roi]]
                self.gui.image_view.addItem(self.gui.tip_target)
                self.nanonis.piezo_range_update()
                self.nanonis.frame_update(unlink = True)
                self.set_view_range("frame")

            case _:
                self.status.update({"view": "none"})
                self.gui.buttons["view"].setIcon(self.icons.get("eye"))
                
                image_item = self.gui.image_view.getImageItem()
                image_item.setImage(self.splash_screen)                
                image_item.setRotation(0)
                image_item.setPos(0, 0)
                
                view_box.autoRange()

        return

    def camera_finished(self):
        self.camera.message.disconnect()
        self.camera.frame_captured.disconnect()
        self.camera.finished.disconnect()

        delattr(self, "camera_thread")
        delattr(self, "camera")
        return

    def launch_scanalyzer(self) -> None:
        if "scanalyzer_path" in list(self.paths.keys()):
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
        if "session_path" in list(self.paths.keys()):
            try:
                session_path = self.paths["session_path"]
                self.logprint("Opening the session folder", message_type = "message")
                os.startfile(session_path)
                self.gui.buttons["session_folder"].setState("connected")
            except Exception as e:
                self.logprint(f"Failed to open session folder: {e}", message_type = "error")
                self.gui.buttons["session_folder"].setState("disconnected")
        else:
            self.logprint("Error. Session folder unknown.", message_type = "error")
            self.gui.buttons["session_folder"].setState("disconnected")
        return

    def cleanup(self) -> None:
        self.user.save_parameter_sets()
        try:
            self.nanonis.unlink()
            self.nanonis.disconnect()
        except: pass
        try:
            self.experiment.disconnect()
            self.experiment.deleteLater()
        except: pass
        try:
            self.mla.disconnect()
        except: pass
        try:
            if hasattr(self, "nanonis"): delattr(self, "nanonis")
        except: pass
        try:
            if hasattr(self, "experiment"): delattr(self, "experiment")
        except: pass
        try:
            if hasattr(self, "experiment_thread"): delattr(self, "experiment_thread")
        except: pass
        return

    def exit(self) -> None:
        self.cleanup()
        self.logprint("Thank you for using Scantelligent!", message_type = "success")
        QtWidgets.QApplication.instance().quit()

    def closeEvent(self, event) -> None:
        self.exit()



    # Getting, setting, loading parameters. To be deprecated after completion of the ParameterManager class
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

    def update_processing_flags(self) -> None:
        flags = {"dict_name": "processing_flags"}
        
        checkboxes = self.gui.checkboxes
        buttons = self.gui.buttons
        comboboxes = self.gui.comboboxes
        radio_buttons = self.gui.radio_buttons
        line_edits = self.gui.line_edits

        # Background
        bg_methods = ["none", "plane", "linewise"]
        for method in bg_methods:
            if buttons[f"bg_{method}"].state_index == 1: flags.update({"background": f"{method}"})
        
        if buttons["rot_trans"].state_index == 1: flags.update({"rotation": True, "offset": True})
        else: flags.update({"rotation": False, "offset": False})
        
        # Limits
        lim_methods = ["full", "percentiles", "deviations", "absolute"]
        for method in lim_methods:
            if radio_buttons[f"min_{method}"].isChecked():
                min_value = 0
                try:
                    min_str = line_edits[f"min_{method}"].text()
                    numbers = self.data.extract_numbers_from_str(min_str)
                    if len(numbers) > 0: min_value = numbers[0]
                except:
                    pass
                flags.update({"min_method": f"{method}", "min_method_value": f"{min_value}"})
            if radio_buttons[f"max_{method}"].isChecked():
                max_value = 1
                try:
                    max_str = line_edits[f"max_{method}"].text()
                    numbers = self.data.extract_numbers_from_str(max_str)
                    if len(numbers) > 0: max_value = numbers[0]
                    else: max_value = 0
                except: pass
                flags.update({"max_method": f"{method}", "max_method_value": f"{max_value}"})

        # Channel, direction, projection
        try:
            channel = comboboxes["channels"].currentText()
            direction = "backward" if bool(buttons["direction"].state_index) else "forward"
            projection = comboboxes["projection"].currentText()
            flags.update({"channel": channel, "direction": direction, "projection": projection})
        except:
            print("Error updating the image processing flags.")
        
        # Operations
        try: [flags.update({operation: checkboxes[operation].isChecked()}) for operation in ["sobel", "normal", "laplace", "gaussian", "fft"]]
        except: pass
        phase = self.gui.phase_slider.getValue()
        flags.update({"phase": phase})

        self.data.processing_flags.update(flags)
        return



    # Nanonis functions 
    # Simple data requests over TCP-IP
    def tip_prep(self, action: str):
        if not hasattr(self, "nanonis"): return
        
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



    # Simple Nanonis functions; typically return either True if successful or an old parameter value when it is changed
    def toggle_withdraw(self) -> bool:
        if not hasattr(self, "nanonis"): return
        
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

        self.update_tip_status()

        return True

    def change_tip_status(self) -> bool:
        if not hasattr(self, "nanonis"): return
        
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

        self.update_tip_status()

        return True

    def on_coarse_move(self, direction: str = "n") -> bool:
        if not hasattr(self, "nanonis"): return
        
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
            advance = checkboxes["advance"].isChecked()
            approach = checkboxes["approach"].isChecked()
            composite = checkboxes["composite_motion"].isChecked()

            # Retrieve the line_edit values
            [V_hor, V_ver, f_motor] = [line_edits[name].getValue() for name in ["V_hor", "V_ver", "f_motor"]] # Frequency and amplitude
            [z_steps, h_steps, minus_z_steps] = [line_edits[name].getValue() for name in ["z_steps", "h_steps", "minus_z_steps"]] # Steps
            """
            numbers = self.data.extract_numbers_from_str(line_edits["V_hor"].text())
            if len(numbers) > 0: V_hor = float(numbers[0])
            else: V_hor = None
            numbers = self.data.extract_numbers_from_str(line_edits["V_ver"].text())
            if len(numbers) > 0: V_ver = float(numbers[0])
            else: V_ver = None
            numbers = self.data.extract_numbers_from_str(line_edits["f_motor"].text())
            if len(numbers) > 0: f_motor = float(numbers[0])
            else: f_motor = None
            
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
            """

            # Toggle the view feed
            if not self.status["view"] == "camera": self.toggle_view("camera")

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
                    if not composite: # Disable the vertical motions if a horizontal motion is requested but 'composite' is unchecked
                        approach = False
                        retract = False
                        advance = False
                    pass



            # Horizontal (composite) motion
            motions = {
                "withdraw": withdraw,
                "approach": approach,
                "V_hor (V)": V_hor,
                "V_ver (V)": V_ver,
                "f_motor (Hz)": f_motor
            }
            
            if retract and (z_steps > 0) and composite: motions.update({"z_steps": z_steps})
            if advance and (minus_z_steps > 0) and composite: motions.update({"minus_z_steps": minus_z_steps})
            if (h_steps > 0): motions.update({"h_steps": h_steps, "direction": direction})
            
            self.nanonis.coarse_move(motions, unlink = True)
            
            return True
        
        except Exception as e:
            self.logprint("Error. Unable to execute tip move.", message_type = "error")

            return False

    def on_approach(self) -> None:
        if not hasattr(self, "nanonis"): return
        
        numbers = self.data.extract_numbers_from_str(self.gui.line_edits["V_ver"].text())
        if len(numbers) > 0: V_ver = float(numbers[0])
        else: V_ver = None

        self.nanonis.auto_approach(True, V_motor = V_ver)
        return



    # Experiments and thread management
    def change_experiment(self) -> None:
        if hasattr(self, "experiment_thread"):
            if self.experiment_thread.isRunning(): return # Return if an experiment is active
            else: # Delete the experiment and experiment_thread if the experiment has stopped
                try:
                    delattr(self, "experiment")
                    delattr(self, "experiment_thread")
                except:
                    pass

        self.gui.buttons["start_pause"].setIcon(self.icons.get("start"))
        self.gui.progress_bars["experiment"].setValue(0)
        experiment_name = self.gui.comboboxes["experiment"].currentText()
        self.status["experiment"].update({"name": experiment_name})
        
        if "session_path" in self.paths.keys():
            self.paths.update({"experiment_filename": self.file_functions.get_next_indexed_filename(self.paths["session_path"], experiment_name, ".hdf5")})
            self.gui.line_edits["experiment_filename"].setText(self.paths["experiment_filename"])
        else:
            return
        
        file_path = os.path.join(self.paths["experiments_folder"], experiment_name + ".py")
        if not os.path.isfile(file_path):
            self.logprint("The selected experiment was not found", "error")
            return

        try:
            self.experiment = self.file_functions.load_experiment_from_file(file_path, parent = self)
            self.experiment_thread = QtCore.QThread()
            self.experiment.moveToThread(self.experiment_thread)
                        
            self.experiment_thread.started.connect(self.experiment.run)            
            self.experiment.finished.connect(self.experiment_thread.quit)
            self.experiment_thread.finished.connect(self.experiment.deleteLater)
            self.experiment_thread.finished.connect(self.experiment_thread.deleteLater)
            self.experiment_thread.finished.connect(self.change_experiment)
            
            self.experiment.progress.connect(self.receive_progress)
            self.experiment.message.connect(self.receive_message)
            self.experiment.parameters.connect(self.parameters.receive)
            self.experiment.image.connect(self.receive_image)
            self.experiment.data_array.connect(self.receive_data)            
            
        except Exception as e:
            self.logprint(f"Error loading the experiment: {e}", "error")
        
        return

    def control_experiment(self, action: str = "start_pause") -> None:
        sp_button = self.gui.buttons["start_pause"]
        
        match action:
            case "start_pause":
                if hasattr(self, "experiment_thread"):
                    if self.experiment_thread.isRunning(): return
                    else:
                        sp_button.setIcon(self.icons.get("pause"))
                        for i in range(20): self.gui.graphs[i].setData([])
                        self.experiment_thread.start()
                else:
                    self.logprint("No experiment loaded", "warning")
                    
            case "stop":
                sp_button.setIcon(self.icons.get("start"))
                if hasattr(self, "experiment_thread"):
                    if not self.experiment_thread.isRunning(): return
                    else:
                        self.experiment_thread.requestInterruption()
                else:
                    self.logprint("No experiment loaded", "warning")

            case _:
                pass

        return

    def modulator_control(self, modulator_number: int = 1) -> None:
        if not hasattr(self, "nanonis"): return
        
        style_sheets = self.gui.style_sheets
        
        try:
            mod1_on = self.gui.buttons["nanonis_mod1"].isChecked()
            mod2_on = self.gui.buttons["nanonis_mod2"].isChecked()

            self.nanonis.lockin_update({"modulator_1": {"on": mod1_on}, "modulator_2": {"on": mod2_on}})
            
        except Exception as e:
            self.logprint(f"Error controlling modulator {modulator_number}: {e}", message_type = "error")
        
        return



# Main program
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    logic_app = Scantelligent()
    sys.exit(app.exec())
