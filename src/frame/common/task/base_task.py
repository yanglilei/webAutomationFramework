from PyQt5.QtCore import QObject, pyqtSignal


class BaseTask(QObject):
    finished = pyqtSignal()

    def __init__(self):
        super().__init__()

    def run(self):
        pass
