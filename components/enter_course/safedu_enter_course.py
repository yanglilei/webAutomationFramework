from dataclasses import dataclass
from typing import Tuple

import time

from src.frame.base.base_enter_course_node import BaseEnterCourseTaskNode

@dataclass(init=False)
class SAFEDUEnterCourse(BaseEnterCourseTaskNode):

    course_page_window_handler: str = ""

    def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        # 等待跳转到首页
        while True:
            current_url = self.get_current_url(self.get_latest_window())
            if "safedu.org.cn/home" not in current_url:
                self.logger.info("等待跳转到首页")
                time.sleep(1)
            else:
                self.logger.info("已跳转到首页")
                break

        btn_enter_manager_center = self.get_elem_with_wait_by_xpath(10, "//span[@class='glcenter']")
        # 点击管理中心，打开新的窗口
        btn_enter_manager_center.click()
        self.switch_to_window(self.get_latest_window())
        time.sleep(2)
        tab_my_training = self.get_elem_with_wait_by_xpath(10, "//a[text()='我的培训']")
        tab_my_training.click()
        target_iframe = self.wait_for_visible_by_xpath(10, "//iframe[@name='iframe0']")
        self.switch_to_frame(target_iframe)
        course_link = self.get_elem_by_css("table#myassess tbody tr:nth-child(1) td:nth-child(1) a")
        if not course_link:
            self.logger.error("未找到课程链接")
            return False, "未找到课程链接"
        # 点击后弹出新窗口
        course_link.click()
        # 等待新窗口打开
        time.sleep(2)
        self.course_page_window_handler = self.get_latest_window()
        self.close_other_windows(self.course_page_window_handler)
        return True, ""

    def enter_course(self) -> Tuple[bool, str]:
        first_unfinished_course = self.get_first_unfinished_course()
        if not first_unfinished_course:
            self.logger.error("未找到未完成课程")
            return False, "未找到未完成课程"
        # 获取课程名称
        course_name = self.get_relative_elem_by_xpath(first_unfinished_course, "./following-sibling::h5").text
        if first_unfinished_course:
            first_unfinished_course.click()
            # 每天2个课时的弹窗
            btn_confirm = self.wait_for_visible_by_xpath(3, "//div[@class='layui-layer-btn']/a")
            if btn_confirm:
                btn_confirm.click()
                return False, "每天只能学2个课时"
            # 等待打开新窗口
            time.sleep(2)
            # 切换到最新窗口
            self.switch_to_latest_window()
            return True, course_name
        else:
            self.logger.error("未找到未完成课程")
            return False, "未找到未完成课程"

    def handle_after_course_finished(self) -> Tuple[bool, str]:
        self.close_other_windows(self.course_page_window_handler)
        # 刷新页面
        self.refresh()
        # 等待页面加载完成
        time.sleep(2)
        return True, ""
        # 进入课程
        # return self.enter_course()

    def get_first_unfinished_course(self):
        return self.get_elem_with_wait_by_xpath(3, "(//a[@class='lazybg'][./following-sibling::span[not(contains(@class,'already'))]])[1]")

