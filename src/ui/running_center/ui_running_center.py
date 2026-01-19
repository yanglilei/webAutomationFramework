from typing import List

from src.frame.base.ui.base_ui import TabWidgetInfo, BaseTabWidget
from src.ui.running_center.ui_execute_task import FullAutomaticTaskPage, UIExecuteTask
from src.ui.running_center.ui_log import LogPage


class RunningCenterWidget(BaseTabWidget):
    def __init__(self):
        self.tab_execute_task = UIExecuteTask()
        self.tab_log = LogPage()
        super().__init__()

    def add_tab_widgets(self) -> List[TabWidgetInfo]:
        return [TabWidgetInfo("执行任务", self.tab_execute_task),
                TabWidgetInfo("运行日志", self.tab_log)
                ]

    def has_running_task(self) -> bool:
        return self.tab_execute_task.has_running_task()