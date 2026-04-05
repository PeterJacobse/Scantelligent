import re
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
import numpy as np



class STWidgets:

    class Label(QtWidgets.QLabel):
        def __init__(self, *args, **kwargs):
            text = kwargs.pop("text", None)
            tooltip = kwargs.pop("tooltip", None)
            
            super().__init__()
            
            self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            if isinstance(text, str): self.setText(text)
            if isinstance(tooltip, str): self.setToolTip(tooltip)
        
    class TargetItem(pg.TargetItem):
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

        def setRelPos(self, rel_pos) -> None:
            self.rel_pos = rel_pos
            return

        def setTipText(self, text) -> None:
            self.tip_text = text
            self.text_item.setText(self.tip_text)
            return

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

    class MultiStateButton(QtWidgets.QPushButton):
        """
        A QPushButton with extra method changeToolTip
        """
        def __init__(self, *args, **kwargs):
            name = kwargs.pop("name", None)
            tooltip = kwargs.pop("tooltip", None)
            icon = kwargs.pop("icons", None)
            states = kwargs.pop("states", None)
            click_to_toggle = kwargs.pop("click_to_toggle", True)
            self.state_index = 0
                    
            super().__init__(*args, **kwargs)
            
            if isinstance(name, str): self.setObjectName(name)
            if isinstance(states, list):
                self.states = states
            else:
                # Default for when no different states are provided
                self.states = [{"name": "unchecked", "color": "#101010"}]
            
            if isinstance(tooltip, str): self.states[0].update({"tooltip": tooltip}) # If a global tooltip is provided, it is assigned to be the tooltip of state 0
            if isinstance(icon, QtGui.QIcon): self.states[0].update({"icon": icon}) # If a global icon is provided, it is assigned to be the icon of state 0
            if not isinstance(click_to_toggle, bool): click_to_toggle = True # click_to_toggle = True means that clicking the button automatically toggles its state

            self.setState(0)
            
            # If multiple states are defined for the button, turn it into a toggle button
            if len(self.states) > 1 and click_to_toggle: self.clicked.connect(self.toggleState)

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

        def setState(self, value = 0) -> None:
            if isinstance(value, int): # Index given
                if value > -1: self.state_index = value # Valid index given: set
                else: self.state_index += 1 # No index given: tally
            elif isinstance(value, str): # Name given: find index
                for index, state in enumerate(self.states):
                    state_name = state.get("name")
                    if value == state_name:
                        self.state_index = index
                        break
            else: return
            if self.state_index > len(self.states) - 1: self.state_index = 0 # Roll over if necessary

            self.state = self.states[self.state_index]
            self.state_name = self.state.get("name")
            self.state_tooltip = self.state.get("tooltip")
            self.state_icon = self.state.get("icon")
            self.state_color = self.state.get("color")
            
            if isinstance(self.state_tooltip, str): self.setToolTip(self.state_tooltip)
            if isinstance(self.state_icon, QtGui.QIcon): self.setIcon(self.state_icon)
            if isinstance(self.state_color, str): self.setStyleSheet("QPushButton{ background-color: " + self.state_color + "; icon-size: 22px 22px; }")
            return

        def toggleState(self) -> None:
            self.setState(-1)
            return

    class ComboBox(QtWidgets.QComboBox):
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

    class CheckBox(QtWidgets.QCheckBox):
        """
        A QCheckBox with extra method changeToolTip
        """
        def __init__(self, *args, **kwargs):
            value = kwargs.pop("value", None)
            tooltip = kwargs.pop("tooltip", None)
            icon = kwargs.pop("icons", None)

            super().__init__(*args, **kwargs)

            if isinstance(tooltip, str): self.setToolTip(tooltip)
            if isinstance(icon, QtGui.QIcon): self.setIcon(icon)
            if isinstance(value, str): self.setText(value)
        
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

    class RadioButton(QtWidgets.QRadioButton):
        """
        A QRadioButton with extra method changeToolTip
        """
        def __init__(self, *args, **kwargs):
            tooltip = kwargs.pop("tooltip", None)
            icon = kwargs.pop("icon", None)

            super().__init__(*args, **kwargs)

            self.setStyleSheet("QRadioButton{ icon-size: 22px 22px; }")
            if isinstance(tooltip, str): self.setToolTip(tooltip)
            
            if isinstance(icon, QtGui.QIcon):
                try: self.setIcon(icon)
                except: pass

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

    class PhysicsLineEdit(QtWidgets.QLineEdit):
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

            if not self.hasFocus(): return # Only accept scrolling if it is selected

            pos = self.cursorPosition() - 1 # Cursor position
            if pos < 0: pos = 0

            old_pos = pos
            new_pos = pos
            
            for iteration in range(10):
                new_pos = self.update_number_at_pos(old_pos, new_pos, delta)
                if isinstance(new_pos, bool): break
                elif new_pos < 0: break

        def update_number_at_pos(self, old_pos: int = 0, new_pos: int = 0, delta = 1) -> bool | int:
            txt = self.text()
            text_pos = txt[new_pos] # Text at the cursor position
            # if text_pos == ".": return new_pos - 1
            if not text_pos.isnumeric(): return new_pos - 1 # Only continue if the character at the cursor position is an integer
            number = int(text_pos) # Integer at the cursor position

            if delta > 0: # Scroll up
                new_number = number + 1
                if new_number > 9: new_number = 0
            else: # Scroll down
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

        def keyPressEvent(self, event):
            # Check if Tab is pressed and a completer is set up and visible. If so, use tab to autocomplete
            if event.key() == QtCore.Qt.Key.Key_Tab:
                print("Tab was pressed") # Not working yet
                if self.completer() and self.completer().popup().isVisible():
                    # Get the current completion from the popup
                    completion = self.completer().currentCompletion()
                    self.setText(completion)
                    self.completer().popup().hide()
                    event.accept()
                else:
                    super().keyPressEvent(event)
            else:
                # For all other keys, use default QLineEdit behavior
                super().keyPressEvent(event)

    class ProgressBar(QtWidgets.QProgressBar):
        """
        A QProgressBar with extra method changeToolTip
        """
        def __init__(self, **kwargs):            
            tooltip = kwargs.pop("ttoltip", None)
            
            super().__init__()
            
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

    class GroupBox(QtWidgets.QGroupBox):
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

    class Console(QtWidgets.QTextEdit):
        """
        A QTextEdit with extra method changeToolTip
        """
        def __init__(self, *args, **kwargs):
            tooltip = kwargs.pop("tooltip", None)

            super().__init__()

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

    class Slider(QtWidgets.QSlider):
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
            self.slider = STWidgets.Slider(orientation = orientation, tooltip = tooltip)
            self.line_edit = STWidgets.PhysicsLineEdit(max_width = max_width, unit = unit, limits = limits, digits = digits, tooltip = tooltip)

            if minmax_buttons:
                self.min_button = STWidgets.MultiStateButton(tooltip = "set slider to minimum")
                self.max_button = STWidgets.MultiStateButton(tooltip = "set slider to maximum")

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

    class ImageView(pg.ImageView):
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
        def __init__(self, parent = None, unit = "", phase_0_icon = None, phase_180_icon = None, tooltip = None):
            super().__init__(parent, unit = unit, limits = [-180, 180], initial_val = 0, max_width = 80)
            
            self.phase_0_button = STWidgets.MultiStateButton()
            self.phase_0_button.setToolTip("Set the phase to 0")
            if isinstance(phase_0_icon, QtGui.QIcon): self.phase_0_button.setIcon(phase_0_icon)
            self.phase_180_button = STWidgets.MultiStateButton()
            self.phase_180_button.setToolTip("Set the phase to 180 deg")
            if isinstance(phase_180_icon, QtGui.QIcon): self.phase_180_button.setIcon(phase_180_icon)
            
            self.widget_layout.addWidget(self.phase_0_button)
            self.widget_layout.addWidget(self.phase_180_button)
            # Remove extra margins from the layout
            self.setLayout(self.widget_layout)
            
            self.phase_0_button.clicked.connect(self.set_phase_0)
            self.phase_180_button.clicked.connect(self.set_phase_180)

            if isinstance(tooltip, str): self.setToolTip(tooltip)
            
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

    class GroupBox(QtWidgets.QGroupBox):
        def __init__(self, *args, **kwargs):
            title = kwargs.pop("title", None)
            tooltip = kwargs.pop("tooltip", None)
            
            super().__init__(*args, **kwargs)
            
            if isinstance(title, str): self.setTitle(title)
            if isinstance(tooltip, str): self.setToolTip(tooltip)

    class Completer(QtWidgets.QCompleter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)




def rotate_icon(icon: QtGui.QIcon, angle) -> QtGui.QIcon:
    try:
        pixmap = icon.pixmap(QtCore.QSize(92, 92))
        transform = QtGui.QTransform()
        transform.rotate(angle)

        rotated_pixmap = pixmap.transformed(transform)

        return QtGui.QIcon(rotated_pixmap)

    except Exception as e:
        print(f"Error: {e}")
        return False

def make_layout(orientation: str = "h") -> QtWidgets.QBoxLayout:
    match orientation:
        case "h":
            layout = QtWidgets.QHBoxLayout()
        case "v":
            layout = QtWidgets.QVBoxLayout()
        case _:
            layout = QtWidgets.QGridLayout()

    layout.setSpacing(0)    
    return layout

def make_line(orientation: str = "h", thickness: int = 1) -> QtWidgets.QFrame:
    line = QtWidgets.QFrame()
    match orientation:
        case "h":
            line.setFrameShape(QtWidgets.QFrame.Shape.HLine)
        case _:
            line.setFrameShape(QtWidgets.QFrame.Shape.VLine)
    line.setLineWidth(thickness)
    return line

