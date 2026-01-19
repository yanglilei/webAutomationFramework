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

    def _clear_module_cache(self, component_path: str):
        """清理组件对应的模块缓存（实现热更新）"""
        delete_keys = []
        for key in self.component_map:
            if key.startswith(component_path):
                delete_keys.append(key)

        for key in delete_keys:
            module_name = self.component_map.get(key)
            if module_name and module_name in sys.modules:
                del sys.modules[module_name]  # 删除模块缓存
                self.component_map.pop(key)  # 移除映射记录

    def _get_latest_component_path(self, component_path: str) -> str:
        """获取最新的组件路径"""
        max_ts = 0
        max_ts_key = ""
        for key in self.component_map:
            if key.startswith(component_path):
                ts = int(key[-10:])
                if ts > max_ts:
                    max_ts = ts
                    max_ts_key = key
        return self.component_map[max_ts_key]

    def _load_python_component(self, component_path: str, base_cls) -> Type:
        """加载Python组件"""
        with self._lock:
            # with open(component_path, "r", encoding="utf-8") as f:
            #     logging.info(f"加载Python组件：{f.read()}")
            # key = f"{component_path}_{batch_no}" if batch_no else component_path
            key = component_path
            if key in self.component_map:
                return self._get_final_subclasses(sys.modules.get(self.component_map[key]), base_cls)[0]

            # 1. 清理原有模块缓存
            self._clear_module_cache(component_path)
            # 动态导入组件
            if not os.path.exists(component_path):
                raise FileNotFoundError(f"Python组件文件不存在：{component_path}")
            if not os.path.isfile(component_path):
                raise IsADirectoryError(f"Python组件路径指向目录，非文件：{component_path}")

            # 生成唯一模块名
            module_name = self._get_module_name(key)
            self.component_map[key] = module_name

            # 动态导入模块
            # 1. 创建spec（生成模块加载说明书）
            spec = importlib.util.spec_from_file_location(module_name, component_path)
            # 2. 基于spec创建空模块对象（按说明书造“空架子”）
            component_module = importlib.util.module_from_spec(spec)
            # 3. 基于spec绑定的加载器执行模块（按说明书填充“内容”）
            spec.loader.exec_module(component_module)
            sys.modules[module_name] = component_module  # 手动注册到sys.modules

            # 查找并返回符合接口的组件类
            matched_classes = self._get_final_subclasses(component_module, base_cls)
            # 多个符合条件类时，抛出明确异常（或根据业务规则筛选）
            if len(matched_classes) > 1:
                cls_names = [cls.__name__ for cls in matched_classes]
                raise ValueError(
                    f"Python组件{component_path}存在多个{base_cls.__name__}子类：{cls_names}，请确保仅存在一个实现类")

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
            # 获取模块成员对应的对象
            cls = getattr(module, name)
            # 判断是否为类，且排除内置类和基类C本身
            if isinstance(cls, type) and issubclass(cls, base_cls) and cls != base_cls:
                subclasses_of_C.append(cls)

        # 步骤2：筛选最终子类（模块中没有其他类继承它）
        final_subclasses = []
        for candidate_cls in subclasses_of_C:
            # 标记是否为最终类（默认是最终类）
            is_final = True
            # 遍历所有继承自C的子类，判断是否有其他类以candidate_cls为父类
            for other_cls in subclasses_of_C:
                if candidate_cls is not other_cls and issubclass(other_cls, candidate_cls):
                    # 存在其他类继承当前类，说明当前类是中间父类，不是最终类
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
        # 2. 加载组件（原有逻辑）
        file_ext = os.path.splitext(component_path)[1].lower()
        if file_ext == ".py":
            return self._load_python_component(component_path, base_cls)
        else:
            raise ValueError(f"不支持的组件类型：{file_ext}")
