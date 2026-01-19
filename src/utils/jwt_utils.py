import uuid
from datetime import datetime, timedelta
from typing import Tuple

import jwt
import requests
from faker import Faker

from src.utils.crypto_utils import TripleDESCryptor


class JWTPayload:

    def __init__(self, app_name: str, mac_id: str, app_expired_days: float, exp=3):
        """
        初始化JWT实体类
        :param app_name: 应用名称
        :param mac_id: 软件的mac地址
        :param app_expired_days: 应用过期时间，从激活后开始计算，支持小数，单位：天
        :param exp: 秘钥过期时间，单位：天。默认为3，3天不使用秘钥则过期！
        """
        self.app_name = app_name
        self.mac_id = mac_id
        # 应用的过期时间，从激活后开始计算，单位：天
        self.app_expired_days = app_expired_days
        # 秘钥的过期时间（utc时间），计算出到期的时间戳，单位秒
        # 当前该字段的作用：秘钥若是超过3天未使用，则过期！若是使用了（激活了），则该时间也会更新为最新的过期时间！
        self.exp = datetime.utcnow() + timedelta(days=exp)
        # 秘钥的唯一标识
        self.unique_id = str(uuid.uuid4())
        # 发行方
        self.iss = "CRYPTO_MACHINE"
        # 发行时间，必须为数字的时间戳
        self.iat = int(datetime.now().timestamp())
        # 随机扰乱字符串
        self.random_str = Faker().pystr(128, 512)
        # 激活后的到期时间戳，单位秒
        self.expired_time = 0

    def to_json(self):
        return {
            "app_name": self.app_name,
            "mac_id": self.mac_id,
            "app_expired_days": self.app_expired_days,
            "exp": self.exp,
            "unique_id": self.unique_id,
            "iss": self.iss,
            "iat": self.iat,
            "random_str": self.random_str,
            "expired_time": self.expired_time
        }

    @classmethod
    def from_json(cls, json_data: dict):
        app_name = json_data.get("app_name")
        mac_id = json_data.get("mac_id")
        obj = cls(app_name, mac_id, json_data.get("app_expired_days"))
        obj.exp = json_data.get("exp")
        obj.unique_id = json_data.get("unique_id")
        obj.iss = json_data.get("iss")
        obj.iat = json_data.get("iat")
        obj.random_str = json_data.get("random_str")
        obj.expired_time = json_data.get("expired_time")
        return obj


class SignatureUtils:
    SECRET_KEY = "SDFLK23ls*^#kdfj9123()*^&$13)(12344_r123h871^1235^%$%^"
    # SERVER_URL = "http://wxapi.guanglizhubao.com:8090/check_id"
    SERVER_URL = "http://mm.budiaohua.com:28091/check_id"
    ALGORITHM = "HS256"
    TRIPLE_DES_KEY = "12*1743d)()*&^(@"

    @classmethod
    def generate_activation_key(cls, app_name="", mac_id="", days=1.0, jwt_payload: JWTPayload = None):
        # 构建 JWT 负载，包含过期时间和唯一标识
        if jwt_payload is None:
            payload = JWTPayload(app_name, mac_id, days)
        else:
            payload = jwt_payload
        # 生成 JWT 秘钥
        return jwt.encode(payload.to_json(), key=cls.SECRET_KEY, algorithm=cls.ALGORITHM)

    @classmethod
    def verify_activation_key(cls, app_name, mac_id, activation_key, remote_verify=True) -> Tuple[
        bool, str, JWTPayload]:
        """
        验证秘钥
        :param app_name: 软件名称
        :param mac_id: mac id
        :param activation_key: 秘钥
        :param remote_verify: True-远程验证（默认）；False-本地验证；在激活软件时必须要远程验证！
        :return:
        """
        status = True
        fail_reason = ""
        jwt_payload = None
        try:
            # 解析 JWT 密钥
            jwt_payload = jwt.decode(activation_key, key=cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
            jwt_payload = JWTPayload.from_json(jwt_payload)
            if jwt_payload.iss != "CRYPTO_MACHINE":
                # 写日志，解析失败，发行方不对
                status = False
                # fail_reason = "发行方有误"
                fail_reason = "激活失败"
            elif jwt_payload.app_expired_days <= 0:
                # 写日志，应用已过期
                status = False
                # fail_reason = "应用已过期"
                fail_reason = "激活失败"
            # 请求远程服务器，验证密钥
            elif app_name == jwt_payload.app_name and mac_id == jwt_payload.mac_id:
                if remote_verify:
                    # 请求远程服务器，验证密钥
                    headers = {"Content-Type": "application/json; charset=utf-8"}
                    # 报文加密
                    encrypt_body = TripleDESCryptor(cls.TRIPLE_DES_KEY).encrypt(f"unique_id={jwt_payload.unique_id}")
                    response = requests.post(cls.SERVER_URL, json={"body": encrypt_body}, headers=headers, timeout=5)
                    if response.status_code == 200:
                        key_status = response.json().get("status")
                        if key_status:
                            status = True
                            fail_reason = ""
                        else:
                            status = False
                            fail_reason = "秘钥已使用！"
                    else:
                        # TODO 写日志，所有地方都要补充好日志！
                        status = False
                        # fail_reason = "远程服务器验证失败"
                        fail_reason = "激活失败"
            else:
                # 激活失败，写日志！
                status = False
                fail_reason = "激活失败"
        except jwt.ExpiredSignatureError:
            # 写日志，密钥过期
            status = False
            fail_reason = "密钥已过期"
        except jwt.InvalidTokenError as e:
            # 无效的密钥，写日志！
            print(e)
            status = False
            fail_reason = "激活失败"
        except Exception as e:
            # 其他错误，写日志！
            status = False
            fail_reason = "激活失败"

        return status, fail_reason, jwt_payload


if __name__ == '__main__':

    # utc_now = datetime.utcnow()
    # cur_now = datetime.now()
    # print(utc_now)
    # print(cur_now)
    #
    # utc_ts = int((datetime.utcnow() + timedelta(days=0.1)).timestamp())
    # cur_ts = int((datetime.now() + timedelta(days=0.1)).timestamp())
    #
    # print(utc_ts)
    # print(cur_ts)
    # style = "stroke-dasharray: 282.743px, 282.743px; stroke-dashoffset: 0px; transition: stroke-dashoffset 0.6s ease 0s, stroke 0.6s ease 0s;"
    # print(re.findall("stroke-dashoffset:(.*)px", style))
    SECRET_KEY = "SDFLK23ls*^#kdfj9123()*^&$13)(12344_r123h871^1235^%$%^"
    # SERVER_URL = "http://wxapi.guanglizhubao.com:8090/check_id"
    SERVER_URL = "http://mm.budiaohua.com:28091/check_id"
    ALGORITHM = "HS256"
    TRIPLE_DES_KEY = "12*1743d)()*&^(@"
    headers = {"Content-Type": "application/json; charset=utf-8"}
    # 报文加密
    encrypt_body = TripleDESCryptor(TRIPLE_DES_KEY).encrypt(f"unique_id=3")
    response = requests.post(SERVER_URL, json={"body": encrypt_body}, headers=headers, timeout=5)
    if response.status_code == 200:
        key_status = response.json().get("status")
        if key_status:
            status = True
            fail_reason = ""
        else:
            status = False
            fail_reason = "秘钥已使用！"
    else:
        # TODO 写日志，所有地方都要补充好日志！
        status = False
        # fail_reason = "远程服务器验证失败"
        fail_reason = "激活失败"
