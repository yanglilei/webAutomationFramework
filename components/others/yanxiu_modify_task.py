import asyncio
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Dict
from typing import Tuple

from playwright.async_api import Page

from src.frame.base.base_task_node import BasePYNode
from src.utils.doc_utils import DocReader


@dataclass(init=False)
class YanxiuUploadTask(BasePYNode):
    """
    上传作业
    配置参数：
    area：区域名称，用于区分文件夹名称
    project_name：项目名称
    """
    course_page_window_handle: Page = None
    area: str = ""

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        # 获取第一个未完成的项目
        project_name = self.node_config.get("node_params", {}).get("project_name", "")
        if not project_name:
            return False, "请配置项目名称！"
        xpath = f"//div[@class='home-project-pane'][.//div[@class='project-name' and text()='{project_name}']]//div[@class='btn-group']//button"
        btn_enter_project = await self.get_elem_with_wait_by_xpath(10, xpath)
        if not btn_enter_project:
            return False, "没找到课程！"
        # 进入课程
        await btn_enter_project.click()
        await self.wait_for_url_changed(re.compile(r"workspace/\d+/"))
        self.course_page_window_handle = self.get_current_page()
        tab_my_learning_status = await self.get_elem_with_wait_by_xpath(10, "//li[.//text()='我的学情']")
        if not tab_my_learning_status:
            return False, "没找到我的学情！"
        await tab_my_learning_status.click()

        return True, "已进入课程！"

    async def execute(self, context: Dict) -> bool:
        task_result = ""
        status, desc = await self.prepare_before_first_enter_course()
        if not status:
            self.logger.error(f"用户【{self.username}】进入培训失败！")
            return False

        status, desc = await self.modify_summary()
        if not status:
            self.logger.error(f"用户【{self.username}】修改培训总结失败！")
            return False
        task_result += "培训总结-修改成功；"
        self.logger.info(f"用户【{self.username}】修改培训总结成功！")

        await self.close_other_windows(self.course_page_window_handle)

        # status, desc = await self.upload_teaching_plan()
        # if not status:
        #     self.logger.error(f"用户【{self.username}】上传教学计划失败！")
        #     return False
        # self.logger.info(f"用户【{self.username}】上传教学计划成功！")
        # task_result += "教学计划-上传成功；"

        self.user_manager.update_record_by_username(self.username, {4: task_result})
        return True

    async def modify_summary(self):
        # 修改培训总结
        xpath = "//div[contains(@class, 'tool-card')][.//div[@class='left'][.//p[text()='培训总结']]]"
        btn_upload_task = await self.get_elem_with_wait_by_xpath(15, xpath)
        if not btn_upload_task:
            self.logger.info(f"没有找到培训总结！")
            return True, "没有找到培训总结"
        await btn_upload_task.click()
        await asyncio.sleep(3)
        await self.switch_to_window_by_url_key("homework/list/member")
        await self._modify_task()

        return True, "修改培训总结成功！"

    async def _modify_task(self):
        btn_do_task = await self.get_elem_with_wait_by_xpath(10, "//div[@class='entity-user-action']/button")
        await btn_do_task.click()
        await asyncio.sleep(3)
        await self.switch_to_window_by_url_key("homework/detail/member")
        btn_modify_task = await self.get_elem_with_wait_by_xpath(10, "//div[@class='tools-homework-bottom']//button")
        await btn_modify_task.click()
        await asyncio.sleep(3)  # 等待iframe加载完成
        input_title = await self.get_elem_with_wait_by_xpath(10, "//input[@class='el-input__inner']")
        frame = self.switch_to_frame("iframe.tox-edit-area__iframe")
        # input_paragraphs = await self.get_elems_with_wait_by_xpath(10, "//body[@id='tinymce']//p", iframe=frame)
        input_content = await self.get_elem_with_wait_by_xpath(10, "//body[@id='tinymce']", iframe=frame)
        input_paragraphs = await self.get_relative_elems_by_xpath(input_content, ".//p")

        title = await input_title.input_value()
        # 替换其中的“荔城区”三个字
        title = title.replace("荔城区", "")
        title = title.replace("2024年", "")

        await input_title.fill(title)
        # 替换掉input_content中的“荔城区”三个字
        paragraphs = []
        for input_paragraph in input_paragraphs:
            old_content = await input_paragraph.text_content()
            modified_content = old_content.replace('荔城区', '')
            modified_content = modified_content.replace('2024年', '')
            paragraphs.append(f"<p>{modified_content}</p>")
        await self.execute_js(f"elem=>elem.innerHTML=`{''.join(paragraphs)}`", locator=input_content)
        btn_confirm = await self.get_elem_with_wait_by_xpath(10, "//button[./span[text()='确定']]")
        await btn_confirm.click()
        await asyncio.sleep(2)

    def find_target_file(self, dir_name: Path, file_name):
        for file in dir_name.iterdir():
            if file.name.startswith(file_name):
                return file
        return None
