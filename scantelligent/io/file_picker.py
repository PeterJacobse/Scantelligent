


def get_file_path_from_dialog(extensions: list[str] | None = None) -> str:
    """
    Opens the safest native dialog depending on the environment (PyQt6, Jupyter Notebook, or Tkinter).
    """
    if extensions:
        pyqt_filter = ";;".join([f"{ext.upper()} Files (*.{ext})" for ext in extensions])
        tk_filter = [(f"{ext.upper()} Files", f"*.{ext}") for ext in extensions]
    else:
        pyqt_filter = "All Files (*)"
        tk_filter = [("All Files", "*.*")]
    
    # Check for an active PyQt6 App
    try:
        from PyQt6.QtWidgets import QApplication, QFileDialog
        if QApplication.instance():
            file_path, _ = QFileDialog.getOpenFileName(None, "Select File", "", pyqt_filter)
            return file_path
    except ImportError:
        pass

    # Fallback to Tkinter only if running as a standard desktop script
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.attributes("-topmost", True)
        root.withdraw()
        file_path = filedialog.askopenfilename(parent = root, title = "Select a File to Open", filetypes = tk_filter)
        root.destroy()
    except Exception as e:
        print(f"Could not open a graphical file dialog: {e}")
        # Absolute fallback: console input
        file_path = input("Please type or paste the absolute file path: ").strip('"\'')

    return file_path
