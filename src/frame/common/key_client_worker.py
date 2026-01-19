from enum import Enum
from typing import List

from PyQt5.QtCore import QThread, pyqtSignal

from src.frame.common.constants import ActivateStatus
from src.frame.common.key_client import KeyClientConfig, KeyClient


class KeyClientCommand(Enum):
    # 激活
    ACTIVATE = 0
    # 续期
    RENEWAL = 1
    # 验证
    VERIFY = 2
    # 吊销
    REVOKE = 3
    # 批量吊销
    BATCH_REVOKE = 4


class KeyWorkerParams:
    def __init__(self, cmd: KeyClientCommand, *args):
        self.cmd = cmd
        self.args = args


class KeyWorker(QThread):
    activate_finished = pyqtSignal(bool, str)
    renew_finished = pyqtSignal(bool, str)
    verify_finished = pyqtSignal(ActivateStatus, str)
    revoke_finished = pyqtSignal(bool, str)
    batch_revoke_finished = pyqtSignal(bool, str)

    def __init__(self, params: KeyWorkerParams):
        """
        初始化激活线程
        :param cmd: 指令
        :param product_code: 应用名称
        :param machine_id: 识别码
        :param key_data: 秘钥
        """
        super().__init__()
        self.params = params
        self.cmd = params.cmd

    def run(self):
        if self.cmd == KeyClientCommand.ACTIVATE:
            self.activate(*self.params.args)
        elif self.cmd == KeyClientCommand.RENEWAL:
            self.renew(*self.params.args)
        elif self.cmd == KeyClientCommand.REVOKE:
            self.revoke(*self.params.args)
        elif self.cmd == KeyClientCommand.VERIFY:
            self.verify(*self.params.args)
        elif self.cmd == KeyClientCommand.BATCH_REVOKE:
            self.batch_revoke(*self.params.args)
        # try:
        #     self.renewal(self.product_code, self.machine_id, self.activation_key)
        # except:
        #     LOG.exception("激活出现异常，请重新启动软件！")
        #     self.activate_result_signal.emit(ActivateStatus.NOT_ACTIVATED, "0", "激活出现异常！")

    def activate(self, product_code: str, machine_id: str, key_data: str):
        """
        激活
        :param product_code:  产品编号
        :param machine_id:  机器ID
        :param key_data: 秘钥数据
        :return:
        """
        config = KeyClientConfig()
        config.PRODUCT_CODE = product_code
        config.MACHINE_ID = machine_id
        client = KeyClient(config)
        status, msg = client.activate(key_data)
        self.activate_finished.emit(status, msg)

    def renew(self, product_code, machine_id, key_data: str):
        """
        续期
        :param product_code:  产品编号
        :param machine_id:  机器ID
        :param key_data: 新的秘钥数据
        :return: Tuple[bool, str] (状态, 失败原因)
        """
        config = KeyClientConfig()
        config.PRODUCT_CODE = product_code
        config.MACHINE_ID = machine_id
        client = KeyClient(config)
        status, msg = client.renew(key_data)
        self.renew_finished.emit(status, msg)

    def revoke(self, product_code, machine_id):
        config = KeyClientConfig()
        config.PRODUCT_CODE = product_code
        config.MACHINE_ID = machine_id
        status, msg = KeyClient(config).revoke()
        self.revoke_finished.emit(status, msg)

    def verify(self, product_code, machine_id):
        config = KeyClientConfig()
        config.PRODUCT_CODE = product_code
        config.MACHINE_ID = machine_id
        status, msg = KeyClient(config).verify(True)
        self.verify_finished.emit(status, msg)

    def batch_revoke(self, key_ids: List[str], acct_info, remark=""):
        status, msg = KeyClient(KeyClientConfig()).revoke_keys(key_ids, acct_info, remark)
        self.batch_revoke_finished.emit(status, msg)
