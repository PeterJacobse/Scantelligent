import re, types, os, h5py
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
import numpy as np



class SCTWidgets:
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

    class ScanItem(pg.ImageItem):
        def __init__(self, name: str = "", scan: np.ndarray = None, grid: dict = {}):            
            super().__init__()
            self.setOpts(axisOrder = "row-major")
            
            # Instantiate with dummy data. To be overridden later
            self.name = name
            if isinstance(scan, np.ndarray): self.scan = scan
            else: self.scan = np.empty((2, 2, 2, 2), dtype = float)
            self.pixels = 2
            self.lines = 2
            self.directions = 2
            self.direction_names = np.array(["forward", "backward"])
            self.direction_index = 0
            self.direction = "forward"
            self.n_channels = 2
            self.channel_names = np.array(["channel 0", "channel 1"])
            self.channel_index = 0
            self.channel = "channel 0"
            self.setImage(self.scan[0, 0])
            self.rank = 4
            
            if isinstance(grid, dict) and "offset (nm)" in grid.keys() and "scan_range (nm)" in grid.keys() and "angle (deg)" in grid.keys():
                self.grid = grid
                self.setGrid(grid)


        
        def setName(self, name: str = "") -> None:
            self.name = name
            return
        
        def setScan(self, scan: np.ndarray) -> None: # Saves a 4D scan array, from which slices can be retrieved
            shape = scan.shape
            self.rank = len(shape)
            
            if self.rank < 2 or self.rank > 4: return # Only 2D images, 3D and 4D arrays supported at this time
            self.scan = scan
            
            self.directions = 1
            self.n_channels = 1
            match self.rank:
                case 2: # Flat image
                    self.pixels = shape[0]
                    self.lines = shape[1]
                    self.setImage(scan)
                case 3: # x, y and channel axes
                    self.n_channels = shape[0]
                    self.pixels = shape[1]
                    self.lines = shape[2]
                    self.setImage(scan[0])
                case 4: # x, y and channel axes and forward/backward
                    self.directions = 2
                    self.n_channels = shape[1]
                    self.pixels = shape[2]
                    self.lines = shape[3]
                    self.setImage(scan[0, 0])
            return

        def setChannels(self, channels: list | np.ndarray) -> None:
            self.channel_names = np.array(channels, dtype = str)
            return
        
        def setChannel(self, channel: str | int) -> None:
            if isinstance(channel, str) and channel in self.channel_names:
                for index, name in enumerate(self.channel_names):
                    if name == channel:
                        self.channel_index = index
                        break
            elif isinstance(channel, int) and -1 < channel < len(self.channel_names):
                self.channel_index = channel
            return

        def setDirection(self, direction: str | int) -> None:
            if direction == "forward" or direction == 0: self.direction_index = 0
            else: self.direction_index = 1
            return

        def getImage(self, axis: int = 0, channel: str | int = None, direction: str | int = None) -> np.ndarray:
            if isinstance(channel, str | int): self.setChannel(channel)
            if isinstance(direction, str | int): self.setDirection(direction)
            
            match self.rank:
                case 2: # The scan is a flat image
                    data_slice = self.scan
                case 3:
                    data_slice = self.scan[self.channel_index]
                case 4:
                    data_slice = self.scan[self.direction_index, self.channel_index]
                case _:
                    pass
            return data_slice

        def setGrid(self, grid: dict) -> None:
            """
            Parses the provided grid dictionary and applies the correct scaling, centering, and rotation transformations.
            """
            [pixels, lines, scan_range, offset, angle] = [grid.get(key, None) for key in ["pixels", "lines", "scan_range (nm)", "offset (nm)", "angle (deg)"]]
            [width, height] = [scan_range[index] for index in range(2)]
            [x, y] = [offset[index] for index in range(2)]
            
            if isinstance(pixels, int): self.pixels = pixels # Update the pixels and lines attributes if explicitly passed
            if isinstance(lines, int): self.lines = lines
            
            pixels = self.pixels
            lines = self.lines
            
            pixel_width = width / pixels
            pixel_height = height / lines
                        
            for value in [pixels, lines, width, height, angle]:
                if not isinstance(value, float | int): return
                        
            self.resetTransform()
            transform = QtGui.QTransform()
            transform.rotate(-angle)
            transform.scale(pixel_width, pixel_height)
            transform.translate(-.5 * pixels, -.5 * lines)
            self.setTransform(transform)
            self.setPos(x, y)
            return

    class MultiStateButton(QtWidgets.QToolButton):
        """
        A QToolButton that holds a number (list) of states, allows toggling through them, and changes the button according to the details of each state
        """
        def __init__(self, *args, **kwargs):
            name = kwargs.pop("name", None)
            tooltip = kwargs.pop("tooltip", None)
            icon = kwargs.pop("icons", None)
            states = kwargs.pop("states", None)
            click_to_toggle = kwargs.pop("click_to_toggle", True)
            size = kwargs.pop("size", None)
            self.state_index = 0
                    
            super().__init__(*args, **kwargs)
           
            if isinstance(name, str): self.setObjectName(name)
            if isinstance(states, list):
                self.states = states
            else:
                # Default for when no different states are provided
                self.states = [{"name": "unchecked", "color": "#101010"}]
            
            self.button_size = 22
            if isinstance(size, int): self.button_size = size
            self.setFixedSize(self.button_size + 8, self.button_size + 8)
            if isinstance(tooltip, str): self.states[0].update({"tooltip": tooltip}) # If a global tooltip is provided, it is assigned to be the tooltip of state 0
            if isinstance(icon, QtGui.QIcon): self.states[0].update({"icon": icon}) # If a global icon is provided, it is assigned to be the icon of state 0
            if not isinstance(click_to_toggle, bool): click_to_toggle = True # click_to_toggle = True means that clicking the button automatically toggles its state

            self.setState(0)
            self.setToggleable(click_to_toggle)



        def changeToolTip(self, text: str, line: int = 0) -> None:
            """
            Function to change just a single line of a multiline tooltip, instead of the entire tooltip message
            """
            try:
                for state in self.states:
                    old_tooltip = state.get("tooltip")
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
                    
                    state.update({"tooltip": new_tooltip})
                
                # Set the new tooltip
                self.setToolTip(self.state.get("tooltip"))
            except:
                pass

        def setToggleable(self, value: bool = True) -> None:
            if len(self.states) > 1 and value: self.clicked.connect(self.toggleState)
            else:
                try: self.clicked.disconnect(self.toggleState)
                except: pass
            return

        def setSize(self, value: int = 0) -> None:
            self.button_size = value
            self.setFixedSize(self.button_size + 8, self.button_size + 8)
            return

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
            if isinstance(self.state_color, str): self.setStyleSheet("QToolButton{ background-color: " + self.state_color + f"; icon-size: {self.button_size}px {self.button_size}px" + "; }")
            return

        def toggleState(self) -> None:
            self.setState(-1) # Triggers an increase in state_index by 1
            return

        def setStates(self, states: list[dict] = [{}]) -> None:
            if isinstance(states, list) and isinstance(states[0], dict):
                self.states = states
                self.setState(0)            
            return
        
        def isChecked(self) -> bool:
            return bool(self.state_index) # Returns True unless the state_index is 0

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
            
            self.setDefaults()
            if isinstance(items, list): self.addItems(items)


        
        def setDefaults(self) -> None:
            if isinstance(self.name, str): self.setObjectName(self.name)
            #if isinstance(self.tooltip, str): self.setToolTip(self.tooltip)
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

        def getItems(self) -> list:
            return [self.itemText(index) for index in range(self.count())]

        def toggleIndex(self, delta_index: int = 1) -> None:
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

    class CheckBoxOld(QtWidgets.QCheckBox):
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
            
            self.setStyleSheet("QCheckBox{ icon-size: 22px 22px; }")
        
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

    class CheckBox(MultiStateButton):
        """
        A MultiStateButton implementation of a checkBox
        """
        def __init__(self, *args, **kwargs):
            name = kwargs.pop("name", None)
            size = kwargs.pop("size", None)
            color = kwargs.pop("color", None)            
            if not isinstance(size, int): size = 8
            
            super().__init__(*args, size = size, **kwargs)
            
            self.setStates([{"name": "unchecked", "color": "#101010"}, {"name": "checked", "color": "#2090ff"}])
            if isinstance(color, str): self.setColor(color)
            if isinstance(name, str): self.setText(name)
            self.setToggleable()
            self.setState(0)

        
        
        def setChecked(self, value: bool = True) -> None:
            self.setState(int(value))            
            return
        
        def changeToolTip(self, text: str = "", line = 0) -> None:
            return super().changeToolTip(text, line)

        def setColor(self, color: str = "#101010") -> None:
            self.states[1].update({"color": color})
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
            self.min_width = kwargs.pop("min_width", None)
            self.max_width = kwargs.pop("max_width", None)
            self.style_sheet = kwargs.pop("style_sheet", None)
            self.digits = kwargs.pop("digits", 2)
            self.block = kwargs.pop("block", False)
            self.warning_triggers = kwargs.pop("warning_triggers", None)
            self.base_color = kwargs.pop("base_color", "#101010")
            self.edited_color = kwargs.pop("edited_color", "#2020C0")
            self.warning_color = kwargs.pop("warning_color", "#A05000")
            
            super().__init__(parent)
            
            self.setDefaults()
            if not self.block: self.editingFinished.connect(self.addUnit)
            self.old_tooltip = self.toolTip()

        def setColor(self, color: str) -> None:
            self.setStyleSheet("QLineEdit{ background-color: " + color + " }")
            return

        def resetColor(self) -> None:
            self.setColor(self.base_color)
            return

        def setEditedColor(self, value = None) -> None:
            if isinstance(value, str):
                self.edited_color = value
                self.editingFinished.connect(lambda: self.setColor(self.edited_color))
            return

        def setWarning(self) -> None:
            if isinstance(self.warning_color, str):
                self.setColor(self.warning_color)
            self.old_tooltip = self.toolTip()
            return

        def resetWarning(self) -> None:
            self.setToolTip(self.old_tooltip)
            self.resetColor()
            return

        def postEditing(self, edited_color: bool = False) -> None:
            if edited_color: self.setColor(self.edited_color)
            else: self.resetColor()
            if isinstance(self.warning_triggers, list):
                new_value = self.getValue()
                for trigger in self.warning_triggers:
                    if trigger(new_value):
                        self.setWarning()
                        break
            return

        def setDefaults(self) -> None:
            if isinstance(self.value, str) or isinstance(self.value, int) or isinstance(self.value, float): self.setValue(self.value)
            if isinstance(self.tooltip, str): self.setToolTip(self.tooltip)
            if isinstance(self.min_width, int): self.setMinimumWidth(self.min_width)
            if isinstance(self.max_width, int): self.setMaximumWidth(self.max_width)            
            self.resetColor()            
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
                try: self.addUnit()
                except: pass
            else:
                self.unit = None
            return

        def addUnit(self) -> None:
            number = self.getValue()
            if not isinstance(number, str | int | float): return
            
            self.blockSignals(True)
            if isinstance(self.unit, str):
                if isinstance(self.digits, int): self.setText(f"{number:.{self.digits}f} {self.unit}")
                else: self.setText(f"{number} {self.unit}")
            else:
                if isinstance(self.digits, int): self.setText(f"{number:.{self.digits}f}")
                else: self.setText(f"{number}")
            self.blockSignals(False)
            self.postEditing(edited_color = True)
            return

        def getValue(self) -> float | str:
            entered_text = self.text()
            
            # Extract the numeric part of what was entered
            regex_pattern = r"([-+]?(?:[0-9]*\.)?[0-9]+(?:[eE][-+]?[0-9]+)?)(?:\s*[a-zA-Zμ°%]+)?"
            number_matches = re.findall(regex_pattern, entered_text)
            
            if isinstance(self.digits, int) and self.digits < 1: numbers = [int(float(x)) for x in number_matches]
            else: numbers = [float(x) for x in number_matches]
            
            if len(numbers) > 0:
                number = numbers[0]
                
                # Apply limits in case the number is too big or small
                if isinstance(self.limits, list) and isinstance(number, int | float):
                    if number < self.limits[0]: number = self.limits[0]
                    if number > self.limits[1]: number = self.limits[1]

                # Add the unit to the number
                if isinstance(self.digits, int):
                    number = round(number, self.digits)
                if isinstance(self.digits, int) and self.digits < 1:
                    number = int(number)
                
                return number
            else:
                return entered_text

        def setValue(self, value, edited_color: bool = False) -> None:
            # Method for programatically setting a value or str
            if isinstance(value, int) or isinstance(value, float):
                number = value
                
                # Apply limits in case the number is too big or small
                if isinstance(self.limits, list):
                    if number < self.limits[0]: number = self.limits[0]
                    if number > self.limits[1]: number = self.limits[1]

                if isinstance(self.digits, int):
                    number = round(number, self.digits)
                    if self.digits < 1: number = int(number)

                if isinstance(self.unit, str):
                    if isinstance(self.digits, int): self.setText(f"{number:.{self.digits}f} {self.unit}")
                    else: self.setText(f"{number} {self.unit}")
                else:
                    if isinstance(self.digits, int): self.setText(f"{number:.{self.digits}f}")
                    else: self.setText(f"{number}")                    
            
                self.postEditing(edited_color = edited_color)
            else:
                self.setText(f"{value}")
            return

        def wheelEvent(self, event: QtGui.QMouseEvent) -> None:
            if not self.hasFocus(): # Only accept scrolling if it is selected
                event.ignore()
                return
            
            (pos, number, error) = self.move_cursor()
            if bool(error): return

            delta = event.angleDelta().y() # Scroll direction
            value = self.getValue()
            if value < 0: delta *= -1
            old_pos = pos
            new_pos = pos
            
            for _ in range(10):
                new_pos = self.update_number_at_pos(old_pos, new_pos, delta)
                if isinstance(new_pos, bool): break
                elif new_pos < 0: break
            
            self.postEditing()
            return

        def move_cursor(self) -> tuple[int, int, int]:
            number = 0
            
            pos = self.cursorPosition() - 1
            if pos < 0: # Cursor is all the way to the left: move one character to the right so the character 'in focus' is the first one
                pos = 0
                self.setCursorPosition(pos + 1)

            txt = self.text() # Read the text
            if len(txt) < 1: return (pos, number, 1) # No text. Return
            
            text_at_pos = txt[pos]
            if text_at_pos.isnumeric(): # The character in focus is a number. Return
                number = int(txt[pos])
                return (pos, number, 0)
            
            if text_at_pos == ".": # The character in focus is a decimal dot. Move one position to the right
                pos += 1
                self.setCursorPosition(pos + 1)
                text_at_pos = txt[pos]
                if text_at_pos.isnumeric():
                    number = int(txt[pos])
                    return (pos, number, 0)

            if pos < 1: # The character in focus is the first one but it is not numeric. This happens when there is a leading minus sign
                pos += 1
                self.setCursorPosition(pos + 1)
                text_at_pos = txt[pos]
                if text_at_pos.isnumeric():
                    number = int(txt[pos])
                    return (pos, number, 0)
            
            # Else the cursor must be to the right side. Move it to the left until it hits a numeric character
            while pos > 0:
                pos -= 1
                text_at_pos = txt[pos]
                if text_at_pos.isnumeric():
                    self.setCursorPosition(pos + 1)
                    number = int(txt[pos])
                    return (pos, number, 0)

            # In case the value is not numeric at all
            return (pos, number, 1)

        def update_number_at_pos(self, old_pos: int = 0, new_pos: int = 0, delta = 1) -> bool | int:
            txt = self.text()
            text_pos = txt[new_pos] # Text at the cursor position
            if not text_pos.isnumeric(): return new_pos - 1 # Only continue if the character at the cursor position is an integer
            number = int(text_pos) # Integer at the cursor position

            if delta > 0: # Scroll up
                new_number = number + 1
                if new_number > 9: new_number = 0
            else: # Scroll down
                new_number = number - 1
                if new_number < 0:
                    if new_pos > 0: new_number = 9
                    else: new_number = -1
                
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
        
        def focusAndSelect(self) -> None:
            self.setFocus()
            self.selectAll()
            return
        
        def keyPressEvent(self, event: QtGui.QKeyEvent) -> QtGui.QKeyEventne:
            if event.key() in [QtCore.Qt.Key.Key_Enter, QtCore.Qt.Key.Key_Return]: self.clearFocus()
            return super().keyPressEvent(event)

    class InputLineEdit(QtWidgets.QLineEdit):
        """
        A QLineEdit with capabilities to efficiently add units, extract and set values
        """
        def __init__(self, parent = None, **kwargs):
            self.value = kwargs.pop("value", None)
            self.tooltip = kwargs.pop("tooltip", None)
            self.min_width = kwargs.pop("min_width", None)
            self.max_width = kwargs.pop("max_width", None)
            self.style_sheet = kwargs.pop("style_sheet", None)
            self.block = kwargs.pop("block", False)
            self.base_color = kwargs.pop("base_color", "#101010")
            self.history = []
            self.history_index = -1

            super().__init__(parent)
            
            self.setDefaults()
            self.old_tooltip = self.toolTip()

        def setDefaults(self) -> None:
            if isinstance(self.value, str) or isinstance(self.value, int) or isinstance(self.value, float): self.setValue(self.value)
            if isinstance(self.tooltip, str): self.setToolTip(self.tooltip)
            if isinstance(self.min_width, int): self.setMinimumWidth(self.min_width)
            if isinstance(self.max_width, int): self.setMaximumWidth(self.max_width)            
            self.resetColor()            
            return

        def setColor(self, color: str) -> None:
            self.setStyleSheet("QLineEdit{ background-color: " + color + " }")
            return

        def resetColor(self) -> None:
            self.setColor(self.base_color)
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

        def event(self, event):
            # Use .Type.KeyPress for PySide6/PyQt6
            if event.type() == QtCore.QEvent.Type.KeyPress:
                match event.key():
                    case QtCore.Qt.Key.Key_Tab | QtCore.Qt.Key.Key_Right:
                        if self.completer() and self.completer().popup().isVisible():
                            # Get the current completion from the popup
                            # completion = self.completer().currentCompletion()
                            
                            index = self.completer().popup().currentIndex()
                            if index.isValid():
                                completion = self.completer().completionModel().data(index)
                                self.setText(completion)
                            
                            self.completer().popup().hide()
                            event.accept()
                            return True
                    case QtCore.Qt.Key.Key_Up: # Up arrow scrolls through history
                        self.history_index += 1
                        if self.history_index > len(self.history) - 1:
                            self.history_index = 0
                        if self.history_index > len(self.history) - 1:
                            event.accept()
                            return super().event(event)
                        self.setText(self.history[self.history_index])
                        event.accept()
                        return True
                    case QtCore.Qt.Key.Key_Return:
                        self.history.insert(0, self.text()) # Add the query to the history
                        if len(self.history) > 10: self.history = self.history[:9]
                        self.history_index = -1 # Reset history
                        return super().event(event)
                    case _:
                        pass
            return super().event(event)

        def focusOutEvent(self, event): # Prevent evaluation when focus is lost
            self.blockSignals(True)
            super().focusOutEvent(event)
            self.blockSignals(False)
            return

    class ProgressBar(QtWidgets.QProgressBar):
        """
        A QProgressBar with extra method changeToolTip
        """
        def __init__(self, *args, **kwargs):            
            tooltip = kwargs.pop("tooltip", None)
            
            super().__init__(*args, **kwargs)
            
            if isinstance(tooltip, str): self.setToolTip(tooltip)
            self.setValue(0)
        
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

        def __init__(self, parent = None, tooltip: str = "", limits: list = [-180, 180], value: float = 0, digits: int = 0, max_width = 150, unit = None, layout_orientation: str = "h", slider_orientation: str = "h",
                     log_scale: bool = False, minmax_buttons: bool = False, min_button_icon: QtGui.QIcon = None, max_button_icon: QtGui.QIcon = None):
            super().__init__(parent)
            [self.min_val, self.max_val] = limits

            # 1: Create the widgets
            self.slider = SCTWidgets.Slider(orientation = slider_orientation, tooltip = tooltip)
            self.line_edit = SCTWidgets.PhysicsLineEdit(max_width = max_width, unit = unit, limits = limits, digits = digits, tooltip = tooltip)
            if slider_orientation == "v": self.slider.setMinimumHeight(20)

            if minmax_buttons:
                if isinstance(min_button_icon, QtGui.QIcon): self.min_button = SCTWidgets.MultiStateButton(tooltip = "set slider to minimum", icon = min_button_icon)
                else: self.min_button = SCTWidgets.MultiStateButton(tooltip = "set slider to minimum")
                if isinstance(max_button_icon, QtGui.QIcon): self.max_button = SCTWidgets.MultiStateButton(tooltip = "set slider to maximum", icon = max_button_icon)
                else: self.max_button = SCTWidgets.MultiStateButton(tooltip = "set slider to maximum")

            # 2: Configure widgets
            self.slider.setRange(self.min_val, self.max_val)
            [widget.setValue(value) for widget in [self.slider, self.line_edit]]

            # 3: Set up the layout
            if layout_orientation == "h": self.widget_layout = QtWidgets.QHBoxLayout()
            else:
                self.widget_layout = QtWidgets.QVBoxLayout()
                self.widget_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            
            if minmax_buttons:
                if layout_orientation == "v": self.widget_layout.addWidget(self.max_button, alignment = QtCore.Qt.AlignmentFlag.AlignCenter)
                else: self.widget_layout.addWidget(self.min_button)
            self.widget_layout.addWidget(self.slider, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
            self.widget_layout.addWidget(self.line_edit)
            if minmax_buttons:
                if layout_orientation == "v": self.widget_layout.addWidget(self.min_button, alignment = QtCore.Qt.AlignmentFlag.AlignCenter)
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



        def _update_line_edit(self, value: float = 0) -> None:
            self.line_edit.blockSignals(True) 
            self.line_edit.setValue(value)
            self.line_edit.blockSignals(False)
            return

        def _update_slider(self):
            try:
                value = self.line_edit.getValue()
                if not isinstance(value, float | int): return
                
                [widget.blockSignals(True) for widget in [self.slider, self.line_edit]]
                [widget.setValue(value) for widget in [self.slider, self.line_edit]]
                [widget.blockSignals(False) for widget in [self.slider, self.line_edit]]
            except ValueError:
                # Handle empty or invalid input by resetting to the current slider value
                self.line_edit.setText(str(self.slider.value()))
            return

        def getValue(self) -> float:
            return self.line_edit.getValue()
        
        def setValue(self, value: float = 0) -> None:
            if value < self.min_val: value = self.min_val
            elif value > self.max_val: value = self.max_val
            self.slider.setValue(value) # Triggers _update_line_edit
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

    class ImageView(pg.ImageView):
        position_signal = QtCore.pyqtSignal(float, float)
        position_signal_middle_button = QtCore.pyqtSignal(float, float)
        scan_file_signal = QtCore.pyqtSignal(str)
        
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.setDefaults()
        
        def setDefaults(self) -> None:
            if isinstance(self.view, pg.PlotItem): self.view.invertY(False)
            self.getViewBox().setBackgroundColor("#000000")
            self.ui.menuBtn.hide()
            self.ui.roiBtn.hide()
            self.setAcceptDrops(True)
            
            layout = self.ui.gridLayout
            layout.setColumnStretch(0, 1)
            layout.setColumnStretch(1, 0)
            layout.setColumnStretch(2, 0)
            return

        def getViewBox(self):
            if isinstance(self.view, pg.PlotItem): return self.view.getViewBox()
            else: return self.view

        def addWidget(self, widget: QtWidgets.QWidget, row: int = 0, column: int = 0, rowSpan: int = 1, columnSpan: int = 1) -> None:
            self.ui.gridLayout.addWidget(widget, row, column, rowSpan, columnSpan)
            return
        
        def addWidgetUnderneathHistogram(self, widget: QtWidgets.QWidget) -> None:
            layout = self.ui.gridLayout
            
            roi_button_index = layout.indexOf(self.ui.roiBtn)
            r_roi, c_roi, r_span_roi, c_span_roi = layout.getItemPosition(roi_button_index)
            layout.addWidget(widget, r_roi + 1, c_roi)
            
            # Reset the graphicsView
            graphics_view = self.ui.graphicsView
            gv_idx = layout.indexOf(graphics_view)
            r_gv, c_gv, r_span_gv, c_span_gv = layout.getItemPosition(gv_idx)
            layout.addWidget(graphics_view, r_gv, c_gv, r_span_gv + 1, c_span_gv + 1)
            return

        def mouseDoubleClickEvent(self, event) -> QtCore.QEvent:
            # Ensure it's a left double-click
            if event.button() == QtCore.Qt.MouseButton.LeftButton:
                # Get scene position
                pos = event.position()
                
                mapped_pos = self.view.mapToView(pos)
                self.position_signal.emit(mapped_pos.x(), mapped_pos.y())

            # Call base class implementation
            return super().mouseDoubleClickEvent(event)
        
        def mousePressEvent(self, event) -> QtCore.QEvent:
            if event.button() == QtCore.Qt.MouseButton.MiddleButton:
                # Get scene position
                pos = event.position()
                
                mapped_pos = self.view.mapToView(pos)
                self.position_signal_middle_button.emit(mapped_pos.x(), mapped_pos.y())
                
            # Call base class implementation
            return super().mousePressEvent(event)
        
        def dragEnterEvent(self, event: QtGui.QDragEnterEvent) -> None:
            try:
                urls: list[QtCore.QUrl] = event.mimeData().urls()
                file_path = urls[0].toLocalFile()
                if os.path.splitext(file_path)[1] in [".hdf5"]:
                    self.getViewBox().setBackgroundColor("#202020")
            except:
                pass
            event.accept()
            return
        
        def dragLeaveEvent(self, event):
            self.getViewBox().setBackgroundColor("#000000")
            event.accept()
            return
        
        def dropEvent(self, event: QtGui.QDropEvent):
            self.getViewBox().setBackgroundColor("#000000")
            event.accept()
            
            try:
                urls: list[QtCore.QUrl] = event.mimeData().urls()
                file_path = urls[0].toLocalFile()
                if os.path.splitext(file_path)[1] == ".hdf5": self.scan_file_signal.emit(file_path)
            except:
                pass
            return

    class GridItem(pg.ScatterPlotItem):
        def __init__(self, x_values: np.ndarray = np.linspace(0, 1, 3), y_values: np.ndarray = np.linspace(0, 1, 3), size: int = 2, color: str = "#FFFFFF"):
            self.x_values = x_values
            self.y_values = y_values
            self.pen = pg.mkPen(color)
            self.brush = pg.mkBrush(color)
            
            super().__init__(pen = self.pen, brush = self.brush, size = size)
            
            self.updateGrid()

        def setXValues(self, x_values: np.ndarray) -> None:
            self.x_values = x_values
            self.updateGrid()
            return
        
        def setYValues(self, y_values: np.ndarray) -> None:
            self.y_values = y_values
            self.updateGrid()
            return
        
        def setValues(self, x_values: np.ndarray, y_values: np.ndarray) -> None:
            self.x_values = x_values
            self.y_values = y_values
            self.updateGrid()
            return

        def updateGrid(self) -> None:
            x_mesh, y_mesh = np.meshgrid(self.x_values, self.y_values)
            x_flat = x_mesh.flatten()
            y_flat = y_mesh.flatten()
            
            self.setData(x = x_flat, y = y_flat)
            return

    class PhaseSlider(SliderLineEdit):
        """
        A slider line edit with buttons for controlling a phase
        """
        def __init__(self, parent = None, unit = "", phase_0_icon = None, phase_180_icon = None, tooltip = None):
            super().__init__(parent, unit = unit, limits = [-180, 180], value = 0, max_width = 80)
            
            self.phase_0_button = SCTWidgets.MultiStateButton()
            self.phase_0_button.setToolTip("Set the phase to 0")
            if isinstance(phase_0_icon, QtGui.QIcon): self.phase_0_button.setIcon(phase_0_icon)
            self.phase_180_button = SCTWidgets.MultiStateButton()
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

    class LevelIndicator(QtWidgets.QWidget):
        def __init__(self, parent = None, fill_color: str = "#4080FF", background_color: str = "#404040", limits: list = [0, 100], warning_color: str = "#A05000", min_warning: float = -1E6, max_warning: float = 1E6,
                     tooltip: str = "", show_tick: bool = True):
            super().__init__(parent)
            
            self.show_tick = show_tick
            self.min = limits[0]
            self.max = limits[1]
            self.total = self.max - self.min
            self.level = 0
            self.tick_level = 0
            self.fill_color = fill_color
            self.background_color = background_color
            
            self.warning_color = warning_color
            self.min_warning = min_warning
            self.max_warning = max_warning
            self.set_warning = False

            self.setFixedWidth(20)
            self.setMinimumHeight(80)
            if isinstance(tooltip, str): self.setToolTip(tooltip)



        def setLimits(self, values: list) -> None:
            self.setMin(values[0])
            self.setMax(values[1])
            return

        def setMin(self, value: float) -> None:
            self.min = value
            self.total = self.max - self.min
            return

        def setMax(self, value: float) -> None:
            self.max = value
            self.total = self.max - self.min
            return

        def getValue(self) -> float:
            return self.level

        def setValue(self, value: float = 0) -> None:
            self.level = max(self.min, min(value, self.max))
            if self.level > self.max_warning or self.level < self.min_warning: self.set_warning = True
            else: self.set_warning = False
            self.update() # Triggers repaint
            return
        
        def getTickValue(self) -> float:
            return self.tick_level

        def setTickValue(self, value: float = 0) -> None:
            self.tick_level = max(self.min, min(value, self.max))
            self.update() # Triggers repaint
            return

        def paintEvent(self, event) -> None:
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            
            width = self.width()
            height = self.height()
            
            cyl_width = int(5)
            cyl_height = int(height * 0.9)
            x_offset = int((width - cyl_width) / 2)
            y_offset = int((height - cyl_height) / 2)
            
            # Rectangles denoting the 'fill level' and the outline
            outline_rect = QtCore.QRectF(x_offset - 1, y_offset - 1, cyl_width + 1, cyl_height + 1)
            fill_fraction = (self.level - self.min) / (self.total)
            fill_height = int(fill_fraction * cyl_height)
            fill_rect = QtCore.QRectF(x_offset - 1, y_offset + (cyl_height - fill_height) - 1, cyl_width + 1, fill_height + 1)
            
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor(self.background_color)))
            painter.drawRect(outline_rect)
            if self.set_warning: painter.setBrush(QtGui.QBrush(QtGui.QColor(self.warning_color)))
            else: painter.setBrush(QtGui.QBrush(QtGui.QColor(self.fill_color)))
            painter.drawRect(fill_rect)
            
            # Draw Graduations
            painter.setPen(QtGui.QPen(QtGui.QColor(self.background_color), 1))
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            num_marks = 5
            for i in range(num_marks + 1):
                y = int(y_offset + (i * (cyl_height / num_marks)))
                painter.drawLine(x_offset + cyl_width, y, x_offset + cyl_width + 4, y)
            
            # Draw tick
            if not self.show_tick: return
            painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.red, 1))
            tick_height = int(cyl_height * (self.tick_level - self.min) / self.total)
            painter.drawLine(x_offset + cyl_width, y_offset - tick_height, x_offset + cyl_width + 4, y_offset - tick_height)
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
            self.checkable = kwargs.pop("checkable", False)
            self.background_color = kwargs.pop("background_color", "#202020")
            self.focus_color = kwargs.pop("focus_color", "#353535")
            
            super().__init__(*args, **kwargs)
            
            if isinstance(title, str): self.setTitle(title)
            if isinstance(tooltip, str): self.setToolTip(tooltip)
            
            self.outer_layout = QtWidgets.QVBoxLayout(self)
            self.outer_layout.setContentsMargins(0, 0, 0, 0)
            self.content_container = QtWidgets.QWidget(self)
            self.outer_layout.addWidget(self.content_container)
            
            if self.checkable:
                self.setCheckable(True)
                self.setChecked(True)
                self.toggled.connect(lambda toggleState: self.content_container.setVisible(toggleState))
            
            self.setFocused(False)
            
            
        
        def setLayout(self, layout: QtWidgets.QLayout) -> None:
            """Overrides setLayout to apply layouts to the inner container instead."""
            # Clean margins on user layouts so they align perfectly with the groupbox borders
            layout.setContentsMargins(2, 0, 2, 0)
            self.content_container.setLayout(layout)
            return

        def setFocused(self, value: bool = True) -> None:
            if value: color = self.focus_color
            else: color = self.background_color
            
            style_sheet = "QGroupBox {background-color: " + color + "; }"
            style_sheet += "QGroupBox::indicator {width: 8px; height: 8px; border: 2px solid #ffffff; border-radius: 3px; background-color: " + self.background_color + "; }"
            style_sheet += "QGroupBox::indicator:checked {border-color: #2020C0; background-color: #2020C0; }"
            self.setStyleSheet(style_sheet)
            return
        
        def maximize(self) -> None:
            self.content_container.setVisible(True)
            return
        
        def minimize(self) -> None:
            self.content_container.setVisible(False)
            return

    class Completer(QtWidgets.QCompleter):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

    class Application(QtWidgets.QApplication):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)

    class ButtonGroup(QtCore.QObject):
        clicked = QtCore.pyqtSignal(str)
        
        def __init__(self, *args, **kwargs):
            super().__init__()
            
            self.widgets = {}
            self.exclusive = True
            self.keep_one_checked = True
            
            exclusive = kwargs.pop("exclusive", "none")
            if isinstance(exclusive, bool):
                self.exclusive = exclusive
            keep_one_checked = kwargs.pop("keep_one_checked", "none")
            if isinstance(keep_one_checked, bool):
                self.keep_one_checked = keep_one_checked
        
        def addButton(self, widget: SCTWidgets.MultiStateButton | SCTWidgets.CheckBox, name: str = "") -> None:
            if not isinstance(widget, SCTWidgets.MultiStateButton | SCTWidgets.CheckBox): return
            widget.setToggleable(False) # Toggling is done manually in widgetClicked
            self.widgets.update({f"{name}": widget})
            
            widget.clicked.connect(lambda checked: self.widgetClicked(name))
            return
        
        def widgetClicked(self, name: str) -> None:
            [widget.blockSignals(True) for widget in self.widgets.values()]
            
            # Manual toggle. Save both the old state and the new one            
            clicked_widget = self.widgets[name]
            old_index = clicked_widget.state_index
            clicked_widget.toggleState()
            new_index = clicked_widget.state_index
            
            if self.keep_one_checked:
                state_indices = []
                for widget in self.widgets.values(): state_indices.append(widget.state_index) # Tally the current states
                if not 1 in state_indices: new_index = 1 # Reset the widget to state_index 1 if it turns out that none of the other widgets is in state 1
            
            if self.exclusive and new_index > 0: [widget.toggleState() for widget in self.widgets.values() if widget.state_index == new_index]
            
            clicked_widget.setState(new_index)
            
            self.clicked.emit(name)
            [widget.blockSignals(False) for widget in self.widgets.values()]
            return
        
        def getSelectedWidget(self) -> str:
            selected_widget = ""
            for name, widget in self.widgets.items():
                if widget.state_index == 1:
                    selected_widget = name
                    break
            return selected_widget

    class ReciprocalGroup(QtCore.QObject):
        def __init__(self, *args, **kwargs):
            self.bounce = 0
            self.min = 0
            self.min_value = 0
            self.max = 1
            self.max_value = 1
            self.product_value = self.max_value - self.min_value
            product = kwargs.pop("product", None)
            if isinstance(product, list) and len(product) > 1:
                if isinstance(product[0], SCTWidgets.PhysicsLineEdit | float | int): self.min = product[0]
                if isinstance(product[1], SCTWidgets.PhysicsLineEdit | float | int): self.max = product[1]
            elif isinstance(product, SCTWidgets.PhysicsLineEdit | float | int):
                self.max = product
            
            self.factor0 = 0
            self.factor0_value = 0
            self.factor1 = 1
            self.factor1_value = 1
            factors = kwargs.pop("factors", None)
            if isinstance(factors, list) and len(factors) > 1:
                if isinstance(factors[0], SCTWidgets.PhysicsLineEdit | float | int): self.factor0 = factors[0]
                if isinstance(factors[1], SCTWidgets.PhysicsLineEdit | float | int): self.factor1 = factors[1]
            elif isinstance(factors, SCTWidgets.PhysicsLineEdit | float | int):
                self.factor1 = factors
            
            self.factor = 1 # Proportionality factor between the product of factors and the product (because of different units)
            factor = kwargs.pop("factor", None)
            if isinstance(factor, float | int): self.factor = factor
            
            self.lock = kwargs.pop("lock", "product")
            self.try_to_retain = kwargs.pop("try_to_retain", "factor0")
            
            if not isinstance(self.factor0, SCTWidgets.PhysicsLineEdit | float | int): self.lock = "factor0"
            if not isinstance(self.factor1, SCTWidgets.PhysicsLineEdit | float | int): self.lock = "factor1"
            if not isinstance(self.max, SCTWidgets.PhysicsLineEdit | float | int): self.lock = "product"
            
            self.factor0_enforce_integer = False
            factor0_enforce_integer = kwargs.pop("factor0_enforce_integer", None)
            if isinstance(factor0_enforce_integer, bool): self.factor0_enforce_integer = factor0_enforce_integer
            self.factor1_enforce_integer = False
            factor1_enforce_integer = kwargs.pop("factor1_enforce_integer", None)
            if isinstance(factor1_enforce_integer, bool): self.factor1_enforce_integer = factor1_enforce_integer
            if self.factor1_enforce_integer and self.factor0_enforce_integer: self.factor1_enforce_integer = False
            
            self.factor0_constraint = lambda value: value
            factor0_constraint = kwargs.pop("factor0_constraint", None)
            if self.factor0_enforce_integer: self.factor0_constraint = lambda value: round(value)
            if isinstance(factor0_constraint, types.LambdaType): self.factor0_constraint = factor0_constraint
            self.factor1_constraint = lambda value: value
            factor1_constraint = kwargs.pop("factor1_constraint", None)
            if self.factor1_enforce_integer: self.factor1_constraint = lambda value: round(value)
            if isinstance(factor1_constraint, types.LambdaType): self.factor1_constraint = factor1_constraint

            self.factor0_include_endpoint = False            
            factor0_include_endpoint = kwargs.pop("factor0_include_endpoint", None)            
            if isinstance(factor0_include_endpoint, bool): self.factor0_include_endpoint = factor0_include_endpoint
            self.factor1_include_endpoint = False
            factor1_include_endpoint = kwargs.pop("factor1_enforce_endpoint", None)
            if isinstance(factor1_include_endpoint, bool): self.factor1_include_endpoint = factor1_include_endpoint

            super().__init__()

            if isinstance(self.factor0, SCTWidgets.PhysicsLineEdit): self.factor0.editingFinished.connect(self.factor0Changed)
            if isinstance(self.factor1, SCTWidgets.PhysicsLineEdit): self.factor1.editingFinished.connect(self.factor1Changed)
            if isinstance(self.min, SCTWidgets.PhysicsLineEdit): self.min.editingFinished.connect(self.productChanged)
            if isinstance(self.max, SCTWidgets.PhysicsLineEdit): self.max.editingFinished.connect(self.productChanged)



        def setLock(self, lock: str = "factor0") -> None:
            if not lock in ["factor0", "factor1", "product"]: return
            self.lock = lock
            return

        def getProduct(self) -> float:
            if isinstance(self.max, SCTWidgets.PhysicsLineEdit): self.max_value = self.max.getValue() # Get max
            else: self.max_value = self.max
            if isinstance(self.min, SCTWidgets.PhysicsLineEdit): self.min_value = self.min.getValue() # Get min
            else: self.min_value = self.min
            
            if not isinstance(self.min_value, float | int) or not isinstance(self.max_value, float | int): return 0

            self.product_value = (self.max_value - self.min_value) * self.factor
            return self.product_value

        def getFactors(self) -> tuple[float, float]:
            if isinstance(self.factor0, SCTWidgets.PhysicsLineEdit): self.factor0_value = self.factor0.getValue() # Get factor0
            else: self.factor0_value = self.factor0
            if isinstance(self.factor1, SCTWidgets.PhysicsLineEdit): self.factor1_value = self.factor1.getValue() # Get factor1
            else: self.factor1_value = self.factor1
                        
            if not isinstance(self.factor0_value, float | int) or not isinstance(self.factor1_value, float | int): return (0, 0)
            return (self.factor0_value, self.factor1_value)

        def factor0Changed(self) -> None:
            factor0_value = self.factor0.getValue() # Get the new value
            factor0_value = self.factor0_constraint(factor0_value) # Apply the constraint, e.g. an integer value or a multiple of 16
            self.factor0.setValue(factor0_value, edited_color = True)
            
            match self.lock:
                case "factor0":
                    if self.try_to_retain == "factor1" and isinstance(self.max, SCTWidgets.PhysicsLineEdit): self.updateProduct()
                    else: self.updateFactor1()
                case "factor1": self.updateProduct()
                case "product": self.updateFactor1()
                case _: pass
            return

        def factor1Changed(self) -> None:
            factor1_value = self.factor1.getValue() # Get the new value
            factor1_value = self.factor1_constraint(factor1_value) # Apply the constraint, e.g. an integer value or a multiple of 16
            self.factor1.setValue(factor1_value, edited_color = True)
            
            match self.lock:
                case "factor0": self.updateProduct()
                case "factor1":
                    if self.try_to_retain == "factor0" and isinstance(self.max, SCTWidgets.PhysicsLineEdit): self.updateProduct()
                    else: self.updateFactor0()
                case "product": self.updateFactor0()
                case _: pass
            return

        def productChanged(self) -> None:            
            match self.lock:
                case "factor0": self.updateFactor1()
                case "factor1": self.updateFactor0()
                case "product":
                    if self.try_to_retain == "factor0" and isinstance(self.factor1, SCTWidgets.PhysicsLineEdit): self.updateFactor1()
                    else: self.updateFactor0()
                case _: pass
            return

        def updateFactor0(self) -> None:
            if not isinstance(self.factor0, SCTWidgets.PhysicsLineEdit): return
            
            if self.bounce > 4: self.bounceWarning()
            self.getProduct()
            self.getFactors()
            
            try:
                # Calculate factor 0 on the basis of the other values, taking possible end points into account
                if self.factor1_include_endpoint: new_factor0_value = self.product_value / (self.factor1_value - 1)
                else: new_factor0_value = self.product_value / self.factor1_value                    
                if self.factor0_include_endpoint: new_factor0_value += 1
                
                # Apply a constraint if it is there. If the constraint changes the value, this needs to be bounced back
                constrained_factor0_value = self.factor0_constraint(new_factor0_value)
                self.factor0.setValue(constrained_factor0_value, edited_color = True)
                if not constrained_factor0_value == new_factor0_value:
                    self.bounce += 1
                    if self.lock == "factor1" and isinstance(self.max, SCTWidgets.PhysicsLineEdit): self.updateProduct()
                    else: self.updateFactor1()
                else:
                    self.bounce = 0
            except:
                pass
            return

        def updateFactor1(self) -> None:
            if not isinstance(self.factor1, SCTWidgets.PhysicsLineEdit): return
            
            if self.bounce > 4: self.bounceWarning()
            self.getProduct()
            self.getFactors()
            
            try:
                # Calculate factor 0 on the basis of the other values, taking possible end points into account
                if self.factor0_include_endpoint: new_factor1_value = self.product_value / (self.factor0_value - 1)
                else: new_factor1_value = self.product_value / self.factor0_value
                if self.factor1_include_endpoint: new_factor1_value += 1
                
                # Apply a constraint if it is there. If the constraint changes the value, this needs to be bounced back
                constrained_factor1_value = self.factor1_constraint(new_factor1_value)
                self.factor1.setValue(constrained_factor1_value, edited_color = True)
                if not constrained_factor1_value == new_factor1_value:
                    self.bounce += 1
                    if self.lock == "factor0" and isinstance(self.max, SCTWidgets.PhysicsLineEdit): self.updateProduct()
                    else: self.updateFactor0()
                else:
                    self.bounce = 0
            except:
                pass
            return

        def updateProduct(self) -> None:
            if not isinstance(self.max, SCTWidgets.PhysicsLineEdit): return
            
            self.getProduct()
            self.getFactors()
            
            try:
                if self.factor0_include_endpoint: self.factor0_value -= 1
                if self.factor1_include_endpoint: self.factor1_value -= 1

                new_product = self.factor0_value * self.factor1_value
                new_max_value = new_product + self.min_value
                self.max.setValue(new_max_value, edited_color = True)
            except:
                pass
            return
        
        def bounceWarning(self) -> None:
            self.bounce = 0
            print("Warning. Factor0 and factor 1 cannot be updated in a mutually consistent way")
            return

    class MainWindow(QtWidgets.QMainWindow):
        def __init__(self):
            super().__init__()

    class PlotWidget(pg.PlotWidget):
        def __init__(self, buffer_size: int = 2000, n_channels: int = 35, colors: list = []):
            super().__init__()
            
            self.buffer_size = buffer_size
            self.n_channels = n_channels
            self.channel_names = np.array([f"channel_{index}" for index in range(n_channels)], dtype = str)
            self.x_channel = -1

            # Make PlotDataItems
            if len(colors) > 0: self.pdis = [self.plot(np.array([]), np.array([]), pen = pg.mkPen(colors[i % len(colors)], width = 1)) for i in range(self.n_channels)]
            else: self.pdis = [self.plot(np.array([]), np.array([]), pen = pg.mkPen("#FFFFFF", width = 1)) for i in range(self.n_channels)]
            [self.addItem(pdi) for pdi in self.pdis]
            
            self.clearBuffer()
            self.h_lines = []
            self.v_lines = []
            self.log_scale = False



        def setLogScale(self, value: bool = True):
            
            return

        def setVLines(self, x_coords: list | int | float) -> None:
            if isinstance(x_coords, int | float): x_coords = [x_coords]
            if not isinstance(x_coords, list): return
            
            for v_line in self.v_lines:
                try: self.getViewBox().removeItem(v_line)
                except: pass
            
            self.v_lines = []
            for coord in x_coords:
                v_line = pg.InfiniteLine(angle = 90, movable = False, pen = "#404040")
                v_line.setPos((coord, 0))                
                self.v_lines.append(v_line)
                self.getViewBox().addItem(v_line, ignoreBounds = True)
            return
        
        def setHLines(self, y_coords: list | int | str) -> None:
            if isinstance(y_coords, int | float): y_coords = [y_coords]
            if not isinstance(y_coords, list): return
            
            for h_line in self.h_lines:
                try: self.getViewBox().removeItem(h_line)
                except: pass
            
            self.h_lines = []
            for coord in y_coords:
                h_line = pg.InfiniteLine(angle = 0, movable = False, pen = "#404040")
                h_line.setPos((0, coord))
                self.h_lines.append(h_line)
                self.getViewBox().addItem(h_line, ignoreBounds = True)
            return
        
        def addData(self, data: np.ndarray) -> None:
            (n_channels, n_datapoints) = data.shape # Read how many channels and data points are given
            if n_channels > self.n_channels: data = data[:n_channels]
            new_buffer_index = self.buffer_index + n_datapoints # Calculate where the buffer fills up to
            
            if new_buffer_index > self.buffer_size: # If the buffer is full: roll over
                overflow = new_buffer_index - self.buffer_size
                
                self.buffer[:n_channels, self.buffer_index : self.buffer_size] = data[:, : n_datapoints - overflow] # Fill up the remainder
                self.buffer_full = True
                self.buffer[:n_channels, : overflow] = data[:, n_datapoints - overflow :] # Roll over and overwrite
                self.buffer_index = overflow
            else:
                self.buffer[:n_channels, self.buffer_index : new_buffer_index] = data
                self.buffer_index = new_buffer_index
            self.plotData()
            return
        
        def clearBuffer(self) -> None:
            self.buffer_full = False
            self.buffer_index = 0
            self.buffer = np.zeros((self.n_channels, self.buffer_size), dtype = np.float32)
            self.plotData()
            return
        
        def setData(self, data: np.ndarray) -> None:
            self.clearBuffer()
            self.addData(data)
            return
        
        def setBufferSize(self, value: int = 6000) -> None:
            self.buffer_size = value
            self.buffer = np.zeros((self.n_channels, self.buffer_size), dtype = np.float32)
            self.buffer_full = False
            self.buffer_index = 0
            self.plotData()
            return
        
        def setChannelNames(self, channel_names: list | np.ndarray) -> None:
            self.channel_names = np.array(channel_names, dtype = str)
            self.setXAxis(self.x_channel)
            return

        def setXAxis(self, channel_index: int = -1) -> None:
            if channel_index > -2 and channel_index < self.n_channels: self.x_channel = channel_index
            if self.x_channel < 0: self.setLabel("bottom", "index")
            else:
                try: self.setLabel("bottom", self.channel_names[self.x_channel])
                except: self.setLabel("bottom", "index")
            self.plotData()
            return

        def plotData(self) -> None:           
            x_data = None
            if self.buffer_full: # Buffer full: roll around to capture all data points for the pdis
                if self.x_channel > -1 and self.x_channel < self.n_channels:
                    x_data = np.concatenate((self.buffer[self.x_channel, self.buffer_index :], self.buffer[self.x_channel, : self.buffer_index]))

                for channel_index in range(self.n_channels):
                    y_data = np.concatenate((self.buffer[channel_index, self.buffer_index :], self.buffer[channel_index, : self.buffer_index]))
                    
                    if isinstance(x_data, np.ndarray): self.pdis[channel_index].setData(x_data, y_data)
                    else: self.pdis[channel_index].setData(y_data)
            else:
                if self.x_channel > -1 and self.x_channel < self.n_channels:
                    x_data = self.buffer[self.x_channel, : self.buffer_index]
                
                for channel_index in range(self.n_channels):
                    y_data = self.buffer[channel_index, : self.buffer_index]
                    
                    if isinstance(x_data, np.ndarray): self.pdis[channel_index].setData(x_data, y_data)
                    else: self.pdis[channel_index].setData(y_data)
            return

    class ScrollWidget(QtWidgets.QScrollArea):
        def __init__(self, vertical: bool = True, horizontal: bool = False):
            super().__init__()
            
            self.setContentsMargins(0, 0, 0, 0)
            self.setWidgetResizable(True)
            
            if horizontal: self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            else: self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            if vertical: self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            else: self.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        
        
        def getScrollBarWidth(self) -> int:
            return self.verticalScrollBar().sizeHint().width()
        
        def getScrollBarHeight(self) -> int:
            return self.horizontalScrollBar().sizeHint().height()
        
        def keyPressEvent(self, event: QtGui.QKeyEvent):
            QKey = QtCore.Qt.Key
            if event.key() in [QKey.Key_PageUp, QKey.Key_PageDown, QKey.Key_Space]:
                event.ignore()
                return
            return super().keyPressEvent(event)



class MinMaxMethods(QtWidgets.QWidget):
    stateChanged = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()
        
        self.widget_layout = make_layout("g")
        self.widget_layout.setContentsMargins(2, 0, 2, 0)
        self.setLayout(self.widget_layout)
        
        self.methods = []
        self.min_line_edits = {}
        self.min_checkboxes = {}
        self.buttons = {}
        self.max_checkboxes = {}
        self.max_line_edits = {}
        self.min_button_group = SCTWidgets.ButtonGroup(exclusive = True)
        self.max_button_group = SCTWidgets.ButtonGroup(exclusive = True)
        self.min_button_group.clicked.connect(lambda button_name: self.stateChanged.emit())
        self.max_button_group.clicked.connect(lambda button_name: self.stateChanged.emit())



    def addMethod(self, method_name: str = "", min_value: float = 0, max_value: float = 1, digits: int = None, limits: list = None, unit: str = "nm", icon: QtGui.QIcon = None, tooltip: str = "", max_width: int = 70) -> None:            
        self.min_line_edits.update({f"{method_name}": SCTWidgets.PhysicsLineEdit(value = min_value, digits = digits, limits = limits, unit = unit, tooltip = tooltip, max_width = max_width, edited_color = "#101010")})
        self.min_checkboxes.update({f"{method_name}": SCTWidgets.CheckBox(tooltip = tooltip)})
        self.buttons.update({f"{method_name}": SCTWidgets.MultiStateButton(icon = icon, tooltip = tooltip)})
        self.max_checkboxes.update({f"{method_name}": SCTWidgets.CheckBox(tooltip = tooltip)})
        self.max_line_edits.update({f"{method_name}": SCTWidgets.PhysicsLineEdit(value = max_value, digits = digits, limits = limits, unit = unit, tooltip = tooltip, max_width = max_width, edited_color = "#101010")})
        
        self.min_button_group.addButton(self.min_checkboxes[f"{method_name}"], name = f"{method_name}")
        self.max_button_group.addButton(self.max_checkboxes[f"{method_name}"], name = f"{method_name}")
        self.methods.append(method_name)
        if len(self.methods) < 2:
            self.min_checkboxes[f"{method_name}"].setState(1)
            self.max_checkboxes[f"{method_name}"].setState(1)
        
        row_widgets = [self.min_line_edits[f"{method_name}"], self.min_checkboxes[f"{method_name}"], self.buttons[f"{method_name}"], self.max_checkboxes[f"{method_name}"], self.max_line_edits[f"{method_name}"]]
        row_index = self.widget_layout.rowCount()
        [self.widget_layout.addWidget(widget, row_index, column_index, QtCore.Qt.AlignmentFlag.AlignCenter) for column_index, widget in enumerate(row_widgets)]
        
        self.widget_layout.setSpacing(0)
        self.widget_layout.update()
        self.setLayout(self.widget_layout)
        
        self.buttons[f"{method_name}"].clicked.connect(lambda checked: self.setMinMax(method_name))
        return
    
    def setUnit(self, method_name: str = "", unit: str = "") -> None:
        try: self.min_line_edits[f"{method_name}"].setUnit(unit)
        except: pass
        return

    def setValue(self, method_name: str = "", side: str = "min", value: float = 0) -> None:
        try:
            match side:
                case "min": self.min_line_edits[f"{method_name}"].setValue(value)
                case "max": self.max_line_edits[f"{method_name}"].setValue(value)
                case _: pass
        except:
            pass
        return
    
    @QtCore.pyqtSlot(str)
    def setMinMax(self, method: str = ""):
        try:
            [group.blockSignals(True) for group in [self.min_button_group, self.max_button_group]]
            self.min_button_group.widgetClicked(name = f"{method}")
            self.max_button_group.widgetClicked(name = f"{method}")
            [group.blockSignals(False) for group in [self.min_button_group, self.max_button_group]]
            self.stateChanged.emit()
        except:
            print(f"Error. Cannot find the checkboxes corresponding to method {method} of the clicked button")
        return

    def getMax(self):
        try:
            max_method  = self.max_button_group.getSelectedWidget()
            max_value = self.max_line_edits[f"{max_method}"].getValue()
            return [f"{max_method}", f"{max_value}"]
        except:
            print(f"Error retrieving the maximum value")
            return False
    
    def getMin(self):
        try:
            min_method  = self.min_button_group.getSelectedWidget()
            min_value = self.min_line_edits[f"{min_method}"].getValue()
            return [f"{min_method}", f"{min_value}"]
        except:
            print(f"Error retrieving the minimum value")
            return False



class CurrentHeightIndicatorWidget(QtWidgets.QWidget):
    def __init__(self, feedback_button: SCTWidgets.MultiStateButton, current_le: SCTWidgets.PhysicsLineEdit, height_le: SCTWidgets.PhysicsLineEdit,
                 fill_color: str = "#A0A0A0", background_color: str = "#A0A0A0", warning_color: str = "#A0A0A0", show_height_tick: bool = True):
        super().__init__()
        
        self.fill_color = fill_color
        self.background_color = background_color
        self.warning_color = warning_color
        self.current_le = current_le
        self.height_le = height_le
        self.height_le.setMinimumWidth(70)
        self.current_le.setMinimumWidth(70)
        
        self.current_indicator = SCTWidgets.LevelIndicator(fill_color = fill_color, background_color = background_color, warning_color = warning_color, show_tick = True, max_warning = 40)
        self.height_indicator = SCTWidgets.LevelIndicator(fill_color = fill_color, background_color = background_color, warning_color = warning_color, show_tick = False, min_warning = -100, max_warning = 100)
        self.feedback_button = feedback_button
        
        layout = make_layout("g")                
        layout.addWidget(self.feedback_button, 0, 0, 1, 2, alignment = QtCore.Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.height_le, 1, 0, 1, 2)
        layout.addWidget(self.height_indicator, 2, 1, 3, 1)
        layout.addWidget(self.current_indicator, 3, 0, 3, 1)
        layout.addWidget(self.current_le, 6, 0, 1, 2)
        self.setLayout(layout)
        
        self.current_indicator.setLimits([-1, 4])
        self.current_le.editingFinished.connect(self.currentChanged)
        self.height_le.editingFinished.connect(self.heightChanged)
    
    def setHeightLimits(self, limits: list = []) -> None:
        return self.height_indicator.setLimits(limits)
    
    def setCurrentLimits(self, limits: list = []) -> None:
        return self.current_indicator.setLimits(limits)
    
    def setHeight(self, value: float = 0) -> None:
        self.height_le.setValue(value)
        self.height_le.setValue(value)
        self.heightChanged()
        return
    
    def setCurrent(self, value: float = 0) -> None:
        abs_value = np.abs(value)
        self.current_le.setValue(abs_value)
        self.currentChanged()
        return

    def heightChanged(self) -> None:
        value = self.height_le.getValue()
        if isinstance(value, float | int): self.height_indicator.setValue(value)
        return
    
    def currentChanged(self) -> None:
        value = self.current_le.getValue()
        if isinstance(value, float | int):
            abs_val = np.clip(np.abs(value), .1, None)
            indicator_level = np.log10(abs_val)
            self.current_indicator.setValue(indicator_level)
        return
    
    def setCurrentTick(self, value) -> None:
        if isinstance(value, float | int):
            abs_val = np.clip(np.abs(value), .1, None)
            tick_level = np.log10(abs_val)
            self.current_indicator.setTickValue(tick_level)
        return

    def setHeightTick(self) -> None:
        value = self.height_le.getValue()
        if isinstance(value, float | int): self.height_indicator.setValue(value)
        return



class ModulatorWidget(QtWidgets.QWidget):
    def __init__(self, state_button: SCTWidgets.MultiStateButton, input: SCTWidgets.MultiStateButton | SCTWidgets.ComboBox, output: SCTWidgets.MultiStateButton | SCTWidgets.ComboBox,
                 mod_amplitude_le: SCTWidgets.PhysicsLineEdit, demod_amplitude_le: SCTWidgets.PhysicsLineEdit, mod_phase_le: SCTWidgets.PhysicsLineEdit, demod_phase_le: SCTWidgets.PhysicsLineEdit,
                 frequency_le: SCTWidgets.PhysicsLineEdit, number_le: SCTWidgets.PhysicsLineEdit, volume):
        
        super().__init__()
        
        self.state_button = state_button
        self.input = input
        self.output = output
        self.frequency_le = frequency_le
        self.number_le = number_le
        
        self.mod_amplitude_le = mod_amplitude_le
        self.mod_phase_le = mod_phase_le
        self.demod_amplitude_le = demod_amplitude_le
        self.demod_phase_le = demod_phase_le
        
        self.volume = None
        if isinstance(volume, SCTWidgets.SliderLineEdit): self.volume = volume
        
        self.df = 100
        
        self.modulator_layout = make_layout("g")
        [self.modulator_layout.addWidget(widget, 0, index, 2, 1) for index, widget in enumerate([self.state_button, self.output])]
        self.modulator_layout.addWidget(self.frequency_le, 0, 2, 1, 2)
        self.modulator_layout.addWidget(self.number_le, 1, 2, 1, 1)
        
        [self.modulator_layout.addWidget(widget, index, 4) for index, widget in enumerate([self.mod_amplitude_le, self.mod_phase_le])]        
        self.modulator_layout.addWidget(input, 0, 5, 2, 1)
        [self.modulator_layout.addWidget(widget, index, 6) for index, widget in enumerate([self.demod_amplitude_le, self.demod_phase_le])]
        
        if self.volume:
            try:
                self.modulator_layout.addWidget(self.volume.min_button, 0, 7, 2, 1)
                self.modulator_layout.addWidget(self.volume.slider, 0, 8, 1, 1, alignment = QtCore.Qt.AlignmentFlag.AlignBottom)
                self.modulator_layout.addWidget(self.volume.line_edit, 1, 8, 1, 1)
                self.modulator_layout.addWidget(self.volume.max_button, 0, 9, 2, 1)
            except:
                pass
        
        self.modulator_layout.setContentsMargins(2, 0, 2, 0)
        self.setLayout(self.modulator_layout)



    def getdf(self) -> float:
        return self.df

    def setdf(self, value: float) -> None:
        self.df = value
        return

    def getFrequency(self) -> float:
        return self.frequency_le.getValue()

    def setFrequency(self, value: float) -> None:
        return self.frequency_le.setValue(value)

    def getAmplitude(self) -> float:
        return self.mod_amplitude_le.getValue()
    
    def setAmplitude(self, value: float) -> None:
        return self.mod_amplitude_le.setValue(value)

    def setMeasuredAmplitude(self, value: float) -> None:
        return self.demod_amplitude_le.setValue(value)

    def getPhase(self) -> float:
        return self.mod_phase_le.getValue()

    def setPhase(self, value: float) -> None:
        return self.mod_phase_le.setValue(value)

    def setMeasuredPhase(self, value: float) -> None:
        return self.demod_phase_le.setValue(value)

    def readTone(self, value: complex) -> None:
        abs = np.abs(value)
        arg = np.rad2deg(np.angle(value))
        self.setMeasuredAmplitude(abs)
        self.setMeasuredPhase(arg)
        return

    def getInput(self) -> int | str:
        return self.input.state_name

    def setInput(self, value: int | str) -> None:
        return self.input.setState(value)

    def getOutput(self) -> int | str:
        return self.output.state_name

    def setOutput(self, value: int | str) -> None:
        return self.output.setState(value)

    def getVolume(self) -> int:
        return self.volume.getValue()



class LockinWidget(QtWidgets.QWidget):
    set_signal = QtCore.pyqtSignal()
    get_signal = QtCore.pyqtSignal()
    volumes = QtCore.pyqtSignal(list)
    amplitudes = QtCore.pyqtSignal(list)
    frequencies = QtCore.pyqtSignal(list)
    
    def __init__(self, modulators: list, df_line_edit: SCTWidgets.PhysicsLineEdit, t_line_edit: SCTWidgets.PhysicsLineEdit, audio_button: SCTWidgets.MultiStateButton, extrapolate_icon: QtGui.QIcon,
                 min_button_icon: QtGui.QIcon, max_button_icon: QtGui.QIcon, get_button: SCTWidgets.MultiStateButton = None, set_button: SCTWidgets.MultiStateButton = None, zero_volumes_button: SCTWidgets.MultiStateButton = None):
        super().__init__()
        
        self.modulators = modulators
        self.df_le = df_line_edit
        self.t_le = t_line_edit
        self.audio_button = audio_button
        self.zero_volumes_button = zero_volumes_button
        self.get_button = get_button
        self.set_button = set_button
        
        self.scroll_area = QtWidgets.QScrollArea()
        self.mod_widget = QtWidgets.QWidget()        
        self.volume = SCTWidgets.SliderLineEdit(unit = "%", layout_orientation = "h", minmax_buttons = True, min_button_icon = min_button_icon, max_button_icon = max_button_icon, limits = [0, 100])

        layout = make_layout("v")
        
        df_t_layout = make_layout("h")
        [df_t_layout.addWidget(widget) for widget in [self.df_le, self.t_le, self.audio_button, self.volume, self.zero_volumes_button]]
        layout.addLayout(df_t_layout)
        
        mod_layout = make_layout("v")
        mod_layout.setContentsMargins(2, 0, 2, 0)
        
        # Add extrapolate buttons
        for index, modulator in enumerate(self.modulators):
            modulator_layout = modulator.modulator_layout
            
            modulator.extrapolate_outputs = SCTWidgets.MultiStateButton(tooltip = "extrapolate to buttons below", icon = extrapolate_icon, size = 14)
            modulator.extrapolate_inputs = SCTWidgets.MultiStateButton(tooltip = "extrapolate to buttons below", icon = extrapolate_icon, size = 14)
            modulator.extrapolate_frequencies = SCTWidgets.MultiStateButton(tooltip = "extrapolate to buttons below", icon = extrapolate_icon, size = 14)

            [input_button, output_button] = [modulator.input, modulator.output]
            [button.setSize(14) for button in [input_button, output_button]]
            
            if index > 0 and index < len(self.modulators) - 1:
                [modulator.modulator_layout.addWidget(widget, index1, 1) for index1, widget in enumerate([output_button, modulator.extrapolate_outputs])]
                [modulator.modulator_layout.addWidget(widget, index1, 5) for index1, widget in enumerate([input_button, modulator.extrapolate_inputs])]
                modulator.modulator_layout.addWidget(modulator.extrapolate_frequencies, 1, 3)
                
                modulator.extrapolate_outputs.clicked.connect(lambda clicked, index0 = index: self.extrapolate(target = "outputs", index = index0))
                modulator.extrapolate_inputs.clicked.connect(lambda clicked, index0 = index: self.extrapolate(target = "inputs", index = index0))
                modulator.extrapolate_frequencies.clicked.connect(lambda clicked, index0 = index: self.extrapolate(target = "frequencies", index = index0))
                modulator.volume.slider.valueChanged.connect(self.sendVolumes)
            
            modulator.setLayout(modulator.modulator_layout)
            mod_layout.addWidget(modulator)
        
        self.mod_widget.setLayout(mod_layout)
        self.scroll_area.setWidget(self.mod_widget)
        layout.addWidget(self.scroll_area)
        
        get_set_layout = make_layout("h")
        [get_set_layout.addWidget(widget) for widget in [self.get_button, self.set_button]]
        layout.addLayout(get_set_layout)
        
        self.setLayout(layout)
        
        RG = SCTWidgets.ReciprocalGroup
        self.df_t_rg = RG(product = 1000, factors = [self.df_le, self.t_le])
        self.tone_rgs = [RG(product = self.modulators[index].frequency_le, factors = [self.df_le, self.modulators[index].number_le], lock = "factor0", try_to_retain = "product") for index in range(len(self.modulators))]
        
        # Set up connections
        self.zero_volumes_button.clicked.connect(self.setZeroVolumes)
        self.get_button.clicked.connect(self.get_signal.emit)
        self.set_button.clicked.connect(self.set_signal.emit)
        self.volume.slider.valueChanged.connect(self.sendVolumes)



    def getFrequencies(self) -> list:
        [modulator.frequency_le.resetColor() for modulator in self.modulators]
        return [modulator.getFrequency() for modulator in self.modulators]
    
    def setFrequencies(self, frequencies) -> None:
        for index, frequency in enumerate(frequencies):
            if index > len(self.modulators): break
            self.modulators[index].setFrequency(frequency)
            self.tone_rgs[index].updateFactor1()
        return

    def getAmplitudes(self) -> list:
        [modulator.mod_amplitude_le.resetColor() for modulator in self.modulators]
        return [modulator.getAmplitude() for modulator in self.modulators]

    def setAmplitudes(self, amplitudes) -> None:
        for index, amplitude in enumerate(amplitudes):
            if index > len(self.modulators): break
            self.modulators[index].setAmplitude(amplitude)
        return

    def getPhases(self) -> list:
        [modulator.mod_phase_le.resetColor() for modulator in self.modulators]
        return [modulator.getPhase() for modulator in self.modulators]

    def setPhases(self, phases) -> None:
        for index, phase in enumerate(phases):
            if index > len(self.modulators): break
            self.modulators[index].setPhase(phase)
        return

    def getdf(self) -> float:
        self.df_le.resetColor()
        return self.df_le.getValue()

    def setdf(self, value) -> None:
        self.df_le.setValue(value)
        self.df_t_rg.updateFactor1()
        self.t_le.resetColor()
        return

    def setMeasuredAmplitudes(self, amplitudes) -> None:
        for index, amplitude in enumerate(amplitudes):
            if index > len(self.modulators): break
            self.modulators[index].setMeasuredAmplitude(amplitude)
        return

    def setMeasuredPhases(self, phases) -> None:
        for index, phase in enumerate(phases):
            if index > len(self.modulators): break
            self.modulators[index].setMeasuredPhase(phase)
        return

    def getInputs(self) -> list:
        return [int(modulator.input.state_index + 1) for modulator in self.modulators]

    def setInputs(self, input_mask) -> None:
        for index, value in enumerate(input_mask):
            if index > len(self.modulators): break
            try: self.modulators[index].setInput(value)
            except: pass
        return

    def getOutputs(self) -> np.ndarray:
        output_mask = np.zeros((32, 2), dtype = int)
        for index, modulator in enumerate(self.modulators):
            if modulator.state_button.isChecked():
                if modulator.output.state_name == "1": output_mask[index] = [1, 0]
                else: output_mask[index] = [0, 1]
        return output_mask.transpose()

    def setOutputs(self, output_masks: np.ndarray) -> None:
        for index, modulator in enumerate(output_masks.transpose()):
            if index > len(self.modulators): break
            
            if 1 in modulator:
                self.modulators[index].state_button.setState("on")
                if modulator[0] == 1: self.modulators[index].output.setState("1")
                elif modulator[1] == 1: self.modulators[index].output.setState("2")
            else:
                self.modulators[index].state_button.setState("off")
        return

    def setZeroVolumes(self) -> None:
        try:
            [modulator.volume.setValue(0) for modulator in self.modulators]
            self.sendVolumes()
        except:
            pass
        return

    def extrapolate(self, target: str = "", index: int = 1) -> None:
        if index < 1 or index > len(self.modulators) - 1: return
        
        match target:
            case "outputs":
                current_value = self.modulators[index].output.state_index
                previous_value = self.modulators[index - 1].output.state_index
                difference = current_value - previous_value
                
                for new_index in range(index + 1, len(self.modulators)):
                    modulator = self.modulators[new_index]
                    new_state_index = (current_value + (new_index - index) * difference) % len(modulator.output.states)
                    modulator.output.setState(new_state_index)

            case "inputs":
                current_value = self.modulators[index].input.state_index
                previous_value = self.modulators[index - 1].input.state_index
                difference = current_value - previous_value
                
                for new_index in range(index + 1, len(self.modulators)):
                    modulator = self.modulators[new_index]
                    new_state_index = (current_value + (new_index - index) * difference) % len(modulator.input.states)
                    modulator.input.setState(new_state_index)

            case "frequencies":
                current_value = self.modulators[index].getFrequency()
                previous_value = self.modulators[index - 1].getFrequency()
                difference = current_value - previous_value
                
                for new_index in range(index + 1, len(self.modulators)):
                    modulator = self.modulators[new_index]
                    new_frequency = current_value + (new_index - index) * difference
                    modulator.setFrequency(new_frequency)
                    self.tone_rgs[new_index].updateFactor1()

            case _:
                pass        
        return

    def sendVolumes(self) -> None:
        overal_volume = int(self.volume.line_edit.getValue())
        audio_button_state_index = self.audio_button.state_index
        
        if overal_volume == 0 and audio_button_state_index == 1:
            self.audio_button.clicked.emit()
            self.audio_button.setState(0)
        elif overal_volume > 0 and audio_button_state_index == 0:
            self.audio_button.clicked.emit()
            self.audio_button.setState(1)
        
        volumes = [int(modulator.volume.line_edit.getValue() * overal_volume) for modulator in self.modulators]
        self.volumes.emit(volumes)
        return



class WaveFormWidget(QtWidgets.QWidget):
    def __init__(self, colors: list = [], orientation: str = "h", n_outputs = 2, n_inputs = 4, n_modulators: int = 32, buffer_size: int = 256):
        super().__init__()
        
        self.n_outputs = n_outputs
        self.n_inputs = n_inputs
        self.n_modulators = n_modulators
        self.buffer_size = buffer_size
        if len(colors) < 1: colors = ["#ffffff"]
        
        self.wave_plot = SCTWidgets.PlotWidget(colors = colors, buffer_size = self.buffer_size, n_channels = n_outputs + n_inputs + 1)
        self.fourier_plot = SCTWidgets.PlotWidget(colors = colors, buffer_size = self.buffer_size, n_channels = n_outputs + n_inputs + 1)
        if orientation == "h": self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        else: self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        self.widget_layout = make_layout("h")
        self.checkboxes = [SCTWidgets.CheckBox(color = colors[index + 1 % len(colors)]) for index in range(n_outputs)] + [SCTWidgets.CheckBox(color = colors[index + 1 % len(colors)]) for index in range(n_outputs, n_outputs + n_inputs)]
        self.checkbox_labels = [SCTWidgets.Label(text = f"output {index + 1}") for index in range(n_outputs)]
        self.checkbox_labels.extend([SCTWidgets.Label(text = f"input {index - n_outputs + 1}") for index in range(n_outputs, n_inputs + n_outputs)])
        self.checkboxes_layout = make_layout("g")
        [self.checkboxes_layout.addWidget(self.checkboxes[index], index, 0) for index in range(len(self.checkboxes))]
        [self.checkboxes_layout.addWidget(self.checkbox_labels[index], index, 1) for index in range(len(self.checkbox_labels))]
        self.checkboxes_layout.setRowStretch(len(self.checkboxes), 1)
        [self.checkboxes[index].setState(1) for index in range(len(self.checkboxes))]
        
        self.wave_plot.setHLines(0)
        self.wave_plot.setVLines(0)
        self.fourier_plot.setHLines(0)
        self.fourier_plot.setVLines(0)
        
        self.wave_plot.setLabel("left", "V (mV)")
        self.fourier_plot.setLabel("left", "V (mV)")
        self.wave_plot.setXAxis(0)
        self.fourier_plot.setXAxis(0)
        self.wave_plot.setLabel("bottom", "t (ms)")
        self.fourier_plot.setLabel("bottom", "f (Hz)")
        self.wave_plot.pdis[0].setVisible(False)
        self.fourier_plot.pdis[0].setVisible(False)
        
        [self.splitter.addWidget(plot) for plot in [self.wave_plot, self.fourier_plot]]
        self.widget_layout.addWidget(self.splitter)
        self.widget_layout.addLayout(self.checkboxes_layout)
        self.setLayout(self.widget_layout)
        
        self.df = 10
        self.max_freq = 100
        self.f_amp_phase_buffer = np.zeros((2* n_outputs + 2 * n_inputs + 1, n_modulators + 2), dtype = np.float32)
        self.dc_biases_mV = np.zeros((n_outputs), dtype = np.float32)
        self.dc_center_mV = 0
        self.input_mask = np.full((n_modulators), 1, dtype = int)
        self.output_masks = np.full((n_outputs, n_modulators), 0, dtype = int)
        
        # Scaling
        self.wave_plot_vb = self.wave_plot.getViewBox()
        self.fourier_plot_vb = self.fourier_plot.getViewBox()
        self.wave_plot_vb.sigYRangeChanged.connect(self.wavePlotYRangeChanged)
        self.wave_plot_vb.sigXRangeChanged.connect(self.wavePlotTRangeChanged)
        self.fourier_plot_vb.sigXRangeChanged.connect(self.fourierPlotFRangeChanged)
        self.updating_range = False
        [self.checkboxes[index].clicked.connect(self.updateVisiblePDIS) for index in range(len(self.checkboxes))]



    def updateVisiblePDIS(self) -> None:
        for index in range(self.n_outputs + self.n_inputs):
            trace_checked = self.checkboxes[index].isChecked()
            self.wave_plot.pdis[index + 1].setVisible(trace_checked)
            self.fourier_plot.pdis[index + 1].setVisible(trace_checked)
        return

    def wavePlotTRangeChanged(self, viewbox, t_range) -> None:
        if self.updating_range: return
        self.updating_range = True

        t_min, t_max = t_range
        if t_min < 0: t_min = 0 # Do not allow going left of the origin
        self.wave_plot.setXRange(t_min, t_max, padding = 0)
        
        t_total = t_max - t_min
        f_total = (self.max_freq / self.df) * (1000 / t_total)
        self.fourier_plot.setXRange(0, f_total, padding = 0)

        self.updating_range = False
        return

    def fourierPlotFRangeChanged(self, viewbox, f_range) -> None:
        if self.updating_range: return
        self.updating_range = True

        f_min, f_max = f_range
        if f_min < 0: f_min = 0 # Do not allow going left of the origin
        self.fourier_plot.setXRange(f_min, f_max, padding = 0)
        
        f_total = f_max - f_min
        t_total = (self.max_freq / self.df) * (1000 / f_total)
        self.wave_plot.setXRange(0, t_total, padding = 0)

        self.updating_range = False
        return

    def wavePlotYRangeChanged(self, viewbox, y_range) -> None:
        wave_min = np.min(self.wave_plot.buffer[1:, :])
        wave_max = np.max(self.wave_plot.buffer[1:, :])
        wave_avg = .5 * wave_max + .5 * wave_min

        y_min, y_max = y_range
        y_total = y_max - y_min
        self.wave_plot.setYRange(wave_avg - .5 * y_total, wave_avg + .5 * y_total, padding = 0)
        return

    def setDCBiases(self, values: list | np.ndarray) -> None:
        for index in range(self.n_outputs): self.dc_biases_mV[index] = 1000 * values[index]
        self.f_amp_phase_buffer[1, 0] = self.dc_biases_mV[0]
        self.f_amp_phase_buffer[2, 0] = self.dc_biases_mV[1]
        
        dc_min = min(self.dc_biases_mV)
        dc_max = max(self.dc_biases_mV)
        self.dc_center_mV = (dc_max + dc_min) / 2
        return

    def setdf(self, df_Hz: int | float) -> None:
        self.df = df_Hz
        t_ms = 1000 / df_Hz
        self.wave_plot.setVLines([0, t_ms])
        max_n = int(self.max_freq / df_Hz)
        
        vlines = self.df * np.arange(max_n + 2)
        if len(vlines) > 20: vlines = vlines[1::2]
        vline_list = list(vlines)
        self.fourier_plot.setVLines(vline_list)
        return
    
    def setInputs(self, input_mask: np.ndarray) -> None:
        self.input_mask = input_mask.copy()
        return

    def setOutputs(self, output_masks: np.ndarray) -> None:
        self.output_masks = output_masks.copy()
        return

    def setFrequencies(self, frequencies: np.ndarray) -> None:
        freqs = frequencies.copy()
        self.max_freq = max(freqs) + self.df
        f_data = np.append(freqs, self.max_freq) # Add padding frequencies to flank the data
        self.f_amp_phase_buffer[0, 1 : len(f_data) + 1] = f_data
        return

    def setAmplitudes(self, amplitudes: np.ndarray) -> None:
        for row in range(1, 1 + self.n_outputs): self.f_amp_phase_buffer[row] *= 0 # clear
        self.f_amp_phase_buffer[1, 0] = self.dc_biases_mV[0]
        self.f_amp_phase_buffer[2, 0] = self.dc_biases_mV[1]
        
        for mod_index, amplitude in enumerate(amplitudes):
            if mod_index > self.n_modulators: break
            
            output_channels = self.output_masks[:, mod_index]
            if np.sum(output_channels) < 1: continue
            
            for channel_index, value in enumerate(output_channels):
                if value == 1: self.f_amp_phase_buffer[1 + channel_index, mod_index + 1] += amplitude
        return

    def setPhases(self, phases: np.ndarray, unit: str = "deg") -> None:
        if unit == "deg": phases_rad = np.deg2rad(phases)
        else: phases_rad = phases
        
        for row in range(1 + self.n_outputs + self.n_inputs, 1 + 2 * self.n_outputs + self.n_inputs): self.f_amp_phase_buffer[row] *= 0 # clear
        self.f_amp_phase_buffer[1, 0] = self.dc_biases_mV[0]
        self.f_amp_phase_buffer[2, 0] = self.dc_biases_mV[1]
        
        for mod_index, phase in enumerate(phases_rad):
            if mod_index > self.n_modulators: break
            
            output_channels = self.output_masks[:, mod_index]
            if np.sum(output_channels) < 1: continue
            
            for channel_index, value in enumerate(output_channels):
                if value == 1: self.f_amp_phase_buffer[1 + self.n_outputs + self.n_inputs + channel_index, mod_index + 1] += phase
        return

    def readPixel(self, pixel: np.ndarray) -> None:
        amps_mV = np.real(pixel) * 2000
        phases_rad = np.angle(pixel)
        
        self.setMeasuredPhases(phases_rad)
        self.setMeasuredAmplitudes(amps_mV)
        self.updatePlots()
        return

    def setMeasuredAmplitudes(self, amplitudes: np.ndarray) -> None:
        for row in range(1 + self.n_outputs, 1 + self.n_outputs + self.n_inputs): self.f_amp_phase_buffer[row] *= 0
    
        for mod_index, amplitude in enumerate(amplitudes):
            if mod_index > self.n_modulators: break
            input_channel = self.input_mask[mod_index]
            self.f_amp_phase_buffer[self.n_outputs + input_channel, mod_index + 1] += amplitude
        return

    def setMeasuredPhases(self, phases_rad: np.ndarray) -> None:
        for row in range(1 + 2 * self.n_outputs + self.n_inputs, 1 + 2 * self.n_outputs + 2 * self.n_inputs): self.f_amp_phase_buffer[row] *= 0
    
        for mod_index, phase in enumerate(phases_rad):
            if mod_index > self.n_modulators: break
            input_channel = self.input_mask[mod_index]
            self.f_amp_phase_buffer[self.n_inputs + 2 * self.n_outputs + input_channel, mod_index + 1] += phase
        return

    def updatePlots(self) -> None:
        self.updateFourierPlot()
        self.updateWavePlot()
        return

    def updateFourierPlot(self) -> None:
        self.fourier_plot.setData(np.abs(self.f_amp_phase_buffer[: self.n_outputs + self.n_inputs + 1]))
        self.fourier_plot.plotData()
        return

    def updateWavePlot(self) -> None:
        t_ms = 1000 / self.df
        
        wave_data = np.zeros((self.n_outputs + self.n_inputs + 1, self.buffer_size))
        t = np.linspace(0, t_ms, self.buffer_size, dtype = np.float32)
        wave_data[0] = t
        
        for wave_index in range(self.n_outputs + self.n_inputs):
            wave = np.zeros_like(t, dtype = np.float32)
            
            for freq_Hz, amp_mV, phase_rad in zip(self.f_amp_phase_buffer[0], self.f_amp_phase_buffer[wave_index + 1], self.f_amp_phase_buffer[wave_index + self.n_outputs + self.n_inputs + 1]):
                if np.abs(amp_mV) < .0001: continue
                w = 2 * np.pi * freq_Hz / 1000
                wave += amp_mV * np.cos(w * t + phase_rad)
            wave_data[wave_index + 1] = wave
        self.wave_plot.setData(wave_data)
        self.wave_plot.plotData()
        return



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

