# modules/workers.py
from PyQt6.QtCore import QObject, QRunnable, pyqtSignal, pyqtSlot
import json
import urllib.request
import urllib.error


class WorkerSignals(QObject):
    """
    Класс для сигналов, используемых работниками.
    """
    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)


class ApiWorker(QRunnable):
    """
    Рабочий класс для выполнения API-запросов.
    """

    def __init__(self, fn, *args, **kwargs):
        super().__init__()
        self.fn = fn
        self.args = args
        self.kwargs = kwargs
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        """
        Выполнение задачи.
        """
        try:
            result = self.fn(*self.args, **self.kwargs)
        except Exception as e:
            import traceback
            self.signals.error.emit((e, traceback.format_exc()))
        else:
            self.signals.result.emit(result)
        finally:
            self.signals.finished.emit()
