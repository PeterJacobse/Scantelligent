import os
import sys
import yaml
import numpy as np
import socket
import cv2
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QToolButton, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QFileDialog, QButtonGroup, QComboBox, QRadioButton, QGroupBox, QLineEdit, QCheckBox
from PyQt6.QtCore import Qt, QSize, QByteArray, QProcess
from pathlib import Path
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from PyQt6.QtGui import QImage, QImageWriter
import scantelligent.functions as st
from datetime import datetime
from scantelligent.functions import get_session_path

# Establish a TCP/IP connection
# TCP_IP = "192.168.236.1"                           # Local host
TCP_IP = "127.0.0.1"
TCP_PORT = 6501                                    # Check available ports in NANONIS > File > Settings Options > TCP Programming Interface
version_number = 13520
camera_argument = 0


class AppWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scantelligent by Peter H. Jacobse") # Make the app window
        self.setGeometry(100, 100, 1200, 800) # x, y, width, height

        # Add ImageView
        pg.setConfigOptions(imageAxisOrder = "row-major")
        self.image_view = pg.ImageView(view = pg.PlotItem())
        self.script_path = os.path.abspath(__file__) # The full path of Scanalyzer.py
        self.script_folder = os.path.dirname(self.script_path) # The parent directory of Scanalyzer.py
        self.scantelligent_folder = self.script_folder + "\\scantelligent" # The directory of the scanalyzer package
        self.folder = self.scantelligent_folder
        
        # Set the central widget of the QMainWindow
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        right_column = self.draw_buttons()

        # Combine nested layouts: image view and left column
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
        self.z_steps = int(self.z_steps_box.text())
        coarse_actions_group.addWidget(self.z_steps_box, 1, 2)
        coarse_actions_group.addWidget(QLabel("steps"), 1, 3)
        
        self.move_checkbox = QCheckBox()
        self.move_checkbox.setChecked(True)
        coarse_actions_group.addWidget(self.move_checkbox, 2, 0)
        coarse_actions_group.addWidget(QLabel("move"), 2, 1)
        self.h_steps_box = QLineEdit("30")
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
        
        #retract_group = QHBoxLayout()
        
        #retract_label = QLabel("Retract 10 steps and")
        #coarse_motion_group.addWidget(retract_label)
        self.horizontal_steps = 10
        
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

        return column_group

    def update_buttons(self):
        if self.nanonis_online:
            self.nanonis_online_button.setText("Nanonis: online")
            self.nanonis_online_button.setStyleSheet("background-color: green;")
            
            [button.setEnabled(True) for button in self.coarse_action_buttons]
            [button.setEnabled(True) for button in [self.n_button, self.e_button]]
        else:
            self.nanonis_online_button.setText("Nanonis: offline")
            self.nanonis_online_button.setStyleSheet("background-color: red;")
            
            [button.setEnabled(False) for button in self.coarse_action_buttons]
            [button.setEnabled(False) for button in [self.n_button, self.e_button]]

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
    def check_camera(self, argument):
        cap = cv2.VideoCapture(argument)

        if not cap.isOpened(): # Check if the camera opened successfully
            print("Error: Could not open camera.")
            exit()
        else:
            print("Success!")
        
        cap.release()

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
        
        if direction == "N": self.nanonis_online = True
        else: self.nanonis_online = False
        self.update_buttons()
        
        if direction == "S":
            print("time to check on the camera")
            self.check_camera(camera_argument)

    def on_get_session_path(self):
        path = get_session_path()
        print(path)
    # def on_change_bias(self):

    # Exit button
    def on_exit(self):
        print("Thank you for using Scantelligent!")
        QApplication.instance().quit()



# Main program
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())