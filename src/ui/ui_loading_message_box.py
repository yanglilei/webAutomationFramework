from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout
from PyQt5.QtCore import Qt


class LoadingWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 半透明遮罩
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        # self.setModal(True)

        # 加载提示布局
        layout = QVBoxLayout()
        self.label = QLabel("正在加载数据...")
        self.label.setStyleSheet("color: white; font-size: 14px;")
        layout.addWidget(self.label, alignment=Qt.AlignCenter)

        # 白色背景框
        container = QWidget()
        container.setStyleSheet("background-color: rgba(0,0,0,0.7); border-radius: 8px; padding: 20px;")
        container.setLayout(layout)

        main_layout = QVBoxLayout(self)
        main_layout.addWidget(container, alignment=Qt.AlignCenter)

    def showEvent(self, event):
        """显示时居中父窗口"""
        if self.parent():
            self.move(
                self.parent().geometry().center() - self.rect().center()
            )
        super().showEvent(event)