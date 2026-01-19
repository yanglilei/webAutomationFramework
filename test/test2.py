import sys
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QTableWidget, QTableWidgetItem, QPushButton,
                             QComboBox, QLineEdit, QListWidget, QLabel, QSpinBox,
                             QMessageBox, QApplication)
from PyQt5.QtCore import Qt


class TemplateSelectPage(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()

    def init_ui(self):
        # 1. 筛选区布局
        filter_layout = QHBoxLayout()
        self.project_combo = QComboBox()
        self.project_combo.addItems(["全部项目", "项目A", "项目B"])  # 实际从数据库加载
        self.business_combo = QComboBox()
        self.business_combo.addItems(["全部类型", "learning", "exam", "login"])
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("搜索模板名称...")
        filter_layout.addWidget(QLabel("项目："))
        filter_layout.addWidget(self.project_combo)
        filter_layout.addWidget(QLabel("业务类型："))
        filter_layout.addWidget(self.business_combo)
        filter_layout.addWidget(QLabel("模板名称："))
        filter_layout.addWidget(self.search_edit)

        # 2. 模板列表
        self.template_table = QTableWidget()
        self.template_table.setColumnCount(5)
        self.template_table.setHorizontalHeaderLabels(["模板ID", "模板名称", "业务类型", "状态", "创建时间"])
        # 加载模板数据（实际从tb_task_template查询）
        self.load_template_data()

        # 3. 用户选择区
        user_layout = QHBoxLayout()
        self.user_list = QListWidget()
        self.user_list.setSelectionMode(QListWidget.MultiSelection)
        # 加载用户列表（示例数据）
        for user in ["用户1(ID:1)", "用户2(ID:2)", "用户3(ID:3)"]:
            self.user_list.addItem(user)
        self.selected_user_label = QLabel("已选中：0个用户")
        self.user_list.itemSelectionChanged.connect(self.update_selected_user_count)

        # 4. 批次配置区
        config_layout = QHBoxLayout()
        self.priority_spin = QSpinBox()
        self.priority_spin.setRange(1, 10)
        self.priority_spin.setValue(5)
        config_layout.addWidget(QLabel("批次优先级："))
        config_layout.addWidget(self.priority_spin)
        config_layout.addStretch()
        config_layout.addWidget(self.selected_user_label)

        # 5. 操作按钮
        btn_layout = QHBoxLayout()
        self.create_batch_btn = QPushButton("创建执行批次")
        self.reset_btn = QPushButton("重置选择")
        self.create_batch_btn.clicked.connect(self.create_task_batch)
        self.reset_btn.clicked.connect(self.reset_selection)
        btn_layout.addStretch()
        btn_layout.addWidget(self.create_batch_btn)
        btn_layout.addWidget(self.reset_btn)

        # 整体布局
        main_layout = QVBoxLayout()
        main_layout.addLayout(filter_layout)
        main_layout.addWidget(self.template_table)
        main_layout.addWidget(self.user_list)
        main_layout.addLayout(config_layout)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)

    def reset_selection(self):
        pass

    def load_template_data(self):
        """加载任务模板数据（模拟数据库查询）"""
        self.template_table.setRowCount(0)
        # 示例数据：ID、名称、业务类型、状态（启用/停用）、创建时间
        templates = [
            (1, "学习任务模板", "learning", "启用", "2026-01-10 10:00"),
            (2, "考试任务模板", "exam", "启用", "2026-01-10 11:00"),
            (3, "登录任务模板", "login", "停用", "2026-01-10 12:00")
        ]
        for row, (tid, name, btype, status, ctime) in enumerate(templates):
            self.template_table.insertRow(row)
            self.template_table.setItem(row, 0, QTableWidgetItem(str(tid)))
            self.template_table.setItem(row, 1, QTableWidgetItem(name))
            self.template_table.setItem(row, 2, QTableWidgetItem(btype))
            self.template_table.setItem(row, 3, QTableWidgetItem(status))
            self.template_table.setItem(row, 4, QTableWidgetItem(ctime))
        # 自适应列宽
        self.template_table.horizontalHeader().setStretchLastSection(True)

    def update_selected_user_count(self):
        """更新选中用户数量"""
        count = len(self.user_list.selectedItems())
        self.selected_user_label.setText(f"已选中：{count}个用户")

    def create_task_batch(self):
        """创建执行批次（模拟写入tb_task_batch）"""
        # 1. 校验选中状态
        selected_template_rows = self.template_table.selectedItems()
        if not selected_template_rows:
            QMessageBox.warning(self, "提示", "请先选择一个任务模板！")
            return
        selected_user_count = len(self.user_list.selectedItems())
        if selected_user_count == 0:
            QMessageBox.warning(self, "提示", "请至少选择一个执行用户！")
            return

        # 2. 获取选中模板ID和优先级
        template_id = self.template_table.item(selected_template_rows[0].row(), 0).text()
        priority = self.priority_spin.value()

        # 3. 模拟调用后端创建批次（实际需连接数据库写入tb_task_batch）
        batch_no = f"B{20260111}{int(template_id)}{selected_user_count}"  # 生成批次号
        QMessageBox.information(self, "成功", f"批次创建成功！\n批次号：{batch_no}\n是否跳转到批次运行页？")
        # 此处可添加跳转到批次运行页的逻辑


# 测试主窗口
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("任务执行系统")
        self.setGeometry(100, 100, 800, 600)
        self.setCentralWidget(TemplateSelectPage())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec_())