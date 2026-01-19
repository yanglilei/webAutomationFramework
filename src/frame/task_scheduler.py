import threading
from typing import Dict, Optional, Tuple

from src.frame.base.base_task_node import BaseNode
from src.frame.common.constants import ControlCommand
from src.frame.common.decorator.singleton import singleton
from src.frame.hot_reload_manager import NodeHotReloadManager
from src.frame.task import Task


@singleton
class TaskScheduler:
    """任务调度器核心类"""
    _lock = threading.Lock()

    def __init__(self, logger):
        self.tasks: Dict[str, Task] = {}  # 全局任务注册表：{task_uuid: task}
        self.node_index: Dict[Tuple[str, int], BaseNode] = {}  # 节点索引表：{(task_uuid, node_id): node}
        self.hot_reload_manager = NodeHotReloadManager()  # 热重载管理器
        self.logger = logger  # 日志实例

    def submit_task(self, task: Task) -> bool:
        """提交任务到调度器，同时构建节点索引"""
        with self._lock:
            if task.task_uuid in self.tasks:
                self.logger.info(f"[调度器] 任务已存在：{task.task_uuid}")
                return False
            self.tasks[task.task_uuid] = task
            for node in task.nodes.values():
                node_cfg = node.node_config
                if node_cfg.get("node_params", {}).get("is_support_hot_reload"):
                    # 添加到热加载节点列表
                    # self.support_hot_reload_nodes.append(node_instance)
                    # 在create_node_instance方法中component_path被修改了，所以这里需要重新获取
                    component_path = node_cfg.get("component_path")
                    # 需要热加载的组件，添加到看门狗.
                    self.hot_reload_manager.watch_node_file(
                        node_identifier=node_cfg.get("node_id"),
                        node_file_path=component_path,
                        reload_callback=self._task_reload_callback
                    )

        self.logger.info(f"[调度器] 任务提交成功：{task.task_uuid}")
        return True

    def _task_reload_callback(self, component_path: str):
        """文件变更回调：中断旧任务+重启新任务"""
        self.logger.info(f"开始执行热更新，组件路径：{component_path}")
        # self.hot_reload(component_path)
        for task in self.tasks.values():
            task.hot_reload(component_path)
        self.logger.info(f"结束热更新，组件路径：{component_path}")

    def start_task(self, task_uuid: str) -> bool:
        """启动任务（异步执行，不阻塞主线程）"""
        if task_uuid not in self.tasks:
            self.logger.info(f"[调度器] 启动失败，任务不存在：{task_uuid}")
            return False
        return self.tasks[task_uuid].run()

    def remove_task(self, task_uuid: str):
        """移除任务"""
        if task_uuid in self.tasks:
            self.tasks.pop(task_uuid)
            self.logger.info(f"[调度器] 移除任务成功：{task_uuid}")

    def get_target_node(self, task_uuid: str, node_id: Optional[int] = None) -> Optional[BaseNode]:
        """寻址目标节点（核心方法）：支持任务级/节点级寻址"""
        with self._lock:
            if task_uuid not in self.tasks:
                self.logger.info(f"[调度器] 任务不存在：{task_uuid}")
                return None
            # 节点级精准寻址
            if node_id and (task_uuid, node_id) in self.node_index:
                return self.node_index[(task_uuid, node_id)]
            # 任务级寻址：返回当前执行节点
            task = self.tasks[task_uuid]
            if task.current_node_id:
                return task.get_node(task.current_node_id)
        return None

    def terminate_task(self, batch_no: str="", task_uuid: str="", reason="手动强制停止"):
        """
        终止任务
        :param batch_no: 批次号
        :param task_uuid: 任务ID
        :param reason: 终止原因
        """
        if not batch_no and not task_uuid:
            # 两个参数都不传，批量终止所有任务
            for task in self.tasks.values():
                node = task.get_node(task.current_node_id)
                if node.supports_command(ControlCommand.TERMINATE):
                    node.terminate(reason, True)
            return

        if task_uuid:
            if task_uuid not in self.tasks:
                self.logger.info(f"[调度器] 停止失败，任务不存在：{task_uuid}")
                return
            # 终止任务，要找到正在执行的节点，让节点停止执行
            current_running_node = self.get_target_node(task_uuid)
            # 发送终止指令
            if current_running_node.supports_command(ControlCommand.TERMINATE):
                current_running_node.terminate(reason, True)
        elif batch_no:
            for task in self.tasks.values():
                if task.batch_no == batch_no:
                    node = task.get_node(task.current_node_id)
                    if node.supports_command(ControlCommand.TERMINATE):
                        node.terminate(reason, True)

    def pause_task(self, batch_no: str = "", task_uuid: str = "", reason=""):
        """
        暂停任务
        :param batch_no: 批次号
        :param task_uuid: 任务ID
        :param reason: 暂停原因
        """
        if not batch_no and not task_uuid:
            # 两个参数都不传，批量终止所有任务
            for task in self.tasks.values():
                node = task.get_node(task.current_node_id)
                if node.supports_command(ControlCommand.PAUSE):
                    node.pause(reason)
            return

        if task_uuid:
            if task_uuid not in self.tasks:
                self.logger.info(f"[调度器] 暂停失败，任务不存在：{task_uuid}")
                return
            # 终止任务，要找到正在执行的节点，让节点停止执行
            current_running_node = self.get_target_node(task_uuid)
            # 发送终止指令
            if current_running_node.supports_command(ControlCommand.PAUSE):
                current_running_node.pause(reason)
        elif batch_no:
            for task in self.tasks.values():
                if task.batch_no == batch_no:
                    node = task.get_node(task.current_node_id)
                    if node.supports_command(ControlCommand.PAUSE):
                        node.pause(reason)

    def resume_task(self, batch_no: str = "", task_uuid: str = "", reason=""):
        """
        恢复任务
        :param batch_no: 批次号
        :param task_uuid: 任务ID
        :param reason: 恢复原因
        """
        if not batch_no and not task_uuid:
            # 两个参数都不传，批量终止所有任务
            for task in self.tasks.values():
                node = task.get_node(task.current_node_id)
                if node.supports_command(ControlCommand.RESUME):
                    node.resume(reason)
            return

        if task_uuid:
            if task_uuid not in self.tasks:
                self.logger.info(f"[调度器] 恢复失败，任务不存在：{task_uuid}")
                return
            # 终止任务，要找到正在执行的节点，让节点停止执行
            current_running_node = self.get_target_node(task_uuid)
            # 发送终止指令
            if current_running_node.supports_command(ControlCommand.RESUME):
                current_running_node.resume(reason)
        elif batch_no:
            for task in self.tasks.values():
                if task.batch_no == batch_no:
                    node = task.get_node(task.current_node_id)
                    if node.supports_command(ControlCommand.RESUME):
                        node.resume(reason)
    # def dispatch_to_all_task(self, cmd_name: str):
    #     """分发外部事件给所有的任务（核心方法）：外部系统唯一调用入口"""
    #     for task_uuid, task in self.tasks.items():
    #         task.get_node(task.current_node_id).execute_command(cmd_name)


