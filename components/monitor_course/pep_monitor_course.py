from src.frame.base import BaseMonitorCourseTaskNode


class PEPMonitorCourse(BaseMonitorCourseTaskNode):

    def prepare_before_poll_monitor_course(self):
        pass

    def single_poll_monitor(self):
        # self.switch_to_window_by_url_key("bjpep.gensee.com")
        tabs = self.get_windows_by_url_key("bjpep.gensee.com")
        course_finished_status = []
        for tab in tabs:
            self.switch_to_window(tab)
            # 获取播放声音
            if btn_no_muted:= self.get_elem_by_xpath("//button[text()='播放声音']"):
                if btn_no_muted.states.is_displayed and btn_no_muted.states.is_enabled:
                    btn_no_muted.click(by_js=True)

            course_name_elem = self.get_elem_by_xpath("//div[@class='gs-live-in-fo']")
            course_name = course_name_elem.text if course_name_elem else ""
            times = self.execute_js("""let played_time = document.querySelector('.time_one1').textContent;
                        let total_time = document.querySelector('.time_one2').textContent;
                        return [played_time, total_time];
                        """)
            played_time = self.format_video_time(times[0])
            total_time = self.format_video_time(times[1])
            self.logger.info(f"课程：【{course_name}】播放进度: {played_time}/{total_time}")
            if played_time == total_time and played_time != "00:00:00":
                self.logger.info(f"课程：【{course_name}】播放完成")
                self.close_window(tab)
                course_finished_status.append(True)
                continue

            course_finished_status.append(False)

            # 解决暂停
            btn_play = self.get_elem_by_css("#playBtn")
            if btn_play and "gs-icon-pause" not in btn_play.attr("class"):
                btn_play.click(by_js=True)

        if all(course_finished_status):
            self.terminate("今日所有课程已学完！")
