from src.base.base_learning_monitor import LearningTaskMonitor
from src.base.base_login_handler import BaseLoginHandler
from src.base.base_navigate_handler import BaseNavigateHandler
from src.common.login_machine import LoginMachine
from src.common.task.base_task import BaseTask
from src.utils.user_info_operator import UserInfoOperator


class LearningTask(BaseTask):

    def __init__(self, user_info_operator: UserInfoOperator, login_machine: LoginMachine,
                 navigate_handler: BaseNavigateHandler, learning_handler: LearningHandler):
        super().__init__()
        self.learning_monitor = LearningTaskMonitor()
        self.study_machine = StudyMachine()