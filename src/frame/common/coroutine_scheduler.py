import asyncio
import logging
from asyncio import Task
from typing import Coroutine, List, Optional, Dict, Any, Callable, Tuple

from shortuuid import ShortUUID

from src.utils.async_utils import get_event_loop_safely

# 定义回调函数的类型注解
TaskCallback = Callable[[str, str, Any, Optional[Exception], Tuple, Dict], None]
"""
回调函数签名要求：
:param task_id: 任务ID
:param status: 任务状态（pending/completed/failed/cancelled/not_found）
:param result: 任务返回结果（失败/取消时为None）
:param exception: 异常对象（成功时为None）
:param args: tuple形参
:param kwargs: dict形参
"""


# @singleton
class CoroutineScheduler:
    """
    支持任务完成回调的协程调度器：
    1. 单个任务延迟调度 + 回调
    2. 多个任务间隔启动（并行） + 回调
    3. 全局/单个/批次级回调，异常隔离
    4. 结果记录 + 回调触发 + 任务管理
    """

    def __init__(self, batch_no: str):
        self.batch_no = batch_no
        self._loop = asyncio.get_event_loop()
        self._callbacks: Dict[str, List[TaskCallback]] = {}  # 任务ID -> 回调列表
        self._global_callbacks: List[TaskCallback] = []  # 全局回调
        self._results: Dict[str, Any] = {}  # 任务ID -> 结果/异常
        self._tasks: List[Task] = []  # 任务对象列表

    # ------------------------------ 回调管理 ------------------------------
    def add_global_callback(self, callback: TaskCallback):
        if callback not in self._global_callbacks:
            self._global_callbacks.append(callback)

    def add_task_callback(self, task_id: str, callback: TaskCallback):
        if task_id not in self._callbacks:
            self._callbacks[task_id] = []
        if callback not in self._callbacks[task_id]:
            self._callbacks[task_id].append(callback)

    def _trigger_callbacks(self, task_id: str, status: str, result: Any, exc: Optional[Exception], *args, **kwargs):
        """触发回调（异常隔离）"""
        # 触发全局回调
        for cb in self._global_callbacks:
            try:
                cb(task_id, status, result, exc, args, kwargs)
            except Exception as e:
                logging.debug(f"全局回调执行失败（任务 {task_id}）: {e}")
        # 触发任务专属回调
        if task_id in self._callbacks:
            for cb in self._callbacks[task_id]:
                try:
                    cb(task_id, status, result, exc, args, kwargs)
                except Exception as e:
                    logging.debug(f"任务 {task_id} 回调执行失败: {e}")
            del self._callbacks[task_id]

    # ------------------------------ 核心：TaskGroup 管理任务 ------------------------------
    async def add_delayed_task(
            self,
            coro_func: Callable[..., Coroutine],
            *args,
            delay: float = 0.0,
            task_id: Optional[str] = None,
            callback: Optional[TaskCallback] = None,
            **kwargs
    ) -> str:
        """
        添加延迟任务
        若要交由TaskGroup管理，则参考add_tasks_with_interval方法！
        :param coro_func: 协程函数（如 demo_task）
        :param args: 协程函数的位置参数
        :param delay: 延迟时间（秒）
        :param task_id: 自定义任务ID
        :param callback: 任务回调
        :param kwargs: 协程函数的关键字参数
        :return: 任务ID
        """
        task_id = task_id or f"{self.batch_no}_{ShortUUID().random(length=8)}"
        if callback:
            self.add_task_callback(task_id, callback)

        async with asyncio.TaskGroup() as tg:
            # 任务执行包装器
            async def _wrapper():
                try:
                    if delay > 0:
                        await asyncio.sleep(delay)
                    # 执行目标协程
                    result = await coro_func(*args, **kwargs)
                    self._results[task_id] = {"status": "completed", "result": result}
                    self._trigger_callbacks(task_id, "completed", result, None, *args, **kwargs)
                except asyncio.CancelledError as e:
                    self._results[task_id] = {"status": "cancelled", "exception": e}
                    self._trigger_callbacks(task_id, "cancelled", None, e, *args, **kwargs)
                except Exception as e:
                    self._results[task_id] = {"status": "failed", "exception": e}
                    self._trigger_callbacks(task_id, "failed", None, e, *args, **kwargs)

            # 直接创建任务（若需加入自定义TaskGroup，可扩展参数）
            task = tg.create_task(_wrapper())
            # 任务列表
            self._tasks.append(task)

        return task_id

    async def add_tasks_with_interval(
            self,
            coro_funcs: List[Tuple[Callable[..., Coroutine], tuple, dict]],
            interval: float = 1.0,
            initial_delay: float = 0.0,
            callback: Optional[TaskCallback] = None
    ) -> List[str]:
        """
        按间隔启动批次任务（核心：用TaskGroup管理，无需批次主任务）
        :param coro_funcs: [(协程函数, 位置参数元组, 关键字参数字典), ...]
        :param interval: 任务启动间隔
        :param initial_delay: 初始延迟
        :param batch_no: 批次ID
        :param callback: 回调函数
        :return: 任务ID列表
        """
        task_ids = []
        # 核心：创建TaskGroup管理该批次所有子任务
        async with asyncio.TaskGroup() as tg:
            # 初始延迟
            if initial_delay > 0:
                await asyncio.sleep(initial_delay)

            # 按间隔启动子任务（TaskGroup自动管控）
            for idx, (func, args, kwargs) in enumerate(coro_funcs):
                task_id = f"{self.batch_no}_task_{idx}"
                task_ids.append(task_id)
                if callback:
                    self.add_task_callback(task_id, callback)

                # 子任务包装器
                async def _task_wrapper(task_id: str, func, args, kwargs):
                    try:
                        result = await func(*args, **kwargs)
                        self._results[task_id] = {"status": "completed", "result": result}
                        self._trigger_callbacks(task_id, "completed", result, None, *args, **kwargs)
                    except asyncio.CancelledError as e:
                        self._results[task_id] = {"status": "cancelled", "exception": e}
                        self._trigger_callbacks(task_id, "cancelled", None, e, *args, **kwargs)
                    except Exception as e:
                        self._results[task_id] = {"status": "failed", "exception": e}
                        self._trigger_callbacks(task_id, "failed", None, e, *args, **kwargs)

                # 关键：用TaskGroup创建任务（自动加入管控）
                task = tg.create_task(_task_wrapper(task_id, func, args, kwargs))
                # 任务列表
                self._tasks.append(task)
                # 间隔（最后一个任务无需间隔）
                if idx < len(coro_funcs) - 1:
                    await asyncio.sleep(interval)

        # TaskGroup退出上下文时，已自动等待所有子任务完成
        return task_ids

    # ------------------------------ 任务管控 ------------------------------
    def cancel(self):
        """取消整个批次的任务（TaskGroup一键取消）"""
        for task in self._tasks:
            task.cancel()  # 取消任务
        logging.info(f"批次 {self.batch_no} 已取消")

    def get_task_result(self, task_id: str) -> Dict[str, Any]:
        return self._results.get(task_id, {"status": "not_found"})

    def get_batch_results(self, batch_no: str) -> Dict[str, Any]:
        """获取批次所有任务结果"""
        return {tid: res for tid, res in self._results.items() if tid.startswith(f"{batch_no}_")}


# ------------------------------ 测试示例 ------------------------------
def global_callback(task_id: str, status: str, result: Any, exception: Optional[Exception]):
    """全局回调"""
    logging.debug(f"\n【全局回调】任务 {task_id} 状态: {status}")
    if status == "completed":
        logging.debug(f"【全局回调】任务 {task_id} 返回值: {result}")
    elif status in ["failed", "cancelled"]:
        logging.debug(f"【全局回调】任务 {task_id} 异常: {exception}")


async def demo_task(name: str):
    """示例任务"""
    logging.debug(f"\n启动任务: {name} - {asyncio.current_task()}")
    await asyncio.sleep(2)
    if "异常" in name:
        raise ValueError(f"{name} 主动抛出异常")
    return f"{name} 执行完成，返回值: {asyncio.current_task()}"


async def main():
    logging.debug("===== 测试取消任务（无警告） =====")
    async with CoroutineScheduler() as scheduler:
        # 添加全局回调
        scheduler.add_global_callback(global_callback)

        # 测试1：添加延迟任务并取消（核心修改：传入协程函数+参数，而非已创建的协程）
        # test_task_id = await scheduler.add_delayed_task(
        #     demo_task,  # 协程函数
        #     "待取消任务",  # demo_task的参数
        #     delay=5,  # 延迟参数
        # )
        # logging.debug(f"添加延迟任务，ID: {test_task_id}")
        # # 2秒后取消
        # await asyncio.sleep(2)
        # scheduler.cancel_task(test_task_id)

        # 测试2：批次任务（传入协程函数+参数列表）
        await asyncio.sleep(1)
        batch_no = "normal_batch"
        await scheduler.add_tasks_with_interval(
            batch_no,
            coro_funcs=[
                (demo_task, ("正常任务1",), {}),  # (函数, 位置参数, 关键字参数)
                (demo_task, ("正常任务2",), {})
            ],
            initial_delay=1,
            interval=1,
        )

        # 等待足够时间观察结果
        # await asyncio.sleep(6)
        await scheduler.wait_all_tasks_done()


if __name__ == "__main__":
    # 可选：关闭所有RuntimeWarning（如需彻底消除）
    # import warnings
    # warnings.filterwarnings("ignore", category=RuntimeWarning)
    get_event_loop_safely().run_until_complete(main())
