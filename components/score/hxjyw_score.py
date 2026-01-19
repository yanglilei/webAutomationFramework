import time
from dataclasses import dataclass
from typing import Dict, Any

import bs4
import requests
from selenium.webdriver.common.by import By

from src.frame.base.base_task_node import BasePYNode


@dataclass(init=False)
class HXJYWScore(BasePYNode):
    # 课程类型，格式：公需课|1  专业课|2
    course_type: str = ""
    # 项目编码
    project_code: str = ""

    def set_up(self):
        self.course_type = self.node_config.get("node_params", {}).get("course_type")
        self.project_code = self.node_config.get("node_params", {}).get("project_code")

    def execute(self, context: Dict) -> bool:
        self.update_exam_score()
        return True

    def update_exam_score(self):
        score = self.get_user_score()
        self.logger.info("用户【%s】考试得分：%s" % (self.username_showed, score))
        self.user_manager.update_record_by_username(self.username, {6: score})

    def get_user_score(self):
        self.web_browser.switch_to.window(self.web_browser.window_handles[-1])
        score_info = []
        if "hj" in self.project_code:
            if "office/home" not in self.web_browser.current_url:
                # 跳转到选择项目页面
                self.web_browser.get("https://hxwyxpt.t-px.cn/office/home")
                time.sleep(2)

            if not "intoStudentStudy" in self.web_browser.current_url:
                # 查2次分数
                # 1.查公需课
                self._enter_pub_project()
                time.sleep(3)
                self.wait_for_disappeared(20, (By.XPATH, "//div[@class='layui-layer-shade']"))
                learn_tab = self.get_elem_with_wait(10, (By.XPATH, "//a[text()='学习计划']"))
                learn_tab.click()

                self._init_user_id()
                self._init_project_id()
                score_info.append("公需课：")
                score_info.extend(self._get_score_info())

                # self.web_browser.back()
                if "office/home" not in self.web_browser.current_url:
                    # 跳转到选择项目页面
                    self.web_browser.get("https://hxwyxpt.t-px.cn/office/home")
                    time.sleep(2)

                # 2.查专业课
                self._enter_pro_project()
                time.sleep(3)
                self.wait_for_disappeared(20, (By.XPATH, "//div[@class='layui-layer-shade']"))
                learn_tab = self.get_elem_with_wait(10, (By.XPATH, "//a[text()='学习计划']"))
                learn_tab.click()

                self._init_user_id()
                self._init_project_id()
                # self._get_score_info(self.project_id, self.user_id)
                score_info.append("专业课：")
                score_info.extend(self._get_score_info())
            else:
                time.sleep(3)
                # 直接查分
                self.wait_for_disappeared(20, (By.XPATH, "//div[@class='layui-layer-shade']"))
                learn_tab = self.get_elem_with_wait(10, (By.XPATH, "//a[text()='学习计划']"))
                learn_tab.click()
                self._init_user_id()
                self._init_project_id()
                score_info = self._get_score_info()
        elif "pt" in self.project_code or "xy" in self.project_code:
            # if "office/home" not in self.web_browser.current_url:
            #     # 跳转到选择项目页面
            #     self.web_browser.get("https://hxwyxpt.t-px.cn/office/home")
            #     time.sleep(2)
            # enter_study_btn = self.get_elem_with_wait(10, (By.XPATH, "//a[@class='btn-start']"))
            # enter_study_btn.click()
            if not "intoStudentStudy" in self.web_browser.current_url:
                if self.course_type.split("|")[-1] == 1:
                    # 进入公需课
                    self._enter_pub_project()
                else:
                    # 进入专业课
                    self._enter_pro_project()
                time.sleep(3)
            # 直接查分
            # self.wait_for_disappeared(20, (By.XPATH, "//div[@class='layui-layer-shade']"))
            # learn_tab = self.get_elem_with_wait(10, (By.XPATH, "//a[text()='学习计划']"))
            # learn_tab.click()
            # self._init_user_id()
            # self._init_project_id()
            self.wait_for_disappeared(20, (By.XPATH, "//div[@class='layui-layer-shade']"))
            my_score_tab = self.get_elem_with_wait(10, (By.XPATH, "//a[text()='我的考核']"))
            # my_score_tab.click()
            self.execute_js('arguments[0].click()', my_score_tab)
            self.wait_for_disappeared(20, (By.XPATH, "//div[@class='layui-layer-shade']"))
            score_info = self._get_score_info()
        return "".join(score_info)

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

    def _get_score_info(self):
        # 请求获取分数
        # return self._get_phase_score_v2()
        return self._get_phase_score_v3()

    def _get_phase_score_v3(self):

        phase_name_elem = self.get_elem_with_wait(10, (By.XPATH, '//div[@class="title"]'))
        if phase_name_elem:
            phase_name = phase_name_elem.text
        else:
            phase_name = "获取失败"

        total_score_elem = self.get_elem_with_wait(10, (By.XPATH, '//span[contains(@class,"totalpoint")]'))
        if total_score_elem:
            total_score = total_score_elem.text[3:]
        else:
            total_score = "获取失败"

        btn_score_detail = self.get_elem_with_wait(10, (By.XPATH, '//a[text()="查看详细成绩>>"]'))
        if btn_score_detail:
            btn_score_detail.click()
            course_score_elem = self.get_elem_with_wait(20, (By.XPATH, '//span[@class="courseScore"]'))
            course_score = course_score_elem.text if course_score_elem else "获取失败"

            project_activity_score_elem = self.get_elem_with_wait(20, (By.XPATH, '//span[@class="activitytatolscore"]'))
            if project_activity_score_elem:
                if "0" == project_activity_score_elem.text:
                    project_activity_score = self._get_project_score()
                else:
                    project_activity_score = project_activity_score_elem.text + "分"
            else:
                project_activity_score = "获取失败"
            self_activity_score_elem = self.get_elem_with_wait(20,
                                                               (By.XPATH, '//span[@class="autoactivitytatolscore"]'))
            self_activity_score = self_activity_score_elem.text + "分" if self_activity_score_elem else "获取失败"
        else:
            course_score = "获取失败"
            project_activity_score = "获取失败"
            self_activity_score = "获取失败"

        return f"{phase_name}总得分：{total_score}，课程分：{course_score}，项目级研修活动：{project_activity_score}，自主研修活动：{self_activity_score}"
        # return [course_score, project_activity_score, self_activity_score]

    def _get_project_score(self):
        status = "获取研修状态失败！"
        project_activity_score_elem = self.get_elem_with_wait(20, (By.XPATH, '//a[@title="教学设计"]'))
        headers = {"Cookie": self.cookie_to_str(),
                   "User-Agent": self.user_agent(),
                   "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                   "Referer": "https://%s.stu.t-px.cn/scoreStudent/intoScoreStudent" % self.project_code,
                   "Origin": "https://%s.stu.t-px.cn" % self.project_code
                   }
        try:
            resp = requests.request("GET", project_activity_score_elem.get_attribute("href"), headers=headers)
        except:
            self.logger.error("用户【%s】获取项目成绩异常" % self.username_showed)
        else:
            bs = bs4.BeautifulSoup(resp.text, "lxml")
            status = bs.select('div.current-state > em')[0].text.strip()
        return status
