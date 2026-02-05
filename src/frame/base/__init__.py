# 必须指定导入模块，否则无法打包到可执行文件中
from src.frame.base.base_login_node import BaseLoginTaskNode
from src.frame.base.base_enter_course_node import BaseEnterCourseTaskNode
from src.frame.base.base_monitor_course_node import BaseMonitorCourseTaskNode
from src.frame.base.base_exam_node import BaseMCQExamTaskNode

# import httpx
import tenacity