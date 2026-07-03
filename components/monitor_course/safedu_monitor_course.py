from src.frame.base.base_monitor_course_node import BaseMonitorCourseTaskNode


class SAFEDUMonitorCourse(BaseMonitorCourseTaskNode):

    async def prepare_before_poll_monitor_course(self):
        speed_up_play_cmd = "document.querySelector('video.vjs-tech').playbackRate=16.0"
        await self.execute_js(speed_up_play_cmd)

    async def single_poll_monitor(self):
        if await self.is_current_course_finished():
            self.terminate("已学完！")
            return
        # 处理暂停
        await self.play_video("video.vjs-tech")
        remaining_time = await self.get_remaining_time()
        self.logger.info(f"当前课程【{self.course_name}】剩余时间：{remaining_time}")

    async def is_current_course_finished(self):
        elem = await self.get_elem_by_xpath("//div[@class='vjs-control-bar']/button[1]")
        if elem:
            return True if "vjs-ended" in await elem.get_attribute("class") else False
        return False

    async def get_remaining_time(self):
        # display_time_elem = self.get_elem_by_css('div.vjs-remaining-time-display')
        # if display_time_elem:
        #     return display_time_elem.text
        # else:
        #     return ""
        return await self.execute_js("document.querySelector('div.vjs-remaining-time-display').textContent")
