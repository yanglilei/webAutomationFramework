from datetime import datetime
from typing import Optional

from PyQt5.QtCore import pyqtSignal, QObject, QTimer

from src.frame.common.constants import ActivateStatus
from src.frame.common.decorator.singleton import singleton
from src.frame.common.key_client_worker import KeyWorker, KeyWorkerParams, KeyClientCommand
from src.frame.common.qt_log_redirector import LOG
from src.frame.dao.async_db_task_scheduler import AsyncTaskScheduler
from src.utils.hardware_finger_utils import HardwareFingerprint


@singleton
class ActivationManager(QObject):
    """激活状态管理类，负责激活验证、状态存储、有效期计算"""
    # 用于通知UI更新mac
    mac_get_success_signal = pyqtSignal(str)
    # 手动激活信号
    manual_activate_signal = pyqtSignal(bool, str)  # (是否激活成功, 描述信息)
    # 启动验证信号
    startup_verify_signal = pyqtSignal(bool, str)  # (是否激活, 剩余时间文本或描述信息)
    # 激活状态改变信号，可监听该信号用于更新激活的状态和时间
    activation_status_changed = pyqtSignal(bool, str)  # (是否激活, 剩余时间文本或描述信息)
    # 续期信号
    renew_signal = pyqtSignal(bool, str)
    # 吊销信号
    revoke_signal = pyqtSignal(bool, str)

    def __init__(self, parent=None, app_name: str = "", is_need_verify=True):
        super().__init__(parent)
        self.is_need_verify = is_need_verify  # 是否需要验证
        self.activate_worker = None  # 激活worker
        self.renew_worker = None  # 续期worker
        self.revoke_worker = None  # 吊销worker
        self.app_name = app_name  # 软件名称
        self.mac: Optional[str] = None  # mac值
        self.async_task_scheduler = AsyncTaskScheduler()  # 异步任务调度器
        self.timer: Optional[QTimer] = None  # 定时器
        self.activate_status = None  # 软件的激活状态
        self.expired_time = 0  # 过期时间，时间戳，单位秒
        # 获取mac
        self.get_mac()
        # 启动定时器
        self.start_timer()

    def get_mac(self):
        if self.is_need_verify:
            LOG.info("开始获取mac...")
            self.async_task_scheduler.submit_task(self._get_mac, finished_callback=self._handle_get_mac_success)

    def _get_mac(self):
        return HardwareFingerprint("sdf*(*1234_)_(^%$%$2135sdf(**^%%$!@#%$%&^(*()^%#$").generate_fingerprint()[0]

    def _handle_get_mac_success(self, status, msg, mac: str):
        if not status:
            self.activation_status_changed.emit(False, f"获取mac失败：{msg}")
            return
        LOG.info("获取mac成功！")
        # 通知UI更新mac
        self.mac = mac
        self.mac_get_success_signal.emit(mac)
        # 启动软件后激活
        self.async_task_scheduler.submit_task(self._verify_at_start)

    def activate(self, activation_key):
        """
        激活
        外部统一调用该方法实现软件激活
        :param activation_key: 秘钥
        :return:
        """
        self.activate_worker = KeyWorker(KeyWorkerParams(KeyClientCommand.ACTIVATE,
                                                         self.app_name,
                                                         self.mac,
                                                         activation_key))
        self.activate_worker.activate_finished.connect(self._activate_result_callback)
        self.activate_worker.start()

    def renewal(self, activation_key):
        """
        续期
        外部统一调用该方法实现软件续期
        :param activation_key: 秘钥
        :return:
        """
        self.renew_worker = KeyWorker(
            KeyWorkerParams(KeyClientCommand.RENEWAL, self.app_name, self.mac, activation_key))
        self.renew_worker.renew_finished.connect(self._renew_result_callback)
        self.renew_worker.start()

    def revoke(self):
        """
        吊销
        外部统一调用该方法实现软件吊销
        :return:
        """
        self.revoke_worker = KeyWorker(KeyWorkerParams(KeyClientCommand.REVOKE, self.app_name, self.mac))
        self.revoke_worker.revoke_finished.connect(self._revoke_result_callback)
        self.revoke_worker.start()

    def _activate_result_callback(self, status, msg):
        if status:  # 激活成功
            # 获取到期时间
            self.expired_time = int(datetime.strptime(msg, "%Y-%m-%d %H:%M:%S").timestamp())
            # 设置激活状态
            self.activate_status = ActivateStatus.ACTIVATED
            self.manual_activate_signal.emit(True, msg)
        else:  # 激活失败
            # 提示激活失败
            self.manual_activate_signal.emit(False, msg)

    def _renew_result_callback(self, status, msg):
        if status:  # 激活成功
            # 获取到期时间
            self.expired_time = int(datetime.strptime(msg, "%Y-%m-%d %H:%M:%S").timestamp())
            self.renew_signal.emit(True, "")
        else:  # 激活失败
            # 更新按钮状态
            # self.btn_active.setEnabled(False)
            # self.btn_renewal.setEnabled(True)
            # self.btn_revoke.setEnabled(True)
            self.renew_signal.emit(False, msg)
            # 提示续期失败
            # QMessageBox.information(self, "操作结果", f"续期失败：{msg}")

    def _revoke_result_callback(self, status, msg):
        if status:  # 吊销成功
            self.activate_status = ActivateStatus.NOT_ACTIVATED
            self.revoke_signal.emit(True, "")
        else:  # 吊销失败
            self.revoke_signal.emit(False, msg)

    def update_remaining_time(self):
        """计算剩余时间，并发送状态更新信号"""
        if not self.is_need_verify:
            # 不需要激活
            self.activation_status_changed.emit(True, "")
            return

        if not self.is_activate():
            self.activation_status_changed.emit(False, "")
            return

        now = int(datetime.utcnow().timestamp())
        if now >= self.expired_time:
            # 激活过期
            self.activate_status = ActivateStatus.EXPIRED
            self.expired_time = 0
            self.activation_status_changed.emit(False, "已过期，请续期！")
        else:
            # 计算剩余时间
            remaining = self.expired_time - now
            self.activation_status_changed.emit(True, self._timestamp_to_dhms(remaining))

    def _verify_at_start(self):
        """
        启动软件验证秘钥
        :return:
        """
        LOG.debug("启动软件验证秘钥...")
        self.verify_worker = KeyWorker(KeyWorkerParams(KeyClientCommand.VERIFY, self.app_name, self.mac))
        self.verify_worker.verify_finished.connect(self._startup_verify_result_callback)
        self.verify_worker.start()

    def start_timer(self):
        # 定时器：每秒更新剩余时间
        if not self.timer or not self.timer.isActive():
            self.timer = QTimer()
            self.timer.setInterval(1000)
            self.timer.timeout.connect(self.update_remaining_time)
            self.timer.start()

    def _startup_verify_result_callback(self, status: ActivateStatus, msg):
        LOG.debug("启动软件验证秘钥结束！")
        self.activate_status = status
        # 验证结果
        if self.activate_status == ActivateStatus.ACTIVATED:
            # 过期时间
            expired_ts = int(datetime.strptime(msg, "%Y-%m-%d %H:%M:%S").timestamp())
            # 更新软件的过期时间
            self.expired_time = expired_ts
            self.startup_verify_signal.emit(True, "")
        elif self.activate_status == ActivateStatus.NOT_ACTIVATED:
            self.startup_verify_signal.emit(False, msg)
        elif self.activate_status == ActivateStatus.EXPIRED:
            self.startup_verify_signal.emit(False, msg)
        else:
            LOG.error("激活失败：未知的激活状态")
            self.startup_verify_signal.emit(False, msg)

    def is_activate(self):
        return self.activate_status == ActivateStatus.ACTIVATED

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

# 全局唯一的激活管理器
# activation_manager = ActivationManager(QApplication.instance(), constants.APP_NAME, constants.IS_NEED_ACTIVATION)
