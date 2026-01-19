# db_task_manager.py
import traceback
import uuid
from typing import Callable, Dict, Any, Optional, Tuple

from PyQt5.QtCore import QThread, pyqtSignal, QObject

from src.frame.common.decorator.singleton import singleton
from src.frame.common.exceptions import BusinessException


class WorkerSignals(QObject):
    """子线程信号定义（与UI通信的唯一通道）"""
    # 任务完成信号：参数(状态, 消息, 数据)
    finished = pyqtSignal(bool, str, object)
    # 进度更新信号（可选，如批量操作）：参数(进度值(0-100), 进度描述)
    progress = pyqtSignal(int, str)


class Worker(QThread):
    """通用数据库工作线程（单任务/复用）"""

    def __init__(self, task_id: str, func: Callable, *args, **kwargs):
        super().__init__()
        self.task_id = task_id  # 任务唯一标识（区分多任务）
        self.func = func  # 要执行的数据库函数（如分页查询、新增任务）
        self.signals = WorkerSignals()  # 信号实例
        self.args = args
        self.kwargs = kwargs

    def run(self):
        """线程执行入口（自动调用，无需手动触发）"""
        try:
            # 执行数据库操作（子线程核心逻辑）
            # result = self.db_func_info[0](*self.db_func_info[1:]) if len(self.db_func_info) > 1 else self.db_func_info[0]()
            result = self.func(*self.args, **self.kwargs)
            # 任务完成：发送结果到UI主线程
            self.signals.finished.emit(True, "succ", result)
        except BusinessException as e:
            # 业务异常：发送异常信息到UI主线程
            self.signals.finished.emit(False, e.error_desc, None)
        except Exception as e:
            # 捕获所有异常，避免线程崩溃
            err_msg = str(e)
            err_trace = traceback.format_exc()
            self.signals.finished.emit(False, err_msg, err_trace)

    def stop(self):
        """安全停止线程（可选）"""
        if self.isRunning():
            self.quit()
            self.wait(1000)  # 等待1秒，超时强制退出


@singleton
class AsyncTaskScheduler(QObject):
    """异步数据库任务调度器（UI层唯一调用入口，优雅封装）"""

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)
        self.workers: Dict[str, Worker] = {}  # 管理所有运行中的线程

    def submit_task(self,
                    func: Callable,
                    /,
                    *args,
                    task_id: Optional[str] = None,
                    finished_callback: Optional[Callable] = None,
                    progress_callback: Optional[Callable] = None,
                    **kwargs) -> str:
        """
        提交数据库异步任务（核心方法，UI层仅需调用此方法）
        :param func: 要执行的数据库函数及参数（如：(db.task_tmpl_dao.get_task_page_data, {}, 1, 10)）
        :param task_id: 任务ID（可选，自动生成唯一ID）
        :param finished_callback: 任务完成回调（UI主线程执行）
        :param progress_callback: 进度更新回调（可选）
        :return: 任务ID（用于追踪/取消任务）
        """
        # 生成唯一任务ID（区分多并发任务）
        task_id = task_id or f"db_task_{uuid.uuid4().hex[:8]}"

        # 创建工作线程
        worker = Worker(task_id, func, *args, **kwargs)
        self.workers[task_id] = worker

        # 绑定信号与回调（自动在UI主线程执行）
        if finished_callback:
            worker.signals.finished.connect(finished_callback)
        if progress_callback:
            worker.signals.progress.connect(progress_callback)

        # 线程结束后清理（避免内存泄漏）
        worker.finished.connect(lambda: self._clean_worker(task_id))

        # 启动线程
        worker.start()
        return task_id

    def cancel_task(self, task_id: str) -> bool:
        """取消指定任务"""
        if task_id in self.workers:
            worker = self.workers[task_id]
            worker.stop()
            del self.workers[task_id]
            return True
        return False

    def _clean_worker(self, task_id: str):
        """线程结束后清理资源"""
        if task_id in self.workers:
            del self.workers[task_id]
