from typing import Dict, Callable

from src.frame.common.constants import ControlCommand, NodeState


class BaseTest:
    def __init__(self):
        self.command_registry: Dict[ControlCommand, Callable] = {}  # 命令注册表
        self.node_id = "xxx0"
        self.state = NodeState.RUNNING


    def register_command(self, cmd_name: ControlCommand) -> Callable:
        """命令注册装饰器：节点子类用该装饰器注册控制命令"""

        def decorator(func: Callable) -> Callable:
            self.command_registry[cmd_name] = func
            return func

        return decorator


    def execute_command(self, cmd_name: ControlCommand, /, *args, **kwargs) -> bool:
        """执行注册的命令（调度器调用入口）"""
        if cmd_name not in self.command_registry:
            print(f"[节点{self.node_id}] 未注册命令：{cmd_name}")
            return False
        try:
            self.command_registry[cmd_name](*args, **kwargs)
            print(f"[节点{self.node_id}] 命令执行成功：{cmd_name}")
            return True
        except Exception as e:
            print(f"[节点{self.node_id}] 命令执行失败：{cmd_name}，错误：{str(e)}")
            return False


class LearningNode(BaseTest):
    def __init__(self):
        super().__init__()
        # 注册所有支持的控制命令（与ControlCommand枚举对应）
        # self._register_builtin_commands()

    def _register_builtin_commands(self):
        """注册内置控制命令：pause/resume/wake_up"""

        @self.register_command(ControlCommand.PAUSE)
        def pause(*args, **kwargs):
            if self.state == NodeState.RUNNING:
                print(f"课程已暂停监视！")
                self.state = NodeState.PAUSED
                print(args)
                print(kwargs)

        @self.register_command(ControlCommand.RESUME)
        def resume():
            if self.state == NodeState.PAUSED:
                self.state = NodeState.RUNNING
                print(f"课程已恢复监视！")


# 3. 测试（实例属性独立）
if __name__ == "__main__":
    LearningNode().execute_command(ControlCommand.PAUSE, "sdf", ok="cc")
