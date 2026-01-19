from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QPushButton, QGraphicsDropShadowEffect


class ShadowButton(QPushButton):
    def __init__(self, text, parent=None):
        super(ShadowButton, self).__init__(text, parent)
        shadow = QGraphicsDropShadowEffect()
        shadow.setBlurRadius(15)
        shadow.setColor(Qt.red)
        shadow.setOffset(2, 2)
        self.setGraphicsEffect(shadow)
