import logging
import traceback
from datetime import datetime
from typing import Dict, Optional, List

from PyQt5.QtCore import QMutex, QMutexLocker
from PyQt5.QtWidgets import QMessageBox

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.schedulers.qt import QtScheduler
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED, JobEvent

from src.frame.common.decorator.singleton import singleton
from src.frame.dao.db_manager import db


@singleton
class SchedulerManager:
    """
    定时任务调度管理器
    核心功能：
    1. 单例模式，全局唯一调度器实例
    2. 启动/停止单个定时任务
    3. 全局启动/关闭调度器
    4. 任务执行状态监控与日志记录
    5. 自动同步数据库任务状态
    """
    # _instance: Optional["SchedulerManager"] = None
    _lock = QMutex()  # 线程安全锁

    def __init__(self, logger):
        """初始化调度器及相关状态"""
        self.logger = logger
        self.db = db
        # 1. 初始化APScheduler（Qt适配版）
        self.scheduler = QtScheduler()
        # 2. 运行中任务映射：{scheduled_task_id: job_id}
        self.running_tasks: Dict[int, str] = {}
        # 3. 日志器
        self.logger = logging.getLogger("SchedulerManager")
        # 4. 注册任务执行事件监听
        self._register_scheduler_listeners()
        # 5. 启动时自动加载已启用的任务（可选）
        self._load_enabled_tasks()


    def _register_scheduler_listeners(self):
        """注册调度器事件监听器（监控任务执行状态）"""

        def job_executed_listener(event: JobEvent):
            """任务执行完成监听"""
            task_id = self._get_task_id_from_job_id(event.job_id)
            if task_id:
                self.logger.info(
                    f"定时任务 {task_id} 执行完成 | "
                    f"耗时：{event.retval['run_time']:.2f}s | "
                    f"成功数：{event.retval['success_count']} | "
                    f"失败数：{event.retval['fail_count']}"
                )

        def job_error_listener(event: JobEvent):
            """任务执行异常监听"""
            task_id = self._get_task_id_from_job_id(event.job_id)
            if task_id:
                self.logger.error(
                    f"定时任务 {task_id} 执行异常 | "
                    f"异常类型：{type(event.exception).__name__} | "
                    f"异常信息：{str(event.exception)} | "
                    f"堆栈：{traceback.format_exc()}"
                )
                # 可选：发送告警、标记任务状态等

        # 注册监听器
        self.scheduler.add_listener(job_executed_listener, EVENT_JOB_EXECUTED)
        self.scheduler.add_listener(job_error_listener, EVENT_JOB_ERROR)

    def _get_task_id_from_job_id(self, job_id: str) -> Optional[int]:
        """从APScheduler的job_id解析出定时任务ID"""
        try:
            # job_id格式：scheduled_task_123
            return int(job_id.replace("scheduled_task_", ""))
        except (ValueError, AttributeError):
            return None

    def _load_enabled_tasks(self):
        """启动时自动加载已启用且未运行的定时任务（可选）"""
        try:
            # 查询所有已启用但未运行的定时任务
            enabled_tasks = self.db.scheduled_task_dao.get_scheduled_task_list({
                "is_enabled": 1,
                "is_running": 0
            })
            self.logger.info(f"发现 {len(enabled_tasks)} 个已启用的定时任务，准备自动加载")

            for task in enabled_tasks:
                # 异步启动（避免阻塞UI）
                self.start_task(task["id"], auto_load=True)
        except Exception as e:
            self.logger.error(f"自动加载已启用任务失败：{str(e)}")

    def _build_trigger(self, trigger_type: str, trigger_params: Dict) -> object:
        """构建APScheduler触发器"""
        try:
            if trigger_type == "interval":
                return IntervalTrigger(**trigger_params)
            elif trigger_type == "cron":
                return CronTrigger(**trigger_params)
            elif trigger_type == "date":
                return DateTrigger(**trigger_params)
            else:
                raise ValueError(f"不支持的触发器类型：{trigger_type}")
        except Exception as e:
            self.logger.error(f"构建触发器失败：{str(e)} | 参数：{trigger_params}")
            raise

    def _execute_batch_tasks(self, batch_ids: List[int], task_id: int) -> Dict:
        """
        执行关联的普通任务（核心业务逻辑）
        :param batch_ids: 关联的普通任务ID列表
        :param task_id: 定时任务ID
        :return: 执行结果统计
        """
        success_count = 0
        fail_count = 0
        start_time = datetime.now()

        for batch_id in batch_ids:
            try:
                self.logger.info(f"开始执行普通任务 | 定时任务ID：{task_id} | 普通任务ID：{batch_id}")

                # 1. 查询普通任务详情（可根据业务扩展）
                batch_info = self.db.task_batch_dao.get_task_batch_by_id(batch_id)
                if not batch_info:
                    raise ValueError(f"普通任务 {batch_id} 不存在")

                # 2. TODO: 替换为你的实际业务执行逻辑
                # 示例：run_batch_task(batch_info)
                # 这里仅做日志记录，需根据你的tb_task_batch表逻辑实现
                self.logger.info(f"普通任务执行成功 | 定时任务ID：{task_id} | 普通任务ID：{batch_id}")
                success_count += 1

            except Exception as e:
                self.logger.error(
                    f"普通任务执行失败 | 定时任务ID：{task_id} | 普通任务ID：{batch_id} | "
                    f"异常：{str(e)}"
                )
                fail_count += 1

        # 计算执行耗时
        run_time = (datetime.now() - start_time).total_seconds()

        # 返回执行结果（供事件监听器使用）
        return {
            "run_time": run_time,
            "success_count": success_count,
            "fail_count": fail_count,
            "total_count": len(batch_ids)
        }

    def start_task(self, task_id: int, auto_load: bool = False) -> bool:
        """
        启动单个定时任务
        :param task_id: 定时任务ID
        :param auto_load: 是否为启动时自动加载（不弹UI提示）
        :return: 启动结果
        """
        with QMutexLocker(self._lock):
            try:
                # 1. 查询定时任务详情
                task_data = self.db.scheduled_task_dao.get_scheduled_task_by_id(task_id)
                if not task_data:
                    raise ValueError(f"定时任务 {task_id} 不存在")

                # 2. 状态校验
                if task_data["is_running"] == 1:
                    if not auto_load:
                        raise ValueError("任务已处于运行状态")
                    self.logger.warning(f"定时任务 {task_id} 已运行，跳过自动加载")
                    return False

                if task_data["is_enabled"] == 0:
                    if not auto_load:
                        raise ValueError("任务未启用，无法启动")
                    self.logger.warning(f"定时任务 {task_id} 未启用，跳过自动加载")
                    return False

                # 3. 校验关联的普通任务
                batch_ids = task_data["task_batch_ids"]
                if not isinstance(batch_ids, list) or len(batch_ids) == 0:
                    raise ValueError("未关联任何普通任务，无法启动")

                # 4. 构建触发器
                trigger = self._build_trigger(
                    trigger_type=task_data["trigger_type"],
                    trigger_params=task_data["trigger_params"]
                )

                # 5. 定义任务执行函数（绑定定时任务ID）
                def task_executor():
                    return self._execute_batch_tasks(batch_ids, task_id)

                # 6. 添加任务到调度器
                job_id = f"scheduled_task_{task_id}"
                job = self.scheduler.add_job(
                    func=task_executor,
                    trigger=trigger,
                    id=job_id,
                    name=task_data["task_name"],
                    replace_existing=True,  # 覆盖已存在的同名任务
                    misfire_grace_time=300  # 任务错过执行的容忍时间（秒）
                )

                # 7. 更新状态（内存+数据库）
                self.running_tasks[task_id] = job.id
                self.db.scheduled_task_dao.update_task_status(
                    task_id=task_id,
                    is_running=1,
                    is_enabled=1  # 启动时自动启用
                )

                # 8. 日志/提示
                self.logger.info(
                    f"定时任务启动成功 | ID：{task_id} | 名称：{task_data['task_name']} | "
                    f"关联普通任务数：{len(batch_ids)} | 触发器类型：{task_data['trigger_type']}"
                )
                if not auto_load:
                    QMessageBox.information(None, "启动成功",
                                            f"定时任务「{task_data['task_name']}」已启动！")
                return True

            except Exception as e:
                error_msg = f"定时任务启动失败 | ID：{task_id} | 异常：{str(e)}"
                self.logger.error(error_msg)
                if not auto_load:
                    QMessageBox.warning(None, "启动失败", error_msg)
                return False

    def stop_task(self, task_id: int) -> bool:
        """
        停止单个定时任务
        :param task_id: 定时任务ID
        :return: 停止结果
        """
        with QMutexLocker(self._lock):
            try:
                # 1. 状态校验
                if task_id not in self.running_tasks:
                    raise ValueError("任务未运行，无需停止")

                # 2. 从调度器移除任务
                job_id = self.running_tasks[task_id]
                self.scheduler.remove_job(job_id)

                # 3. 更新状态（内存+数据库）
                del self.running_tasks[task_id]
                self.db.scheduled_task_dao.update_task_status(task_id=task_id, is_running=0)

                # 4. 日志/提示
                task_data = self.db.scheduled_task_dao.get_scheduled_task_by_id(task_id)
                task_name = task_data["task_name"] if task_data else f"ID:{task_id}"
                self.logger.info(f"定时任务停止成功 | ID：{task_id} | 名称：{task_name}")
                QMessageBox.information(None, "停止成功", f"定时任务「{task_name}」已停止！")
                return True

            except Exception as e:
                error_msg = f"定时任务停止失败 | ID：{task_id} | 异常：{str(e)}"
                self.logger.error(error_msg)
                QMessageBox.warning(None, "停止失败", error_msg)
                return False

    def start_all_tasks(self) -> Dict[str, List[int]]:
        """
        启动所有已启用的定时任务
        :return: 执行结果 {"success": [成功ID列表], "failed": [失败ID列表]}
        """
        result = {"success": [], "failed": []}
        try:
            enabled_tasks = self.db.scheduled_task_dao.get_scheduled_task_list({"is_enabled": 1})
            self.logger.info(f"开始启动所有已启用任务 | 总数：{len(enabled_tasks)}")

            for task in enabled_tasks:
                if self.start_task(task["id"], auto_load=True):
                    result["success"].append(task["id"])
                else:
                    result["failed"].append(task["id"])

            self.logger.info(
                f"批量启动任务完成 | 成功：{len(result['success'])} | "
                f"失败：{len(result['failed'])} | 失败列表：{result['failed']}"
            )
            QMessageBox.information(None, "批量启动完成",
                                    f"成功启动 {len(result['success'])} 个任务，失败 {len(result['failed'])} 个")
            return result

        except Exception as e:
            self.logger.error(f"批量启动任务失败：{str(e)}")
            QMessageBox.critical(None, "批量启动失败", str(e))
            return result

    def stop_all_tasks(self) -> Dict[str, List[int]]:
        """
        停止所有运行中的定时任务
        :return: 执行结果 {"success": [成功ID列表], "failed": [失败ID列表]}
        """
        result = {"success": [], "failed": []}
        with QMutexLocker(self._lock):
            try:
                running_task_ids = list(self.running_tasks.keys())
                self.logger.info(f"开始停止所有运行中任务 | 总数：{len(running_task_ids)}")

                for task_id in running_task_ids:
                    if self.stop_task(task_id):
                        result["success"].append(task_id)
                    else:
                        result["failed"].append(task_id)

                self.logger.info(
                    f"批量停止任务完成 | 成功：{len(result['success'])} | "
                    f"失败：{len(result['failed'])} | 失败列表：{result['failed']}"
                )
                QMessageBox.information(None, "批量停止完成",
                                        f"成功停止 {len(result['success'])} 个任务，失败 {len(result['failed'])} 个")
                return result

            except Exception as e:
                self.logger.error(f"批量停止任务失败：{str(e)}")
                QMessageBox.critical(None, "批量停止失败", str(e))
                return result

    def start_scheduler(self):
        """启动全局调度器（应用启动时调用）"""
        if not self.scheduler.running:
            self.scheduler.start()
            self.logger.info("全局调度器已启动")

    def shutdown_scheduler(self, wait: bool = True):
        """
        关闭全局调度器（应用退出时调用）
        :param wait: 是否等待正在执行的任务完成
        """
        if self.scheduler.running:
            # 先停止所有运行中的任务
            self.stop_all_tasks()
            # 关闭调度器
            self.scheduler.shutdown(wait=wait)
            self.logger.info("全局调度器已关闭")

    def get_task_status(self, task_id: int) -> Optional[Dict]:
        """
        获取单个任务的运行状态
        :param task_id: 定时任务ID
        :return: 状态信息 {"is_running": bool, "job_id": str, "task_name": str}
        """
        try:
            task_data = self.db.scheduled_task_dao.get_scheduled_task_by_id(task_id)
            if not task_data:
                return None

            return {
                "is_running": task_data["is_running"] == 1,
                "is_enabled": task_data["is_enabled"] == 1,
                "job_id": self.running_tasks.get(task_id),
                "task_name": task_data["task_name"],
                "batch_count": len(task_data["task_batch_ids"])
            }
        except Exception as e:
            self.logger.error(f"获取任务状态失败 | ID：{task_id} | 异常：{str(e)}")
            return None


# ------------------- 测试示例（可选） -------------------
if __name__ == "__main__":
    # 初始化调度器
    scheduler_manager = SchedulerManager()
    scheduler_manager.start_scheduler()

    # 示例：启动ID为1的定时任务
    # scheduler_manager.start_task(1)

    # 示例：停止ID为1的定时任务
    # scheduler_manager.stop_task(1)

    # 示例：关闭调度器（退出时调用）
    # scheduler_manager.shutdown_scheduler()
    pass