import asyncio
import random
from typing import Tuple

from src.frame.base import BaseEnterCourseTaskNode
from src.frame.common.exceptions import BusinessException


class PEPEnterCourse(BaseEnterCourseTaskNode):
    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        return True, ""

    async def enter_course(self) -> Tuple[bool, str]:
        subject_ids = await self.get_subjects()
        if not subject_ids:
            return False, "获取科目失败！"
        return await self._enter_courses(subject_ids)

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        pass

    async def get_subjects(self):
        elements = await self.get_elems_with_wait_by_xpath(10,
                                                           "//div[@class='container_xksx_gztb2020b']//*[@id='sid']//option",
                                                           False)
        return [await elem.get_attribute("value") for elem in elements]

    async def get_current_subject(self):
        subject_name_elem = await self.get_elem_by_xpath("//*[@id='sid']/option[@selected='selected']")
        subject_name = await subject_name_elem.text_content()
        return subject_name

    async def _close_alert(self):
        alert_close_btn = await self.wait_for_visible_by_xpath(4,
                                                               "//div[@class='container_tzgg_gztb2020b']//img[@class='btn_close_tzgg']")
        if alert_close_btn:
            await alert_close_btn.click()

    async def _enter_courses(self, subject_ids):
        # current_url = self.get_current_url()
        url_prefix = "https://wp.pep.com.cn/web/index.php?/px/index/186"
        # 获取第一个窗口的url
        current_url = await self.get_current_url()

        for subject_id in subject_ids:
            url = url_prefix + f'/{subject_id}'
            await self.open_in_new_window(url)
            await self.switch_to_latest_window()
            await self._close_alert()
            await asyncio.sleep(2)

        windows = await self.get_windows_by_url_key(current_url, False)
        if windows:
            # 关掉第一个窗口
            await self.close_window(windows[0])

        all_subject_enter_status = []
        # subject_status_desc = []
        windows = self.get_windows()
        for window in windows:
            await self.switch_to_window(window)
            subject_name, status_desc = await self._wait_for_open_course()
            subject_status = f"学科【{subject_name}】{status_desc}"
            self.logger.info(subject_status)
            if status_desc != "正在学习":
                # 没有未读的课程，关闭窗口
                await self.close_window(window)
                all_subject_enter_status.append(False)
            else:
                all_subject_enter_status.append(True)

            if self.user_manager:
                self.user_manager.update_record_by_username(self.username, {4: f"{subject_status}|"}, True)

        if not any(all_subject_enter_status):
            return False, "课程未开始或已完成！"
        return True, ""

    async def _wait_for_open_course(self):
        # 科目名称
        subject_name = await self.get_current_subject()
        current_url = await self.get_current_url()
        # 未完成的课程名称
        course_names = await self._get_unfinished_course_names()
        if not course_names:  # 科目已完成
            return subject_name, "已完成"
        # 重新加载之前的链接
        await self.load_url(current_url)
        # btn_learn = await self.get_elem_with_wait_by_xpath(10, "//a[text()='课程学习']")
        # await btn_learn.click()
        # 关闭提示
        await self._close_alert()
        # 获取必修课的开课时间
        xpath = "//tbody[.//td[@class='txt_pxkc_xk'][./h4[contains(text(), '必修')]]]"
        elems = await self.get_elems_with_wait_by_xpath(4, xpath)
        if not elems:
            return subject_name, "异常：无必修课"

        enter_course_status = []
        for elem in elems:
            child_xpath = ".//h4"
            child_elem = await self.get_relative_elem_by_xpath(elem, child_xpath)
            course_name = await child_elem.text_content()
            if course_name in course_names:
                child_xpath = ".//td[@class='txt_pxrk']//a"
                child_elem = await self.get_relative_elem_by_xpath(elem, child_xpath)
                if child_elem:
                    # url = await child_elem.get_attribute("href")
                    # await self.open_in_new_window(url)
                    await self.js_click(child_elem)
                    enter_course_status.append(True)
                else:
                    self.logger.error(f"无法进入课程学习，按钮为灰色，课程名【{course_name}】")
                    enter_course_status.append(False)
            else:
                enter_course_status.append(False)
            await asyncio.sleep(random.uniform(0.5, 2.5))

        return subject_name, "正在学习" if any(enter_course_status) else "课程信息异常，人工介入"

    async def _update_subject_status(self):
        subject_name = await self.get_current_subject()
        if self.user_manager:
            self.user_manager.update_record_by_username(self.username, {4: f"学科【{subject_name}】已结束"}, True)
        return subject_name

    async def _get_unfinished_course_names(self):
        # 点击进入学习数据
        btn_progress = await self.get_elem_with_wait_by_xpath(10, "//a[text()='学习数据']")
        if not btn_progress:
            raise BusinessException("未找到【学习数据】按钮！")
        await btn_progress.click()

        xpath = "//li[@class='fl ell'][contains(text(), '必修')]"
        # 获取必修课
        elems = await self.get_elems_with_wait_by_xpath(10, xpath)
        target_course_names = []
        for elem in elems:
            child_xpath = "./following-sibling::li"
            child_elem = await self.get_relative_elem_by_xpath(elem, child_xpath)
            if child_elem:
                child_text = await child_elem.text_content()
                if "100%" not in child_text:
                    target_course_names.append(await elem.text_content())
        return target_course_names