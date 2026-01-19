import json
import logging
import os
import uuid
from datetime import datetime
from typing import Tuple
from urllib.parse import urljoin

from qiniu import Auth, BucketManager, UploadProgressRecorder
from qiniu.config import _BLOCK_SIZE, get_default
from qiniu.http import ResponseInfo
from qiniu.services.storage.uploaders import FormUploader, ResumeUploaderV1, ResumeUploaderV2
from qiniu.utils import crc32, file_crc32, rfc_from_timestamp


class FileOperatorResult:

    def __init__(self, status: bool, hash_val=None, remote_resource_name=None, fail_desc=""):
        """
        存储文件操作的结果，上传、下载、复制等
        :param status: True-操作成功；False-操作失败
        :param hash_val: 文件上传操作时，文件在第三方系统的唯一标识
        :param remote_resource_name: 远程资源名，文件上传到远程服务器上，存储的完整名称（含路径）
        :param fail_desc: 操作失败描述，status=False时，有值
        """
        # 状态。True-成功，False-失败
        self.status = status
        # 七牛云返回的文件唯一哈希值
        self.hash = hash_val
        # 文件在七牛云上的名称
        self.resource_name = remote_resource_name
        # 错误描述，status=2时有值
        self.fail_desc = fail_desc
        # 完整资源地址
        self.resource_url = ""

    def __str__(self):
        return f"status={self.status}&hash={self.hash}&resource_name={self.resource_name}&fail_desc={self.fail_desc}"


class QiniuService:

    def __init__(self, access_key=None, secret_key=None, is_need_callback=False, callback_url=None,
                 custom_callback_vars=None, max_size=1024 * 1024 * 1024, progress_handler=None):
        """
        七牛文件操作类
        :param access_key: 七牛后台获取，存储在系统的配置信息中，不传的话中，文件空间配置中读取配置信息
        :param secret_key: 七牛后台获取，存储在系统的配置信息中，不传的话中，文件空间配置中读取配置信息
        :param is_need_callback: bool 是否需要回调。True-是；False-否
            默认回调报文：{"remote_file_path": "$(key}", "remote_file_hash": "$(etag)", "size": "$(fsize)", "origin_name": "$(fname)"}
            post方式，application/json
        :param callback_url: 回调地址
        :param custom_callback_vars: dict 自定义回调参数。
            七牛要求自定义回调的参数，必须以x:开头，例如：自定义回调参数为x:task_id，x:price，则该参数要传：{"x:task_id": "TASK10001", "x:price": 100.00}
        :param max_size: 最大文件大小，单位Byte，默认为1G
        :param progress_handler: func 进度回调函数，必须传入一个方法。例如：
                                def progress_handler(uploaded_size, total_size):
                                    uploaded_size: 已经上传的大小
                                    total_size: 总共大小
        """
        self.file_bucket = None
        # if not access_key or not secret_key:
        #     # 读配置信息
        #     file_bucket: CfgFileBucketDTO = CfgFileBucketService.get_cli_file_bucket()
        #     access_key = access_key or file_bucket.access_key
        #     secret_key = secret_key or file_bucket.secret_key
        #     self.file_bucket = file_bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.progress_handler = progress_handler
        # 回调标志
        self.is_need_callback = is_need_callback
        if self.is_need_callback and not callback_url:
            raise ValueError("callback_url必传")
        # 回调地址，is_need_callback=True必传
        self.callback_url = callback_url
        self.callback_body = {"remote_file_path": "$(key)", "remote_file_hash": "$(etag)", "size": "$(fsize)",
                              "origin_name": "$(fname)"}
        # 上传策略，后续
        self.policy = {"fsizeLimit": max_size}
        self.custom_callback_vars = {}
        if self.is_need_callback:
            self._handle_callback(custom_callback_vars)

        # 构建鉴权对象
        self.auth = Auth(self.access_key, self.secret_key)
        # 空间管理对象BucketManager，用于管理空间中的文件
        self.bucket_manager = BucketManager(self.auth)
        # 日志
        self.log = logging.getLogger()

    # def __init__(self, bucket_name, is_need_callback=True, test_mode=False, **kwargs):
    #     """
    #     七牛文件操作类
    #     :param bucket_name: 文件空间名称
    #     :param is_need_callback: bool 是否需要回调
    #     :param test_mode: bool True-测试模式，传入access_key，secret_key，bucket_name三个参数可以实现文件操作；False-正常模式
    #     """
    #     if test_mode:
    #         self.init_test_mode(kwargs.get("access_key"), kwargs.get("secret_key"), kwargs.get("bucket_name"))
    #         return
    #     # 七牛的ak和sk，从系统配置中获取
    #     sys_config: SysConfigDTO = SysConfigService.get_by_key(SysConfigKey.QN_ACCESS_KEY)
    #     if not sys_config:
    #         raise ServiceException("没有找到相关配置QN_ACCESS_KEY")
    #     else:
    #         self.access_key = sys_config.cfg_value
    #
    #     sys_config = SysConfigService.get_by_key(SysConfigKey.QN_SECRET_KEY)
    #     if not sys_config:
    #         raise ServiceException("没有找到相关配置QN_SECRET_KEY")
    #     else:
    #         self.secret_key = sys_config.cfg_value
    #
    #     # 七牛文件空间，从系统配置中获取
    #     self.bucket_name = bucket_name
    #     # sys_config = SysConfigService.get_by_key(SysConfigKey.QN_BUCKET_NAME)
    #     # if not sys_config:
    #     #     raise ServiceException("没有找到相关配置QN_BUCKET_NAME")
    #     # else:
    #     #     self.bucket_name = sys_config.cfg_value
    #
    #     # 是否需要回调的标志，False-不需要回调；True-需要回调
    #     self.is_need_callback = is_need_callback
    #     if self.is_need_callback:
    #         # 回调地址，从系统配置中获取
    #         sys_config = SysConfigService.get_by_key(SysConfigKey.QN_UPLOAD_SUCC_CALLBACK_URL)
    #         if not sys_config:
    #             raise ServiceException("没有找到相关配置QN_UPLOAD_SUCC_CALLBACK_URL")
    #         else:
    #             self.callback_url = sys_config.cfg_value
    #
    #     # 上传最大文件限制
    #     sys_config = SysConfigService.get_by_key(SysConfigKey.QN_UPLOAD_MAX_SIZE)
    #     # 默认最大上传大小为512M
    #     self.max_file_size = 512 * 1024 * 1024 if not sys_config else int(sys_config.cfg_value) * 1024 * 1024
    #
    #     # 构建鉴权对象
    #     self.auth = Auth(self.access_key, self.secret_key)
    #     # 空间管理对象BucketManager，用于管理空间中的文件
    #     self.bucket_manager = BucketManager(self.auth)
    #     self.log = logging.getLogger()

    def gen_download_url(self, private_file_url, expires=3600):
        """
        生成私有资源的下载链接

        :param private_file_url: 私有文件的地址
        :param expires: 单位：秒，下载链接的过期时间，默认3600s
        :return:
        """
        return self.auth.private_download_url(private_file_url, expires)

    def upload_file(self, res_file, dest_file, bucket_name=None) -> FileOperatorResult:
        """
        上传文件
        :param res_file: str 源文件，要上传的文件
        :param dest_file: str 目标文件，文件在七牛上的名称，可以带目录，例如：cas2.0/abc.xlsx，在七牛上的空间下会创建一个名称为cas2.0的目录，
            但是不能以斜杠（/）开头
        :param bucket_name: str 文件空间名称，当access_key和secret_key都为自定义时，bucket_name必传！

        :return: FileOperateResult对象
        """
        if self.file_bucket:
            bucket_name = self.file_bucket.name

        if not bucket_name:
            raise ValueError("bucket_name必传")
        upload_token = self.gen_upload_token(bucket_name, dest_file, 7200)

        upload_ret = self.put_file(upload_token, dest_file, res_file, params=self.custom_callback_vars, version='v2',
                                   progress_handler=self.progress_handler)

        response_info: ResponseInfo = upload_ret[1]
        self.log.info(f"上传文件：{res_file}，响应报文：{upload_ret[0]}，错误消息：{response_info}")

        # 上传状态。True-成功；False-失败
        is_upload_succ = True
        # 失败原因
        upload_fail_desc = ""

        if response_info.connect_failed():
            is_upload_succ = False
            upload_fail_desc = "上传失败：连接文件服务器失败"
            self.log.error(f"文件：{res_file}，上传失败：连接七牛服务器失败")
        elif not response_info.ok():
            is_upload_succ = False
            upload_fail_desc = f"上传失败：{response_info.error}"
            self.log.error(f"文件：{res_file}，上传失败：{response_info.error}")
            # if response_info.status_code == 579:
            #     # 上传成功但是回调失败，也当做失败来处理，需要人工介入检查回调接口，上传结果以回调为准
            #     self.LOG.error(f"文件：{res_file}，上传成功但是回调失败！七牛异常消息：{upload_fail_reason}")
            # else:
            #     # 上传失败了
            #     self.LOG.error(f"文件：{res_file}，上传失败，原因：{upload_fail_reason}")
            #     raise ServiceException("文件上传失败")

        return FileOperatorResult(is_upload_succ, upload_ret[0].get("hash"),
                                  upload_ret[0].get("key")) if is_upload_succ else FileOperatorResult(is_upload_succ,
                                                                                                      fail_desc=upload_fail_desc)

    def copy(self, ori_bucket_name, ori_file_name, dest_bucket_name, dest_file_name):
        """
        复制文件
        :param ori_bucket_name: 原空间名称
        :param ori_file_name: 原文件名
        :param dest_bucket_name: 目标空间名称
        :param dest_file_name: 目标文件名
        :return:
        """
        resp = self.bucket_manager.copy(ori_bucket_name, ori_file_name, dest_bucket_name, dest_file_name)
        response_info: ResponseInfo = resp[1]
        self.log.info(
            f"复制文件：从 空间{ori_bucket_name}文件{ori_file_name} 到 空间{dest_bucket_name}文件{dest_file_name}，响应报文：{resp[0]}，错误消息：{response_info}")
        if not response_info.ok():
            # 复制失败
            return FileOperatorResult(False, fail_desc=f"复制失败：{response_info.error}")
        else:
            # 复制成功
            return FileOperatorResult(True)

    def _handle_callback(self, custom_callback_vars=None):
        if custom_callback_vars:
            for k, v in custom_callback_vars.items():
                if not k.startswith("x:"):
                    self.callback_body[k] = f"x:{k}"
                    self.custom_callback_vars[f"x:{k}"] = v
                else:
                    self.callback_body[k[2:]] = f"$({k})"
                    self.custom_callback_vars[k] = v

        # 上传文件到存储后， 存储服务将文件名和文件大小回调给业务服务器。
        self.policy.update({
            "callbackUrl": self.callback_url,
            'callbackBody': json.dumps(self.callback_body, ensure_ascii=False),
            "callbackBodyType": "application/json"
        })

    def gen_upload_token(self, bucket_name, remote_file_name, expire_seconds):
        """
        生成上传token
        :param bucket_name: 空间名称
        :param remote_file_name: str 文件在七牛上的名称，可以带目录，例如：cas2.0/abc.xlsx，在七牛上的空间下会创建一个
        :param expire_seconds: int token过期时间，单位：秒，请务必预估好文件的大小和上传的时间，若文件比较大且上传时间超过该时间，则中途上传失败！
        :return:
        """
        # 生成上传 Token，可以指定过期时间等
        return self.auth.upload_token(bucket_name, remote_file_name, expire_seconds, self.policy)

    def _put_data(self,
                  up_token, key, data, params=None, mime_type='application/octet-stream', check_crc=False,
                  progress_handler=None,
                  fname=None, hostscache_dir=None, metadata=None
                  ) -> Tuple[dict, ResponseInfo]:
        """
        上传二进制流到七牛

        :param up_token: 上传凭证
        :param key: 上传文件名
        :param data: 上传二进制流
        :param params: 自定义变量，规格参考 https://developer.qiniu.com/kodo/manual/vars#xvar
        :param mime_type: 上传数据的mimeType
        :param check_crc: 是否校验crc32
        :param progress_handler: 上传进度
        :param fname: 文件名
        :param hostscache_dir: host请求 缓存文件保存位置
        :param metadata: 元数据
        :return: tuple (dict, ResponseInfo) 一个dict变量，类似 {"hash": "<Hash string>", "key": "<Key string>"}；一个ResponseInfo对象
        """

        final_data = b''
        if hasattr(data, 'read'):
            while True:
                tmp_data = data.read(_BLOCK_SIZE)
                if len(tmp_data) == 0:
                    break
                else:
                    final_data += tmp_data
        else:
            final_data = data

        crc = crc32(final_data)
        return self._form_put(
            up_token, key, final_data, params, mime_type,
            crc, hostscache_dir, progress_handler, fname, metadata=metadata
        )

    def put_file(self,
                 up_token, key, file_path, params=None,
                 mime_type='application/octet-stream', check_crc=False,
                 progress_handler=None, upload_progress_recorder=None, keep_last_modified=False, hostscache_dir=None,
                 part_size=None, version=None, bucket_name=None, metadata=None
                 ) -> Tuple[dict, ResponseInfo]:
        """上传文件到七牛

        Args:
            up_token:                 上传凭证
            key:                      上传文件名
            file_path:                上传文件的路径
            params:                   自定义变量，规格参考 https://developer.qiniu.com/kodo/manual/vars#xvar
            mime_type:                上传数据的mimeType
            check_crc:                是否校验crc32
            progress_handler:         上传进度
            upload_progress_recorder: 记录上传进度，用于断点续传
            hostscache_dir:           host请求 缓存文件保存位置
            version:                  分片上传版本 目前支持v1/v2版本 默认v1
            part_size:                分片上传v2必传字段 默认大小为4MB 分片大小范围为1 MB - 1 GB
            bucket_name:              分片上传v2字段 空间名称
            metadata:                 元数据信息

        Returns:
            一个dict变量，类似 {"hash": "<Hash string>", "key": "<Key string>"}
            一个ResponseInfo对象
        """
        ret = {}
        size = os.stat(file_path).st_size
        with open(file_path, 'rb') as input_stream:
            file_name = os.path.basename(file_path)
            modify_time = int(os.path.getmtime(file_path))
            if size > get_default('default_upload_threshold'):
                ret, info = self.put_stream(
                    up_token, key, input_stream, file_name, size, hostscache_dir, params,
                    mime_type, progress_handler,
                    upload_progress_recorder=upload_progress_recorder,
                    modify_time=modify_time, keep_last_modified=keep_last_modified,
                    part_size=part_size, version=version, bucket_name=bucket_name, metadata=metadata
                )
            else:
                crc = file_crc32(file_path)
                ret, info = self._form_put(
                    up_token, key, input_stream, params, mime_type,
                    crc, hostscache_dir, progress_handler, file_name,
                    modify_time=modify_time, keep_last_modified=keep_last_modified, metadata=metadata
                )
        return ret, info

    def _form_put(self,
                  up_token,
                  key,
                  data,
                  params,
                  mime_type,
                  crc,
                  hostscache_dir=None,
                  progress_handler=None,
                  file_name=None,
                  modify_time=None,
                  keep_last_modified=False,
                  metadata=None
                  ):
        bucket_name = Auth.get_bucket_name(up_token)
        uploader = FormUploader(
            bucket_name,
            progress_handler=progress_handler,
            hosts_cache_dir=hostscache_dir
        )

        if modify_time and keep_last_modified:
            metadata['x-qn-meta-!Last-Modified'] = rfc_from_timestamp(modify_time)

        return uploader.upload(
            key=key,
            data=data,
            data_size=None,
            file_name=file_name,
            modify_time=modify_time,
            mime_type=mime_type,
            metadata=metadata,
            custom_vars=params,
            crc32_int=crc,
            up_token=up_token
        )

    def put_stream(self,
                   up_token,
                   key,
                   input_stream,
                   file_name,
                   data_size,
                   hostscache_dir=None,
                   params=None,
                   mime_type=None,
                   progress_handler=None,
                   upload_progress_recorder=None,
                   modify_time=None,
                   keep_last_modified=False,
                   part_size=None,
                   version='v1',
                   bucket_name=None,
                   metadata=None
                   ):
        if not bucket_name:
            bucket_name = Auth.get_bucket_name(up_token)
        if not upload_progress_recorder:
            upload_progress_recorder = UploadProgressRecorder()
        if not version:
            version = 'v1'
        if not part_size:
            part_size = 4 * (1024 * 1024)

        if version == 'v1':
            uploader = ResumeUploaderV1(
                bucket_name,
                progress_handler=progress_handler,
                upload_progress_recorder=upload_progress_recorder,
                hosts_cache_dir=hostscache_dir
            )
            if modify_time and keep_last_modified:
                metadata['x-qn-meta-!Last-Modified'] = rfc_from_timestamp(modify_time)
        elif version == 'v2':
            uploader = ResumeUploaderV2(
                bucket_name,
                progress_handler=progress_handler,
                upload_progress_recorder=upload_progress_recorder,
                part_size=part_size,
                hosts_cache_dir=hostscache_dir
            )
        else:
            raise ValueError('version only could be v1 or v2')
        return uploader.upload(
            key=key,
            data=input_stream,
            data_size=data_size,
            file_name=file_name,
            modify_time=modify_time,
            mime_type=mime_type,
            metadata=metadata,
            custom_vars=params,
            up_token=up_token
        )


class UploadFileOperator:
    FILE_DOMAIN = "https://file.ptzhs.com"

    def __init__(self):
        self.access_key = "wou0d38bcdx8q_RA7yYhw-R6beIdz3X8rwrBSln6"
        self.secret_key = '14_8yTLwbPs0AO6CQggVaVSp8cz0SRFEJoIruwNc'
        self.bucket_name = "ptzhs"
        # self.access_key = '0BMrIdH-NuXuCCk1Bmq1PganjxNynHc6qOjxIfbO'
        # self.secret_key = '7j2bCo1V-go7WS_hhku6-IniiAsYlY1fxkCeZdeS'
        self.max_size = 3 * 1024 * 1024 * 1024

    def progress_handler(self, uploaded_size, total_size):
        print(f"已上传大小：{uploaded_size / 1024 / 1024}M，总大小{total_size / 1024 / 1024}M，当前时间：{datetime.now()}")

    def upload(self, file_full_path: str, remote_file_name=None) -> FileOperatorResult:
        """
        上传文件
        :param file_full_path: 文件完整路径
        :param remote_file_name: 远程文件名（上传到服务器之后的文件名）
        :return:
        """
        if not os.path.exists(file_full_path):
            raise Exception(f"文件不仅存在：{file_full_path}")

        base_name = os.path.basename(file_full_path)
        if not remote_file_name:
            remote_file_name = f"{str(uuid.uuid4())}.{base_name.split('.')[-1]}"

        qiniu_service = QiniuService(access_key=self.access_key, secret_key=self.secret_key,
                                     progress_handler=self.progress_handler, max_size=self.max_size,
                                     is_need_callback=False)
        file_operator_result = qiniu_service.upload_file(file_full_path, remote_file_name, self.bucket_name)
        if file_operator_result.status:
            file_operator_result.resource_url = urljoin(UploadFileOperator.FILE_DOMAIN,
                                                        file_operator_result.resource_name)
        return file_operator_result

    def test_copy_file(self):
        # bucket_name = 'cli-lingcha'
        bucket_name = 'zjh-test'
        qiniu_service = QiniuService(access_key=self.access_key, secret_key=self.secret_key,
                                     progress_handler=self.progress_handler, max_size=self.max_size)
        upload_info = qiniu_service.copy(bucket_name, "xxx/xxcas_task.sql", bucket_name, "aa/xxcas_tasxc3.sql")
        print(upload_info)

    def test_gen_public_download_url(self):
        qiniu_service = QiniuService(access_key=self.access_key, secret_key=self.secret_key)
        url = "http://file.cli.lingcha.cn/其他出库列表.xlsx"
        print(qiniu_service.gen_download_url(url, 100000))


class QiniuTest:
    def __init__(self):
        self.access_key = "wou0d38bcdx8q_RA7yYhw-R6beIdz3X8rwrBSln6"
        self.secret_key = '14_8yTLwbPs0AO6CQggVaVSp8cz0SRFEJoIruwNc'
        # self.bucket_name = "pub-yangzai"
        self.bucket_name = "ptzhs"
        # self.access_key = '0BMrIdH-NuXuCCk1Bmq1PganjxNynHc6qOjxIfbO'
        # self.secret_key = '7j2bCo1V-go7WS_hhku6-IniiAsYlY1fxkCeZdeS'
        self.max_size = 3 * 1024 * 1024 * 1024

    def progress_handler(self, uploaded_size, total_size):
        print(f"已上传大小：{uploaded_size / 1024 / 1024}M，总大小{total_size / 1024 / 1024}M，当前时间：{datetime.now()}")

    def test_upload_callback(self):
        # bucket_name = 'zjh-test'
        qiniu_service = QiniuService(access_key=self.access_key, secret_key=self.secret_key,
                                     progress_handler=self.progress_handler, max_size=self.max_size,
                                     is_need_callback=False,
                                     callback_url="http://47.116.72.109:12000/ca_data_file/upload/notify",
                                     custom_callback_vars={"x:task_id": 123, "x:action_id": "dfdfdf12333ddd",
                                                           "x:entity_id": 1, "x:file_type": 12})
        file = r"C:\Users\lovel\Downloads\公众号写作素材\dfcvv223.jpg"
        return qiniu_service.upload_file(file, r"dfcvv223.jpg", self.bucket_name)

    def test_copy_file(self):
        # bucket_name = 'cli-lingcha'
        bucket_name = 'zjh-test'
        qiniu_service = QiniuService(access_key=self.access_key, secret_key=self.secret_key,
                                     progress_handler=self.progress_handler, max_size=self.max_size)
        upload_info = qiniu_service.copy(bucket_name, "xxx/xxcas_task.sql", bucket_name, "aa/xxcas_tasxc3.sql")
        print(upload_info)

    def test_gen_public_download_url(self):
        qiniu_service = QiniuService(access_key=self.access_key, secret_key=self.secret_key)
        url = "http://file.cli.lingcha.cn/其他出库列表.xlsx"
        print(qiniu_service.gen_download_url(url, 100000))

if __name__ == '__main__':
    UploadFileOperator().upload(r"C:\Users\lovel\Desktop\关于转发《关于组织开展2026年度自治区基础教育教研专项课题申报工作的通知》的通知.zip", "关于转发《关于组织开展2026年度自治区基础教育教研专项课题申报工作的通知》的通知")