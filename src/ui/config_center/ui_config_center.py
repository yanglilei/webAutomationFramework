from typing import List

from src.frame.base.ui.base_ui import TabWidgetInfo, BaseTabWidget
from src.ui.config_center.ui_data_dict import DataDictPage
from src.ui.config_center.ui_node import NodePage
from src.ui.config_center.ui_project import ProjectPage
from src.ui.config_center.ui_create_task_page import CreateTaskPage


class ConfigCenterWidget(BaseTabWidget):
    def __init__(self):
        self.tab_create_task = CreateTaskPage()
        self.tab_node_page = NodePage()
        self.tab_project_page = ProjectPage()
        self.tab_data_dict_page = DataDictPage()
        self.tab_project_page.data_changed_signal.connect(self.tab_create_task.update_project_info)
        super().__init__()

    def add_tab_widgets(self) -> List[TabWidgetInfo]:
        return [TabWidgetInfo("创建任务", self.tab_create_task),
                TabWidgetInfo("节点列表", self.tab_node_page),
                TabWidgetInfo("项目列表", self.tab_project_page),
                TabWidgetInfo("全局配置", self.tab_data_dict_page),
                ]
