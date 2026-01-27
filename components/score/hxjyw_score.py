import asyncio
import time
from dataclasses import dataclass
from typing import Dict

import bs4
import httpx

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

    async def execute(self, context: Dict) -> bool:
        await self.update_exam_score()
        return True

    async def update_exam_score(self):
        score = await self.get_user_score()
        self.logger.info("考试得分：%s" % score)
        if self.user_mode == 1:
            self.user_manager.update_record_by_username(self.username, {6: score})

    async def get_user_score(self):
        await self.switch_to_latest_window()
        score_info = []
        if "hj" in self.project_code:
            if "office/home" not in await self.get_current_url():
                # 跳转到选择项目页面
                await self.load_url("https://hxwyxpt.t-px.cn/office/home")
                time.sleep(2)

            if "intoStudentStudy" not in await self.get_current_url():
                # 查2次分数intoStudentStudy
                # 1.查公需课
                await self._enter_pub_project()
                await asyncio.sleep(3)
                await self.wait_for_disappeared_by_xpath(20, "//div[@class='layui-layer-shade']")
                learn_tab = await self.get_elem_with_wait_by_xpath(10, "//a[text()='学习计划']")
                await learn_tab.click()

                await self._init_user_id()
                await self._init_project_id()
                score_info.append("公需课：")
                score_info.extend(await self._get_score_info())

                # self.web_browser.back()
                if "office/home" not in await self.get_current_url():
                    # 跳转到选择项目页面
                    await self.load_url("https://hxwyxpt.t-px.cn/office/home")
                    time.sleep(2)

                # 2.查专业课
                await self._enter_pro_project()
                time.sleep(3)
                await self.wait_for_disappeared_by_xpath(20, "//div[@class='layui-layer-shade']")
                learn_tab = await self.get_elem_with_wait_by_xpath(10, "//a[text()='学习计划']")
                await learn_tab.click()

                await self._init_user_id()
                await self._init_project_id()
                # self._get_score_info(self.project_id, self.user_id)
                score_info.append("专业课：")
                score_info.extend(await self._get_score_info())
            else:
                time.sleep(3)
                # 直接查分
                await self.wait_for_disappeared_by_xpath(20, "//div[@class='layui-layer-shade']")
                learn_tab = await self.get_elem_with_wait_by_xpath(10, "//a[text()='学习计划']")
                await learn_tab.click()
                await self._init_user_id()
                await self._init_project_id()
                score_info = self._get_score_info()
        elif "pt" in self.project_code or "xy" in self.project_code:
            # if "office/home" not in self.web_browser.current_url:
            #     # 跳转到选择项目页面
            #     self.web_browser.get("https://hxwyxpt.t-px.cn/office/home")
            #     time.sleep(2)
            # enter_study_btn = self.get_elem_with_wait(10, (By.XPATH, "//a[@class='btn-start']"))
            # enter_study_btn.click()
            if not "intoStudentStudy" in await self.get_current_url():
                if self.course_type.split("|")[-1] == 1:
                    # 进入公需课
                    await self._enter_pub_project()
                else:
                    # 进入专业课
                    await self._enter_pro_project()
                time.sleep(3)
            # 直接查分
            # self.wait_for_disappeared(20, (By.XPATH, "//div[@class='layui-layer-shade']"))
            # learn_tab = self.get_elem_with_wait(10, (By.XPATH, "//a[text()='学习计划']"))
            # learn_tab.click()
            # self._init_user_id()
            # self._init_project_id()
            await self.wait_for_disappeared_by_xpath(20, "//div[@class='layui-layer-shade']")
            my_score_tab = await self.get_elem_with_wait_by_xpath(10,  "//a[text()='我的考核']")
            # my_score_tab.click()
            await self.js_click(my_score_tab)
            await self.wait_for_disappeared_by_xpath(20, "//div[@class='layui-layer-shade']")
            score_info = await self._get_score_info()
        return "".join(score_info)

    async def _init_plan_id(self):
        self.plan_id = await self._get_plan_id()
        if not self.plan_id:
            raise ValueError("未找到计划ID")

    async def _init_phase_id(self):
        self.phase_id = await self._get_phase_id()
        if not self.phase_id:
            raise ValueError("未找到项目ID")

    async def _get_plan_id(self):
        elem = await self.get_elem_with_wait_by_xpath(20, "//input[@id='studyPlanId']", False)
        return await elem.get_attribute("value") if elem else ""

    async def _get_phase_id(self):
        elem = await self.get_elem_with_wait_by_xpath(20, "//input[@id='initProjectPhaseId']", False)
        return await elem.get_attribute("value") if elem else ""

    async def _init_user_id(self):
        max_retry_count = 20
        retry_count = 0
        url = await self.get_current_url()
        while "intoStudentStudy" not in url:
            time.sleep(1)
            retry_count += 1
            if retry_count >= max_retry_count:
                break

        # 在学习的页面
        params_seg = url.split("?")[1]
        for val in params_seg.split("&"):
            if "userId" in val:
                self.user_id = val.split("=")[1]
                break
        if not self.user_id:
            raise Exception("获取用户ID失败")

    async def _init_project_id(self):
        max_retry_count = 20
        retry_count = 0
        current_url = await self.get_current_url()
        while "intoStudentStudy" not in current_url:
            time.sleep(1)
            retry_count += 1
            if retry_count >= max_retry_count:
                break

        # 在学习的页面
        params_seg = current_url.split("?")[1]
        for val in params_seg.split("&"):
            if "projectId" in val:
                self.project_id = val.split("=")[1]
                break
        if not self.project_id:
            raise Exception("获取项目ID失败")

    async def _enter_pub_project(self):
        # 进入公需课
        enter_study_btn = await self.get_elem_with_wait_by_xpath(10,
                                                           "//a[@class='btn-start' and contains(@onclick, '14071')]")
        if enter_study_btn:
            await enter_study_btn.click()
        else:
            self.logger.error(f"用户【{self.username_showed}】获取“进入学习”按钮失败，页面加载失败或者有变动")

    async def _enter_pro_project(self):
        # 进入专业课
        enter_study_btn = await self.get_elem_with_wait_by_xpath(10,
                                                           "//a[@class='btn-start' and not(contains(@onclick, '14071'))]")
        if enter_study_btn:
            await enter_study_btn.click()
        else:
            self.logger.error(f"用户【{self.username_showed}】获取“进入学习”按钮失败，页面加载失败或者有变动")

    async def _get_score_info(self):
        # 请求获取分数
        # return self._get_phase_score_v2()
        return await self._get_phase_score_v3()

    async def _get_phase_score_v3(self):

        phase_name_elem = await self.get_elem_with_wait_by_xpath(10, '//div[@class="title"]')
        if phase_name_elem:
            phase_name = await phase_name_elem.text_content()
        else:
            phase_name = "获取失败"

        total_score_elem = await self.get_elem_with_wait_by_xpath(10, '//span[contains(@class,"totalpoint")]')
        if total_score_elem:
            total_score = await total_score_elem.text_content()[3:]
        else:
            total_score = "获取失败"

        btn_score_detail = await self.get_elem_with_wait_by_xpath(10, '//a[text()="查看详细成绩>>"]')
        if btn_score_detail:
            await btn_score_detail.click()
            course_score_elem = await self.get_elem_with_wait_by_xpath(20, '//span[@class="courseScore"]')
            course_score = await course_score_elem.text_content() if course_score_elem else "获取失败"

            project_activity_score_elem = await self.get_elem_with_wait_by_xpath(20, '//span[@class="activitytatolscore"]')
            if project_activity_score_elem:
                if "0" == await project_activity_score_elem.text_content():
                    project_activity_score = await self._get_project_score()
                else:
                    project_activity_score = await project_activity_score_elem.text_content() + "分"
            else:
                project_activity_score = "获取失败"
            self_activity_score_elem = await self.get_elem_with_wait_by_xpath(20, '//span[@class="autoactivitytatolscore"]')
            self_activity_score = await self_activity_score_elem.text_content() + "分" if self_activity_score_elem else "获取失败"
        else:
            course_score = "获取失败"
            project_activity_score = "获取失败"
            self_activity_score = "获取失败"

        return f"{phase_name}总得分：{total_score}，课程分：{course_score}，项目级研修活动：{project_activity_score}，自主研修活动：{self_activity_score}"
        # return [course_score, project_activity_score, self_activity_score]

    async def _get_project_score(self):
        status = "获取研修状态失败！"
        project_activity_score_elem = await self.get_elem_with_wait_by_xpath(20, '//a[@title="教学设计"]')
        headers = {"Cookie": self.cookie_to_str(),
                   "User-Agent": self.user_agent(),
                   "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                   "Referer": "https://%s.stu.t-px.cn/scoreStudent/intoScoreStudent" % self.project_code,
                   "Origin": "https://%s.stu.t-px.cn" % self.project_code
                   }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(await project_activity_score_elem.get_attribute("href"), headers=headers)
                # resp = await session.get("GET", project_activity_score_elem.get_attribute("href"), headers=headers)
        except:
            self.logger.error("用户【%s】获取项目成绩异常" % self.username_showed)
        else:
            bs = bs4.BeautifulSoup(resp.text, "lxml")
            status = bs.select('div.current-state > em')[0].text.strip()
        return status
