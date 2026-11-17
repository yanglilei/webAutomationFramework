import asyncio

from src.frame.base import BaseMonitorCourseTaskNode


class PEPMonitorCourse(BaseMonitorCourseTaskNode):

    async def prepare_before_poll_monitor_course(self):
        pass

    async def single_poll_monitor(self):
        # self.switch_to_window_by_url_key("bjpep.gensee.com")
        tabs = await self.get_windows_by_url_key("bjpep.gensee.com")
        course_finished_status = []
        for tab in tabs:
            await self.switch_to_window(tab, False)
            await asyncio.sleep(0.5)
            # 获取播放声音
            if btn_no_muted:= await self.get_elem_by_xpath("//button[text()='播放声音']"):
                if btn_no_muted and await btn_no_muted.is_visible() and await btn_no_muted.is_enabled():
                    try:
                        await self.js_click(btn_no_muted)
                    except:
                        self.logger.error("点击‘播放声音’按钮失败！")

            course_name_elem = await self.get_elem_by_xpath("//div[@class='gs-live-in-fo']")
            course_name = await course_name_elem.text_content() if course_name_elem else ""
            played_str, total_str = await self.execute_js("""
            () => {
                const playedEl = document.querySelector('.time_one1');
                const totalEl = document.querySelector('.time_one2');
                return [playedEl?.textContent || '', totalEl?.textContent || ''];
            }
            """)
            played_time = self.format_video_time(played_str) if played_str else played_str
            total_time = self.format_video_time(total_str) if total_str else total_str
            self.logger.info(f"【{course_name}】{played_time}/{total_time}")
            # 出现视频结束的按钮
            btn_play_stop = await self.get_elem_by_xpath("//button[@class='stop-reporting-btn']")
            if (played_time == total_time and played_time != "00:00:00") or (btn_play_stop and await btn_play_stop.is_visible()):
                self.logger.info(f"【{course_name}】播放完成")
                await self.close_window(tab)
                course_finished_status.append(True)
                continue

            course_finished_status.append(False)

            # 解决暂停
            btn_play = await self.get_elem_by_css("#playBtn")
            if btn_play and "gs-icon-pause" not in await btn_play.get_attribute("class"):
                await self.js_click(btn_play)

        if all(course_finished_status):
            self.terminate("今日所有课程已学完！")