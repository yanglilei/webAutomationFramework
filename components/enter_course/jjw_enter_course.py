import asyncio
import re
from dataclasses import field, dataclass
from typing import Tuple

from playwright.async_api import Locator
from tenacity import stop_after_attempt, wait_fixed, retry_if_exception_type, retry

from src.frame.base import BaseEnterCourseTaskNode


@dataclass(init=False)
class JJWEnterCourse(BaseEnterCourseTaskNode):
    """
    继教网进入课程
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

    def set_up(self):
        self.excluded_courses = []
        self.chapter_name_list = []

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        # 进入圈子
        if "intoStudentStudy" not in await self.get_current_url():
            try:
                if not await self._enter_project():
                    return False, "没有【进入xx圈学习】按钮"
            except:
                self.logger.exception("进入圈子异常")
                return False, "进入圈子异常"

        # 等待跳转
        await asyncio.sleep(3)
        # 处理完善个人信息的弹窗
        await self._handle_complete_info_tips()
        await self.wait_for_disappeared_by_xpath(20, "//div[@class='layui-layer-shade']")
        await self._enter_study_plan()

        await self._init_plan_id()
        await self._init_phase_id()

        await self._init_user_id()
        await self._init_project_id()
        self.main_window_url = await self.get_current_url()
        # 从url中获取项目编号
        # https://cn202643005.stu.teacher.com.cn/studyPlan/intoStudentStudy?projectId=3967&userId=8564277&hexstamp=d4be256520eda327786c
        self.project_code = re.findall("//(\w+)\.", self.main_window_url)[0].strip()
        if not self.project_code:
            return False, "项目编号未配置"

        if await self._is_passed():
            # 学习通过了，无需学习
            self.logger.info(f"学习成绩已经合格了，准备退出")
            # self.do_after_finished_all_courses()
            return False, f"{self.course_type.split('|')[0]}已学完"
        else:
            # 处理完善个人信息的弹窗
            # await self._handle_complete_info_tips()
            # 处理课程页面的建议信息
            # await self._handle_course_page_tips()
            # 处理选课
            # self._handle_choose_course()
            # 判断课程类型
            # self._init_course_type()
            return True, ""

    async def _is_passed(self):
        # 解决有时候获取分数异常，重新获取一次
        scores = await self._get_score(self.project_id, self.user_id)
        # if "hxwysqy2025" in self.project_code:
        #     scores = await self._get_score(self.project_id, self.user_id)
        # else:
        #     scores = await self._get_score2(self.plan_id, self.phase_id)
        return scores[1] >= scores[0]

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _get_score(self, project_id, user_id) -> tuple:
        """
        获取考核成绩
        :param project_id:
        :param user_id:
        :return: tuple (总分,得分)
        """
        ret = None
        url = f"https://{self.project_code}.stu.teacher.com.cn/scoreStudent/findProjectPhaseScoreAndDetail"
        # url = "https://%s.stu.t-px.cn/scoreStudent/findProjectPhaseScore" % self.project_code
        # id=2974&projectPhaseId=642
        # params = {"id": user_id, "projectPhaseId": user_id}
        headers = {"Cookie": await self.cookie_to_str() + f";student_userId_cookie={user_id};projectId={project_id}",
                   "User-Agent": await self.user_agent(),
                   "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                   "Referer": f"https://{self.project_code}.stu.t-px.cn/scoreStudent/intoScoreStudent",
                   "Origin": f"https://{self.project_code}.stu.t-px.cn"
                   }
        try:
            # resp = requests.post(url, data=params, headers=headers)
            # resp = requests.post(url, headers=headers)
            resp = await self.context.request.post(url, headers=headers)
        except:
            self.logger.error("用户【%s】获取考核结果异常" % self.username_showed)
            raise
        else:
            resp_json = await resp.json()
            # ret = resp_json["data"]["projectPhaseScoreList"][0]["qualifiedPoint"], \
            #     resp_json["data"]["projectPhaseScoreList"][0]["onLineScore"]
            ret = resp_json["data"]["scoreDetailInfoList"][0]["scoreDetailDTO"]["contentTypeCourse"]["courseMaxScore"], \
                resp_json["data"]["scoreDetailInfoList"][0]["scoreDetailDTO"]["contentTypeCourse"]["courseScore"]
        return ret

    async def _handle_complete_info_tips(self):
        await self.wait_for_visible_by_xpath(5,
                                             "//div[@class='layui-layer layui-layer-page'][./*[contains(text(),'补充个人信息')]]")
        confirm_btn = await self.get_elem_by_xpath(
            "//div[@class='layui-layer layui-layer-page']//input[@class='layui-btn layui-btn-normal' and @value='保存']")
        if confirm_btn:
            if not await confirm_btn.is_visible():
                await confirm_btn.scroll_into_view_if_needed()
                await asyncio.sleep(1)
            await confirm_btn.click()

    async def _enter_project(self) -> bool:
        btn_enter_project = await self.get_elem_with_wait_by_xpath(10, "//div[@class='button-item button-item-hover']")
        if not btn_enter_project:
            self.logger.error("没有【进入xx圈学习】按钮")
            return False
        else:
            await btn_enter_project.click()
            return True

    async def _enter_study_plan(self):
        learn_tab = await self.get_elem_with_wait_by_xpath(10, "//a[text()='学习计划']")
        await learn_tab.click()

    async def _enter_score(self):
        score_tab = await self.get_elem_with_wait_by_xpath(10, "//a[text()='我的考核']")
        await score_tab.click()

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
        while "intoStudentStudy" not in await self.get_current_url():
            await asyncio.sleep(1)
            # time.sleep(1)
            retry_count += 1
            if retry_count >= max_retry_count:
                break

        # 在学习的页面
        params_seg = (await self.get_current_url()).split("?")[1]
        for val in params_seg.split("&"):
            if "userId" in val:
                self.user_id = val.split("=")[1]
                break
        if not self.user_id:
            raise Exception("获取用户ID失败")

    async def _init_project_id(self):
        max_retry_count = 20
        retry_count = 0
        while "intoStudentStudy" not in await self.get_current_url():
            await asyncio.sleep(1)
            # time.sleep(1)
            retry_count += 1
            if retry_count >= max_retry_count:
                break

        # 在学习的页面
        params_seg = (await self.get_current_url()).split("?")[1]
        for val in params_seg.split("&"):
            if "projectId" in val:
                self.project_id = val.split("=")[1]
                break
        if not self.project_id:
            raise Exception("获取项目ID失败")

    async def enter_course(self) -> Tuple[bool, str]:
        # 获得第一个未读的课程
        course = await self._get_pub_first_course()
        if not course:
            self.logger.info("用户【%s】没有未学习的课程，准备退出" % self.username_showed)
            return False, f"{self.course_type.split('|')[0]}已学完"
        # 展开章节，让课程元素可见
        if not await course.is_visible():
            try:
                await course.scroll_into_view_if_needed(timeout=3000)
            except:
                pass
        # 展开课程
        if not await course.is_visible():
            menu_elem = await self.get_relative_elem_by_xpath(course,
                                                              "./ancestor::div[@class='module_wrap']/preceding-sibling::div/span[contains(@class, 'step')]")
            if menu_elem:
                # 点击展开
                await menu_elem.click()
                # 等待3秒
                await asyncio.sleep(3)
                # time.sleep(3)

        elem = await self.get_relative_elem_by_xpath(course, "./preceding-sibling::a")
        course_name = await elem.text_content()
        # 点击进入课程之前还需要进一步检测是否有弹窗等信息
        # 处理完善个人信息的弹窗
        await self._handle_complete_info_tips()
        # 处理课程页面的建议信息
        await self._handle_course_page_tips()
        # 点击进入学习页面
        try:
            await self.js_click(course)
        except:
            self.logger.exception(f"用户【{self.username_showed}】点击进入课程【{course_name}】失败")
            return False, "点击进入课程失败"
        else:
            await asyncio.sleep(2)
            await self.switch_to_latest_window()
            # 等待打开新窗口
            max_retry_count = 20
            while "intoSelectCourseVideo" not in await self.get_current_url() and max_retry_count > 0:
                await asyncio.sleep(1)
                max_retry_count -= 1
                await self.switch_to_latest_window()
        return True, course_name

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        # 排除掉这个课程
        self.excluded_courses.append(self.course_name)
        if btn_go_back := await self.get_elem_by_css("div.goback_href"):
            # 点击返回
            await self.js_click(btn_go_back)
            # 等待页面加载完成
            await asyncio.sleep(2)
            # time.sleep(2)
        else:
            # self.close_window(self.web_browser.window_handles[-1])
            # self.web_browser.switch_to.window(self.main_window_url)
            # self.web_browser.refresh()
            await self.close_latest_window()
            await self.switch_to_window_by_url_key(self.main_window_url)
            await self.refresh()
        return True, ""

    async def _get_pub_first_course(self) -> Locator:
        ret = None
        xpath = "//a[(./preceding-sibling::i/text() = '学习中' or ./preceding-sibling::i/text() = '未学习') and @class='layui-btn layui-btn-primary' and @data-type='课程' ]"

        courses = await self.get_elems_with_wait_by_xpath(10, xpath, False)
        if courses:
            for course in courses:
                if await course.text_content() not in self.excluded_courses:
                    ret = course
                    break
        return ret

    async def _handle_course_page_tips(self):
        # 处理课程页面的提示信息，偶尔该页面会有通知，或者弹出学员手册
        alert_tips = await self.wait_for_visible_by_xpath(2, "//div[@id='pop_tips']")
        if alert_tips:
            btn_confirm = await self.get_elem_by_xpath("//a[@class='pop_btn']")
            if not await btn_confirm.is_visible():
                await btn_confirm.scroll_into_view_if_needed()
                await asyncio.sleep(1)
            await btn_confirm.click()
