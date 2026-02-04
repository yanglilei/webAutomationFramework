# ./framework/general_component_manager.py
# 新增导入
import hashlib
import importlib.util
import os
import sys
import threading
from typing import Any, Type

from src.frame.common.decorator.singleton import singleton
from src.frame.compenent_dependency_manager import ComponentDependencyManager


@singleton
class GeneralComponentManager:
    """通用组件管理器：支持分类目录+热更新+依赖管理"""
    _lock = threading.Lock()  # 初始化线程锁

    def __init__(self):
        # 存储组件路径和组件名称的映射关系
        self.component_map = {}
        self.dependency_manager = ComponentDependencyManager()  # 依赖管理器

    def _get_module_name(self, component_path: str) -> str:
        """
        生成唯一模块名（基于组件文件路径的MD5）
        避免不同组件路径生成相同模块名导致冲突
        """
        md5 = hashlib.md5(component_path.encode("utf-8")).hexdigest()
        return f"dynamic_component_{md5}"

    def _get_file_mtime(self, file_path: str) -> float:
        """获取文件的最后修改时间戳（精确到秒）"""
        try:
            return os.path.getmtime(file_path)
        except FileNotFoundError:
            raise FileNotFoundError(f"文件不存在，无法获取修改时间：{file_path}")

    def _clear_module_cache(self, component_path: str):
        """清理组件对应的模块缓存（实现更新重载）"""
        delete_keys = []
        for key in self.component_map:
            if key == component_path:  # 精准匹配，避免误删
                delete_keys.append(key)

        for key in delete_keys:
            module_name, _ = self.component_map.get(key, (None, None))
            if module_name and module_name in sys.modules:
                del sys.modules[module_name]  # 删除模块缓存
                self.component_map.pop(key)  # 移除映射记录

    def _load_python_component(self, component_path: str, base_cls) -> Type:
        """加载Python组件（新增文件修改时间检测）"""
        with self._lock:
            # 1. 检查文件是否存在并获取当前修改时间
            if not os.path.exists(component_path):
                raise FileNotFoundError(f"Python组件文件不存在：{component_path}")
            if not os.path.isfile(component_path):
                raise IsADirectoryError(f"Python组件路径指向目录，非文件：{component_path}")
            current_mtime = self._get_file_mtime(component_path)

            # 2. 检查缓存：如果文件未修改且缓存存在，直接返回缓存的类
            if component_path in self.component_map:
                cached_module_name, cached_mtime = self.component_map[component_path]
                # 对比修改时间，仅当时间一致时使用缓存
                if cached_mtime == current_mtime and cached_module_name in sys.modules:
                    return self._get_final_subclasses(sys.modules[cached_module_name], base_cls)[0]

            # 3. 文件已修改/无缓存，清理原有缓存并重新加载
            self._clear_module_cache(component_path)

            # 4. 动态导入组件（原有核心逻辑）
            module_name = self._get_module_name(component_path)
            spec = importlib.util.spec_from_file_location(module_name, component_path)
            component_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(component_module)
            sys.modules[module_name] = component_module

            # 5. 更新缓存：存储模块名 + 文件修改时间
            self.component_map[component_path] = (module_name, current_mtime)

            # 6. 查找并返回符合接口的组件类
            matched_classes = self._get_final_subclasses(component_module, base_cls)
            if len(matched_classes) > 1:
                cls_names = [cls.__name__ for cls in matched_classes]
                raise ValueError(
                    f"Python组件{component_path}存在多个{base_cls.__name__}子类：{cls_names}，请确保仅存在一个实现类")
            if not matched_classes:
                raise ValueError(f"Python组件{component_path}未找到{base_cls.__name__}的子类实现")

            return matched_classes[0]

    def _get_final_subclasses(self, module, base_cls):
        """
        获取模块中继承自base_class_C的最终子类（排除中间父类和基类本身）
        :param module: 目标模块对象
        :param base_cls: 顶层基类C
        :return: 最终子类列表
        """
        # 步骤1：获取模块中所有的类对象
        subclasses_of_C = []
        for name in dir(module):
            cls = getattr(module, name)
            if isinstance(cls, type) and issubclass(cls, base_cls) and cls != base_cls:
                subclasses_of_C.append(cls)

        # 步骤2：筛选最终子类（模块中没有其他类继承它）
        final_subclasses = []
        for candidate_cls in subclasses_of_C:
            is_final = True
            for other_cls in subclasses_of_C:
                if candidate_cls is not other_cls and issubclass(other_cls, candidate_cls):
                    is_final = False
                    break
            if is_final:
                final_subclasses.append(candidate_cls)

        return final_subclasses

    def load_component(self, component_path: str, base_cls, dependency_install_dir) -> Any:
        """
        通用组件加载方法（先处理依赖，再加载组件）
        默认会去component_path的目录下寻找requirements.txt进行依赖的安装
        :param component_path: 组件绝对路径
        :param base_cls: 继承的基类
        :param dependency_install_dir: 依赖安装目录
        :return:
        """
        # 1. 先处理组件第三方依赖
        if not self.dependency_manager.handle_component_dependencies(component_path, dependency_install_dir):
            raise Exception(f"组件{component_path}依赖处理失败，无法加载")
        # 2. 加载组件（新增文件时间检测逻辑）
        file_ext = os.path.splitext(component_path)[1].lower()
        if file_ext == ".py":
            return self._load_python_component(component_path, base_cls)
        else:
            raise ValueError(f"不支持的组件类型：{file_ext}")


component_manager = GeneralComponentManager()