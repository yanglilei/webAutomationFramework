from src.frame.base.base_monitor_course_node import BaseMonitorCourseTaskNode


class SAFEDUMonitorCourse(BaseMonitorCourseTaskNode):

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

    async def handle_slider_bar(self):
        slider_bar = await self.get_elem_by_xpath("//div[@class='handler handler_bg']")
        if slider_bar and await slider_bar.is_enabled() and await slider_bar.is_visible():
            box = await slider_bar.bounding_box()
            window = self.get_latest_window()
            x_pos = box["x"] + box["width"] / 2
            y_pos = box["y"] + box["height"] / 2
            mouse = window.mouse
            await mouse.move_to(x=x_pos, y=y_pos)
            await mouse.down()
            await mouse.move(x_pos + 260, y_pos, 10)
            await mouse.up()
            await self.wait_for_disappeared_by_xpath(3, "//div[@class='handler handler_bg']")
            self.logger.info(f"用户【{self.username_showed}】处理滑块成功")
        else:
            self.logger.info(f"用户【{self.username_showed}】没有处理滑块")
