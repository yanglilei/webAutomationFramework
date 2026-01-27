from typing import Optional, List

from PyQt5.QtWidgets import QPushButton, QVBoxLayout, QHBoxLayout, QMessageBox, QWidget

from src.frame.base.ui.base_ui import BaseTabWidget, TabWidgetInfo
from src.frame.common.activate_manager import ActivationManager
from src.frame.common.qt_log_redirector import LOG
from src.frame.dao.async_db_task_scheduler import AsyncTaskScheduler
from src.frame.dao.db_manager import db
from src.frame.task_manager import TaskManager
from src.ui.running_center.ui_task_batch import UITaskBatch


class FullAutomaticTaskPage(QWidget):
    """全自动任务页面"""

    def __init__(self):
        super().__init__()
        # 释放资源按钮
        self.btn_free = None
        # 全自动模式
        self.run_mode = 1
        # 开启批次运行按钮
        self.btn_start: Optional[QPushButton] = None
        # 强制终止按钮
        self.btn_force_terminate: Optional[QPushButton] = None
        # 表格
        self.tbl_task_batch: Optional[UITaskBatch] = None
        # 异步任务执行器
        self.async_task_executor: AsyncTaskScheduler = AsyncTaskScheduler()
        # 任务管理器
        self.task_manager = TaskManager(LOG)
        # 激活管理器
        self.activation_manager = ActivationManager()
        self.activation_manager.activation_status_changed.connect(self.on_activation_status_changed)
        # 初始化UI
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        ##### 按钮区域 #####
        ly_buttons = QHBoxLayout()
        self.btn_start = QPushButton("开始运行")
        self.btn_force_terminate = QPushButton("停止任务")
        self.btn_free = QPushButton("释放资源")
        ly_buttons.addWidget(self.btn_start)
        ly_buttons.addWidget(self.btn_force_terminate)
        ly_buttons.addWidget(self.btn_free)

        self.btn_start.clicked.connect(self.on_start_clicked)
        self.btn_force_terminate.clicked.connect(self.on_force_terminate_clicked)
        self.btn_free.clicked.connect(self.on_free_resource)
        ##### 表格区域 #####
        self.tbl_task_batch = UITaskBatch(self.run_mode)

        ##### 添加到主布局 #####
        main_layout.addLayout(ly_buttons)
        main_layout.addWidget(self.tbl_task_batch)
        self.setLayout(main_layout)

    def on_activation_status_changed(self, status, msg):
        self.btn_start.setEnabled(status)

    def on_start_clicked(self):
        self.btn_start.setEnabled(False)
        # 1.校验
        rows = self.tbl_task_batch.get_selected_rows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要运行的批次")
            return
        batch_ids = [row.get("id") for row in rows]
        # 异步查询后执行批次
        self.async_task_executor.submit_task(self.start_task_batches, batch_ids,
                                             finished_callback=self.on_start_task_batches)

    def has_running_task(self) -> bool:
        return self.task_manager.is_running

    def start_task_batches(self, batch_ids):
        # 在线程内部执行
        try:
            task_batches = []
            for batch_id in batch_ids:
                task_batch = db.task_batch_dao.get_by_id(batch_id)
                if not task_batch:
                    LOG.error(f"未找到任务批次，任务批次ID：{batch_id}")
                    continue
                task_batches.append(task_batch)
            if not task_batches:
                LOG.error("任务批次不存在！无法运行！")
                return False, "任务批次不存在！无法运行！"

            if task_batches:
                action_id = db.action_dao.add_one(
                    {"batch_ids": ",".join([str(task_batch.get("id")) for task_batch in task_batches])})
                for task_batch in task_batches:
                    db.task_batch_dao.update_by_id(task_batch.get("id"), {"action_id": action_id})
                    task_batch["action_id"] = action_id
            LOG.info(f"准备初始化任务管理器...")
            # 启动任务
            self.task_manager.start_task(task_batches)
            LOG.info(f"启动任务批次成功...")
            return True, "成功"
        except Exception as e:
            LOG.exception(f"启动任务批次失败：{str(e)}")
            return False, str(e)

    def on_start_task_batches(self, status, msg, payloads):
        self.btn_start.setEnabled(True)
        LOG.debug(f"任务批次启动结果：{status}，{msg}，{payloads}")
        if status:
            if not payloads[0]:
                QMessageBox.critical(self, "错误", f"任务启动失败：{payloads[1]}")
            else:
                QMessageBox.information(self, "提示", "任务启动成功，具体请查看运行日志！")
        else:
            QMessageBox.critical(self, "错误", f"任务启动失败：{msg}")

    def on_force_terminate_clicked(self):
        """
        停止任务
        """
        rows = self.tbl_task_batch.get_selected_rows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要强制终止的批次")
            return

        for row in rows:
            batch_no = row.get("batch_no")
            self.async_task_executor.submit_task(self.task_manager.terminate_task, batch_no)
            # self.task_manager.terminate_task(batch_no)
        QMessageBox.information(self, "提示", "已发送强制终止信号，请刷新任务状态！")

    def on_free_resource(self):
        """
        释放资源
        :return:
        """
        rows = self.tbl_task_batch.get_selected_rows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要释放的批次")
            return
        else:
            val = QMessageBox.warning(self, "提示", "请确认是否要释放资源？", QMessageBox.Yes | QMessageBox.No)
            if val != QMessageBox.Yes:
                return

            batch_nos = [row.get("batch_no") for row in rows]
            self.async_task_executor.submit_task(self.task_manager.free_resource, batch_nos,
                                                 finished_callback=self.on_free_resource_finished)

    def on_free_resource_finished(self, status, msg, payloads):
        """
        释放资源完成
        :param status:
        :param msg:
        :param payloads:
        :return:
        """
        if status:
            QMessageBox.information(self, "提示", payloads)
        else:
            QMessageBox.critical(self, "错误", f"释放资源失败：{msg}")


class SemiAutomaticTaskPage(QWidget):
    """半自动任务页面"""

    def __init__(self):
        super().__init__()
        # 释放资源按钮
        self.btn_free = None
        # 全自动模式
        self.btn_switch_status = None
        # 运行模式：1-全自动，2-半自动
        self.run_mode = 2
        # 开启批次运行按钮
        self.btn_startup: Optional[QPushButton] = None
        # 启动按钮
        self.btn_run_monitor: Optional[QPushButton] = None
        # 表格
        self.tbl_task_batch: Optional[UITaskBatch] = None
        # 异步任务执行器
        self.async_task_executor: AsyncTaskScheduler = AsyncTaskScheduler()
        # 任务管理器
        self.task_manager = TaskManager(LOG)
        # 激活管理器
        self.activation_manager = ActivationManager()
        self.activation_manager.activation_status_changed.connect(self.on_activation_status_changed)
        # 初始化UI
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout()
        ##### 按钮区域 #####
        ly_buttons = QHBoxLayout()
        self.btn_startup = QPushButton("启动任务")
        self.btn_switch_status = QPushButton("开启监控")
        self.btn_free = QPushButton("释放资源")
        ly_buttons.addWidget(self.btn_startup)
        ly_buttons.addWidget(self.btn_switch_status)
        ly_buttons.addWidget(self.btn_free)

        self.btn_startup.clicked.connect(self.on_startup_clicked)
        self.btn_switch_status.clicked.connect(self.on_switch_status)
        self.btn_free.clicked.connect(self.on_free_resource)
        self.btn_switch_status.setEnabled(False)
        ##### 表格区域 #####
        self.tbl_task_batch = UITaskBatch(self.run_mode)

        ##### 添加到主布局 #####
        main_layout.addLayout(ly_buttons)
        main_layout.addWidget(self.tbl_task_batch)
        self.setLayout(main_layout)

    def on_activation_status_changed(self, status, msg):
        self.btn_startup.setEnabled(status)

    def on_switch_status(self):
        """
        开始运行
        :return:
        """
        rows = self.tbl_task_batch.get_selected_rows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择任务批次")
            return

        if self.btn_switch_status.text() == "开启监控":
            self.btn_switch_status.setText("暂停监控")
            # 继续
            for row in rows:
                batch_no = row.get("batch_no")
                self.task_manager.resume_task(batch_no)
        elif self.btn_switch_status.text() == "暂停监控":
            self.btn_switch_status.setText("开启监控")
            # 暂停
            for row in rows:
                batch_no = row.get("batch_no")
                self.task_manager.pause_task(batch_no)

    def has_running_task(self) -> bool:
        return self.task_manager.is_running

    def on_free_resource(self):
        """
        释放资源
        :return:
        """
        rows = self.tbl_task_batch.get_selected_rows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要释放的批次")
            return
        else:
            val = QMessageBox.warning(self, "提示", "请确认是否要释放资源？", QMessageBox.Yes | QMessageBox.No)
            if val != QMessageBox.Yes:
                return

            batch_nos = [row.get("batch_no") for row in rows]
            self.async_task_executor.submit_task(self.task_manager.free_resource, batch_nos,
                                                 finished_callback=self.on_free_resource_finished)

    def on_free_resource_finished(self, status, msg, payloads):
        """
        释放资源完成
        :param status:
        :param msg:
        :param payloads:
        :return:
        """
        if status:
            QMessageBox.information(self, "提示", payloads)
        else:
            QMessageBox.critical(self, "错误", f"释放资源失败：{msg}")

    # def on_run_monitor_clicked(self):
    #     """
    #     运行监控
    #     :return:
    #     """
    #     # 1.校验
    #     rows = self.tbl_task_batch.get_selected_rows()
    #     if not rows:
    #         QMessageBox.warning(self, "提示", "请选择任务批次")
    #         return
    #
    #     for row in rows:
    #         batch_no = row.get("batch_no")
    #         self.task_manager.pause_task(batch_no)

    def on_startup_clicked(self):
        """
        运行任务
        :return:
        """
        rows = self.tbl_task_batch.get_selected_rows()
        if not rows:
            QMessageBox.warning(self, "提示", "请选择要运行的批次")
            return
        batch_ids = [row.get("id") for row in rows]
        # 异步查询后执行批次
        self.async_task_executor.submit_task(self.start_task_batches, batch_ids,
                                             finished_callback=self.on_startup_task_batches)

    def start_task_batches(self, batch_ids):
        """
        异步运行任务
        :param batch_ids: 批次ID列表
        :return:
        """
        try:
            task_batches = []
            for batch_id in batch_ids:
                task_batch = db.task_batch_dao.get_by_id(batch_id)
                if not task_batch:
                    LOG.error(f"未找到任务批次，任务批次ID：{batch_id}")
                    continue
                task_batches.append(task_batch)
            if not task_batches:
                LOG.error("任务批次不存在！无法运行！")
                return False, "任务批次不存在！无法运行！"

            if task_batches:
                action_id = db.action_dao.add_one(
                    {"batch_ids": ",".join([str(task_batch.get("id")) for task_batch in task_batches])})
                for task_batch in task_batches:
                    db.task_batch_dao.update_by_id(task_batch.get("id"), {"action_id": action_id})
                    task_batch["action_id"] = action_id
            LOG.info(f"准备初始化任务管理器...")
            # 启动任务
            self.task_manager.start_task(task_batches)
            LOG.info(f"启动任务批次成功...")
            return True, "成功"
        except Exception as e:
            LOG.exception(f"启动任务批次失败：{str(e)}")
            return False, str(e)

    def on_startup_task_batches(self, status, msg, payloads):
        LOG.debug(f"任务批次启动结果：{status}，{msg}，{payloads}")
        if status:
            if not payloads[0]:
                QMessageBox.critical(self, "错误", f"任务启动失败：{payloads[1]}")
            else:
                self.btn_startup.setEnabled(False)  # 运行按钮不可点击
                QMessageBox.information(self, "提示", "任务启动成功，具体请查看运行日志！")
        else:
            QMessageBox.critical(self, "错误", f"任务启动失败：{msg}")


class UIExecuteTask(BaseTabWidget):
    """执行任务页面"""

    def __init__(self):
        self.running_status = False
        self.full_automation_task_page: Optional[FullAutomaticTaskPage] = None
        self.semi_automation_task_page: Optional[SemiAutomaticTaskPage] = None
        super().__init__()
        self.setStyleSheet(self.STYLE_MODERN)

    def add_tab_widgets(self) -> List[TabWidgetInfo]:
        self.full_automation_task_page = FullAutomaticTaskPage()
        self.semi_automation_task_page = SemiAutomaticTaskPage()
        return [TabWidgetInfo("全自动", self.full_automation_task_page),
                TabWidgetInfo("半自动", self.semi_automation_task_page)
                ]

    def has_running_task(self):
        return self.semi_automation_task_page.has_running_task() or self.full_automation_task_page.has_running_task()
