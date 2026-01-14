import os
from PyQt6 import QtGui, QtWidgets, QtCore
import pyqtgraph as pg
from typing import Callable
from .gui_items import GUIItems, HoverTargetItem, SmartPushButton



class GUI:
    def __init__(self, icons_path):
        self.icons_path = icons_path
        self.get_icons()
        self.gui_items = GUIItems()

        self.buttons = self.make_buttons()
        self.make_comboboxes = self.make_comboboxes()
        self.shortcuts = self.make_shortcuts()

    def get_icons(self):
        icons_path = self.icons_path
        icon_files = os.listdir(icons_path)
        
        self.icons = {}
        for icon_file in icon_files:
            [icon_name, extension] = os.path.splitext(os.path.basename(icon_file))
            try:
                if extension == ".png": self.icons.update({icon_name: QtGui.QIcon(os.path.join(icons_path, icon_file))})
            except:
                pass

    def make_buttons(self) -> dict:
        make_button = lambda *args, **kwargs: self.gui_items.make_smart_button(*args, parent = self, **kwargs)
        icons = self.icons
        arrow = icons.get("single_arrow")
        mtt = "Move the tip "

        buttons = {
            "scanalyzer": make_button("", "Launch Scanalyzer", icon = icons.get("scanalyzer")),
            "nanonis": make_button("", "Nanonis: offline\n(click to reconnect)", icon = icons.get("nanonis")),
            "mla": make_button("", "Connect to the Multifrequency Lockin Amplifier\n()", icon = icons.get("imp")),
            "camera": make_button("", "Camera on/off\n()", icon = icons.get("scanalyzer")),
            "exit": make_button("", "Exit scantelligent\n(Esc / X / E)", icon = icons.get("escape")),
            "tip_status": make_button("Tip", "Tip status\n(Space to toggle feedback on/off)"),
            "oscillator": make_button("Osc", "Oscillator on/off\n(Ctrl + O)"),
            "view": make_button("Active view", "Toggle the active view\n(V)"),
            "session_folder": make_button("Session folder", "Open the session folder\n(1)"),
            
            "nanonis_bias": make_button("V_nn", "Nanonis bia"),
            "mla_bias": make_button("V_mla", "MLA bias"),
            "swap_bias": make_button("<>", "Swap the bias between Nanonis and the MLA"),
            "set": make_button("Set", "Set the new parameters\n(Ctrl + P)"),
            "get": make_button("Get", "Get parameters\n(P)"),
            
            "withdraw": make_button("Withdraw", "Withdraw the tip\n(Ctrl + W)"),
            "retract": make_button("Retract", "Retract the tip from the surface\n(Ctrl + PgUp)"),
            "advance": make_button("Advance", "Advance the tip towards the surface\n(Ctrl + PgDown)"),
            "approach": make_button("Approach", "Initiate auto approach\n(Ctrl + A)"),

            "n": make_button("", mtt + "north\n(Ctrl + ↑ / Ctrl + 8)", icon = arrow, rotate_icon = 270),
            "ne": make_button("", mtt + "northeast\n(Ctrl + 9)", icon = arrow, rotate_icon = 315),
            "e": make_button("", mtt + "east\n(Ctrl + → / Ctrl + 6)", icon = arrow, rotate_icon = 0),
            "se": make_button("", mtt + "southeast\n(Ctrl + 3)", icon = arrow, rotate_icon = 45),
            "s": make_button("", mtt + "south\n(Ctrl + ↓ / Ctrl + 2)", icon = arrow, rotate_icon = 90),
            "sw": make_button("", mtt + "southwest\n(Ctrl + 1)", icon = arrow, rotate_icon = 135),
            "w": make_button("", mtt + "west\n(Ctrl + ← / Ctrl + 4)", icon = arrow, rotate_icon = 180),
            "nw": make_button("", mtt + "northwest\n(Ctrl + 7)", icon = arrow, rotate_icon = 225),

            "direction": make_button("", "Change scan direction (X)", icon = icons.get("triple_arrow")),

            "full_data_range": make_button("", "Set the image value range to the full data range\n(U)", icons.get("100")),
            "percentiles": make_button("", "Set the image value range by percentiles\n(R)", icons.get("percentiles")),
            "standard_deviation": make_button("", "Set the image value range by standard deviations\n(D)", icons.get("deviation")),
            "absolute_values": make_button("", "Set the image value range by absolute values\n(A)", icons.get("numbers")),
        }
        
        return buttons
    
    def make_comboboxes(self) -> dict:
        make_combobox = self.gui_items.make_smart_combobox
        
        comboboxes = {            
        
        }
        
        return comboboxes
    
    def make_labels(self) -> None:
        pass

    def make_shortcuts(self) -> dict:
        QKey = QtCore.Qt.Key
        QMod = QtCore.Qt.Modifier
        QSeq = QtGui.QKeySequence
        
        shortcuts = {
            "set": QSeq(QMod.CTRL | QKey.Key_P),
            "get": QSeq(QKey.Key_P),
        }
        
        return shortcuts

