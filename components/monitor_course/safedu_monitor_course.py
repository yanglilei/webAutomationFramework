import time

from src.frame.base.base_monitor_course_node import BaseMonitorCourseTaskNode


class SAFEDUMonitorCourse(BaseMonitorCourseTaskNode):

    def single_poll_monitor(self):
        if self.is_current_course_finished():
            self.terminate("已学完！")
            return
        # 处理暂停
        self.play_video("video.vjs-tech")
        remaining_time = self.get_remaining_time()
        self.logger.info(f"当前课程【{self.course_name}】剩余时间：{remaining_time}")

    def is_current_course_finished(self):
        elem = self.get_elem_by_xpath("//div[@class='vjs-control-bar']/button[1]")
        if elem:
            return True if "vjs-ended" in elem.get_attribute("class") else False
        return False

    def get_remaining_time(self):
        # display_time_elem = self.get_elem_by_css('div.vjs-remaining-time-display')
        # if display_time_elem:
        #     return display_time_elem.text
        # else:
        #     return ""
        return self.execute_js("return document.querySelector('div.vjs-remaining-time-display').textContent")

    def handle_slider_bar(self):
        slider_bar = self.get_elem_by_xpath("//div[@class='handler handler_bg']")
        if slider_bar and slider_bar.is_enabled() and slider_bar.is_displayed():
            slider_bar.click()
            ac = self.get_action_chains()
            ac.click_and_hold(slider_bar)
            ac.move_by_offset(260, 0).perform()
            time.sleep(1)
            ac.release().perform()
            self.wait_for_disappeared_by_xpath(3, "//div[@class='handler handler_bg']")
            self.logger.info("用户【{}】处理滑块成功".format(self.username_showed))
        else:
            self.logger.info("用户【{}】没有处理滑块".format(self.username_showed))
