import asyncio
from dataclasses import dataclass

from playwright.async_api import Page

from src.frame.base import BaseMonitorCourseTaskNode


@dataclass(init=False)
class TTCDWMonitorCourse(BaseMonitorCourseTaskNode):
    video_page: Page = None
    course_page: Page = None

    async def prepare_before_poll_monitor_course(self):
        self.video_page = self.get_prev_output().get("video_page")
        self.course_page = self.get_prev_output().get("course_page")
        await self.switch_to_window(self.video_page)
        # 获取第一个未完成的视频
        first_unfinished_video = await self.get_elem_with_wait_by_xpath(10, "//div[contains(@class, 'videorevision-catalogue-single') and @data-progress and @data-progress != '1']")
        if first_unfinished_video:
            # await first_unfinished_video.click()
            await self.js_click(first_unfinished_video)

    async def single_poll_monitor(self):
        await self._handle_pause()
        if await self.is_video_ended("div#video-Player video"):
            await self._switch_to_next_content()
            return

        await self.play_video("div#video-Player video")

        current_content = await self.get_elem_by_xpath("//div[@class='videorevision-catalogue-single on']")
        progress = await current_content.get_attribute("data-progress")
        if progress == "1":
            await self._switch_to_next_content()
            return
        el_content_name = await self.get_relative_elem_by_xpath(current_content, ".//div[@class='videorevision-catalogue-single-name ellipsis']")
        content_name = await el_content_name.text_content() if el_content_name else ""
        played_time, total_time = await self._get_played_time_and_total_time()
        self.logger.info(f"【{self.course_name}-{content_name}】已播放时间：{played_time}，总时间：{total_time}")
        # if self.poll_count > 0 and self.poll_count % 200 == 0:
        #     # 每隔10分钟刷新一次页面，避免掉线
        #     await self.switch_to_window(self.course_page)
        #     await self.refresh()

    async def _switch_to_next_content(self):
        # 获取第一个未完成的视频
        first_unfinished_video = await self.get_elem_with_wait_by_xpath(10,
                                                                        "//div[contains(@class, 'videorevision-catalogue-single') and @data-progress != 1]")
        if first_unfinished_video:
            if not await first_unfinished_video.is_visible():
                await first_unfinished_video.scroll_into_view_if_needed()
                await asyncio.sleep(2)
            await self.js_click(first_unfinished_video)
        else:
            self.logger.info("课程已结束")
            self.terminate("课程已结束！")

    async def _handle_pause(self):
        # 判断是否弹出打卡
        btn_check_in = await self.get_elem_by_xpath("//button[@id='comfirmClock' and contains(text(),'打卡')]")
        if btn_check_in:
            # await btn_check_in.click()
            await self.js_click(btn_check_in)
            # 获取继续学习按钮
            btn_continue = await self.get_elem_with_wait_by_xpath(3, "//button[@id='comfirmClock' and text()='继续学习']")
            if btn_continue:
                # await btn_continue.click()
                await self.js_click(btn_continue)

    async def _get_played_time_and_total_time(self):
        ret = None, None
        try:
            played_time_js = "document.querySelector('.xgplayer-time span:nth-of-type(1)').textContent"
            total_time_js = "document.querySelector('.xgplayer-time span:nth-of-type(2)').textContent"
            played_time = await self.execute_js(played_time_js)
            total_time = await self.execute_js(total_time_js)
        except:
            # 没有找到已经播放完的时间
            self.logger.error("没有获取到时间，页面出现异常！")
        else:
            ret = played_time, total_time
        return ret

    async def _is_last_content_finished(self):
        next_content = await self.get_elem_by_xpath("//div[@class='videorevision-catalogue-single on']/following-sibling::div")
        if await self.is_video_ended("div#video-Player video") and not next_content:
            return True
        return False