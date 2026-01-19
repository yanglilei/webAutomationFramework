import dataclasses
import os.path
import re
from abc import abstractmethod
from datetime import datetime
from typing import List, Union

from PyQt5.QtCore import QTimer, Qt
from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIcon, QFont
from PyQt5.QtWidgets import QGroupBox, QTextBrowser, QFileDialog
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLineEdit, QGridLayout
from PyQt5.QtWidgets import QWidget, QMessageBox, QPushButton, QLabel, \
    QTextEdit, QTabWidget, QApplication, QLayout

from src.frame.common.constants import Constants, ActivateStatus
from src.frame.common.exceptions import ParamError
from src.frame.common.qt_log_redirector import qt_logger
from src.frame.common.sys_config import SysConfig
from src.frame.common.threads.activate import ActivateThread
from src.frame.common.user_manager import UserInfoLocation
from src.frame.dao.db_manager import db
from src.frame.task_manager import TaskManager
from src.utils.crypto_utils import Md5Utils, MACUtils
from src.utils.sys_path_utils import SysPathUtils


@dataclasses.dataclass
class TabWidgetInfo:
    tab_name: str
    widget: QWidget


class BaseUI(QWidget):
    def __init__(self, need_activate=True):
        super().__init__()
        # 定时器
        self.timer = None
        # 软件的激活状态
        self.activate_status = None
        # 过期时间，时间戳，单位秒
        self.expired_time = 0
        # 设置icon
        self.setWindowIcon(QIcon(self.get_icon()))
        # 标签控件
        self.tab_widget = self.init_tab_widget()
        # 是否需要激活标志。True-激活；False-不需要激活
        self.need_activate = need_activate
        # 激活UI
        if self.need_activate:
            # 设置初始标题
            self.setWindowTitle(f"{self.get_app_name()}{self.get_version()}        激活中请等待......")
            # 初始化激活页面
            self._init_activate_ui()
            # 初始化软件状态
            self.init_app_status()
        else:
            # 设置初始标题
            self.setWindowTitle(f"{self.get_app_name()}{self.get_version()}")
        # 添加标签页
        self._add_tab_widgets()
        # 主页面
        # self.central_widget = QWidget()
        # self.ly_main = QVBoxLayout(self.central_widget)
        self.ly_main = QVBoxLayout()
        self.ly_main.addWidget(self.tab_widget)
        # 在主页面添加控件
        self._add_to_main_layout()
        # self.setCentralWidget(self.central_widget)
        self.setLayout(self.ly_main)

    def _add_tab_widgets(self):
        widgets = self.add_tab_widgets()
        if widgets:
            for widget in widgets:
                self.tab_widget.addTab(widget.widget, widget.tab_name)
        # 设置默认标签页，第一个标签页为激活页面，若是没有显示激活页面，则设置第一个标签页为当前标签页，否则设置第二个标签页为当前标签页
        self.tab_widget.setCurrentIndex(1 if self.tab_widget.count() > 1 and self.need_activate else 0)

    def _add_to_main_layout(self):
        objs = self.add_to_main_layout()
        if objs:
            for obj in objs:
                if isinstance(obj, QLayout):
                    self.ly_main.addLayout(obj)
                elif isinstance(obj, QWidget):
                    self.ly_main.addWidget(obj)

    @abstractmethod
    def add_tab_widgets(self) -> List[TabWidgetInfo]:
        """
        添加标签页面
        :return: List[QWidget]
        """
        raise NotImplementedError()

    def add_to_main_layout(self) -> List[Union[QWidget, QLayout]]:
        """
        添加控件到主页面
        :return:
        """
        return []

    def init_tab_widget(self):
        tab_widget = QTabWidget()
        # 设置样式表来改变活动标签页的底色
        style_sheet = """
            QTabBar::tab {
                padding: 5px;
            }
            QTabBar::tab:selected {
                background-color: #007BFF; /* 设置活动标签页的背景颜色为金色 */
                color: white; /* 设置活动标签页的文字颜色为白色 */
            }
        """
        tab_widget.setStyleSheet(style_sheet)
        return tab_widget

    def _init_activate_ui(self):
        #### mac ui ####
        self.ly_activate = QVBoxLayout()
        self.ly_mac_btns = QHBoxLayout()
        self.ly_mac_btns.setAlignment(Qt.AlignLeft)
        self.ly_mac_btns.addWidget(QLabel("识 别 码："))

        # mac地址
        self.lb_mac = QLabel(
            Md5Utils.encrypt(MACUtils.get_mac_address() + "sdf*(*1234_)_(^%$%$2135sdf(**^%%$!@#%$%&^(*()^%#$"))
        self.btn_copy = QPushButton("复制")
        self.btn_copy.clicked.connect(self.copy_text)
        self.btn_active = QPushButton("激活")
        self.ly_mac_btns.addWidget(self.lb_mac)
        self.ly_mac_btns.addWidget(self.btn_copy)
        self.ly_mac_btns.addWidget(self.btn_active)

        # 秘钥输入框
        self.te_key = QTextEdit()
        self.te_key.setLineWrapMode(QTextEdit.WidgetWidth)
        self.te_key.setPlaceholderText("请输入秘钥...")
        self.te_key.textChanged.connect(self.on_te_key_changed)
        if not self.te_key.toPlainText().strip():
            self.btn_active.setEnabled(False)

        # 激活信号
        self.btn_active.clicked.connect(lambda: self.activate(self.te_key.toPlainText()))

        # 添加控件
        self.ly_activate.addLayout(self.ly_mac_btns)
        self.ly_activate.addWidget(self.te_key)
        # 激活页面
        self.tab_mac = QWidget()
        self.tab_mac.setLayout(self.ly_activate)
        self.tab_widget.addTab(self.tab_mac, "激活")

    def on_te_key_changed(self):
        if not self.te_key.toPlainText().strip():
            self.btn_active.setEnabled(False)
        else:
            self.btn_active.setEnabled(True)

    def copy_text(self):
        # 获取剪贴板
        clipboard = QApplication.clipboard()
        # 设置剪贴板文本内容
        clipboard.setText(self.lb_mac.text())
        # 弹出消息框提示复制成功
        QMessageBox.information(self, '信息', '文本已复制到剪贴板', QMessageBox.Ok)

    def init_app_status(self):
        # 获取激活状态，在启动时获取
        activate_status = SysConfig.get_value(Constants.ConfigFileKey.ACTIVATE_STATUS)
        signature_file = SysPathUtils.get_signature_file()

        activate_status = ActivateStatus.get_by_value(activate_status.get("value"))
        if activate_status:
            if activate_status in {ActivateStatus.ACTIVATED, ActivateStatus.REMOTE_VERIFY_FAILED}:
                # 新增一个远程校验证失败的状态，然后在此处重新开启验证！原则验证的时候需要标识出为远程验证失败！提示联网后，重新验证！
                if not os.path.exists(signature_file):
                    self.activate_status = ActivateStatus.NOT_ACTIVATED
                    # 更新标题
                    self.set_title_when_not_activated()
                    # 更新配置文件
                    SysConfig.save_value(Constants.ConfigFileKey.ACTIVATE_STATUS, self.activate_status.value)
                    db.data_dict_dao.get_by_key(Constants.ConfigFileKey.ACTIVATE_STATUS)
                else:
                    self.startup_verify()
            elif activate_status == ActivateStatus.EXPIRED:
                # 过期
                self.activate_status = ActivateStatus.EXPIRED
                # 更新标题
                self.set_title_when_expired()
            elif activate_status == ActivateStatus.NOT_ACTIVATED:
                # 未激活
                self.activate_status = ActivateStatus.NOT_ACTIVATED
                # 更新标题
                self.set_title_when_not_activated()
            else:
                # 状态未知
                self.activate_status = ActivateStatus.NOT_ACTIVATED
                # 更新标题
                self.set_title_when_not_activated()
        else:
            # 状态未知
            self.activate_status = ActivateStatus.NOT_ACTIVATED
            # 更新标题
            self.set_title_when_not_activated()
            # 更新配置文件
            SysConfig.save_value(Constants.ConfigFileKey.ACTIVATE_STATUS, self.activate_status.value)

    def _start_timer(self, expired_time: int):
        if not self.timer:
            self.timer = QTimer(self)
            self.timer.timeout.connect(lambda: self._update_countdown(expired_time))
            self.timer.start(1000)
        else:
            self.timer.stop()
            self.timer.timeout.disconnect()
            self.timer.timeout.connect(lambda: self._update_countdown(expired_time))
            self.timer.start(1000)

    def activate(self, activation_key):
        activate_thread = ActivateThread(self, self.get_app_name(), self.get_mac_id(), self.activate_status,
                                         activation_key,
                                         self.expired_time)
        activate_thread.activate_result_signal.connect(self._activate_result_callback)
        activate_thread.start()

    def startup_verify(self):
        activate_thread = ActivateThread(self, self.get_app_name(), self.get_mac_id(), action=1)
        activate_thread.startup_verify_signal.connect(self._startup_verify_callback)
        activate_thread.start()

    def _startup_verify_callback(self, activate_status: ActivateStatus, expired_time: str, fail_reason: str):
        expired_time = int(expired_time)
        if activate_status == ActivateStatus.EXPIRED:
            # 过期了
            self.activate_status = activate_status
            # 更新标题
            self.set_title_when_expired()
            # 更新配置文件
            SysConfig.save_value(Constants.ConfigFileKey.ACTIVATE_STATUS, activate_status.value)
        elif activate_status == ActivateStatus.ACTIVATED:
            # 未过期
            self.activate_status = activate_status
            # 过期时间
            self.expired_time = expired_time
            # 启动倒计时定时器
            self._start_timer(self.expired_time)
        elif activate_status == ActivateStatus.NOT_ACTIVATED:
            # 激活状态未知，此种情况的发生，可能存在人为修改了秘钥
            self.activate_status = activate_status
            # 更新标题
            self.set_title_when_not_activated()
            # 更新配置文件
            SysConfig.save_value(Constants.ConfigFileKey.ACTIVATE_STATUS, self.activate_status.value)
        elif activate_status == ActivateStatus.REMOTE_VERIFY_FAILED:
            self.activate_status = activate_status
            # 更新标题
            self.set_title_when_not_activated(
                "激活失败：秘钥已使用！" if "秘钥已使用" in fail_reason else "激活失败：请检查网络、重启软件或重新激活！")
            SysConfig.save_value(Constants.ConfigFileKey.ACTIVATE_STATUS, self.activate_status.value)
        else:
            pass

    def _activate_result_callback(self, activate_status: ActivateStatus, expired_time: str, fail_reason: str):
        expired_time = int(expired_time)
        if activate_status == ActivateStatus.ACTIVATED:
            # 更新标题
            self.set_title_with_time_countdown(expired_time - int(datetime.utcnow().timestamp()))
            # 更新软件状态
            self.activate_status = ActivateStatus.ACTIVATED
            # 更新软件的过期时间
            self.expired_time = expired_time
            # 定时器重新计时
            self._start_timer(self.expired_time)
            # 提示激活成功
            QMessageBox.information(self, "操作结果", "激活成功")
        else:
            # 提示激活失败
            QMessageBox.warning(self, "操作结果", f"激活失败-{fail_reason}")

    def _timestamp_to_dhms(self, timestamp):
        # 计算总秒数
        total_seconds = int(timestamp)
        # 计算天数
        days = total_seconds // (3600 * 24)
        # 计算剩余秒数
        remaining_seconds = total_seconds % (3600 * 24)
        # 计算小时数
        hours = remaining_seconds // 3600
        # 计算剩余秒数
        remaining_seconds %= 3600
        # 计算分钟数
        minutes = remaining_seconds // 60
        # 计算秒数
        seconds = remaining_seconds % 60
        # 格式化输出
        result = []
        if days:
            result.append(f" {days} 天")
        if hours:
            result.append(f" {hours} 时")
        if minutes:
            result.append(f" {minutes} 分")
        if seconds >= 0 or (not days and not hours and not minutes):
            result.append(f" {seconds} 秒")

        return "".join(result)

    def _update_countdown(self, expired_time: int):
        remaining_time = expired_time - int(datetime.utcnow().timestamp())
        if remaining_time > 0:
            self.set_title_with_time_countdown(remaining_time)
        else:
            self.set_title_when_expired()
            self.activate_status = ActivateStatus.EXPIRED
            self.timer.stop()

    def is_activate(self):
        return not self.need_activate or self.activate_status == ActivateStatus.ACTIVATED

    def set_title_with_time_countdown(self, expired_time: int):
        self.setWindowTitle(
            f"{self.get_app_name()}{self.get_version()}        剩余时间：{self._timestamp_to_dhms(expired_time)}")

    def set_title_when_expired(self):
        self.setWindowTitle(f"{self.get_app_name()}{self.get_version()}        已过期，请续期！")

    def set_title_when_not_activated(self, extra=""):
        self.setWindowTitle(f"{self.get_app_name()}{self.get_version()}        {'未激活！' if not extra else extra}")

    def get_app_name(self):
        raise NotImplementedError()

    def get_version(self):
        raise NotImplementedError()

    def get_icon(self):
        raise NotImplementedError()

    def get_mac_id(self):
        return self.lb_mac.text()


class BaseTabWidget(QWidget):
    # ======================== 3套QTabWidget样式常量 ========================
    # 风格1：简约现代风（通用后台，清爽易读）
    STYLE_MODERN = """
    /* 整体QTabWidget */
    QTabWidget {
        font-family: "黑体";
        font-size: 18px;
    }

    /* 标签栏（顶部） */
    QTabBar {
        background-color: #f8f9fa;
        border-bottom: 1px solid #dee2e6;
    }

    /* 单个标签 */
    QTabBar::tab {
        background-color: transparent;
        color: #495057;
        padding: 10px 20px;
        margin-right: 2px;
        border-bottom: 3px solid transparent;
    }
    /* 悬浮标签 */
    QTabBar::tab:hover {
        color: #0d6efd;
        background-color: #e9f0fd;
    }

    /* 选中标签 */
    QTabBar::tab:selected {
        /*color: #0d6efd;*/
        /*border-bottom: 3px solid #0d6efd;*/
        color: #198754;
        border-bottom: 3px solid #198754;
        font-weight: 600;
    }

    /* 禁用标签 */
    QTabBar::tab:disabled {
        color: #adb5bd;
    }

    /* 标签内容面板 */
    QTabWidget::pane {
        border: 1px solid #dee2e6;
        border-top: none;
        background-color: white;
        margin-top: -1px; /* 消除标签栏与面板的缝隙 */
    }

    /* 标签过多时的滚动按钮 */
    QTabBar::scroller {
        width: 30px;
        color: #0d6efd;
    }
    
    """

    # 风格2：深色专业风（匹配左侧深色导航）
    STYLE_DARK = """
    /* 整体QTabWidget */
    QTabWidget {
        font-family: "微软雅黑";
        font-size: 18px;
        color: white;
    }

    /* 标签栏（顶部） */
    QTabBar {
        background-color: #2c3e50;
        border-bottom: 1px solid #34495e;
    }

    /* 单个标签 */
    QTabBar::tab {
        background-color: transparent;
        color: #bdc3c7;
        padding: 10px 20px;
        margin-right: 2px;
        border-bottom: 3px solid transparent;
    }

    /* 悬浮标签 */
    QTabBar::tab:hover {
        color: white;
        background-color: #34495e;
    }

    /* 选中标签 */
    QTabBar::tab:selected {
        color: white;
        border-bottom: 3px solid #3498db;
        font-weight: 600;
    }

    /* 禁用标签 */
    QTabBar::tab:disabled {
        color: #7f8c8d;
    }

    /* 标签内容面板 */
    QTabWidget::pane {
        border: 1px solid #34495e;
        border-top: none;
        background-color: #1a2530;
        margin-top: -1px;
    }

    /* 标签过多时的滚动按钮 */
    QTabBar::scroller {
        width: 30px;
        color: #3498db;
    }
    """

    # 风格3：清新轻量风（明亮柔和，低视觉疲劳）
    STYLE_LIGHT = """
    /* 整体QTabWidget */
    QTabWidget {
        font-family: "黑体";
        font-size: 18px;
    }

    /* 标签栏（顶部） */
    QTabBar {
        background-color: #f0f8fb;
        border-bottom: 1px solid #e8f4f8;
    }

    /* 单个标签 */
    QTabBar::tab {
        background-color: transparent;
        color: #2d3748;
        padding: 10px 20px;
        margin-right: 4px;
        border-radius: 0px 0px 0 0; /* 顶部圆角 */
    }

    /* 悬浮标签 */
    QTabBar::tab:hover {
        color: #38b2ac;
        background-color: #e8f4f8;
    }

    /* 选中标签 */
    QTabBar::tab:selected {
        color: white;
        background-color: #38b2ac;
        /*background-color: #198754;*/
        font-weight: 600;
    }

    /* 禁用标签 */
    QTabBar::tab:disabled {
        color: #a0aec0;
    }

    /* 标签内容面板 */
    QTabWidget::pane {
        border: 1px solid #e8f4f8;
        border-top: none;
        background-color: white;
        margin-top: -1px;
        border-radius: 0 8px 8px 8px; /* 面板圆角 */
    }

    /* 标签过多时的滚动按钮 */
    QTabBar::scroller {
        width: 30px;
        color: #38b2ac;
    }
    """
    def __init__(self):
        super().__init__()
        # 标签控件
        self.tab_widget = self.create_tab_widget()
        self.setStyleSheet(self.STYLE_LIGHT)
        # 添加标签页
        self._add_tab_widgets()
        self.ly_main = QVBoxLayout()
        self.ly_main.addWidget(self.tab_widget)
        # 在主页面添加控件
        self._add_to_main_layout()
        self.setLayout(self.ly_main)

    def _add_tab_widgets(self):
        widgets = self.add_tab_widgets()
        if widgets:
            for widget in widgets:
                self.tab_widget.addTab(widget.widget, widget.tab_name)

    def _add_to_main_layout(self):
        objs = self.add_to_main_layout()
        if objs:
            for obj in objs:
                if isinstance(obj, QLayout):
                    self.ly_main.addLayout(obj)
                elif isinstance(obj, QWidget):
                    self.ly_main.addWidget(obj)

    @abstractmethod
    def add_tab_widgets(self) -> List[TabWidgetInfo]:
        """
        添加标签页面
        :return: List[QWidget]
        """
        raise NotImplementedError()

    def add_to_main_layout(self) -> List[Union[QWidget, QLayout]]:
        """
        添加控件到主页面
        :return:
        """
        return []

    def create_tab_widget(self):
        tab_widget = QTabWidget()
        # 设置样式表来改变活动标签页的底色
        # style_sheet = """
        #     QTabBar::tab {
        #         padding: 5px;
        #     }
        #     QTabBar::tab:selected {
        #         background-color: #007BFF; /* 设置活动标签页的背景颜色为金色 */
        #         color: white; /* 设置活动标签页的文字颜色为白色 */
        #     }
        # """
        return tab_widget

    def set_style_sheet(self, style_sheet):
        self.tab_widget.setStyleSheet(style_sheet)

def is_cell_input_legal(input_text: str):
    ret = False
    if input_text is not None and isinstance(input_text, str) and len(input_text) > 0:
        pattern = "^[a-zA-Z]+[1-9][0-9]*$"
        if re.match(pattern, input_text):
            ret = True
    return ret


class CoreBusinessWidget(QWidget):
    signal = pyqtSignal(bool)

    def __init__(self, activate_status=False):
        super().__init__(flags=Qt.MSWindowsFixedSizeDialogHint)
        self.activate_status = activate_status
        # 重定向日志信息
        # 日志信息输出到该位置
        self.tb_log_info = QTextBrowser()
        self.tb_log_info.document().setMaximumBlockCount(1000)
        self.gb_user_info = QGroupBox("用户信息")
        self.gb_log_info = QGroupBox("日志")
        qt_logger.signal.connect(self.tb_log_info.append)

        self.le_file_path = QLineEdit()
        self.le_file_path.setPlaceholderText("用户表格路径xlsx")
        self.btn_open_file = QPushButton("打开文件")
        ly_file_path = QHBoxLayout()
        ly_file_path.addWidget(QLabel("用户信息表："))
        ly_file_path.addWidget(self.le_file_path)
        ly_file_path.addWidget(self.btn_open_file)

        self.le_workbook_name = QLineEdit()
        self.le_workbook_name.setText(self.get_workbook_name())
        self.ly_workbook_name = QHBoxLayout()
        self.ly_workbook_name.addWidget(QLabel("工作簿名称："))
        self.ly_workbook_name.addWidget(self.le_workbook_name)

        self.btn_open_file.clicked.connect(self._open_file)
        self.username_start_pos_line_edit = QLineEdit("a1")
        self.username_start_pos_line_edit.setPlaceholderText("用户名起始单元格，例如A1")
        self.username_end_pos_line_edit = QLineEdit("a")
        self.username_end_pos_line_edit.setPlaceholderText("用户名截止单元格，例如A20")
        self.password_start_pos_line_edit = QLineEdit("b1")
        self.password_start_pos_line_edit.setPlaceholderText("密码起始单元格，例如B1")
        self.password_end_pos_line_edit = QLineEdit("b")
        self.password_end_pos_line_edit.setPlaceholderText("密码截止单元格，例如B1")

        ly_username_password = QGridLayout()
        self.btn_start = QPushButton("开始")
        font = QFont()
        font.setPointSize(12)
        self.btn_start.setFont(font)
        self.btn_start.clicked.connect(self.start_tasks)
        # self.btn_start.maximumHeight()
        # self.btn_start.setFixedSize(self.btn_start.sizeHint())
        # self.btn_start.setFixedSize(50,50)
        self.btn_start.setFixedHeight(60)
        ly_username_password.addWidget(QLabel("用户名列："), 0, 0)
        ly_username_password.addWidget(self.username_start_pos_line_edit, 0, 1)
        ly_username_password.addWidget(QLabel(":"), 0, 2)
        ly_username_password.addWidget(self.username_end_pos_line_edit, 0, 3)

        ly_username_password.addWidget(QLabel("密 码 列："), 1, 0)
        ly_username_password.addWidget(self.password_start_pos_line_edit, 1, 1)
        ly_username_password.addWidget(QLabel(":"), 1, 2)
        ly_username_password.addWidget(self.password_end_pos_line_edit, 1, 3)
        # ly_username_password.heightForWidth()
        # ly_username_password.addWidget(self.btn_start, 0, 4)

        ly_user_info_spilt = QHBoxLayout()
        ly_user_info_spilt.addLayout(ly_username_password)
        ly_user_info_spilt.addWidget(self.btn_start, alignment=Qt.AlignCenter)
        # ly_user_info_spilt.setsi

        ly_login_info = QHBoxLayout()
        ly_login_info.addWidget(self.tb_log_info)
        self.gb_log_info.setLayout(ly_login_info)

        self.ly_user_info = QVBoxLayout()
        self.ly_user_info.addLayout(ly_file_path)
        self.ly_user_info.addLayout(self.ly_workbook_name)
        self.ly_user_info.addLayout(ly_user_info_spilt)
        self.gb_user_info.setLayout(self.ly_user_info)

        self.setLayout(self.compose_components())

    def compose_components(self) -> QLayout:
        """
        组合组件
        :return:
        """
        ly_main_window = QVBoxLayout()
        ly_main_window.addWidget(self.gb_user_info)
        ly_main_window.addWidget(self.gb_log_info)
        ly_main_window.setStretch(0, 1)
        ly_main_window.setStretch(1, 3)
        return ly_main_window

    @abstractmethod
    def get_workbook_name(self) -> str:
        return ""

    @abstractmethod
    def get_activate_status(self) -> bool:
        pass

    def _open_file(self):
        path_obj = SysConfig.get_value(Constants.ConfigFileKey.LATEST_USER_INFO_FILE_DIR_NAME)
        if not path_obj or not path_obj.get("value"):
            path = os.getcwd()
        else:
            path = path_obj.get("value")
        file_path, filter = QFileDialog.getOpenFileName(self, "打开文件", path, "格式 (*.xlsx)")
        if file_path:
            SysConfig.save_value(Constants.ConfigFileKey.LATEST_USER_INFO_FILE_DIR_NAME, os.path.dirname(file_path))
            self.le_file_path.setText(file_path)

    def _is_active(self) -> bool:
        return self.get_activate_status()

    def start_tasks(self):
        """
        开始任务
        :return:
        """
        try:
            if not self._is_active():
                QMessageBox.warning(self, "警告", "未激活，联系管理员激活！", QMessageBox.Ok)
                return
        except Exception as e:
            QMessageBox.warning(self, "警告", "未激活，联系管理员激活！", QMessageBox.Ok)
            return

        if self.check_params():
            # 参数合格了
            self.btn_start.setText("运行中...")
            self.enabled_widget(False)
            self.tb_log_info.clear()
            xlsx_path = self.le_file_path.text()
            sheet_name = self.le_workbook_name.text()
            username_start_cell = self.username_start_pos_line_edit.text()
            username_end_cell = self.username_end_pos_line_edit.text()
            password_start_cell = self.password_start_pos_line_edit.text()
            password_end_cell = self.password_end_pos_line_edit.text()
            user_info_location = UserInfoLocation(xlsx_path, sheet_name, username_start_cell, username_end_cell,
                                                  password_start_cell, password_end_cell)
            # self.busi_handler.xlsx_path = xlsx_path
            # self.busi_handler.sheet_name = sheet_name
            # self.busi_handler.username_start_cell = username_start_cell
            # self.busi_handler.username_end_cell = username_end_cell
            # self.busi_handler.password_start_cell = password_start_cell
            # self.busi_handler.password_end_cell = password_end_cell
            # self.busi_handler.start()
            task = self.get_task_obj(user_info_location)
            # TODO 其他信号未监听
            task.all_task_finished_signal.connect(self.update_progress)
            task.start_task()

    @abstractmethod
    def get_task_obj(self, user_info_location: UserInfoLocation) -> TaskManager:
        pass

    def enabled_widget(self, status):
        self.btn_start.setEnabled(status)
        self.username_start_pos_line_edit.setEnabled(status)
        self.username_end_pos_line_edit.setEnabled(status)
        self.password_start_pos_line_edit.setEnabled(status)
        self.password_end_pos_line_edit.setEnabled(status)
        self.btn_open_file.setEnabled(status)
        self.le_workbook_name.setEnabled(status)
        self.le_file_path.setEnabled(status)

    # def update_text_browser(self, text):
    #     self.tb_log_info.append(text)
    #     self.tb_log_info.moveCursor(QTextCursor.End)

    def update_progress(self):
        # print("结束")
        self.btn_start.setText("开始")
        self.enabled_widget(True)

    def check_params(self):
        if len(self.le_file_path.text().strip()) == 0:
            # 弹窗警告
            QMessageBox.critical(self, "输入错误", "用户表格路径不能为空", QMessageBox.Yes)
            return False
        if not is_cell_input_legal(self.username_start_pos_line_edit.text()):
            # 弹窗警告
            QMessageBox.critical(self, "输入错误", "用户名起始位置输入格式有误", QMessageBox.Yes)
            return False
        if not is_cell_input_legal(self.username_end_pos_line_edit.text()):
            # 弹窗警告
            QMessageBox.critical(self, "输入错误", "用户名截止位置输入格式有误", QMessageBox.Yes)
            return False
        if not is_cell_input_legal(self.password_start_pos_line_edit.text()):
            # 弹窗警告
            QMessageBox.critical(self, "输入错误", "密码起始位置输入格式有误", QMessageBox.Yes)
            return False
        if not is_cell_input_legal(self.password_end_pos_line_edit.text()):
            # 弹窗警告
            QMessageBox.critical(self, "输入错误", "密码截止位置输入格式有误", QMessageBox.Yes)
            return False

        try:
            self.check_custom_params()
        except ParamError as e:
            QMessageBox.critical(self, "输入错误", e.error_desc, QMessageBox.Yes)
            return False
        except Exception as e:
            QMessageBox.critical(self, "输入错误", "校验参数出现异常！", QMessageBox.Yes)
            return False
        return True

    def check_custom_params(self):
        """
        子类自行实现参数校验，参数错误时候抛出ParamError异常
        :raise: ParamError
        :return:
        """
        pass
        # if len(self.le_file_path.text().strip()) == 0:
        #     # 弹窗警告
        #     QMessageBox.critical(self, "输入错误", "用户表格路径不能为空", QMessageBox.Yes)
        #     return False
        # elif not is_cell_input_legal(self.le_username_start_pos.text()):
        #     # 弹窗警告
        #     QMessageBox.critical(self, "输入错误", "用户名起始位置输入格式有误", QMessageBox.Yes)
