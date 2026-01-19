# ./framework/hot_reload_manager.py
import importlib
import logging
import os
import sys
import time
from typing import Dict, Callable, Optional

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from src.frame.common.decorator.singleton import singleton

logger = logging.getLogger("HotReloadManager")

class NodeFileChangeHandler(FileSystemEventHandler):
    """节点文件变更事件处理器"""

    def __init__(self, node_file_path: str, reload_callback: Callable):
        self.node_file_path = os.path.abspath(node_file_path)
        self.reload_callback = reload_callback  # 文件变更后的回调（触发任务重启）
        self.last_modify_time = os.path.getmtime(self.node_file_path)

    def on_modified(self, event):
        """文件修改事件触发"""
        if not event.is_directory and os.path.abspath(event.src_path) == self.node_file_path:
            # 避免重复触发（文件保存可能触发多次修改事件）
            current_modify_time = os.path.getmtime(self.node_file_path)
            if current_modify_time - self.last_modify_time < 1:
                return
            self.last_modify_time = current_modify_time

            logger.info(f"检测到节点文件变更：{event.src_path}，准备触发热重载")
            self.reload_callback(event.src_path)  # 调用回调，触发任务重启


@singleton
class NodeHotReloadManager:
    """节点热重载管理器：监听文件变更+动态重载节点类"""

    def __init__(self):
        self.observer = Observer()
        self.node_file_map: Dict[int, NodeFileChangeHandler] = {}  # 节点标识->文件处理器
        self.node_class_cache: Dict[int, type] = {}  # 节点标识->节点类缓存

    def watch_node_file(self, node_identifier: int, node_file_path: str, reload_callback: Callable):
        """
        监听指定节点文件
        :param node_identifier: 节点唯一标识（如"general_monitor_course"）
        :param node_file_path: 节点文件路径（.py）
        :param reload_callback: 文件变更后的回调函数
        """
        if not os.path.exists(node_file_path):
            logger.error(f"节点文件不存在：{node_file_path}")
            return
        if node_identifier in self.node_file_map:
            logger.warning(f"节点文件已监听：{node_file_path}")
            return
        # 创建文件处理器
        event_handler = NodeFileChangeHandler(node_file_path, reload_callback)
        self.node_file_map[node_identifier] = event_handler

        # 启动监听
        self.observer.schedule(
            event_handler,
            path=os.path.dirname(node_file_path),
            recursive=False
        )
        if not self.observer.is_alive():
            self.observer.start()
        logger.info(f"已开始监听节点文件：{node_file_path}")

    def unwatch_node_file(self, node_identifier: int):
        """停止监听指定节点文件"""
        if node_identifier not in self.node_file_map:
            return
        event_handler = self.node_file_map.pop(node_identifier)
        self.observer.unschedule(event_handler)
        logger.info(f"已停止监听节点文件：{event_handler.node_file_path}")

    def reload_node_class(self, node_identifier: int, component_path: str) -> Optional[type]:
        """
        动态重载节点类（清空缓存+重新导入）
        :param node_identifier: 节点唯一标识
        :param component_path: 节点组件路径（如"components.monitor_course.general_monitor_course_handler.GeneralMonitorCourseNode"）
        :return: 重载后的节点类
        """
        try:
            # 1. 拆分组件路径（模块路径+类名）
            module_path, class_name = component_path.rsplit(".", 1)

            # 2. 清空模块缓存（强制重新导入）
            if module_path in sys.modules:
                del sys.modules[module_path]
            # 清空节点类缓存
            if node_identifier in self.node_class_cache:
                del self.node_class_cache[node_identifier]

            # 3. 动态导入模块和类
            module = importlib.import_module(module_path)
            node_class = getattr(module, class_name)
            # 更新缓存
            self.node_class_cache[node_identifier] = node_class

            logger.info(f"节点类[{node_identifier}]动态重载成功")
            return node_class
        except Exception as e:
            logger.error(f"节点类[{node_identifier}]动态重载失败：{e}")
            return None

    def get_node_class(self, node_identifier: int, component_path: str) -> Optional[type]:
        """获取节点类（优先从缓存获取，缓存不存在则加载）"""
        if node_identifier in self.node_class_cache:
            return self.node_class_cache[node_identifier]
        # 首次加载
        module_path, class_name = component_path.rsplit(".", 1)
        module = importlib.import_module(module_path)
        node_class = getattr(module, class_name)
        self.node_class_cache[node_identifier] = node_class
        return node_class

    def stop(self):
        """停止所有监听"""
        self.observer.stop()
        self.observer.join()
        self.node_file_map.clear()
        self.node_class_cache.clear()
        logger.info("节点热重载管理器已停止")
