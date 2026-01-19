import json
import logging
import os
import sqlite3
from abc import abstractmethod
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, Any

from src.utils.sys_path_utils import SysPathUtils


from PyQt5.QtCore import QThread, pyqtSignal

class DBThread(QThread):
    result_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def __init__(self, func, *args):
        super().__init__()
        self.func = func
        self.args = args

    def run(self):
        try:
            res = self.func(*self.args)
            self.result_signal.emit(res)
        except Exception as e:
            self.error_signal.emit(str(e))


data_dir = Path(SysPathUtils.get_data_file_dir())
data_dir.mkdir(parents=True, exist_ok=True)

DB_FILE_PATH = str(data_dir.joinpath("frame_config.db"))
# logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
# logger = logging.getLogger("BaseDB")
SQLITE_CONNECT_ARGS = {"check_same_thread": False}


class BaseDB:
    def __init__(self, logger=logging):
        """实例化时自动初始化数据库（建表+建索引+建触发器）"""
        self.logger = logger
        self.init_database()

    def init_database(self) -> None:
        """初始化数据库：执行建表、索引、触发器SQL，首次运行自动执行"""
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            # 读取并执行修正后的完整建表SQL
            init_sql = self.get_init_sql()
            cursor.executescript(init_sql)
        self.logger.info("数据库初始化完成：表、索引、触发器已创建/更新")

    @abstractmethod
    def get_init_sql(self):
        pass

    @contextmanager
    def get_db_connection(self):
        conn = None
        try:
            conn = sqlite3.connect(str(os.path.join(SysPathUtils.get_config_file_dir(), DB_FILE_PATH)), **SQLITE_CONNECT_ARGS)
            conn.execute("PRAGMA foreign_keys = ON")
            conn.row_factory = sqlite3.Row
            # 开启SQL执行日志
            # conn.set_trace_callback(print)
            yield conn
            conn.commit()
        except sqlite3.Error as e:
            if conn: conn.rollback()
            self.logger.error(f"数据库错误：{str(e)}")
            raise e
        finally:
            if conn: conn.close()

    @staticmethod
    def json_serialize(data: Any) -> str:
        return json.dumps(data, ensure_ascii=False, indent=0)

    @staticmethod
    def json_deserialize(data_str: str) -> Any:
        if not data_str: return {}
        try:
            return json.loads(data_str)
        except:
            return {}

    def dict_from_row(self, row: sqlite3.Row) -> Dict[str, Any]:
        return dict(row) if row else {}
