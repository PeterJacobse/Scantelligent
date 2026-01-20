import re
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg



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

        if isinstance(icon, QtGui.QIcon):
            if type(rotate_icon) == float or type(rotate_icon) == int and rotate_icon != 0:
                try: icon = self.rotate_icon(icon, rotate_icon)
                except: pass
            try: button.setIcon(icon)
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

        if len(items) > 0: box.addItems(items)
        
        return box

    def make_line_edit(self, name: str, tooltip: str = "", unit = None, limits = None) -> PJLineEdit:
        line_edit = PJLineEdit(unit = unit, limits = limits)
        line_edit.setObjectName(name)
        line_edit.setToolTip(tooltip)
        line_edit.setText(name)
        
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
        if not isinstance(items, list): return
        
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



class PJLineEdit(QtWidgets.QLineEdit):
    """
    A QLineEdit with extra method changeToolTip, and which adds a unit after editing is finished
    """
    def __init__(self, parent = None, **kwargs):
        super().__init__(parent)
        self.unit = kwargs.get("unit", None)
        self.limits = kwargs.get("limits", None)
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
        numbers = [float(x) for x in number_matches]
        
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

