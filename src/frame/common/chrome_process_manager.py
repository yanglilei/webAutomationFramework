import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Dict, Set, Tuple, Callable

import psutil

from src.utils.process_utils import ProcessUtils


@dataclass
class BatchProcessRecord:
    """批次进程记录：按父PID管理进程树"""
    batch_no: str
    parent_pids: Set[int] = field(default_factory=set)  # 新增：存储进程组的父PID（核心）
    chrome_pid_groups: Dict[int, Set[int]] = field(default_factory=dict)  # 父PID→子进程树PID
    create_time: float = field(default_factory=time.time)
    is_cleaned: bool = False


class ChromeProcessManager:
    """
    改造版：基于进程池对比+父PID追踪进程组
    记录操作前的 Chrome 进程池 → 操作后对比新增进程 → 溯源新增进程的父 PID → 按父 PID 管理进程树
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance.batch_process_map: Dict[str, BatchProcessRecord] = {}
                    cls._instance.app_main_pid = os.getpid()
                    cls._instance.thread_lock = threading.Lock()
        return cls._instance

    def register_batch(self, batch_no: str):
        """注册批次（无需要父PID，后续自动捕获）"""
        with self.thread_lock:
            if batch_no in self.batch_process_map:
                logging.warning(f"批次[{batch_no}]已注册，跳过")
                return
            self.batch_process_map[batch_no] = BatchProcessRecord(batch_no=batch_no)
            logging.info(f"批次[{batch_no}]已注册")

    def capture_new_chrome_processes(self, batch_no: str) -> Callable:
        """
        核心：捕获批次操作后新增的Chrome进程组
        逻辑：
        1. 记录操作前的Chrome进程池
        2. （外部执行创建Context/Browser操作）
        3. 记录操作后的Chrome进程池，对比得到新增PID
        4. 溯源新增PID的父PID，构建进程树
        """
        # 步骤1：获取操作前的Chrome进程池（基准）
        before_pids = self._get_all_chrome_pids()

        # 步骤2：返回"捕获器"函数（外部执行创建操作后调用）
        def _capture():
            # 等待进程创建完成（必要的延迟）
            time.sleep(0.5)

            # 步骤3：获取操作后的Chrome进程池，对比新增PID
            after_pids = self._get_all_chrome_pids()
            new_pids = after_pids - before_pids
            if not new_pids:
                logging.warning(f"批次[{batch_no}]未捕获到新增Chrome进程")
                return set(), {}

            # 步骤4：溯源新增PID的父PID，构建进程树
            parent_pids = set()
            pid_groups = {}  # 父PID → 子进程树PID
            for pid in new_pids:
                try:
                    # 获取进程的父PID
                    proc = psutil.Process(pid)
                    parent_pid = proc.ppid()
                    # 仅保留归属当前应用的进程（父PID是应用内进程）
                    if self._is_app_related_pid(parent_pid):
                        parent_pids.add(parent_pid)
                        # 构建该父PID的进程树
                        pid_tree = self._get_process_tree(pid)
                        pid_groups[parent_pid] = pid_tree
                        logging.info(f"批次[{batch_no}]捕获Chrome进程组：父PID={parent_pid}，进程树={pid_tree}")
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # 步骤5：更新批次记录
            with self.thread_lock:
                if batch_no not in self.batch_process_map:
                    return parent_pids, pid_groups
                batch_record = self.batch_process_map[batch_no]
                batch_record.parent_pids.update(parent_pids)
                batch_record.chrome_pid_groups.update(pid_groups)

            return parent_pids, pid_groups

        return _capture

    def _get_all_chrome_pids(self) -> Set[int]:
        """获取当前系统中所有Chrome进程PID"""
        # chrome_pids = set()
        # try:
        #     for proc in psutil.process_iter(['pid', 'name']):
        #         if proc.info['name'] and 'chrome.exe' in proc.info['name'].lower():
        #             chrome_pids.add(proc.info['pid'])
        # except Exception as e:
        #     logging.error(f"获取Chrome进程池失败：{e}", exc_info=True)
        chrome_pids = ProcessUtils.get_app_chrome_processes(self.app_main_pid)
        return chrome_pids

    def _is_app_related_pid(self, pid: int) -> bool:
        """判断PID是否归属当前应用（避免捕获其他Chrome进程）"""
        try:
            # 递归溯源父PID，直到根进程
            current_pid = pid
            while current_pid != 0 and current_pid != 1:
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

    def clean_batch_processes(self, batch_no: str, force: bool = True) -> bool:
        """按批次清理：杀死所有父PID对应的进程树"""
        with self.thread_lock:
            if batch_no not in self.batch_process_map:
                logging.warning(f"批次[{batch_no}]不存在，无需清理")
                return True
            batch_record = self.batch_process_map[batch_no]
            if batch_record.is_cleaned:
                logging.info(f"批次[{batch_no}]已清理，跳过")
                return True
            batch_record.is_cleaned = True

        success = True
        # 遍历所有父PID，杀死对应的进程树
        for parent_pid in batch_record.parent_pids:
            # 1. 获取该父PID对应的所有进程树
            pid_tree = batch_record.chrome_pid_groups.get(parent_pid, set())
            if not pid_tree:
                # 兜底：重新扫描该父PID的进程树
                pid_tree = self._get_process_tree(parent_pid)
                # 筛选Chrome进程
                pid_tree = {p for p in pid_tree if self._is_chrome_process(p)}

            # 2. 杀死进程树
            if pid_tree:
                logging.info(f"批次[{batch_no}]清理父PID={parent_pid}的Chrome进程树：{pid_tree}")
                for pid in pid_tree:
                    if not self._kill_process(pid):
                        success = False
                self._kill_process(parent_pid)
            else:
                logging.warning(f"批次[{batch_no}]父PID={parent_pid}无Chrome进程树可清理")

        # 3. 最终兜底：清理当前应用下所有残留Chrome进程（可选）
        if not success and force:
            logging.warning(f"批次[{batch_no}]清理不彻底，执行应用级兜底清理")
            self._clean_app_chrome_processes()

        # 4. 移除批次记录
        with self.thread_lock:
            del self.batch_process_map[batch_no]
        logging.info(f"批次[{batch_no}]进程清理完成")
        return success

    def _kill_process(self, pid: int) -> bool:
        """杀死单个进程（返回是否成功）"""
        try:
            proc = psutil.Process(pid)
            if proc.is_running():
                proc.kill()
                logging.info(f"杀死Chrome进程：PID={pid}")
            return True
        except psutil.NoSuchProcess:
            return True
        except Exception as e:
            logging.warning(f"杀死进程PID={pid}失败：{e}")
            return False

    def _clean_app_chrome_processes(self):
        """清理当前应用下的所有Chrome进程（兜底）"""
        all_chrome_pids = self._get_all_chrome_pids()
        app_chrome_pids = {p for p in all_chrome_pids if self._is_app_related_pid(p)}
        for pid in app_chrome_pids:
            self._kill_process(pid)
        logging.info(f"应用级兜底清理：杀死{len(app_chrome_pids)}个Chrome进程")

    def _is_chrome_process(self, pid: int) -> bool:
        """判断PID是否为Chrome进程"""
        try:
            return 'chrome.exe' in psutil.Process(pid).name().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def clean_all_batch_processes(self):
        """清理所有批次"""
        with self.thread_lock:
            batch_nos = list(self.batch_process_map.keys())
        for batch_no in batch_nos:
            self.clean_batch_processes(batch_no, force=True)
        # 最终兜底
        self._clean_app_chrome_processes()


# 全局实例
chrome_process_manager = ChromeProcessManager()
