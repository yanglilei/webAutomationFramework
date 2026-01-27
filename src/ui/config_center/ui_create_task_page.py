import json
import logging
import os
import re
from datetime import datetime
from typing import Optional, List, Tuple

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QVBoxLayout, QHBoxLayout, QLabel, QGridLayout, QWidget, QLineEdit, QPushButton, \
    QMessageBox, QFileDialog, QGroupBox, QRadioButton, QButtonGroup, QSizePolicy, QSpacerItem

from src.frame.base.ui.base_table_widget import BaseTableWidget
from src.frame.base.ui.base_ui import BaseTabWidget, TabWidgetInfo
from src.frame.common.activate_manager import ActivationManager
from src.frame.common.constants import Constants
from src.frame.common.exceptions import ParamError
from src.frame.common.sys_config import SysConfig
from src.frame.dao.async_db_task_scheduler import AsyncTaskScheduler
from src.frame.dao.db_manager import db
from src.ui.config_center.ui_task_tmpl import UITaskTmpl
from src.utils import batch_no_utils


class AutoModePage(BaseTabWidget):
    def __init__(self, ui_task_tmpl):
        super().__init__()
        self.db = db
        self.ui_task_tmpl = ui_task_tmpl
        self.setStyleSheet(self.STYLE_MODERN)
        self.async_task_scheduler = AsyncTaskScheduler()  # 异步任务调度器
        self.activation_manager = ActivationManager()  # 激活管理器
        self.activation_manager.activation_status_changed.connect(self.on_activation_status_changed)

    def add_tab_widgets(self) -> List[TabWidgetInfo]:
        return [TabWidgetInfo("表格导入", self._create_table_user_info_page()),
                TabWidgetInfo("文本导入", self._create_text_user_info_page())]

    def _create_table_user_info_page(self):
        self.le_file_path = QLineEdit()
        self.le_file_path.setPlaceholderText("用户表格路径xlsx")
        self.btn_open_file = QPushButton("打开文件")
        self.btn_open_file.clicked.connect(self._open_file)
        self.le_workbook_name = QLineEdit()

        self.le_username_start_pos = QLineEdit("a1")
        self.le_username_start_pos.setPlaceholderText("用户名起始单元格，例如A1")
        self.le_username_end_pos = QLineEdit("a")
        self.le_username_end_pos.setPlaceholderText("用户名截止单元格，例如A20")
        self.le_password_start_pos = QLineEdit("b1")
        self.le_password_start_pos.setPlaceholderText("密码起始单元格，例如B1")
        self.le_password_end_pos = QLineEdit("b")
        self.le_password_end_pos.setPlaceholderText("密码截止单元格，例如B1")
        ly_username_password = QGridLayout()

        ly_username_password.addWidget(QLabel("用户信息表："), 0, 0)
        ly_username_password.addWidget(self.le_file_path, 0, 1)
        ly_username_password.addWidget(self.btn_open_file, 0, 2)

        ly_username_password.addWidget(QLabel("用户名列："), 0, 3)
        ly_username_password.addWidget(self.le_username_start_pos, 0, 4)
        ly_username_password.addWidget(QLabel(":"), 0, 5)
        ly_username_password.addWidget(self.le_username_end_pos, 0, 6)

        ly_username_password.addWidget(QLabel("工作簿名称："), 1, 0)
        ly_username_password.addWidget(self.le_workbook_name, 1, 1)
        ly_username_password.addWidget(QLabel("密 码 列："), 1, 3)
        ly_username_password.addWidget(self.le_password_start_pos, 1, 4)
        ly_username_password.addWidget(QLabel(":"), 1, 5)
        ly_username_password.addWidget(self.le_password_end_pos, 1, 6)

        self.btn_add_task = QPushButton("添加任务")
        self.btn_add_task.setEnabled(False)
        # font = QFont()
        # font.setPointSize(12)
        # self.btn_start.setFont(font)
        self.btn_add_task.clicked.connect(self.on_add_task_in_file_mode)
        # self.btn_start.maximumHeight()
        # self.btn_start.setFixedSize(self.btn_start.sizeHint())
        # self.btn_start.setFixedSize(50,50)
        self.btn_add_task.setFixedHeight(60)

        ly_user_info_spilt = QHBoxLayout()
        ly_user_info_spilt.addLayout(ly_username_password)
        ly_user_info_spilt.addWidget(self.btn_add_task, alignment=Qt.AlignCenter)

        ly_user_info = QVBoxLayout()
        ly_user_info.addLayout(ly_user_info_spilt)
        widget = QWidget()
        widget.setLayout(ly_user_info)
        return widget

    def _create_text_user_info_page(self):
        ly_username_password = QVBoxLayout()
        self.le_username = QLineEdit()
        self.le_password = QLineEdit()
        ly_username_password = QGridLayout()
        # ly_username = QHBoxLayout()
        # ly_password = QHBoxLayout()
        ly_username_password.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Expanding), 0, 0)
        ly_username_password.addWidget(QLabel("用户名："), 0, 1)
        ly_username_password.addWidget(self.le_username, 0, 2)
        ly_username_password.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Expanding), 0, 3)

        ly_username_password.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Expanding), 1, 0)
        ly_username_password.addWidget(QLabel("密  码："), 1, 1)
        ly_username_password.addWidget(self.le_password, 1, 2)
        ly_username_password.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Expanding), 1, 3)

        self.btn_add_task_in_text_mode = QPushButton("添加任务")
        self.btn_add_task_in_text_mode.clicked.connect(self.on_add_task_in_text_mode)
        self.btn_add_task_in_text_mode.setFixedHeight(60)

        ly_main = QHBoxLayout()
        ly_main.addLayout(ly_username_password)
        ly_main.addWidget(self.btn_add_task_in_text_mode, alignment=Qt.AlignCenter)

        widget = QWidget()
        widget.setLayout(ly_main)
        return widget

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

    def on_add_task_in_text_mode(self):
        if not self.le_username.text() or not self.le_username.text().strip() or not self.le_password.text() or not self.le_password.text().strip():
            QMessageBox.critical(self, "错误", "用户名或密码不能为空")
            return
        self.async_task_scheduler.submit_task(self.add_task_in_text_mode, self.le_username.text(),
                                              self.le_password.text(),
                                              finished_callback=self.on_add_task_batch_success)

    def on_add_task_in_file_mode(self):
        # 用户文件模式
        if not self.check_params():
            return
        self.async_task_scheduler.submit_task(self.add_task_in_file_mode,
                                              finished_callback=self.on_add_task_batch_success)

    def add_task_in_text_mode(self, username, password):
        records = []
        for row in self.ui_task_tmpl.get_selected_rows():
            # 如tb_task_batch表
            task_tmpl_id = row["id"]
            task_tmpl = self.db.task_tmpl_dao.get_by_id(task_tmpl_id)
            project_id = task_tmpl.get("project_id")
            project = self.db.project_dao.get_by_id(project_id)
            record = {"task_tmpl_id": task_tmpl_id,
                      "task_tmpl_name": task_tmpl.get("name"),
                      "business_type": task_tmpl.get("business_type"),
                      "project_id": project_id,
                      "project_name": project.get("name"),
                      "run_mode": 1,
                      "user_mode": 2,
                      "user_info": json.dumps([{"username": username, "password": password}],
                                              ensure_ascii=False),
                      "priority": 5,  # 默认值为5
                      "queue_time": datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S"),
                      "execute_status": 0,
                      "batch_no": batch_no_utils.generate_batch_number("-")
                      }

            records.append(record)
        status = True
        msg = "添加任务批次成功"
        try:
            self.db.task_batch_dao.batch_add(records)
        except:
            logging.exception(f"添加任务批次失败：")
            msg = "添加任务批次失败"
            status = False

        return status, msg

    def on_activation_status_changed(self, status, msg):
        self.btn_add_task.setEnabled(status)

    def add_task_in_file_mode(self):
        """
        用户文件模式添加任务
        :return:
        """
        # try:
        #     if not self._is_active():
        #         QMessageBox.warning(self, "警告", "未激活，联系管理员激活！", QMessageBox.Ok)
        #         return
        # except Exception as e:
        #     QMessageBox.warning(self, "警告", "未激活，联系管理员激活！", QMessageBox.Ok)
        #     return
        # status, msg = self.check_params2()
        # if not status:
        #     logging.error(f"添加任务批次失败：{msg}")
        #     return status, msg

        # 参数合格了
        xlsx_path = self.le_file_path.text()
        sheet_name = self.le_workbook_name.text()
        username_start_cell = self.le_username_start_pos.text()
        username_end_cell = self.le_username_end_pos.text()
        password_start_cell = self.le_password_start_pos.text()
        password_end_cell = self.le_password_end_pos.text()
        # user_info_location = UserInfoLocation(xlsx_path, sheet_name, username_start_cell, username_end_cell,
        #                                       password_start_cell, password_end_cell)

        datas = self.db.data_dict_dao.get_all()
        global_config = json.dumps({data.get("key"): data.get("value") for data in datas}, ensure_ascii=False)
        user_info = json.dumps({"workbook_addr": xlsx_path, "sheet_name": sheet_name,
                                "username_start_cell": username_start_cell,
                                "username_end_cell": username_end_cell,
                                "password_start_cell": password_start_cell,
                                "password_end_cell": password_end_cell}, ensure_ascii=False)
        records = []
        for row in self.ui_task_tmpl.get_selected_rows():
            # 如tb_task_batch表
            task_tmpl_id = row["id"]
            task_tmpl = self.db.task_tmpl_dao.get_by_id(task_tmpl_id)
            project_id = task_tmpl.get("project_id")
            project = self.db.project_dao.get_by_id(project_id)
            record = {"task_tmpl_id": task_tmpl_id,
                      "task_tmpl_name": task_tmpl.get("name"),
                      "business_type": task_tmpl.get("business_type"),
                      "project_id": project_id,
                      "project_name": project.get("name"),
                      "run_mode": 1,
                      "user_mode": 1,
                      "global_config": global_config,
                      "user_info": user_info,
                      "priority": 5,  # 默认值为5
                      "queue_time": datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S"),
                      "execute_status": 0,
                      "batch_no": batch_no_utils.generate_batch_number("-")
                      }

            records.append(record)
        status = True
        msg = "添加任务批次成功"
        try:
            self.db.task_batch_dao.batch_add(records)
        except:
            logging.exception(f"添加任务批次失败：")
            msg = "添加任务批次失败"
            status = False

        return status, msg

    def check_params(self):
        if len(self.le_file_path.text().strip()) == 0:
            # 弹窗警告
            QMessageBox.critical(self, "输入错误", "用户表格路径不能为空", QMessageBox.Yes)
            return False
        if not self.is_cell_input_legal(self.le_username_start_pos.text()):
            # 弹窗警告
            QMessageBox.critical(self, "输入错误", "用户名起始位置输入格式有误", QMessageBox.Yes)
            return False
        if not self.is_cell_input_legal(self.le_username_end_pos.text()):
            # 弹窗警告
            QMessageBox.critical(self, "输入错误", "用户名截止位置输入格式有误", QMessageBox.Yes)
            return False
        if not self.is_cell_input_legal(self.le_password_start_pos.text()):
            # 弹窗警告
            QMessageBox.critical(self, "输入错误", "密码起始位置输入格式有误", QMessageBox.Yes)
            return False
        if not self.is_cell_input_legal(self.le_password_end_pos.text()):
            # 弹窗警告
            QMessageBox.critical(self, "输入错误", "密码截止位置输入格式有误", QMessageBox.Yes)
            return False
        if not self.ui_task_tmpl.get_selected_rows():
            QMessageBox.critical(self, "错误", "请选择任务模板", QMessageBox.Yes)
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

    def check_custom_params(self) -> Tuple[bool, str]:
        """
        子类自行实现参数校验，参数错误时候抛出ParamError异常
        :raise: ParamError
        :return:
        """
        return True, ""

    def is_cell_input_legal(self, input_text: str):
        ret = False
        if input_text is not None and isinstance(input_text, str) and len(input_text) > 0:
            pattern = "^[a-zA-Z]+[1-9][0-9]*$"
            if re.match(pattern, input_text):
                ret = True
        return ret

    def on_add_task_batch_success(self, status, msg, payloads):
        if status:
            if not payloads[0]:
                QMessageBox.critical(self, "错误", f"添加任务批次失败：{payloads[1]}")
            else:
                QMessageBox.information(self, "提示", "添加任务批次成功")
        else:
            QMessageBox.critical(self, "错误", f"添加任务批次失败：{msg}")


class SemiModePage(QWidget):
    def __init__(self, ui_task_tmpl):
        super().__init__()
        self.db = db
        self.async_task_scheduler = AsyncTaskScheduler()
        # 激活管理器
        self.activation_manager = ActivationManager()
        self.activation_manager.activation_status_changed.connect(self.on_activation_status_changed)
        self.ui_task_tmpl = ui_task_tmpl
        self.setLayout(self._create_semi_mode_ui())

    def _create_semi_mode_ui(self):
        layout = QVBoxLayout()
        self.btn_add_task = QPushButton("添加任务")
        self.btn_add_task.setEnabled(False)
        self.btn_add_task.clicked.connect(self.on_add_task)
        layout.addWidget(self.btn_add_task)
        return layout

    def on_activation_status_changed(self, status, msg):
        self.btn_add_task.setEnabled(status)

    def on_add_task(self):
        if not self.check_params():
            return
        self.async_task_scheduler.submit_task(self.add_task,
                                              finished_callback=self.on_add_task_batch_success)

    def check_params(self):
        if not self.ui_task_tmpl.get_selected_rows():
            QMessageBox.critical(self, "错误", "请选择任务模板", QMessageBox.Yes)
            return False
        return True

    def add_task(self):
        records = []
        for row in self.ui_task_tmpl.get_selected_rows():
            # 如tb_task_batch表
            task_tmpl_id = row["id"]
            task_tmpl = self.db.task_tmpl_dao.get_by_id(task_tmpl_id)
            project_id = task_tmpl.get("project_id")
            project = self.db.project_dao.get_by_id(project_id)
            record = {"task_tmpl_id": task_tmpl_id,
                      "task_tmpl_name": task_tmpl.get("name"),
                      "business_type": task_tmpl.get("business_type"),
                      "project_id": project_id,
                      "project_name": project.get("name"),
                      "run_mode": 2,  # 1-自动模式；2-半自动模式
                      "user_mode": 0,  # 0-无用户；1-表格模式；2-文本模式
                      "user_info": "",
                      "priority": 5,  # 默认值为5
                      "queue_time": datetime.strftime(datetime.now(), "%Y-%m-%d %H:%M:%S"),
                      "execute_status": 0,
                      "batch_no": batch_no_utils.generate_batch_number("-")
                      }

            records.append(record)
        status = True
        msg = "添加任务批次成功"
        try:
            self.db.task_batch_dao.batch_add(records)
        except:
            logging.exception(f"添加任务批次失败：")
            msg = "添加任务批次失败"
            status = False

        return status, msg

    def on_add_task_batch_success(self, status, msg, payloads):
        if status:
            if not payloads[0]:
                QMessageBox.critical(self, "错误", f"添加任务批次失败：{payloads[1]}")
            else:
                QMessageBox.information(self, "提示", "添加任务批次成功")
        else:
            QMessageBox.critical(self, "错误", f"添加任务批次失败：{msg}")


class UserInfoWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.ui_user_info = UserInfoWidget()
        self.btn_add_task = QPushButton("添加任务")
        self.async_task_scheduler = AsyncTaskScheduler()


class CreateTaskPage(QWidget):
    # 定义自定义信号，用于传递模式选择结果
    mode_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.ly_dynamic = None
        self.ly_main_window = None
        self.db = db
        # self.gb_user_info = QGroupBox("用户信息")
        self.gb_task_tmpl = QGroupBox("任务模板")
        self.ui_task_tmpl: Optional[BaseTableWidget] = None
        self.async_task_scheduler = AsyncTaskScheduler()  # 异步DB任务调度器
        self.init_ui()

    def init_ui(self):
        # 主界面
        self.ly_main_window = QVBoxLayout()
        self.setLayout(self.ly_main_window)
        # 动态变化的UI区域
        self.ly_dynamic = QVBoxLayout()

        ly_task_tmpl = QVBoxLayout()

        self.ui_task_tmpl = UITaskTmpl()
        ly_task_tmpl.addWidget(self.ui_task_tmpl)
        self.gb_task_tmpl.setLayout(ly_task_tmpl)

        ui_run_mode = self._create_run_mode_ui()
        # 1. 设置单选按钮默认选中
        self.auto_radio.setChecked(True)
        # 2. 手动触发模式更新，让子窗口同步显示全自动UI
        self.on_mode_changed(1)
        # 组合组件
        self.ly_main_window.addLayout(ui_run_mode)
        self.ly_main_window.addLayout(self.ly_dynamic)
        self.ly_main_window.addWidget(self.gb_task_tmpl, 1)
        return self.ly_main_window

    def _create_run_mode_ui(self):
        # 单选按钮组布局
        radio_layout = QHBoxLayout()
        radio_layout.addWidget(QLabel("模式："))
        # 创建单选按钮组
        self.mode_group = QButtonGroup(self)

        # 全自动单选按钮
        self.auto_radio = QRadioButton("全自动")
        self.mode_group.addButton(self.auto_radio, 1)
        radio_layout.addWidget(self.auto_radio)

        # 半自动单选按钮
        self.semi_radio = QRadioButton("半自动")
        self.mode_group.addButton(self.semi_radio, 2)
        radio_layout.addWidget(self.semi_radio)
        radio_layout.addStretch()

        # 单选按钮状态变化时触发模式更新
        self.mode_group.buttonClicked[int].connect(self.on_mode_changed)
        return radio_layout

    def on_mode_changed(self, btn_id):
        """单选按钮选择变化时的处理函数"""
        if btn_id == 1:
            self.update_ui("全自动")
        elif btn_id == 2:
            self.update_ui("半自动")

    def update_ui(self, mode):
        # 清空原有动态UI元素
        for i in reversed(range(self.ly_dynamic.count())):
            widget = self.ly_dynamic.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        if mode == "全自动":
            self.ly_dynamic.addWidget(AutoModePage(self.ui_task_tmpl))
        elif mode == "半自动":
            self.ly_dynamic.addWidget(SemiModePage(self.ui_task_tmpl))
        else:
            QMessageBox.critical(self, "错误", "请选择正确的模式")
