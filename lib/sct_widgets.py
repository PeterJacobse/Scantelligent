import re, types
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
            self.setFixedSize(self.button_size + 12, self.button_size + 12)
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
            size = kwargs.pop("size", None)
            color = kwargs.pop("color", None)            
            if not isinstance(size, int): size = 8
            
            super().__init__(*args, size = size, **kwargs)
            
            self.setStates([{"name": "unchecked", "color": "#101010"}, {"name": "checked", "color": "#2090ff"}])
            if isinstance(color, str): self.setColor(color)
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
            self.base_color = kwargs.pop("base_color", "#101010")
            self.edited_color = kwargs.pop("edited_color", None)
            self.warning_color = kwargs.pop("warning_color", None)
            
            super().__init__(parent)
            
            self.setDefaults()
            if not self.block: self.editingFinished.connect(self.addUnit)
            if isinstance(self.edited_color, str): self.editingFinished.connect(lambda: self.setColor(self.edited_color))
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

        def setWarning(self, tooltip: str = "") -> None:
            if isinstance(self.warning_color, str):
                self.setColor(self.warning_color)
            self.old_tooltip = self.toolTip()
            self.setToolTip(tooltip)
            return

        def resetWarning(self) -> None:
            self.setToolTip(self.old_tooltip)
            self.resetColor()
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
                self.addUnit()
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
                if isinstance(self.limits, list):
                    if number < self.limits[0]: number = self.limits[0]
                    if number > self.limits[1]: number = self.limits[1]

                # Add the unit to the number
                if isinstance(self.digits, int):
                    number = round(number, self.digits)
                if isinstance(self.digits, int) and self.digits < 1:
                    number = int(number)
                
                return number

            return entered_text

        def setValue(self, value, edited_color: bool = False) -> None:
            # Method for programatically setting a value or str
            if isinstance(value, int) or isinstance(value, float):
                number = value

                if isinstance(self.digits, int):
                    number = round(number, self.digits)
                    if self.digits < 1: number = int(number)

                if isinstance(self.unit, str):
                    if isinstance(self.digits, int): self.setText(f"{number:.{self.digits}f} {self.unit}")
                    else: self.setText(f"{number} {self.unit}")
                else:
                    if isinstance(self.digits, int): self.setText(f"{number:.{self.digits}f}")
                    else: self.setText(f"{number}")                    
            
            else:
                self.setText(f"{value}")
            
            if edited_color: self.setColor(self.edited_color)
            else: self.resetColor()
            return

        def wheelEvent(self, event) -> None:
            if not self.hasFocus(): return # Only accept scrolling if it is selected
            
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

        def __init__(self, parent = None, tooltip: str = "", limits: list = [-180, 180], value: float = 0, digits: int = 0, max_width = 150, unit = None, orientation: str = "h",
                     minmax_buttons: bool = False, min_button_icon: QtGui.QIcon = None, max_button_icon: QtGui.QIcon = None):
            super().__init__(parent)
            [self.min_val, self.max_val] = limits

            # 1: Create the widgets
            self.slider = SCTWidgets.Slider(orientation = orientation, tooltip = tooltip)
            self.line_edit = SCTWidgets.PhysicsLineEdit(max_width = max_width, unit = unit, limits = limits, digits = digits, tooltip = tooltip)
            if orientation == "v": self.slider.setMinimumHeight(20)

            if minmax_buttons:
                if isinstance(min_button_icon, QtGui.QIcon): self.min_button = SCTWidgets.MultiStateButton(tooltip = "set slider to minimum", icon = min_button_icon)
                else: self.min_button = SCTWidgets.MultiStateButton(tooltip = "set slider to minimum")
                if isinstance(max_button_icon, QtGui.QIcon): self.max_button = SCTWidgets.MultiStateButton(tooltip = "set slider to maximum", icon = max_button_icon)
                else: self.max_button = SCTWidgets.MultiStateButton(tooltip = "set slider to maximum")

            # 2: Configure widgets
            self.slider.setRange(self.min_val, self.max_val)
            [widget.setValue(value) for widget in [self.slider, self.line_edit]]

            # 3: Set up the layout
            if orientation == "h": self.widget_layout = QtWidgets.QHBoxLayout()
            else:
                self.widget_layout = QtWidgets.QVBoxLayout()
                self.widget_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            
            if minmax_buttons:
                if orientation == "v": self.widget_layout.addWidget(self.max_button, alignment = QtCore.Qt.AlignmentFlag.AlignCenter)
                else: self.widget_layout.addWidget(self.min_button)
            self.widget_layout.addWidget(self.slider, 0, QtCore.Qt.AlignmentFlag.AlignCenter)
            self.widget_layout.addWidget(self.line_edit)
            if minmax_buttons:
                if orientation == "v": self.widget_layout.addWidget(self.min_button, alignment = QtCore.Qt.AlignmentFlag.AlignCenter)
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
        position_signal_middle_button = QtCore.pyqtSignal(float, float)
        
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

            # Call base class implementation
            return super().mouseDoubleClickEvent(event)
        
        def mousePressEvent(self, event):
            if event.button() == QtCore.Qt.MouseButton.MiddleButton:
                # Get scene position
                pos = event.position()
                
                mapped_pos = self.view.mapToView(pos)
                self.position_signal_middle_button.emit(mapped_pos.x(), mapped_pos.y())
                
            # Call base class implementation
            return super().mousePressEvent(event)

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
        def __init__(self, parent = None, color: str = "#4080FF", limits: list = [0, 100], tooltip: str = "", show_tick: bool = True):
            super().__init__(parent)
            
            self.setToolTip(tooltip)
            self.show_tick = show_tick
            self.min = limits[0]
            self.max = limits[1]
            self.total = self.max - self.min
            self.level = 0
            self.tick_level = 0
            self.color = color
            #self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
            self.setFixedWidth(20)
            self.setMinimumHeight(80)



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
            self.update() # Triggers repaint
            return
        
        def getTickValue(self) -> float:
            return self.tick_level

        def setTickValue(self, value: float = 0) -> None:
            self.tick_level = max(self.min, min(value, self.max))
            self.update() # Triggers repaint
            return

        def paintEvent(self, event):
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)
            
            width = self.width()
            height = self.height()
            
            cyl_width = width * 0.6
            cyl_height = height * 0.9
            x_offset = (width - cyl_width) / 2
            y_offset = (height - cyl_height) / 2
            
            # Draw Liquid
            cylinder_fraction = (self.level - self.min) / (self.total)            
            liquid_height = int(cylinder_fraction * cyl_height)
            liquid_rect = QtCore.QRectF(x_offset, y_offset + (cyl_height - liquid_height), cyl_width, liquid_height)
            painter.setPen(QtCore.Qt.PenStyle.NoPen)
            painter.setBrush(QtGui.QBrush(QtGui.QColor(self.color)))
            painter.drawRect(liquid_rect)
            
            # Draw Cylinder Outline
            painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.gray, 2))
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            painter.drawRect(int(x_offset), int(y_offset), int(cyl_width), int(cyl_height + 1))
            
            # Draw Graduations
            painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.gray, 2))
            painter.setBrush(QtCore.Qt.BrushStyle.NoBrush)
            num_marks = 5
            for i in range(num_marks + 1):
                y = y_offset + (i * (cyl_height / num_marks))
                painter.drawLine(int(x_offset + cyl_width), int(y), int(x_offset + cyl_width - 4), int(y))
            
            # Draw tick
            if not self.show_tick: return
            painter.setPen(QtGui.QPen(QtCore.Qt.GlobalColor.red, 2))
            tick_height = cyl_height * (self.tick_level - self.min) / (self.total)
            painter.drawLine(int(x_offset + cyl_width), int(y_offset - tick_height), int(x_offset + cyl_width - 6), int(y_offset - tick_height))
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
            
            super().__init__(*args, **kwargs)
            
            if isinstance(title, str): self.setTitle(title)
            if isinstance(tooltip, str): self.setToolTip(tooltip)

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
            
            self.factor0_warn_if_not_integer = False
            factor0_warn_if_not_integer = kwargs.pop("factor0_warn_if_not_integer", None)
            if isinstance(factor0_warn_if_not_integer, bool): self.factor0_warn_if_not_integer = factor0_warn_if_not_integer
            self.factor1_warn_if_not_integer = False
            factor1_warn_if_not_integer = kwargs.pop("factor1_warn_if_not_integer", None)
            if isinstance(factor1_warn_if_not_integer, bool): self.factor1_warn_if_not_integer = factor1_warn_if_not_integer

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

            self.product_value = (self.max_value - self.min_value) * self.factor
            return self.product_value

        def getFactors(self) -> tuple[float, float]:
            if isinstance(self.factor0, SCTWidgets.PhysicsLineEdit):
                self.factor0_value = self.factor0.getValue() # Get factor0
                if self.factor0_warn_if_not_integer and not round(self.factor0_value * 10000) % 10000 == 0: self.factor0.setWarning()
            else:
                self.factor0_value = self.factor0
            
            if isinstance(self.factor1, SCTWidgets.PhysicsLineEdit):
                self.factor1_value = self.factor1.getValue() # Get factor1
                if self.factor1_warn_if_not_integer and not round(self.factor1_value * 10000) % 10000 == 0: self.factor0.setWarning()
            else:
                self.factor1_value = self.factor1
            
            return (self.factor0_value, self.factor1_value)

        def factor0Changed(self) -> None:
            factor0_value = self.factor0.getValue() # Get the new value
            factor0_value = self.factor0_constraint(factor0_value) # Apply the constraint, e.g. an integer value or a multiple of 16
            self.factor0.setValue(factor0_value)
            
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
            self.factor1.setValue(factor1_value)
            
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
                self.factor0.setValue(constrained_factor0_value)
                if not constrained_factor0_value == new_factor0_value:
                    self.bounce += 1
                    if self.lock == "factor1" and isinstance(self.max, SCTWidgets.PhysicsLineEdit): self.updateProduct()
                    else: self.updateFactor1()
                else:
                    self.bounce = 0
                
                # Set a warning if requested
                if self.factor0_warn_if_not_integer and not round(new_factor0_value * 10000) % 10000 == 0: self.factor0.setWarning()
                else: self.factor0.resetWarning()
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
                self.factor1.setValue(constrained_factor1_value)
                if not constrained_factor1_value == new_factor1_value:
                    self.bounce += 1
                    if self.lock == "factor0" and isinstance(self.max, SCTWidgets.PhysicsLineEdit): self.updateProduct()
                    else: self.updateFactor0()
                else:
                    self.bounce = 0
                
                # Set a warning if requested
                if self.factor1_warn_if_not_integer and not round(new_factor1_value * 10000) % 10000 == 0: self.factor1.setWarning()
                else: self.factor1.resetWarning()
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
            self.min_line_edits.update({f"{method_name}": SCTWidgets.PhysicsLineEdit(value = min_value, digits = digits, limits = limits, unit = unit, tooltip = tooltip, max_width = max_width)})
            self.min_checkboxes.update({f"{method_name}": SCTWidgets.CheckBox(tooltip = tooltip)})
            self.buttons.update({f"{method_name}": SCTWidgets.MultiStateButton(icon = icon, tooltip = tooltip)})
            self.max_checkboxes.update({f"{method_name}": SCTWidgets.CheckBox(tooltip = tooltip)})
            self.max_line_edits.update({f"{method_name}": SCTWidgets.PhysicsLineEdit(value = max_value, digits = digits, limits = limits, unit = unit, tooltip = tooltip, max_width = max_width)})
            
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
    def __init__(self, feedback_button: SCTWidgets.MultiStateButton, current_le: SCTWidgets.PhysicsLineEdit, height_le: SCTWidgets.PhysicsLineEdit, color: str = "#A0A0A0", show_height_tick: bool = True):
        super().__init__()
        
        self.color = color
        self.current_le = current_le
        self.height_le = height_le
        self.height_le.setMinimumWidth(70)
        self.current_le.setMinimumWidth(70)
        
        self.current_indicator = SCTWidgets.LevelIndicator(color = color)
        self.height_indicator = SCTWidgets.LevelIndicator(color = color, show_tick = False)
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
            indicator_level = np.log10(np.abs(value))
            self.current_indicator.setValue(indicator_level)
        return
    
    def setCurrentTick(self, value) -> None:
        if isinstance(value, float | int):
            tick_level = np.log10(np.abs(value))
            self.current_indicator.setTickValue(tick_level)
        return

    def setHeightTick(self) -> None:
        value = self.height_le.getValue()
        if isinstance(value, float | int): self.height_indicator.setValue(value)
        return



class ModulatorWidget(QtWidgets.QWidget):
    def __init__(self, state_button: SCTWidgets.MultiStateButton, input: SCTWidgets.MultiStateButton, output: SCTWidgets.MultiStateButton,
                 mod_amplitude_le: SCTWidgets.PhysicsLineEdit, demod_amplitude_le: SCTWidgets.PhysicsLineEdit, mod_phase_le: SCTWidgets.PhysicsLineEdit, demod_phase_le: SCTWidgets.PhysicsLineEdit,
                 frequency_le: SCTWidgets.PhysicsLineEdit, number_le: SCTWidgets.PhysicsLineEdit):
        
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
        
        self.df = 100
        
        layout = make_layout("g")
        layout.addWidget(input, 0, 0, 2, 1)
        [layout.addWidget(widget, index, 1) for index, widget in enumerate([self.demod_amplitude_le, self.demod_phase_le])]
        layout.addWidget(state_button, 0, 2, 2, 1)
        [layout.addWidget(widget, index, 3) for index, widget in enumerate([self.number_le, self.frequency_le])]
        [layout.addWidget(widget, index, 4) for index, widget in enumerate([self.mod_amplitude_le, self.mod_phase_le])]
        layout.addWidget(output, 0, 5, 2, 1)
        layout.setContentsMargins(2, 0, 2, 0)
        self.setLayout(layout)

    def setdf(self, value) -> None:
        self.df = value
        return

    def setFrequency(self, value) -> None:
        return self.frequency_le.setValue(value)
    
    def setAmplitude(self, value) -> None:
        return self.mod_amplitude_le.setValue(value)

    def setMeasuredAmplitude(self, value) -> None:
        return self.demod_amplitude_le.setValue(value)

    def setPhase(self, value) -> None:
        return self.mod_phase_le.setValue(value)

    def setMeasuredPhase(self, value) -> None:
        return self.demod_phase_le.setValue(value)

    def readTone(self, value) -> None:
        abs = np.abs(value)
        arg = np.rad2deg(np.angle(value))
        self.setMeasuredAmplitude(abs)
        self.setMeasuredPhase(arg)
        return

    def setInput(self, value) -> None:
        return self.input.setState(value)

    def setOutput(self, value) -> None:
        return self.output.setState(value)



class LockinWidget(QtWidgets.QWidget):
    def __init__(self, modulators: list, df_line_edit: SCTWidgets.PhysicsLineEdit, t_line_edit: SCTWidgets.PhysicsLineEdit):
        super().__init__()
        
        self.modulators = modulators
        self.df_le = df_line_edit
        self.t_le = t_line_edit
        
        self.scroll_area = QtWidgets.QScrollArea()
        self.mod_widget = QtWidgets.QWidget()
        
        layout = make_layout("v")
        
        df_t_layout = make_layout("h")
        [df_t_layout.addWidget(widget) for widget in [self.df_le, self.t_le]]
        layout.addLayout(df_t_layout)
        
        mod_layout = make_layout("v")
        mod_layout.setContentsMargins(2, 0, 2, 0)
        [mod_layout.addWidget(modulator_widget) for modulator_widget in self.modulators]
        self.mod_widget.setLayout(mod_layout)
        self.scroll_area.setWidget(self.mod_widget)
        layout.addWidget(self.scroll_area)
        
        self.setLayout(layout)
        
        self.df_t_rg = SCTWidgets.ReciprocalGroup(product = 1000, factors = [self.df_le, self.t_le])
        #self.tone_rgs = [RG(product = line_edits[f"mla_mod{index}_f"], factors = [line_edits["mla_df"], line_edits[f"mla_mod{index}_n"]],
        #            lock = "factor0", try_to_retain = "product", factor1_warn_if_not_integer = True) for index in range(4)]


    
    def setFrequencies(self, frequencies) -> None:
        for index, frequency in enumerate(frequencies):
            if index > len(self.modulators): break
            self.modulators[index].setFrequency(frequency)
        return

    def setAmplitudes(self, amplitudes) -> None:
        for index, amplitude in enumerate(amplitudes):
            if index > len(self.modulators): break
            self.modulators[index].setAmplitude(amplitude)
        return

    def setPhases(self, phases) -> None:
        for index, phase in enumerate(phases):
            if index > len(self.modulators): break
            self.modulators[index].setPhase(phase)
        return

    def setdf(self, value) -> None:
        self.df_le.setValue(value)
        self.df_t_rg.updateFactor1()
        return

    def getInputs(self) -> list:
        input_mask = []
        [input_mask.append(modulator.input.state_index) for modulator in self.modulators]
        return input_mask

    def setInputs(self, input_mask) -> None:
        for index, value in enumerate(input_mask):
            if index > len(self.modulators): break
            try: self.modulators[index].input.setState(value)
            except: pass
        return

    def getOutputs(self) -> list:
        output_mask = []
        [output_mask.append(modulator.output.state_index) for modulator in self.modulators]
        return output_mask

    def setOutputs(self, input_mask) -> None:
        for index, value in enumerate(input_mask):
            if index > len(self.modulators): break
            try: self.modulators[index].output.setState(value)
            except: pass
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

