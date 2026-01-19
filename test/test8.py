import sys
import json
import os
from datetime import datetime, timedelta
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QDialog, QDialogButtonBox,
    QStatusBar, QMenuBar, QMenu, QAction, QMessageBox
)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QObject
from PyQt5.QtGui import QFont


# ---------------------- 激活管理核心类（与UI解耦） ----------------------
class ActivationManager(QObject):
    """激活状态管理类，负责激活验证、状态存储、有效期计算"""
    # 定义信号，用于通知UI更新激活状态
    activation_status_changed = pyqtSignal(bool, str)  # (是否激活, 剩余时间文本)

    def __init__(self, config_path="activation_config.json"):
        super().__init__()
        self.config_path = config_path
        self.is_activated = False  # 当前激活状态
        self.expire_time = None  # 过期时间（datetime对象）
        self.load_activation_config()  # 加载本地配置
        # 定时器：每秒更新剩余时间（模拟实时刷新）
        self.timer = QTimer()
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self.update_remaining_time)
        self.timer.start()

    def load_activation_config(self):
        """加载本地激活配置文件"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    self.is_activated = config.get("is_activated", False)
                    expire_str = config.get("expire_time", "")
                    if expire_str and self.is_activated:
                        self.expire_time = datetime.fromisoformat(expire_str)
        except Exception as e:
            print(f"加载激活配置失败: {e}")
            self.is_activated = False
            self.expire_time = None
        # 首次加载后通知UI更新状态
        self.update_remaining_time()

    def save_activation_config(self):
        """保存激活配置到本地文件"""
        config = {
            "is_activated": self.is_activated,
            "expire_time": self.expire_time.isoformat() if self.expire_time else ""
        }
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"保存激活配置失败: {e}")

    def verify_activation_code(self, code):
        """
        验证激活码（实际项目中替换为真实验证逻辑，如对接服务器）
        这里模拟验证：激活码以"VALID_"开头则验证通过，有效期30天
        """
        if code.startswith("VALID_"):
            self.is_activated = True
            self.expire_time = datetime.now() + timedelta(days=30)
            self.save_activation_config()
            self.update_remaining_time()
            return True, "激活成功！"
        else:
            return False, "激活码无效，请检查后重试。"

    def update_remaining_time(self):
        """计算剩余时间，并发送状态更新信号"""
        if not self.is_activated:
            self.activation_status_changed.emit(False, "未激活")
            return

        now = datetime.now()
        if now >= self.expire_time:
            # 激活过期
            self.is_activated = False
            self.expire_time = None
            self.save_activation_config()
            self.activation_status_changed.emit(False, "激活已过期")
        else:
            # 计算剩余时间
            remaining = self.expire_time - now
            days = remaining.days
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            remaining_text = f"剩余: {days}天{hours}时{minutes}分{seconds}秒"
            self.activation_status_changed.emit(True, remaining_text)

    def deactivate(self):
        """取消激活（测试用）"""
        self.is_activated = False
        self.expire_time = None
        self.save_activation_config()
        self.update_remaining_time()


# ---------------------- 激活对话框 ----------------------
class ActivationDialog(QDialog):
    def __init__(self, activation_manager, parent=None):
        super().__init__(parent)
        self.activation_manager = activation_manager
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("软件激活")
        self.setFixedSize(400, 150)
        self.setModal(True)  # 模态对话框，阻塞主窗口操作

        layout = QVBoxLayout()

        # 激活码输入框
        input_layout = QHBoxLayout()
        input_layout.addWidget(QLabel("激活码："))
        self.code_edit = QLineEdit()
        self.code_edit.setPlaceholderText("请输入激活码")
        input_layout.addWidget(self.code_edit)
        layout.addLayout(input_layout)

        # 按钮区
        btn_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal, self
        )
        btn_box.accepted.connect(self.on_activate)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

        self.setLayout(layout)

    def on_activate(self):
        """点击激活按钮的处理逻辑"""
        code = self.code_edit.text().strip()
        if not code:
            QMessageBox.warning(self, "提示", "请输入激活码！")
            return

        success, msg = self.activation_manager.verify_activation_code(code)
        if success:
            QMessageBox.information(self, "成功", msg)
            self.accept()
        else:
            QMessageBox.critical(self, "失败", msg)


# ---------------------- 主窗口 ----------------------
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PyQt5 激活功能演示")
        self.setMinimumSize(800, 500)

        # 初始化激活管理器
        self.activation_manager = ActivationManager()
        # 绑定激活状态变化信号
        self.activation_manager.activation_status_changed.connect(self.on_activation_status_changed)

        # 初始化UI
        self.init_menu()
        self.init_status_bar()
        self.init_main_ui()

    def init_menu(self):
        """初始化菜单栏（添加激活入口）"""
        menubar = self.menuBar()
        help_menu = menubar.addMenu("帮助")

        # 激活菜单项
        activate_action = QAction("软件激活", self)
        activate_action.triggered.connect(self.open_activation_dialog)
        help_menu.addAction(activate_action)

        # 测试用：取消激活
        deactivate_action = QAction("取消激活（测试）", self)
        deactivate_action.triggered.connect(self.activation_manager.deactivate)
        help_menu.addAction(deactivate_action)

    def init_status_bar(self):
        """初始化状态栏（显示激活状态和剩余时间）"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        # 状态栏样式优化
        self.status_bar.setStyleSheet("QStatusBar { background-color: #f0f0f0; font-size: 12px; }")
        # 初始显示
        self.status_bar.showMessage("激活状态：未激活", 0)  # 0表示永久显示

    def init_main_ui(self):
        """初始化主界面（包含受限按钮和普通按钮）"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 标题
        title_label = QLabel("软件功能演示")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 功能按钮区
        btn_layout = QHBoxLayout()

        # 普通按钮（无需激活）
        normal_btn = QPushButton("普通功能（无需激活）")
        normal_btn.clicked.connect(lambda: QMessageBox.information(self, "提示", "普通功能执行成功！"))
        btn_layout.addWidget(normal_btn)

        # 受限按钮1（需激活）
        self.restricted_btn1 = QPushButton("高级功能1（需激活）")
        self.restricted_btn1.setToolTip("激活软件后即可使用此功能")
        self.restricted_btn1.setEnabled(False)  # 初始禁用
        self.restricted_btn1.clicked.connect(lambda: QMessageBox.information(self, "提示", "高级功能1执行成功！"))
        btn_layout.addWidget(self.restricted_btn1)

        # 受限按钮2（需激活）
        self.restricted_btn2 = QPushButton("高级功能2（需激活）")
        self.restricted_btn2.setToolTip("激活软件后即可使用此功能")
        self.restricted_btn2.setEnabled(False)  # 初始禁用
        self.restricted_btn2.clicked.connect(lambda: QMessageBox.information(self, "提示", "高级功能2执行成功！"))
        btn_layout.addWidget(self.restricted_btn2)

        layout.addLayout(btn_layout)

    def open_activation_dialog(self):
        """打开激活对话框"""
        dialog = ActivationDialog(self.activation_manager, self)
        dialog.exec_()

    def on_activation_status_changed(self, is_activated, remaining_text):
        """激活状态变化时更新UI"""
        # 更新状态栏
        status_text = f"激活状态：{'已激活' if is_activated else '未激活'} | {remaining_text}"
        self.status_bar.showMessage(status_text, 0)

        # 更新受限按钮状态
        self.restricted_btn1.setEnabled(is_activated)
        self.restricted_btn2.setEnabled(is_activated)


# ---------------------- 程序入口 ----------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 全局样式优化（可选）
    app.setStyle("Fusion")
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())