import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QTableWidget, QTableWidgetItem, QPushButton, QHBoxLayout
)


class TableHideColumnDemo(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("QTableWidget 隐藏列示例")
        self.setGeometry(100, 100, 600, 400)

        # 中心Widget和主布局
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # ========== 创建QTableWidget并添加测试数据 ==========
        self.table = QTableWidget()
        # 设置行列数：5行4列
        self.table.setRowCount(5)
        self.table.setColumnCount(4)
        # 设置列标题
        self.table.setHorizontalHeaderLabels(["姓名", "年龄", "性别", "手机号"])

        # 填充测试数据
        test_data = [
            ["张三", "25", "男", "13800138000"],
            ["李四", "30", "女", "13900139000"],
            ["王五", "28", "男", "13700137000"],
            ["赵六", "35", "女", "13600136000"],
            ["孙七", "22", "男", "13500135000"]
        ]
        for row in range(5):
            for col in range(4):
                self.table.setItem(row, col, QTableWidgetItem(test_data[row][col]))

        main_layout.addWidget(self.table)

        # ========== 控制按钮布局 ==========
        btn_layout = QHBoxLayout()
        # 隐藏“手机号”列（索引3）
        self.btn_hide = QPushButton("隐藏手机号列")
        self.btn_hide.clicked.connect(self.hide_phone_column)
        # 显示“手机号”列
        self.btn_show = QPushButton("显示手机号列")
        self.btn_show.clicked.connect(self.show_phone_column)
        # 切换“年龄”列（索引1）的显示状态
        self.btn_toggle = QPushButton("切换年龄列显示/隐藏")
        self.btn_toggle.clicked.connect(self.toggle_age_column)

        btn_layout.addWidget(self.btn_hide)
        btn_layout.addWidget(self.btn_show)
        btn_layout.addWidget(self.btn_toggle)
        main_layout.addLayout(btn_layout)

    def hide_phone_column(self):
        """隐藏手机号列（索引3）"""
        self.table.setColumnHidden(3, True)
        print(f"手机号列是否隐藏：{self.table.isColumnHidden(3)}")

    def show_phone_column(self):
        """显示手机号列（索引3）"""
        self.table.setColumnHidden(3, False)
        print(f"手机号列是否隐藏：{self.table.isColumnHidden(3)}")

    def toggle_age_column(self):
        """切换年龄列（索引1）的显示状态"""
        current_state = self.table.isColumnHidden(1)
        self.table.setColumnHidden(1, not current_state)
        print(f"年龄列是否隐藏：{self.table.isColumnHidden(1)}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TableHideColumnDemo()
    window.show()
    sys.exit(app.exec_())