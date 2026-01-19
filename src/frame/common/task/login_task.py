import time

from src.base.base_login_handler import BaseLoginHandler
from src.common.login_machine import LoginMachine
from src.common.task.base_task import BaseTask
from src.utils.user_info_operator import UserInfoOperator


class LoginTask(BaseTask):
    def __init__(self, user_info_operator: UserInfoOperator, login_busi_handler: BaseLoginHandler, is_need_exit=False):
        super().__init__()
        self.user_info_operator = user_info_operator
        self.login_busi_handler = login_busi_handler
        self.is_need_exit = is_need_exit

    def run(self):
        login_machine = LoginMachine(self.user_info_operator, self.login_busi_handler)
        gen  = login_machine.batch_login()
        while not self.is_need_exit or not login_machine.is_all_done:
            # 等待所有登录完成
            time.sleep(1)
        else:
            for webdriver, username in gen:
                if webdriver:
                    webdriver.quit()
            self.finished.emit()
