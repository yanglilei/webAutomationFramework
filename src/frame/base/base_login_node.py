from abc import abstractmethod
from typing import Tuple, Dict, Any

from src.frame.base.base_task_node import BasePYNode
from src.frame.common.constants import NodeState
from src.utils import basic


class BaseLoginTaskNode(BasePYNode):
    """
    登录基类：封装通用的登录逻辑，开放业务扩展接口
    子类只需实现抽象方法，即可快速开发登录节点
    """

    def __init__(self, driver, user_manager, global_config: Dict[str, Any], task_config: Dict[str, Any],
                 node_config: Dict[str, Any],
                 user_config: Tuple, logger, is_auto_fill_pwd: bool = True):
        super().__init__(driver, user_manager, global_config, task_config, node_config, user_config, logger)

        # 登录url
        self.login_url = self.node_config.get("node_params", {}).get("login_url")
        # 是否自动填充密码，true-如果是身份证作为账号，则取用户名后六位作为密码
        self.is_auto_fill_pwd = is_auto_fill_pwd

    def execute(self, context: Dict) -> bool:
        self.state = NodeState.RUNNING
        try:
            ret = self.login()
        except Exception as e:
            self.user_manager.update_login_msg_by_username(self.username, "登录异常")
            self.logger.exception(f"用户【{self.username_showed}】登录异常：")
            self.node_result["is_success"] = False
            self.node_result["error_msg"] = f"登录异常：{str(e)}"
            return False
        else:
            if not ret[0]:
                # 登录失败
                self.user_manager.update_login_msg_by_username(self.username, ret[1])
                self.logger.error(f"用户【{self.username_showed}】登录失败：{ret[1]}")
                self.node_result["is_success"] = False
                self.node_result["error_msg"] = f"{ret[1]}"
                return False
            else:
                self.logger.info(f"登录成功！")
                self.node_result["is_success"] = True
                return True

    def clean_up(self):
        self.state = NodeState.READY

    def login(self) -> Tuple[bool, str]:
        """
        登录
        :return: (True, success) or (False, fail reason)
        """
        if self.is_auto_fill_pwd and basic.is_id_no(self.username) and len(self.password.strip()) == 0:
            # 自动填充密码
            self.password = self.username[-6:].lower()

        if not self.username or not self.username.strip():
            return False, "用户名为空"
        if not self.password or not self.password.strip():
            return False, "密码为空"

        # 关闭其他页面，重登的时候清除掉其余的窗口
        if len(self.get_windows()) > 0:
            self.close_other_windows(self.get_latest_window())

        # 加载页面
        self.load_url(self.login_url)
        # 进入登录页面
        self.enter_login_page()
        # 登录
        return self.do_login()

    def enter_login_page(self):
        """
        进入登录页面
        登录前的预操作，比如：让用户名、密码框展示出来！
        :return:
        """
        pass

    @abstractmethod
    def do_login(self) -> Tuple[bool, str]:
        """
        登录
        :return: (bool, str): (status, reason) True-success, False-fail
        """
        pass
