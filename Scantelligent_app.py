import os
import sys
import yaml
import numpy as np
from PyQt6.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QToolButton, QVBoxLayout, QHBoxLayout, QGridLayout, QWidget, QFileDialog, QButtonGroup, QComboBox, QRadioButton, QGroupBox, QLineEdit
from PyQt6.QtCore import Qt, QSize, QByteArray, QProcess
from pathlib import Path
import pyqtgraph as pg
from pyqtgraph.Qt import QtCore, QtWidgets
from PyQt6.QtGui import QImage, QImageWriter
import scantelligent.functions as st
from datetime import datetime



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

        try: # Read the last scan file from the config yaml file
            with open(self.scantelligent_folder + "\\config.yml", "r") as file:
                config = yaml.safe_load(file)
                self.scanalyzer_path = config.get("scanalyzer_path")
        except:  # Display the dummy scan
            pass

    def draw_buttons(self):
        column_group = QVBoxLayout()
        group1 = QGroupBox()

        group1_box = QVBoxLayout()
        self.scanalyzer_button = QPushButton("Launch Scanalyzer")
        self.exit_button = QPushButton("Exit Scantelligent")
        self.scanalyzer_button.clicked.connect(self.on_launch_scanalyzer)
        self.exit_button.clicked.connect(self.on_exit)
        group1_box.addWidget(self.scanalyzer_button)
        group1_box.addWidget(self.exit_button)

        group1.setLayout(group1_box)

        column_group.addWidget(group1)

        return column_group

    # Start a Scanalyzer instance
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

    # Exit button
    def on_exit(self):
        print("Thank you for using Scantelligent!")
        QApplication.instance().quit()



if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = AppWindow()
    window.show()
    sys.exit(app.exec())