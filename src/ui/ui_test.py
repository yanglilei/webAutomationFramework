import atexit
import sys
import uuid
import time
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QHBoxLayout, QVBoxLayout,
    QListWidget, QPushButton, QMessageBox, QInputDialog, QLabel, QSizePolicy,
    QDialog, QTextEdit, QProgressBar, QDialogButtonBox, QFrame, QListWidgetItem
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QFont, QColor

from src.frame.common.common import release
from src.frame.common.qt_log_redirector import LOG


# ===================== 1. 数据模型（无修改） =====================
class Task:
    def __init__(self, task_id, name, desc="无描述"):
        self.task_id = task_id
        self.name = name
        self.desc = desc
        self.nodes = []

    def __str__(self):
        return self.name


class Node:
    def __init__(self, node_id, name, params="默认参数", task_id=None):
        self.node_id = node_id
        self.name = name
        self.params = params
        self.task_id = task_id

    def __str__(self):
        return self.name


# ===================== 2. 任务执行线程（无修改） =====================
class TaskRunThread(QThread):
    log_signal = pyqtSignal(str)
    progress_signal = pyqtSignal(int)
    finish_signal = pyqtSignal(bool)

    def __init__(self, task_list):
        super().__init__()
        self.task_list = task_list
        self.is_running = True

    def run(self):
        total_task = len(self.task_list)
        if total_task == 0:
            self.log_signal.emit("⚠️ 无勾选任务，无需执行")
            self.finish_signal.emit(True)
            return
        self.log_signal.emit(f"✅ 开始执行任务，共【{total_task}】个勾选任务")
        self.log_signal.emit("-" * 60)
        for idx, task in enumerate(self.task_list):
            if not self.is_running:
                self.log_signal.emit("🛑 检测到停止指令，任务运行中断！")
                self.finish_signal.emit(False)
                return
            current_progress = int((idx + 1) / total_task * 100)
            self.log_signal.emit(f"\n📌 正在执行任务【{task.name}】(ID: {task.task_id})")
            self.log_signal.emit(f"📋 任务描述：{task.desc}")
            self.log_signal.emit(f"⚙️ 该任务包含【{len(task.nodes)}】个节点：")
            for node in task.nodes:
                if not self.is_running: break
                self.log_signal.emit(f"  └─▶ 执行节点：{node.name} | 节点参数：{node.params}")
                time.sleep(0.5)
            self.log_signal.emit(f"✅ 任务【{task.name}】执行完成")
            self.progress_signal.emit(current_progress)
        self.log_signal.emit("-" * 60)
        self.log_signal.emit("🎉 所有勾选任务执行完毕！")
        self.progress_signal.emit(100)
        self.finish_signal.emit(True)

    def stop_task(self):
        self.is_running = False


# ===================== 3. 任务运行窗口（无修改） =====================
class TaskRunWindow(QDialog):
    def __init__(self, parent, checked_tasks):
        super().__init__(parent)
        self.checked_tasks = checked_tasks
        self.run_thread = None
        self.init_ui()
        self.init_signal()

    def init_ui(self):
        self.setWindowTitle("📊 任务运行中心 - 执行勾选任务")
        self.setFixedSize(800, 600)
        self.setFont(QFont("Microsoft YaHei", 9))
        self.setWindowModality(Qt.ApplicationModal)
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(20, 20, 20, 20)
        preview_widget = QWidget()
        preview_layout = QVBoxLayout(preview_widget)
        preview_title = QLabel("✅ 已勾选待执行任务列表")
        preview_title.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        preview_layout.addWidget(preview_title)
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(120)
        self.fill_preview_data()
        preview_layout.addWidget(self.preview_text)
        main_layout.addWidget(preview_widget)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("执行进度：%p%")
        main_layout.addWidget(self.progress_bar)
        log_widget = QWidget()
        log_layout = QVBoxLayout(log_widget)
        log_title = QLabel("📝 任务执行实时日志")
        log_title.setFont(QFont("Microsoft YaHei", 11, QFont.Bold))
        log_layout.addWidget(log_title)
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setTextColor(QColor("#333333"))
        log_layout.addWidget(self.log_text)
        main_layout.addWidget(log_widget)
        btn_layout = QHBoxLayout()
        self.btn_start = QPushButton("▶️ 开始执行任务")
        self.btn_start.setStyleSheet("background-color: #4CAF50; color: white; font-weight: bold;")
        self.btn_stop = QPushButton("🛑 停止执行")
        self.btn_stop.setStyleSheet("background-color: #F44336; color: white; font-weight: bold;")
        self.btn_stop.setEnabled(False)
        self.btn_clear_log = QPushButton("🗑️ 清空日志")
        btn_layout.addWidget(self.btn_start)
        btn_layout.addWidget(self.btn_stop)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_clear_log)
        main_layout.addLayout(btn_layout)

    def init_signal(self):
        self.btn_start.clicked.connect(self.start_run_task)
        self.btn_stop.clicked.connect(self.stop_run_task)
        self.btn_clear_log.clicked.connect(self.clear_log)

    def fill_preview_data(self):
        preview_content = ""
        for idx, task in enumerate(self.checked_tasks, 1):
            preview_content += f"{idx}. 任务名称：{task.name}\n   任务描述：{task.desc}\n   包含节点数：{len(task.nodes)} 个\n\n"
        self.preview_text.setText(preview_content if preview_content else "⚠️ 未勾选任何任务")

    def start_run_task(self):
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.progress_bar.setValue(0)
        self.log_text.append("📌 任务执行线程已启动...")
        self.run_thread = TaskRunThread(self.checked_tasks)
        self.run_thread.log_signal.connect(self.append_log)
        self.run_thread.progress_signal.connect(self.update_progress)
        self.run_thread.finish_signal.connect(self.task_finish)
        self.run_thread.start()

    def stop_run_task(self):
        if self.run_thread and self.run_thread.isRunning():
            self.run_thread.stop_task()
            self.btn_stop.setEnabled(False)
            self.log_text.append("🛑 正在执行强制停止操作...")

    def append_log(self, log_msg):
        self.log_text.append(log_msg)
        self.log_text.moveCursor(self.log_text.textCursor().End)

    def update_progress(self, value):
        self.progress_bar.setValue(value)

    def task_finish(self, is_success):
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        if not is_success: self.progress_bar.setValue(0)

    def clear_log(self):
        self.log_text.clear()
        self.log_text.append("📝 日志已清空，等待任务执行...")


# ===================== 4. 主窗口（核心改造：QListWidget添加按钮） =====================
class TaskConfigUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.task_list = []
        self.init_ui()
        self.init_signal()

    def init_ui(self):
        self.setWindowTitle("任务配置中心 - 列表带按钮版")
        self.setGeometry(100, 100, 1100, 600)
        self.setFont(QFont("Microsoft YaHei", 9))
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        # 左侧任务管理区
        task_widget = QWidget()
        task_layout = QVBoxLayout(task_widget)
        task_layout.setSpacing(15)
        task_title = QLabel("📋 任务列表（勾选+每行按钮）")
        task_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        task_layout.addWidget(task_title)

        self.task_list_widget = QListWidget()
        self.task_list_widget.setMinimumWidth(380)  # 加宽适配按钮
        task_layout.addWidget(self.task_list_widget)

        self.btn_add_task = QPushButton("➕ 新增任务")
        self.btn_run_task = QPushButton("▶️ 运行勾选任务")
        self.btn_run_task.setStyleSheet("background-color: #2196F3; color: white; font-weight: bold;")
        task_btn_layout = QVBoxLayout()
        task_btn_layout.setSpacing(8)
        task_btn_layout.addWidget(self.btn_add_task)
        task_btn_layout.addWidget(self.btn_run_task)
        task_layout.addLayout(task_btn_layout)

        # 右侧节点配置区（无修改）
        node_widget = QWidget()
        node_layout = QVBoxLayout(node_widget)
        node_layout.setSpacing(15)
        self.node_title = QLabel("⚙️ 节点配置（未选中任务）")
        self.node_title.setFont(QFont("Microsoft YaHei", 12, QFont.Bold))
        node_layout.addWidget(self.node_title)
        self.node_list_widget = QListWidget()
        node_layout.addWidget(self.node_list_widget)
        self.btn_add_node = QPushButton("➕ 新增节点")
        self.btn_edit_node = QPushButton("✏️ 编辑节点")
        self.btn_del_node = QPushButton("🗑️ 删除节点")
        self.btn_add_node.setEnabled(False)
        self.btn_edit_node.setEnabled(False)
        self.btn_del_node.setEnabled(False)
        node_btn_layout = QVBoxLayout()
        node_btn_layout.setSpacing(8)
        node_btn_layout.addWidget(self.btn_add_node)
        node_btn_layout.addWidget(self.btn_edit_node)
        node_btn_layout.addWidget(self.btn_del_node)
        node_layout.addLayout(node_btn_layout)

        main_layout.addWidget(task_widget, 4)
        main_layout.addWidget(node_widget, 6)
        self.statusBar().showMessage("就绪 - 任务列表每行自带编辑/删除按钮")

    def init_signal(self):
        self.btn_add_task.clicked.connect(self.add_task)
        self.btn_run_task.clicked.connect(self.open_run_window)
        self.btn_add_node.clicked.connect(self.add_node)
        self.btn_edit_node.clicked.connect(self.edit_node)
        self.btn_del_node.clicked.connect(self.del_node)
        self.task_list_widget.currentItemChanged.connect(self.refresh_node_list)

    # ✨ 核心改造1：封装【创建带按钮的任务项】方法（核心）
    def create_task_item_with_btn(self, task_name):
        """创建带「复选框+任务名+编辑按钮+删除按钮」的列表项"""
        # 1. 创建列表占位项（带复选框）
        item = QListWidgetItem()
        item.setText(task_name)
        item.setCheckState(Qt.Unchecked)  # 保留复选框
        item.setSizeHint(item.sizeHint())  # 适配控件高度

        # 2. 创建自定义控件容器（承载标签+按钮）
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(5, 2, 5, 2)
        layout.setSpacing(5)

        # 3. 添加任务名称标签（占满剩余空间）
        task_label = QLabel(task_name)
        task_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        task_label.setStyleSheet("font-size:9px;")
        layout.addWidget(task_label)
        layout.addStretch()  # 标签居左，按钮居右

        # 4. 添加编辑/删除按钮（核心：每行的按钮）
        btn_edit = QPushButton("✏️")
        btn_edit.setFixedSize(30, 25)
        btn_edit.setStyleSheet("background-color:#FFC107; color:white; border:none; border-radius:3px;")
        btn_del = QPushButton("🗑️")
        btn_del.setFixedSize(30, 25)
        btn_del.setStyleSheet("background-color:#F44336; color:white; border:none; border-radius:3px;")

        # 绑定按钮点击事件 → 传参当前任务名，调用原有编辑/删除方法
        btn_edit.clicked.connect(lambda: self.edit_task_by_name(task_name))
        btn_del.clicked.connect(lambda: self.del_task_by_name(task_name))

        layout.addWidget(btn_edit)
        layout.addWidget(btn_del)

        # 5. 将自定义控件挂载到列表项上（关键API）
        self.task_list_widget.addItem(item)
        self.task_list_widget.setItemWidget(item, widget)
        return item

    # ✨ 核心改造2：新增任务 → 调用带按钮的创建方法
    def add_task(self):
        task_name, ok = QInputDialog.getText(self, "新增任务", "请输入任务名称：")
        if ok and task_name.strip():
            task_desc, _ = QInputDialog.getText(self, "任务描述", "请输入任务描述（可选）：", text="无描述")
            task_id = str(uuid.uuid4())[:8]
            new_task = Task(task_id, task_name.strip(), task_desc.strip())
            self.task_list.append(new_task)
            # 调用带按钮的任务项创建方法（替代原有简单创建）
            self.create_task_item_with_btn(task_name.strip())
            self.statusBar().showMessage(f"✅ 任务创建成功：{task_name}（已添加行内按钮）")
        elif ok and not task_name.strip():
            QMessageBox.warning(self, "输入错误", "任务名称不能为空！")

    # ✨ 辅助方法：通过任务名执行编辑/删除（按钮专用）
    def edit_task_by_name(self, task_name):
        """通过任务名执行编辑（行内按钮调用）"""
        target_task = next(t for t in self.task_list if t.name == task_name)
        new_name, ok = QInputDialog.getText(self, "编辑任务", "修改任务名称：", text=target_task.name)
        if ok and new_name.strip():
            new_desc, _ = QInputDialog.getText(self, "编辑描述", "修改任务描述：", text=target_task.desc)
            target_task.name = new_name.strip()
            target_task.desc = new_desc.strip()
            # 更新列表项文本+按钮绑定
            self.refresh_all_task_items()
            self.statusBar().showMessage(f"✅ 任务编辑成功：{new_name}")

    def del_task_by_name(self, task_name):
        """通过任务名执行删除（行内按钮调用）"""
        reply = QMessageBox.question(self, "确认删除", f"是否确定删除任务【{task_name}】？\n该任务下的所有节点将一并删除！",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply == QMessageBox.Yes:
            target_task = next(t for t in self.task_list if t.name == task_name)
            self.task_list.remove(target_task)
            self.refresh_all_task_items()
            self.node_list_widget.clear()
            self.node_title.setText("⚙️ 节点配置（未选中任务）")
            self.statusBar().showMessage(f"✅ 任务已删除：{task_name}")

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

    def open_run_window(self):
        checked_tasks = self.get_checked_tasks()
        if not checked_tasks:
            QMessageBox.warning(self, "操作提示", "⚠️ 请先勾选需要运行的任务！")
            return
        self.run_window = TaskRunWindow(self, checked_tasks)
        self.run_window.show()

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

    def add_node(self):
        selected_task_item = self.task_list_widget.currentItem()
        if not selected_task_item: return
        task_name = selected_task_item.text()
        target_task = next(t for t in self.task_list if t.name == task_name)
        node_name, ok = QInputDialog.getText(self, "新增节点", "请输入节点名称：")
        if ok and node_name.strip():
            node_params, _ = QInputDialog.getText(self, "节点参数", "请输入节点配置参数：", text="默认参数")
            node_id = str(uuid.uuid4())[:8]
            new_node = Node(node_id, node_name.strip(), node_params.strip(), target_task.task_id)
            target_task.nodes.append(new_node)
            self.node_list_widget.addItem(new_node.name)
            self.statusBar().showMessage(f"✅ 节点创建成功：{node_name}")

    def edit_task(self):
        pass  # 被行内按钮替代，保留占位

    def del_task(self):
        pass  # 被行内按钮替代，保留占位

    def edit_node(self):
        selected_task_item = self.task_list_widget.currentItem()
        selected_node_item = self.node_list_widget.currentItem()
        if not selected_task_item or not selected_node_item:
            QMessageBox.warning(self, "操作提示", "请先选中任务和要编辑的节点！")
            return
        task_name = selected_task_item.text()
        node_name = selected_node_item.text()
        target_task = next(t for t in self.task_list if t.name == task_name)
        target_node = next(n for n in target_task.nodes if n.name == node_name)
        new_node_name, ok = QInputDialog.getText(self, "编辑节点", "修改节点名称：", text=target_node.name)
        if ok and new_node_name.strip():
            new_params, _ = QInputDialog.getText(self, "编辑参数", "修改节点配置参数：", text=target_node.params)
            target_node.name = new_node_name.strip()
            target_node.params = new_params.strip()
            selected_node_item.setText(new_node_name)

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



# ===================== 程序入口 =====================
if __name__ == "__main__":
    try:
        atexit.register(release)
        app = QApplication([])
        window = TaskConfigUI()
        window.show()
        sys.exit(app.exec())
    except Exception as e:
        LOG.error(exc_info=True)
    finally:
        # 释放资源
        pass