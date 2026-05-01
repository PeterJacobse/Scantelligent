import os, sys, html, atexit
from PIL import Image
import numpy as np
from PyQt6 import QtGui, QtCore
import pyqtgraph as pg
from lib import STWidgets, ScantelligentGUI
from lib import DataProcessing, FileFunctions, ParameterManager, UserData, AudioGenerator
from lib import NanonisAPI, KeithleyAPI, CameraAPI, MLAAPI
from datetime import datetime



# Main class
class Scantelligent(QtCore.QObject):
    volume = QtCore.pyqtSignal(int)
    amplitudes = QtCore.pyqtSignal(list)
    amplitude_volumes = QtCore.pyqtSignal(list)
    frequency = QtCore.pyqtSignal(float)

    def __init__(self):
        super().__init__()
        self.parameters_init()
        self.gui = ScantelligentGUI()
        self.gui.show()
        [self.toggle_view(view) for view in ["nanonis", "none"]]
        self.connect_console()
        self.connect_buttons()
        self.connect_hardware()



    def parameters_init(self) -> None:
        # Cleanup
        atexit.register(self.exit)

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
        self.user = UserData()
        self.file_functions = FileFunctions()
        self.data = DataProcessing() # Class for data processing and analysis
        self.lines = [] # Lines for plotting in the graph
        self.splash_screen = np.flipud(np.array(Image.open(os.path.join(self.paths["sys"], "splash_screen.png"))))
        self.parameters = ParameterManager(parent = self) # Intantiate the ParameterManger, which implements easy parameter getting, setting, loading and saving
        self.xy_mode = True # False means graphing parameters as a function of index, rolling when more than 1000 buffer values are filled. True means using the values of channel 0 as x values.

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
        button_slots = {"scanalyzer": self.launch_scanalyzer, "session_folder": self.open_session_folder, "view": self.toggle_view, "info": self.gui.info_box.exec, "exit": self.exit,
                        "tip": self.change_tip_status, "withdraw": self.toggle_withdraw, "retract": lambda: self.coarse_move("up"), "advance": lambda: self.coarse_move("down"), "approach": self.on_approach,
                        
                        "bias_pulse": lambda: self.tip_prep("pulse"), "tip_shape": lambda: self.tip_prep("shape"),
                        
                        "fit_to_frame": lambda: self.set_view_range("frame"), "fit_to_range": lambda: self.set_view_range("piezo_range"),
                        
                        "audio": self.toggle_audio, "start_stop": self.control_experiment
                        }
        
        [button_slots.update({hardware_component: lambda checked, hwc = hardware_component: self.dis_reconnect(target = hwc)}) for hardware_component in ["nanonis", "mla", "camera", "keithley"]]
        [button_slots.update({button_name: self.update_processing_flags}) for button_name in ["bg_none", "bg_plane", "bg_linewise", "sobel", "laplace", "fft", "normal", "gaussian", "direction"]]
        
        for parameter_type in ["bias", "feedback", "frame", "grid", "gain", "lockin", "speed", "tip_shaper", "spectroscopy"]:
            button_slots.update({f"get_{parameter_type}_parameters": lambda checked, param_type = parameter_type: self.parameters.get(f"{param_type}")})
            button_slots.update({f"set_{parameter_type}_parameters": lambda checked, param_type = parameter_type: self.parameters.set(f"{param_type}")})
        
        [button_slots.update({direction: lambda checked, drxn = direction: self.coarse_move(drxn)}) for direction in ["n", "ne", "e", "se", "s", "sw", "w", "nw"]]

        for button_name, connected_function in button_slots.items():
            self.gui.buttons[button_name].clicked.connect(connected_function)
            if button_name in self.gui.shortcuts.keys():
                shortcut = QtGui.QShortcut(self.gui.shortcuts[button_name], self.gui)
                shortcut.activated.connect(connected_function)

        # Line edits
        self.gui.line_edits["input"].editingFinished.connect(self.execute_command)
        [self.gui.line_edits[name].editingFinished.connect(self.update_processing_flags) for name in ["min_full", "min_percentiles", "min_deviations", "min_absolute", "max_full", "max_percentiles", "max_deviations", "max_absolute"]]
        
        # Comboboxes
        self.gui.comboboxes["channels"].currentIndexChanged.connect(self.update_processing_flags)
        self.experiments = self.file_functions.find_experiment_files(self.paths["experiments_folder"])
        self.gui.comboboxes["experiment"].addItems(self.experiments)
        self.gui.comboboxes["experiment"].currentIndexChanged.connect(lambda: self.gui.buttons["start_stop"].setState("load"))
                
        # Sliders
        self.gui.sliders["volume"].valueChanged.connect(self.send_amplitudes)
        [self.gui.sliders[f"f{i}"].valueChanged.connect(self.send_amplitudes) for i in range(32)]
        
        # Checkboxes
        for index in range(len(self.gui.pdis)): self.gui.checkboxes[f"channel_{index}"].clicked.connect(lambda checked, i = index: self.set_pdi_visible(i))
        for method in ["full", "percentiles", "deviations", "absolute"]:
            self.gui.checkboxes[f"min_{method}"].clicked.connect(self.update_processing_flags)
            self.gui.checkboxes[f"max_{method}"].clicked.connect(self.update_processing_flags)
        return

    def connect_hardware(self, target: str = "all") -> None:
        """
        Set up and test hardware connections, and request parameters from the hardware components
        """

        self.logprint(f"Attempting to connect to the following hardware: {target}", message_type = "message")

        # Read hardware configurations from file
        (hw_config, error) = self.file_functions.load_yaml(self.paths.get("config_file"))
        if error:
            self.logprint(".\\sys\\config.yml: Problem loading the hardware configurations from file", message_type = "error")
            return
        else:
            self.logprint(".\\sys\\config.yml: Loaded hardware configurations from file as (dict) hw_config", message_type = "success")
        self.hw_config = hw_config

        # MLA (library)
        mla_config = hw_config.get("mla")
        if isinstance(mla_config, dict):
            mla_path = mla_config.get("library_path")
            if os.path.isdir(mla_path):
                self.paths.update({"mla": mla_path})
                sys.path.insert(0, mla_path) # Path to the MLA library

        # Audio generator
        if target.lower() == "audio" or target.lower() == "all":
            try:
                # Instantiate
                self.audio = AudioGenerator()
                # self.audio_thread = QtCore.QThread()
                # self.audio.moveToThread(self.audio_thread)

                # Set up signal-slot connections
                self.volume.connect(self.audio.update_volume)
                self.amplitudes.connect(self.audio.update_amplitudes)
                self.amplitude_volumes.connect(self.audio.update_amplitude_volumes)
                self.frequency.connect(self.audio.update_frequency)
                                
                self.logprint(f"AudioGenerator: Successfully connected the audio generator, and instantiated AudioGenerator as audio", "success")
            except Exception as e:
                self.logprint(f"AudioGenerator: Unable to connect to the audio generator: {e}", "error")

        # Camera
        if target.lower() == "camera" or target.lower() == "all":
            try:
                # Instantiate
                self.camera = CameraAPI(hw_config = self.hw_config)
                
                # Set up signal-slot connections
                self.camera.parameters.connect(self.parameters.receive)
                
                # Initialize
                self.camera.initialize()
                self.camera_home_thread = self.camera.thread()
                self.logprint("Camera: Found the camera and instantiated CameraAPI as camera", "success")
                self.gui.buttons["camera"].setState("online")
            except Exception as e:
                self.logprint(f"Camera: Unable to connect to camera: {e}", "warning")
                self.gui.buttons["keithley"].setState("offline")



        # Scanalyzer
        if target.lower() == "scanalyzer" or target.lower() == "all":
            scanalyzer_path = hw_config.get("scanalyzer_path")
            if os.path.isfile(scanalyzer_path):
                self.paths.update({"scanalyzer": scanalyzer_path})
                self.logprint(f"Scanalyzer: Scanalyzer found at {self.paths["scanalyzer"]} and linked", message_type = "success")
                self.gui.buttons["scanalyzer"].setState("online")
            else:
                self.logprint("Scanalyzer: Scanalyzer path could not be read", message_type = "warning")
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
                self.logprint("Keithley: Found the Keithley source meter and instantiated KeithleyAPI as keithley", "success")
                self.gui.buttons["keithley"].setState("online")
            except Exception as e:
                self.logprint(f"Keithley: Unable to connect to the Keithley source meter: {e}", "warning")
                self.gui.buttons["keithley"].setState("offline")

        # MLA
        if target.lower() == "mla" or target.lower() == "all":
            try:
                # Instantiate
                self.mla = MLAAPI(hw_config = self.hw_config)
                
                # Set up signal-slot connections
                
                # MLA -> Scantelligent
                self.mla.message.connect(self.receive_message)
                self.mla.parameters.connect(self.parameters.receive) # Parameter dictionaries are received in the ParameterManager class, instantiated as self.parameters

                self.logprint("MLA: Found the MLA", "success")
                self.status.update({"mla": "online"})
                self.gui.buttons["mla"].setState("online")
            except Exception as e:
                self.logprint(f"MLA: Unable to connect to the MLA: {e}", "warning")
                self.gui.buttons["mla"].setState("offline")

        # Nanonis
        if target.lower() == "nanonis" or target.lower() == "all":
            try:
                # Instantiate
                self.nanonis = NanonisAPI(hw_config = self.hw_config, status_callback = self.gui.buttons["nanonis"].setState)
                
                # Set up signal-slot connections
                # Scantelligent -> Nanonis
                self.gui.image_view.position_signal.connect(lambda x, y: self.nanonis.tip_update({"x (nm)": x, "y (nm)": y}, wait = True, unlink = True))
                self.gui.image_view.position_signal_middle_button.connect(lambda x, y: self.parameters.set("grid"))

                # Nanonis -> Scantelligent
                self.nanonis.task_progress.connect(lambda val: self.gui.progress_bars["task"].setValue(val))
                self.nanonis.message.connect(self.receive_message)
                self.nanonis.parameters.connect(self.parameters.receive) # Parameter dictionaries are received in the ParameterManager class, instantiated as self.parameters
                self.nanonis.image.connect(self.receive_image)
                self.nanonis.data_array.connect(self.receive_data)
                
                # Get parameters from Nanonis
                (nanonis_parameters, _) = self.nanonis.nanonis_update()
                                
                self.logprint(f"Nanonis: Successfully connected to Nanonis, and instantiated NanonisAPI as nanonis", "success")
                self.gui.buttons["nanonis"].setState("online")
            except Exception as e:
                self.logprint(f"Nanonis: Unable to connect to Nanonis: {e}", "error")
                self.gui.buttons["nanonis"].setState("offline")
        

        
        # Populate the autocomplete suggestions in the command input
        self.process = QtCore.QProcess(self.gui) # Instantiate process for CLI-style commands (opening folders and other programs)
        self.populate_completer()
        return

    def dis_reconnect(self, target: str = "nanonis") -> None:
        match target:
            case "nanonis":
                if self.gui.buttons["nanonis"].state_name == "running":
                    try: self.nanonis.unlink(verbose = True)
                    except: pass
                elif self.gui.buttons["nanonis"].state_name == "idle" or self.gui.buttons["nanonis"].state_name == "online":
                    try: self.nanonis.link(verbose = True)
                    except: pass
                else:
                    self.connect_hardware(target = "nanonis")
                return
            
            case "mla":
                if self.status["mla"] == "running":
                    try:
                        self.mla.unlink()
                        self.status.update({"mla": "idle"})
                        self.gui.buttons["mla"].setState("online")
                    except:
                        self.status.update({"mla": "offline"})
                        self.gui.buttons["mla"].setState("offline")
                elif self.status["mla"] == "idle" or self.status["mla"] == "online":
                    try:
                        self.mla.link()
                        self.status.update({"mla": "running"})
                        self.gui.buttons["mla"].setState("running")
                    except:
                        pass
                else:
                    self.connect_hardware(target = "mla")
                return
            
            case _:
                pass
        
        return



    # PyQt slots
    @QtCore.pyqtSlot(str, str)
    def receive_message(self, text: str, mtype: str) -> None:
        self.logprint(text, message_type = mtype)
        return

    @QtCore.pyqtSlot(np.ndarray)
    def receive_image(self, image: np.ndarray) -> None:
        try:
            if self.gui.buttons["view"].state_name == "none": return
            if np.count_nonzero(~np.isnan(image)) < 10: return
            
            match self.gui.buttons["view"].state_name:
                case "nanonis":
                    flipped_image = np.fliplr(np.flipud(image)).T
                    (processed_scan, statistics, limits, error) = self.data.process_scan(flipped_image)
                    [self.gui.line_edits[f"{side}_full"].setValue(statistics[f"{side}"]) for side in ["min", "max"]]
                    
                    self.gui.image_view.setImage(processed_scan, autoRange = False)

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
                    
                    self.gui.hist_item.setLevels(limits[0], limits[1])
                
                case "camera":
                    self.gui.image_view.setImage(np.flipud(image), autoRange = False)

                    image_item = self.gui.image_view.getImageItem()
                    identity_transform = QtGui.QTransform()
                    image_item.setTransform(identity_transform)
                    
                    view_box = self.gui.image_view.getView()
                    view_box.autoRange()
                
                case _:
                    pass

        except Exception as e:
            pass
            
        return

    @QtCore.pyqtSlot(np.ndarray)
    def receive_data(self, data_array: np.ndarray, max_length: int = 1000) -> None:
        x_data = None

        for index in range(min(len(data_array[0]), 40)):            
            new_data = data_array[:, index]

            plot_data_item = self.gui.pdis[index]
            old_data = plot_data_item.getData()[1]
            
            if isinstance(old_data, np.ndarray):
                total_length = len(old_data) + len(new_data)
                if total_length < max_length:
                    data = np.concatenate([old_data, new_data])
                else:
                    crop_length = total_length - max_length
                    data = np.concatenate([old_data[crop_length:], new_data])
            else: data = new_data
            
            if index == 0: x_data = data # Set x_data to be the updated data from channel 0

            if bool(self.xy_mode):
                n_points = max(len(x_data), len(data))
                plot_data_item.setData(x = x_data[:n_points], y = data[:n_points])
            else:
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
        if hasattr(self, "camera"): camera_attributes = ["camera." + attr for attr in self.camera.__dict__ if not attr.startswith("_")]
        
        [self.all_attributes.extend(attributes) for attributes in [gui_attributes, nanonis_attributes, nanonis_hw_attributes, data_attributes, file_function_attributes, parameters_attributes, user_attributes, mla_analog_attributes, mla_lockin_attributes, mla_osc_attributes, mla_attributes, keithley_attributes, camera_attributes]]
        completer = STWidgets.Completer(self.all_attributes, self.gui)
        completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(STWidgets.Completer.CompletionMode.PopupCompletion)
        self.gui.line_edits["input"].setCompleter(completer)
        return

    def set_view_range(self, obj: str = "full") -> None:
        match obj:            
            case "frame":
                roi_rect = self.gui.frame_roi.boundingRect()
                mapped_rect = self.gui.frame_roi.mapRectToParent(roi_rect)
                self.gui.image_view.view.setRange(mapped_rect)
            case _:
                self.gui.image_view.view.autoRange(item = self.gui.piezo_roi)
        return

    def set_pdi_visible(self, index: int = 0) -> None:
        checked = bool(self.gui.checkboxes[f"channel_{index}"].state_index)
        self.gui.pdis[index].setVisible(checked)
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
        if self.gui.buttons["view"].state_name == view: return
        new_view = "none"
        
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
        if new_view == "camera": new_view = "nanonis"



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
                self.gui.buttons["view"].setState("nanonis")

                image_item = self.gui.image_view.getImageItem()
                image_item.setImage(np.zeros((2, 2)))
                
                [self.gui.image_view.addItem(roi) for roi in [self.gui.new_frame_roi, self.gui.frame_roi, self.gui.piezo_roi]]
                self.gui.image_view.addItem(self.gui.tip_target)
                self.nanonis.piezo_range_update()
                self.nanonis.frame_update(unlink = True)
                self.set_view_range("full")

            case _:
                self.status.update({"view": "none"})
                self.gui.buttons["view"].setState("none")
                
                image_item = self.gui.image_view.getImageItem()
                image_item.setImage(self.splash_screen)                
                image_item.setRotation(0)
                image_item.setPos(0, 0)
                
                view_box.autoRange()

        self.logprint(f"View set to {self.gui.buttons["view"].state_name}", message_type = "message")
        return

    def camera_finished(self):
        self.camera.message.disconnect()
        self.camera.frame_captured.disconnect()
        self.camera.finished.disconnect()

        delattr(self, "camera_thread")
        delattr(self, "camera")
        return

    def launch_scanalyzer(self) -> None:
        if "scanalyzer" in list(self.paths.keys()):
            try:
                scanalyzer_path = self.paths["scanalyzer"]
                self.logprint("Launching Scanalyzer:", message_type = "message")
                self.logprint(f"{sys.executable} {scanalyzer_path}", message_type = "code")
                self.process.start(sys.executable, [self.paths["scanalyzer"]])
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
                self.gui.buttons["session_folder"].setState("online")
            except Exception as e:
                self.logprint(f"Failed to open session folder: {e}", message_type = "error")
                self.gui.buttons["session_folder"].setState("offline")
        else:
            self.gui.buttons["session_folder"].setState("offline")
            
            # Open a file dialog to select a session folder
            try:
                folder_path = self.gui.dialogs["open_file"].getExistingDirectory(self.gui, "Select session folder")
                if isinstance(folder_path, str):
                    self.paths.update({"session_path": folder_path})
                    self.logprint(f"Session folder manually set to {self.paths["session_path"]}", message_type = "message")
                    self.gui.buttons["session_folder"].setState("online")
            except:
                pass
            
        return

    def cleanup(self) -> None:
        self.user.save_parameter_sets()
        try:
            self.nanonis.unlink()
        except: pass
        try:
            self.experiment.disconnect()
            self.experiment.deleteLater()
        except: pass
        try:
            self.mla.unlink()
        except: pass

        for attribute_name in ["nanonis", "mla", "experiment", "experiment_thread", "camera", "camera_thread"]:
            try: delattr(self, attribute_name)
            except: pass
        return

    def exit(self) -> None:
        self.cleanup()
        self.logprint("Thank you for using Scantelligent!", message_type = "success")
        STWidgets.Application.instance().quit()

    def closeEvent(self, event) -> None:
        self.exit()

    def toggle_audio(self) -> None:
        if not hasattr(self, "audio"): return

        if bool(self.gui.buttons["audio"].state_index):
            self.audio.start()
        else:
            self.audio.stop()
        return

    def send_amplitudes(self) -> None:
        volume = int(self.gui.sliders["volume"].getValue())
        amplitude_volumes = [self.gui.sliders[f"f{i}"].getValue() * volume / 10000 for i in range(1, 32)]
        self.volume.emit(volume)
        self.amplitude_volumes.emit(amplitude_volumes)        
        return



    # Read the GUI to set processing flags for image/spectrum processing
    def update_processing_flags(self) -> None:
        flags = {}
              
        checkboxes = self.gui.checkboxes
        buttons = self.gui.buttons
        comboboxes = self.gui.comboboxes
        line_edits = self.gui.line_edits

        # Background
        bg_methods = ["none", "plane", "linewise"]
        for method in bg_methods:
            if buttons[f"bg_{method}"].isChecked(): flags.update({"background": f"{method}"})

        if buttons["rot_trans"].isChecked(): flags.update({"rotation": True, "offset": True})
        else: flags.update({"rotation": False, "offset": False})
        
        # Limits
        lim_methods = ["full", "percentiles", "deviations", "absolute"]
        for method in lim_methods:
            if checkboxes[f"min_{method}"].isChecked():
                min_value = 0
                try:
                    min_str = line_edits[f"min_{method}"].text()
                    numbers = self.data.extract_numbers_from_str(min_str)
                    if len(numbers) > 0: min_value = numbers[0]
                except:
                    pass
                flags.update({"min_method": f"{method}", "min_method_value": f"{min_value}"})
            if checkboxes[f"max_{method}"].isChecked():
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
            selected_channel = comboboxes["channels"].currentText()
            (quantity, unit, backward, error) = self.file_functions.split_physical_quantity(selected_channel)
            if isinstance(unit, str): [line_edits[f"{side}_full"].setUnit(unit) for side in ["min", "max"]]
            
            backward = bool(buttons["direction"].state_index)
            projection = comboboxes["projection"].currentText()
            flags.update({"backward": backward, "projection": projection})
        except:
            print("Error updating the image processing flags.")

        # Operations
        try: [flags.update({operation: buttons[operation].isChecked()}) for operation in ["sobel", "normal", "laplace", "gaussian", "fft"]]
        except: pass
        phase = self.gui.sliders["phase"].getValue()
        flags.update({"phase (deg)": phase})

        channels = self.data.scan_processing_flags.get("channels")
        if channels:
            channel_index = channels.get(selected_channel, None)
            if isinstance(channel_index, int): flags.update({"channel": selected_channel, "channel_index": channel_index})
                
        self.data.scan_processing_flags.update(flags)
        return



    # Simple Nanonis functions; typically return either True if successful or an old parameter value when it is changed
    def tip_prep(self, action: str):
        if not hasattr(self, "nanonis"): return
        
        try:
            match action:
            
                case "pulse":
                    V_pulse_V = self.gui.line_edits["pulse_voltage"].getValue()
                    t_pulse_ms = self.gui.line_edits["pulse_duration"].getValue()
                    
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

    def toggle_withdraw(self) -> bool:
        if not hasattr(self, "nanonis"): return
        
        error = False

        try:
            tip_status = self.status["tip"]
            tip_withdrawn = tip_status.get("withdrawn")
            
            if tip_withdrawn:
                (tip_status, error) = self.nanonis.tip_update({"feedback": True}, unlink = True)
                if error: raise
            else:
                (tip_status, error) = self.nanonis.tip_update({"withdraw": True}, unlink = True)
                if error: raise

        except Exception as e:
            self.logprint(f"Error toggling the tip status: {e}", message_type = "error")

        return True

    def change_tip_status(self) -> bool:
        if not hasattr(self, "nanonis"): return
        
        try:
            tip_status = self.status["tip"]
            tip_withdrawn = tip_status.get("withdrawn")
            tip_in_feedback = tip_status.get("feedback")
            
            if tip_withdrawn: # Tip is withdrawn: land it
                (tip_status, error) = self.nanonis.tip_update({"feedback": True}, unlink = True)
                if error:
                    self.logprint(f"Error: {e}")
                elif type(tip_status) == dict:
                    self.status["tip"] = tip_status
                    self.logprint(f"nanonis.tip_update({{\"feedback\": True}})", message_type = "code")
            
            else: # Toggle the feedback                
                (tip_status, error) = self.nanonis.tip_update({"feedback": not tip_in_feedback}, unlink = True)
                if error:
                    self.logprint(f"Error. {e}")
                if type(tip_status) == dict:
                    self.status["tip"] = tip_status

        except Exception as e:
            self.logprint(f"Error toggling the tip status: {e}", message_type = "error")
            return False

        return True

    def coarse_move(self, direction: str = "n") -> bool:
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



    # Experiments
    def control_experiment(self) -> None:
        if not "session_path" in list(self.paths.keys()) or not os.path.isdir(self.paths["session_path"]):
            self.logprint(f"Error. No session folder loaded. Either select one manually or get it from a Nanonis connection", message_type = "error")
            return
        
        start_button = self.gui.buttons["start_stop"]
        
        match start_button.state_name:
            case "load": # Load the experiment
                experiment_name = self.gui.comboboxes["experiment"].currentText()
                experiment_path = os.path.join(self.paths["experiments_folder"], experiment_name + ".py")
                if not os.path.isfile(experiment_path):
                    self.logprint(f"The selected experiment was not found in {self.paths["experiments_folder"]}", "error")
                    return

                self.logprint(f"Loading/resetting experiment {experiment_name}", message_type = "message")
                [self.gui.progress_bars[name].setValue(0) for name in ["task", "experiment"]]
                [pdi.setData() for pdi in self.gui.pdis]
                self.gui.comboboxes["direction"].renewItems([])
                for i in range(9):
                    self.gui.line_edits[f"experiment_{i}"].setToolTip(f"Experiment parameter field {i}\ngui.line_edits[\"experiment_{i}\"]")
                    self.gui.line_edits[f"experiment_{i}"].setUnit()
                    self.gui.line_edits[f"experiment_{i}"].setValue("")
                    
                self.paths.update({"experiment_filename": self.file_functions.get_next_indexed_filename(self.paths["session_path"], experiment_name, ".hdf5")})
                self.gui.line_edits["experiment_filename"].setText(self.paths["experiment_filename"])
                
                try:
                    self.experiment = self.file_functions.load_experiment_from_file(experiment_path, parent = self, hw_config = self.hw_config)                    
                    self.experiment_thread = QtCore.QThread()
                    self.experiment.moveToThread(self.experiment_thread)
                    
                    # Worker-thread connections
                    self.experiment_thread.started.connect(self.experiment.run)
                    self.experiment.finished.connect(self.experiment_thread.quit)
                    self.experiment_thread.finished.connect(self.experiment.deleteLater)
                    self.experiment_thread.finished.connect(self.experiment_thread.deleteLater)
                    self.experiment_thread.finished.connect(lambda: start_button.setState("load"))
                    
                    # Progress
                    self.experiment.task_progress.connect(lambda val: self.gui.progress_bars["task"].setValue(val))
                    self.experiment.exp_progress.connect(lambda val: self.gui.progress_bars["experiment"].setValue(val))

                    # Other data
                    self.experiment.message.connect(self.receive_message)
                    self.experiment.parameters.connect(self.parameters.receive)
                    self.experiment.image.connect(self.receive_image)
                    self.experiment.data_array.connect(self.receive_data)
                
                except Exception as e:
                    self.logprint(f"Unable to load the experiment. {e}", message_type = "error")
                    return
                
                self.status["experiment"].update({"name": experiment_name})                
                start_button.setState("ready")
            
            case "ready":
                if not hasattr(self, "experiment") or not hasattr(self, "experiment_thread"):
                    self.logprint("Error. No experiment object or thread initialized", message_type = "error")
                    start_button.setState("load")
                    return
                
                start_button.setState("running")
                self.experiment_thread.start()
            
            case "running":
                start_button.setState("aborted")
                if hasattr(self, "experiment_thread"):
                    if not self.experiment_thread.isRunning(): return
                    else:
                        self.experiment_thread.requestInterruption()
            
            case _:
                pass
                
        return



# Main program
if __name__ == "__main__":
    app = STWidgets.Application(sys.argv)
    logic_app = Scantelligent()
    sys.exit(app.exec())
