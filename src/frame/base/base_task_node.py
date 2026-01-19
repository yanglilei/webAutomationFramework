# ./components/abc_task_node.py
import json
import os
from abc import ABC, abstractmethod, ABCMeta
from typing import Dict, Any, Tuple, Optional, Callable

from src.frame.base.base_web_operator import SeleniumWebOperator
from src.frame.common.constants import NodeState, ControlCommand
from src.utils import basic


class BaseNode(ABC):
    """
    任务节点组件接口（所有组件均需实现该接口）
    后续节点获取输出结果请调用get_prev_output方法，避免直接访问上个节点实例的属性，因为在execute结束时通常会进行清除的动作
    """

    def __init__(self, user_manager, global_config: Dict, task_config: Dict, node_config: Dict, user_config: Tuple,
                 logger):
        self.user_manager = user_manager  # 用户管理器实例
        # self.previous_outputs: Optional[Dict[str, Any]] = None  # 前一个节点的输出数据
        self.global_config: Dict[str, Any] = global_config or {}  # 全局配置
        self.task_config: Dict[str, Any] = task_config or {}  # 任务配置
        self.node_config: Dict[str, Any] = node_config or {}  # 节点配置
        self.logger = logger  # 带用户标识的日志
        # self.node_result: Optional[NodeResult] = None  # 节点执行结果
        self._task = None  # 关联的调度器，TaskScheduler实例
        # 遇到需要重登的情况时需要特殊处理：is_success=True，并设置error_msg，此处会去匹配关键词
        self.node_result: Dict[str, Any] = {
            "is_success": False,  # 节点执行是否成功
            "node_name": self.__class__.__name__,  # 节点名称
            "error_msg": "",  # 错误信息
            "output_data": {}  # 节点输出数据（供后续节点使用）
        }
        self.node_id: int = node_config.get("node_id")  # 节点ID
        self.next_node_id: int = node_config.get("next_node_id")  # 下一个节点ID
        self.pre_node_id: int = node_config.get("pre_node_id")  # 上一个节点ID
        self.node_name: str = node_config.get("name")  # 节点名称
        self.node_type: str = node_config.get("type")  # 节点类型
        if not isinstance(user_config, Tuple) or len(user_config) < 2:
            raise Exception("用户配置：user_config格式错误，必须为元组至少含2个元素，例：(用户名, 密码, )")
        self.user_config: Tuple = user_config  # 用户独立配置
        self.state: NodeState = NodeState.READY  # 初始状态
        self.command_registry: Dict[ControlCommand, Callable] = {}  # 命令注册表
        # 注册所有支持的控制命令（与ControlCommand枚举对应）
        self._auto_register_standard_commands()  # 注册内置控制命令
        self.execute_result = True  # execute返回值

    @abstractmethod
    def execute(self, context: Dict) -> bool:
        """
        TODO 退出返回的参数需要丰富！不能仅仅是bool，否则外部容易搞懵逼！
        TODO pause by zcy 20250115!
        执行节点逻辑
        遇到需要重登的情况时，返回True，配合node_result的error_msg，框架中会决定是否重登
        :return: 是否继续流程。True-继续流程；False-截止流程
        """
        pass

    def pause(self, reason="") -> None:
        """
        暂停指令：基类默认空实现
        仅子类重写该方法时，才会被注册到command_registry
        :param reason: 暂停原因
        """
        self.logger.info(
            f"节点{self.node_id}[{self.node_name}] 不支持terminate指令，终止请求已忽略（原因：{reason}）"
        )

    def resume(self, reason="") -> None:
        """
        恢复指令：基类默认空实现
        仅子类重写该方法时，才会被注册到command_registry
        :param reason: 恢复原因
        """
        self.logger.info(
            f"节点{self.node_id}[{self.node_name}] 不支持terminate指令，终止请求已忽略（原因：{reason}）"
        )

    def terminate(self, stop_reason: str, is_terminate_task=False) -> None:
        """
        终止指令：基类默认空实现
        仅子类重写该方法时，才会被注册到command_registry
        """
        self.logger.info(
            f"节点{self.node_id}[{self.node_name}] 不支持terminate指令，终止请求已忽略（原因：{stop_reason}，是否终结任务流程：{'是' if is_terminate_task else '否'}）"
        )

    def _auto_register_standard_commands(self):
        """
        自动注册标准指令：
        - pause/resume/terminate：仅子类重写时才注册
        """
        standard_commands = {}
        # 1. 条件注册terminate（仅子类重写时）
        if self.__class__.terminate != BaseNode.terminate:
            standard_commands[ControlCommand.TERMINATE] = self.terminate

        if self.__class__.pause != BaseNode.pause:
            standard_commands[ControlCommand.PAUSE] = self.pause

        if self.__class__.resume != BaseNode.resume:
            standard_commands[ControlCommand.RESUME] = self.resume

        # 批量注册+校验签名
        for cmd, func in standard_commands.items():
            # self._validate_standard_command_signature(cmd, func)
            self.command_registry[cmd] = func

    def supports_command(self, cmd_name: ControlCommand) -> bool:
        """
        简化版支持性判断：仅判断指令是否在注册表中
        - pause/resume/terminate：仅重写时才在
        """
        return cmd_name in self.command_registry

    def register_command(self, cmd: ControlCommand) -> Callable:
        """
        扩展指令注册装饰器：仅用于注册非标准指令（标准指令已自动注册）
        :param cmd: 扩展指令枚举
        """
        def decorator(func: Callable) -> Callable:
            # 禁止用此装饰器注册标准指令（防止子类覆盖）
            if cmd in [ControlCommand.PAUSE, ControlCommand.RESUME, ControlCommand.TERMINATE]:
                raise RuntimeError(f"禁止手动注册标准指令{cmd.value}，请直接实现对应方法")
            self.command_registry[cmd] = func
            return func

        return decorator

    # def execute_command(self, cmd_name: ControlCommand, /, *args, **kwargs) -> bool:
    #     """
    #     执行注册的命令（调度器调用入口）
    #     :param cmd_name: 指令名称。查看src.frame.common.constants.ControlCommand的指令内容
    #     :param args:
    #     :param kwargs:
    #     :return: bool True-执行成功；False-执行事变
    #     """
    #     if cmd_name not in self.command_registry:
    #         self.logger.info(f"节点{self.node_id}[{self.node_name}] 未注册命令：{cmd_name.value}")
    #         return False
    #     try:
    #         self.command_registry[cmd_name](*args, **kwargs)
    #         self.logger.info(f"节点{self.node_id}[{self.node_name}] 命令执行成功：{cmd_name.value}")
    #         return True
    #     except Exception as e:
    #         self.logger.info(f"节点{self.node_id}[{self.node_name}] 命令执行失败：{cmd_name.value}，错误：{str(e)}")
    #         return False

    def has_registered_command(self, cmd_name: str) -> bool:
        """
        判断是否注册了指定命令
        :param cmd_name: 指令名称。查看src.frame.common.constants.ControlCommand的指令内容
        :return : bool True-已注册指令；False-未注册
        """
        return cmd_name in self.command_registry

    def bind_task(self, task):
        """绑定调度器（用于获取上下文和上一节点信息）"""
        self._task = task

    def get_prev_node(self) -> Optional["BaseNode"]:
        """获取上一个执行的节点（便捷API）"""
        if not self._task or len(self._task.executed_nodes) < 1:
            return None
        prev_node_id = self._task.executed_nodes[-1]
        return self._task.nodes.get(prev_node_id)

    def get_prev_output(self) -> Any:
        """获取上一个节点的输出（便捷API）"""
        prev_node = self.get_prev_node()
        return prev_node.node_result.get("output_data") if prev_node else {}

    def clean_up(self):
        """
        节点执行后的清理工作（可选实现）
        执行execute完毕后，框架会再次调用该方法执行清除的工作！
        处理需要清理的资源：如变量、文件、数据库连接等
        切记：node_result不能在此处清理，否则后续的节点无法获取输出结果！
        """
        pass

    def get_node_result(self) -> Dict[str, Any]:
        """获取节点执行结果"""
        return self.node_result

    def set_output_data(self, key: str, value: Any):
        """设置节点输出数据（供后续节点使用）"""
        self.node_result["output_data"][key] = value

    def validate_session(self) -> bool:
        """
        TODO 目前暂时无需用到
        会话有效性校验（可选实现，默认返回True）
        业务节点可自定义校验逻辑（如：检查登录态标识、cookie是否存在）
        """
        pass

    def pack_result(self, status=True, desc="", **output_data):
        """
        封装结果（通用逻辑，子类可重写扩展）
        子类可通过set_output_data扩展输出数据
        """
        self.node_result["is_success"] = status
        self.node_result["error_msg"] = desc
        if output_data:
            self.node_result["output_data"].update(output_data)

    def reset_node_result(self):
        """重置输出数据"""
        self.node_result = {
            "is_success": False,  # 节点执行是否成功
            "node_name": self.__class__.__name__,  # 节点名称
            "error_msg": "",  # 错误信息
            "output_data": {}  # 节点输出数据（供后续节点使用）
        }


class BasePYNode(BaseNode, SeleniumWebOperator, metaclass=ABCMeta):
    """统一任务节点组件接口（所有组件均需实现该接口）"""

    def __init__(self, driver, user_manager, global_config: Dict, task_config: Dict, node_config: Dict,
                 user_config: Tuple, logger):
        SeleniumWebOperator.__init__(self, driver)
        BaseNode.__init__(self, user_manager, global_config, task_config, node_config, user_config, logger)
        self.username = self.user_config[0]  # 用户名
        self.password = self.user_config[1]  # 密码
        self.username_showed = basic.mask_username(self.username)  # 用户名展示
        self.set_up()  # 初始化，仅运行一次，逻辑由子类实现

    def set_up(self):
        """
        初始化方法，仅运行一次
        :return:
        """
        pass


class JSNode(BaseNode, SeleniumWebOperator):
    """
    JS节点
    利用selenium执行的js代码如下：

    -----------------
    // 传入参数
    const params = [此处为入参，转换成json字符串];
    // 执行JS组件逻辑
    [此处为组件中的js代码]
    // 返回节点结果
    return executeTaskNode(params);
    -----------------
    其中：const params = json.dumps(js_params)
    js_params = {
        "user_config": self.user_config,
        "node_config": self.node_config,
        "global_config": self.global_config,
        "previous_outputs": self.get_prev_output()  # 上一个节点的输出数据
    }

    组件中必须有executeTaskNode方法，否则调用失败！该方法返回对象格式如下：
    {
        "is_success": [true or false，布尔型],
        "error_msg": [错误消息，字符串],
        "output_data": [返回的数据，对象]
    }
    例如：
    {
        "is_success": true,
        "error_msg": "",
        "output_data": {
            "coco": "mini"
        }
    }
    """

    def __init__(self, driver, user_manager, js_component_path: str, global_config: Dict,
                 task_config: Dict, node_config: Dict, user_config: Tuple, logger):
        SeleniumWebOperator.__init__(self, driver)
        BaseNode.__init__(self, user_manager, global_config, task_config, node_config, user_config, logger)
        self.js_component_path = js_component_path

    def execute(self, context: Dict) -> bool:
        node_result = self._execute_js_node()
        return node_result["is_success"]

    def _execute_js_node(self) -> Dict:
        """通过Selenium执行JS任务节点"""
        self.logger.info(f"开始执行JS节点：{os.path.basename(self.js_component_path)}")
        node_result = {
            "is_success": False,
            "node_name": os.path.basename(self.js_component_path),
            "error_msg": "",
            "output_data": {}
        }

        try:
            # 1. 读取JS文件内容
            with open(self.js_component_path, "r", encoding="utf-8") as f:
                js_code = f.read()

            # 2. 构造JS执行参数（传递给JS代码）
            js_params = {
                "user_config": self.user_config,
                "node_config": self.node_config,
                "global_config": self.global_config,
                "previous_outputs": self.get_prev_output()  # 上一个节点的输出数据
            }

            # 3. Selenium执行JS代码（封装执行逻辑）
            # JS代码需暴露全局函数：executeTaskNode(parameters)
            js_exec_code = f"""
                // 传入参数
                const params = {json.dumps(js_params, ensure_ascii=False)};
                // 执行JS组件逻辑
                {js_code}
                // 返回节点结果
                return executeTaskNode(params);
            """
            # 执行JS并获取结果
            js_node_result = self.execute_js(js_exec_code)

            # 4. 解析JS执行结果
            node_result["is_success"] = js_node_result.get("is_success", False)
            node_result["error_msg"] = js_node_result.get("error_msg", "")
            node_result["output_data"] = js_node_result.get("output_data", {})
            self.logger.info(f"JS节点{node_result['node_name']}执行成功")
            return node_result
        except Exception as e:
            node_result["error_msg"] = str(e)
            node_result["is_success"] = False
            self.logger.error(f"JS节点执行失败：{e}")
            return node_result
