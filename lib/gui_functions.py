from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
from typing import Callable



class GUIFunctions:
    def __init__(self):
        pass

    def make_groupbox(self, name: str, description: str = "") -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox(name)
        box.setToolTip(description)
        box.setCheckable(True)
        return box

    def make_button(self, name: str, func: Callable, description: str = "", icon = None, rotate_degrees: float = 0, key_shortcut = None, parent = None) -> QtWidgets.QPushButton:
        button = QtWidgets.QPushButton(name)
        button.setObjectName(name)
        button.clicked.connect(lambda checked, f = func: f())
        button.setToolTip(description)

        if isinstance(key_shortcut, QtCore.Qt.Key):
            if parent is not None:
                shortcut = QtGui.QShortcut(QtGui.QKeySequence(key_shortcut), parent)
                shortcut.activated.connect(func)
            else:
                button.setShortcut(key_shortcut)

        if isinstance(icon, QtGui.QIcon):
            if type(rotate_degrees) == float or type(rotate_degrees) == int and rotate_degrees != 0:
                try: icon = self.rotate_icon(icon, rotate_degrees)
                except: pass
            try: button.setIcon(icon)
            except: pass
        return button
    
    def make_label(self, name: str, description: str = "", icon_path = None) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(name)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        label.setObjectName(name)
        label.setToolTip(description)

        if isinstance(icon_path, str):
            try:
                icon = QtGui.QIcon(icon_path)
                label.setIcon(icon)
            except:
                pass
        return label
    
    def make_radio_button(self, name: str, description: str = "", icon = None, rotate_degrees: float = 0) -> QtWidgets.QRadioButton:
        button = QtWidgets.QRadioButton(name)
        button.setObjectName(name)
        button.setToolTip(description)

        if isinstance(icon, QtGui.QIcon):
            if type(rotate_degrees) == float or type(rotate_degrees) == int and rotate_degrees != 0:
                try: icon = self.rotate_icon(icon, rotate_degrees)
                except: pass
            try: button.setIcon(icon)
            except: pass
        return button
    
    def make_checkbox(self, name: str, description: str = "", icon = None, rotate_degrees: float = 0) -> QtWidgets.QCheckBox:
        box = QtWidgets.QCheckBox(name)
        box.setObjectName(name)
        box.setToolTip(description)
        
        if isinstance(icon, QtGui.QIcon):
            if type(rotate_degrees) == float or type(rotate_degrees) == int and rotate_degrees != 0:
                try: icon = self.rotate_icon(icon, rotate_degrees)
                except: pass
            try: box.setIcon(icon)
            except: pass
        return box
    
    def make_combobox(self, name: str = "", description: str = "", func = None, items: list = []) -> QtWidgets.QComboBox:
        box = QtWidgets.QComboBox()
        box.setObjectName(name)
        box.setToolTip(description)

        if len(items) > 0: box.addItems(items)

        if callable(func): box.currentIndexChanged.connect(lambda index, f = func: f(index))
        return box
    
    def make_line_edit(self, name: str, description: str = "", icon = None, key_shortcut = None, rotate_degrees: float = 0) -> QtWidgets.QLineEdit:
        button = QtWidgets.QLineEdit()
        button.setObjectName(name)
        button.setToolTip(description)
        button.setText(name)

        if isinstance(icon, QtGui.QIcon):
            if type(rotate_degrees) == float or type(rotate_degrees) == int and rotate_degrees != 0:
                try: icon = self.rotate_icon(icon, rotate_degrees)
                except: pass
            try: button.setIcon(icon)
            except: pass
        return button 
    
    def make_layout(self, orientation: str = "h") -> QtWidgets.QLayout:
        match orientation:
            case "h":
                layout = QtWidgets.QHBoxLayout()
            case "v":
                layout = QtWidgets.QVBoxLayout()
            case _:
                layout = QtWidgets.QGridLayout()
        
        layout.setSpacing(1)
        return layout
    
    def line_widget(self, orientation: str = "v", thickness: int = 1) -> QtWidgets.QFrame:
        line = QtWidgets.QFrame()
        match orientation:
            case "h":
                line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
            case _:
                line.setFrameShape(QtWidgets.QFrame.Shape.VLine)
        line.setLineWidth(thickness)
        return line

    def rotate_icon(self, icon, angle) -> QtGui.QIcon:
        try:
            pixmap = icon.pixmap(QtCore.QSize(92, 92))
            transform = QtGui.QTransform()
            transform.rotate(angle)

            rotated_pixmap = pixmap.transformed(transform)

            return QtGui.QIcon(rotated_pixmap)
    
        except Exception as e:
            print(f"Error: {e}")
            return False



class HoverTargetItem(pg.TargetItem):
    def __init__(self, pos = None, size = 10, tip_text = ""):
        super().__init__(pos, size)
        self.size = size
        self.tip_text = tip_text

        self.text_item = pg.TextItem(tip_text, anchor = (0, 1), fill = 'k')
        self.text_item.setParentItem(self)
        self.text_item.hide()

    def hoverEvent(self, event):
        super().hoverEvent(event)

        if event.isEnter():
            self.text_item.setPos(0, 0) # Adjust position as needed
            self.text_item.show()
        elif event.isExit():
            self.text_item.hide()
