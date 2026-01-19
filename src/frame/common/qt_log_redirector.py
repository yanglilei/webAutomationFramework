import logging
import re
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from PyQt5.QtCore import pyqtSignal, QObject

from src.frame.common.config_file_reader import ConfigFileReader
from src.frame.common.constants import Constants
from src.frame.common.decorator.singleton import singleton
from src.utils.sys_path_utils import SysPathUtils


class QtLogRedirector(QObject):
    signal = pyqtSignal(str)

    # 级别-颜色映射（HTML 颜色码，可自定义）
    LEVEL_COLORS = {
        "DEBUG": "#666666",  # 灰色
        "INFO": "#000000",  # 黑色
        "WARNING": "#FF8C00",  # 橙色
        "ERROR": "#DC143C",  # 深红色
        "CRITICAL": "#800080"  # 紫色
    }
    # 正则匹配日志中的级别（适配格式 [%(levelname)s]）
    LEVEL_PATTERN = re.compile(r"\[([A-Z]+)\]")

    @classmethod
    def instance(cls, *args, **kwargs):
        if not hasattr(QtLogRedirector, "_instance"):
            QtLogRedirector._instance = QtLogRedirector(*args, **kwargs)
        return QtLogRedirector._instance

    def __init__(self, *args, **kwargs):
        super().__init__()

    # 实现文件类对象的 write 方法（StreamHandler 会调用）
    def write(self, log_text):
        """
        改造 write 方法：解析级别 → 生成彩色 HTML → 发送信号
        """
        try:
            # 1. 过滤空行和多余换行
            clean_text = log_text.rstrip("\n")
            if not clean_text:
                return

            # 2. 提取日志级别（如从 "[INFO]" 中提取 "INFO"）
            level_match = self.LEVEL_PATTERN.search(clean_text)
            level = level_match.group(1) if level_match else "INFO"  # 默认 INFO
            color = self.LEVEL_COLORS.get(level, "#000000")  # 默认黑色

            # 3. 生成带颜色的 HTML（仅给级别和日志内容上色，保持格式）
            # 替换级别部分为彩色，或直接给整行上色（两种方案选其一）
            # 方案1：仅级别上色（推荐，格式更清晰）
            # colored_text = self.LEVEL_PATTERN.sub(
            #     rf'<span style="color:{color}; font-weight:bold;">[\1]</span>',
            #     clean_text
            # )
            # 方案2：整行上色（注释掉方案1，启用此方案）
            colored_text = f'<span style="color:{color};">{clean_text}</span>'

            # 4. 追加换行符（HTML 换行），发送信号
            html_msg = colored_text + "<br>"
            self.signal.emit(html_msg)

        except Exception as e:
            # 兜底：输出纯文本到原生 stderr
            print(f"日志上色失败：{e} | 原始日志：{log_text}", file=sys.stderr)
            # 发送原始文本（无颜色）
            self.signal.emit(clean_text + "<br>")

    def flush(self):
        pass

    def create_logger(
            self,
            log_full_path_name: str,
            log_name=__name__,
            root_file_level=logging.DEBUG,
            stream_level=logging.INFO
    ) -> logging.Logger:
        """
        初始化日志：
        - 根 Logger：仅绑定文件 Handler（全局日志写入文件）
        - 指定 log_name 的 Logger：仅绑定 StreamHandler（日志输出到 UI）

        非常重要！日志的流转逻辑说明：
        1.业务 Logger 日志
        LOG.info("测试")
        → 业务 Logger 的 StreamHandler → UI 展示
        → 传播到根 Logger → 根 Logger 的文件 Handler → 写入全局日志文件

        2.第三方/系统 Logger 日志
        logging.getLogger("requests").warning("测试")
        → 传播到根 Logger → 根 Logger 的文件 Handler → 写入全局日志文件（无 UI 展示）

        :param log_full_path_name: 根日志的文件保存路径
        :param log_name: 业务 Logger 名称（仅该 Logger 输出到 UI）
        :param root_file_level: 根日志文件输出级别（默认 DEBUG，捕获所有）
        :param stream_level: 业务日志 UI 输出级别（默认 INFO）
        :return: 业务 Logger 实例（log_name 对应的 Logger）
        """
        # ===================== 第一步：配置根 Logger（仅文件输出） =====================
        root_logger = logging.getLogger()
        root_logger.setLevel(root_file_level)  # 根日志级别设为最低，保证所有日志能被捕获

        # 检查根 Logger 是否已添加文件 Handler（避免重复添加）
        has_root_file_handler = any(
            isinstance(h, RotatingFileHandler) for h in root_logger.handlers
        )
        if not has_root_file_handler:
            # 根日志的文件格式（可自定义）
            root_formatter = logging.Formatter(
                '[%(asctime)s][%(levelname)s]%(module)s:%(lineno)s-%(message)s',
                "%Y-%m-%d %H:%M:%S"
            )
            # 按大小滚动的文件 Handler（100MB/文件，保留5个）
            root_file_handler = RotatingFileHandler(
                log_full_path_name, "a", 100 * 1024 * 1024, 5, encoding="utf-8"
            )
            root_file_handler.setLevel(root_file_level)
            root_file_handler.setFormatter(root_formatter)
            root_logger.addHandler(root_file_handler)

        # ===================== 第二步：配置业务 Logger（仅 Stream 输出） =====================
        business_logger = logging.getLogger(log_name)
        business_logger.setLevel(logging.DEBUG)  # 业务日志级别设为最低

        # 检查业务 Logger 是否已添加 StreamHandler（避免重复添加）
        has_business_stream_handler = any(
            isinstance(h, logging.StreamHandler) and h.stream is self for h in business_logger.handlers
        )
        if not has_business_stream_handler:
            # 业务日志的 UI 展示格式（可自定义）
            stream_formatter = logging.Formatter(
                '[%(asctime)s][%(levelname)s]%(module)s:%(lineno)s-%(message)s',
                "%Y-%m-%d %H:%M:%S"
            )
            # 绑定自定义 StreamHandler（输出到 UI）
            stream_handler = logging.StreamHandler(self)
            stream_handler.setLevel(stream_level)  # UI 仅展示 INFO 及以上
            stream_handler.setFormatter(stream_formatter)
            business_logger.addHandler(stream_handler)

            # （可选）关闭业务 Logger 的传播（避免日志重复到根 Logger 的 StreamHandler，此处根 Logger 无 StreamHandler，可忽略）
            # business_logger.propagate = False

        return business_logger

@singleton
class QtLogRedirectorV2(QObject):
    """多线程 + Qt 日志类改造方案：日志自动携带线程专属用户名，线程启动时调用set_current_user方法"""
    signal = pyqtSignal(str)

    # 级别-颜色映射（HTML 颜色码，可自定义）
    LEVEL_COLORS = {
        "DEBUG": "#666666",  # 灰色
        "INFO": "#000000",   # 黑色
        "WARNING": "#FF8C00",# 橙色
        "ERROR": "#DC143C",  # 深红色
        "CRITICAL": "#800080"# 紫色
    }
    # 正则匹配日志中的级别（适配格式 [%(levelname)s]）
    LEVEL_PATTERN = re.compile(r"\[([A-Z]+)\]")

    # ✅ 新增：线程本地存储 - 每个线程独立存储自己的用户名，线程隔离不串值
    _thread_local = threading.local()

    # ✅ 新增：设置当前线程的用户名（业务线程初始化时调用一次即可）
    def set_current_user(self, username: str):
        """为当前执行线程绑定用户名，该线程后续所有日志自动携带此用户名"""
        setattr(self._thread_local, "username", username)

    # ✅ 新增：获取当前线程的用户名（内部日志过滤使用）
    def get_current_user(self) -> str:
        """获取当前线程绑定的用户名，未设置则返回默认值"""
        return getattr(self._thread_local, "username", "FRAMEWORK")

    # ✅ 新增：自定义日志过滤器 - 自动为日志Record对象追加username字段
    class UserContextFilter(logging.Filter):
        def __init__(self, qt_logger):
            super().__init__()
            self.qt_logger = qt_logger

        def filter(self, record: logging.LogRecord) -> bool:
            # 核心：从当前线程本地存储中，获取用户名并绑定到日志Record
            record.username = self.qt_logger.get_current_user()
            return True

    # 实现文件类对象的 write 方法（StreamHandler 会调用）
    def write(self, log_text):
        """
        改造 write 方法：解析级别 → 生成彩色 HTML → 发送信号
        """
        try:
            # 1. 过滤空行和多余换行
            clean_text = log_text.rstrip("\n")
            if not clean_text:
                return

            # 2. 提取日志级别（如从 "[INFO]" 中提取 "INFO"）
            level_match = self.LEVEL_PATTERN.search(clean_text)
            level = level_match.group(1) if level_match else "INFO"  # 默认 INFO
            color = self.LEVEL_COLORS.get(level, "#000000")  # 默认黑色

            # 3. 生成带颜色的 HTML（仅给级别和日志内容上色，保持格式）
            colored_text = f'<span style="color:{color};">{clean_text}</span>'

            # 4. 追加换行符（HTML 换行），发送信号
            html_msg = colored_text + "<br>"
            self.signal.emit(html_msg)

        except Exception as e:
            # 兜底：输出纯文本到原生 stderr
            print(f"日志上色失败：{e} | 原始日志：{log_text}", file=sys.stderr)
            # 发送原始文本（无颜色）
            self.signal.emit(clean_text + "<br>")

    def flush(self):
        pass

    def create_logger(
            self,
            log_full_path_name: str,
            log_name=__name__,
            root_file_level=logging.DEBUG,
            stream_level=logging.INFO
    ) -> logging.Logger:
        """
        初始化日志：
        - 根 Logger：仅绑定文件 Handler（全局日志写入文件）
        - 指定 log_name 的 Logger：仅绑定 StreamHandler（日志输出到 UI）

        非常重要！日志的流转逻辑说明：
        1.业务 Logger 日志
        LOG.info("测试")
        → 业务 Logger 的 StreamHandler → UI 展示
        → 传播到根 Logger → 根 Logger 的文件 Handler → 写入全局日志文件

        2.第三方/系统 Logger 日志
        logging.getLogger("requests").warning("测试")
        → 传播到根 Logger → 根 Logger 的文件 Handler → 写入全局日志文件（无 UI 展示）

        :param log_full_path_name: 根日志的文件保存路径
        :param log_name: 业务 Logger 名称（仅该 Logger 输出到 UI）
        :param root_file_level: 根日志文件输出级别（默认 DEBUG，捕获所有）
        :param stream_level: 业务日志 UI 输出级别（默认 INFO）
        :return: 业务 Logger 实例（log_name 对应的 Logger）
        """
        # ===================== 第一步：配置根 Logger（仅文件输出） =====================
        root_logger = logging.getLogger()
        root_logger.setLevel(root_file_level)  # 根日志级别设为最低，保证所有日志能被捕获

        # 检查根 Logger 是否已添加文件 Handler（避免重复添加）
        has_root_file_handler = any(
            isinstance(h, RotatingFileHandler) for h in root_logger.handlers
        )
        if not has_root_file_handler:
            # ✅ 修改：文件日志格式 - 新增【%(username)s】占位符，自动显示线程用户名
            root_formatter = logging.Formatter(
                '[%(asctime)s][%(levelname)s][%(username)s]%(module)s:%(lineno)s-%(message)s',
                "%Y-%m-%d %H:%M:%S"
            )
            # 按大小滚动的文件 Handler（100MB/文件，保留5个）
            root_file_handler = RotatingFileHandler(
                log_full_path_name, "a", 100 * 1024 * 1024, 5, encoding="utf-8"
            )
            root_file_handler.setLevel(root_file_level)
            root_file_handler.setFormatter(root_formatter)
            # ✅ 新增：为文件Handler绑定「用户上下文过滤器」
            root_file_handler.addFilter(self.UserContextFilter(self))
            root_logger.addHandler(root_file_handler)

        # ===================== 第二步：配置业务 Logger（仅 Stream 输出） =====================
        business_logger = logging.getLogger(log_name)
        business_logger.setLevel(logging.DEBUG)  # 业务日志级别设为最低

        # 检查业务 Logger 是否已添加 StreamHandler（避免重复添加）
        has_business_stream_handler = any(
            isinstance(h, logging.StreamHandler) and h.stream is self for h in business_logger.handlers
        )
        if not has_business_stream_handler:
            # ✅ 修改：UI日志格式 - 新增【%(username)s】占位符，自动显示线程用户名
            stream_formatter = logging.Formatter(
                '[%(asctime)s][%(levelname)s][%(username)s]%(module)s:%(lineno)s-%(message)s',
                "%Y-%m-%d %H:%M:%S"
            )
            # 绑定自定义 StreamHandler（输出到 UI）
            stream_handler = logging.StreamHandler(self)
            stream_handler.setLevel(stream_level)  # UI 仅展示 INFO 及以上
            stream_handler.setFormatter(stream_formatter)
            # ✅ 新增：为UI Handler绑定「用户上下文过滤器」
            stream_handler.addFilter(self.UserContextFilter(self))
            business_logger.addHandler(stream_handler)

        return business_logger

output_local_flag = False

if ConfigFileReader.get_val(Constants.ConfigFileKey.LOG_LOCAL_FLAG,
                            section_name=ConfigFileReader.base_section_name) != "0":
    output_local_flag = True

log_dir = Path(SysPathUtils.get_root_dir()).joinpath("logs")
log_dir.mkdir(exist_ok=True)
log_file_path = str(log_dir.joinpath("running_log.txt"))
#  获取业务 Logger 实例（log_name 自定义，比如 "user_score_business"）
# qt_logger = QtLogRedirector.instance()
qt_logger = QtLogRedirectorV2()
LOG = qt_logger.create_logger(
    log_full_path_name=log_file_path,
    log_name="user_task_logger",  # 业务专属 Logger 名称
    root_file_level=logging.INFO,  # 根日志文件捕获所有级别
    stream_level=logging.INFO  # UI 仅展示 INFO 及以上
)
