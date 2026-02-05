import atexit
import os
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from src.utils.process_utils import ProcessUtils

sys.coinit_flags = 2
from PyQt5.QtCore import Qt, pyqtSignal, QSharedMemory, QSystemSemaphore, QTimer, QThread, qInstallMessageHandler
from PyQt5.QtGui import QFont, QIcon
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QListWidget, QStackedWidget,
    QVBoxLayout, QHBoxLayout, QLabel, QListWidgetItem, QStyleFactory, QPushButton, QTextEdit, QMessageBox, QStatusBar
)

from src.frame.common import constants
from src.frame.common.activate_manager import ActivationManager
from src.frame.common.common import release
from src.frame.common.qt_log_redirector import LOG
from src.ui.config_center.ui_config_center import ConfigCenterWidget
from src.ui.running_center.ui_running_center import RunningCenterWidget
from src.utils.sys_path_utils import SysPathUtils


# ======================== 页面基类（可选，用于统一页面规范） ========================
class BasePage(QWidget):
    """所有业务页面的基类，定义统一接口，提升扩展性"""
    # 定义通用信号（如页面需要向主窗口发送消息）
    message_signal = pyqtSignal(str, str)  # (消息类型, 消息内容)：info/warning/error

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        """每个页面需实现自己的UI初始化"""
        raise NotImplementedError("子类必须实现init_ui方法")

    def refresh_data(self):
        """可选：页面数据刷新接口（统一刷新逻辑）"""
        pass


# ======================== 具体业务页面实现 ========================
class ConfigCenterPage(BasePage):
    """1. 模板选择页面"""

    def init_ui(self):
        ly_main = QVBoxLayout()
        ly_main.addWidget(ConfigCenterWidget())
        self.setLayout(ly_main)


@dataclass(init=False)
class RunningCenterPage(BasePage):
    """2. 运行中心页面"""
    running_center_widget: Optional[RunningCenterWidget] = None
    timer: Optional[QTimer] = None
    # 运行状态刷新信号
    running_status_refresh_signal = pyqtSignal(bool)

    def init_ui(self):
        ly_main = QVBoxLayout()
        self.running_center_widget = RunningCenterWidget()
        ly_main.addWidget(self.running_center_widget)
        self.setLayout(ly_main)

        self.timer = QTimer()
        self.timer.timeout.connect(self.refresh_running_status)
        self.timer.start(1000)

    def refresh_running_status(self):
        self.running_status_refresh_signal.emit(self.has_running_task())

    def has_running_task(self):
        return self.running_center_widget.has_running_task()


class ActivationPage(BasePage):
    """3. 激活页面"""
    # 激活状态改变信号，可监听该信号用于更新激活的状态和时间
    activation_status_changed = pyqtSignal(bool, str)

    def __init__(self, parent=None):
        self.btn_revoke = None
        self.btn_renewal = None
        self.btn_active = None
        self.te_key = None
        self.btn_copy = None
        self.lb_mac: Optional[QLabel] = None
        self.ly_mac_btns = None
        self.ly_activate = None
        super().__init__(parent)
        self.activation_manager = ActivationManager()
        self.activation_manager.startup_verify_signal.connect(self.handle_startup_verify)
        self.activation_manager.mac_get_success_signal.connect(self.handle_mac_get_success)
        self.activation_manager.manual_activate_signal.connect(self.handle_manual_activate)
        self.activation_manager.revoke_signal.connect(self.handle_revoke)
        self.activation_manager.renew_signal.connect(self.handle_renew)
        self.activation_manager.activation_status_changed.connect(self.activation_status_changed)

    def init_ui(self):
        #### mac ui ####
        self.ly_activate = QVBoxLayout()
        self.ly_mac_btns = QHBoxLayout()
        self.ly_mac_btns.setAlignment(Qt.AlignLeft)
        self.ly_mac_btns.addWidget(QLabel("识 别 码："))

        self.lb_mac = QLabel("获取中...")
        self.btn_copy = QPushButton("复制")
        self.btn_copy.clicked.connect(self.copy_text)
        self.btn_active = QPushButton("激活")
        self.btn_active.setEnabled(False)
        self.btn_renewal = QPushButton("续期")
        self.btn_renewal.setEnabled(False)
        self.btn_revoke = QPushButton("吊销")
        self.btn_revoke.setEnabled(False)
        self.ly_mac_btns.addWidget(self.lb_mac)
        self.ly_mac_btns.addWidget(self.btn_copy)
        self.ly_mac_btns.addWidget(self.btn_active)
        self.ly_mac_btns.addWidget(self.btn_renewal)
        self.ly_mac_btns.addWidget(self.btn_revoke)

        # 秘钥输入框
        self.te_key = QTextEdit()
        self.te_key.setLineWrapMode(QTextEdit.WidgetWidth)
        self.te_key.setPlaceholderText("请输入激活码...")
        # self.te_key.textChanged.connect(self.on_te_key_changed)
        if not self.te_key.toPlainText().strip():
            self.btn_active.setEnabled(False)

        # 激活信号
        self.btn_active.clicked.connect(lambda: self.activate(self.te_key.toPlainText().strip()))
        # 续期信号
        self.btn_renewal.clicked.connect(lambda: self.renewal(self.te_key.toPlainText().strip()))
        # 注销信号
        self.btn_revoke.clicked.connect(self.revoke)

        # 添加控件
        self.ly_activate.addLayout(self.ly_mac_btns)
        self.ly_activate.addWidget(self.te_key)
        # 激活页面
        self.setLayout(self.ly_activate)

    def activate(self, activation_key):
        if not activation_key:
            QMessageBox.warning(self, "提示", "请输入激活码！")
            return

        self.activation_manager.activate(activation_key)

    def renewal(self, activation_key):
        if not activation_key:
            QMessageBox.warning(self, "提示", "请输入激活码！")
            return

        self.activation_manager.renewal(activation_key)

    def revoke(self):
        # 再次确认是否确定吊销
        if QMessageBox.warning(self, "提示", "确定要吊销吗？", QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
            return
        self.activation_manager.revoke()

    def handle_mac_get_success(self, mac: str):
        """处理获取mac成功"""
        self.lb_mac.setText(mac)
        self.btn_active.setEnabled(True)

    def handle_startup_verify(self, status: bool, msg: str):
        # 验证结果
        if status:
            # 更新按钮状态
            self.btn_active.setEnabled(False)
            self.btn_renewal.setEnabled(True)
            self.btn_revoke.setEnabled(True)
        else:
            # 更新按钮状态
            self.btn_active.setEnabled(True)
            self.btn_renewal.setEnabled(False)
            self.btn_revoke.setEnabled(False)

    def handle_manual_activate(self, status: bool, msg: str):
        """处理手动激活成功"""
        if status:  # 激活成功
            # 更新按钮状态
            self.btn_active.setEnabled(False)
            self.btn_renewal.setEnabled(True)
            self.btn_revoke.setEnabled(True)
            # 提示激活成功
            QMessageBox.information(self, "操作结果", "激活成功")
        else:  # 激活失败
            # 更新按钮状态
            self.btn_active.setEnabled(True)
            self.btn_renewal.setEnabled(False)
            self.btn_revoke.setEnabled(False)
            # 提示激活失败
            QMessageBox.warning(self, "操作结果", f"{msg}")

    def handle_revoke(self, status: bool, msg: str):
        if status:  # 吊销成功
            # 更新按钮状态
            self.btn_active.setEnabled(True)
            self.btn_renewal.setEnabled(False)
            self.btn_revoke.setEnabled(False)
            # 提示吊销成功
            QMessageBox.information(self, "操作结果", "吊销成功！")
        else:  # 吊销失败
            # 提示吊销失败
            QMessageBox.information(self, "操作结果", "吊销失败！")

    def handle_renew(self, status: bool, msg: str):
        if status:  # 激活成功
            # 更新按钮状态
            self.btn_active.setEnabled(False)
            self.btn_renewal.setEnabled(True)
            self.btn_revoke.setEnabled(True)
            # 提示续期成功
            QMessageBox.information(self, "操作结果", "续期成功！")
        else:  # 激活失败
            # 提示续期失败
            QMessageBox.information(self, "操作结果", f"续期失败：{msg}")

    def copy_text(self):
        # 获取剪贴板
        clipboard = QApplication.clipboard()
        # 设置剪贴板文本内容
        clipboard.setText(self.lb_mac.text())
        # 弹出消息框提示复制成功
        QMessageBox.information(self, '信息', '文本已复制到剪贴板', QMessageBox.Ok)


# 创建一个资源监控线程
# class ResourceMonitor(QThread):
#     """资源监控线程"""
#     signal = pyqtSignal(bool)
#
#     def __init__(self, logger, ui_running_center: 'RunningCenterPage'):
#         super().__init__()
#         self.logger = logger
#         self.ui_running_center = ui_running_center
#
#     def run(self):
#         while True:
#             self.free_resource(self.ui_running_center.has_running_task())
#             time.sleep(5)
#
#     def free_resource(self, status: bool):
#         if not status:
#             self.logger.debug("开始清理浏览器资源")
#             ProcessUtils.kill_residual_chrome(os.getpid())
#             # chrome_process_manager.clean_all_batch_processes()
#             self.logger.debug("已释放浏览器资源")


# ======================== 主窗口（核心布局） ========================
class MainWindow(QMainWindow):
    def __init__(self, is_need_activate: bool = True):
        super().__init__()
        # 是否正在运行，辅助限制不能多开！
        self.is_running = False
        # 运行限制
        self.running_limit()
        # 激活管理器
        self.activation_manager = ActivationManager(self, constants.APP_NAME, constants.IS_NEED_ACTIVATION)
        self.status_bar = None  # 状态栏
        self.is_need_activate = is_need_activate  # 是否需要激活
        self.app_name = constants.APP_NAME  # 应用名称
        self.version = constants.VERSION
        self.activation_page = None  # 激活页面
        self.config_center_page = None  # 配置配置页面
        self.running_center_page: Optional[RunningCenterPage] = None  # 运行中心页面
        self.nav_widget = None  # 右侧堆叠窗口
        self.stacked_widget = None  # 左侧导航栏
        self.setWindowTitle(f"{self.app_name}V{self.version}")
        self.setGeometry(100, 100, 1000, 700)  # 初始窗口大小
        self.setMinimumSize(1200, 680)  # 最小窗口尺寸，避免缩放过小
        self.init_ui()  # 初始化UI
        # self.resource_monitor = ResourceMonitor(LOG, self.running_center_page)
        # self.resource_monitor.start()

    def init_ui(self):
        # 1. 创建中心部件和主布局（水平布局：左导航 + 右内容）
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(0)  # 取消布局间距
        main_layout.setContentsMargins(0, 0, 0, 0)  # 取消内边距
        self.setCentralWidget(central_widget)
        # 2. 创建状态栏
        self.init_status_bar()
        # 3. 右侧堆叠窗口（用于切换页面）
        self.stacked_widget = self.create_stacked_widget()
        # 4. 左侧导航栏
        self.nav_widget = self.create_nav_widget()
        # 5. 添加到主布局（导航栏宽度固定，内容区自适应）
        main_layout.addWidget(self.nav_widget)
        main_layout.addWidget(self.stacked_widget, stretch=1)
        # 5. 美化样式（可选，提升体验）
        self.set_style()
        self.setWindowIcon(QIcon(str(Path(SysPathUtils.get_icon_file_dir(), "xgs.ico"))))

    def running_limit(self, key="com.ptzhs.xgs2026"):
        shared_memory = QSharedMemory(self)
        shared_memory.setKey(key)
        self.is_running = self._is_program_running(shared_memory)

        if not self.is_running:
            shared_memory.attach()
            shared_memory.create(1)
            semaphore = QSystemSemaphore(shared_memory.key() + '-semaphore', 1)
            semaphore.acquire()
        else:
            QMessageBox.warning(None, '警告', '程序正在运行！')
            sys.exit(1)

    def _is_program_running(self, shared_memory):
        shared_memory.attach()
        return shared_memory.size() != 0

    # def init_status_bar(self):
    #     """初始化状态栏（显示激活状态和剩余时间）"""
    #     self.status_bar = QStatusBar()
    #     self.setStatusBar(self.status_bar)
    #     # 状态栏样式优化
    #     # self.status_bar.setStyleSheet("QStatusBar { background-color: #f0f0f0; font-size: 12px; }")
    #     # 初始显示
    #     if not self.is_need_activate:
    #         self.status_bar.showMessage("激活状态：永久激活版", 0)
    #     else:
    #         self.status_bar.showMessage("激活状态：未激活", 0)  # 0表示永久显示

    def init_status_bar_bak(self):
        """初始化状态栏：实现左右对齐+图层效果"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 1. 状态栏基础样式
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #f0f0f0;
                font-size: 12px;
                border-top: 1px solid #cccccc;
            }
            QStatusBar QLabel {
                padding: 0 5px;  /* 文字左右间距 */
            }
        """)

        # 2. 左侧标签：激活状态（左对齐）
        self.left_label = QLabel("激活状态：未激活")
        self.left_label.setAlignment(Qt.AlignLeft)
        # 设置文字颜色：未激活红色，激活绿色
        self.left_label.setStyleSheet("color: #FF4444; font-weight: bold;")
        self.status_bar.addWidget(self.left_label)  # 添加到左侧

        # 3. 右侧标签：剩余时间（右对齐）
        self.right_label = QLabel("剩余时间：--")
        self.right_label.setAlignment(Qt.AlignRight)
        self.right_label.setStyleSheet("color: #333333;")
        # addPermanentWidget：永久固定在右侧，不受窗口缩放影响
        self.status_bar.addPermanentWidget(self.right_label)

        # 4. 图层演示：添加一个悬浮提示标签（层级更高）
        self.layer_label = QLabel(" ✨ 高级版功能已解锁 ")
        self.layer_label.setStyleSheet("""
            background-color: #4CAF50;
            color: white;
            border-radius: 8px;
            padding: 2px 8px;
        """)
        self.layer_label.setAlignment(Qt.AlignCenter)
        # 添加到状态栏，默认层级较低
        self.status_bar.addWidget(self.layer_label)
        # 提升层级：让这个标签显示在最上方（覆盖其他控件）
        self.layer_label.raise_()
        # 初始隐藏，激活后显示
        self.layer_label.setVisible(False)

    def init_status_bar(self):
        """初始化状态栏：实现左右对齐+图层效果+运行状态指示灯"""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)

        # 1. 状态栏基础样式
        self.status_bar.setStyleSheet("""
            QStatusBar {
                background-color: #f0f0f0;
                font-size: 12px;
                border-top: 1px solid #cccccc;
            }
            QStatusBar QLabel {
                padding: 0 5px;  /* 文字左右间距 */
            }
        """)

        # 2. 左侧容器：激活状态 + 运行指示灯
        left_container = QWidget()
        left_layout = QHBoxLayout(left_container)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(8)

        # 2.1 激活状态标签
        self.left_label = QLabel("激活状态：未激活")
        self.left_label.setAlignment(Qt.AlignLeft)
        self.left_label.setStyleSheet("color: #FF4444; font-weight: bold;")

        # 2.2 运行状态指示灯（圆形）
        self.running_indicator = QLabel()
        self.running_indicator.setFixedSize(12, 12)  # 指示灯大小
        self.running_indicator.setStyleSheet("""
            QLabel {
                background-color: #FF7F27;  /* 初始红色：停止状态 */
                border-radius: 6px;         /* 圆形：宽度/高度的一半 */
            }
        """)

        # 2.3 运行状态文字说明
        self.running_label = QLabel("状态：待机")
        self.running_label.setStyleSheet("color: #FF7F27; font-weight: bold;")

        # 添加到左侧容器
        left_layout.addWidget(self.left_label)
        left_layout.addWidget(self.running_indicator)
        left_layout.addWidget(self.running_label)
        self.status_bar.addWidget(left_container)

        # 3. 右侧标签：剩余时间（右对齐）
        self.right_label = QLabel("剩余时间：--")
        self.right_label.setAlignment(Qt.AlignRight)
        self.right_label.setStyleSheet("color: #333333;")
        self.status_bar.addPermanentWidget(self.right_label)

        # 4. 图层演示：添加一个悬浮提示标签（层级更高）
        self.layer_label = QLabel(" ✨ 高级版功能已解锁 ")
        self.layer_label.setStyleSheet("""
            background-color: #4CAF50;
            color: white;
            border-radius: 8px;
            padding: 2px 8px;
        """)
        self.layer_label.setAlignment(Qt.AlignCenter)
        self.status_bar.addWidget(self.layer_label)
        self.layer_label.raise_()
        self.layer_label.setVisible(False)

    # @pyqtSlot(bool)
    def update_running_indicator(self, is_running: bool):
        """
        更新运行状态指示灯
        :param is_running: True-运行中（绿色），False-停止（红色）
        """
        if is_running:
            # 运行中：绿色指示灯 + 绿色文字
            self.running_indicator.setStyleSheet("""
                   QLabel {
                       background-color: #4CAF50;
                       border-radius: 6px;
                   }
               """)
            self.running_label.setText("状态：运行中")
            self.running_label.setStyleSheet("color: #4CAF50; font-weight: bold;")
        else:
            # 停止：红色指示灯 + 红色文字
            self.running_indicator.setStyleSheet("""
                   QLabel {
                       background-color: #FF7F27;
                       border-radius: 6px;
                   }
               """)
            self.running_label.setText("状态：待机")
            self.running_label.setStyleSheet("color: #FF7F27; font-weight: bold;")

    def on_activation_status_changed(self, is_activated, remaining_text):
        """激活状态变化时更新UI"""
        # 更新状态栏
        # suffix = "请联系管理员VX：glowing3925"
        # status_text = f"激活状态：{'已激活' if is_activated else '未激活'} | {remaining_text}"
        # self.status_bar.showMessage(status_text, 0)

        # 1. 更新左侧激活状态标签
        if is_activated:
            self.left_label.setText("激活状态：已激活")
            self.left_label.setStyleSheet("color: #2E8B57; font-weight: bold;")
            self.layer_label.setVisible(True)  # 显示图层提示标签
        else:
            self.left_label.setText(f"激活状态：未激活")
            self.left_label.setStyleSheet("color: #FF4444; font-weight: bold;")
            self.layer_label.setVisible(False)  # 隐藏图层提示标签

        # 2. 更新右侧剩余时间标签
        if is_activated:
            self.right_label.setText(f"剩余时间：{remaining_text}" if self.is_need_activate else "")
        else:
            self.right_label.setText("剩余时间：--")

    def create_nav_widget(self):
        """创建左侧导航栏"""
        nav_widget = QWidget()
        nav_widget.setFixedWidth(130)  # 固定导航栏宽度
        nav_layout = QVBoxLayout(nav_widget)
        nav_layout.setContentsMargins(0, 0, 0, 0)

        # 导航列表
        self.nav_list = QListWidget()
        self.nav_list.setStyleSheet("QListWidget::item { height: 60px; font-size: 14px;}")
        self.nav_list.setSelectionMode(QListWidget.SingleSelection)

        # 导航项（与页面一一对应）
        nav_items = [
            "🔆配置中心",
            "️🔥运行中心",
        ]
        if self.is_need_activate:
            nav_items.append("🔑激  活")
        for item_text in nav_items:
            item = QListWidgetItem(item_text)
            item.setTextAlignment(Qt.AlignCenter)  # 文字居中
            self.nav_list.addItem(item)

        # 绑定导航点击事件（切换页面）
        self.nav_list.currentRowChanged.connect(self.switch_page)
        self.nav_list.setCurrentRow(0)  # 默认选中第一个页面

        # 添加到导航布局
        nav_layout.addWidget(self.nav_list)
        return nav_widget

    def create_stacked_widget(self):
        """创建右侧堆叠窗口（存放所有业务页面）"""
        stacked_widget = QStackedWidget()
        # 注册页面（低耦合核心：新增页面只需在这里添加）
        self.config_center_page = ConfigCenterPage()
        self.running_center_page = RunningCenterPage()
        self.running_center_page.running_status_refresh_signal.connect(self.update_running_indicator)
        # self.running_center_page.running_status_refresh_signal.connect(self.resource_monitor.free_resource)

        self.activation_page = ActivationPage()
        self.activation_page.activation_status_changed.connect(self.on_activation_status_changed)

        # 添加到堆叠窗口
        stacked_widget.addWidget(self.config_center_page)
        stacked_widget.addWidget(self.running_center_page)
        stacked_widget.addWidget(self.activation_page)

        # 绑定页面消息信号（示例：页面向主窗口发送消息）
        self.config_center_page.message_signal.connect(self.show_message)
        self.running_center_page.message_signal.connect(self.show_message)
        self.activation_page.message_signal.connect(self.show_message)

        return stacked_widget

    def switch_page(self, index):
        """切换堆叠窗口的页面"""
        self.stacked_widget.setCurrentIndex(index)

    def show_message(self, msg_type, msg_content):
        """统一处理页面发送的消息（示例：后续可扩展为弹窗/日志栏）"""
        print(f"[{msg_type.upper()}] {msg_content}")

    def set_global_font_advanced(self):
        """按平台动态设置字体"""
        font_config = {
            "win32": {  # Windows
                "family": "Microsoft YaHei, 微软雅黑, Segoe UI, sans-serif",
                "size": 12
            },
            "darwin": {  # Mac
                "family": "PingFang SC, Hiragino Sans GB, 微软雅黑, sans-serif",
                "size": 13
            },
            "linux": {  # Linux
                "family": "Source Han Sans SC, Roboto, Arial, sans-serif",
                "size": 11
            }
        }
        # 获取当前平台配置
        platform = sys.platform
        config = font_config.get(platform, font_config["win32"])  # 兜底Windows配置

        # 设置全局字体
        global_font = QFont(config["family"], config["size"])
        QApplication.setFont(global_font)

    def set_style(self):
        """设置全局样式（美化UI）"""
        # 设置全局字体
        # font = QFont("微软雅黑", 10)
        # font = QFont("PingFang SC", 11)
        # QApplication.setFont(font)
        self.set_global_font_advanced()
        style_one = """
            QListWidget {
                background-color: #f8f9fa;  /* 浅灰色底色 */
                color: #212529;             /* 深灰色文字 */
                border: 1px solid #dee2e6;
            }
            QListWidget::item {  /* 列表项基础样式 */
                height: 60px;     /* 列表项高度 */
                font-size: 14px;  /* 字体大小（修改此处会生效） */
                text-align: center; /* 文字居中（补充优化） */
            }
            QListWidget::item:selected {
                background-color: #0d6efd;  /* 蓝色选中项 */
                color: white;
            }
            QMenu::item:selected {
                background-color: #198754;  /* 选中背景色 */
                color: white;
            }
            QListWidget::item:hover {
                background-color: #e9ecef;  /* 悬浮浅灰 */
            }
        """

        style_two = """
            QListWidget {
                background-color: #fff8f0;  /* 浅橙底色 */
                color: #e67700;             /* 橙文字 */
                border: 1px solid #dee2e6;
            }
            QListWidget::item {  /* 列表项基础样式 */
                height: 60px;     /* 列表项高度 */
                font-size: 14px;  /* 字体大小（修改此处会生效） */
                text-align: center; /* 文字居中（补充优化） */
            }
            QListWidget::item:selected {
                background-color: #e67700;  /* 橙色选中项 */
                color: white;
            }
            QMenu::item:selected {
                background-color: #198754;  /* 选中背景色 */
                color: white;
            }
            QListWidget::item:hover {
                background-color: #fff3e0;
            }
        """

        style_three = """
            QListWidget {
                background-color: #e9ecef;  /* 中性浅灰 */
                color: #212529;
                border: none;
            }
            QListWidget::item {  /* 列表项基础样式 */
                height: 60px;     /* 列表项高度 */
                font-size: 14px;  /* 字体大小（修改此处会生效） */
                text-align: center; /* 文字居中（补充优化） */
            }
            QListWidget::item:selected {
                background-color: #198754;  /* 绿色选中项 */
                color: white;
            }
        """

        style_four = """
            QListWidget {
                background-color: #2c3e50;
                color: white;
                border: none;
            }
            QListWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
            QListWidget::item:hover {
                background-color: #34495e;
            }
        """
        # QListWidget::item:hover {
        #     background-color: #dee2e6;
        # }
        # 导航栏样式
        self.nav_list.setStyleSheet(style_three)

        # 主窗口背景
        self.centralWidget().setStyleSheet("background-color: #FAFAFA")

        self.setStyleSheet(self.set_comboBox_style())

    def set_comboBox_style(self):
        """
        设置下拉列表样式

        QComboBox {
            background-color: #fff;
            color: #333;
            font-size: 13px;
            height: 35px;
            padding: 0 10px;
            border: 1px solid #ccc;
            border-radius: 4px;
        }
        QComboBox::drop-down {
            width: 30px;
        }
        QComboBox::down-arrow {
            color: #666;
            width: 8px;
            height: 8px;
        }
        QComboBox QAbstractItemView {
            background-color: white;
            border: 1px solid #ccc;
            outline: none;
        }
        QComboBox QAbstractItemView::item {
            height: 30px;
            padding: 0 10px;
        }
        QComboBox QAbstractItemView::item:selected {
            background-color: #ccc;
            color: #333;
        }

        """

        return """
        /* 全局QComboBox样式 */
        QComboBox {
            background-color: #fff;
            color: #333;            
        }
        
        """

# 自定义Qt日志处理器，输出所有Qt警告/错误
def qt_message_handler(msg_type, context, msg):
    LOG.info(f"Qt日志[{msg_type}]: {msg} (文件:{context.file}, 行:{context.line})")

# ======================== 程序入口 ========================
if __name__ == "__main__":
    try:
        atexit.register(release)
        # 高分屏+抗锯齿
        # QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
        # QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)
        qInstallMessageHandler(qt_message_handler)  # 安装日志处理器
        app = QApplication([])
        app.setStyle(QStyleFactory.create("Fusion"))  # 统一跨平台样式
        win = MainWindow(constants.IS_NEED_ACTIVATION)
        win.show()
        sys.exit(app.exec_())
    except Exception as e:
        LOG.exception("应用异常退出：")
    finally:
        # 释放资源
        pass
