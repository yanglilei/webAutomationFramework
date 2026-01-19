import atexit
import os
import sys
from typing import List

from PyQt5.QtWidgets import QApplication

from src.frame.base.ui.base_ui import BaseUI, TabWidgetInfo
from src.frame.common.common import release
from src.ui.config_center.ui_node import NodePage
from src.ui.config_center.ui_project import ProjectPage
from src.ui.config_center.ui_create_task_page import CreateTaskPage
from src.utils.sys_path_utils import SysPathUtils


class MainWindow(BaseUI):
    def __init__(self):
        # TODO 未获取任务
        self.tab_create_task = CreateTaskPage(self, {})
        # self.tab_task_tmpl_page = UITaskTmpl()
        self.tab_node_page = NodePage()
        self.tab_project_page = ProjectPage()
        super().__init__()
        # self.setMinimumSize(800, 600)  # 最小窗口尺寸，避免缩放过小

    def get_signature_prefix(self) -> str:
        return "学霸"

    def add_tab_widgets(self) -> List[TabWidgetInfo]:
        return [TabWidgetInfo("创建任务", self.tab_create_task),
                # TabWidgetInfo("任务模板", self.tab_task_tmpl_page),
                TabWidgetInfo("节点列表", self.tab_node_page),
                TabWidgetInfo("项目列表", self.tab_project_page),
                ]

    def get_app_name(self):
        return "学霸"

    def get_version(self):
        return "V1.0.0"

    def get_icon(self):
        return os.path.join(SysPathUtils.get_icon_file_dir(), "xxgsstudy.ico")


if __name__ == "__main__":
    try:
        atexit.register(release)
        app = QApplication([])
        main_window = MainWindow()
        main_window.show()
        sys.exit(app.exec())
    except Exception as e:
        print(e)
    finally:
        # 释放资源
        pass
