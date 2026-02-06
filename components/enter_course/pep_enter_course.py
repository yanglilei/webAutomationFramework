import asyncio
import random
import time
from typing import Tuple

from Demos.win32ts_logoff_disconnected import username

from src.frame.base import BaseEnterCourseTaskNode


class PEPEnterCourse(BaseEnterCourseTaskNode):
    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        return True, ""

    async def enter_course(self) -> Tuple[bool, str]:
        course_ids = await self.get_courses()
        if not course_ids:
            return False, "获取科目失败！"
        return await self._enter_courses(course_ids)

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        pass

    async def get_courses(self):
        elements = await self.get_elems_with_wait_by_xpath(10,
                                                     "//div[@class='container_xksx_gztb2020b']//*[@id='sid']//option",
                                                     False)
        return [await elem.get_attribute("value") for elem in elements]

    async def _enter_courses(self, course_ids):
        # current_url = self.get_current_url()
        url_prefix = "https://wp.pep.com.cn/web/index.php?/px/index/186"
        for course_id in course_ids:
            url = url_prefix + f'/{course_id}'
            await self.open_in_new_window(url)
            await self.switch_to_latest_window()
            alert_close_btn = await self.wait_for_visible_by_xpath(4,
                                                             "//div[@class='container_tzgg_gztb2020b']//img[@class='btn_close_tzgg']")
            if alert_close_btn:
                await alert_close_btn.click()
            await asyncio.sleep(1)
        # 关掉第一个窗口
        await self.close_window(self.get_windows()[0])

        all_subject_enter_status = []
        subject_status_desc = []
        windows = self.get_windows()
        for window in windows:
            await self.switch_to_window(window)
            is_enter_course  = await self._wait_for_open_course()
            all_subject_enter_status.append(is_enter_course)
            if not is_enter_course:
                subject_name_elem = await self.get_elem_by_xpath("//div[@class='container_user_gztb2020b']//h5")
                subject_name = await subject_name_elem.text_content()
                subject_status = f"学科【{subject_name}】未开始！"
                self.logger.info(subject_status)
                subject_status_desc.append(subject_status)
                # 没有未读的课程，关闭窗口
                await self.close_window(window)

        if not any(all_subject_enter_status):
            self.logger.info("课程未开始")
            if self.user_manager:
                self.user_manager.update_record_by_username(username, {4: "课程未开始"})
            return False, "课程未开始"
        elif subject_status_desc:
            self.user_manager.update_record_by_username(username, {4: "部分学科未开始！"})
        return True, ""

    async def _wait_for_open_course(self):
        # 获取必修课的开课时间
        xpath = "//tbody[.//td[@class='txt_pxkc_xk'][./h4[contains(text(), '必修')]]]//td[@class='txt_pxrk']//a"
        elems = await self.get_elems_with_wait_by_xpath(4, xpath)
        if not elems:
            return False
        for elem in elems:
            await elem.click()
            await asyncio.sleep(random.uniform(0.5, 1.5))
        return True