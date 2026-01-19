from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QMessageBox

from src.ui.config_center.ui_node import UINodeInTaskConfigPage
from src.ui.config_center.ui_task_tmpl_node_mapping import UITaskNodeMapping


class UIConfigTaskNodes(QWidget):
    # class TaskConfigUI(QMainWindow):
    def __init__(self, task_tmpl_id: int, start_node_id: int):
        super().__init__()
        self.task_list = []
        self.ui_task_node_mapping = UITaskNodeMapping(task_tmpl_id, start_node_id)
        self.ui_node_in_task_config = UINodeInTaskConfigPage(task_tmpl_id)
        self.init_ui()
        self.init_signal()

    def init_ui(self):
        # self.setWindowTitle("任务配置中心 - 列表带按钮版")
        # self.setGeometry(100, 100, 1100, 600)
        # self.setFont(QFont("Microsoft YaHei", 9))
        # central_widget = QWidget()
        # self.setCentralWidget(central_widget)
        # main_layout = QHBoxLayout(central_widget)
        main_layout = QHBoxLayout()
        # main_layout.setSpacing(20)
        # main_layout.setContentsMargins(20, 20, 20, 20)

        # 左侧任务管理区
        task_widget = QWidget()
        task_layout = QVBoxLayout(task_widget)
        task_layout.setSpacing(15)
        task_title = QLabel("📋 已配置节点（设置前后节点和起始节点）")
        task_title.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        task_layout.addWidget(task_title)

        self.ui_task_node_mapping.setMinimumWidth(680)  # 加宽适配按钮
        task_layout.addWidget(self.ui_task_node_mapping)

        # 右侧节点配置区（无修改）
        node_widget = QWidget()
        node_layout = QVBoxLayout(node_widget)
        node_layout.setSpacing(10)
        self.node_title = QLabel("⚙️ 节点列表（勾选+保存）")
        self.node_title.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        node_layout.addWidget(self.node_title)
        node_layout.addWidget(self.ui_node_in_task_config)

        main_layout.addWidget(task_widget, 7)
        main_layout.addWidget(node_widget, 3)
        self.setLayout(main_layout)
        # self.statusBar().showMessage("就绪 - 任务列表每行自带编辑/删除按钮")

    def init_signal(self):
        #     self.task_list_widget.currentItemChanged.connect(self.refresh_node_list)
        self.ui_node_in_task_config.chosen_node_signal.connect(self.ui_task_node_mapping.async_refresh_table)

    # ✨ 辅助方法：刷新任务列表（编辑/删除后同步UI）
    def refresh_all_task_items(self):
        """清空并重新渲染所有带按钮的任务项"""
        self.task_list_widget.clear()
        for task in self.task_list:
            self.create_task_item_with_btn(task.name)

    # 原有核心方法（勾选获取/运行/节点配置等，无修改）
    def get_checked_tasks(self):
        checked_tasks = []
        for row in range(self.task_list_widget.count()):
            item = self.task_list_widget.item(row)
            if item.checkState() == Qt.Checked:
                task_name = item.text()
                target_task = next(t for t in self.task_list if t.name == task_name)
                checked_tasks.append(target_task)
        return checked_tasks

    def refresh_node_list(self):
        self.node_list_widget.clear()
        selected_item = self.task_list_widget.currentItem()
        if selected_item:
            task_name = selected_item.text()
            target_task = next(t for t in self.task_list if t.name == task_name)
            self.node_title.setText(f"⚙️ 节点配置（当前任务：{task_name}）")
            for node in target_task.nodes:
                self.node_list_widget.addItem(node.name)
            self.btn_add_node.setEnabled(True)
            self.btn_edit_node.setEnabled(True)
            self.btn_del_node.setEnabled(True)
        else:
            self.node_title.setText("⚙️ 节点配置（未选中任务）")
            self.btn_add_node.setEnabled(False)
            self.btn_edit_node.setEnabled(False)
            self.btn_del_node.setEnabled(False)

    def edit_task(self):
        pass  # 被行内按钮替代，保留占位

    def del_task(self):
        pass  # 被行内按钮替代，保留占位

    def del_node(self):
        selected_task_item = self.task_list_widget.currentItem()
        selected_node_item = self.node_list_widget.currentItem()
        if not selected_task_item or not selected_node_item:
            QMessageBox.warning(self, "操作提示", "请先选中任务和要删除的节点！")
            return
        task_name = selected_task_item.text()
        node_name = selected_node_item.text()
        target_task = next(t for t in self.task_list if t.name == task_name)
        target_node = next(n for n in target_task.nodes if n.name == node_name)
        reply = QMessageBox.question(self, "确认删除", f"是否确定删除节点【{node_name}】？",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            target_task.nodes.remove(target_node)
            self.node_list_widget.takeItem(self.node_list_widget.row(selected_node_item))

# if __name__ == "__main__":
#     try:
#         atexit.register(release)
#         app = QApplication([])
#         window = UIConfigTaskNodes(1, 3)
#         window.show()
#         sys.exit(app.exec())
#     except Exception as e:
#         LOG.exception("")
#     finally:
#         # 释放资源
#         pass
