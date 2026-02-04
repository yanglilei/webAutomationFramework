import asyncio
from signal import valid_signals
from typing import Tuple

from src.frame.base import BaseEnterCourseTaskNode


class PEPEnterCourse(BaseEnterCourseTaskNode):
    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        pass

    async def enter_course(self) -> Tuple[bool, str]:
        course_ids = await self.get_courses()
        await self._enter_courses(course_ids)
        return True, ""

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        pass

    async def get_courses(self):
        elements = await self.get_elems_with_wait_by_css(10, "div.container_xksx_gztb2020b #sid option")
        return [await elem.get_attribute("value") for elem in elements]

    async def _enter_courses(self, course_ids):
        # current_url = self.get_current_url()
        url_prefix = "https://wp.pep.com.cn/web/index.php?/px/index/186"
        for course_id in course_ids:
            url = url_prefix + f'/{course_id}'
            await self.open_in_new_window(url)
            await self.switch_to_latest_window()
            alert_close_btn = await self.wait_for_visible_by_css(4, "div.container_tzgg_gztb2020b img.btn_close_tzgg")
            await alert_close_btn.click()
            await asyncio.sleep(1)
        # 关掉第一个窗口
        await self.close_window(self.get_windows()[0])


        while True:
            windows = self.get_windows()
            for window in windows:
                await self.switch_to_window(window)
                if await self._wait_for_open_course():
                    break


    async def _wait_for_open_course(self):
        # 获取必修课的开课时间
        xpath = "//tbody[.//td[@class='txt_pxkc_xk'][./h4[contains(text(), '必修')]]]//td[@class='txt_pxkc_pxxx']//span[@class='showtime_lesson']"
        xpath = "//tbody[.//td[@class='txt_pxkc_xk'][./h4[contains(text(), '必修')]]]//td[@class='txt_pxrk']//img"
        elems = await self.get_elems_with_wait_by_xpath(4, xpath)
        for elem in elems:
            if await elem.get_attribute("src") != "https://wp.pep.com.cn/web/views/default/img/btn_wks.jpg":
                await elem.click()
                return True
        return False

