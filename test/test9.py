import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QLabel, QPushButton
)
from PyQt5.QtCore import Qt

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QLabel 动态修改文本")
        self.setFixedSize(400, 200)

        # 初始化中心组件和布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setAlignment(Qt.AlignCenter)

        # 1. 创建QLabel（初始文本）
        self.label = QLabel("初始文本内容")
        # 设置字体大小，方便查看
        self.label.setStyleSheet("font-size: 16px;")
        layout.addWidget(self.label)

        # 2. 创建按钮，点击触发文本修改
        btn = QPushButton("点击修改标签文本")
        btn.clicked.connect(self.change_label_text)
        layout.addWidget(btn)

        # 计数变量（演示动态文本）
        self.count = 0

    def change_label_text(self):
        """点击按钮修改QLabel文本的回调函数"""
        self.count += 1
        # 核心操作：调用setText()修改文本
        new_text = f"文本已修改 {self.count} 次"
        self.label.setText(new_text)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())