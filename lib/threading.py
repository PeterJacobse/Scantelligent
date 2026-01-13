import html
import numpy as np
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot



class WorkerSignals(QObject):
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(int)



class Worker1(QRunnable):
    """
    Worker thread to run a function in a separate thread.
    """
    def __init__(self, target_function, *args, **kwargs):
        super().__init__()
        self.target_function = target_function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()
        self.setAutoDelete(True)

    @pyqtSlot()
    def run(self):
        """
        Initialize the runner function with passed args, kwargs, and emit signals.
        """
        try:
            # Execute the function with arguments
            result = self.target_function(*self.args, **self.kwargs)
        except:
            self.signals.error.emit()
        else:
            # Emit result signal on success
            self.signals.result.emit(result)
        finally:
            # Emit finished signal
            self.signals.finished.emit()



class Worker(QRunnable):
    def __init__(self, target_function, *args, **kwargs):
        super().__init__()
        self.target_function = target_function
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        # Inject the signals bridge into the function's arguments
        self.kwargs['progress_callback'] = self.signals.update_received
        try:
            self.target_function(*self.args, **self.kwargs)
        finally:
            self.signals.finished.emit()