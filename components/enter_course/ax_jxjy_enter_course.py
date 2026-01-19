import os
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from random import random
from typing import Tuple, List, Dict, Any

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from src.frame.base.base_enter_course_node import BaseEnterCourseTaskNode
from src.utils.sys_path_utils import SysPathUtils


@dataclass(init=False)
class AXJXJYEnterCourseTaskNode(BaseEnterCourseTaskNode):
    # 首页窗口句柄
    main_page_window_handler: str = ""
    # 工作空间窗口句柄
    workspace_window_handler: str = ""
    # 跳过的课程列表
    skip_course_list: List = field(default_factory=list)
    # 是否需要刷新页面
    is_page_load_error: bool = False
    # 上一次刷新时间
    pre_refresh_time: int = 0
    # 当前刷新时间
    cur_refresh_time: int = 0
    # 当前任务ID，用于记录是否切换了视频
    cur_job_id: str = ""
    # 教的课程名称
    teach_course_name: str = ""

    def set_up(self):
        self.teach_course_name = self.user_manager.get_cell_val(self.username, 2)

    def handle_prev_output(self, prev_output: Dict[str, Any]):
        skip_course_name = self.get_prev_output().get("skip_course")
        if skip_course_name and skip_course_name.strip():
            self.skip_course_list.append(skip_course_name.strip())

    def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        self.main_page_window_handler = self.web_browser.window_handles[0]
        # 进入工作空间
        if not self.enter_workspace():
            self.logger.error("进入工作空间异常")
            return False, "进入工作空间异常"
        self.switch_to_latest_window()

        if not self.has_chosen_course():
            self.close_other_windows(self.main_page_window_handler)
            # 未选择课程，则选择课程
            try:
                status, err_msg = self.choose_course()
                if not status:
                    return False, err_msg
            except Exception as e:
                self.logger.exception("选课异常，准备退出")
                return False, "选课异常"
            else:
                # 选课完成
                self.close_other_windows(self.main_page_window_handler)
                # 进入空间
                if not self.enter_workspace():
                    self.logger.error("进入工作空间异常")
                    return False, "进入工作空间异常"

        time.sleep(3)
        # 关闭首页
        self.workspace_window_handler = self.get_latest_window()
        self.switch_to_latest_window()

        # 进入课程
        status, desc = self.enter_course_list()
        if not status:
            if "已合格" in desc:
                self.logger.info("已合格，退出！")
                return False, "已合格"
            else:
                return False, "进入培训专题异常"

    def enter_course(self) -> Tuple[bool, str]:
        unfinished_course, preclick_flag = self.get_first_unfinished_course()
        if not unfinished_course:
            return False, "没有未完成课程"

        # if not preclick_flag:  # 此处有点多余，因为get_first_unfinished_course()中会进行预点击操作，若是有课程，此时已经进入了课程页面
        #     if not unfinished_course.is_displayed():
        #         unfinished_course.location_once_scrolled_into_view
        #         time.sleep(1)
        #     unfinished_course.click()
        #     self.web_browser.switch_to.default_content()
        #     # 等待打开新窗口
        #     time.sleep(2)
        # 切换窗口
        self.switch_to_latest_window()
        # 处理学习诚信承诺书
        self.handle_promission_tips()
        time.sleep(1)
        # 获取课程名称
        course_name = self.get_course_name()
        # 点击第一个视频开始学习
        if not self.enter_course_detail_page():
            # 进入课程详情页面失败
            # 关掉课程详情页面，回到工作空间，重新尝试
            self.close_latest_window()
            self.web_browser.switch_to.window(self.workspace_window_handler)
            self.refresh_course_list_current_page()
            return self.enter_course()
        # 等待跳转
        time.sleep(2)
        return True, course_name

    def handle_after_course_finished(self) -> Tuple[bool, str]:
        """
        一个课程结束后的操作逻辑
        :return: 切换成功返回：(True, 成功)；切换失败返回：(False, 失败原因)
        """
        self.close_latest_window()
        self.switch_to_window(self.workspace_window_handler)
        self.refresh_course_list_current_page()
        return True, "切换成功"

    def enter_workspace(self):
        ret = True
        btn_enter_workspace = self.get_elem_with_wait(10, (By.XPATH, "//div[@aria-label='去学习']/div"))
        try:
            btn_enter_workspace.click()
            # self.execute_js("arguments[0].click();", btn_enter_workspace)
        except:
            self.logger.error("用户【%s】点击【去学习】按钮失败" % self.username_showed)
            ret = False

        return ret

    def has_chosen_course(self):
        self.web_browser.switch_to.frame("frame_content")
        sign = self.get_elem_with_wait(10, (By.XPATH, "//li[@class='curr']//a"))
        if not sign or sign.text in ["进行中 (0)", "Processing (0)"]:
            self.web_browser.switch_to.default_content()
            return False
        else:
            self.web_browser.switch_to.default_content()
            return True

    def choose_course(self) -> Tuple[bool, str]:
        grade_idx = 1
        if "幼儿" in self.teach_course_name:
            grade_idx = 1
        elif "小学" in self.teach_course_name:
            grade_idx = 2
        elif "初中" in self.teach_course_name:
            grade_idx = 3
        elif "高中" in self.teach_course_name:
            grade_idx = 4
        else:
            self.logger.error("选课失败，课程名称【%s】无法判断课程年级" % self.teach_course_name)
            return False, f"选课失败-课程名称【{self.teach_course_name}】无法判断课程年级"

        xpath = f"(//div[@class='other_content top'][.//span[text()='去学习']]/following-sibling::div[@class='content_otherLR']//div[@class='rowBox']/div[@class='row justify-content-center'])[2]/div[{grade_idx}]//div[@class='componentBox_after vertical']"
        grade_item = self.get_elem_with_wait(10, (By.XPATH, xpath))
        try:
            if not grade_item.is_displayed():
                grade_item.location_once_scrolled_into_view
                time.sleep(1)
            grade_item.click()
            # self.execute_js("arguments[0].click();", grade_item)
        except:
            self.logger.error("用户【%s】点击【年段】按钮失败" % self.username_showed)
            return False, f"选课失败-进入【年段】失败"
        # 等待弹出新浏览器tab
        time.sleep(3)

        self.switch_to_latest_window()

        target_course = self.get_elem_with_wait(10, (By.XPATH,
                                                     f"//div[@class='content overflowHidMultiLine'][starts-with(text(), '{self.teach_course_name}')]"),
                                                False)
        while not target_course:
            btn_next_page = self.get_elem_with_wait(10, (By.XPATH, "//button[@class='btn-next']"), False)
            if btn_next_page and btn_next_page.is_enabled():
                # 跳到下一页
                self.execute_js("arguments[0].click();", btn_next_page)
                time.sleep(2)
                target_course = self.get_elem_with_wait(10, (By.XPATH,
                                                             f"//div[@class='content overflowHidMultiLine'][text()='{self.teach_course_name}']"),
                                                        False)
            else:
                # 到了最后一页，没有更多课程了，说明没有找到该课程
                self.logger.error("选课失败：没有找到【%s】课程" % (self.username_showed, self.teach_course_name))
                return False, f"选课失败-没有【{self.teach_course_name}】课程"

        self.execute_js("arguments[0].click();", target_course)
        time.sleep(2)
        btn_sign_up = self.get_elem_with_wait(10, (By.XPATH, "//a[contains(text(),'报名')]"))
        btn_sign_up.click()

        self.wait_for_visible(10, (By.XPATH, "//p[@class='px_tree_stit overhidden']"))

        btn_commit_info = self.get_elem_with_wait(10, (By.XPATH, "//a[@id='submit']"))
        btn_commit_info.click()
        if self.wait_for_visible(10, (By.XPATH, "//div[@class='w_paystatus_pic']")):
            self.logger.info("用户【%s】选课成功" % self.username_showed)

        return True, "选课成功"

    def enter_course_list(self):
        status = True
        desc = ""
        self.web_browser.switch_to.frame("frame_content")
        xpath_tmp = "//div[@class='l_tcourse_center h120'][.//dt[contains(text(), '教育培训')]][.//dd[4][contains(text(), '%s')]]/preceding-sibling::div[@class='l_tcourse_right fr clearf']//a"

        first_subject = self.get_elem_with_wait(10, (By.XPATH, xpath_tmp % '未合格'))
        if not first_subject:
            if self.get_elem((By.XPATH, xpath_tmp % '已合格')):
                # 学习已合格了，截图保存
                succ_dir = Path(SysPathUtils.get_root_dir(), "succ")
                succ_dir.mkdir(parents=True, exist_ok=True)
                self.web_browser.save_screenshot(succ_dir.joinpath(self.username + "-succ.png"))
                status = False
                desc = "已合格"
            else:
                # 进入课程失败截图
                error_dir = Path(SysPathUtils.get_root_dir(), "error", "安溪继续教育")
                error_dir.mkdir(parents=True, exist_ok=True)
                self.web_browser.save_screenshot(error_dir.joinpath(self.username + "-error" + str(
                    random.randint(0, 100000)) + ".png"))
                status = False
                desc = "进入异常"
        else:
            if not first_subject.is_displayed():
                first_subject.location_once_scrolled_into_view
                time.sleep(0.5)
            first_subject.click()
            self.web_browser.switch_to.default_content()
        return status, desc

    def get_first_unfinished_course(self):  # 返回第一个未完成课程和预点击状态，对每个课程都会做预点击操作，为什么这么做？因为有些课程点击了进不去（平台bug）。
        is_preclick_succ = False
        self.web_browser.switch_to.frame("frame_content")
        # 获取第一个未完成的课程
        # xpath = "//li[@class='l_tcourse_list moocCourse clearf'][.//span[@class='l_sprogress_text mal10' and not(contains(text(), '100%'))]][1]//a"
        xpath = "//li[@class='l_tcourse_list moocCourse clearf'][.//span[@class='l_sprogress_text mal10' and not(contains(text(), '100%'))]]//div[@class='px_form_btn l_sform_btn fr']"
        # TODO 关键测试xxxxx
        # xpath = "//li[@class='l_tcourse_list moocCourse clearf'][.//span[@class='l_sprogress_text mal10' and not(contains(text(), '100%'))]]//div[@class='px_form_btn l_sform_btn fr'][contains(@onclick, '师生沟通的艺术')]"
        course_elems = self.get_elems_with_wait(10, (By.XPATH, xpath), False)
        # 去掉被排除的课程！
        course_elems = self._exclude_courses(course_elems)
        course_elems = self._search_paginate(course_elems, xpath)
        if course_elems:
            # 1.预点击，检查是否弹出新窗口
            while not self._preclick(course_elems[0]):
                # 2.没有弹出新窗口，则排除该课程
                self.skip_course_list.append(self._get_course_name_in_course_list(course_elems[0]))
                course_elems = self._exclude_courses(course_elems)
                # 3.重新搜索
                course_elems = self._search_paginate(course_elems, xpath)
                if not course_elems:
                    break

            # 预点击成功，外头不要再点击，否则会出现元素过期的bug
            is_preclick_succ = True
            # self.close_latest_window()
            # self.switch_to_window(self.workspace_window_handler)
        if not course_elems:
            return None, is_preclick_succ
        else:
            return course_elems[0], is_preclick_succ

    def _exclude_courses(self, course_elems: List[WebElement]):
        tmp_need_remove_elems = []
        if self.skip_course_list:
            for course_name in self.skip_course_list:
                for course_elem in course_elems:
                    if course_name in course_elem.get_attribute("onclick"):
                        tmp_need_remove_elems.append(course_elem)
        course_elems = [course_elem for course_elem in course_elems if course_elem not in tmp_need_remove_elems]
        return course_elems

    def _search_paginate(self, course_elems, xpath):
        while not course_elems:
            is_succ = self.go_next_course_page()
            if is_succ:
                # 强制等待页面加载完成
                time.sleep(2)
                course_elems = self.get_elems_with_wait(10, (By.XPATH, xpath), False)
                # 去掉被排除的课程！
                course_elems = self._exclude_courses(course_elems)
            else:
                # 翻页失败，或则没有下一页了，则没有未读课程
                break
            # 等待页面加载完成
            time.sleep(2)
        return course_elems

    def go_next_course_page(self):
        # True-翻页成功；False-翻页失败
        # self.web_browser.switch_to.frame("frame_content")
        ret = True
        btn_next_page = self.get_elem_with_wait(10, (By.XPATH, "//li[@class='xl-nextPage']"), False)
        if not btn_next_page or not btn_next_page.is_enabled():
            ret = False
        else:
            if not btn_next_page.is_displayed():
                btn_next_page.location_once_scrolled_into_view
                time.sleep(1)

            try:
                btn_next_page.click()
            except:
                self.logger.exception("用户【%s】点击【下一页】按钮失败" % self.username_showed)
                ret = False
        return ret

    def _preclick(self, elem):
        ret = False
        # 预点击
        if not elem.is_displayed():
            elem.location_once_scrolled_into_view
            time.sleep(0.5)
        elem.click()
        # 等待新窗口打开
        max_wait_count = 10
        # 最多等待10秒
        while max_wait_count > 0:
            time.sleep(1)
            if len(self.web_browser.window_handles) == 3:
                ret = True
                break
            max_wait_count -= 1

        return ret

    def _get_course_name_in_course_list(self, elem):
        # onclick = "isAllowGoStudy('68f60c39048f4e00504d0bbb','2025年安溪县“初中信息科技”（职校）教师远程继续教育培训_《信息科技课程各学段学业质量标准分析》','1')"
        maches = re.findall(r"'(.*?)'", elem.get_attribute("onclick"), re.S)
        return maches[1].split("_")[1].strip()

    def handle_promission_tips(self):
        tips_elem = self.get_elem_with_wait(3, (By.XPATH, "//div[@class='popDiv course-pop']"))
        if tips_elem:
            self.get_elem((By.XPATH, "//input[@class='agreeButton']")).click()
            time.sleep(1)
            self.get_elem((By.XPATH, "//a[contains(@class, 'agreeStart') and text()='开始学习'][2]")).click()

    def get_course_name(self):
        course_name_elem = self.get_elem_with_wait(10, (By.XPATH, "//dd[@class='textHidden colorDeep']"))
        return "" if not course_name_elem else course_name_elem.get_attribute("title")

    def enter_course_detail_page(self):
        self.web_browser.switch_to.frame("frame_content-zj")
        contents = self.get_elems_with_wait(10, (By.XPATH,
                                                 "//li[./div[@class='chapter_item']//span[@class='catalog_points_yi' and text()>0]]"))
        if contents:
            if not contents[0].is_displayed():
                contents[0].location_once_scrolled_into_view
                time.sleep(0.5)
            contents[0].click()
            return True
        else:
            return False

    def refresh_course_list_current_page(self):
        self.web_browser.switch_to.frame("frame_content")
        btn_refresh = self.get_elem_with_wait(10, (By.XPATH, "//div[@class='pagination']//li[@class='xl-active']"),
                                              False)
        if btn_refresh:
            if not btn_refresh.is_displayed():
                btn_refresh.location_once_scrolled_into_view
                time.sleep(1)
            # btn_refresh.click()
            self.execute_js("arguments[0].click()", btn_refresh)
        self.web_browser.switch_to.default_content()

