import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Set, Callable

import psutil

from src.utils.process_utils import ProcessUtils

# 浏览器类型配置（扩展其他浏览器只需新增配置）
BROWSER_CONFIG = {
    "chrome": {
        "process_name_keyword": "chrome.exe",
        "get_processes_func": ProcessUtils.get_app_chrome_processes
    },
    "firefox": {
        "process_name_keyword": "firefox.exe",
        "get_processes_func": ProcessUtils.get_app_firefox_processes
    }
}


@dataclass
class BatchProcessRecord:
    """批次进程记录：按父PID管理进程树"""
    batch_no: str
    browser_type: str  # 新增：标记浏览器类型
    parent_pids: Set[int] = field(default_factory=set)
    pid_groups: Dict[int, Set[int]] = field(default_factory=dict)  # 父PID→子进程树PID
    create_time: float = field(default_factory=time.time)
    is_cleaned: bool = False


class BrowserProcessManager:
    """
    通用浏览器进程管理器：支持Chrome/Firefox（可扩展）
    逻辑：进程池对比 + 父PID追踪 + 进程树管理
    """
    _instances: Dict[str, "BrowserProcessManager"] = {}
    _lock = threading.Lock()

    def __new__(cls, browser_type: str = "chrome"):
        """单例模式：按浏览器类型区分实例"""
        if browser_type not in BROWSER_CONFIG:
            raise ValueError(f"不支持的浏览器类型：{browser_type}，支持类型：{list(BROWSER_CONFIG.keys())}")

        with cls._lock:
            if browser_type not in cls._instances:
                instance = super().__new__(cls)
                # 初始化实例属性
                instance.browser_type = browser_type
                instance.config = BROWSER_CONFIG[browser_type]
                instance.batch_process_map: Dict[str, BatchProcessRecord] = {}
                instance.app_main_pid = os.getpid()
                instance.thread_lock = threading.Lock()
                cls._instances[browser_type] = instance
        return cls._instances[browser_type]

    def register_batch(self, batch_no: str):
        """注册批次"""
        with self.thread_lock:
            if batch_no in self.batch_process_map:
                logging.warning(f"[{self.browser_type}] 批次[{batch_no}]已注册，跳过")
                return
            self.batch_process_map[batch_no] = BatchProcessRecord(
                batch_no=batch_no,
                browser_type=self.browser_type
            )
            logging.info(f"[{self.browser_type}] 批次[{batch_no}]已注册")

    def capture_new_browser_processes(self, batch_no: str) -> Callable:
        """
        核心：捕获批次操作后新增的浏览器进程组
        返回：捕获器函数（外部执行创建操作后调用）
        """
        # 步骤1：获取操作前的浏览器进程池（基准）
        before_pids = self._get_all_browser_pids()

        def _capture():
            """内部捕获逻辑"""
            time.sleep(0.5)  # 等待进程创建完成

            # 步骤2：对比新增PID
            after_pids = self._get_all_browser_pids()
            new_pids = after_pids - before_pids
            if not new_pids:
                logging.warning(f"[{self.browser_type}] 批次[{batch_no}]未捕获到新增进程")
                return set(), {}

            # 步骤3：溯源父PID，构建进程树
            parent_pids = set()
            pid_groups = {}
            for pid in new_pids:
                try:
                    proc = psutil.Process(pid)
                    parent_pid = proc.ppid()
                    if self._is_app_related_pid(parent_pid):
                        parent_pids.add(parent_pid)
                        pid_tree = self._get_process_tree(pid)
                        pid_groups[parent_pid] = pid_tree
                        logging.info(
                            f"[{self.browser_type}] 批次[{batch_no}]捕获进程组：父PID={parent_pid}，进程树={pid_tree}"
                        )
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # 步骤4：更新批次记录
            with self.thread_lock:
                if batch_no not in self.batch_process_map:
                    return parent_pids, pid_groups
                batch_record = self.batch_process_map[batch_no]
                batch_record.parent_pids.update(parent_pids)
                batch_record.pid_groups.update(pid_groups)

            return parent_pids, pid_groups

        return _capture

    def clean_batch_processes(self, batch_no: str, force: bool = True) -> bool:
        """按批次清理进程树"""
        with self.thread_lock:
            if batch_no not in self.batch_process_map:
                logging.warning(f"[{self.browser_type}] 批次[{batch_no}]不存在，无需清理")
                return True
            batch_record = self.batch_process_map[batch_no]
            if batch_record.is_cleaned:
                logging.info(f"[{self.browser_type}] 批次[{batch_no}]已清理，跳过")
                return True
            batch_record.is_cleaned = True

        success = True
        # 遍历父PID清理进程树
        for parent_pid in batch_record.parent_pids:
            pid_tree = batch_record.pid_groups.get(parent_pid, set())
            if not pid_tree:
                pid_tree = self._get_process_tree(parent_pid)
                pid_tree = {p for p in pid_tree if self._is_browser_process(p)}

            if pid_tree:
                logging.info(
                    f"[{self.browser_type}] 批次[{batch_no}]清理父PID={parent_pid}的进程树：{pid_tree}"
                )
                for pid in pid_tree:
                    if not self._kill_process(pid):
                        success = False
                if parent_pid != self.app_main_pid:
                    self._kill_process(parent_pid)
            else:
                logging.warning(
                    f"[{self.browser_type}] 批次[{batch_no}]父PID={parent_pid}无进程树可清理"
                )

        # 兜底清理
        if not success and force:
            logging.warning(f"[{self.browser_type}] 批次[{batch_no}]清理不彻底，执行应用级兜底清理")
            self._clean_app_browser_processes()

        # 移除批次记录
        with self.thread_lock:
            del self.batch_process_map[batch_no]
        logging.info(f"[{self.browser_type}] 批次[{batch_no}]进程清理完成")
        return success

    def clean_all_batch_processes(self):
        """清理所有批次"""
        with self.thread_lock:
            batch_nos = list(self.batch_process_map.keys())
        for batch_no in batch_nos:
            self.clean_batch_processes(batch_no, force=True)
        self._clean_app_browser_processes()

    def _get_all_browser_pids(self) -> Set[int]:
        """获取当前系统中所有目标浏览器进程PID"""
        return self.config["get_processes_func"](self.app_main_pid)

    def _is_app_related_pid(self, pid: int) -> bool:
        """判断PID是否归属当前应用"""
        try:
            current_pid = pid
            while current_pid not in (0, 1):
                if current_pid == self.app_main_pid:
                    return True
                try:
                    current_pid = psutil.Process(current_pid).ppid()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    break
            return False
        except Exception:
            return False

    def _get_process_tree(self, pid: int) -> Set[int]:
        """递归获取进程树（包含自身）"""
        process_tree = set()
        try:
            parent_proc = psutil.Process(pid)
            children = parent_proc.children(recursive=True)
            process_tree = {p.pid for p in children}
            process_tree.add(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        return process_tree

    def _kill_process(self, pid: int) -> bool:
        """杀死单个进程"""
        try:
            proc = psutil.Process(pid)
            if proc.is_running():
                proc.kill()
                logging.info(f"[{self.browser_type}] 杀死进程：PID={pid}")
            return True
        except psutil.NoSuchProcess:
            return True
        except Exception as e:
            logging.warning(f"[{self.browser_type}] 杀死进程PID={pid}失败：{e}")
            return False

    def _clean_app_browser_processes(self):
        """清理当前应用下的所有目标浏览器进程"""
        all_browser_pids = self._get_all_browser_pids()
        app_browser_pids = {p for p in all_browser_pids if self._is_app_related_pid(p)}
        for pid in app_browser_pids:
            self._kill_process(pid)
        logging.info(
            f"[{self.browser_type}] 应用级兜底清理：杀死{len(app_browser_pids)}个进程"
        )

    def _is_browser_process(self, pid: int) -> bool:
        """判断PID是否为目标浏览器进程"""
        try:
            return self.config["process_name_keyword"] in psutil.Process(pid).name().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False


# 全局实例（保持原有API兼容性）
chrome_process_manager = BrowserProcessManager("chrome")
firefox_process_manager = BrowserProcessManager("firefox")
