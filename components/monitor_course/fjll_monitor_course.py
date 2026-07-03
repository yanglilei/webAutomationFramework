import asyncio
import time
from dataclasses import dataclass

from src.frame.base import BaseMonitorCourseTaskNode


@dataclass(init=False)
class FJLLMonitorCourse(BaseMonitorCourseTaskNode):
    content_name: str = ""
    # 线程启动的时间。用于判断学习过程中是否卡住了。实际时间有更新，但是学习时间没有更新，则认为当前学习卡住了。需要刷新页面或者重启学习线程。
    first_sys_time: int = 0
    cur_sys_time: int = 0
    first_cal_time_flag: bool = True
    pre_learned_time: str = ""
    cur_learned_time: str = ""

    async def prepare_before_poll_monitor_course(self):
        course_page = self.get_prev_output().get('course_page')
        if not course_page:
            return False, '没有传递课程页面参数：course_page'
        await self.switch_to_window(course_page)
        choose_one_course_elem = await self.get_elem_with_wait_by_xpath(3, "(//span[@class='choose-content'])[1]")
        if choose_one_course_elem:
            await choose_one_course_elem.click()
        return True, ""

    async def single_poll_monitor(self):
        current_content_elem = await self.get_elem_with_wait_by_xpath(10, "//ul[@class='kc-list']//li[./h5[contains(@style, 'rgb(166')]]")
        if current_content_elem:
            # 获取课程进度
            content_name_elem = await self.get_relative_elem_by_xpath(current_content_elem, "./h5")
            self.content_name = await content_name_elem.text_content() if content_name_elem else ""
            progress_elem = await self.get_relative_elem_by_xpath(current_content_elem, ".//div[@class='kc-info']/span[2]")
            if progress_elem and "100.00" in await progress_elem.text_content():
                # 读完了，获取下一个视频
                next_content = await self.get_elem_with_wait_by_xpath(10, "(//ul[@class='kc-list']//li[./h5[contains(@style, 'rgb(166')]]/following-sibling::li)[1]")
                if not next_content:
                    # 没有下一个视频了
                    self.terminate("已学完")
                    return
                else:
                    if not await next_content.is_visible():
                        await next_content.scroll_into_view_if_needed()
                        await asyncio.sleep(1)
                    await next_content.click()
                    return

        # 处理暂停
        await self.play_video("div#video video")
        play_time_elem = await self.get_elem_by_css("div.custom-video-process-time")
        play_time = await play_time_elem.text_content()
        self.logger.info(f"【{self.content_name}】进度：{play_time if play_time else '没获取到时间'}")

        if self.poll_count == 0:
            # 第一次轮询记录播放的时间
            self.pre_learned_time = play_time
        elif self.poll_count % 60 == 0:
            # 轮询一次3秒，每3分钟监测一次时间是否卡住
            if self.pre_learned_time == play_time:
                # 卡了3分钟，刷新页面
                await self.refresh()
            else:
                self.pre_learned_time = play_time


