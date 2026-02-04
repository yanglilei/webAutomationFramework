import base64
import uuid
from base64 import b64encode, b64decode

from Crypto import Random
from Crypto.Cipher import AES
from Crypto.Cipher import DES3
from Crypto.Cipher import PKCS1_v1_5 as Cipher_PKC
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5 as Signature_PKC
from Crypto.Util.Padding import pad, unpad


class MACUtils:

    # @staticmethod
    # def get_mac_address():
    #     mac = uuid.UUID(int=uuid.getnode()).hex[-12:]
    #     return "-".join([mac[e:e + 2] for e in range(0, 11, 2)]).upper()

    @staticmethod
    def get_mac_address():
        node = uuid.getnode()
        mac = uuid.UUID(int=node).hex[-12:]
        return mac


class RSAUtils:

    @classmethod
    def create_rsa_key(cls):
        """
        创建RSA密钥
        步骤说明：
        1、从 Crypto.PublicKey 包中导入 RSA，创建一个密码
        2、生成 1024/2048 位的 RSA 密钥
        3、调用 RSA 密钥实例的 exportKey 方法，传入密码、使用的 PKCS 标准以及加密方案这三个参数。
        4、将私钥写入磁盘的文件。
        5、使用方法链调用 publickey 和 exportKey 方法生成公钥，写入磁盘上的文件。
        """

        # 伪随机数生成器
        random_gen = Random.new().read
        # 生成秘钥对实例对象：1024是秘钥的长度
        rsa = RSA.generate(1024, random_gen)

        # Server的秘钥对的生成
        private_pem = rsa.exportKey()
        with open("server_private.pem", "wb") as f:
            f.write(private_pem)

        public_pem = rsa.publickey().exportKey()
        with open("server_public.pem", "wb") as f:
            f.write(public_pem)

        # Client的秘钥对的生成
        # private_pem = rsa.exportKey()
        # with open("client_private.pem", "wb") as f:
        #     f.write(private_pem)
        #
        # public_pem = rsa.publickey().exportKey()
        # with open("client_public.pem", "wb") as f:
        #     f.write(public_pem)

    @classmethod
    # Server使用Client的公钥对内容进行rsa 加密
    def encrypt(cls, plaintext):
        """
        client 公钥进行加密
        plaintext:需要加密的明文文本，公钥加密，私钥解密
        """

        # 加载公钥
        rsa_key = RSA.import_key(open("client_public.pem").read())

        # 加密
        cipher_rsa = Cipher_PKC.new(rsa_key)
        en_data = cipher_rsa.encrypt(plaintext.encode("utf-8"))  # 加密

        # base64 进行编码
        base64_text = base64.b64encode(en_data)

        return base64_text.decode()  # 返回字符串

    @classmethod
    # Client使用自己的私钥对内容进行rsa 解密
    def decrypt(cls, en_data):
        """
        en_data:加密过后的数据，传进来是一个字符串
        """
        # base64 解码
        base64_data = base64.b64decode(en_data.encode("utf-8"))

        # 读取私钥
        private_key = RSA.import_key(open("client_private.pem").read())

        # 解密
        cipher_rsa = Cipher_PKC.new(private_key)
        data = cipher_rsa.decrypt(base64_data, None)

        return data.decode()

    @classmethod
    def signature(cls, data: str, server_private_key_path: str):
        """
         RSA私钥签名
         Server使用自己的私钥对内容进行签名
        :param data: 明文数据
        :param server_private_key_path: 服务端私钥路径
        :return: 签名后的字符串sign
        """
        with open(server_private_key_path) as f:
            # 读取私钥
            private_key = RSA.import_key(f.read())
        # 根据SHA256算法处理签名内容data
        sha_data = SHA256.new(data.encode("utf-8"))  # byte类型

        # 私钥进行签名
        signer = Signature_PKC.new(private_key)
        sign = signer.sign(sha_data)

        # 将签名后的内容，转换为base64编码
        sign_base64 = base64.b64encode(sign)
        return sign_base64.decode()

    @classmethod
    def verify(cls, data: str, signature_file_path: str, server_public_key_path: str):
        """
        RSA公钥验签
        Client使用Server的公钥对内容进行验签
        :param data: 明文数据
        :param signature_file_path: 签名文件路径
        :param server_public_key_path: 服务端公钥路径
        :return: 验签结果,布尔值
        """
        with open(signature_file_path, "r") as f:
            signature = f.read()

        with open(server_public_key_path, "r") as f:
            server_public_key = f.read()
        return cls._verify(data, signature, server_public_key)

    @classmethod
    def _verify(cls, data: str, signature: str, server_public_key: str) -> bool:
        """
        RSA公钥验签
        Client使用Server的公钥对内容进行验签
        :param data: 明文数据,签名之前的数据
        :param signature: 接收到的sign签名
        :param server_public_key: 服务端公钥
        :return: 验签结果,布尔值
        """
        # 接收到的sign签名 base64解码
        sign_data = base64.b64decode(signature.encode("utf-8"))
        # 加载公钥
        public_key = RSA.importKey(server_public_key)

        # 根据SHA256算法处理签名之前内容data
        sha_data = SHA256.new(data.encode("utf-8"))  # byte类型

        # 验证签名
        signer = Signature_PKC.new(public_key)
        is_verify = signer.verify(sha_data, sign_data)

        return is_verify


class Md5Utils:
    @staticmethod
    def encrypt(text):
        import hashlib
        # 创建 MD5 对象
        m = hashlib.md5()
        # 更新 MD5 对象的内容
        m.update(text.encode('utf-8'))
        # 获取加密后的十六进制字符串
        return m.hexdigest()


class TripleDESCryptor:
    def __init__(self, key):
        # 3DES 密钥长度必须为 16 或 24 字节
        if len(key) not in [16, 24]:
            raise ValueError("3DES 密钥长度必须为 16 或 24 字节")
        self.key = key.encode()

    def encrypt(self, plaintext):
        # 创建 3DES 加密器
        cipher = DES3.new(self.key, DES3.MODE_ECB)
        # 对明文进行填充
        padded_plaintext = pad(plaintext.encode(), DES3.block_size)
        # 加密
        ciphertext = cipher.encrypt(padded_plaintext)
        # 将加密结果进行 Base64 编码
        return base64.b64encode(ciphertext).decode()

    def decrypt(self, ciphertext):
        # 对 Base64 编码的密文进行解码
        ciphertext = base64.b64decode(ciphertext)
        # 创建 3DES 解密器
        cipher = DES3.new(self.key, DES3.MODE_ECB)
        # 解密
        decrypted_data = cipher.decrypt(ciphertext)
        # 去除填充
        return unpad(decrypted_data, DES3.block_size).decode()


class CryptoUtil:
    # 密钥，必须是16（AES-128）、24（AES-192）或32（AES-256）字节长
    # key = b'This is a key123'  # 16字节长

    # 初始化向量，必须是16字节长
    # iv = b'This is an IV456'

    encoding = "utf-8"

    def __init__(self, key: str, iv: str):
        # 密钥，必须是16（AES-128）、24（AES-192）或32（AES-256）字节长
        self.key = key.encode(encoding=self.encoding)
        # 初始化向量，必须是16字节长
        self.iv = iv.encode(encoding=self.encoding)

    # 加密函数
    def encrypt_data(self, data):
        cipher = AES.new(self.key, AES.MODE_CBC, self.iv)
        ct_bytes = cipher.encrypt(pad(data.encode(), AES.block_size))
        iv_bytes = cipher.iv
        return b64encode(iv_bytes + ct_bytes).decode(self.encoding)

    # 解密函数
    def decrypt_data(self, encrypted_data: str):
        encrypted_data_bytes = b64decode(encrypted_data)
        iv_bytes = encrypted_data_bytes[:16]
        ct_bytes = encrypted_data_bytes[16:]
        cipher = AES.new(self.key, AES.MODE_CBC, iv_bytes)
        return unpad(cipher.decrypt(ct_bytes), AES.block_size).decode(self.encoding)
