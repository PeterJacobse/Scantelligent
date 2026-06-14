import os, sys, html, atexit, re, copy, time
from PIL import Image
import numpy as np
from PyQt6 import QtGui, QtCore, sip
from lib import Spectelligent, SCTWidgets, ScantelligentGUI
from lib import DataProcessing, FileFunctions, ParameterManager, UserData, AudioGenerator
from lib import NanonisAPI, KeithleyAPI, CameraAPI, MLAAPI
from datetime import datetime



# Main class
class Scantelligent(QtCore.QObject):
    volumes = QtCore.pyqtSignal(list)
    amplitudes = QtCore.pyqtSignal(list)
    frequencies = QtCore.pyqtSignal(list)

    def __init__(self):
        super().__init__()
        self.parameters_init()
        self.gui = ScantelligentGUI()
        self.gui.show()
        self.spt = Spectelligent(parent = self)
        self.connect_console()
        self.connect_buttons()
        self.connect_hardware()
        self.toggle_view("none")



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
        self.parameters = ParameterManager(parent = self) # Intantiate the ParameterManger, which implements easy parameter getting, setting, loading and saving
        self.focus_group = "connections"
        self.saved_items = []
                
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
        self.stdout_redirector = SCTWidgets.StreamRedirector()
        self.stdout_redirector.output_written.connect(lambda text: self.gui.consoles["output"].append(text))
        sys.stdout = self.stdout_redirector
        #sys.stderr = self.stdout_redirector
        now = datetime.now()
        self.logprint(now.strftime("Opening Scantelligent on %Y-%m-%d %H:%M:%S"), message_type = "message")
        return

    def connect_buttons(self) -> None:
        button_slots = {"scanalyzer": self.launch_scanalyzer, "session_folder": self.open_session_folder, "view": self.toggle_view, "info": self.gui.info_box.exec, "exit": self.exit,
                        "tip": self.change_tip_status, "retract": lambda: self.coarse_move("up"), "advance": lambda: self.coarse_move("down"),
                        "approach": self.start_auto_approach, "approach_2": self.start_auto_approach, "withdraw": self.toggle_withdraw, "withdraw_2": self.toggle_withdraw,
                        
                        "bias_pulse": lambda: self.tip_prep("pulse"), "tip_shape": lambda: self.tip_prep("shape"), "paste": self.save_active_item,
                        "rot_trans": self.rot_trans_changed, "fit_to_frame": lambda: self.set_view_range("frame"), "fit_to_range": lambda: self.set_view_range("piezo_range"),
                        "frame": self.toggle_items, "path": self.toggle_items, "grid": self.toggle_items, "set_dz": self.set_dz, "limits": self.toggle_limits_view,
                        
                        "start_stop": self.control_experiment, "start_scan": self.quick_scan, "spectelligent": self.open_spectelligent, "spectelligent_2": self.open_spectelligent}
        
        [button_slots.update({hardware_component: lambda checked, hwc = hardware_component: self.dis_reconnect(target = hwc)}) for hardware_component in ["nanonis", "mla", "camera", "keithley"]]
        [button_slots.update({button_name: self.update_processing_flags}) for button_name in ["reciprocal", "sobel", "laplace", "normal", "gaussian", "direction", "image_projection"]]
        
        for parameter_type in ["bias", "mla_bias", "keithley_bias", "feedback", "frame", "grid", "gain", "lockin", "speed", "tip_shaper", "spectroscopy"]:
            button_slots.update({f"get_{parameter_type}_parameters": lambda checked, param_type = parameter_type: self.parameters.get(f"{param_type}")})
            button_slots.update({f"set_{parameter_type}_parameters": lambda checked, param_type = parameter_type: self.parameters.set(f"{param_type}")})
        
        [button_slots.update({direction: lambda checked, drxn = direction: self.coarse_move(drxn)}) for direction in ["n", "ne", "e", "se", "s", "sw", "w", "nw"]]
        
        for button_name, connected_function in button_slots.items(): self.gui.buttons[button_name].clicked.connect(connected_function)

        # Line edits
        self.gui.line_edits["input"].editingFinished.connect(self.execute_command)
        self.gui.line_edits["graph_buffer_size"].editingFinished.connect(lambda buf_size = self.gui.line_edits["graph_buffer_size"].getValue(): self.gui.grapher.setBufferSize(buf_size))
        
        # Sliders
        self.gui.sliders["phase"].valueChanged.connect(self.update_processing_flags)
        
        # Comboboxes
        experiments = self.file_functions.find_experiment_files(self.paths["experiments_folder"])
        self.experiments = [experiment for experiment in experiments if not experiment in ["spectroscopy", "auto_approach"]]
        self.experiments.append("")
        self.gui.comboboxes["experiment"].addItems(self.experiments)
        self.gui.comboboxes["experiment"].currentIndexChanged.connect(lambda: self.gui.buttons["start_stop"].setState("load"))
        self.gui.comboboxes["graph_x_axis"].currentIndexChanged.connect(lambda cbb = self.gui.comboboxes["graph_x_axis"].currentIndex(): self.gui.grapher.setXAxis(cbb - 1))
        [self.gui.comboboxes[name].currentIndexChanged.connect(self.slice_axes_changed) for name in ["x_axis", "y_axis", "slice_0", "slice_1", "slice_2"]]
        self.gui.comboboxes["projection"].currentIndexChanged.connect(self.update_processing_flags)
        self.gui.comboboxes["items"].currentIndexChanged.connect(self.set_active_item)
        
        # Checkboxes and button groups
        self.gui.button_groups["background"].clicked.connect(self.update_processing_flags)
        self.gui.limits_widget.stateChanged.connect(self.update_processing_flags)
        self.gui.button_groups["channels"].clicked.connect(self.update_pdi_visibility)
        
        # ImageView
        self.gui.image_view.scan_file_signal.connect(self.open_file)
        self.gui.image_view.getHistogramWidget().item.sigLevelChangeFinished.connect(self.histogram_levels_changed)
        [self.gui.groupboxes[name].clicked.connect(lambda name0 = name: self.focus_on_groupbox(name0)) for name in self.gui.groupboxes.keys()]
        
        
        
        # Spectelligent
        sptgui = self.spt.gui
        sptgui.lockin_widget.get_button.clicked.connect(lambda: self.parameters.get("lockin"))
        sptgui.lockin_widget.set_button.clicked.connect(lambda: self.parameters.set("lockin"))
        sptgui.lockin_widget.set_button.clicked.connect(lambda: self.parameters.get("lockin"))
        sptgui.lockin_widget.set_button.clicked.connect(self.spt.gui.waveform_widget.updatePlots)
        sptgui.lockin_widget.get_button.clicked.connect(self.spt.gui.waveform_widget.updatePlots)
        
        sptgui.lockin_widget.audio_button.clicked.connect(self.toggle_audio)
        sptgui.buttons["start_spectroscopy"].clicked.connect(self.start_spectroscopy)
        sptgui.buttons["expose_dIdV"].clicked.connect(self.expose_dIdV)
        
        # Key presses
        self.gui.key_pressed.connect(self.keyPressEvent)
        return

    def connect_hardware(self, target: str = "all") -> None:
        self.process = QtCore.QProcess(self.gui) # Instantiate process for CLI-style commands (opening folders and other programs)
        self.populate_completer()
        
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

                # Set up signal-slot connections
                self.spt.gui.lockin_widget.volumes.connect(self.audio.volumes_update)
                self.amplitudes.connect(self.audio.amplitudes_update)
                self.frequencies.connect(self.audio.frequencies_update)
                
                # Add attributes to the input line edit
                new_attributes = ["audio." + attr for attr in self.audio.__dict__ if not attr.startswith("_")]
                completer = self.gui.line_edits["input"].completer()
                model = completer.model()
                string_list = model.stringList()
                [string_list.append(item) for item in new_attributes if item not in string_list]
                model.setStringList(string_list)
                completer.setModel(model)
                                
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
                self.camera.captured_frame.connect(self.receive_image)
                
                # Initialize
                self.camera.initialize()
                
                self.logprint("Camera: Found the camera and instantiated CameraAPI as camera", "success")
                self.gui.buttons["camera"].setState("online")
            except Exception as e:
                self.logprint(f"Camera: Unable to connect to camera: {e}", "warning")
                self.gui.buttons["camera"].setState("offline")
                self.camera = None
                delattr(self, "camera")



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
                self.mla.task_progress.connect(lambda val: self.gui.progress_bars["task"].setValue(val))
                self.mla.parameters.connect(self.parameters.receive) # Parameter dictionaries are received in the ParameterManager class, instantiated as self.parameters
                self.mla.message.connect(self.logprint)

                self.logprint("MLA: Found the MLA", "success")
                self.gui.buttons["mla"].setState("online")
            except Exception as e:
                self.logprint(f"MLA: Unable to connect to the MLA: {e}", "warning")
                self.mla = None
                delattr(self, "mla")



        # Nanonis
        if target.lower() == "nanonis" or target.lower() == "all":
            try:
                # Instantiate
                nanonis_config = self.hw_config.get("nanonis")
                nanonis_ports = nanonis_config.get("tcp_ports")
                
                nanonis_config0 = nanonis_config.copy()
                nanonis_config0.update({"tcp_port": nanonis_ports[0]})
                nanonis_config1 = nanonis_config.copy()
                nanonis_config1.update({"tcp_port": nanonis_ports[1]})
                
                # First port
                self.nanonis = NanonisAPI(hw_config = nanonis_config0)
                
                # Set up signal-slot connections
                # Scantelligent -> Nanonis
                self.gui.image_view.position_signal.connect(lambda x, y: self.nanonis.tip_update({"x (nm)": x, "y (nm)": y}, wait = True, unlink = True))
                self.gui.image_view.position_signal_middle_button.connect(lambda x, y: self.parameters.set("grid"))

                # Nanonis -> Scantelligent
                self.nanonis.task_progress.connect(lambda val: self.gui.progress_bars["task"].setValue(val))
                self.nanonis.parameters.connect(self.parameters.receive) # Parameter dictionaries are received in the ParameterManager class, instantiated as self.parameters
                self.nanonis.message.connect(self.logprint)
                self.nanonis.image.connect(self.receive_image)
                self.nanonis.data_array.connect(self.receive_data)
                
                # Get parameters from Nanonis
                (nanonis_parameters, _) = self.nanonis.initialize()
                
                
                
                # Second port
                self.nanonis1 = NanonisAPI(hw_config = nanonis_config1)
                
                # Set up signal-slot connections
                # Nanonis -> Scantelligent
                self.nanonis1.task_progress.connect(lambda val: self.gui.progress_bars["task"].setValue(val))
                self.nanonis1.parameters.connect(self.parameters.receive) # Parameter dictionaries are received in the ParameterManager class, instantiated as self.parameters
                self.nanonis1.message.connect(self.logprint)
                self.nanonis1.image.connect(self.receive_image)
                self.nanonis1.data_array.connect(self.receive_data)
                
                # Get parameters from Nanonis
                (nanonis_parameters1, _) = self.nanonis1.initialize(verbose = False)
                
                
                
                # Populate the input line edit completer
                nanonis_attributes = ["nanonis." + attr for attr in self.nanonis.__dict__ if not attr.startswith("_")]
                nanonis_hw_attributes = ["nanonis.nanonis_hardware." + attr for attr in self.nanonis.nanonis_hardware.__dict__ if not attr.startswith("_")]
                completer = self.gui.line_edits["input"].completer()
                model = completer.model()
                string_list = model.stringList()
                [string_list.append(item) for item in nanonis_attributes if item not in string_list]
                [string_list.append(item) for item in nanonis_hw_attributes if item not in string_list]
                model.setStringList(string_list)
                completer.setModel(model)
                                
                self.logprint(f"Nanonis: Successfully connected to Nanonis, and instantiated NanonisAPI as nanonis", "success")
                try: self.spt.get_fb_parameters()
                except: pass
            except Exception as e:
                self.logprint(f"Nanonis: Unable to connect to Nanonis: {e}", "error")
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
                if self.gui.buttons["mla"].state_name == "running":
                    try:
                        self.mla.unlink()
                        self.status.update({"mla": "idle"})
                    except:
                        self.status.update({"mla": "offline"})
                elif self.gui.buttons["mla"].state_name == "idle" or self.gui.buttons["mla"].state_name == "online":
                    try:
                        self.mla.link()
                        self.status.update({"mla": "running"})
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
        try: self.gui.camera_item.setImage(np.flipud(image), autoRange = False)
        except: pass
        return

    @QtCore.pyqtSlot(np.ndarray, list, list)
    def receive_array_slice(self, data_slice: np.ndarray, target_indices: list, axes: list) -> None:
        if not hasattr(self, "active_item") or self.gui.buttons["view"].state_name in ["none", "camera"]: return
        
        try:
            indexer = [slice(None)] * self.active_item.rank
            
            # Inject the insertion indices into the targeted axes
            for axis, idx in zip(axes, target_indices):
                indexer[axis] = idx
            self.active_item.array[tuple(indexer)] = data_slice
            
            image = self.active_item.getSlice()
            (processed_scan, statistics, limits, error) = self.data.process_scan(image)
            [self.gui.limits_widget.setValue("full", side, limits[index]) for index, side in enumerate(["min", "max"])]
            
            self.active_item.setImage(processed_scan)
            self.gui.hist_item.setLevels(limits[0], limits[1])
        except Exception as e:
            print(f"{e}")
        return

    @QtCore.pyqtSlot(np.ndarray)
    def receive_data(self, data: np.ndarray) -> None:
        data_array = np.atleast_2d(data).transpose()[:self.gui.grapher.n_channels] # Cast the data into a 2D np.ndarray, if it isn't in that form yet

        # Single elements can be used to signal the grapher
        if data_array.shape == (1, 1):
            if isinstance(data_array[0, 0], int) and data_array[0, 0] < self.gui.grapher.n_channels and data_array[0, 0] > -2:
                self.x_channel = data_array[0, 0]
                self.gui.grapher.setXAxis(data_array[0, 0])
                try: self.gui.comboboxes["graph_x_axis"].selectIndex(self.x_channel + 1)
                except: pass
            elif isinstance(data_array[0, 0], str) and data_array[0, 0] == "clear": # Magic word to clear the buffer
                self.gui.grapher.clearBuffer()
                [self.gui.checkboxes[f"channel_{channel_index}"].setToolTip(f"channel {channel_index}") for channel_index in range(self.gui.grapher.n_channels)]
                [self.gui.checkboxes[f"channel_{channel_index}"].setChecked(False) for channel_index in range(self.gui.grapher.n_channels)]
            self.update_pdi_visibility()
            self.gui.grapher.plotData()
            return
        
        # String and bool arrays can be passed to give information about channels and their checked state
        if data_array.dtype.kind in ["U", "S"]: # The data array provided contains strings. These are the channel names
            [self.gui.checkboxes[f"channel_{channel_index}"].setToolTip(f"channel {channel_index}: {value}") for channel_index, value in enumerate(data_array[:, 0])]
            [self.gui.checkboxes[f"channel_{channel_index}"].setChecked(True) for channel_index, value in enumerate(data_array[:, 0])]
            self.gui.comboboxes["graph_x_axis"].renewItems(np.insert(np.astype(data_array[:, 0], object), 0, "index"))
            try: self.gui.comboboxes["graph_x_axis"].selectIndex(self.x_channel + 1)
            except: pass
            self.update_pdi_visibility()
            self.gui.grapher.plotData()
            self.gui.grapher.setChannelNames(np.astype(data_array[:, 0], object))
            return
        elif data_array.dtype.kind == "b": # The data array has booleans. Check and uncheck according to the boolean values
            [self.gui.checkboxes[f"channel_{channel_index}"].setChecked(value) for channel_index, value in enumerate(data_array[:, 0])]
            self.gui.grapher.plotData()
            return

        
        
        # Numeric data is added to the buffer
        self.gui.grapher.addData(data_array)
        self.gui.grapher.plotData()
        return

    @QtCore.pyqtSlot(str)
    def receive_fileopen_request(self, file_path: str) -> None:
        if hasattr(self, "experiment_thread") and self.experiment_thread is not None:
            if not sip.isdeleted(self.experiment_thread):
                self.logprint(f"Cannot load files while an experiment is active", message_type = "error")
                return
        self.open_file(file_path)

    @QtCore.pyqtSlot(QtGui.QKeyEvent)
    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        buttons = self.gui.buttons
        line_edits = self.gui.line_edits
        QKey = QtCore.Qt.Key
        
        try:
            if event.modifiers() == QtCore.Qt.KeyboardModifier.ControlModifier:
                #if event.key() in [QKey.Key_T, QKey.Key_C, QKey.Key_E, QKey.Key_B, QKey.Key_S, QKey.Key_F, QKey.Key_G, QKey.Key_H, QKey.Key_V, QKey.Key_P, QKey.Key_M]:
                [groupbox.setFocused(False) for groupbox in self.gui.groupboxes.values()]
                
                match event.key():
                    case QKey.Key_T: target = "tip"
                    case QKey.Key_C: target = "connections"
                    case QKey.Key_E: target = "experiment"
                    case QKey.Key_B: target = "bias"
                    case QKey.Key_S: target = "speeds"
                    case QKey.Key_F: target = "feedback"
                    case QKey.Key_G: target = "frame_grid"
                    case QKey.Key_H: target = "horizontal"
                    case QKey.Key_V: target = "vertical"
                    case QKey.Key_P: target = "tip_prep"
                    case QKey.Key_M: target = "modulators"
                    case _: target = ""
                self.focus_on_groupbox(target)
            
            if event.modifiers() == QtCore.Qt.KeyboardModifier.ShiftModifier:
                return
            
            else:
                match (event.key(), self.focus_group):
                    case (QKey.Key_Plus | QKey.Key_Equal, _): self.gui.groupboxes[self.focus_group].maximize()
                    case (QKey.Key_Minus, _): self.gui.groupboxes[self.focus_group].minimize()
                    
                    case (QKey.Key_Escape, "connections"): self.exit()
                    case (QKey.Key_PageUp, "tip"):
                        if buttons["withdraw_2"].state_index == 0: buttons["withdraw_2"].click()
                    case (QKey.Key_PageUp, "vertical"):
                        if buttons["withdraw"].state_index == 0: buttons["withdraw"].click()
                    case (QKey.Key_PageUp, "experiment"): buttons["scan_direction"].click()
                    case (QKey.Key_PageDown, "tip"):
                        if buttons["withdraw_2"].state_index == 1: buttons["withdraw_2"].click()
                    case (QKey.Key_PageDown, "vertical"):
                        if buttons["withdraw"].state_index == 1: buttons["withdraw"].click()
                    case (QKey.Key_PageDown, "prep"): buttons["tip_shape"].click()
                    case (QKey.Key_PageDown, "experiment"): buttons["scan_direction"].click()
                    case (QKey.Key_Space, "tip"): buttons["tip"].click()
                    case (QKey.Key_Space, "horizontal"): buttons["composite"].click()
                    case (QKey.Key_Space, "experiment"): buttons["start_stop"].click()
                    
                    case (QKey.Key_Up, "horizontal"): buttons["n"].click()
                    case (QKey.Key_Right, "horizontal"): buttons["e"].click()
                    case (QKey.Key_Down, "horizontal"): buttons["s"].click()
                    case (QKey.Key_Left, "horizontal"): buttons["w"].click()
                    case (QKey.Key_Home | QKey.Key_7, "horizontal"): buttons["nw"].click()
                    case (QKey.Key_9, "horizontal"): buttons["ne"].click()
                    case (QKey.Key_3, "horizontal"): buttons["se"].click()
                    case (QKey.Key_End | QKey.Key_1), "horizontal": buttons["sw"].click()
                    
                    case (QKey.Key_A, "frame_grid"): line_edits["frame_angle"].focusAndSelect()
                    case (QKey.Key_C, "connections"): buttons["camera"].click()
                    case (QKey.Key_D, "tip"): buttons["set_dz"].click()
                    case (QKey.Key_D, "bias"): line_edits["dV_nanonis"].focusAndSelect()
                    case (QKey.Key_E, "experiment"): self.gui.comboboxes["experiment"].toggleIndex()
                    case (QKey.Key_H, "frame_grid"): line_edits["frame_height"].focusAndSelect()
                    case (QKey.Key_K, "bias"): line_edits["V_keithley"].focusAndSelect()
                    case (QKey.Key_L, "frame_grid"): line_edits["grid_lines"].focusAndSelect()
                    case (QKey.Key_M, "bias"): line_edits["V_mla_port1"].focusAndSelect()
                    case (QKey.Key_M, "connections"): buttons["mla"].click()
                    case (QKey.Key_N, "bias"): line_edits["V_nanonis"].focusAndSelect()
                    case (QKey.Key_N, "connections"): buttons["nanonis"].click()
                    case (QKey.Key_P, "prep"): buttons["bias_pulse"].click()
                    case (QKey.Key_P, "frame_grid"): line_edits["grid_pixels"].focusAndSelect()
                    case (QKey.Key_W, "frame_grid"): line_edits["frame_width"].focusAndSelect()
                    case (QKey.Key_X, "frame_grid"): line_edits["frame_x"].focusAndSelect()
                    case (QKey.Key_Y, "frame_grid"): line_edits["frame_y"].focusAndSelect()
                    case (QKey.Key_Z, "tip"): line_edits["z_rel"].focusAndSelect()

                    case (_, _): pass
        except Exception as e:
            self.logprint(f"{e}", message_type = "error")        
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
        completer = SCTWidgets.Completer(self.all_attributes, self.gui)
        completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
        completer.setCompletionMode(SCTWidgets.Completer.CompletionMode.PopupCompletion)
        self.gui.line_edits["input"].setCompleter(completer)
        return

    def execute_command(self) -> None:
        input_le = self.gui.line_edits["input"]
        input_le.blockSignals(True)
        text = input_le.text()
        input_le.clear()
        input_le.blockSignals(False)
        
        # Add "self." to attributes that are instances of the main Scantelligent class
        self_objects = [attribute for attribute in dir(self) if not attribute.startswith("_")]
        split_text = re.split(r"(\s+|,|\(|\)|:|\w+)", text)
        for index, substring in enumerate(split_text):
            if substring in self_objects:
                if index < 2:
                    split_text[index] = "self." + substring
                if split_text[index - 2] == "self" or split_text[index - 1] == ".":
                    pass
                else:
                    split_text[index] = "self." + substring
        command = "".join(split_text)
        
        try: # Attempt to evaluate
            self.logprint(f"{text}", message_type = "code")
            compile(command, "<string>", "eval")

            result = eval(command)
            self.logprint(f"{result}", message_type = "result")
        except SyntaxError:
            try: # Attempt to execute
                compile(command, "<string>", "exec")

                exec(command)
            except SyntaxError:
                self.logprint("Invalid code.", message_type = "error")
            except Exception as e:
                self.logprint(f"{e}", message_type = "error")
        except Exception as e:
            self.logprint(f"{e}", message_type = "error")        
        return

    def camera_finished(self) -> None:
        try: self.camera_thread = None
        except: pass
        return

    def toggle_limits_view(self) -> None:
        if self.gui.buttons["limits"].isChecked(): self.gui.limits_widget.show()
        else: self.gui.limits_widget.hide()
        return

    def focus_on_groupbox(self, target: str = "") -> None:
        if not target in self.gui.groupboxes.keys(): return
        self.gui.groupboxes[target].setFocused()
        self.gui.tool_scroller.ensureWidgetVisible(self.gui.groupboxes[target], 0, 20)
        self.focus_group = target
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
    
    def open_file(self, file_path: str = "") -> None:
        if not os.path.isfile(file_path):
            self.logprint(f"Cannot open non-existing file {file_path}", message_type = "error")
            return
        
        self.toggle_view("nanonis")
        dataset = None
        frame = None

        try:
            file_data = self.file_functions.read_file(file_path)
            [dataset, frame, axes, axes_data] = [file_data.get(key, None) for key in ["dataset", "frame", "axes", "axes_data"]]
        except Exception as e:
            self.logprint(f"Could not open this file: {e}", message_type = "error")

        if not isinstance(dataset, np.ndarray):
            self.logprint(f"Could not retrieve data from this file", message_type = "error")
            return
        
        try:
            array_item = SCTWidgets.ArrayItem(name = os.path.basename(file_path), array = dataset, frame = frame) # Create the ArrayItem object
            
            previous_rank = self.gui.comboboxes["x_axis"].count() # Record the initial state of the comboboxes. The previous rank is equal to the number of axis labels currently present in the combobox
            previous_x_index = self.gui.comboboxes["x_axis"].currentIndex()
            previous_y_index = self.gui.comboboxes["y_axis"].currentIndex()
            
            if isinstance(axes, list | np.ndarray):
                self.gui.comboboxes["x_axis"].renewItems(axes) # Add the names of the various array axes to the x and y axes comboboxes
                self.gui.comboboxes["y_axis"].renewItems(axes)
                
                for axis_index, axis_name in enumerate(axes): # Attach the axis data (x values, channel names, etc.) to the various axes of the ArrayItem                    
                    if axis_name in axes_data: array_item.setAxisData(axis_index, axis_name, labels = axes_data[axis_name])
                    else: array_item.setAxisData(axis_index, axis_name)
                
                if previous_rank < 2: # If the combobox previously held no items, attempt to default to mapping the image x axis to the array x axis
                    [self.gui.comboboxes["x_axis"].selectItem(tag) for tag in axes if tag.lower() in ["x", "x (nm)", "x_axis", "x_axis (nm)", "x-axis", "x-axis (nm)", "x axis", "x axis (nm)", "x_values", "x_values (nm)"]]
                    [self.gui.comboboxes["y_axis"].selectItem(tag) for tag in axes if tag.lower() in ["y", "y (nm)", "y_axis", "y_axis (nm)", "y-axis", "y-axis (nm)", "y axis", "y axis (nm)", "y_values", "y_values (nm)"]]
                # Toggle the y axis to the next index if it is the same as the x axis
                if self.gui.comboboxes["y_axis"].currentIndex() == self.gui.comboboxes["x_axis"].currentIndex(): self.gui.comboboxes["y_axis"].toggleIndex()
                if not previous_rank < 1: # Attempt to reset the comboboxes to the same items if there was a previous data array
                    self.gui.comboboxes["x_axis"].selectIndex(previous_x_index)
                    self.gui.comboboxes["y_axis"].selectIndex(previous_y_index)
            
            # Activating the ArrayItem and passing it to ImageView
            for item in self.saved_items: item.showLabels(False)
            if hasattr(self, "active_item"): self.active_item.showLabels(False)
        
            self.active_item = array_item
            self.active_item.setZValue(64)
            self.gui.image_view.setItem(self.active_item)
            self.slice_axes_changed()
            self.update_processing_flags()
            self.active_item.showImage(autoLevels = True)
            self.set_view_range("frame")
            
            self.logprint(f"Successfully loaded scan file {file_path}", message_type = "success")
        except Exception as e:
            self.logprint(f"Error trying to open this file: {e}", message_type = "error")
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
        #self.user.save_parameter_sets()
        try: self.experiment_thread.requestInterruption()
        except: pass
        
        try: self.nanonis.unlink()
        except: pass        
        try: self.mla.unlink()
        except: pass
        try: self.toggle_view("none")
        except: pass
        
        for attribute_name in ["nanonis", "mla", "experiment", "experiment_thread", "camera", "camera_thread"]:
            try: delattr(self, attribute_name)
            except: pass
        return

    def exit(self) -> None:
        self.cleanup()
        self.logprint("Thank you for using Scantelligent!", message_type = "success")
        SCTWidgets.Application.instance().quit()

    def closeEvent(self, event: QtCore.QEvent) -> None:
        event.ignore()
        self.exit()



    # Image_view functions
    def set_view_range(self, obj: str = "full") -> None:
        match obj:            
            case "frame":
                roi_rect = self.gui.frame.boundingRect()
                mapped_rect = self.gui.frame.mapRectToParent(roi_rect)
                self.gui.image_view.view.setRange(mapped_rect)
            case _:
                self.gui.image_view.view.autoRange(item = self.gui.piezo_frame)
        return

    def save_active_item(self) -> None:
        if hasattr(self, "active_item"):
            self.saved_items.insert(0, self.active_item) # Save the active item to the saved_items
        if len(self.saved_items) > 18: self.saved_items = self.saved_items[:18] # Clip the length of saved_items to a maximum number of 18
        
        saved_item_names = []
        for index, item in enumerate(self.saved_items):
            item.setZValue(20 - index) # Reset the ZValues of the items
            saved_item_names.append(item.name)
        self.gui.comboboxes["items"].renewItems(saved_item_names)
        
        view = self.gui.image_view.view
        [view.removeItem for item in view.items if isinstance(item, SCTWidgets.ArrayItem)]
        [view.addItem(item) for item in self.saved_items]
        [item.showLabels(False) for item in self.saved_items[1:]]
        self.saved_items[0].showLabels(True)
        return
    
    def create_array_item(self, name: str = None, shape: list | tuple = (), dtype: np.dtype = np.float32, axes: list | np.ndarray = [], axis_values: list[np.ndarray] = [np.empty((0,))], frame: dict = {}) -> None:
        if not dtype: dtype = np.float32
        if not name: name = "active_item"
        
        if dtype in [np.complex64, np.complex128]: array = np.full(shape, np.nan + 1j * np.nan, dtype = dtype)
        else: array = np.full(shape, np.nan, dtype = dtype)
        
        try:
            array_item = SCTWidgets.ArrayItem(name = name, array = array, frame = frame) # Create the ArrayItem object
            
            previous_rank = self.gui.comboboxes["x_axis"].count() # Record the initial state of the comboboxes. The previous rank is equal to the number of axis labels currently present in the combobox
            previous_x_index = self.gui.comboboxes["x_axis"].currentIndex()
            previous_y_index = self.gui.comboboxes["y_axis"].currentIndex()
            axes_data = axis_values
            
            if isinstance(axes, list | np.ndarray):
                self.gui.comboboxes["x_axis"].renewItems(axes) # Add the names of the various array axes to the x and y axes comboboxes
                self.gui.comboboxes["y_axis"].renewItems(axes)

                for axis_index, axis_name in enumerate(axes): # Attach the axis data (x values, channel names, etc.) to the various axes of the ArrayItem                    
                    if isinstance(axes_data, dict) and axis_name in axes_data: array_item.setAxisData(axis_index, axis_name, labels = axes_data[axis_name])
                    elif isinstance(axes_data, list) and len(axes_data) > axis_index: array_item.setAxisData(axis_index, axis_name, labels = axes_data[axis_index])
                    else: array_item.setAxisData(axis_index, axis_name)

                if previous_rank < 2: # If the combobox previously held no items, attempt to default to mapping the image x axis to the array x axis
                    [self.gui.comboboxes["x_axis"].selectItem(tag) for tag in axes if tag.lower() in ["x", "x (nm)", "x_axis", "x_axis (nm)", "x-axis", "x-axis (nm)", "x axis", "x axis (nm)", "x_values", "x_values (nm)"]]
                    [self.gui.comboboxes["y_axis"].selectItem(tag) for tag in axes if tag.lower() in ["y", "y (nm)", "y_axis", "y_axis (nm)", "y-axis", "y-axis (nm)", "y axis", "y axis (nm)", "y_values", "y_values (nm)"]]
                # Toggle the y axis to the next index if it is the same as the x axis

                if self.gui.comboboxes["y_axis"].currentIndex() == self.gui.comboboxes["x_axis"].currentIndex(): self.gui.comboboxes["y_axis"].toggleIndex()
                if not previous_rank < 1: # Attempt to reset the comboboxes to the same items if there was a previous data array
                    self.gui.comboboxes["x_axis"].selectIndex(previous_x_index)
                    self.gui.comboboxes["y_axis"].selectIndex(previous_y_index)

            # Activating the ArrayItem and passing it to ImageView
            self.active_item = array_item
            self.active_item.setZValue(64)
            self.gui.image_view.setItem(self.active_item)
        
            view = self.gui.image_view.view
            [view.removeItem for item in view.items if isinstance(item, SCTWidgets.ArrayItem) and not item == self.active_item]
            [view.addItem(item) for item in self.saved_items]
        
        except Exception as e:
            self.logprint(f"Error encountered while creating an ArrayItem object: {e}", message_type = "error")
        
        self.slice_axes_changed()
        return

    def toggle_view(self, view: str = None, verbose: bool = True) -> None:
        old_view = self.gui.buttons["view"].state_name
        if old_view == view: return # Return if the view is not changed

        # Determine the new view mode
        if isinstance(view, str) and view in ["nanonis", "camera", "graph", "none"]: # Explicit selection
            new_view = view
        else:
            match old_view: # Toggling to the next view mode
                # Set to Camera
                case "none": new_view = "camera"
                case "camera": new_view = "nanonis"
                case "nanonis": new_view = "graph"
                case "graph": new_view = "camera"
                case _: pass

        # Skip through view modes if hardware components are missing
        if new_view == "camera" and not hasattr(self, "camera"): new_view = "nanonis"
        
        # Clean up old attributes and processes
        if hasattr(self, "camera_thread"):
            try:
                self.camera_thread.requestInterruption()
                time.sleep(.5)
            except:
                pass

        # Reset ImageView. Remove old items. Prepare the QSplitters for resizing
        [min_view_height, min_graph_height, min_console_height] = [self.gui.splitters["image_graph"].widget(index).minimumSizeHint().height() for index in range(3)]
        total_splitter_height = self.gui.splitters["image_graph"].height()

        match new_view:
            case "camera":
                self.gui.buttons["view"].setState("camera")
                self.gui.splitters["image_graph"].setSizes([total_splitter_height - (min_graph_height + min_console_height), min_graph_height, min_console_height])
                
                [self.gui.view.removeItem(item) for item in self.gui.view.addedItems[:]]
                self.gui.image_view.setItem(self.gui.camera_item)
                camera_frame = self.camera.grab_frame()
                self.gui.view.autoRange()
                
                # Set up the camera thread
                self.camera_thread = QtCore.QThread()
                self.camera.moveToThread(self.camera_thread)
                self.camera_thread.finished.connect(self.camera_thread.deleteLater)
                self.camera_thread.finished.connect(self.camera_finished)
                
                if not self.camera.thread() == self.camera_thread:
                    self.logprint(f"Error moving the camera to the camera thread", message_type = "error")
                    self.camera_thread.quit()
                    return
                
                self.camera_thread.started.connect(self.camera.run)
                self.camera.finished.connect(self.camera_thread.quit)
                self.camera_thread.start()

            case "nanonis":
                self.gui.buttons["view"].setState("nanonis")
                self.gui.splitters["image_graph"].setSizes([total_splitter_height - (min_graph_height + min_console_height), min_graph_height, min_console_height])
                
                try: self.gui.view.removeItem(self.gui.camera_item)
                except: pass

                [self.gui.view.addItem(item) for item in [self.gui.new_frame, self.gui.frame, self.gui.piezo_frame, self.gui.tip_target, self.gui.path_pdi]]
                for item in self.saved_items: self.gui.view.addItem(item)
                try: self.nanonis.hardware_update()
                except: pass
                self.set_view_range("full")
            
            case "graph":
                self.gui.buttons["view"].setState("graph")
                self.gui.splitters["image_graph"].setSizes([min_view_height, total_splitter_height - (min_console_height + min_view_height), min_console_height])
                return

            case _:
                self.gui.buttons["view"].setState("none")
                self.gui.splitters["image_graph"].setSizes([total_splitter_height - (min_graph_height + min_console_height), min_graph_height, min_console_height])

        if verbose: self.logprint(f"View set to {self.gui.buttons["view"].state_name}", message_type = "message")
        return

    def toggle_items(self) -> None:
        self.gui.path_pdi.setVisible(self.gui.buttons["path"].isChecked())
        self.gui.new_frame.setVisible(self.gui.buttons["frame"].isChecked())
        
        grid_state = self.gui.buttons["grid"].state_name
        match grid_state:
            case "above":
                for side in ["left", "bottom"]:
                    axis = self.gui.image_view.view.getAxis(side)
                    axis.setGrid(100)
                    axis.setZValue(128)
            case "below":
                for side in ["left", "bottom"]:
                    axis = self.gui.image_view.view.getAxis(side)
                    axis.setGrid(100)
                    axis.setZValue(0)
            case _:
                for side in ["left", "bottom"]:
                    axis = self.gui.image_view.view.getAxis(side)
                    axis.setGrid(False)
        return

    def set_active_item(self) -> None:
        for item in self.saved_items: item.showLabels(False)
        if hasattr(self, "active_item"): self.active_item.showLabels(False)
        try:
            index = self.gui.comboboxes["items"].currentIndex()
            selected_item = self.saved_items[index]
            self.gui.image_view.setItem(selected_item)
            self.active_item = selected_item
            self.active_item.showLabels(True)
            self.gui.frame.setFrame(self.active_item.frame)
            
            view = self.gui.image_view.view
            [view.removeItem for item in view.items if isinstance(item, SCTWidgets.ArrayItem) and not item == selected_item]
            [view.addItem(item) for item in self.saved_items]
        except Exception as e:
            self.logprint(f"{e}", message_type = "error")
        return

    def update_pdi_visibility(self) -> None:
        for index in range(self.gui.grapher.n_channels):
            checked = bool(self.gui.checkboxes[f"channel_{index}"].state_index)
            self.gui.grapher.pdis[index].setVisible(checked)
        return

    def histogram_levels_changed(self) -> None:
        hist_levels = self.gui.image_view.getHistogramWidget().item.getLevels()

        self.gui.limits_widget.setValue("absolute", "min", hist_levels[0])
        self.gui.limits_widget.setValue("absolute", "max", hist_levels[1])
        self.redraw_item()
        return



    # Spectelligent
    def open_spectelligent(self) -> None:
        screens = QtGui.QGuiApplication.screens()
        if len(screens) > 1:
            screen_1_geom = screens[1].geometry()
            self.spt.gui.move(screen_1_geom.topLeft())
        
        self.spt.gui.show()
        self.spt.gui.raise_()
        self.spt.gui.activateWindow()
        return



    # Audio
    def toggle_audio(self) -> None:
        if not hasattr(self, "audio"): return

        if self.spt.gui.lockin_widget.audio_button.isChecked(): self.audio.start()
        else: self.audio.stop()
        return



    # Array slicing and image processing operations
    def slice_axes_changed(self) -> None:
        if not hasattr(self, "active_item"): return
        try:
            # Retrieve the array x and y axes from the comboboxes. If they describe the same axis, toggle the y combobox
            x_axis = self.gui.comboboxes["x_axis"].currentText()
            if self.gui.comboboxes["y_axis"].currentText() == x_axis: self.gui.comboboxes["y_axis"].toggleIndex()
            y_axis = self.gui.comboboxes["y_axis"].currentText()
            
            # Mapping the axes
            self.active_item.mapAxes(x_axis = x_axis, y_axis = y_axis)
            
            # Retrieve the remaining axes and populate the slice comboboxes with the corresponding axis data
            axes = self.active_item.getAxes()
            remaining_axes = sorted(set(axes) - {x_axis, y_axis})
            
            n_slice_comboboxes = 3
            for axis_index in range(n_slice_comboboxes):
                axis_name = None
                if axis_index < len(remaining_axes): axis_name = remaining_axes[axis_index]
                
                try:
                    cbb = self.gui.comboboxes[f"slice_{axis_index}"]
                    if not isinstance(axis_name, str):
                        cbb.setName(f"slice_{axis_index}")
                        cbb.changeToolTip(f"slice_{axis_index}")
                        cbb.clear()
                        continue
                    
                    cbb_previous_index = cbb.currentIndex()
                    (_, axis_data) = self.active_item.getAxisData(axis_name)
                    cbb.setName(axis_name)
                    cbb.changeToolTip(axis_name)
                    axis_data = [str(axis_datum) for axis_datum in axis_data]
                    cbb.renewItems(list(axis_data))
                    cbb.selectIndex(cbb_previous_index % cbb.count())
                    
                    slice_index = cbb.currentIndex()
                    self.active_item.setSlice(axis = axis_name, slice = slice_index)
                    
                    slice_label = cbb.currentText()
                    (quantity, unit, _, _) = self.file_functions.split_physical_quantity(slice_label)
                    if isinstance(unit, str):
                        self.gui.image_view.setHistogramUnit(unit)
                        self.gui.limits_widget.setUnit("absolute", unit)
                        self.gui.limits_widget.setUnit("full", unit)
                except Exception as e:
                    self.logprint(f"{e}")
            
            self.active_item.showImage()
            self.active_item.setFrame()
            self.gui.frame.setFrame(self.active_item.frame)
        except Exception as e:
            self.logprint(f"{e}", message_type = "error")
        return

    def rot_trans_changed(self) -> None:
        if not hasattr(self.gui, "active_item"): return
        try:
            rot_trans = bool(self.gui.buttons["rot_trans"].state_index)
            if rot_trans:
                self.active_item.resetFrame()
                self.gui.frame.setFrame(self.active_item.frame)
            else:
                self.active_item.setOffset(0, 0)
                self.active_item.setAngle(0)
                self.active_item.setFrame()
                item_range = self.active_item.frame.get("domain (nm)")
                self.gui.frame.setFrame({"domain (nm)": item_range, "center (nm)": [0, 0], "angle (deg)": 0})
        except:
            self.logprint(f"Unable to apply rotation and translation", message_type = "error")
        return

    def update_processing_flags(self) -> None:
        flags = {}

        try:
            # Dataset axes and slicing
            x_axis = self.gui.comboboxes["x_axis"].currentIndex()
            y_axis = self.gui.comboboxes["y_axis"].currentIndex()
            flags.update({"x_axis": x_axis, "y_axis": y_axis})
            
            # Background
            bg_method = self.gui.button_groups["background"].getSelectedWidget()
            rot_trans = self.gui.buttons["rot_trans"].isChecked()
            flags.update({"background": f"{bg_method[3:]}", "rotation": rot_trans, "offset": rot_trans})
            
            # Limits
            [min_method, min_value] = self.gui.limits_widget.getMin()
            [max_method, max_value] = self.gui.limits_widget.getMax()
            flags.update({"min_method": f"{min_method}", "min_method_value": f"{min_value}", "max_method": f"{max_method}", "max_method_value": f"{max_value}"})

            # Channel, direction, projection
            selected_channel = self.gui.comboboxes["slice_0"].name
            (quantity, unit, backward, error) = self.file_functions.split_physical_quantity(selected_channel)
            if isinstance(unit, str):
                self.gui.limits_widget.setUnit("full", unit)
                self.gui.limits_widget.setUnit("absolute", unit)
            
            backward = bool(self.gui.buttons["direction"].state_index)
            projection = self.gui.buttons["image_projection"].state_name
            flags.update({"backward": backward, "projection": projection})
            
            # Operations
            [flags.update({operation: self.gui.buttons[operation].isChecked()}) for operation in ["sobel", "normal", "laplace", "gaussian", "reciprocal"]]
            
            phase = self.gui.sliders["phase"].getValue()
            flags.update({"phase (deg)": phase})
        except Exception as e:
            self.logprint(f"Error updating the image processing flags: {e}", message_type = "error")

        # Channels
        channels = self.data.scan_processing_flags.get("channels")
        if channels:
            channel_index = channels.get(selected_channel, None)
            if isinstance(channel_index, int): flags.update({"channel_name": selected_channel, "channel_index": channel_index})

        self.data.scan_processing_flags.update(flags)
        self.redraw_item()
        return

    def redraw_item(self) -> None:
        if self.gui.buttons["view"].state_name == "nanonis":
            try:
                if self.data.scan_processing_flags.get("reciprocal"): self.active_item.setReciprocalFrame()
                else: self.active_item.setFrame()
                image = self.active_item.getSlice()
                (image, statistics, limits, error) = self.data.process_scan(image)
                self.active_item.setImage(image)
                img_min = statistics.get("min")
                img_max = statistics.get("max")
                self.gui.limits_widget.setValue("full", "min", img_min)
                self.gui.limits_widget.setValue("full", "max", img_max)
                
                hist_item = self.gui.image_view.getHistogramWidget().item
                hist_item.setLevels(limits[0], limits[1])
                hist_item.autoHistogramRange()
            except Exception as e:
                self.logprint(f"{e}")
        return



    # Simple Nanonis functions; typically return either True if successful or an old parameter value when it is changed
    def tip_prep(self, action: str) -> None:
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
                if error: raise Exception(error)
            else:
                (tip_status, error) = self.nanonis.tip_update({"withdraw": True}, unlink = False)
                time.sleep(.2)
                (tip_status, error) = self.nanonis.tip_update(unlink = True, verbose = False)
                if error: raise Exception(error)

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
            composite = self.gui.buttons["composite_motion"].isChecked()

            # Retrieve the line_edit values
            [V_hor, V_ver, f_motor] = [line_edits[name].getValue() for name in ["V_hor", "V_ver", "f_motor"]] # Frequency and amplitude
            [z_steps, h_steps, minus_z_steps] = [line_edits[name].getValue() for name in ["z_steps", "h_steps", "minus_z_steps"]] # Steps

            # Toggle the view feed
            if hasattr(self, "camera"): self.toggle_view("camera")

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
            
            if approach: self.start_auto_approach()
            
            return True
        
        except Exception as e:
            self.logprint(f"Unable to execute tip move: {e}", message_type = "error")

            return False

    def modulator_control(self, modulator_number: int = 1) -> None:
        if not hasattr(self, "nanonis"): return
        try:
            mod1_on = self.gui.buttons["nanonis_mod1"].isChecked()
            mod2_on = self.gui.buttons["nanonis_mod2"].isChecked()

            self.nanonis.lockin_update({"modulator_1": {"on": mod1_on}, "modulator_2": {"on": mod2_on}})
            
        except Exception as e:
            self.logprint(f"Error controlling modulator {modulator_number}: {e}", message_type = "error")
        return

    def set_dz(self) -> None:
        if not hasattr(self, "nanonis"): return
        try:
            z_rel_nm = self.gui.line_edits["z_rel"].getValue()
            self.nanonis.tip_update({"z_rel (nm)": z_rel_nm})
        except Exception as e:
            self.logprint(f"Error: {e}", message_type = "error")
        return



    # Simple MLA functions
    def expose_dIdV(self) -> None:
        if not hasattr(self, "mla"): return
        try: self.mla.expose_dIdV()
        except Exception as e: self.logprint(f"{e}", message_type = "error")
        return



    # Experiments
    def control_experiment(self, experiment_name = None) -> bool:
        if not "session_path" in list(self.paths.keys()) or not os.path.isdir(self.paths["session_path"]):
            self.logprint(f"Error. No session folder loaded. Either select one manually or get it from a Nanonis connection", message_type = "error")
            return False
        
        start_button = self.gui.buttons["start_stop"]
        
        match start_button.state_name:
            case "load": # Load the experiment
                if not experiment_name: experiment_name = self.gui.comboboxes["experiment"].currentText()
                else:
                    try:
                        if experiment_name in self.gui.comboboxes["experiment"].getItems(): self.gui.comboboxes["experiment"].setCurrentText(experiment_name)
                        else: self.gui.comboboxes["experiment"].setCurrentText("")
                    except:
                        pass
                experiment_path = os.path.join(self.paths["experiments_folder"], experiment_name + ".py")
                if not os.path.isfile(experiment_path):
                    self.logprint(f"The selected experiment was not found in {self.paths["experiments_folder"]}", "error")
                    return False

                self.logprint(f"Loading/resetting experiment {experiment_name}", message_type = "message")
                [self.gui.progress_bars[name].setValue(0) for name in ["task", "experiment"]]
                self.receive_data(np.array(["clear"]))
                self.gui.comboboxes["direction"].renewItems([])
                for i in range(9):
                    self.gui.line_edits[f"experiment_{i}"].setToolTip(f"Experiment parameter field {i}\ngui.line_edits[\"experiment_{i}\"]")
                
                
                                
                # Decorate the file name
                match experiment_name:
                    case "spectroscopy":
                        x_axis_name = self.spt.gui.buttons["sts_x_axis"].state_name
                        y_axis_name = self.spt.gui.buttons["sts_y_axis"].state_name
                        
                        if x_axis_name in ["V", "z", "f", "amp"]:
                            if y_axis_name in ["V", "z", "f", "amp"]: experiment_name = "_".join([x_axis_name, y_axis_name, "spectroscopy"]) # 2D spectroscopy
                            else: experiment_name = "_".join([x_axis_name, "spectroscopy"]) # 1D spectroscopy
                    
                    case "scan":
                        active_controller = self.gui.comboboxes["controller"].currentText()
                        feedback = bool(self.gui.buttons["tip"].state_index % 2)
                        scan_range = [self.gui.line_edits["frame_width"].getValue(), self.gui.line_edits["frame_height"].getValue()]
                        
                        if not feedback: experiment = "constant_height_scan"
                        elif scan_range[0] > 100 and scan_range[1] > 100: experiment = "overview_scan"
                        else:
                            match active_controller:
                                case text if "current" in text.lower(): experiment_name = "I_fb_scan"
                                case text if "didv" in text.lower(): experiment_name = "dIdV_fb_scan"
                                case _: pass
                    
                    case _:
                        pass
                
                [previous_filename, next_filename] = self.file_functions.get_next_indexed_filename(self.paths["session_path"], experiment_name, ".hdf5")
                experiment_filename = next_filename
                if self.gui.buttons["save"].state_name == "data_present": experiment_filename = previous_filename # Overwrite the previous file if it was not saved
                
                
                
                self.paths.update({"experiment_filename": experiment_filename})
                experiment_filepath = os.path.join(self.paths["session_path"], experiment_filename)
                self.paths.update({"experiment_filepath": experiment_filepath})
                self.gui.line_edits["experiment_filename"].setText(self.paths["experiment_filename"])
                
                try:
                    mla_pointer = None
                    if hasattr(self, "mla"): mla_pointer = self.mla                    
                    self.experiment = self.file_functions.load_experiment_from_file(experiment_path, hw_config = self.hw_config, experiment_file = experiment_filepath, scantelligent_folder = self.paths["parent_folder"],
                                                                                    scan_processing_flags = self.data.scan_processing_flags, nanonis = self.nanonis1, mla = mla_pointer)
                    self.experiment_thread = QtCore.QThread()
                    self.experiment.moveToThread(self.experiment_thread)
                    
                    # Worker-thread connections
                    self.experiment_thread.started.connect(self.experiment.run)
                    self.experiment.finished.connect(self.save_active_item)
                    self.experiment.finished.connect(self.experiment_thread.quit)
                    self.experiment_thread.finished.connect(self.experiment_cleanup)
                    
                    # Progress
                    self.experiment.task_progress.connect(lambda val: self.gui.progress_bars["task"].setValue(val))
                    self.experiment.exp_progress.connect(lambda val: self.gui.progress_bars["experiment"].setValue(val))

                    # Other data
                    self.experiment.message.connect(lambda message, message_type: self.logprint(message = message, message_type = message_type))
                    self.experiment.parameters.connect(self.parameters.receive)
                    self.experiment.image.connect(self.receive_image)
                    self.experiment.data_array.connect(self.receive_data)
                    self.experiment.array_slice.connect(self.receive_array_slice)
                    
                    # Set up the GUI. This direct call triggers the self.gui_setup to be emitted and handled by the Scantelligent ParameterManager
                    self.experiment.prepare_gui()
                
                except Exception as e:
                    self.logprint(f"Unable to load the experiment. {e}", message_type = "error")
                    return False
                
                self.status["experiment"].update({"name": experiment_name})
                start_button.setState("ready")
            
            case "ready": # Experiment is loaded and ready. Start it
                if not hasattr(self, "experiment") or not hasattr(self, "experiment_thread"): # Abort if the experiment wasn't properly loaded
                    self.logprint("Error. No experiment object or thread initialized", message_type = "error")
                    start_button.setState("load")
                    return False
                
                # Pass the parameters from the gui to the experiment
                spec_line_edits = {}
                [spec_line_edits.update({f"{quantity}_{key}": self.spt.gui.line_edits[f"sts_{quantity}_{key}"].getValue() for key in ["start", "end", "points"]}) for quantity in ["x", "y", "V", "f", "z", "amp", "V_keithley"]]
                spec_line_edits.update({f"t_{key}": self.spt.gui.line_edits[f"sts_t_{key}"].getValue() for key in ["settle", "int"]})
                spec_line_edits.update({f"{key}_feedback": self.spt.gui.line_edits[f"sts_{key}_feedback"].getValue() for key in ["t", "V", "I", "p", "t_const", "z"]})
                spec_buttons = {}
                spec_buttons.update({f"{key}": self.spt.gui.buttons[f"sts_{key}"].state_name for key in ["x_axis", "y_axis"]}) # Names of the spectroscopic axes
                spec_buttons.update({f"{quantity}_retrace": self.spt.gui.buttons[f"{quantity}_retrace"].isChecked() for quantity in ["V", "f", "z", "amp", "V_keithley"]}) # Bools desribing whether to retrace
                spec_buttons.update({key: self.spt.gui.buttons[key].isChecked() for key in ["tia_correct", "intermediate_feedback", "blank_modulators"]}) # Spec settings: bools
                spec_buttons.update({key: self.spt.gui.buttons[key].state_name for key in ["nanonis_mla", "spectroscopy_feedback"]})
                spec_buttons.update({key: self.gui.buttons[key].state_name for key in ["scan_direction"]})
                modulators_bool_list = [self.spt.gui.checkboxes[f"modulator_{index}"].isChecked() for index in range(32)]
                spec_modulators = [index for index, val in enumerate(modulators_bool_list) if val]
                gui_parameters = {"combobox": self.gui.comboboxes["direction"].currentText(),
                                  "line_edits": [self.gui.line_edits[f"experiment_{index}"].getValue() for index in range(9)],
                                  "buttons": [self.gui.buttons[f"experiment_{index}"].state_name for index in range(6)],
                                  "spectroscopy_line_edits": spec_line_edits, "spectroscopy_buttons": spec_buttons, "modulators": spec_modulators}
                self.experiment.gui_parameters = copy.deepcopy(gui_parameters) # Pass a copy of (not a reference to) these parameters to the experiment object, so they can be read out locally
                
                self.receive_data(np.array(["clear"])) # Clear the grapher widget
                self.gui.image_view.blockDrops = True
                start_button.setState("running")
                self.gui.buttons["save"].setState("data_present")
                self.experiment_thread.start()
            
            case "running":
                start_button.setState("aborted")
                if hasattr(self, "experiment_thread"):
                    if not self.experiment_thread.isRunning(): return False
                    else:
                        self.experiment_thread.requestInterruption()
            
            case _:
                pass
                
        return True

    def experiment_cleanup(self) -> None:
        self.experiment.deleteLater()
        self.experiment_thread.deleteLater()
        self.gui.buttons["start_stop"].setState("load")
        self.spt.gui.buttons["start_spectroscopy"].setState(0)
        [self.gui.buttons[name].setState(0) for name in ["start_scan", "approach", "approach_2"]]
        
        if not self.experiment.abort_requested: self.gui.buttons["save"].setState(2) # Save the experimental data by default if the experiment ended successfully.
        return

    def save_experiment(self) -> None:
        if self.gui.buttons["save"].state_name == "data_present":
            self.gui.buttons["save"].setState("data_saved")
        return

    def quick_scan(self) -> bool:
        experiment_loaded = self.control_experiment("scan")
        if not experiment_loaded: return False
        self.gui.buttons["start_scan"].setState(1)
        return self.control_experiment("scan")
    
    def start_spectroscopy(self) -> None:
        experiment_loaded = self.control_experiment("spectroscopy")
        if not experiment_loaded: return False
        self.spt.gui.buttons["start_spectroscopy"].setState(1)
        return self.control_experiment("spectroscopy")        

    def start_auto_approach(self) -> None:
        experiment_loaded = self.control_experiment("auto_approach")
        if not experiment_loaded: return False
        self.gui.buttons["approach"].setState(1)
        self.gui.buttons["approach_2"].setState(1)
        return self.control_experiment("auto_approach")



# Main program
if __name__ == "__main__":
    app = SCTWidgets.Application(sys.argv)
    logic_app = Scantelligent()
    sys.exit(app.exec())
