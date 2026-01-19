import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTableWidget,
    QTableWidgetItem, QPushButton, QStyleFactory, QHeaderView
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont


class BatchRunPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # 1. 创建批次列表QTableWidget
        self.batch_table = QTableWidget()
        self.batch_table.setColumnCount(5)
        self.batch_table.setHorizontalHeaderLabels(["批次号", "模板ID", "总用户数", "状态", "创建时间"])

        # 核心设置：确保行高可拖拽（默认就是Interactive，可显式声明）
        self.batch_table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)

        # 可选：设置行高的最小值（避免拖拽到过窄）
        self.batch_table.verticalHeader().setMinimumSectionSize(30)  # 最小行高30px
        # 可选：设置行高的最大值（避免拖拽到过宽）
        self.batch_table.verticalHeader().setMaximumSectionSize(200)  # 最大行高200px

        # 填充测试数据
        self.load_test_data()

        # 2. 控制按钮（演示禁用/恢复行高拖拽）
        self.disable_drag_btn = QPushButton("禁用行高拖拽")
        self.enable_drag_btn = QPushButton("恢复行高拖拽")
        self.reset_height_btn = QPushButton("重置行高为50px")

        self.disable_drag_btn.clicked.connect(self.disable_row_height_drag)
        self.enable_drag_btn.clicked.connect(self.enable_row_height_drag)
        self.reset_height_btn.clicked.connect(self.reset_row_height)

        # 组装布局
        layout.addWidget(self.batch_table)
        layout.addWidget(self.disable_drag_btn)
        layout.addWidget(self.enable_drag_btn)
        layout.addWidget(self.reset_height_btn)
        self.setLayout(layout)

    def load_test_data(self):
        """填充测试数据"""
        self.batch_table.setRowCount(3)
        test_data = [
            ("B202601121123", "1", "5", "排队中", "2026-01-12 10:00"),
            ("B202601122456", "2", "8", "执行中", "2026-01-12 10:10"),
            ("B202601123789", "3", "3", "已结束", "2026-01-12 10:20")
        ]
        for row, (batch_no, tid, user_count, status, ctime) in enumerate(test_data):
            self.batch_table.setItem(row, 0, QTableWidgetItem(batch_no))
            self.batch_table.setItem(row, 1, QTableWidgetItem(tid))
            self.batch_table.setItem(row, 2, QTableWidgetItem(user_count))
            self.batch_table.setItem(row, 3, QTableWidgetItem(status))
            self.batch_table.setItem(row, 4, QTableWidgetItem(ctime))
            # 初始化行高（可选）
            self.batch_table.setRowHeight(row, 50)

    def disable_row_height_drag(self):
        """禁用行高拖拽（设置为Fixed模式）"""
        self.batch_table.verticalHeader().setSectionResizeMode(QHeaderView.Fixed)

    def enable_row_height_drag(self):
        """恢复行高拖拽（设置为Interactive模式）"""
        self.batch_table.verticalHeader().setSectionResizeMode(QHeaderView.Interactive)

    def reset_row_height(self):
        """重置所有行高为50px"""
        for row in range(self.batch_table.rowCount()):
            self.batch_table.setRowHeight(row, 50)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QTableWidget行高拖拽示例")
        self.setGeometry(100, 100, 800, 500)
        self.setCentralWidget(BatchRunPage())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle(QStyleFactory.create("Fusion"))
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())