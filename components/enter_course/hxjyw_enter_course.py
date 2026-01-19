import json
import time
from dataclasses import dataclass, field
from typing import Tuple, Dict, Any

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from src.frame.base.base_enter_course_node import BaseEnterCourseTaskNode
from src.frame.common.exceptions import BusinessException


@dataclass(init=False)
class HXJYWEnterCourseTaskNode(BaseEnterCourseTaskNode):
    """
    海西教育网进入课程
    1.支持通公需课和专业课的学习
    2.切换课程方式：支持在课程页面点击“返回”按钮和直接“关闭”课程页面两种
    """
    # 计划ID
    plan_id: str = ""
    # 专题ID
    phase_id: str = ""
    # 用户ID
    user_id: str = ""
    # 项目ID
    project_id: str = ""
    # 章节名称列表
    chapter_name_list: list = field(default_factory=list)
    # 课程名称
    course_name: str = ""
    # 排除的课程
    excluded_courses: list = field(default_factory=list)
    # 课程类型
    course_type: str = ""
    # 项目编码
    project_code: str = ""
    # 主窗口的URL
    main_window_url: str = ""

    def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        self.logger.info(f"用户【{self.username_showed}】开始执行【{self.node_config.get('node_name')}】")
        self.switch_to_latest_window()
        if not self.project_code:
            return False, "项目编码为空"

        if "hj" in self.project_code and "office/home" not in self.web_browser.current_url:
            # 跳转到选择项目页面
            self.web_browser.get("https://hxwyxpt.t-px.cn/office/home")
            time.sleep(2)

        self.course_type = self.node_config.get("node_params", {}).get("course_type")
        if not "intoStudentStudy" in self.web_browser.current_url:
            if self.course_type.split("|")[-1] == 1:
                # 进入公需课
                self._enter_pub_project()
            else:
                # 进入专业课
                self._enter_pro_project()
        # 等待页面加载完成
        # 处理完善个人信息的弹窗
        self._handle_complete_info_tips()
        time.sleep(3)
        self.wait_for_disappeared_by_xpath(20, "//div[@class='layui-layer-shade']")
        learn_tab = self.get_elem_with_wait_by_xpath(10, "//a[text()='学习计划']")
        learn_tab.click()
        self._init_plan_id()
        self._init_phase_id()

        self._init_user_id()
        self._init_project_id()
        self.main_window_url = self.web_browser.current_url
        if self._is_passed():
            # 学习通过了，无需学习
            self.logger.info(f"用户【{self.username_showed}】学习成绩已经合格了，准备退出")
            # self.do_after_finished_all_courses()
            return False, f"{self.course_type.split('|')[0]}已学完"
        else:
            # 处理完善个人信息的弹窗
            self._handle_complete_info_tips()
            # 处理课程页面的建议信息
            self._handle_course_page_tips()
            # 处理选课
            # self._handle_choose_course()
            # 判断课程类型
            # self._init_course_type()
            return True, ""

    def handle_after_course_finished(self) -> Tuple[bool, str]:
        # 排除掉这个课程
        self.excluded_courses.append(self.course_name)
        if btn_go_back := self.get_elem_by_css("div.goback_href"):
            # 点击返回
            self.execute_js("arguments[0].click()", btn_go_back)
            # 等待页面加载完成
            time.sleep(2)
        else:
            self.close_window(self.web_browser.window_handles[-1])
            self.web_browser.switch_to.window(self.main_window_url)
            self.web_browser.refresh()
        return True, ""

    def enter_course(self) -> Tuple[bool, str]:
        # 获得第一个未读的课程
        course = self._get_pub_first_course()
        if not course:
            self.logger.info("用户【%s】没有未学习的课程，准备退出" % self.username_showed)
            return False, f"{self.course_type.split('|')[0]}已学完"
        # 展开章节，让课程元素可见
        if not course.is_displayed():
            course.location_once_scrolled_into_view
            self.wait_for_visible(2, course)
        # 展开课程
        if not course.is_displayed():
            menu_elem = self.get_relative_elem_by_xpath(course,
                                                        "./ancestor::div[@class='module_wrap']/preceding-sibling::div/span[contains(@class, 'step')]")
            if menu_elem:
                # 点击展开
                menu_elem.click()
                # 等待3秒
                time.sleep(3)

        course_name = self.get_relative_elem(course, (By.XPATH, "./preceding-sibling::a")).text
        # 点击进入课程之前还需要进一步检测是否有弹窗等信息
        # 处理完善个人信息的弹窗
        self._handle_complete_info_tips()
        # 处理课程页面的建议信息
        self._handle_course_page_tips()
        # 点击进入学习页面
        try:
            self.execute_js("arguments[0].click()", course)
        except:
            self.logger.exception(f"用户【{self.username_showed}】点击进入课程【{self.course_name}】失败")
            return False, "点击进入课程失败"
        else:
            # 等待打开新窗口
            time.sleep(2)
            self.switch_to_latest_window()

        return True, course_name

    def handle_prev_output(self, prev_output: Dict[str, Any]):
        project_code = prev_output.get("project_code", "")
        if project_code and project_code.strip():
            self.project_code = project_code.strip()

    def send_node_output(self):
        """
        传递输出数据，可调用set_output_data方法设置输出的参数
        """
        self.set_output_data("project_code", self.project_code)

    def _get_pub_first_course(self) -> WebElement:
        ret = None
        xpath = "//a[(./preceding-sibling::i/text() = '学习中' or ./preceding-sibling::i/text() = '未学习') and @class='list-title'][.//following-sibling::a[text()='进入学习']]"
        if "hxwysqy2025" in self.project_code or "hxxy2025" in self.project_code:
            xpath = "//a[(./preceding-sibling::i/text() = '学习中' or ./preceding-sibling::i/text() = '未学习') and @class='layui-btn layui-btn-primary' and @data-type='课程' ]"

        courses = self.get_elems_with_wait_by_xpath(10, xpath, False)
        if courses:
            for course in courses:
                if course.text not in self.excluded_courses:
                    ret = course
                    break
        return ret

    def _get_first_content(self):
        if "hxwysqy2025" in self.project_code:
            contents = self.get_elems_with_wait(10, (
                By.XPATH, "(//li[contains(@class, 'isStudy')])[last()]//following::li[contains(@class, 'type_1')]"))
            if contents:
                first_content = contents[0]
                if not first_content.is_displayed():
                    first_content.location_once_scrolled_into_view
                return first_content
            else:
                return None
        else:
            first_content = None
            try:
                first_content: WebElement = self.get_elem_with_wait_by_xpath(3,
                                                                             "//div[@class='course-list-con']//li[contains(@class, 'cur')]//a",
                                                                             False)
            except:
                pass
            else:
                if not first_content.is_displayed():
                    first_content.location_once_scrolled_into_view
                    # if self.course_type == HXCourseType.PRO_COURSE:
                    # # 获取目录所处的章节，目的为了点击展开章节，让目录可见，才能点击
                    # chapter_elem: WebElement = first_content.find_element(By.XPATH,
                    #                                                       "../../preceding-sibling::h4//a")
                    # chapter_elem.click()
                    # time.sleep(1)
                    # if not first_content.is_displayed():
                    #     first_content.location_once_scrolled_into_view
            return first_content

    def _get_content_name(self, cur_content: WebElement):
        ret = None
        if "hxwysqy2025" in self.project_code:
            ret = cur_content.get_attribute("title")
        else:
            try:
                course_name_elem: WebElement = self.get_elem_with_wait_by_xpath(5, "//div[@class='course-info']//a")
            except Exception as e:
                self.logger.error("用户【%s】没有获取到课程名称，页面出现异常！" % (self.username_showed,))
            else:
                ret = course_name_elem.text + "(" + cur_content.text + ")"
        return ret

    def _wait_for_shade_disappear(self):
        self.wait_for_disappeared_by_xpath(2, "//div[@class='layui-layer-shade']")

    def _is_cur_content_contains_video(self):
        return True if self.get_elem_with_wait_by_xpath(3, "//div[@class='ccH5playerBox']", False) else False

    def _play_video(self):
        self.execute_js("""let css_expr = 'div.ccH5playerBox video';
            let video = document.querySelector(css_expr);
            if (video != null && !video.muted) {
                video.muted = true;
            }
        
            css_expr = 'div#replaybtn';
            let play_button = document.querySelector(css_expr);
            if (play_button != null && play_button.offsetParent !== null) {
                play_button.click();
            }""")

    def _init_plan_id(self):
        self.plan_id = self._get_plan_id()
        if not self.plan_id:
            raise ValueError("未找到计划ID")

    def _init_phase_id(self):
        self.phase_id = self._get_phase_id()
        if not self.phase_id:
            raise ValueError("未找到项目ID")

    def _get_plan_id(self):
        elem = self.get_elem_with_wait_by_xpath(20, "//input[@id='studyPlanId']", False)
        return elem.get_attribute("value") if elem else ""

    def _get_phase_id(self):
        elem = self.get_elem_with_wait_by_xpath(20, "//input[@id='initProjectPhaseId']", False)
        return elem.get_attribute("value") if elem else ""

    def _init_user_id(self):
        max_retry_count = 20
        retry_count = 0
        while "intoStudentStudy" not in self.web_browser.current_url:
            time.sleep(1)
            retry_count += 1
            if retry_count >= max_retry_count:
                break

        # 在学习的页面
        params_seg = self.web_browser.current_url.split("?")[1]
        for val in params_seg.split("&"):
            if "userId" in val:
                self.user_id = val.split("=")[1]
                break
        if not self.user_id:
            raise Exception("获取用户ID失败")

    def _init_project_id(self):
        max_retry_count = 20
        retry_count = 0
        while "intoStudentStudy" not in self.web_browser.current_url:
            time.sleep(1)
            retry_count += 1
            if retry_count >= max_retry_count:
                break

        # 在学习的页面
        params_seg = self.web_browser.current_url.split("?")[1]
        for val in params_seg.split("&"):
            if "projectId" in val:
                self.project_id = val.split("=")[1]
                break
        if not self.project_id:
            raise Exception("获取项目ID失败")

    def _enter_pub_project(self):
        # 进入公需课
        enter_study_btn = self.get_elem_with_wait_by_xpath(10,
                                                           "//a[@class='btn-start' and contains(@onclick, '14071')]")
        if enter_study_btn:
            enter_study_btn.click()
        else:
            self.logger.error(f"用户【{self.username_showed}】获取“进入学习”按钮失败，页面加载失败或者有变动")

    def _enter_pro_project(self):
        # 进入专业课
        enter_study_btn = self.get_elem_with_wait_by_xpath(10,
                                                           "//a[@class='btn-start' and not(contains(@onclick, '14071'))]")
        if enter_study_btn:
            enter_study_btn.click()
        else:
            self.logger.error(f"用户【{self.username_showed}】获取“进入学习”按钮失败，页面加载失败或者有变动")

    def _handle_complete_info_tips(self):
        alert_complete_info = self.wait_for_visible_by_xpath(3,
                                                             "//div[@class='layui-layer layui-layer-page'][./*[contains(text(),'补充个人信息')]]")
        if alert_complete_info:
            user_info = self._get_user_info()
            if not user_info[5].strip():
                # 工作单位为空
                self.web_browser.execute_script(
                    "document.querySelector('input[name=\"workUnit\"]').value='%s'" % user_info[4].split(",")[-1])
            btn_confirm = self.get_elem_by_xpath(
                "//div[@class='layui-layer layui-layer-page']//input[@class='layui-btn layui-btn-normal' and @value='保存']")
            if not btn_confirm.is_displayed():
                btn_confirm.location_once_scrolled_into_view
                time.sleep(1)
            btn_confirm.click()

    def _get_user_info(self) -> tuple:
        """
        获取个人详细信息
        :return: tuple (姓名,学科,手机,身份证,区域,工作单位)
        """
        ret = None
        url = f"https://{self.project_code}.stu.t-px.cn/auth/complementUserInfo"
        # id=2974&projectPhaseId=642
        headers = {"Cookie": self.cookie_to_str(), "User-Agent": self.user_agent(),
                   "Referer": f"https://{self.project_code}.stu.t-px.cn/studyPlan/intoStudentStudy",
                   }
        try:
            resp = requests.get(url, headers=headers)
        except:
            self.logger.error("用户【%s】获取考核结果异常" % self.username_showed)
            raise
        else:
            resp_json = json.loads(resp.text)
            user_info = resp_json["data"]["userInfo"]

        return user_info["name"], user_info["sectionName"] + user_info["subjectName"], user_info["mobile"], user_info[
            'idnumber'], user_info["path"], user_info["workUnit"]

    def _is_passed(self):
        if "hxwysqy2025" in self.project_code:
            scores = self._get_score(self.project_id, self.user_id)
        else:
            scores = self._get_score2(self.plan_id, self.phase_id)
        return scores[1] >= scores[0]

    def _get_score(self, project_id, user_id) -> tuple:
        """
        获取考核成绩
        :param project_id:
        :param user_id:
        :return: tuple (总分,得分)
        """
        ret = None
        url = "https://%s.stu.t-px.cn/scoreStudent/findProjectPhaseScoreAndDetail" % self.project_code
        # url = "https://%s.stu.t-px.cn/scoreStudent/findProjectPhaseScore" % self.project_code
        # id=2974&projectPhaseId=642
        # params = {"id": user_id, "projectPhaseId": user_id}
        headers = {"Cookie": self.cookie_to_str() + f";student_userId_cookie={user_id};projectId={project_id}",
                   "User-Agent": self.user_agent(),
                   "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                   "Referer": "https://%s.stu.t-px.cn/scoreStudent/intoScoreStudent" % self.project_code,
                   "Origin": "https://%s.stu.t-px.cn" % self.project_code
                   }
        try:
            # resp = requests.post(url, data=params, headers=headers)
            resp = requests.post(url, headers=headers)
        except:
            self.logger.error("用户【%s】获取考核结果异常" % self.username_showed)
            raise
        else:
            resp_json = json.loads(resp.text)
            # ret = resp_json["data"]["projectPhaseScoreList"][0]["qualifiedPoint"], \
            #     resp_json["data"]["projectPhaseScoreList"][0]["onLineScore"]
            ret = resp_json["data"]["scoreDetailInfoList"][0]["scoreDetailDTO"]["contentTypeCourse"]["courseMaxScore"], \
                resp_json["data"]["scoreDetailInfoList"][0]["scoreDetailDTO"]["contentTypeCourse"]["courseScore"]

        return ret

    def _get_score2(self, study_plan_id, project_phase_id) -> tuple:
        """
        获取考核成绩
        :param study_plan_id:
        :param project_phase_id:
        :return: tuple (总分,得分)
        """
        ret = None
        url = "https://%s.stu.t-px.cn/scoreStudent/findScoreStudentListByStudyPlanIdAndProjectPhaseId" % self.project_code
        # id=2974&projectPhaseId=642
        params = {"id": study_plan_id, "projectPhaseId": project_phase_id}
        headers = {"Cookie": self.cookie_to_str(), "User-Agent": self.user_agent(),
                   "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                   "Referer": "https://%s.stu.t-px.cn/scoreStudent/intoScoreStudent" % self.project_code,
                   "Origin": "https://%s.stu.t-px.cn" % self.project_code
                   }
        try:
            resp = requests.post(url, data=params, headers=headers)
            # resp = requests.post(url, headers=headers)
        except:
            self.logger.error("用户【%s】获取考核结果异常" % self.username_showed)
            raise
        else:
            resp_json = json.loads(resp.text)
            ret = resp_json["data"]["scoreDetailDTO"]["contentTypeCourse"]["courseMaxScore"], \
                resp_json["data"]["scoreDetailDTO"]["contentTypeCourse"]["courseScore"]
        return ret

    def _handle_course_page_tips(self):
        # 处理课程页面的提示信息，偶尔该页面会有通知，或者弹出学员手册
        alert_tips = self.wait_for_visible_by_xpath(2, "//div[@id='pop_tips']")
        if alert_tips:
            btn_confirm = self.get_elem_by_xpath("//a[@class='pop_btn']")
            if not btn_confirm.is_displayed():
                btn_confirm.location_once_scrolled_into_view
                time.sleep(1)
            btn_confirm.click()

    def _handle_choose_course(self):
        for chapter_name in self.chapter_name_list:
            # 获取未选课的章节
            first_unchoose_chapter = self.get_elem_with_wait_by_xpath(5,
                                                                      f"(//li[.//h2[text()='{chapter_name}']]//a[text()='去选课'])[1]",
                                                                      False)
            if first_unchoose_chapter:
                # 处理选课
                self._enter_choose_course(chapter_name, first_unchoose_chapter)

    def _enter_choose_course(self, chapter_name, first_unchoose_chapter):

        if not first_unchoose_chapter.is_displayed():
            chapter_title_elem = self.get_elem_with_wait_by_xpath(10, f"//li[.//h2[text()='{chapter_name}']]")
            chapter_title_elem.click()

        # 等待元素可见
        self.wait_for_visible(10, first_unchoose_chapter)
        if not first_unchoose_chapter.is_displayed():
            raise BusinessException(f"选课模块{chapter_name}不可见，点击不了！")
        # 点击元素
        time.sleep(2)
        unchoose_module = self.get_relative_elem_by_xpath(first_unchoose_chapter, "./preceding-sibling::a")
        unchoose_module_name = unchoose_module.text
        self.logger.info(f"用户【{self.username_showed}】{chapter_name}-{unchoose_module_name}，开始选课...")

        first_unchoose_chapter.click()
        max_count = 20
        cycle_count = 0
        while cycle_count < max_count:
            cycle_count += 1
            time.sleep(0.4)
            if "intoSelectCourseList" in self.web_browser.current_url:
                break
        if cycle_count == max_count:
            raise BusinessException("进入选课页面失败")

        time.sleep(2)
        # 获取选课规则
        course_course_rule = self.get_elems_with_wait_by_xpath(10, "//div[@id='selectRule']//span[@class='c_orange']")
        if not course_course_rule:
            raise BusinessException("获取选课规则失败")
        total_course_count = int(course_course_rule[1].text)
        min_course_count = int(course_course_rule[0].text)
        need_choose_course_count = min_course_count
        if min_course_count <= total_course_count - 1:
            need_choose_course_count = min_course_count + 1

        courses = self.get_elems_with_wait_by_xpath(10, "//td[@class='fristchild']")
        need_choose_course_count = len(courses) if need_choose_course_count > len(courses) else need_choose_course_count

        for i in range(need_choose_course_count):
            course_check_box = self.get_elem_with_wait_by_xpath(10, f"(//input[@name='ids'])[{i + 1}]")
            if not course_check_box:
                pass
                # raise BusinessException("获取选课选择框失败")
            else:
                if not course_check_box.is_displayed():
                    course_check_box.location_once_scrolled_into_view
                    time.sleep(0.5)
                course_check_box.click()

            time.sleep(1.5)

        # 确认选课按钮
        confirm_choose_btn = self.get_elem_with_wait_by_xpath(10, "//button[@id='submitCourse']")
        if not confirm_choose_btn:
            raise BusinessException("获取选课确认按钮失败")

        if not confirm_choose_btn.is_displayed():
            confirm_choose_btn.location_once_scrolled_into_view
            time.sleep(0.5)
        confirm_choose_btn.click()

        max_count = 20
        cycle_count = 0
        while cycle_count < max_count:
            cycle_count += 1
            time.sleep(0.4)
            if "intoStudentStudy" in self.web_browser.current_url:
                break
        if cycle_count == max_count:
            raise BusinessException("进入课程页面失败")
        else:
            self.logger.info(f"用户【{self.username_showed}】{chapter_name}-{unchoose_module_name}，选课成功！")
            first_unchoose_chapter = self.get_elem_with_wait_by_xpath(10,
                                                                      f"(//li[.//h2[text()='{chapter_name}']]//a[text()='去选课'])[1]",
                                                                      visible=False)
            if first_unchoose_chapter:
                self._enter_choose_course(chapter_name, first_unchoose_chapter)
            else:
                return

    def _handle_content_pause_tips(self):
        confirm_btn = self.get_elem_by_xpath(
            "//div[contains(@class,'layui-layer layui-layer-dialog')][.//*[contains(text(),'视频暂停')]]//a[text()='Ok，我知道了！']")

        if confirm_btn and confirm_btn.is_enabled() and confirm_btn.is_displayed():
            try:
                confirm_btn.click()
            except:
                pass
            else:
                # 等待确认按钮消失
                self.wait_for_disappeared(2, confirm_btn)
                # 等待蒙版消失
                self._wait_for_shade_disappear()

    def _handle_content_finished_tips(self):
        ret = False
        xpath = "//div[contains(@class,'layui-layer layui-layer-dialog')][.//*[contains(text(),'视频已播放完成')]]//a[text()='Ok，我知道了！']"
        if "hxwysqy2025" in self.project_code:
            xpath = "//div[contains(@class,'layui-layer layui-layer-dialog')]//a[text()='Ok，我知道了！']"

        confirm_btn = self.get_elem_by_xpath(xpath)
        if confirm_btn and confirm_btn.is_enabled() and confirm_btn.is_displayed():
            confirm_btn.click()
            # 等待对话框消失
            self.wait_for_disappeared(2, confirm_btn)
            # 等待蒙版消失
            self._wait_for_shade_disappear()
            ret = True
        return ret
