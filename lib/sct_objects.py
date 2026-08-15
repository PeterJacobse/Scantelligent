from PyQt6.QtCore import QMutex, QMutexLocker



class ThreadSafeDict:
    def __init__(self):
        self._data = {}
        self._mutex = QMutex()
    
    def update(self, entry: dict = {}) -> None:
        if not entry: return
        
        locker = QMutexLocker(self._mutex)
        self._data.update(entry)
        return
    
    def get(self, key: str = "", default = None) -> object:
        locker = QMutexLocker(self._mutex)
        return self._data.get(key, default)
    
    def get_all(self) -> dict:
        locker = QMutexLocker(self._mutex)
        return self._data.copy()

