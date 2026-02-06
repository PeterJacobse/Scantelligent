import re
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
import numpy as np



class PJTargetItem(pg.TargetItem):
    clicked = QtCore.pyqtSignal(str)
    position_signal = QtCore.pyqtSignal(float, float)
    
    def __init__(self, pos = None, rel_pos = [], size: int = 10, pen = "y", tip_text: str = "", movable = False):
        super().__init__(pos = pos, size = size, pen = pen, movable = movable)
        self.size = size
        self.tip_text = tip_text
        self.rel_pos = rel_pos # Position relative to the scan frame

        self.text_item = pg.TextItem(tip_text, anchor = (0, 1), fill = 'k')
        self.text_item.setParentItem(self)
        self.text_item.hide()
        self.setZValue(10)

    def hoverEvent(self, event) -> None:
        super().hoverEvent(event)

        if event.isEnter(): self.activate_tooltip()
        elif event.isExit(): self.deactivate_tooltip()
        return

    def activate_tooltip(self) -> None:
        self.text_item.setPos(0, 0)
        self.text_item.show()
        return
    
    def deactivate_tooltip(self) -> None:
        self.text_item.hide()
        return

    def mouseDragEvent(self, event) -> None:
        super().mouseReleaseEvent(event)
        
        # Check if the drag is finished
        if event.isFinish():
            new_pos = self.pos()
            self.position_signal.emit(new_pos.x(), new_pos.y())

    def mouseClickEvent(self, event) -> None:
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            event.accept()
            self.clicked.emit(self.tip_text)
        else:
            super().mouseClickEvent(event)



class PJGroupBox(QtWidgets.QGroupBox):
    """
    A Collapsible QGroupbox
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    


class PJPushButton(QtWidgets.QPushButton):
    """
    A QPushButton with extra method changeToolTip
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def changeToolTip(self, text: str, line: int = 0) -> None:
        """
        Function to change just a single line of a multiline tooltip, instead of the entire tooltip message
        """
        try:
            old_tooltip = self.toolTip()
            tooltip_list = old_tooltip.split("\n")
            
            if line > len(tooltip_list) - 1: # Add a line to the end if the line number is too big
                tooltip_list.append(text)
                new_tooltip = "\n".join(tooltip_list)
            elif line < 0: # Add a line to the front if the line number is negative
                new_tooltip_list = [text]
                [new_tooltip_list.append(item) for item in tooltip_list]
                new_tooltip = "\n".join(new_tooltip_list)
            else: # Replace a line
                tooltip_list[line] = text
                new_tooltip = "\n".join(tooltip_list)

            self.setToolTip(new_tooltip)
        except:
            pass



class PJTogglePushButton(QtWidgets.QPushButton):
    """
    A checkable QPushButton with extra method changeToolTip, and which can flip its icon when toggled
    """
    def __init__(self, parent = None, **kwargs):
        super().__init__(parent)
        self.setCheckable(True)
        self.flip_icon = kwargs.get("flip_icon", False)
        self.toggled.connect(self.smartToggle)
    
    def newIcon(self, icon):
        self.new_icon = icon
        self.flipped_icon = icon
        
        try:
            self.setIcon(icon)
            
            if self.flip_icon:            
                pixmap = self.new_icon.pixmap(QtCore.QSize(92, 92))
                transform = QtGui.QTransform()
                transform.scale(-1, 1)
            
                flipped_pixmap = pixmap.transformed(transform)
                self.flipped_icon = QtGui.QIcon(flipped_pixmap)
        except:
            pass
        return
    
    def changeToolTip(self, text: str, line: int = 0) -> None:
        """
        Function to change just a single line of a multiline tooltip, instead of the entire tooltip message
        """
        try:
            old_tooltip = self.toolTip()
            tooltip_list = old_tooltip.split("\n")
            
            if line > len(tooltip_list) - 1: # Add a line to the end if the line number is too big
                tooltip_list.append(text)
                new_tooltip = "\n".join(tooltip_list)
            elif line < 0: # Add a line to the front if the line number is negative
                new_tooltip_list = [text]
                [new_tooltip_list.append(item) for item in tooltip_list]
                new_tooltip = "\n".join(new_tooltip_list)
            else: # Replace a line
                tooltip_list[line] = text
                new_tooltip = "\n".join(tooltip_list)

            self.setToolTip(new_tooltip)
        except:
            pass
    
    def smartToggle(self) -> None:
        self.blockSignals(True)
        self.toggle()
        if self.isChecked():
            self.setIcon(self.new_icon)
            self.setStyleSheet("QPushButton{ background-color: #101010; icon-size: 22px 22px; }")
            self.setChecked(False)
        else:
            self.setIcon(self.flipped_icon)
            self.setStyleSheet("QPushButton{ background-color: #2020C0; icon-size: 22px 22px; }")
            self.setChecked(True)
        self.blockSignals(False)
        
        return



class PJComboBox(QtWidgets.QComboBox):
    """
    A QComboBox with extra method changeToolTip
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def changeToolTip(self, text: str, line: int = 0) -> None:
        """
        Function to change just a single line of a multiline tooltip, instead of the entire tooltip message
        """
        try:
            old_tooltip = self.toolTip()
            tooltip_list = old_tooltip.split("\n")
            
            if line > len(tooltip_list) - 1: # Add a line to the end if the line number is too big
                tooltip_list.append(text)
                new_tooltip = "\n".join(tooltip_list)
            elif line < 0: # Add a line to the front if the line number is negative
                new_tooltip_list = [text]
                [new_tooltip_list.append(item) for item in tooltip_list]
                new_tooltip = "\n".join(new_tooltip_list)
            else: # Replace a line
                tooltip_list[line] = text
                new_tooltip = "\n".join(tooltip_list)

            self.setToolTip(new_tooltip)
        except:
            pass
        return

    def renewItems(self, items) -> None:
        if isinstance(items, list) or isinstance(items, np.ndarray):
            self.blockSignals(True)
            
            self.clear()
            self.addItems(items)
            
            self.blockSignals(False)
        return

    def toggleIndex(self, delta_index) -> None:
        if not isinstance(delta_index, int) or isinstance(delta_index, float): return
        delta_i = int(delta_index)
        
        self.blockSignals(True)
        
        n = self.count()
        index = self.currentIndex()
        new_index = index + delta_index
        
        if new_index > n - 1: new_index = 0
        if new_index < 0: new_index = n - 1
        self.setCurrentIndex(new_index)
        
        self.blockSignals(False)
        return

    def selectItem(self, desired_item) -> None:
        if not isinstance(desired_item, str): return

        self.blockSignals(True)

        all_items = [self.itemText(i) for i in range(self.count())]
        if desired_item in all_items:
            self.setCurrentText(desired_item)
        
        self.blockSignals(False)
        return

    def selectIndex(self, desired_item) -> None:
        if not isinstance(desired_item, int): return

        self.blockSignals(True)

        self.setCurrentIndex(desired_item)
        
        self.blockSignals(False)
        return



class PJCheckBox(QtWidgets.QCheckBox):
    """
    A QCheckBox with extra method changeToolTip
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def changeToolTip(self, text: str, line: int = 0) -> None:
        """
        Function to change just a single line of a multiline tooltip, instead of the entire tooltip message
        """
        try:
            old_tooltip = self.toolTip()
            tooltip_list = old_tooltip.split("\n")
            
            if line > len(tooltip_list) - 1: # Add a line to the end if the line number is too big
                tooltip_list.append(text)
                new_tooltip = "\n".join(tooltip_list)
            elif line < 0: # Add a line to the front if the line number is negative
                new_tooltip_list = [text]
                [new_tooltip_list.append(item) for item in tooltip_list]
                new_tooltip = "\n".join(new_tooltip_list)
            else: # Replace a line
                tooltip_list[line] = text
                new_tooltip = "\n".join(tooltip_list)

            self.setToolTip(new_tooltip)
        except:
            pass

    def setSilentCheck(self, check_state: bool = True):
        self.blockSignals(True)
        self.setChecked(check_state)
        self.blockSignals(False)
        return



class PJRadioButton(QtWidgets.QRadioButton):
    """
    A QRadioButton with extra method changeToolTip
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    
    def changeToolTip(self, text: str, line: int = 0) -> None:
        """
        Function to change just a single line of a multiline tooltip, instead of the entire tooltip message
        """
        try:
            old_tooltip = self.toolTip()
            tooltip_list = old_tooltip.split("\n")
            
            if line > len(tooltip_list) - 1: # Add a line to the end if the line number is too big
                tooltip_list.append(text)
                new_tooltip = "\n".join(tooltip_list)
            elif line < 0: # Add a line to the front if the line number is negative
                new_tooltip_list = [text]
                [new_tooltip_list.append(item) for item in tooltip_list]
                new_tooltip = "\n".join(new_tooltip_list)
            else: # Replace a line
                tooltip_list[line] = text
                new_tooltip = "\n".join(tooltip_list)

            self.setToolTip(new_tooltip)
        except:
            pass

    def setSilentCheck(self, check_state: bool = True):
        self.blockSignals(True)
        self.setChecked(check_state)
        self.blockSignals(False)
        return



class PJLineEdit(QtWidgets.QLineEdit):
    """
    A QLineEdit with extra method changeToolTip, and which adds a unit after editing is finished
    """
    def __init__(self, parent = None, **kwargs):
        super().__init__(parent)
        self.unit = kwargs.get("unit", None)
        self.limits = kwargs.get("limits", None)
        self.number_type = kwargs.get("number_type", "float")
        if self.unit: self.editingFinished.connect(self.addUnit)
    
    def changeToolTip(self, text: str, line: int = 0) -> None:
        """
        Function to change just a single line of a multiline tooltip, instead of the entire tooltip message
        """
        try:
            old_tooltip = self.toolTip()
            tooltip_list = old_tooltip.split("\n")
            
            if line > len(tooltip_list) - 1: # Add a line to the end if the line number is too big
                tooltip_list.append(text)
                new_tooltip = "\n".join(tooltip_list)
            elif line < 0: # Add a line to the front if the line number is negative
                new_tooltip_list = [text]
                [new_tooltip_list.append(item) for item in tooltip_list]
                new_tooltip = "\n".join(new_tooltip_list)
            else: # Replace a line
                tooltip_list[line] = text
                new_tooltip = "\n".join(tooltip_list)

            self.setToolTip(new_tooltip)
        except:
            pass
    
    def addUnit(self):
        self.blockSignals(True)
        entered_text = self.text()
        
        # Extract the numeric part of what was entered
        regex_pattern = r"([-+]?(?:[0-9]*\.)?[0-9]+(?:[eE][-+]?[0-9]+)?)(?:\s*[a-zA-Zμ°%]+)?"
        number_matches = re.findall(regex_pattern, entered_text)
        if self.number_type == "int": numbers = [int(x) for x in number_matches]
        else: numbers = [float(x) for x in number_matches]
        
        if len(numbers) > 0:
            number = numbers[0]
            
            # Apply limits in case the number is too big or small
            if type(self.limits) == list:
                if number < self.limits[0]: number = self.limits[0]
                if number > self.limits[1]: number = self.limits[1]

            # Add the unit to the number
            if self.number_type == "int":
                number = int(number)
            self.setText(f"{number} {self.unit}")
        else:
            self.setText("")
        
        self.blockSignals(False)
        
        return



class PJProgressBar(QtWidgets.QProgressBar):
    """
    A QProgressBar with extra method changeToolTip
    """
    def __init__(self):
        super().__init__()
    
    def changeToolTip(self, text: str, line: int = 0) -> None:
        """
        Function to change just a single line of a multiline tooltip, instead of the entire tooltip message
        """
        try:
            old_tooltip = self.toolTip()
            tooltip_list = old_tooltip.split("\n")
            
            if line > len(tooltip_list) - 1: # Add a line to the end if the line number is too big
                tooltip_list.append(text)
                new_tooltip = "\n".join(tooltip_list)
            elif line < 0: # Add a line to the front if the line number is negative
                new_tooltip_list = [text]
                [new_tooltip_list.append(item) for item in tooltip_list]
                new_tooltip = "\n".join(new_tooltip_list)
            else: # Replace a line
                tooltip_list[line] = text
                new_tooltip = "\n".join(tooltip_list)

            self.setToolTip(new_tooltip)
        except:
            pass



class PJConsole(QtWidgets.QTextEdit):
    """
    A QTextEdit with extra method changeToolTip
    """
    def __init__(self):
        super().__init__()
    
    def changeToolTip(self, text: str, line: int = 0) -> None:
        """
        Function to change just a single line of a multiline tooltip, instead of the entire tooltip message
        """
        try:
            old_tooltip = self.toolTip()
            tooltip_list = old_tooltip.split("\n")
            
            if line > len(tooltip_list) - 1: # Add a line to the end if the line number is too big
                tooltip_list.append(text)
                new_tooltip = "\n".join(tooltip_list)
            elif line < 0: # Add a line to the front if the line number is negative
                new_tooltip_list = [text]
                [new_tooltip_list.append(item) for item in tooltip_list]
                new_tooltip = "\n".join(new_tooltip_list)
            else: # Replace a line
                tooltip_list[line] = text
                new_tooltip = "\n".join(tooltip_list)

            self.setToolTip(new_tooltip)
        except:
            pass



class PJSlider(QtWidgets.QSlider):
    """
    A QSlider with extra method changeToolTip
    """
    def __init__(self, parent = None, orientation: str = "h"):
        super().__init__(parent)
        if orientation == "h":
            self.setOrientation(QtCore.Qt.Orientation.Horizontal)
        else:
            self.setOrientation(QtCore.Qt.Orientation.Vertical)
    
    def changeToolTip(self, text: str, line: int = 0) -> None:
        """
        Function to change just a single line of a multiline tooltip, instead of the entire tooltip message
        """
        try:
            old_tooltip = self.toolTip()
            tooltip_list = old_tooltip.split("\n")
            
            if line > len(tooltip_list) - 1: # Add a line to the end if the line number is too big
                tooltip_list.append(text)
                new_tooltip = "\n".join(tooltip_list)
            elif line < 0: # Add a line to the front if the line number is negative
                new_tooltip_list = [text]
                [new_tooltip_list.append(item) for item in tooltip_list]
                new_tooltip = "\n".join(new_tooltip_list)
            else: # Replace a line
                tooltip_list[line] = text
                new_tooltip = "\n".join(tooltip_list)

            self.setToolTip(new_tooltip)
        except:
            pass



class PJSliderLineEdit(QtWidgets.QWidget):
    """
    A custom widget combining a QSlider and a QLineEdit, linked together.
    """
    valueChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent = None, min_val = -180, max_val = 180, initial_val = 0, unit = "deg"):
        super().__init__(parent)
        
        # 1: Create the widgets
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.line_edit = PJLineEdit()

        # 2: Configure widgets
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(initial_val)
        
        # Ensure only integer values within range can be typed in the line edit
        self.line_edit.setValidator(QtGui.QIntValidator(min_val, max_val))
        self.line_edit.setText(str(initial_val))

        # 3: Set up the layout
        self.widget_layout = QtWidgets.QHBoxLayout()
        self.widget_layout.addWidget(self.slider)
        self.widget_layout.addWidget(self.line_edit)
        # Remove extra margins from the layout
        self.widget_layout.setContentsMargins(0, 0, 0, 0) 
        self.setLayout(self.widget_layout)

        # 4: Connect signals and slots
        self.slider.valueChanged.connect(self._update_line_edit)
        self.line_edit.editingFinished.connect(self._update_slider)
        
        # Connect to the custom signal
        self.slider.valueChanged.connect(lambda: self.valueChanged.emit(self.value()))
        self.line_edit.editingFinished.connect(lambda: self.valueChanged.emit(self.value()))

    def _update_line_edit(self, value):
        self.line_edit.blockSignals(True) 
        self.line_edit.setText(f"{value} deg")
        self.line_edit.blockSignals(False)

    def _update_slider(self):
        try:
            text = self.line_edit.text()
            if text.startswith("."): text = "0" + text
            regex_pattern = r"[-+]?(?:[0-9]*\.)?[0-9]+(?:[eE][-+]?[0-9]+)?"
            number_matches = re.findall(regex_pattern, text)
            numbers = [int(x) for x in number_matches]
            value = numbers[0]            
            
            self.slider.blockSignals(True)
            self.slider.setValue(value)
            self.slider.blockSignals(False)

            self.line_edit.blockSignals(True) 
            self.line_edit.setText(f"{value} deg")
            self.line_edit.blockSignals(False)
        except ValueError:
            # Handle empty or invalid input by resetting to the current slider value
            self.line_edit.setText(str(self.slider.value()))

    def value(self):
        """Returns the current integer value of the combined widget."""
        return self.slider.value()
    
    def setValue(self, value):
        """Sets the value of the combined widget programmatically."""
        self.slider.setValue(value)

    def changeToolTip(self, text: str, line: int = 0) -> None:
        """
        Function to change just a single line of a multiline tooltip, instead of the entire tooltip message
        """
        try:
            old_tooltip = self.toolTip()
            tooltip_list = old_tooltip.split("\n")
            
            if line > len(tooltip_list) - 1: # Add a line to the end if the line number is too big
                tooltip_list.append(text)
                new_tooltip = "\n".join(tooltip_list)
            elif line < 0: # Add a line to the front if the line number is negative
                new_tooltip_list = [text]
                [new_tooltip_list.append(item) for item in tooltip_list]
                new_tooltip = "\n".join(new_tooltip_list)
            else: # Replace a line
                tooltip_list[line] = text
                new_tooltip = "\n".join(tooltip_list)

            self.setToolTip(new_tooltip)
        except:
            pass



class PJImageView(pg.ImageView):
    position_signal = QtCore.pyqtSignal(float, float)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.view.invertY(False)

    def mouseDoubleClickEvent(self, event):
        # Ensure it's a left double-click
        if event.button() == QtCore.Qt.MouseButton.LeftButton:
            # Get scene position
            pos = event.position()
            
            mapped_pos = self.view.mapToView(pos)
            self.position_signal.emit(mapped_pos.x(), mapped_pos.y())
            return
            
        # Call base class implementation
        super().mouseDoubleClickEvent(event)



class PhaseSlider(PJSliderLineEdit):
    """
    A slider line edit with buttons for controlling a phase
    """
    def __init__(self, parent = None, unit = "", phase_0_icon = None, phase_180_icon = None):
        super().__init__(parent, unit = unit, min_val = -180, max_val = 180, initial_val = 0)
        
        self.phase_0_button = PJPushButton()
        self.phase_0_button.setToolTip("Set the phase to 0")
        if isinstance(phase_0_icon, QtGui.QIcon): self.phase_0_button.setIcon(phase_0_icon)
        self.phase_180_button = PJPushButton()
        self.phase_180_button.setToolTip("Set the phase to 180 deg")
        if isinstance(phase_180_icon, QtGui.QIcon): self.phase_180_button.setIcon(phase_180_icon)
        
        self.widget_layout.addWidget(self.phase_0_button)
        self.widget_layout.addWidget(self.phase_180_button)
        # Remove extra margins from the layout
        self.setLayout(self.widget_layout)
        
        self.phase_0_button.clicked.connect(self.set_phase_0)
        self.phase_180_button.clicked.connect(self.set_phase_180)
        
    def set_phase_0(self):
        self.line_edit.blockSignals(True) 
        self.line_edit.setText(f"0 deg")
        self.line_edit.blockSignals(False)
        self.slider.setValue(0)

    def set_phase_180(self):
        self.line_edit.blockSignals(True) 
        self.line_edit.setText(f"180 deg")
        self.line_edit.blockSignals(False)
        self.slider.setValue(180)



class StreamRedirector(QtCore.QObject):
    output_written = QtCore.pyqtSignal(str)

    def __init__(self, parent = None):
        super().__init__(parent)
        self._buffer = ""

    def write(self, text: str = "") -> None:
        if not text:
            return
        # Accumulate text and only emit complete lines. This avoids
        # emitting lone "\n" chunks which caused extra blank lines
        # in the QTextEdit when using `append` for each write call.
        self._buffer += text
        while "\n" in self._buffer:
            line, self._buffer = self._buffer.split("\n", 1)
            self.output_written.emit(line)
        
        return

    def flush(self) -> None:
        # Emit any remaining partial line (no trailing newline)
        if self._buffer:
            self.output_written.emit(self._buffer)
            self._buffer = ""
        
        return



class GUIItems:
    def __init__(self):
        pass

    def make_groupbox(self, name: str = "", tooltip: str = "") -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox(name)
        box.setToolTip(tooltip)
        box.setCheckable(True)
        return box

    def make_button(self, name: str = "", tooltip: str = "", icon = None, rotate_icon: float = 0) -> PJPushButton:
        button = PJPushButton(name)
        button.setObjectName(name)
        button.setToolTip(tooltip)
        button.setStyleSheet("QPushButton{ background-color: #101010; icon-size: 22px 22px; }")

        if isinstance(icon, QtGui.QIcon):
            if type(rotate_icon) == float or type(rotate_icon) == int and rotate_icon != 0:
                try: icon = self.rotate_icon(icon, rotate_icon)
                except: pass
            try: button.setIcon(icon)
            except: pass
        return button

    def make_toggle_button(self, name: str = "", tooltip: str = "", icon = None, rotate_icon: float = 0, flip_icon: bool = False) -> PJPushButton:
        button = PJTogglePushButton(name, flip_icon = flip_icon)
        button.setObjectName(name)
        button.setToolTip(tooltip)
        button.setStyleSheet("QPushButton{ background-color: #101010; icon-size: 22px 22px; }")

        if isinstance(icon, QtGui.QIcon):
            if type(rotate_icon) == float or type(rotate_icon) == int and rotate_icon != 0:
                try: icon = self.rotate_icon(icon, rotate_icon)
                except: pass
            try: button.newIcon(icon)
            except: pass
        return button

    def make_label(self, name: str = "", tooltip: str = "") -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(name)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        label.setObjectName(name)
        label.setToolTip(tooltip)

        return label

    def make_radio_button(self, name: str = "", tooltip: str = "", icon = None, rotate_icon: float = 0) -> PJRadioButton:
        button = PJRadioButton(name)
        button.setObjectName(name)
        button.setToolTip(tooltip)
        button.setStyleSheet("QRadioButton{ icon-size: 22px 22px; }")

        if isinstance(icon, QtGui.QIcon):
            if type(rotate_icon) == float or type(rotate_icon) == int and rotate_icon != 0:
                try: icon = self.rotate_icon(icon, rotate_icon)
                except: pass
            try: button.setIcon(icon)
            except: pass
        return button
    
    def make_checkbox(self, name: str = "", tooltip: str = "", icon = None, rotate_icon: float = 0) -> PJCheckBox:
        box = PJCheckBox(name)
        box.setObjectName(name)
        box.setToolTip(tooltip)
        box.setStyleSheet("QCheckBox{ icon-size: 22px 22px; }")
        
        if isinstance(icon, QtGui.QIcon):
            if type(rotate_icon) == float or type(rotate_icon) == int and rotate_icon != 0:
                try: icon = self.rotate_icon(icon, rotate_icon)
                except: pass
            try: box.setIcon(icon)
            except: pass
        return box
    
    def make_combobox(self, name: str = "", tooltip: str = "", items: list = []) -> PJComboBox:
        box = PJComboBox()
        box.setObjectName(name)
        box.setToolTip(tooltip)
        box.setStyleSheet("QCombobox{ background-color: #101010; icon-size: 22px 22px; }")

        if len(items) > 0: box.addItems(items)
        
        return box

    def make_line_edit(self, name: str = "", tooltip: str = "", unit = None, limits = None, number_type: str = "float") -> PJLineEdit:
        line_edit = PJLineEdit(unit = unit, limits = limits, number_type = number_type)
        line_edit.setObjectName(name)
        line_edit.setToolTip(tooltip)
        line_edit.setText(name)
        line_edit.setStyleSheet("QLineEdit{ background-color: #101010 }")
        
        return line_edit

    def make_progress_bar(self, name: str = "", tooltip: str = "") -> PJProgressBar:
        bar = PJProgressBar()
        
        bar.setObjectName(name)
        bar.setMinimum(0)
        bar.setMaximum(100)
        bar.setValue(0)
        bar.setToolTip(tooltip)
        
        return bar

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
    
    def make_console(self, name: str = "", tooltip: str = "") -> PJConsole:
        console = PJConsole()
        console.setObjectName(name)
        console.setToolTip(tooltip)
        
        return console

    def make_slider_line_edit(self, name: str = "", tooltip: str = "") -> PJSliderLineEdit:
        slider_line_edit = PJSliderLineEdit()
        slider_line_edit.setObjectName(name)
        slider_line_edit.setToolTip(tooltip)
        
        return slider_line_edit

    def make_slider(self, name: str = "", tooltip: str = "", orientation: str = "h") -> PJSlider:
        slider = PJSlider(orientation = orientation)
        slider.setObjectName(name)
        slider.setToolTip(tooltip)
        slider.setMinimum(-10)
        slider.setMaximum(10)
        slider.setValue(10)
        
        return slider

    def make_phase_slider(self, name: str = "", tooltip: str = "", unit: str = "deg", phase_0_icon = None, phase_180_icon = None) -> PhaseSlider:
        phase_slider = PhaseSlider(unit = unit, phase_0_icon = phase_0_icon, phase_180_icon = phase_180_icon)
        phase_slider.setObjectName(name)
        phase_slider.setToolTip(tooltip)
        
        return phase_slider        

    def make_image_view(self) -> PJImageView:
        pg.setConfigOptions(imageAxisOrder = "row-major", antialias = True)

        plot_item = pg.PlotItem()
        image_view = PJImageView(view = plot_item)      
        
        return image_view
    
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

