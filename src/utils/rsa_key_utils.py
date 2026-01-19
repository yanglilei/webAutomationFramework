import base64
import json

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding


class RSAKeyUtils:
    @classmethod
    def load_public_key(cls, public_key_path: str):
        """加载公钥"""
        try:
            with open(public_key_path, 'rb') as key_file:
                public_key = serialization.load_pem_public_key(
                    key_file.read(),
                    backend=default_backend()
                )
            return public_key
        except Exception as e:
            print(f"Error loading public key: {e}")
            return None

    @classmethod
    def verify_by_public_key(cls, public_key_path, data: dict, signature):
        """
        公钥验证签名，返回明文数据
        :param public_key_path: 公钥文件路径
        :param data: 数据
        :param signature:  签名
        :return: 明文数据
        """
        # 验证签名
        data_bytes = json.dumps(data, sort_keys=True).encode()
        # data_bytes = base64.urlsafe_b64decode(key_value)
        signature_bytes = base64.urlsafe_b64decode(signature)

        # 使用公钥验证签名
        public_key = cls.load_public_key(public_key_path)
        public_key.verify(
            signature_bytes,
            data_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )

    @classmethod
    def verify_signature(cls, public_key_path, key_value, signature) -> bytes:
        """
        验证签名，返回明文数据
        :param key_value: 数据
        :param signature:  签名
        :return: 明文数据
        """
        data_bytes = base64.urlsafe_b64decode(key_value)
        signature_bytes = base64.urlsafe_b64decode(signature)

        # 使用公钥验证签名
        public_key = cls.load_public_key(public_key_path)
        public_key.verify(
            signature_bytes,
            data_bytes,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        return data_bytes
        # return json.loads(data_bytes)
        # 解析许可证数据
        # return fromdict(KeyValue, json.loads(data_bytes))
