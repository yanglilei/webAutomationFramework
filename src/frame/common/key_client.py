import base64
import datetime
import decimal
import json
import os
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum
from typing import Tuple, Union, List, Optional

import requests
from dataclass_wizard import fromdict

from src.frame.common.constants import ActivateStatus
from src.frame.common.qt_log_redirector import LOG
from src.utils.crypto_utils import TripleDESCryptor
from src.utils.rsa_key_utils import RSAKeyUtils
from src.utils.sys_path_utils import SysPathUtils


class KeyClientConfig:
    SERVER_URL = "https://mm.budiaohua.com:28092"
    # SERVER_URL = "http://127.0.0.1:5000"
    PRODUCT_CODE = ""
    # MACHINE_ID = HardwareFingerprint("sdf*(*1234_)_(^%$%$2135sdf(**^%%$!@#%$%&^(*()^%#$").generate_fingerprint()[0]
    MACHINE_ID = ""
    LICENSE_FILE = os.path.join(SysPathUtils.get_data_file_dir(), f".license_receipt")
    if not os.path.exists(SysPathUtils.get_data_file_dir()):
        os.makedirs(SysPathUtils.get_data_file_dir())
    # DB_FILE = os.path.join(os.getcwd(), f".{PRODUCT_CODE}_lic.db")
    PUBLIC_KEY_PATH = os.path.join(SysPathUtils.get_config_file_dir(), "public_key.pem")  # 从服务器获取的公钥


class KeyError(Exception):
    """激活码相关错误"""

    def __init__(self, msg):
        self.msg = msg


@dataclass
class KeyReceipt:
    # 许可证票据
    product_code: str  # 产品编号
    key_value: str  # 秘钥数据
    machine_id: str  # 机器ID
    issue_time: str  # 发布时间
    expiry_time: str  # 过期时间
    signature: str  # 签名


@dataclass
class KeyData:
    # 许可证数据
    key_id: str  # 密钥ID
    product_code: str  # 产品编码
    user_id: str  # 用户ID
    nonce: str  # 随机数


class KeyReceiptStatus(Enum):
    INVALID_KEY = "无效的秘钥信息"
    INVALID_MACHINE_ID = "激活码与此机器不匹配"
    INVALID_PRODUCT_CODE = "许可证不匹配此产品"
    EXPIRED = "秘钥已过期"
    MISSING_FILE = "缺失秘钥文件"
    READ_ERROR = "读取秘钥文件失败"
    SUCCESS = 100


class KeyClient:
    def __init__(self, config: KeyClientConfig):
        self.config: KeyClientConfig = config
        # self._init_database()

    # def _init_database(self):
    #     """初始化本地数据库"""
    #     conn = sqlite3.connect(self.config.DB_FILE)
    #     c = conn.cursor()
    #     c.execute('''CREATE TABLE IF NOT EXISTS key
    #                  (id INTEGER PRIMARY KEY,
    #                  key_receipt TEXT,
    #                  last_verified TEXT,
    #                  status TEXT)''')
    #     conn.commit()
    #     conn.close()

    def activate(self, key_data, username="", email=""):
        """
        激活软件
        :param key_data: 激活码数据
        :param username: 用户名，暂无用到
        :param email: 邮箱，暂无用到
        :return:
        """
        try:
            payload = {
                "product_code": self.config.PRODUCT_CODE,
                "key_value": key_data,
                "machine_id": self.config.MACHINE_ID,
                # "username": username,
                # "email": email
            }

            response = requests.post(f"{self.config.SERVER_URL}/api/key/activate", json=payload)

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == "0000":
                    key_receipt_str = result.get("data").get("body")[0].get("key_receipt")
                    try:
                        # 验证激活码回执
                        status, key_receipt = self._verify_key_receipt(self.config.PUBLIC_KEY_PATH,
                                                                       key_receipt_str)
                        if status != KeyReceiptStatus.SUCCESS:
                            return False, status.value
                        # 保存激活码文件
                        self._save_key(key_receipt_str)
                        # 获取到激活码到期时间
                        return True, key_receipt.expiry_time
                    except KeyError as e:
                        return False, e.msg
                    except:
                        # TODO 写入日志
                        LOG.exception("激活码回执签名验证失败: ")
                        return False, "激活码回执签名验证失败"
                else:
                    return False, result.get("msg", "激活失败")
            else:
                return False, f"服务器错误: {response.status_code}"
        except Exception as e:
            return False, f"请求错误: {str(e)}"

    def _save_key(self, key_receipt):
        """保存激活码数据到本地文件和数据库"""
        try:
            # 保存到文件
            with open(self.config.LICENSE_FILE, "w") as f:
                f.write(key_receipt)

            # 保存到数据库
            # conn = sqlite3.connect(self.config.DB_FILE)
            # c = conn.cursor()
            # timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            # c.execute("INSERT INTO key (key_receipt, last_verified, status) VALUES (?, ?, ?)",
            #           (key_receipt, timestamp, "active"))
            # conn.commit()
            # conn.close()
        except Exception as e:
            raise KeyError(f"保存激活码失败: {str(e)}")

    def _verify_key_receipt(self, public_key_path, key_receipt: str) -> Tuple[KeyReceiptStatus, Optional[KeyReceipt]]:
        """
        验证激活码回执
        :param public_key_path: 公钥文件路径
        :param key_receipt: 激活码回执
        :return: KeyReceipt 激活码回执对象
        """
        try:
            ret = self.analyze_key_receipt(public_key_path, key_receipt)
            # 检查产品编号
            if ret.product_code != self.config.PRODUCT_CODE:
                LOG.error("许可证不匹配此产品")
                return KeyReceiptStatus.INVALID_PRODUCT_CODE, None

            # 检查机器ID
            if ret.machine_id != self.config.MACHINE_ID:
                LOG.error("激活码与此机器不匹配")
                return KeyReceiptStatus.INVALID_MACHINE_ID, None

            # 检查过期日期
            expiry_time = datetime.datetime.strptime(ret.expiry_time, "%Y-%m-%d %H:%M:%S")
            if datetime.datetime.utcnow() > expiry_time:
                # raise KeyError("激活码已过期")
                LOG.error("激活码已过期")
                return KeyReceiptStatus.EXPIRED, None

            return KeyReceiptStatus.SUCCESS, ret
        except:
            # raise KeyError(f"激活码回执验证失败: {str(e)}")
            LOG.exception("激活码回执验证失败: ")
            return KeyReceiptStatus.INVALID_KEY, None

    @staticmethod
    def analyze_key_receipt(public_key_path, key_receipt: str) -> KeyReceipt:
        # 解析激活码数据
        key_obj = json.loads(base64.b64decode(key_receipt).decode())
        # 检查激活码格式
        required_fields = ["product_code", "key_value", "machine_id", "issue_time", "expiry_time", "signature"]
        for field in required_fields:
            if field not in key_obj:
                raise KeyError("无效的激活码格式")
        data_to_verify = {
            k: key_obj[k] for k in
            ['product_code', 'key_value', 'machine_id', "issue_time", 'expiry_time']
        }
        
        RSAKeyUtils.verify_by_public_key(public_key_path, data_to_verify, key_obj["signature"])

        # 转换成LicenseReceipt对象
        return fromdict(KeyReceipt, key_obj)

    @staticmethod
    def analyze_key(public_key_path, key_value: str) -> Tuple[bool, Union[str, dict]]:
        """
        验证激活码的有效性
        :param key_value: 激活码
        :return: tuple(bool, Union[str, dict])
        """
        try:
            # 分割数据和签名
            data_part, signature_part = key_value.split('.', 1)
            key_val = RSAKeyUtils.verify_signature(public_key_path, data_part, signature_part)
            return True, json.loads(key_val)
        except Exception as e:
            LOG.exception("验证失败：")
            return False, f"验证失败: {str(e)}"

    def verify(self, online_check=True) -> Tuple[ActivateStatus, str]:
        """验证激活码回执的有效性"""
        # 先检查本地激活码回执文件
        status, obj = self._local_verify_key_receipt()
        if status:
            # 在线验证
            if online_check:
                status, msg = self._online_verify(obj)
                if not status:
                    LOG.error(f"{msg}")
                    if "激活码已过期" in msg:
                        return ActivateStatus.EXPIRED, "激活码已过期"
                    else:
                        return ActivateStatus.NOT_ACTIVATED, msg

            return ActivateStatus.ACTIVATED, obj.expiry_time
        else:
            if obj == KeyReceiptStatus.EXPIRED:
                return ActivateStatus.EXPIRED, obj.value
            else:
                return ActivateStatus.NOT_ACTIVATED, obj.value

    def _local_verify_key_receipt(self) -> Tuple[bool, Union[KeyReceiptStatus, KeyReceipt]]:
        # 先检查本地激活码文件
        if not os.path.exists(self.config.LICENSE_FILE):
            LOG.error("未找到激活码回执文件")
            return False, KeyReceiptStatus.MISSING_FILE

        try:
            with open(self.config.LICENSE_FILE, "r") as f:
                key_receipt_str = f.read()
        except Exception as e:
            LOG.exception("读取激活码回执失败")
            return False, KeyReceiptStatus.READ_ERROR

        # 验证证书回执
        status, key_receipt = self._verify_key_receipt(self.config.PUBLIC_KEY_PATH,
                                                       key_receipt_str)
        if status != KeyReceiptStatus.SUCCESS:
            return False, status
        else:
            return True, key_receipt

    def _online_verify(self, key_receipt: KeyReceipt):
        """在线验证激活码"""
        try:
            payload = {
                "product_code": self.config.PRODUCT_CODE,
                "key_value": key_receipt.key_value,
                "machine_id": key_receipt.machine_id
            }

            response = requests.post(f"{self.config.SERVER_URL}/api/key/verify", json=payload)

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == "0000":
                    # 更新本地激活码数据
                    # new_key_value = result.get("key_receipt")
                    # if new_key_value:
                    #     self._save_key(new_key_value)

                    # 更新本地验证时间
                    # conn = sqlite3.connect(self.config.DB_FILE)
                    # c = conn.cursor()
                    # timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    # c.execute("UPDATE key SET last_verified = ?, status = ? WHERE key_receipt = ?",
                    #           (timestamp, "valid", json.dumps(key_obj)))
                    # conn.commit()
                    # conn.close()

                    return True, "在线验证成功"
                else:
                    return False, result.get("msg", "在线验证失败")
            else:
                # 在线验证失败，但使用本地激活码
                print("在线验证服务器不可用，使用本地激活码")
                return True, "本地激活码有效（在线验证服务器不可用）"

        except Exception as e:
            LOG.exception(f"远程验证服务器不可用")
            return True, "本地激活码有效（远程验证服务器不可用）"

    def renew(self, new_key_value: str) -> Tuple[bool, str]:
        """
        续期
        :param new_key_value: 新的激活码
        :return:
        """
        # 获取当前激活码
        old_key_value = self._get_current_key_value()
        if not old_key_value:
            # raise KeyError("未找到现有激活码")
            return False, "未找到现有激活码信息"

        if new_key_value == old_key_value:
            LOG.error("新激活码与旧激活码相同，存在使用同一个激活码去续期的情况！")
            return False, "激活码已使用"

        try:
            payload = {
                "product_code": self.config.PRODUCT_CODE,
                "old_key_value": old_key_value,
                "new_key_value": new_key_value,
                "machine_id": self.config.MACHINE_ID
            }
            response = requests.post(f"{self.config.SERVER_URL}/api/key/renew", json=payload)

            if response.status_code == 200:
                result = response.json()
                if result.get("code") == "0000":
                    key_receipt_str = result.get("data").get("body")[0].get("key_receipt")
                    try:
                        # 验证证书回执
                        status, key_receipt = self._verify_key_receipt(self.config.PUBLIC_KEY_PATH,
                                                                       key_receipt_str)
                        if not status:
                            LOG.error("激活码回执验证失败")
                            return False, status.value
                        # 保存激活码文件
                        self._save_key(key_receipt_str)
                        # 获取到激活码到期时间
                        return True, key_receipt.expiry_time
                    except:
                        LOG.exception("激活码校验失败: ")
                        return False, "激活码校验失败"
                else:
                    return False, result.get("msg", "续期失败")
            else:
                return False, f"服务器错误: {response.status_code}"
        except Exception as e:
            LOG.exception("续期失败: ")
            return False, f"续期发生意外错误"

    def _get_current_key_value(self):
        # 获取当前激活码
        if not os.path.exists(self.config.LICENSE_FILE):
            return None

        try:
            with open(self.config.LICENSE_FILE, "r") as f:
                key_receipt = f.read()

            key_obj = json.loads(base64.b64decode(key_receipt).decode())
            return key_obj.get("key_value")
        except:
            return None

    def get_key_info(self):
        """
        获取当前激活码信息
        :return:
        """
        if not os.path.exists(self.config.LICENSE_FILE):
            return False, "缺失激活码信息文件"

        try:
            with open(self.config.LICENSE_FILE, "r") as f:
                key_data = f.read()

            key_obj = json.loads(base64.b64decode(key_data).decode())

            # 计算剩余天数
            expiry_time = datetime.datetime.strptime(key_obj["expiry_time"], "%Y-%m-%d %H:%M:%S")
            remaining_days = Decimal(
                (expiry_time - datetime.datetime.utcnow()).total_seconds() / (24 * 60 * 60)).quantize(Decimal('0.0001'),
                                                                                                      rounding=decimal.ROUND_DOWN)

            return True, {
                "key_value": key_obj["key_value"],
                "product_code": key_obj["product_code"],
                "expiry_time": key_obj["expiry_time"],
                "remaining_days": float(remaining_days),
                "is_valid": remaining_days > 0,
                "machine_id": key_obj["machine_id"]
            }
        except Exception as e:
            LOG.exception(f"获取激活码信息失败: ")
            return False, f"获取激活码信息失败"

    def revoke(self, username="", email=""):
        """
        吊销
        :param username: 用户名，暂无用到
        :param email: 邮箱，暂无用到
        :return:
        """
        payload = {
            "product_code": self.config.PRODUCT_CODE,
            "machine_id": self.config.MACHINE_ID,
            # "username": username,
            # "email": email
        }

        status, obj = self._local_verify_key_receipt()
        if status:
            try:
                payload["key_value"] = obj.key_value
                response = requests.post(f"{self.config.SERVER_URL}/api/key/revoke", json=payload)
                if response.status_code == 200:
                    result = response.json()
                    if result.get("code") == "0000":
                        # 吊销成功
                        return True, "吊销成功"
                    else:
                        return False, result.get("msg", "吊销失败")
                else:
                    return False, f"服务器错误: {response.status_code}"
            except Exception as e:
                return False, f"请求错误: {str(e)}"
        else:
            LOG.error(f"本地激活码回执验证失败：{obj.value}")
            return False, obj.value

    def revoke_keys(self, key_ids: List[str], acct_info, remark=""):
        """
        吊销多个激活码
        :param key_ids: 激活码列表
        :param acct_info: 账户信息
        :param remark: 备注信息
        :return:
        """
        try:
            payload = {"key_ids": key_ids, "acct_info": acct_info, "remark": remark}
            response = requests.post(f"{self.config.SERVER_URL}/api/key/batch_revoke", json=payload)
            if response.status_code == 200:
                result = response.json()
                if result.get("code") == "0000":
                    # 吊销成功
                    return True, "批量吊销成功"
                else:
                    return False, result.get("msg", "批量吊销失败")
            else:
                return False, f"服务器错误: {response.status_code}"
        except Exception as e:
            return False, f"请求错误: {str(e)}"

    def create(self, acct_info: str, expiry_days=1):
        # # 1. 获取管理员令牌
        # status, admin_token = self._get_admin_token(username, password)
        # if not status:
        #     return False, "获取管理员访问令牌失败"
        #
        # # 2. 创建产品
        # flag = self._create_product(admin_token)
        # if not flag:
        #     return False, "创建产品失败"
        #
        # # 3. 创建初始激活码
        # status, key = self._create_key(admin_token, expiry_days)
        # if not status:
        #     return False, "创建激活码失败"
        # else:
        #     return True, key

        # acct_info = ConfigFileReader.get_val(Constants.ConfigFileKey.KM_ACCOUNT, ConfigFileReader.busi_section_name)
        status, key = self._quick_create_key(acct_info, expiry_days)
        if not status:
            return False, "创建激活码失败"
        else:
            return True, key

    def _get_admin_token(self, username, password) -> Tuple[bool, str]:
        """获取管理员访问令牌"""
        try:
            url = f"{self.config.SERVER_URL}/api/admin/login"
            payload = {
                "username": username,
                "password": password
            }

            response = requests.post(url, json=payload)
            if response.status_code == 200:
                code = response.json().get("code")
                msg = response.json().get("msg")
                if code == "0000":
                    LOG.info(f"管理员 {username} 登录成功")
                    return True, response.json().get("data").get("body")[0].get("access_token")
                else:
                    LOG.error(f"管理员登录失败: {code}-{msg}")
                    return False, msg
            else:
                LOG.error(f"管理员登录失败，服务器错误: {response.status_code}")
                return False, "服务器错误"
        except:
            LOG.exception("获取管理员访问令牌失败: ")
            return False, "未知异常"

    def _create_product(self, token) -> bool:
        """创建产品"""
        ret = False
        try:
            url = f"{self.config.SERVER_URL}/api/admin/products"
            headers = {"Authorization": f"Bearer {token}"}
            payload = {
                "name": self.config.PRODUCT_CODE,
                "code": self.config.PRODUCT_CODE,
                "description": ""
            }

            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                code = response.json().get("code")
                msg = response.json().get("msg")
                if code == "0000" or "产品编号已存在" in msg:
                    LOG.info(f"产品【{self.config.PRODUCT_CODE}】创建成功！")
                    ret = True
                else:
                    LOG.error(f"产品 {self.config.PRODUCT_CODE} 创建失败: {code}-{response.json().get('msg')}")
            else:
                LOG.error(f"产品 {self.config.PRODUCT_CODE} 创建失败，服务器错误：{response.status_code}")
        except:
            LOG.exception(f"产品 {self.config.PRODUCT_CODE} 创建失败")

        return ret

    def _create_key(self, token, expiry_days=30) -> Tuple[bool, str]:
        """创建激活码"""
        try:
            url = f"{self.config.SERVER_URL}/api/key/add"
            headers = {"Authorization": f"Bearer {token}"}
            payload = {
                "product_code": self.config.PRODUCT_CODE,
                "machine_id": self.config.MACHINE_ID,
                "expiry_days": expiry_days,
            }
            response = requests.post(url, headers=headers, json=payload)
            if response.status_code == 200:
                code = response.json().get("code")
                msg = response.json().get("msg")
                if code == "0000":
                    data = response.json().get("data").get("body")[0]
                    key_value = data.get("key_value")
                    expiry_days = data.get("expiry_days")
                    LOG.info(f"激活码创建成功，有效期{expiry_days}天：{key_value}")
                    return True, key_value
                else:
                    LOG.error(f"创建激活码失败: {code}-{msg}")
                    return False, msg
            else:
                LOG.error(f"创建激活码失败，服务器错误: {response.status_code}")
                return False, "服务器错误"
        except:
            LOG.exception(f"创建激活码失败: ")
            return False, "未知异常"

    def _quick_create_key(self, acct_info, expiry_days=30) -> Tuple[bool, str]:
        """创建激活码"""
        try:
            account = TripleDESCryptor("12*1743d)()*&^(@").decrypt(acct_info)
            account = account.split(";")
        except:
            LOG.exception(f"解析账号信息失败：")
            return False, "解析账号信息失败"

        try:
            url = f"{self.config.SERVER_URL}/api/admin/key/quick_add"

            payload = {
                "acct_info": acct_info,
                "product_code": self.config.PRODUCT_CODE,
                "machine_id": self.config.MACHINE_ID,
                "expiry_days": expiry_days,
            }
            response = requests.post(url, json=payload)
            if response.status_code == 200:
                code = response.json().get("code")
                msg = response.json().get("msg")
                if code == "0000":
                    data = response.json().get("data").get("body")[0]
                    key_value = data.get("key_value")
                    expiry_days = data.get("expiry_days")
                    LOG.info(f"激活码创建成功，有效期{expiry_days}天：{key_value}")
                    return True, key_value
                else:
                    LOG.error(f"创建激活码失败: {code}-{msg}")
                    return False, msg
            else:
                LOG.error(f"创建激活码失败，服务器错误: {response.status_code}")
                return False, "服务器错误"
        except:
            LOG.exception(f"创建激活码失败: ")
            return False, "未知异常"

    def get_key_list(self, condition) -> Tuple[bool, Union[dict, str]]:
        """获取激活码列表"""
        # payload = {
        #     "status": status,
        #     "key_id": key_id,
        #     "product_code": product_code,
        #     "machine_id": machine_id,
        #     "page_num":
        # }
        url = f"{self.config.SERVER_URL}/api/key/list"
        try:
            response = requests.get(url, params=condition)
            if response.status_code == 200:
                code = response.json().get("code")
                msg = response.json().get("msg")
                if code == "0000":
                    data = response.json().get("data")
                    return True, data
                else:
                    LOG.error(f"获取激活码列表失败: {code}-{msg}")
                    return False, msg
            else:
                LOG.error(f"获取激活码列表失败，服务器错误: {response.status_code}")
                return False, "服务器错误"
        except:
            LOG.exception(f"获取激活码列表失败: ")
            return False, "未知异常"

    def export_keys(self, conditions: dict) -> Tuple[bool, Union[dict, str]]:
        """获取激活码列表"""
        url = f"{self.config.SERVER_URL}/api/key/export_keys"
        try:

            response = requests.post(url, json=conditions)
            if response.status_code == 200:
                code = response.json().get("code")
                msg = response.json().get("msg")
                if code == "0000":
                    data = response.json().get("data")
                    return True, data
                else:
                    LOG.error(f"获取激活码失败: {code}-{msg}")
                    return False, msg
            else:
                LOG.error(f"获取激活码失败，服务器错误: {response.status_code}")
                return False, "服务器错误"
        except:
            LOG.exception(f"获取激活码失败: ")
            return False, "未知异常"
