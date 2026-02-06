# ./components/monitor_course/base_monitor_course_node.py
import asyncio
import threading
import time
from abc import abstractmethod
from typing import Any, Dict, Tuple, Optional

from src.frame.base.base_task_node import BasePYNode
from src.frame.common.constants import NodeState
from src.frame.common.exceptions import SessionExpiredException


class BaseMonitorCourseTaskNode(BasePYNode):
    """
    课程监控基类：封装通用监控逻辑，开放业务扩展接口
    子类只需实现抽象方法，即可快速开发课程监控节点
    """

    def __init__(self, driver, user_manager, global_config: Dict[str, Any],
                 task_config: Dict[str, Any],
                 node_config: Dict[str, Any],
                 user_config: Tuple, logger):
        # 终止标志，通过设置该标志位，可中断轮询循环
        self.terminate_event = asyncio.Event()
        # 轮询间隔（秒）
        self.poll_interval: Optional[int] = None
        # 最大轮询次数（-1为无限轮询）
        self.max_poll_times: Optional[int] = None

        # 已轮询次数
        self.poll_count = 0
        # 监控停止原因，默认为"正常退出"
        self.stop_reason: str = "未启动"
        # 当前课程名称
        self.course_name: str = ""
        super().__init__(driver, user_manager, global_config, task_config, node_config, user_config, logger)

    def set_up(self):
        self.poll_interval = int(self._get_config_value(
            key="poll_interval",
            default=self._get_default_poll_interval()
        ))  # 轮询间隔（秒）
        self.max_poll_times = int(self._get_config_value(
            key="max_poll_times",
            default=self._get_default_max_poll_times()
        ))  # 最大轮询次数（-1为无限轮询）

    async def pause(self, reason="") -> None:
        if self.state == NodeState.RUNNING:
            self.logger.info(f"课程[{self.course_name}]已暂停监视！")
            self.state = NodeState.PAUSED

    def resume(self, reason="") -> None:
        if self.state == NodeState.PAUSED:
            self.state = NodeState.RUNNING
            self.logger.info(f"课程[{self.course_name}]已恢复监视！")

    def terminate(self, reason: str, is_terminate_task=False):
        """
        监控停止（优雅中断，通用逻辑）
        当学习完成、热加载或者其他异常情况需要终止监控的，调用此方法！
        :param reason: 停止原因
        :param is_terminate_task: 收到terminate信号的时候是否终止整个任务，即设置execute方法的返回值。True-终止任务；False-不终止
        """
        if not self.terminate_event.is_set():
            self.logger.info(f"收到监控停止信号，准备优雅退出轮询，退出原因：{reason}")
            self.terminate_event.set()
            self.stop_reason = reason
            self.execute_result = not is_terminate_task

    async def execute(self, context: Dict) -> bool:
        """
        完整监控流程（封装通用逻辑，子类无需修改）
        :return: 监控是否成功
        """
        self.logger.info(f"===== 启动【课程监控】流程 =====")
        try:
            self.state = NodeState.RUNNING
            # 1.重置节点结果
            self.reset_node_result()
            # 2.处理上一步的输出数据
            await self.handle_prev_output(self.get_prev_output())
            # 3.课程环境前置校验（可选重写）
            if not await self._validate_course_env():
                self.node_result["error_msg"] = "课程环境校验失败，无法启动监控"
                self.logger.error(self.node_result["error_msg"])
                self.execute_result = False
                return self.execute_result
            # 4.循环执行“当前课程完成+下一课切换”
            await self.monitor_current_course_until_finished()
            # 5.监控正常退出，封装结果
            self._pack_result()
            self.logger.info(f"===== 【课程监控】正常退出：{self.stop_reason} =====")
        except SessionExpiredException as e:
            self.node_result["is_success"] = False
            # 外部框架会和relogin_config.relogin_trigger_errors配置的消息对比对，判断是否需要重新登录
            self.node_result["error_msg"] = f"===== 用户【{self.username_showed}】【课程监控】异常退出：{str(e)}"
            self.logger.info(self.node_result["error_msg"])
            self.execute_result = False
        except Exception as e:
            self.node_result["is_success"] = False
            self.node_result["error_msg"] = f"【课程监控】异常退出：{str(e)}"
            self.logger.exception(f"【课程监控】异常退出：")
            self.execute_result = False

        return self.execute_result

    async def clean_up(self):
        # 重置中断标识
        self.terminate_event.clear()
        # 设置运行状态
        self.state = NodeState.READY
        # 设置当前课程名称
        self.course_name = ""
        # 已轮询次数
        self.poll_count = 0
        # 监控停止原因
        self.stop_reason: str = "未启动"

    async def monitor_current_course_until_finished(self):
        """
        监控当前课程所有任务点，直到完成
        """
        # self.logger.info(f"开始监控课程[{self.course_name}]任务点完成状态")
        # 监控课程前置准备，如初始化变量等
        await self.prepare_before_poll_monitor_course()
        while not self.terminate_event.is_set():
            # 出现暂停，则等待
            if self.state == NodeState.PAUSED:
                await asyncio.sleep(1)
                continue
            # 执行单次任务点监控（如弹窗处理、进度恢复等，通用逻辑）
            await self.single_poll_monitor()
            # 轮询次数限制（针对课程切换次数，可选）
            self.poll_count += 1
            if self.max_poll_times != -1 and self.poll_count >= self.max_poll_times:
                self.stop_reason = f"达到最大课程切换次数（{self.max_poll_times}次）"
                break
            # 轮询间隔
            # await self.terminate_event.wait(timeout=self.poll_interval)
            await asyncio.sleep(self.poll_interval)

        # 传递输出数据
        self.send_node_output()

    async def handle_prev_output(self, prev_output: Dict[str, Any]):
        """
        处理上一步的输出数据，子类可根据自身逻辑拓展该方法
        建议通过super().handle_prev_output(xx)来调用
        :param prev_output: 上一步的输出数据
        :return:
        """
        self.course_name = prev_output.get("course_name", "")

    def send_node_output(self):
        """
        传递输出数据
        紧跟在监控结束后的操作，用于设置需要传递给下一个节点的数据！
        子类务必调用set_output_data方法设置输出的参数，更新在self.node_result的output_data属性中
        :return:
        """
        pass

    async def prepare_before_poll_monitor_course(self):
        """
        监控课程前置准备
        发生在进行循环监控课程之前
        紧贴在while之前的操作！
        子类可做初始化变量等操作！
        """
        pass

    def _pack_result(self):
        """
        封装监控结果（通用逻辑，子类可重写扩展）
        子类可通过set_output_data扩展输出数据
        """
        super().pack_result(status=self.execute_result, **{
            "poll_count": self.poll_count,
            "stop_reason": self.stop_reason,
            "last_poll_time": time.strftime("%Y-%m-%d %H:%M:%S"),
            "poll_interval": self.poll_interval,
            "max_poll_times": self.max_poll_times,
            "exit_flag": 1 if self.terminate_event.is_set() else 0,
            "is_need_switch_course": True  # 传给下一个节点，用于判断是否需要切换课程
        })

    def _get_config_value(self, key: str, default: Any) -> Any:
        """
        获取配置值（优先级：节点配置 > 全局配置 > 默认值）
        :param key: 配置键
        :param default: 默认值
        :return: 配置值
        """
        node_config_value = self.node_config.get("node_params", {}).get(key)
        if node_config_value is not None:
            return node_config_value
        global_config_value = self.global_config.get(key)
        return global_config_value if global_config_value is not None else default

    # -------------------------- 抽象方法（子类必须实现） --------------------------
    # @abstractmethod
    # async def _get_target_course_id(self) -> Optional[str]:
    #     """
    #     获取目标课程ID（子类必须实现，支持自定义获取逻辑）
    #     :return: 目标课程ID / None（获取失败）
    #     """
    #     pass

    @abstractmethod
    async def single_poll_monitor(self):
        """
        单次轮询监控核心逻辑（子类必须实现，如状态检查、弹窗处理等）
        """
        pass

    # @abstractmethod
    # async def _is_all_done(self) -> bool:
    #     """
    #     判断课程是否都结束了
    #     :return:
    #     """
    #     pass

    # -------------------------- 可选重写方法（子类按需扩展） --------------------------
    def _get_default_poll_interval(self) -> int:
        """
        获取默认轮询间隔（子类可重写，默认10秒）
        :return: 轮询间隔（秒）
        """
        return 10

    def _get_default_max_poll_times(self) -> int:
        """
        获取默认最大轮询次数（子类可重写，默认-1无限轮询）
        :return: 最大轮询次数
        """
        return -1

    async def _validate_course_env(self) -> bool:
        """
        课程环境前置校验（子类可重写，默认返回True）
        :return: 环境是否有效
        """
        return True
