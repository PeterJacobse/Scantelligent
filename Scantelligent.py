import os
import sys
import yaml
import numpy as np
import socket
import cv2
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QToolButton, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QFileDialog, QButtonGroup, QComboBox, QRadioButton, QGroupBox, QLineEdit, QCheckBox, QFrame
from PyQt6.QtCore import QObject, Qt, QProcess, QThread, pyqtSignal, pyqtSlot
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from PyQt6.QtGui import QImage, QImageWriter
import scantelligent.functions as st
from datetime import datetime
from scantelligent.image_functions import apply_gaussian, apply_fft, image_gradient, compute_normal, apply_laplace, complex_image_to_colors, background_subtract, get_image_statistics
from scantelligent.control import HelperFunctions, Experiments, CameraWorker, MeasurementWorker
from time import sleep
from scipy.interpolate import griddata

# Establish a TCP/IP connection
# TCP_IP = "192.168.236.1"                           # Local host
TCP_IP = "127.0.0.1"
TCP_PORT = 6501                                    # Check available ports in NANONIS > File > Settings Options > TCP Programming Interface
version_number = 13520
camera_argument = 0



class AppWindow(QMainWindow):
    request_start = pyqtSignal(object, object, object, int, int)
    request_stop = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scantelligent by Peter H. Jacobse") # Make the app window
        self.setGeometry(100, 100, 1400, 800) # x, y, width, height

        # Initialize PyQtgraph widget
        # pg.setConfigOptions(imageAxisOrder = "row-major")
        self.image_view = pg.ImageView(view = pg.PlotItem())
        self.hist = self.image_view.getHistogramWidget()
        self.hist_item = self.hist.item

        # Initialize parameters       
        self.parameters_init()
        
        # Set the central widget of the QMainWindow
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.addWidget(self.image_view, 3)
        main_layout.addLayout(self.draw_buttons(), 1)

        # Activate buttons and keys
        self.connect_buttons()
        #self.connect_keys()
        
        # Ensure the central widget can receive keyboard focus
        central_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        central_widget.setFocus()
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.activateWindow()

        # Create a QProcess handle for opening of Scanalyzer
        self.process = QProcess(self)
        try: # Read the config yaml file
            with open(self.scantelligent_folder + "\\config.yml", "r") as file:
                config = yaml.safe_load(file)
                self.scanalyzer_path = config.get("scanalyzer_path")
        except:
            print("Could not link to Scanalyzer")
            self.scanalyzer_button.setEnabled(False)
            pass
        
        # Check / set up hardware connections
        self.helper_functions = HelperFunctions(TCP_IP, TCP_PORT, version_number)
        self.connect_nanonis()
        """
        self.check_camera_connection(camera_argument)
        
        self.thread = None
        self.worker = None
        self.is_camera_running = False
        """

        # Set up the experiments class and thread and connect signals and slots
        self.experiments = Experiments(TCP_IP, TCP_PORT, version_number)
        self.experiment_thread = QThread()
        self.experiments.moveToThread(self.experiment_thread)

        # self.start_experiment.connect(lambda: self.experiments.sample_grid(grid, points = 40))
        self.request_stop.connect(self.experiments.stop)
        self.experiments.data.connect(self.update)
        self.experiments.finished.connect(self.experiment_finished)
        self.experiment_thread.finished.connect(self.experiments.deleteLater)
        self.experiment_thread.finished.connect(self.experiment_thread.deleteLater)

        self.experiment_thread.start()



    def parameters_init(self):
        self.script_path = os.path.abspath(__file__) # The full path of Scanalyzer.py
        self.script_folder = os.path.dirname(self.script_path) # The parent directory of Scanalyzer.py
        self.scantelligent_folder = self.script_folder + "\\scantelligent" # The directory of the scanalyzer package
        self.folder = self.scantelligent_folder
    
        self.background_subtraction = "plane"
        self.min_percentile = 2
        self.max_percentile = 98
        self.min_std_dev = 2
        self.max_std_dev = 2
        self.view_index = 0
        self.experiment_running = False
   
    def draw_buttons(self):

        def draw_connections_group():
            # Connections group
            connections_box = QGroupBox("Connections (push to check)")
            connections_layout = QGridLayout()
            [self.nanonis_online_button, self.tip_status_button, self.mla_online_button, self.oscillation_on_button, self.camera_online_button, self.view_swap_button] = [
                QPushButton("Nanonis: offline"), QPushButton("Tip status: withdrawn"), QPushButton("MLA: offline"), QPushButton("MLA oscillation: off"), QPushButton("Camera: offline"), QPushButton("Active view: scan")
                ]
            self.nanonis_online_button.setStyleSheet("background-color: darkred;")
            self.mla_online_button.setStyleSheet("background-color: darkred;")
            
            connections_layout.addWidget(self.nanonis_online_button, 0, 0)
            connections_layout.addWidget(self.tip_status_button, 0, 1)
            connections_layout.addWidget(self.mla_online_button, 1, 0)
            connections_layout.addWidget(self.oscillation_on_button, 1, 1)
            connections_layout.addWidget(self.camera_online_button, 2, 0)
            connections_layout.addWidget(self.view_swap_button, 2, 1)
            connections_box.setLayout(connections_layout)
        
            return connections_box

        def draw_coarse_motion_group():
            # Coarse motion group
            coarse_motion_group = QGroupBox("Coarse motion (arrow buttons combine checked actions)")
            coarse_motion_layout = QHBoxLayout()
            
            # Coarse actions        
            coarse_actions_layout = QGridLayout()
            [self.withdraw_button, self.retract_button, self.z_steps_box, self.h_steps_box, self.advance_button, self.minus_z_steps_box, self.approach_button] = self.action_buttons = [
                QPushButton("Withdraw,"), QPushButton("Retract"), QLineEdit("10"), QLineEdit("30"), QPushButton("adVance"), QLineEdit("2"), QPushButton("Auto approach")
                ]
            [self.withdraw_checkbox, self.retract_checkbox, self.move_checkbox, self.advance_checkbox, self.approach_checkbox] = self.action_checkboxes = [QCheckBox() for _ in range(5)]
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
            [label.setAlignment(Qt.AlignmentFlag.AlignCenter) for label in [steps_label, move_label, steps_in_direction_label, steps_and_label]]
            coarse_actions_layout.addWidget(steps_label, 1, 3)
            coarse_actions_layout.addWidget(move_label, 2, 1)            
            coarse_actions_layout.addWidget(steps_in_direction_label, 2, 3)
            coarse_actions_layout.addWidget(steps_and_label, 3, 3)

            coarse_motion_layout.addLayout(coarse_actions_layout)
            
            # Arrows
            arrow_keys = QWidget()
            arrow_keys_layout = QGridLayout()
            [self.nw_button, self.n_button, self.ne_button, self.w_button, self.zero_button, self.e_button, self.sw_button, self.s_button, self.se_button] = self.arrow_buttons = [QToolButton() for _ in range(9)]
            self.nw_button.setText("NW")
            self.n_button.setArrowType(Qt.ArrowType.UpArrow)
            self.ne_button.setText("NE")
            self.w_button.setArrowType(Qt.ArrowType.LeftArrow)
            self.zero_button.setText("0")
            self.e_button.setArrowType(Qt.ArrowType.RightArrow)
            self.sw_button.setText("SW")
            self.s_button.setArrowType(Qt.ArrowType.DownArrow)
            self.se_button.setText("SE")
            
            [arrow_keys_layout.addWidget(self.arrow_buttons[i], 0, i) for i in range(3)]
            [arrow_keys_layout.addWidget(self.arrow_buttons[i + 3], 1, i) for i in range(3)]
            [arrow_keys_layout.addWidget(self.arrow_buttons[i + 6], 2, i) for i in range(3)]
            arrow_keys.setLayout(arrow_keys_layout)
                    
            coarse_motion_layout.addWidget(arrow_keys)
            coarse_motion_group.setLayout(coarse_motion_layout)

            return coarse_motion_group

        def draw_experiments_group():
            experiments_group = QGroupBox("Experiments")
            experiments_layout = QGridLayout()

            self.experiment_box = QComboBox()
            self.experiment_box.addItems(["Grid sampling", "Simple scan"])
            self.start_stop_button = QToolButton()
            self.update_start_stop_icon()
            self.experiment_status = QLabel("Ready")
            points_label = QLabel("Points:")
            points_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.points_box = QLineEdit("200")

            experiments_layout.addWidget(self.experiment_box, 0, 0)
            experiments_layout.addWidget(self.start_stop_button, 0, 1)
            experiments_layout.addWidget(self.experiment_status, 0, 2)
            experiments_layout.addWidget(points_label, 1, 0)
            experiments_layout.addWidget(self.points_box, 1, 1)

            experiments_group.setLayout(experiments_layout)

            return experiments_group
       
        def draw_image_processing_group(): # Image processing group            
            im_proc_group = QGroupBox("Image processing")
            im_proc_layout = QVBoxLayout()
            im_proc_layout.setSpacing(1)
            
            back_sub_label = QLabel("Background subtraction")
            back_sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            im_proc_layout.addWidget(back_sub_label)
            
            # Background subtraction group
            bg_layout = QGridLayout()
            [self.bg_none_radio, self.bg_plane_radio, self.bg_inferred_radio, self.bg_linewise_radio] = background_buttons = [QRadioButton("none (0)"), QRadioButton("Plane"), QRadioButton("Inferred"), QRadioButton("lineWise")]
            # Group them for exclusive selection
            self.bg_button_group = QButtonGroup(self)
            [self.bg_button_group.addButton(button) for button in background_buttons]
            
            # Set default according to self.background_subtraction
            if self.background_subtraction == "plane":
                self.bg_plane_radio.setChecked(True)
            elif self.background_subtraction == "inferred":
                self.bg_inferred_radio.setChecked(True)
            elif self.background_subtraction == "linewise":
                self.bg_linewise_radio.setChecked(True)
            else:
                self.bg_none_radio.setChecked(True)
            
            # Add radio buttons to the layout
            bg_layout.addWidget(self.bg_none_radio, 0, 0)
            bg_layout.addWidget(self.bg_plane_radio, 0, 1)
            bg_layout.addWidget(self.bg_inferred_radio, 1, 0)
            bg_layout.addWidget(self.bg_linewise_radio, 1, 1)
            im_proc_layout.addLayout(bg_layout)

            # Create the horizontal line separator
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)  # Set the shape to a horizontal line
            line.setLineWidth(1) # Optional: Set the line width
            im_proc_layout.addWidget(line) # Add the line to the QVBoxLayout



            # Matrix operations
            back_sub_label = QLabel("Matrix operations")
            back_sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            im_proc_layout.addWidget(back_sub_label)

            matrix_layout = QGridLayout()
            matrix_layout.setSpacing(1)
            [self.sobel_button, self.normal_button, self.laplace_button, self.gauss_button, self.fft_button, self.project_complex_box] = matrix_buttons = [QCheckBox("soBel (d/dx + i d/dy)"), QCheckBox("Normal_z"), QCheckBox("laplaCe (∇2)"), QCheckBox("Gaussian"), QCheckBox("Fft"), QComboBox()]
            #self.derivative_button_group = QButtonGroup(self)
            #[self.derivative_button_group.addButton(button) for button in [self.sobel_button, self.normal_button, self.laplace_button]]
            self.project_complex_box.addItems(["re", "im", "abs", "arg (b/w)", "arg (hue)", "complex", "abs^2", "log(abs)"])

            gaussian_width_label = QLabel("width (nm):")
            gaussian_width_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.gaussian_width_box = QLineEdit("1")
            show_label = QLabel("sHow:")
            show_label.setAlignment(Qt.AlignmentFlag.AlignCenter)

            matrix_layout.addWidget(self.sobel_button, 0, 0)
            matrix_layout.addWidget(self.normal_button, 0, 1)
            matrix_layout.addWidget(self.laplace_button, 0, 2)
            matrix_layout.addWidget(self.gauss_button, 1, 0)
            matrix_layout.addWidget(gaussian_width_label, 1, 1)
            matrix_layout.addWidget(self.gaussian_width_box, 1, 2)
            matrix_layout.addWidget(self.fft_button, 2, 0)
            matrix_layout.addWidget(show_label, 2, 1)
            matrix_layout.addWidget(self.project_complex_box, 2, 2)

            im_proc_layout.addLayout(matrix_layout)

            # Add another line
            line = QFrame()
            line.setFrameShape(QFrame.Shape.HLine)
            line.setLineWidth(1)
            im_proc_layout.addWidget(line)



            # Histogram control group: put the statistics/info label here
            limits_label = QLabel("Set limits (toggle using the - and = buttons)")
            limits_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            im_proc_layout.addWidget(limits_label)

            limits_layout = QGridLayout()
            limits_layout.setSpacing(1)            
            [self.min_range_box, self.min_range_set, self.full_scale_button, self.max_range_set, self.max_range_box] = range_boxes = [QLineEdit(), QRadioButton(), QPushButton("by fUll data range"), QRadioButton(), QLineEdit()]
            [box.setEnabled(False) for box in [self.min_range_box, self.max_range_box]]

            [self.min_percentile_box, self.min_percentile_set, self.set_percentile_button, self.max_percentile_set, self.max_percentile_box] = percentile_boxes = [QLineEdit(), QRadioButton(), QPushButton("by peRcentiles"), QRadioButton(), QLineEdit()]
            self.min_percentile_box.setText(str(self.min_percentile))
            self.max_percentile_box.setText(str(self.max_percentile))

            [self.min_std_dev_box, self.min_std_dev_set, self.set_std_dev_button, self.max_std_dev_set, self.max_std_dev_box] = std_dev_boxes = [QLineEdit(), QRadioButton(), QPushButton("by standard deViations"), QRadioButton(), QLineEdit()]
            self.min_std_dev_box.setText(str(self.min_std_dev))
            self.max_std_dev_box.setText(str(self.max_std_dev))

            [self.min_abs_val_box, self.min_abs_val_set, self.set_abs_val_button, self.max_abs_val_set, self.max_abs_val_box] = abs_val_boxes = [QLineEdit(), QRadioButton(), QPushButton("by Absolute values"), QRadioButton(), QLineEdit()]
            self.min_abs_val_box.setText("0")
            self.max_abs_val_box.setText("1")

            [limits_layout.addWidget(range_boxes[index], 0, index) for index in range(len(range_boxes))]
            [limits_layout.addWidget(percentile_boxes[index], 1, index) for index in range(len(percentile_boxes))]
            [limits_layout.addWidget(std_dev_boxes[index], 2, index) for index in range(len(std_dev_boxes))]
            [limits_layout.addWidget(abs_val_boxes[index], 3, index) for index in range(len(abs_val_boxes))]

            # Min and max buttons are exclusive
            self.min_button_group = QButtonGroup(self)
            [self.min_button_group.addButton(button) for button in [self.min_range_set, self.min_percentile_set, self.min_std_dev_set, self.min_abs_val_set]]
            self.max_button_group = QButtonGroup(self)
            [self.max_button_group.addButton(button) for button in [self.max_range_set, self.max_percentile_set, self.max_std_dev_set, self.max_abs_val_set]]
            
            im_proc_layout.addLayout(limits_layout)
            im_proc_group.setLayout(im_proc_layout)

            return im_proc_group

        def draw_miscellaneous_group():
            misc_group = QGroupBox("Miscellaneous")
            misc_layout = QVBoxLayout()
            self.scanalyzer_button = QPushButton("Launch Scanalyzer")
            self.exit_button = QPushButton("Exit Scantelligent")

            misc_layout.addWidget(self.scanalyzer_button)
            misc_layout.addWidget(self.exit_button)

            misc_group.setLayout(misc_layout)

            return misc_group

        # To be deprecated
        def draw_camera_group():
            # Camera buttons (to be deprecated)
            startstop_group = QGroupBox()
            startstop_layout = QHBoxLayout()
            self.camera_start_button = QPushButton("Start Camera")
            self.camera_start_button.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
            startstop_layout.addWidget(self.camera_start_button)
            self.camera_stop_button = QPushButton("Stop Camera")
            self.camera_stop_button.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
            self.camera_stop_button.setEnabled(False) # Start disabled
            startstop_layout.addWidget(self.camera_stop_button)
            startstop_group.setLayout(startstop_layout)

            return startstop_group

        # Make the buttons. Overal layout is a QVBoxLayout
        button_layout = QVBoxLayout()
        button_layout.setSpacing(1)
        button_layout.setContentsMargins(4, 4, 4, 4)
        [button_layout.addWidget(group) for group in [draw_connections_group(), draw_coarse_motion_group(), draw_experiments_group(), draw_image_processing_group(), draw_miscellaneous_group(), draw_camera_group()]]
        button_layout.addStretch(1) # Add a stretch at the end to push buttons up

        return button_layout

    def connect_buttons(self):
        # Connections group
        self.nanonis_online_button.clicked.connect(self.connect_nanonis)
        self.tip_status_button.clicked.connect(self.change_tip_status)
        self.view_swap_button.clicked.connect(self.view_toggle)

        self.withdraw_button.clicked.connect(self.toggle_withdraw)
        self.retract_button.clicked.connect(lambda: self.on_coarse_move("Z+"))
        self.nw_button.clicked.connect(lambda: self.on_coarse_move(direction = "NW", horizontal_steps = self.horizontal_steps))
        self.n_button.clicked.connect(lambda: self.on_coarse_move(direction = "N", horizontal_steps = self.horizontal_steps))
        self.ne_button.clicked.connect(lambda: self.on_coarse_move(direction = "NE", horizontal_steps = self.horizontal_steps))
        self.w_button.clicked.connect(lambda: self.on_coarse_move(direction = "W", horizontal_steps = self.horizontal_steps))
        self.e_button.clicked.connect(lambda: self.on_coarse_move(direction = "E", horizontal_steps = self.horizontal_steps))
        self.sw_button.clicked.connect(lambda: self.on_coarse_move(direction = "SW", horizontal_steps = self.horizontal_steps))
        self.s_button.clicked.connect(lambda: self.on_coarse_move(direction = "S", horizontal_steps = self.horizontal_steps))
        self.se_button.clicked.connect(lambda: self.on_coarse_move(direction = "SE", horizontal_steps = self.horizontal_steps))
    
        # Experiments group
        self.start_stop_button.clicked.connect(self.start_stop_experiment)

        # I/O group
        self.scanalyzer_button.clicked.connect(self.launch_scanalyzer)
        self.exit_button.clicked.connect(self.on_exit)

        # Camera
        self.camera_start_button.clicked.connect(self.start_camera)
        self.camera_stop_button.clicked.connect(self.stop_camera)



    # Check TCP_IP connections
    def connect_nanonis(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((TCP_IP, TCP_PORT))
            sock.close()
            sleep(.05) # Short delay before requesting the tip status
            self.nanonis_online = True

            tip_status = self.helper_functions.tip()
            if tip_status == False:
                print("Error retrieving the tip status.")
                self.nanonis_online = False
            else:
                self.tip_status = tip_status
            
            session_path = self.helper_functions.get_session_path()
            if session_path == False:
                print("Error retrieving the session path.")
                self.nanonis_online = False
            else:
                self.session_path = session_path

        except socket.timeout:
            self.nanonis_online = False
        
        finally:
            self.update_buttons()

    # Enable or disable the buttons according to the available hardware connections
    def update_buttons(self):
        if self.nanonis_online:
            self.nanonis_online_button.setText("Nanonis: online")
            self.nanonis_online_button.setStyleSheet("background-color: darkgreen;")
            
            [button.setEnabled(True) for button in self.action_buttons]
            [button.setEnabled(True) for button in self.arrow_buttons]
        else:
            self.nanonis_online_button.setText("Nanonis: offline")
            self.nanonis_online_button.setStyleSheet("background-color: darkred;")
            
            [button.setEnabled(False) for button in self.action_buttons]
            [button.setEnabled(False) for button in self.arrow_buttons]
        
        if not hasattr(self, "tip_status"):
            self.connect_nanonis()
        if not hasattr(self, "tip_status"):
            print("Error: tip status unknown.")
            return False
        
        if self.tip_status.withdrawn:
            self.tip_status_button.setText("Tip status: withdrawn")
            self.tip_status_button.setStyleSheet("background-color: darkred;")
            self.withdraw_button.setText("Land")
            self.withdraw_checkbox.setEnabled(False)
        else:
            if self.tip_status.feedback:
                self.tip_status_button.setText("Tip status: in feedback")
                self.tip_status_button.setStyleSheet("background-color: darkgreen;")
                self.withdraw_button.setText("Withdraw,")
                self.withdraw_checkbox.setEnabled(True)
            else:
                self.tip_status_button.setText("Tip status: constant height")
                self.tip_status_button.setStyleSheet("background-color: darkorange;")
                self.withdraw_button.setText("Land")
                self.withdraw_checkbox.setEnabled(False)

    # Withdraw function
    def toggle_withdraw(self):
        if not hasattr(self, "tip_status"):
            self.connect_nanonis()
        if not hasattr(self, "tip_status"):
            print("Error: tip status unknown.")
            return False
        
        if self.tip_status.withdrawn:
            self.tip_status = self.helper_functions.tip(feedback = True)
        else:
            self.tip_status = self.helper_functions.tip(withdraw = True)
        
        self.update_buttons()
        return True
    
    def change_tip_status(self):
        if not hasattr(self, "tip_status"):
            self.connect_nanonis()
        if not hasattr(self, "tip_status"):
            print("Error: tip status unknown.")
            return False
        
        if self.tip_status.withdrawn: # Land if withdrawn
            self.tip_status = self.helper_functions.tip(feedback = True)
        else: # Toggle the feedback
            self.tip_status = self.helper_functions.tip(feedback = not self.tip_status.feedback)
        
        self.update_buttons()
        return True

    # Experiments (with QThreading)
    def start_stop_experiment(self):
        # If an experiment is running, stop it
        if self.experiment_running:
            self.experiments.stop()
            self.experiment_status.setText("Status: Stopping...")
            return
        
        # Else, if no experiment is running, start it
        # First, check if the TCP connection is okay
        if not self.nanonis_online:
            self.check_nanonis_connection()
            if not self.nanonis_online:
                print("Error! Could not establish a connection to Nanonis")
                self.update_buttons()
                return False

        # Read which experiment will be carried out
        experiment = self.experiment_box.currentText()
        
        # Grid sampling
        if experiment == "Grid sampling":
            
            # Read the current grid from Nanonis and set the pyqtgraph widget size accordingly
            self.grid = self.experiments.get_grid()
            
            if type(self.grid) == bool:
                print("Error! Could not determine the grid.")
                return False
            
            [self.x_grid, self.y_grid] = [self.grid.x_grid, self.grid.y_grid]
            points = int(self.points_box.text())

            # Connect the correct experiment
            try:
                self.request_start.disconnect()
            except:
                pass
            # self.request_start.connect(self.experiments.sample_grid)
            self.request_start.connect(self.experiments.active_measurement_loop)

            # Start the experiment
            self.experiment_running = True
            self.experiment_status.setText("Running (0 %)")
            self.update_start_stop_icon()
            
            self.data_array = np.empty((points, 6), dtype = float)
            self.current_index = 0
            # Emit the grid and points; the call will be queued into the
            # Experiments object's thread and run there.
            self.request_start.emit([2, 1.9, 1.8], None, None, 12, 0)

        else:
            print("Sorry, I don't know this experiment yet.")
            return False

    def update(self, data_chunk):
        chunk_size = data_chunk.shape[0]
        self.data_array[self.current_index : self.current_index + chunk_size] = data_chunk
        self.current_index += chunk_size
        
        xy_points = self.data_array[: self.current_index, :2]
        z_points = self.data_array[: self.current_index, 2]

        z_grid = np.flip(griddata(xy_points, z_points, (self.x_grid, self.y_grid), method = "linear"), axis = 1)

        processed_z_grid = apply_gaussian(z_grid, sigma = 2)

        progress = self.current_index / int(self.points_box.text())
        self.experiment_status.setText(f"Running ({int(100 * progress)} %%)")
        self.image_view.setImage(processed_z_grid, autoRange = True)

    def update_start_stop_icon(self):
        """Set the start/stop button icon according to the experiment state.

        Uses the platform standard media Play/Stop icons when available.
        """
        try:
            if self.experiment_running:
                icon = QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaStop)
            else:
                icon = QApplication.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MediaPlay)
            self.start_stop_button.setIcon(icon)
        except Exception as e:
            print(e)
            # If for some reason standard icons aren't available, do nothing and
            # keep the arrow indicator.
            pass

    def experiment_finished(self):
        self.experiment_status.setText("Experiment stopped")
        self.experiment_running = False
        # Update the start/stop icon back to the start (play) icon
        self.update_start_stop_icon()
        return True

    def closeEvent(self, event):
        """Ensure thread is stopped when the main window is closed."""
        self.experiments.stop() # Set stop flag
        self.experiment_thread.quit() # Quit the thread's event loop
        self.experiment_thread.wait() # Wait for the thread to actually finish
        event.accept()
        return True



    # Manage the camera thread
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
        self.thread = QThread()
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

    # Check camera
    def check_camera_connection(self, argument):
        try:
            cap = cv2.VideoCapture(argument)
        except:
            self.camera_online = False

        if not cap.isOpened(): # Check if the camera opened successfully
            print("Error: Could not open camera.")
            self.camera_online = False
        else:
            cap.release()
            self.camera_online = True
        
        if self.camera_online:
            self.camera_online_button.setText("Camera: online")
            self.camera_online_button.setStyleSheet("background-color: darkgreen;")
        else:
            self.camera_online_button.setText("Camera: offline")
            self.camera_online_button.setStyleSheet("background-color: darkred;")

    # Toggle view between camera and scan
    def view_toggle(self):
        print(f"View index is {self.view_index}")

        self.view_index = 1 - self.view_index
        
        if self.view_index == 1:
            self.view_swap_button.setText("View: camera")
            self.start_camera()
        else:
            self.view_swap_button.setText("View: scan")
            self.stop_camera()
        print(f"View index is {self.view_index}")

    # Start Scanalyzer
    def launch_scanalyzer(self):
        if hasattr(self, "scanalyzer_path"):
            try:
                python_executable = sys.executable
                print(f"Starting script: {python_executable} {self.scanalyzer_path}")
                self.process.start(python_executable, [self.scanalyzer_path])                
            except:
                print("Failed to load Scanalyzer")
        else:
            print("Scanalyzer path unknown")



    # Exit button
    def on_exit(self):
        #if self.is_camera_running:
        #    self.stop_camera()
        print("Thank you for using Scantelligent!")
        QApplication.instance().quit()

    def closeEvent(self, event):
        """Ensures the thread is stopped when the window is closed."""
        #if self.is_camera_running:
        #    self.stop_camera()
        #event.accept()
        pass



# Main program
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())