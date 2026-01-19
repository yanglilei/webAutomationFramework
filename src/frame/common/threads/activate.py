from datetime import datetime, timedelta

from PyQt5.QtCore import QThread, pyqtSignal

from src.frame.common.constants import Constants, ActivateStatus
from src.frame.common.qt_log_redirector import LOG
from src.frame.dao.db_manager import db
from src.utils.jwt_utils import SignatureUtils
from src.utils.sys_path_utils import SysPathUtils


class ActivateThread(QThread):
    activate_result_signal = pyqtSignal(ActivateStatus, str, str)
    startup_verify_signal = pyqtSignal(ActivateStatus, str, str)

    def __init__(self, parent, app_name, mac_id, current_activate_status=ActivateStatus.NOT_ACTIVATED,
                 activation_key="", expired_time=0, action=0):
        """
        初始化激活线程
        :param app_name: 应用名称
        :param mac_id: 识别码
        :param current_activate_status: 应用当前的激活状态
        :param activation_key: 激活秘钥
        :param expired_time: 应用的过期时间
        :param action: 动作。0-激活；1-启动软件验证秘钥
        """
        super().__init__(parent)
        self.app_name = app_name
        self.mac_id = mac_id
        self.current_activate_status = current_activate_status
        self.activation_key = activation_key
        self.expired_time = expired_time
        self.action = action

    def run(self):
        if self.action == 0:
            # 激活
            try:
                self.activate(self.app_name, self.mac_id, self.current_activate_status, self.activation_key,
                              self.expired_time)
            except:
                LOG.exception("激活出现异常，请重新启动软件！")
                self.activate_result_signal.emit(ActivateStatus.NOT_ACTIVATED, "0", "激活出现异常！")
        else:
            # 启动软件验证秘钥
            try:
                self.startup_verify_key(self.app_name, self.mac_id)
            except:
                LOG.exception("激活出现异常，请重新启动软件！")
                self.startup_verify_signal.emit(ActivateStatus.NOT_ACTIVATED, "0", "激活出现异常！")

    def activate(self, app_name: str, mac_id: str, current_activate_status: ActivateStatus, activation_key: str,
                 expired_time: int):
        """
        激活
        :param activation_key: 秘钥
        :return: Tuple[bool, str] (状态, 失败原因)
        """
        status, fail_reason, payload = SignatureUtils.verify_activation_key(app_name, mac_id, activation_key)
        if status:
            # 激活成功
            # 加上当前剩余的时间
            cur_remaining_time = 0
            if current_activate_status == ActivateStatus.ACTIVATED:
                # 计算当前剩余的时间，为了加上当前剩余的时间
                cur_remaining_time = expired_time - int(datetime.utcnow().timestamp())
                cur_remaining_time = cur_remaining_time if cur_remaining_time > 0 else 0
            # 更新激活状态
            db.data_dict_dao.update_by_key(Constants.ConfigFileKey.ACTIVATE_STATUS, ActivateStatus.ACTIVATED.value)
            # 设置过期时间，新的过期时间=当前时间+延长的时间+当前剩余的时间
            payload.expired_time = int(
                (datetime.utcnow() + timedelta(days=payload.app_expired_days)).timestamp()) + cur_remaining_time
            # 更新exp
            payload.exp = payload.expired_time
            # 产生新token
            new_key = SignatureUtils.generate_activation_key(jwt_payload=payload)
            # 秘钥写入文件
            with open(SysPathUtils.get_signature_file(), "w", encoding="utf-8") as f:
                f.write(new_key)

            self.activate_result_signal.emit(ActivateStatus.ACTIVATED, str(payload.expired_time), "")
        else:
            if "远程验证失败" in fail_reason:
                self.activate_result_signal.emit(ActivateStatus.REMOTE_VERIFY_FAILED, "0", fail_reason)
            else:
                self.activate_result_signal.emit(ActivateStatus.NOT_ACTIVATED, "0", fail_reason)

    def startup_verify_key(self, app_name: str, mac_id: str):
        # 读取签名文件
        with open(SysPathUtils.get_signature_file(), "r", encoding="utf-8") as f:
            activation_key = f.read()
        status, fail_reason, payload = SignatureUtils.verify_activation_key(app_name,
                                                                            mac_id,
                                                                            activation_key)
        if not status:
            if "秘钥已使用！" in fail_reason:
                # 此处逻辑比较特殊：由于先前激活的时候，秘钥肯定已远程验证！在此处再次验证时，必然返回秘钥已使用过！相应的status=False，且fail_reason=秘钥已使用过！
                # 所以status=False，且fail_reason=秘钥已使用！才是通过正常路径激活的秘钥！
                if payload.expired_time < int(datetime.utcnow().timestamp()):
                    # 过期了
                    self.startup_verify_signal.emit(ActivateStatus.EXPIRED, "0", "")
                else:
                    # 未过期
                    self.startup_verify_signal.emit(ActivateStatus.ACTIVATED, str(payload.expired_time), "")
            elif "密钥已过期" in fail_reason:
                # 已过期
                self.startup_verify_signal.emit(ActivateStatus.EXPIRED, "0", "")
            elif "远程验证失败" in fail_reason:
                # 远程验证失败
                self.startup_verify_signal.emit(ActivateStatus.REMOTE_VERIFY_FAILED, "0", fail_reason)
            else:
                # 激活失败，此种情况的发生，可能存在人为修改了秘钥
                self.startup_verify_signal.emit(ActivateStatus.NOT_ACTIVATED, "0", fail_reason)
        else:
            # 目前的逻辑，不存在此处为激活成功的可能，除非人为修改了秘钥文件！
            self.startup_verify_signal.emit(ActivateStatus.ACTIVATED, str(payload.expired_time), "")
