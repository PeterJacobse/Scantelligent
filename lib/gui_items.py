import re
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
import numpy as np



class PJTargetItem(pg.TargetItem):
    def __init__(self, pos = None, size = 10, pen = "y", tip_text = ""):
        super().__init__(pos = pos, size = size, pen = pen)
        self.size = size
        self.tip_text = tip_text

        self.text_item = pg.TextItem(tip_text, anchor = (0, 1), fill = 'k')
        self.text_item.setParentItem(self)
        self.text_item.hide()
        self.setZValue(10)

    def hoverEvent(self, event) -> None:
        super().hoverEvent(event)

        if event.isEnter():
            self.text_item.setPos(0, 0) # Adjust position as needed
            self.text_item.show()
        elif event.isExit():
            self.text_item.hide()



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
        number_matches = re.findall(r"-?\d+\.?\d*", entered_text)
        if self.number_type == "int": numbers = [int(x) for x in number_matches]
        else: numbers = [float(x) for x in number_matches]
        
        if len(numbers) > 0:
            number = numbers[0]
            
            # Apply limits in case the number is too big or small
            if type(self.limits) == list:
                if number < self.limits[0]: number = self.limits[0]
                if number > self.limits[1]: number = self.limits[1]

            # Add the unit to the number
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



class SliderLineEdit(QtWidgets.QWidget):
    """
    A custom widget combining a QSlider and a QLineEdit, linked together.
    """
    valueChanged = QtCore.pyqtSignal(int)

    def __init__(self, parent = None, min_val = -180, max_val = 180, initial_val = 0):
        super().__init__(parent)
        
        # 1: Create the widgets
        self.slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.line_edit = QtWidgets.QLineEdit()

        # 2: Configure widgets
        self.slider.setRange(min_val, max_val)
        self.slider.setValue(initial_val)
        
        # Ensure only integer values within range can be typed in the line edit
        self.line_edit.setValidator(QtGui.QIntValidator(min_val, max_val))
        self.line_edit.setText(str(initial_val))

        # 3: Set up the layout
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self.slider)
        layout.addWidget(self.line_edit)
        # Remove extra margins from the layout
        layout.setContentsMargins(0, 0, 0, 0) 
        self.setLayout(layout)

        # 4: Connect signals and slots
        self.slider.valueChanged.connect(self._update_line_edit)
        self.line_edit.editingFinished.connect(self._update_slider)
        
        # Connect to the custom signal
        self.slider.valueChanged.connect(lambda: self.valueChanged.emit(self.value()))
        self.line_edit.editingFinished.connect(lambda: self.valueChanged.emit(self.value()))

    def _update_line_edit(self, value):
        self.line_edit.blockSignals(True) 
        self.line_edit.setText(str(value))
        self.line_edit.blockSignals(False)

    def _update_slider(self):
        try:
            value = int(self.line_edit.text())
            self.slider.blockSignals(True)
            self.slider.setValue(value)
            self.slider.blockSignals(False)
        except ValueError:
            # Handle empty or invalid input by resetting to the current slider value
            self.line_edit.setText(str(self.slider.value()))

    def value(self):
        """Returns the current integer value of the combined widget."""
        return self.slider.value()
    
    def setValue(self, value):
        """Sets the value of the combined widget programmatically."""
        self.slider.setValue(value)



class StreamRedirector(QtCore.QObject):
    output_written = QtCore.pyqtSignal(str)

    def __init__(self, parent = None):
        super().__init__(parent)
        self._buffer = ""

    def write(self, text: str) -> None:
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

    def make_groupbox(self, name: str, tooltip: str = "") -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox(name)
        box.setToolTip(tooltip)
        box.setCheckable(True)
        return box

    def make_button(self, name: str, tooltip: str = "", icon = None, rotate_icon: float = 0) -> PJPushButton:
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

    def make_toggle_button(self, name: str, tooltip: str = "", icon = None, rotate_icon: float = 0, flip_icon: bool = False) -> PJPushButton:
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

    def make_label(self, name: str, tooltip: str = "") -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(name)
        label.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        label.setObjectName(name)
        label.setToolTip(tooltip)

        return label

    def make_radio_button(self, name: str, tooltip: str = "", icon = None, rotate_icon: float = 0) -> PJRadioButton:
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
    
    def make_checkbox(self, name: str, tooltip: str = "", icon = None, rotate_icon: float = 0) -> PJCheckBox:
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

    def make_line_edit(self, name: str, tooltip: str = "", unit = None, limits = None, number_type: str = "float") -> PJLineEdit:
        line_edit = PJLineEdit(unit = unit, limits = limits, number_type = number_type)
        line_edit.setObjectName(name)
        line_edit.setToolTip(tooltip)
        line_edit.setText(name)
        line_edit.setStyleSheet("QLineEdit{ background-color: #101010 }")
        
        return line_edit

    def make_progress_bar(self, name, tooltip: str = "") -> PJProgressBar:
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
    
    def make_console(self, name, tooltip) -> PJConsole:
        console = PJConsole()
        console.setObjectName(name)
        console.setToolTip(tooltip)
        
        return console

    def make_slider_line_edit(self, name, tooltip) -> SliderLineEdit:
        slider_line_edit = SliderLineEdit()
        slider_line_edit.setObjectName(name)
        slider_line_edit.setToolTip(tooltip)
        
        return slider_line_edit
    
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

