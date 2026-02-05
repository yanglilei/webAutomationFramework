from abc import abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Tuple

from src.frame.base.base_task_node import BasePYNode
from src.frame.common.constants import NodeState
from src.frame.common.exceptions import SessionExpiredException


@dataclass(init=False)
class BaseEnterCourseTaskNode(BasePYNode):
    """
    课程监控基类：封装通用监控逻辑，开放业务扩展接口
    子类只需实现抽象方法，即可快速开发课程监控节点
    """

    course_name: str = ""  # 当前课程名称

    def execute(self, context: Dict) -> bool:
        """
        完整监控流程（封装通用逻辑，子类无需修改）
        进入课程成功，必返回参数：course_name（当前课程名称）
        :return: True-任务继续；False-任务退出
        """
        self.logger.info(f"===== 开始执行【{self.node_config.get('name')}】节点 =====")
        try:
            # 设置运行状态
            self.state = NodeState.RUNNING
            # 1.重置节点结果
            self.reset_node_result()
            # 2.处理上一步的输出数据
            self.handle_prev_output(self.get_prev_output())
            # 3.切换课程 or 第一次进入课程
            if self.get_prev_output().get("is_need_switch_course"):
                # 课程结束后执行操作！
                status, desc = self.handle_after_course_finished()
            else:
                # 登录后执行的操作！
                status, desc = self.prepare_before_first_enter_course()

            if not status:
                self.update_learning_status(desc)
                error_msg = f"进入课程失败：{desc}"
                self.logger.error(error_msg)
                self.pack_result(False, error_msg)
                return False
            # 4.进入课程
            status, desc = self.enter_course()
            if not status:
                self.update_learning_status(desc)
                error_msg = f"进入课程失败：{desc}"
                self.logger.error(error_msg)
                self.pack_result(False, error_msg)
                return False

            # 设置课程名称
            self.course_name = desc
            # 5.正常退出，封装结果
            self.pack_result(course_name=self.course_name)
            # 传递输出数据
            self.send_node_output()
            self.logger.info(f"===== 开始学习课程：{self.course_name} =====")
            return True
        except SessionExpiredException as e:
            self.pack_result(False, str(e))
            return False
        except Exception as e:
            self.update_learning_status("进入课程异常")
            error_msg = f"进入课程异常：{str(e)}"
            self.pack_result(False, error_msg)
            self.logger.exception(f"进入课程异常：")
            return False

    def clean_up(self):
        # 设置运行状态
        self.state = NodeState.READY
        # 设置当前课程名称
        self.course_name = ""

    def update_learning_status(self, remark):
        """
        更新信息
        更新表格中该用户的学习状态
        :return:
        """
        if self.user_mode == 1:
            # 表格模式，更新表格中该用户学习状态
            if self.user_manager.update_learning_status(self.username, remark):
                self.logger.info(f"更新学习状态成功，当前状态为：【{remark}】！")
            else:
                self.logger.warning(f"更新学习状态失败！")
        else:
            # 非表格模式，仅仅输出日志
            self.logger.info(f"当前状态为：【{remark}】！")

    def handle_prev_output(self, prev_output: Dict[str, Any]):
        """
        处理上一步的输出数据
        :param prev_output: 上一步的输出数据
        :return:
        """
        pass

    def send_node_output(self):
        """
        传递输出数据，可调用set_output_data方法设置输出的参数
        :return:
        """
        pass

    @abstractmethod
    def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        """
        第一次进入课程的前置操作，即登录页面到进入课程前，要处理一些页面的跳转等
        :return: 进入成功返回：(True, 成功)；进入失败返回：(False, 失败原因)
        """
        return True, ""

    @abstractmethod
    def enter_course(self) -> Tuple[bool, str]:
        """
        进入课程
        :return: 进入成功返回：(True, 课程名称)；进入失败返回：(False, 失败原因)
        """
        pass

    @abstractmethod
    def handle_after_course_finished(self) -> Tuple[bool, str]:
        """
        一个课程结束后的操作逻辑
        无需再调用enter_course方法
        :return: 切换成功返回：(True, 成功)；切换失败返回：(False, 失败原因)
        """
        pass
