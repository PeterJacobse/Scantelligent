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
        tooltip = kwargs.pop("tooltip", None)
        super().__init__(*args, **kwargs)

        if isinstance(tooltip, str): self.setToolTip(tooltip)


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
        self.name = kwargs.pop("name") if "name" in kwargs.keys() else None
        self.tooltip = kwargs.pop("tooltip") if "tooltip" in kwargs.keys() else None
        self.max_width = kwargs.pop("max_width") if "max_width" in kwargs.keys() else None
        self.style_sheet = kwargs.pop("style_sheet") if "style_sheet" in kwargs.keys() else None
        items = kwargs.pop("items") if "items" in kwargs.keys() else None
        
        super().__init__(*args, **kwargs)
        
        self.set_defaults()
        if isinstance(items, list): self.addItems(items)


    
    def set_defaults(self) -> None:
        if isinstance(self.name, str): self.setObjectName(self.name)
        if isinstance(self.tooltip, str): self.setToolTip(self.tooltip)
        if isinstance(self.max_width, int):
            self.setMaximumWidth(self.max_width)
        else:
            self.setMaximumWidth(150)
        if isinstance(self.style_sheet, str):
            self.setStyleSheet(self.style_sheet)
        else:
            self.setStyleSheet("QCombobox{ background-color: #101010; icon-size: 22px 22px; }")
    
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



class PhysicalLineEdit(QtWidgets.QLineEdit):
    """
    A QLineEdit with capabilities to efficiently add units, extract and set values
    """
    def __init__(self, parent = None, **kwargs):
        self.value = kwargs.pop("value", None)
        self.tooltip = kwargs.pop("tooltip", None)
        self.unit = kwargs.pop("unit", None)
        self.limits = kwargs.pop("limits", None)
        self.max_width = kwargs.pop("max_width", None)
        self.style_sheet = kwargs.pop("style_sheet", None)
        self.digits = kwargs.pop("digits", None)
        self.block = kwargs.pop("block", False)
        
        super().__init__(parent)
        
        self.set_defaults()
        if not self.block: self.editingFinished.connect(self.addUnit) 
    
    def set_defaults(self) -> None:
        if isinstance(self.value, str) or isinstance(self.value, int) or isinstance(self.value, float): self.setValue(self.value)
        if isinstance(self.tooltip, str): self.setToolTip(self.tooltip)
        if isinstance(self.max_width, int):
            self.setMaximumWidth(self.max_width)
        else:
            pass
            # self.setMaximumWidth(150)
        if isinstance(self.style_sheet, str):
            self.setStyleSheet(self.style_sheet)
        else:
            self.setStyleSheet("QLineEdit{ background-color: #101010 }")
        
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

        return

    def setDigits(self, digits: int) -> None:
        if isinstance(digits, int): self.digits = digits
        return

    def setLimits(self, limits: list) -> None:
        if isinstance(limits, list): self.limits = limits
        return

    def setUnit(self, unit: str = "") -> None:
        if isinstance(unit, str):
            self.unit = unit
            self.addUnit()
        return

    def addUnit(self) -> None:
        number = self.getValue()
        
        self.blockSignals(True)
        if isinstance(self.unit, str): self.setText(f"{number} {self.unit}")
        else: self.setText(f"{number}")
        self.blockSignals(False)
        return

    def getValue(self) -> float | str:
        entered_text = self.text()
        
        # Extract the numeric part of what was entered
        regex_pattern = r"([-+]?(?:[0-9]*\.)?[0-9]+(?:[eE][-+]?[0-9]+)?)(?:\s*[a-zA-Zμ°%]+)?"
        number_matches = re.findall(regex_pattern, entered_text)
        
        if isinstance(self.digits, int) and self.digits < 1: numbers = [int(x) for x in number_matches]
        else: numbers = [float(x) for x in number_matches]
        
        if len(numbers) > 0:
            number = numbers[0]
            
            # Apply limits in case the number is too big or small
            if isinstance(self.limits, list):
                if number < self.limits[0]: number = self.limits[0]
                if number > self.limits[1]: number = self.limits[1]

            # Add the unit to the number
            if isinstance(self.digits, int):
                number = round(number, self.digits)
            if isinstance(self.digits, int) and self.digits < 1 < 1:
                number = int(number)
            
            return number

        return entered_text

    def setValue(self, value) -> None:
        # Method for programatically setting a value or str
        if isinstance(value, int) or isinstance(value, float):
            number = value

            if isinstance(self.digits, int):
                number = round(number, self.digits)
                if self.digits < 1: number = int(number)

            if isinstance(self.unit, str):
                self.setText(f"{number} {self.unit}")
            else:
                self.setText(f"{number}")
        
        else:
            self.setText(f"{value}")
        return

    def wheelEvent(self, event) -> None:
        delta = event.angleDelta().y() # Scroll direction

        if not self.hasFocus(): return

        pos = self.cursorPosition() - 1 # Cursor position
        if pos < 0: return

        old_pos = pos
        new_pos = pos
        
        for iteration in range(10):
            new_pos = self.update_number_at_pos(old_pos, new_pos, delta)
            if isinstance(new_pos, bool): break
            elif new_pos < 0: break
        
    def update_number_at_pos(self, old_pos: int = 0, new_pos: int = 0, delta = 1) -> bool | int:
        txt = self.text()
        text_pos = txt[new_pos] # Text at the cursor position
        if text_pos == ".": return new_pos + 1
        elif not text_pos.isnumeric(): return False # Only continue if the character at the cursor position is an integer
        number = int(text_pos) # Integer at the cursor position

        if delta > 0: # Scroll down
            new_number = number + 1
            if new_number > 9: new_number = 0
        else: # Scroll up
            new_number = number - 1
            if new_number < 0: new_number = 9
            
        new_txt = txt[:new_pos] + str(new_number) + txt[new_pos + 1:]
        if new_txt[0] == 0: # Delete leading zero if it arises
            new_txt = new_txt[1:]
            self.setCursorPosition(old_pos)
        else:
            self.setText(new_txt)
            self.setCursorPosition(old_pos + 1)

        if delta > 0 and new_number == 0: # Roll over to the next digit
            return new_pos - 1
        if delta < 0 and new_number == 9: # Roll over to the next digit
            return new_pos - 1

        return True



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



class PJGroupBox(QtWidgets.QGroupBox):
    def __init__(self, title, parent = None, *args, **kwargs):
        super().__init__(title, parent)
        
        if "name" in kwargs: self.setObjectName(kwargs["name"])
        if "tooltip" in kwargs: self.setToolTip(kwargs["tooltip"])
        
        self.setCheckable(True)
        self.setChecked(True)
        
        self.content_container = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content_container)
                
        self.toggled.connect(self.content_container.setVisible)
        self.content_container.setVisible(True)
    
    

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
    def __init__(self, parent = None, orientation: str = "h", tooltip: str = ""):
        super().__init__(parent)
        if orientation == "h":
            self.setOrientation(QtCore.Qt.Orientation.Horizontal)
        else:
            self.setOrientation(QtCore.Qt.Orientation.Vertical)
        if isinstance(tooltip, str): self.setToolTip(tooltip)

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

    def __init__(self, parent = None, tooltip: str = "", limits: list = [-180, 180], initial_val: float = 0, digits: int = 0, max_width = 150, unit = None, orientation: str = "h", minmax_buttons: bool = False):
        super().__init__(parent)
        [self.min_val, self.max_val] = limits

        # 1: Create the widgets
        self.slider = PJSlider(orientation = orientation, tooltip = tooltip)
        self.line_edit = PhysicalLineEdit(max_width = max_width, unit = unit, limits = limits, digits = digits, tooltip = tooltip)

        if minmax_buttons:
            self.min_button = PJPushButton(tooltip = "set slider to minimum")
            self.max_button = PJPushButton(tooltip = "set slider to maximum")

        # 2: Configure widgets
        self.slider.setRange(self.min_val, self.max_val)
        [widget.setValue(initial_val) for widget in [self.slider, self.line_edit]]

        # 3: Set up the layout
        if orientation == "h": self.widget_layout = QtWidgets.QHBoxLayout()
        else: self.widget_layout = QtWidgets.QVBoxLayout()
        
        if minmax_buttons:
            if orientation == "v": self.widget_layout.addWidget(self.max_button)
            else: self.widget_layout.addWidget(self.min_button)
        self.widget_layout.addWidget(self.slider)
        self.widget_layout.addWidget(self.line_edit)
        if minmax_buttons:
            if orientation == "v": self.widget_layout.addWidget(self.min_button)
            else: self.widget_layout.addWidget(self.max_button)
        
        # Remove extra margins from the layout
        self.widget_layout.setContentsMargins(0, 0, 0, 0) 
        self.setLayout(self.widget_layout)

        # 4: Connect signals and slots
        self.slider.valueChanged.connect(self._update_line_edit)
        self.line_edit.editingFinished.connect(self._update_slider)

        if minmax_buttons:
            self.min_button.clicked.connect(lambda: self.setValue(self.min_val))
            self.max_button.clicked.connect(lambda: self.setValue(self.max_val))

        # Connect to the custom signal
        self.slider.valueChanged.connect(lambda: self.valueChanged.emit(self.getValue()))
        self.line_edit.editingFinished.connect(lambda: self.valueChanged.emit(self.getValue()))



    def _update_line_edit(self, value):
        self.line_edit.blockSignals(True) 
        self.line_edit.setValue(value)
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
            self.line_edit.setValue(value)
            self.line_edit.blockSignals(False)
        except ValueError:
            # Handle empty or invalid input by resetting to the current slider value
            self.line_edit.setText(str(self.slider.value()))

    def getValue(self):
        """Returns the current integer value of the combined widget."""
        return self.slider.value()
    
    def setValue(self, value):
        """Sets the value of the combined widget programmatically."""
        if value < self.min_val: value = self.min_val
        elif value > self.max_val: value = self.max_val
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



class PhaseSlider(SliderLineEdit):
    """
    A slider line edit with buttons for controlling a phase
    """
    def __init__(self, parent = None, unit = "", phase_0_icon = None, phase_180_icon = None):
        super().__init__(parent, unit = unit, min_val = -180, max_val = 180, initial_val = 0, max_width = 80)
        
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
        
        self.set_phase_0()
        
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



# Class for making the above widgets and setting their defaults simultaneously.
# May be deprecated by simply setting the defaults in the widgets themselves
class GUIItems:
    def __init__(self):
        pass

    def make_groupbox(self, name: str = "", tooltip: str = "") -> QtWidgets.QGroupBox:
        box = QtWidgets.QGroupBox(name)
        box.setToolTip(tooltip)
        box.setCheckable(False)
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

