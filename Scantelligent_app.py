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
from scantelligent.functions import get_session_path
from scantelligent.control import coarse_move
import time

# Establish a TCP/IP connection
# TCP_IP = "192.168.236.1"                           # Local host
TCP_IP = "127.0.0.1"
TCP_PORT = 6501                                    # Check available ports in NANONIS > File > Settings Options > TCP Programming Interface
version_number = 13520
camera_argument = 0



class CameraWorker(QObject):
    """
    Worker to handle the time-consuming cv2.VideoCapture loop.
    It runs in a separate QThread and emits frames as NumPy arrays.
    """
    # Signal to send the processed RGB NumPy frame data back to the GUI
    frameCaptured = pyqtSignal(np.ndarray)  
    # Signal to indicate that the capture loop has finished
    finished = pyqtSignal()
    
    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self._running = False
        self.cap = None

    def start_capture(self):
        """Initializes VideoCapture and starts the frame-reading loop."""
        if self._running:
            return

        self._running = True
        # Initialize VideoCapture
        self.cap = cv2.VideoCapture(self.camera_index)
        
        if not self.cap.isOpened():
            print(f"Error: Could not open camera {self.camera_index}. Check connections.")
            self._running = False
            self.finished.emit()
            return
            
        # Optimization: Set a reasonable resolution
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
        # Main video-reading loop controlled by the _running flag
        while self._running:
            ret, frame = self.cap.read()
            if ret:
                # IMPORTANT: Convert BGR (OpenCV default) to RGB 
                # as pyqtgraph expects RGB or Grayscale data.
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                self.frameCaptured.emit(rgb_frame)
            else:
                # Exit loop if frame read fails (e.g., camera unplugged)
                print("Warning: Failed to read frame from camera.")
                break 
                
        # Cleanup code runs when the while loop exits
        if self.cap:
             self.cap.release()
        self._running = False
        self.finished.emit() # Notify the main thread that the work is done

    def stop_capture(self):
        """Sets the flag to stop the capture loop cleanly."""
        self._running = False



class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scantelligent by Peter H. Jacobse") # Make the app window
        self.setGeometry(100, 100, 1400, 800) # x, y, width, height

        # Add ImageView
        pg.setConfigOptions(imageAxisOrder = "row-major")
        self.image_view = pg.ImageView(view = pg.PlotItem())
        self.hist = self.image_view.getHistogramWidget()
        self.hist_item = self.hist.item
        
        # I/O paths
        self.script_path = os.path.abspath(__file__) # The full path of Scanalyzer.py
        self.script_folder = os.path.dirname(self.script_path) # The parent directory of Scanalyzer.py
        self.scantelligent_folder = self.script_folder + "\\scantelligent" # The directory of the scanalyzer package
        self.folder = self.scantelligent_folder
        
        # Default parameters
        self.background_subtraction = "plane"
        self.min_percentile = 2
        self.max_percentile = 98
        self.min_std_dev = 2
        self.max_std_dev = 2
        self.view_index = 0
        
        # Set the central widget of the QMainWindow
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        right_column = self.draw_buttons()

        # Combine nested layouts: image view and right column
        main_layout.addWidget(self.image_view, 3)
        main_layout.addLayout(right_column, 1)
        
        # Ensure the central widget can receive keyboard focus
        central_widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        central_widget.setFocus()

        # Ensure the main window also accepts focus and is active
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFocus()
        self.activateWindow()

        # Handle for external processes
        self.process = QProcess(self)

        try: # Read the config yaml file
            with open(self.scantelligent_folder + "\\config.yml", "r") as file:
                config = yaml.safe_load(file)
                self.scanalyzer_path = config.get("scanalyzer_path")
        except:  # Display the dummy scan
            pass
        
        # Parameter initialization
        self.check_nanonis_connection()
        self.check_camera_connection(camera_argument)
        
        self.thread = None
        self.worker = None
        self.is_camera_running = False



    # Draw all the buttons    
    def draw_buttons(self):
        column_group = QVBoxLayout()

        # Connections group
        connections_box = QGroupBox("Connections (push to check)")
        connections_group = QGridLayout()
        (self.nanonis_online_button, self.tip_status_button, self.mla_online_button) = (QPushButton("Nanonis: offline"), QLabel("Tip status: withdrawn"), QPushButton("MLA: offline"))
        (self.oscillation_on_button, self.camera_online_button, self.view_swap_button) = (QPushButton("MLA oscillation: off"), QPushButton("Camera: offline"), QPushButton("View: scan"))
        self.nanonis_online_button.setStyleSheet("background-color: red;")
        self.mla_online_button.setStyleSheet("background-color: red;")
        self.nanonis_online_button.clicked.connect(self.check_nanonis_connection)
        self.view_swap_button.clicked.connect(self.view_toggle)
        
        connections_group.addWidget(self.nanonis_online_button, 0, 0)
        connections_group.addWidget(self.tip_status_button, 0, 1)
        connections_group.addWidget(self.mla_online_button, 1, 0)
        connections_group.addWidget(self.oscillation_on_button, 1, 1)
        connections_group.addWidget(self.camera_online_button, 2, 0)
        connections_group.addWidget(self.view_swap_button, 2, 1)
        connections_box.setLayout(connections_group)
        column_group.addWidget(connections_box)

        # Coarse motion group
        coarse_motion_box = QGroupBox("Coarse motion (arrow buttons combine checked actions)")
        coarse_motion_group = QHBoxLayout()
        
        # Coarse actions        
        coarse_actions_group = QGridLayout()
        
        self.withdraw_checkbox = QCheckBox()
        self.withdraw_checkbox.setChecked(True)
        coarse_actions_group.addWidget(self.withdraw_checkbox, 0, 0)
        self.withdraw_button = QPushButton("Withdraw,")
        coarse_actions_group.addWidget(self.withdraw_button, 0, 1)
        
        self.retract_checkbox = QCheckBox()
        self.retract_checkbox.setChecked(True)
        coarse_actions_group.addWidget(self.retract_checkbox, 1, 0)
        self.retract_button = QPushButton("Retract")
        coarse_actions_group.addWidget(self.retract_button, 1, 1)
        self.z_steps_box = QLineEdit("10")
        self.retract_button.clicked.connect(lambda: self.on_coarse_move("Z+"))
        self.z_steps = int(self.z_steps_box.text())
        coarse_actions_group.addWidget(self.z_steps_box, 1, 2)
        coarse_actions_group.addWidget(QLabel("steps"), 1, 3)
        
        self.move_checkbox = QCheckBox()
        self.move_checkbox.setChecked(True)
        coarse_actions_group.addWidget(self.move_checkbox, 2, 0)
        coarse_actions_group.addWidget(QLabel("move"), 2, 1)
        self.h_steps_box = QLineEdit("30")
        self.horizontal_steps = 10
        self.h_steps_box.editingFinished.connect(self.on_h_steps_edited)
        coarse_actions_group.addWidget(self.h_steps_box, 2, 2)
        steps_in_direction_label = QLabel("steps in direction")
        coarse_actions_group.addWidget(steps_in_direction_label, 2, 3)
        
        self.go_down_checkbox = QCheckBox()
        self.go_down_checkbox.setChecked(False)
        coarse_actions_group.addWidget(self.go_down_checkbox, 3, 0)
        self.go_down_button = QPushButton("adVance")
        coarse_actions_group.addWidget(self.go_down_button, 3, 1)
        self.minus_z_steps_box = QLineEdit("2")
        coarse_actions_group.addWidget(self.minus_z_steps_box, 3, 2)
        coarse_actions_group.addWidget(QLabel("steps, and"), 3, 3)
        
        self.approach_checkbox = QCheckBox()
        self.approach_checkbox.setChecked(True)
        coarse_actions_group.addWidget(self.approach_checkbox, 4, 0)
        self.approach_button = QPushButton("Auto approach")
        coarse_actions_group.addWidget(self.approach_button, 4, 1)
        
        self.coarse_action_buttons = [self.withdraw_checkbox, self.withdraw_button, self.move_checkbox]
        
        #actions_before_move_group.addLayout(withdraw_group)
        coarse_motion_group.addLayout(coarse_actions_group)
        
        arrow_keys = QWidget()
        arrow_keys_layout = QGridLayout()
        [self.nw_button, self.n_button, self.ne_button, self.w_button, self.zero_button, self.e_button, self.sw_button, self.s_button, self.se_button] = [QToolButton() for _ in range(9)]
        arrow_buttons = [self.nw_button, self.n_button, self.ne_button, self.w_button, self.zero_button, self.e_button, self.sw_button, self.s_button, self.se_button]
        self.nw_button.setText("NW")
        self.nw_button.clicked.connect(lambda: self.on_coarse_move(direction = "NW", horizontal_steps = self.horizontal_steps))
        self.n_button.setArrowType(Qt.ArrowType.UpArrow)
        self.n_button.clicked.connect(lambda: self.on_coarse_move(direction = "N", horizontal_steps = self.horizontal_steps))
        self.ne_button.setText("NE")
        self.ne_button.clicked.connect(lambda: self.on_coarse_move(direction = "NE", horizontal_steps = self.horizontal_steps))
        self.w_button.setArrowType(Qt.ArrowType.LeftArrow)
        self.w_button.clicked.connect(lambda: self.on_coarse_move(direction = "W", horizontal_steps = self.horizontal_steps))
        self.zero_button.setText("0")
        self.e_button.setArrowType(Qt.ArrowType.RightArrow)
        self.e_button.clicked.connect(lambda: self.on_coarse_move(direction = "E", horizontal_steps = self.horizontal_steps))
        self.sw_button.setText("SW")
        self.sw_button.clicked.connect(lambda: self.on_coarse_move(direction = "SW", horizontal_steps = self.horizontal_steps))
        self.s_button.setArrowType(Qt.ArrowType.DownArrow)
        self.s_button.clicked.connect(lambda: self.on_coarse_move(direction = "S", horizontal_steps = self.horizontal_steps))
        self.se_button.setText("SE")
        self.se_button.clicked.connect(lambda: self.on_coarse_move(direction = "SE", horizontal_steps = self.horizontal_steps))

        [arrow_keys_layout.addWidget(arrow_buttons[i], 0, i) for i in range(3)]
        [arrow_keys_layout.addWidget(arrow_buttons[i + 3], 1, i) for i in range(3)]
        [arrow_keys_layout.addWidget(arrow_buttons[i + 6], 2, i) for i in range(3)]
        arrow_keys.setLayout(arrow_keys_layout)
                
        coarse_motion_group.addWidget(arrow_keys)
        coarse_motion_box.setLayout(coarse_motion_group)
        column_group.addWidget(coarse_motion_box)

        # Scan control group
        scan_control_box = QGroupBox("Scan control")
        scan_control_group = QVBoxLayout()

        scan_control_box.setLayout(scan_control_group)
        column_group.addWidget(scan_control_box)
        
        # Image processing group
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
        
        column_group.addWidget(draw_image_processing_group())
        
        """
        im_proc_group = QGroupBox("Image processing")
        im_proc_layout = QVBoxLayout()
        im_proc_layout.setSpacing(1)
        
        back_sub_label = QLabel("Background subtraction")
        back_sub_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        im_proc_layout.addWidget(back_sub_label)
        
        # Background subtraction group
        bg_layout = QGridLayout()
        [self.bg_none_radio, self.bg_plane_radio, self.bg_inferred_radio, self.bg_linewise_radio] = [QRadioButton("None"), QRadioButton("Plane"), QRadioButton("Inferred"), QRadioButton("lineWise")]
        self.bg_buttons = [self.bg_none_radio, self.bg_plane_radio, self.bg_inferred_radio, self.bg_linewise_radio]

        # Group them for exclusive selection
        self.bg_button_group = QButtonGroup(self)
        [self.bg_button_group.addButton(button) for button in self.bg_buttons]
        
        # Set default according to self.background_subtraction
        if self.background_subtraction == "plane":
            self.bg_plane_radio.setChecked(True)
        elif self.background_subtraction == "inferred":
            self.bg_inferred_radio.setChecked(True)
        elif self.background_subtraction == "linewise":
            self.bg_linewise_radio.setChecked(True)
        else:
            self.bg_none_radio.setChecked(True)
        
        # Connect toggle signals
        self.bg_none_radio.toggled.connect(lambda checked: self.on_bg_change("none") if checked else None)
        self.bg_plane_radio.toggled.connect(lambda checked: self.on_bg_change("plane") if checked else None)
        self.bg_inferred_radio.toggled.connect(lambda checked: self.on_bg_change("inferred") if checked else None)
        self.bg_inferred_radio.toggled.connect(lambda checked: self.on_bg_change("linewise") if checked else None)
        self.bg_inferred_radio.setEnabled(False)
        self.bg_linewise_radio.setEnabled(False)

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
        self.sobel_button = QRadioButton("soBel (d/dx + i d/dy)") # Only for initialization
        self.sobel_button.setEnabled(False)
        self.laplace_button = QRadioButton("laplaCe (∇2)") # Only for initialization
        self.laplace_button.setEnabled(False)
        self.gauss_button = QRadioButton("Gaussian") # Only for initialization
        self.gauss_button.setEnabled(False)
        self.fft_button = QRadioButton("Fft") # Only for initialization
        self.fft_button.setEnabled(False)
        matrix_layout.addWidget(self.sobel_button, 0, 0)
        matrix_layout.addWidget(self.laplace_button, 0, 1)
        matrix_layout.addWidget(self.gauss_button, 1, 0)
        matrix_layout.addWidget(self.fft_button, 1, 1)

        im_proc_layout.addLayout(matrix_layout)

        # Add another line
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setLineWidth(1)
        im_proc_layout.addWidget(line)



        # Histogram control group: put the statistics/info label here
        limits_label = QLabel("Set limits")
        limits_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        im_proc_layout.addWidget(limits_label)

        minmax_layout = QHBoxLayout()
        self.toggle_min_button = QPushButton("Toggle min (-)")
        self.toggle_max_button = QPushButton("Toggle max (=)")
        minmax_layout.addWidget(self.toggle_min_button)
        minmax_layout.addWidget(self.toggle_max_button)
        im_proc_layout.addLayout(minmax_layout)

        limits_layout = QGridLayout()
        limits_layout.setSpacing(1)
        
        (self.min_range_box, self.full_scale_button, self.max_range_box) = (QLineEdit(), QPushButton("by fUll data range"), QLineEdit())
        self.min_range_box.setEnabled(False)
        self.max_range_box.setEnabled(False)
        limits_layout.addWidget(self.min_range_box, 0, 0)
        limits_layout.addWidget(self.full_scale_button, 0, 1)
        limits_layout.addWidget(self.max_range_box, 0, 2)
        #self.full_scale_button.clicked.connect(self.on_full_scale)

        (self.min_percentile_box, self.set_percentile_button, self.max_percentile_box) = (QLineEdit(), QPushButton("by data Range percentiles"), QLineEdit())
        self.min_percentile_box.setText(str(self.min_percentile))
        self.max_percentile_box.setText(str(self.max_percentile))
        limits_layout.addWidget(self.min_percentile_box, 1, 0)
        limits_layout.addWidget(self.set_percentile_button, 1, 1)
        limits_layout.addWidget(self.max_percentile_box, 1, 2)

        (self.min_std_dev_box, self.set_std_dev_button, self.max_std_dev_box) = (QLineEdit(), QPushButton("by standard deViations"), QLineEdit())
        self.min_std_dev_box.setText(str(self.min_std_dev))
        self.max_std_dev_box.setText(str(self.max_std_dev))
        limits_layout.addWidget(self.min_std_dev_box, 2, 0)
        limits_layout.addWidget(self.set_std_dev_button, 2, 1)
        limits_layout.addWidget(self.max_std_dev_box, 2, 2)

        (self.min_abs_val_box, self.set_abs_val_button, self.max_abs_val_box) = (QLineEdit(), QPushButton("by Absolute values"), QLineEdit())
        self.min_abs_val_box.setText("0")
        self.max_abs_val_box.setText("1")
        limits_layout.addWidget(self.min_abs_val_box, 3, 0)
        limits_layout.addWidget(self.set_abs_val_button, 3, 1)
        limits_layout.addWidget(self.max_abs_val_box, 3, 2)

        im_proc_layout.addLayout(limits_layout)

        im_proc_group.setLayout(im_proc_layout)
        """
        
        #column_group.addWidget(im_proc_group)
        
        # Macro group
        macro_box = QGroupBox("Macros")
        macro_group = QVBoxLayout()

        macro_box.setLayout(macro_group)
        column_group.addWidget(macro_box)

        # Miscellaneous group
        group1 = QGroupBox("Miscellaneous")
        group1_box = QVBoxLayout()
        self.session_path_button = QPushButton("Get session path")
        self.scanalyzer_button = QPushButton("Launch Scanalyzer")
        self.exit_button = QPushButton("Exit Scantelligent")

        self.session_path_button.clicked.connect(self.on_get_session_path)
        self.scanalyzer_button.clicked.connect(self.on_launch_scanalyzer)
        self.exit_button.clicked.connect(self.on_exit)

        group1_box.addWidget(self.session_path_button)
        group1_box.addWidget(self.scanalyzer_button)
        group1_box.addWidget(self.exit_button)

        group1.setLayout(group1_box)

        column_group.addWidget(group1)
        
        startstop_layout = QHBoxLayout()
        self.start_button = QPushButton("Start Camera")
        self.start_button.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        self.start_button.clicked.connect(self.start_camera)
        startstop_layout.addWidget(self.start_button)
        
        self.stop_button = QPushButton("Stop Camera")
        self.stop_button.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        self.stop_button.setEnabled(False) # Start disabled
        self.stop_button.clicked.connect(self.stop_camera)
        startstop_layout.addWidget(self.stop_button)
        column_group.addLayout(startstop_layout)
        
        return column_group

    def update_buttons(self):
        if self.nanonis_online:
            self.nanonis_online_button.setText("Nanonis: online")
            self.nanonis_online_button.setStyleSheet("background-color: darkgreen;")
            
            [button.setEnabled(True) for button in self.coarse_action_buttons]
            [button.setEnabled(True) for button in [self.n_button, self.e_button]]
        else:
            self.nanonis_online_button.setText("Nanonis: offline")
            self.nanonis_online_button.setStyleSheet("background-color: darkred;")
            
            [button.setEnabled(False) for button in self.coarse_action_buttons]
            [button.setEnabled(False) for button in [self.n_button, self.e_button]]

    def on_h_steps_edited(self):
        self.horizontal_steps = int(self.h_steps_box.text())

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
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)

    def stop_camera(self):
        """Signals the worker to stop and updates the button state immediately."""
        if not self.is_camera_running or not self.worker:
            return

        # 1. Signal the worker to stop its loop (non-blocking)
        self.worker.stop_capture() 
        
        # 2. Immediately disable buttons until cleanup is complete
        self.start_button.setEnabled(False) 
        self.stop_button.setEnabled(False)  
        
        # The final cleanup will be handled by the _post_thread_stop_cleanup slot
        # which is connected to self.thread.finished.

    def _post_camera_stop_cleanup(self):
        """Executes safely in the main thread after QThread.finished is emitted."""
        self.is_camera_running = False
        self.start_button.setEnabled(True) 
        self.stop_button.setEnabled(False)

    # Check TCP_IP connections
    def check_nanonis_connection(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((TCP_IP, TCP_PORT))
            sock.close()
            self.nanonis_online = True
        except socket.timeout:
            self.nanonis_online = False
        self.update_buttons()

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
    def on_launch_scanalyzer(self):
        if hasattr(self, "scanalyzer_path"):
            try:
                python_executable = sys.executable
                self.process.start(python_executable, [self.scanalyzer_path])
                #self.scanalyzer_button.setEnabled(False)
                print(f"Starting script: {python_executable} {self.scanalyzer_path}")
            except:
                print("Failed to load Scanalyzer")
        else:
            print("Scanalyzer path unknown")

    # Coarse motion
    def on_coarse_move(self, direction: str = "N", horizontal_steps: int = 10):
        print(f"I will move {horizontal_steps} steps in the {direction} direction")
        coarse_move(direction, steps = horizontal_steps, xy_voltage = 240, z_voltage = 220)

    def on_get_session_path(self):
        path = get_session_path()
        print(path)
    # def on_change_bias(self):

    # Exit button
    def on_exit(self):
        if self.is_camera_running:
            self.stop_camera()
        print("Thank you for using Scantelligent!")
        QApplication.instance().quit()

    def closeEvent(self, event):
        """Ensures the thread is stopped when the window is closed."""
        if self.is_camera_running:
            self.stop_camera()
        event.accept()



# Main program
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())