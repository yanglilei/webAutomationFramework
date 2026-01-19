from PyQt5.QtWidgets import QWidget, QTextBrowser, QGroupBox, QHBoxLayout

from src.frame.common.qt_log_redirector import qt_logger


class LogPage(QWidget):
    """日志页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.tb_log_info = QTextBrowser()
        self.tb_log_info.document().setMaximumBlockCount(1000)
        self.gb_log_info = QGroupBox("日志")
        qt_logger.signal.connect(self.tb_log_info.append)
        ly_login_info = QHBoxLayout()
        ly_login_info.addWidget(self.tb_log_info)
        self.gb_log_info.setLayout(ly_login_info)
        ly_main = QHBoxLayout()
        ly_main.addWidget(self.gb_log_info)
        self.setLayout(ly_main)