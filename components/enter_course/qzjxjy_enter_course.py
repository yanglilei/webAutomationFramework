import asyncio
import random
from dataclasses import dataclass
from typing import Tuple

from playwright.async_api import Page

from src.frame.base import BaseEnterCourseTaskNode


@dataclass(init=False)
class QZJXJYEnterCourse(BaseEnterCourseTaskNode):
    """
    泉州专业技术人员继续教育网络学习平台
    https://www.qzjxjy.com/homefourthIndex
    """
    class_name: str = ""
    video_page: Page = None
    course_page: Page = None

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        self.class_name = self.node_config.get("node_params", {}).get("class_name", "")
        if not self.class_name:
            return False, "未获取到班级名称"
        await self.handle_unfinished_tips()
        btn_workspace = await self.get_elem_with_wait_by_xpath(10, "//div[@class='login-after']//div[text()='去学习']")
        # await btn_workspace.click()
        await self.js_click(btn_workspace)
        xpath = f"//ul[@class='m-class-list']//li[.//div[@class='learning-tit'][contains(text(), '{self.class_name}')] and not(img)]//button[.//span[text()='立即学习 ']]"
        btn_enter_course = await self.get_elem_with_wait_by_xpath(10, xpath)
        if btn_enter_course:
            await btn_enter_course.click()
            self.course_page = self.get_current_page()
            return True, ""
        else:
            return False, "没找到课程或课程已学完！"

    async def enter_course(self) -> Tuple[bool, str]:
        first_unfinished_course, course_name = await self.get_first_unfinished_course()
        if first_unfinished_course:
            await first_unfinished_course.click()

            video_pages = []
            max_wait_time = 20
            while max_wait_time > 0:
                if video_pages:=await self.get_windows_by_url_key("www.qzjxjy.com/play/study"):
                    break
                max_wait_time -= 1
                await asyncio.sleep(1)

            if video_pages:
                self.video_page = video_pages[0]
                await self.switch_to_window(self.video_page)
                self.set_output_data("video_page", self.video_page)
                return True, course_name
            else:
                return False, "进入学习页面失败"
        else:
            return False, "没有未完成的课程"

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        # await self.close_window(self.video_page)
        await self.close_other_windows(self.course_page)
        await self.refresh()
        return True, ""

    async def get_first_unfinished_course(self):
        xpath = "(//ul[@class='m-detail-list']//li[.//p/span[text()='未合格']])[1]"
        course_item = await self.get_elem_with_wait_by_xpath(10, xpath)
        if course_item:
            btn_enter_course = await self.get_relative_elem_by_xpath(course_item, ".//div[@class='op']/button")
            course_name_elem = await self.get_relative_elem_by_xpath(course_item, ".//span[@class='tit']/i")
            return btn_enter_course, await course_name_elem.text_content()
        else:
            return None, ""
        # ret = None
        # unfinished_courses_tab = await self.get_elem_with_wait_by_xpath(10, "//div[@id='tab-unlearn' or @id='tab-unStudy']")
        # if not unfinished_courses_tab:
        #     raise BusinessException("没有找到未完成的课程标签")
        # else:
        #     try:
        #         await unfinished_courses_tab.click()
        #     except:
        #         self.logger.exception("点击“未完成课程”的标签失败")
        #         raise BusinessException("点击“未完成课程”的标签失败")
        #     else:
        #         # 等待切换到未完成的课程页面
        #         await asyncio.sleep(5)
        #         ret = await self.get_elem_with_wait_by_xpath(10, "//ul[@class='m-detail-list']//li[1]//button[.//*[contains(text(),'课程学习')]]")
        # return ret

    async def handle_unfinished_tips(self):
        tips_window = await self.wait_for_visible_by_xpath(5, "//div[@role='dialog' and @aria-label='未完成培训提醒']")
        if tips_window:
            no_tips_anymore = await self.get_elem_by_xpath("//div[@role='dialog' and @aria-label='未完成培训提醒']//span[@class='el-checkbox__input']")
            if no_tips_anymore:
                await self.js_click(no_tips_anymore)
            await asyncio.sleep(random.uniform(0.1, 2))
            btn_pause = await self.get_elem_by_xpath("//div[@role='dialog' and @aria-label='未完成培训提醒']//button[./span[text()='暂不学习']]")
            if btn_pause:
                await self.js_click(btn_pause)