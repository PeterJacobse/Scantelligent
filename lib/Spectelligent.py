import os, sys, html, atexit, re, copy, time
from PIL import Image
import numpy as np
from PyQt6 import QtGui, QtCore
import pyqtgraph as pg
from .gui_spectelligent import SpectelligentGUI
from .sct_widgets import SCTWidgets
from .data_processing import DataProcessing
from .file_functions import FileFunctions
from .parameter_manager import ParameterManager, UserData
from .audio_generator import AudioGenerator
from datetime import datetime



# Main class
class Spectelligent(QtCore.QObject):
    volumes = QtCore.pyqtSignal(list)
    amplitudes = QtCore.pyqtSignal(list)
    frequencies = QtCore.pyqtSignal(list)

    def __init__(self, parent):
        super().__init__()
        #self.parameters_init()
        self.gui = SpectelligentGUI()
        self.sct = parent
        self.connect_buttons()



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
        self.stdout_redirector = SCTWidgets.StreamRedirector()
        self.stdout_redirector.output_written.connect(lambda text: self.gui.consoles["output"].append(text))
        sys.stdout = self.stdout_redirector
        #sys.stderr = self.stdout_redirector
        now = datetime.now()
        self.logprint(now.strftime("Opening Scantelligent on %Y-%m-%d %H:%M:%S"), message_type = "message")

        return

    def connect_buttons(self) -> None:
        button_slots = {"sts_x_axis": self.update_grid, "sts_y_axis": self.update_grid, "exit": self.exit}
        
        for button_name, connected_function in button_slots.items():
            self.gui.buttons[button_name].clicked.connect(connected_function)
            #if button_name in self.gui.shortcuts.keys():
            #    shortcut = QtGui.QShortcut(self.gui.shortcuts[button_name], self.gui)
            #    shortcut.activated.connect(connected_function)
        return



    # Miscellaneous
    def logprint(self, message: str = "", message_type: str = "error", timestamp: bool = True) -> None:
        return self.sct.logprint(message = message, message_type = message_type)

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

    def exit(self) -> None:
        self.gui.close()

    def closeEvent(self, event) -> None:
        self.exit()



    # Update the STS grid
    def update_grid(self) -> None:
        line_edits = self.gui.line_edits
        
        match self.gui.buttons["sts_x_axis"].state_name:
            case "V":
                x_limits = [line_edits[f"sts_V_{side}"].getValue() for side in ["start", "end"]]
                x_points = line_edits["sts_V_points"].getValue()
                self.gui.plot_widget.setLabel("bottom", "V (V)")
            case "amp":
                x_limits = [line_edits[f"sts_amp_{side}"].getValue() for side in ["start", "end"]]
                x_points = line_edits["sts_amp_points"].getValue()
                self.gui.plot_widget.setLabel("bottom", "amp (mV)")
            case "f":
                x_limits = [line_edits[f"sts_f_{side}"].getValue() for side in ["start", "end"]]
                x_points = line_edits["sts_f_points"].getValue()
                self.gui.plot_widget.setLabel("bottom", "f (Hz)")
            case "z":
                x_limits = [line_edits[f"sts_z_{side}"].getValue() for side in ["start", "end"]]
                x_points = line_edits["sts_z_points"].getValue()
                self.gui.plot_widget.setLabel("bottom", "z (nm)")
            case _:
                pass

        match self.gui.buttons["sts_y_axis"].state_name:
            case "V":
                y_limits = [line_edits[f"sts_V_{side}"].getValue() for side in ["start", "end"]]
                y_points = line_edits["sts_V_points"].getValue()
                self.gui.plot_widget.setLabel("left", "V (V)")
            case "amp":
                y_limits = [line_edits[f"sts_amp_{side}"].getValue() for side in ["start", "end"]]
                y_points = line_edits["sts_amp_points"].getValue()
                self.gui.plot_widget.setLabel("left", "amp (mV)")
            case "f":
                y_limits = [line_edits[f"sts_f_{side}"].getValue() for side in ["start", "end"]]
                y_points = line_edits["sts_f_points"].getValue()
                self.gui.plot_widget.setLabel("left", "f (Hz)")
            case "z":
                y_limits = [line_edits[f"sts_z_{side}"].getValue() for side in ["start", "end"]]
                y_points = line_edits["sts_z_points"].getValue()
                self.gui.plot_widget.setLabel("left", "z (nm)")
            case _:
                self.gui.plot_widget.setLabel("left", "")

        try:
            x_min = min(x_limits)
            x_max = max(x_limits)
            dx = (x_max - x_min) / (x_points - 1)
            self.gui.plot_widget.setXRange(x_min - dx, x_max + dx)
            
            if y_limits:
                y_min = min(y_limits)
                y_max = max(y_limits)
                dy = (y_max - y_min) / (y_points - 1)
                self.gui.grid_item.setValues(x_values = np.linspace(x_min, x_max, x_points), y_values = np.linspace(y_min, y_max, y_points))
                self.gui.plot_widget.setYRange(y_min - dy, y_max + dy)
            else:
                self.gui.grid_item.setValues(x_values = np.linspace(x_min, x_max, x_points), y_values = np.array([0], dtype = float))
                self.gui.plot_widget.setYRange(-1, 1)
        except:
            pass
        return



    # Visual stuff: scan/spectroscopy/graphing
    def set_pdi_visible(self, index: int = 0) -> None:
        checked = bool(self.gui.checkboxes[f"channel_{index}"].state_index)
        self.gui.pdis[index].setVisible(checked)
        return



    # Audio
    def toggle_audio(self) -> None:
        if not hasattr(self, "audio"): return

        if bool(self.gui.buttons["audio"].state_index):
            self.audio.start()
        else:
            self.audio.stop()
        return

    def send_volumes(self) -> None:
        overal_volume = int(self.gui.sliders["volume"].getValue())
        volumes = [int(self.gui.sliders[f"f{index}"].getValue() * overal_volume) for index in range(32)]
        self.volumes.emit(volumes)
        return

    def zero_volumes(self) -> None:
        [self.gui.sliders[f"f{index}"].setValue(0) for index in range(32)]
        return



    # Read the GUI to set processing flags for image/spectrum processing
    def update_processing_flags(self) -> None:
        flags = {}

        try:
            # Background
            bg_method = self.gui.button_groups["background"].getSelectedWidget()
            flags.update({"background": f"{bg_method[3:]}", "rotation": True, "offset": True})        
            
            # Limits
            [min_method, min_value] = self.gui.limits_widget.getMin()
            [max_method, max_value] = self.gui.limits_widget.getMax()
            flags.update({"min_method": f"{min_method}", "min_method_value": f"{min_value}", "max_method": f"{max_method}", "max_method_value": f"{max_value}"})

            # Channel, direction, projection
            selected_channel = self.gui.comboboxes["channels"].currentText()
            (quantity, unit, backward, error) = self.file_functions.split_physical_quantity(selected_channel)
            if isinstance(unit, str):
                self.gui.limits_widget.setUnit("full", unit)
                self.gui.limits_widget.setUnit("absolute", unit)
            
            backward = bool(self.gui.buttons["direction"].state_index)
            projection = self.gui.comboboxes["projection"].currentText()
            flags.update({"backward": backward, "projection": projection})
            
            # Operations
            [flags.update({operation: self.gui.buttons[operation].isChecked()}) for operation in ["sobel", "normal", "laplace", "gaussian", "fft"]]
            
            phase = self.gui.sliders["phase"].getValue()
            flags.update({"phase (deg)": phase})        
        except Exception as e:
            self.logprint(f"Error updating the image processing flags: {e}", message_type = "error")

        # Channels
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
                (tip_status, error) = self.nanonis.tip_update({"withdraw": True}, unlink = False)
                time.sleep(.2)
                (tip_status, error) = self.nanonis.tip_update(unlink = True, verbose = False)
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



    # Nanonis/MLA functions
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

    def request_pixel(self, target: str = "mla") -> None:
        match target:
            case "nanonis":
                try:
                    pass
                except Exception as e:
                    self.logprint(f"Cannot request a pixel from Nanonis: {e}", message_type = "error")
            case "mla":
                try:
                    self.mla.frequencies_update()
                    self.mla.start_lockin()
                    self.mla.get_pixels(1)
                    self.mla.stop_lockin()
                except Exception as e:
                    self.logprint(f"Cannot request a pixel from the MLA: {e}", message_type = "error")
            case _:
                pass
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
                    try: self.gui.comboboxes["experiment"].setCurrentText(experiment_name)
                    except: pass
                experiment_path = os.path.join(self.paths["experiments_folder"], experiment_name + ".py")
                if not os.path.isfile(experiment_path):
                    self.logprint(f"The selected experiment was not found in {self.paths["experiments_folder"]}", "error")
                    return False

                self.logprint(f"Loading/resetting experiment {experiment_name}", message_type = "message")
                [self.gui.progress_bars[name].setValue(0) for name in ["task", "experiment"]]
                [pdi.setData() for pdi in self.gui.pdis]
                self.gui.comboboxes["direction"].renewItems([])
                for i in range(9):
                    self.gui.line_edits[f"experiment_{i}"].setToolTip(f"Experiment parameter field {i}\ngui.line_edits[\"experiment_{i}\"]")
                    #self.gui.line_edits[f"experiment_{i}"].setValue("")
                    #self.gui.line_edits[f"experiment_{i}"].setUnit()
                
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
                    self.experiment = self.file_functions.load_experiment_from_file(experiment_path, hw_config = self.hw_config, experiment_file = experiment_filepath,
                                                                                    scan_processing_flags = self.data.scan_processing_flags, nanonis = self.nanonis1, mla = mla_pointer)
                    self.experiment_thread = QtCore.QThread()
                    self.experiment.moveToThread(self.experiment_thread)
                    
                    # Worker-thread connections
                    self.experiment_thread.started.connect(self.experiment.run)
                    self.experiment.finished.connect(self.experiment_thread.quit)
                    self.experiment.finished.connect(self.refresh_image)
                    self.experiment_thread.finished.connect(self.experiment.deleteLater)
                    #self.experiment_thread.finished.connect(lambda: self.gui.buttons["save"].setState("data_saved"))
                    self.experiment_thread.finished.connect(self.experiment_thread.deleteLater)
                    self.experiment_thread.finished.connect(lambda: start_button.setState("load"))
                    [self.experiment_thread.finished.connect(lambda name0 = name: self.gui.buttons[name0].setState(0)) for name in ["start_scan", "start_spectrum", "approach"]]
                    
                    # Progress
                    self.experiment.task_progress.connect(lambda val: self.gui.progress_bars["task"].setValue(val))
                    self.experiment.exp_progress.connect(lambda val: self.gui.progress_bars["experiment"].setValue(val))

                    # Other data
                    self.experiment.message.connect(lambda message, message_type: self.logprint(message = message, message_type = message_type))
                    self.experiment.parameters.connect(self.parameters.receive)
                    self.experiment.image.connect(self.receive_image)
                    self.experiment.data_array.connect(self.receive_data)
                    
                    # Set up the GUI. This direct call triggers the self.gui_setup to be emitted and handled by the Scantelligent ParameterManager
                    self.experiment.prepare_gui()
                
                except Exception as e:
                    self.logprint(f"Unable to load the experiment. {e}", message_type = "error")
                    return False
                
                self.status["experiment"].update({"name": experiment_name})
                start_button.setState("ready")
            
            case "ready": # Experiment is loaded and ready. Start it
                if not hasattr(self, "experiment") or not hasattr(self, "experiment_thread"):
                    self.logprint("Error. No experiment object or thread initialized", message_type = "error")
                    start_button.setState("load")
                    return False
                
                # Pass the parameters from the gui to the experiment
                spec_line_edits = {}
                [spec_line_edits.update({f"{quantity}_{key}": self.gui.line_edits[f"sts_{quantity}_{key}"].getValue() for key in ["start", "end", "points"]}) for quantity in ["V", "f", "z", "amp", "V_keithley"]]
                [spec_line_edits.update({f"t_{key}": self.gui.line_edits[f"sts_t_{key}"].getValue() for key in ["settle", "int"]})]
                spec_buttons = {}
                [spec_buttons.update({f"{quantity}": self.gui.buttons[f"sts_{quantity}"].state_name}) for quantity in ["V", "f", "z", "amp", "V_keithley"]]
                spec_buttons.update({"nanonis_mla": self.gui.buttons["nanonis_mla"].state_name})
                
                gui_parameters = {"combobox": self.gui.comboboxes["direction"].currentText(),
                                  "line_edits": [self.gui.line_edits[f"experiment_{index}"].getValue() for index in range(9)],
                                  "buttons": [self.gui.buttons[f"experiment_{index}"].state_name for index in range(6)],
                                  "spectroscopy_line_edits": spec_line_edits,
                                  "spectroscopy_buttons": spec_buttons}

                self.experiment.gui_parameters = copy.deepcopy(gui_parameters)
                
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

    def save_experiment(self) -> None:
        if self.gui.buttons["save"].state_name == "data_present":
            self.gui.buttons["save"].setState("data_saved")
        return
    
    def start_spectroscopy(self) -> None:
        experiment_loaded = self.control_experiment("spectroscopy")
        if not experiment_loaded: return False
        self.gui.buttons["start_spectrum"].setState(1)
        return self.control_experiment("spectroscopy")        

