import asyncio
import json
from dataclasses import dataclass, field
from typing import Tuple, Dict, Any, Optional

import httpx
from playwright.async_api import Locator
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.frame.base.base_task_node import BasePYNode
from src.frame.common.exceptions import BusinessException
from src.frame.common.question_bank import FixedQuestionBankHandler


class JJWExamHandler:
    def __init__(self, username, web_operator, question_bank: FixedQuestionBankHandler, user_manager, logger):
        self.username = username
        self.question_bank = question_bank
        self.web_operator = web_operator
        self.logger = logger
        self.user_manager = user_manager

    async def do_exam(self):
        while True:
            # 获取题号
            el_question_no = await self.web_operator.get_elem_with_wait_by_css(10, "div.questnum2 span")
            if not el_question_no:
                self.logger.error("获取题号失败，考试失败！")
                break
            # 获取答案
            question_no = (await el_question_no.text_content()).strip()
            answers = self.question_bank.get_answer(question_no)
            self.logger.info(f"第{question_no}题，选：{answers}")
            # 填写答案
            for answer in answers:
                item = await self.web_operator.get_elem_with_wait_by_xpath(10, f"//div[contains(@class, 'title5') and .//span[contains(text(), '{answer}')]]")
                if not item:
                    self.logger.error(f"选项{answer}获取失败，无该选项，不选！")
                else:
                    await item.click()
                await asyncio.sleep(0.5)
            # 进入下一题，如果没有下一题跳出
            btn_next_question = await self.web_operator.get_elem_with_wait_by_xpath(2, "//button[@id='nextquest']")
            if not btn_next_question:
                # self.logger.error("下一题按钮获取失败，考试失败！")
                btn_commit = await self.web_operator.get_elem_with_wait_by_xpath(2, "//button[@id='submitquest']")
                if not btn_commit:
                    self.logger.error("立即交卷按钮获取失败，考试失败！")
                else:
                    # 等待时间满足5分钟。
                    # 获取剩下的时间，00:58:35，达到54分钟后交卷！
                    remaining_time = await self.web_operator.get_elem_with_wait_by_xpath(3, "//div[@id='showTime2']")
                    remaining_time_str = (await remaining_time.text_content()).strip()
                    while not self.is_past_five_minute(remaining_time_str):
                        self.logger.info(f"等待交卷时间满足！当前时间：{remaining_time_str}")
                        await asyncio.sleep(10)
                        remaining_time = await self.web_operator.get_elem_with_wait_by_xpath(3, "//div[@id='showTime2']")
                        remaining_time_str = (await remaining_time.text_content()).strip()

                    btn_commit = await self.web_operator.get_elem_with_wait_by_xpath(2, "//button[@id='submitquest']")
                    await self.web_operator.js_click(btn_commit)
                    # 获取确定按钮
                    btn_confirm = await self.web_operator.get_elem_with_wait_by_xpath(5, "//a[text()='确定']")
                    await self.web_operator.js_click(btn_confirm)
                    await self.web_operator.wait_for_url_changed(lambda url: "examWeb/handOver" in url, 10)
                    # 获取分数
                    el_score = await self.web_operator.get_elem_with_wait_by_xpath(10, "//div[@id='showMark']/p")
                    content_ = await el_score.text_content()
                    self.logger.info(f"考试完成，分数：{content_}")
                    self.user_manager.update_record_by_username(self.username, {5: content_})
                break
            else:
                await btn_next_question.click()
                await asyncio.sleep(1)

    def is_past_five_minute(self, current_remain_time: str, init_time="00:59:59") -> bool:
        """
        初始基准：00:59:59
        参数 current_remain_time: 当前剩余时间字符串，格式 "00:MM:SS"
        return: True 代表从初始00:59:59算起，已经消耗超过5分钟；False 未到
        """
        # init_total = 59 * 60 + 59  # 00:59:59 总秒数 3599
        hh, mm, ss = map(int, init_time.split(":"))
        init_total = hh * 3600 + mm * 60 + ss


        hh, mm, ss = map(int, current_remain_time.split(":"))
        curr_total = hh * 3600 + mm * 60 + ss

        consume = init_total - curr_total
        return consume > 320

@dataclass(init=False)
class HXJYWEnterCourseTaskNode(BasePYNode):
    """
    海西教育网进入课程
    可选参数：
    kw_project_name-项目名称
    exam_2804-题库配置。例如：exam_2804 = "B,B,B,B,B,B,B,AC,B,B,ABC,B,C,B,B,B,B,C,B,C"

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
    # 项目名称
    kw_project_name: str = ""
    # 题库处理器
    question_bank_handler: FixedQuestionBankHandler = None

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        self.excluded_courses = []
        self.chapter_name_list = []
        await self.switch_to_latest_window()
        # 2.处理上一步的输出数据
        self.project_code = self.get_prev_output().get("project_code", "")
        if not self.project_code:
            return False, "项目编码为空"

        if "hj" in self.project_code and "office/home" not in await self.get_current_url():
            # 跳转到选择项目页面
            await self.load_url("https://hxwyxpt.t-px.cn/office/home")
            await asyncio.sleep(2)
            # time.sleep(2)

        # self.course_type = self.node_config.get("node_params", {}).get("course_type")
        # if not "intoStudentStudy" in await self.get_current_url():
        #     if self.course_type.split("|")[-1] == 1:
        #         # 进入公需课
        #         await self._enter_pub_project()
        #     else:
        #         # 进入专业课
        #         await self._enter_pro_project()

        self.kw_project_name = self.node_config.get("node_params", {}).get("kw_project_name")
        if not "intoStudentStudy" in await self.get_current_url():
            await self._enter_project()

        question_bank_config = self.node_config.get("node_params", {}).get("exam_2804", "")
        if not question_bank_config:
            self.logger.error("题库配置为空，参数exam_2804不能为空")
            return False, "题库配置为空"
        self.question_bank_handler = FixedQuestionBankHandler("exam_2804", question_bank_config)

        # 等待页面加载完成
        # 处理完善个人信息的弹窗
        await self._handle_complete_info_tips()
        # await asyncio.sleep(3)
        # time.sleep(3)
        # await self.wait_for_disappeared_by_xpath(20, "//div[@class='layui-layer-shade']")
        learn_tab = await self.get_elem_with_wait_by_xpath(10, "//a[text()='学习计划']")
        await learn_tab.click()
        await self.js_click(learn_tab)
        await self._init_plan_id()
        await self._init_phase_id()

        await self._init_user_id()
        await self._init_project_id()

        learn_tab = await self.get_elem_with_wait_by_xpath(10, "//a[text()='考试']")
        await learn_tab.click()
        self.main_window_url = await self.get_current_url()
        if await self._is_passed():
            # 学习通过了，无需学习
            self.logger.info(f"考试成绩已经合格了，准备退出")
            # self.do_after_finished_all_courses()
            return False, f"公需课考试已合格！"
        else:
            # 处理完善个人信息的弹窗
            await self._handle_complete_info_tips()
            # 处理课程页面的建议信息
            await self._handle_course_page_tips()
            # 处理选课
            # self._handle_choose_course()
            # 判断课程类型
            # self._init_course_type()
            return True, ""

    async def execute(self, context: Dict) -> bool:
        # 登录后执行的操作！
        status, desc = await self.prepare_before_first_enter_course()
        if not status:
            self.user_manager.update_record_by_username(self.username, {3: desc})
            error_msg = f"进入课程失败：{desc}"
            self.logger.error(error_msg)
            return False

        # 1.进入考试
        status, desc = await self.enter_exam()
        if not status:
            self.user_manager.update_record_by_username(self.username, {3: desc})
            error_msg = f"进入考试失败：{desc}"
            self.logger.error(error_msg)
            return False
        # 2.开始考试
        exam_handler = JJWExamHandler(self.username, self, self.question_bank_handler, self.user_manager, self.logger)
        await exam_handler.do_exam()
        self.logger.info("考试结束！")

    async def enter_exam(self) -> Tuple[bool, str]:
        # 获得第一个未读的课程
        btn_enter_exam = await self.get_elem_with_wait_by_xpath(10, "//a[text()='进入考试']")
        if not btn_enter_exam:
            self.logger.error("进入考试按钮不存在")
            return False, "进入考试按钮不存在"
        await self.js_click(btn_enter_exam)
        el_tips = await self.get_elem_with_wait_by_xpath(3, "//div[@class='layui-layer-content']")
        if el_tips:
            # self.logger.error(f"不能考试：{await el_tips.text_content()}")
            return False, await el_tips.text_content()

        await self.wait_for_url_changed(lambda url: "examWeb/welcomeIndex" in url, 10)
        cb_promise = await self.get_elem_with_wait_by_xpath(10, "//input[@id='isCheck']")
        if not cb_promise:
            self.logger.error("同意考试须知复选框不存在")
            return False, "同意考试须知复选框不存在"

        await self.js_click(cb_promise)
        await asyncio.sleep(0.5)
        btn_start = await self.get_elem_with_wait_by_xpath(10, "//button[@id='startHtml']")
        if not btn_start:
            self.logger.error("开始考试按钮不存在")
            return False, "开始考试按钮不存在"
        await self.js_click(btn_start)

        # 获取考试提醒中的确定按钮
        btn_confirm = await self.get_elem_with_wait_by_xpath(10, "//a[text()='确定']")
        if btn_confirm:
            await self.js_click(btn_confirm)

        # 等待页面跳转
        await self.wait_for_url_changed(lambda url: "examWeb/onlineExamIndex" in url, 10)
        return True, ""

    async def send_node_output(self):
        """
        传递输出数据，可调用set_output_data方法设置输出的参数
        """
        self.set_output_data("project_code", self.project_code)

    async def _get_pub_first_course(self) -> Locator:
        ret = None
        xpath1 = "//a[(./preceding-sibling::i/text() = '学习中' or ./preceding-sibling::i/text() = '未学习') and @class='list-title'][.//following-sibling::a[text()='进入学习']]"
        # if "hxwysqy2025" in self.project_code or "hxxy2025" in self.project_code:
        xpath2 = "//a[(./preceding-sibling::i/text() = '学习中' or ./preceding-sibling::i/text() = '未学习') and @class='layui-btn layui-btn-primary' and @data-type='课程' ]"
        xpath = f"{xpath1} | {xpath2}"

        courses = await self.get_elems_with_wait_by_xpath(10, xpath, False)
        if courses:
            for course in courses:
                if await course.text_content() not in self.excluded_courses:
                    ret = course
                    break
        return ret

    async def _get_first_content(self):
        if "hxwysqy2025" in self.project_code:
            contents = await self.get_elems_with_wait_by_xpath(10,
                                                               "(//li[contains(@class, 'isStudy')])[last()]//following::li[contains(@class, 'type_1')]")
            if contents:
                first_content = contents[0]
                if not await first_content.is_visible():
                    await first_content.scroll_into_view_if_needed()
                return first_content
            else:
                return None
        else:
            first_content = None
            try:
                first_content = await self.get_elem_with_wait_by_xpath(3,
                                                                       "//div[@class='course-list-con']//li[contains(@class, 'cur')]//a",
                                                                       False)
            except:
                pass
            else:
                if not await first_content.is_visible():
                    await first_content.scroll_into_view_if_needed()
                    # if self.course_type == HXCourseType.PRO_COURSE:
                    # # 获取目录所处的章节，目的为了点击展开章节，让目录可见，才能点击
                    # chapter_elem: WebElement = first_content.find_element(By.XPATH,
                    #                                                       "../../preceding-sibling::h4//a")
                    # chapter_elem.click()
                    # time.sleep(1)
                    # if not first_content.is_visible():
                    #     first_content.scroll_into_view_if_needed()
            return first_content

    async def _get_content_name(self, cur_content):
        ret = None
        if "hxwysqy2025" in self.project_code:
            ret = await cur_content.get_attribute("title")
        else:
            try:
                course_name_elem = await self.get_elem_with_wait_by_xpath(5, "//div[@class='course-info']//a")
            except Exception as e:
                self.logger.error("没有获取到课程名称，页面出现异常！")
            else:
                ret = await course_name_elem.text_content() + "(" + await cur_content.text_content() + ")"
        return ret

    async def _wait_for_shade_disappear(self, wait_time=2):
        await self.wait_for_disappeared_by_xpath(wait_time, "//div[@class='layui-layer-shade']")

    async def _is_cur_content_contains_video(self):
        return True if await self.get_elem_with_wait_by_xpath(3, "//div[@class='ccH5playerBox']", False) else False

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

    async def _enter_pub_project(self):
        # 进入公需课
        enter_study_btn = await self.get_elem_with_wait_by_xpath(10,
                                                                 "//a[@class='btn-start' and contains(@onclick, '14071')]")
        if enter_study_btn:
            await enter_study_btn.click()
        else:
            self.logger.error(f"获取“进入学习”按钮失败，页面加载失败或者有变动")

    async def _enter_pro_project(self):
        # 进入专业课
        enter_study_btn = await self.get_elem_with_wait_by_xpath(10,
                                                                 "//a[@class='btn-start' and not(contains(@onclick, '14071'))]")
        if enter_study_btn:
            await enter_study_btn.click()
        else:
            self.logger.error(f"获取“进入学习”按钮失败，页面加载失败或者有变动")

    async def _enter_project(self):
        # 进入项目
        if self.kw_project_name:
            xpath = f"//ul[@id='inProgress']//a[@class='btn-start' and contains(text(), '{self.kw_project_name}')]"
        else:
            xpath = f"//ul[@id='inProgress']//a[@class='btn-start'][1]"

        enter_study_btn = await self.get_elem_with_wait_by_xpath(10, xpath)
        if enter_study_btn:
            await enter_study_btn.click()
        else:
            self.logger.error(f"获取“进入学习”按钮失败，页面加载失败或者有变动")

    async def _handle_complete_info_tips(self):
        alert_complete_info = await self.wait_for_visible_by_xpath(5,
                                                                   "//div[@class='layui-layer layui-layer-page'][./*[contains(text(),'补充个人信息')]]")
        if alert_complete_info:
            user_info = await self._get_user_info()
            if not user_info[5].strip():
                # 工作单位为空
                await self.execute_js(
                    "document.querySelector('input[name=\"workUnit\"]').value='%s'" % user_info[4].split(",")[-1])
            btn_confirm = await self.get_elem_by_xpath(
                "//div[@class='layui-layer layui-layer-page']//input[@class='layui-btn layui-btn-normal' and @value='保存']")
            if not await btn_confirm.is_visible():
                await btn_confirm.scroll_into_view_if_needed()
                await asyncio.sleep(1)
            await btn_confirm.click()
            await self._wait_for_shade_disappear(20)

    async def _get_user_info(self) -> tuple:
        """
        获取个人详细信息
        :return: tuple (姓名,学科,手机,身份证,区域,工作单位)
        """
        ret = None
        url = f"https://{self.project_code}.stu.t-px.cn/auth/complementUserInfo"
        # id=2974&projectPhaseId=642
        headers = {"Cookie": await self.cookie_to_str(), "User-Agent": await self.user_agent(),
                   "Referer": f"https://{self.project_code}.stu.t-px.cn/studyPlan/intoStudentStudy",
                   }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, headers=headers)
            # resp = requests.get(url, headers=headers)
        except:
            self.logger.error("获取考核结果异常")
            raise
        else:
            resp_json = json.loads(resp.text)
            user_info = resp_json["data"]["userInfo"]

        return user_info["name"], user_info["sectionName"] + user_info["subjectName"], user_info["mobile"], user_info[
            'idnumber'], user_info["path"], user_info["workUnit"]

    async def _is_passed(self):
        scores = await self._get_exam_score(self.project_id, self.user_id)
        # if not scores:
        #     scores = await self._get_course_score(self.project_id, self.user_id)
        # if "hxptzs2026" in self.project_code:
        #     scores = await self._get_score(self.project_id, self.user_id)
        # else:
        #     scores = await self._get_score2(self.plan_id, self.phase_id)
        return int(scores[1]) >= 60

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(2))
    async def _get_exam_score(self, project_id, user_id) -> tuple:
        """
        获取考试的考核成绩
        :param project_id:
        :param user_id:
        :return: tuple (总分,得分)
        """
        ret = None
        url = "https://%s.stu.t-px.cn/scoreStudent/findProjectPhaseScoreAndDetail" % self.project_code
        # url = "https://%s.stu.t-px.cn/scoreStudent/findProjectPhaseScore" % self.project_code
        # id=2974&projectPhaseId=642
        # params = {"id": user_id, "projectPhaseId": user_id}
        headers = {"Cookie": await self.cookie_to_str() + f";student_userId_cookie={user_id};projectId={project_id}",
                   "User-Agent": await self.user_agent(),
                   "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                   "Referer": "https://%s.stu.t-px.cn/scoreStudent/intoScoreStudent" % self.project_code,
                   "Origin": "https://%s.stu.t-px.cn" % self.project_code
                   }
        try:
            # resp = requests.post(url, data=params, headers=headers)
            # resp = requests.post(url, headers=headers)
            # async with httpx.AsyncClient() as client:
            #     resp = await client.post(url, headers=headers)
            resp = await self.context.request.post(url, headers=headers)
        except:
            self.logger.error("获取考核结果异常")
            raise
        else:
            resp_json = await resp.json()
            # ret = resp_json["data"]["projectPhaseScoreList"][0]["qualifiedPoint"], \
            #     resp_json["data"]["projectPhaseScoreList"][0]["onLineScore"]
            if resp_json.get("isSuccess") != 0:
                ret = resp_json["data"]["scoreDetailInfoList"][0]["scoreDetailDTO"]["examScoreList"][0]["examScore"], \
                    resp_json["data"]["scoreDetailInfoList"][0]["scoreDetailDTO"]["examScoreList"][0]["score"]
        return ret

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(2))
    async def _get_course_score(self, project_id, user_id) -> tuple:
        """
        获取课程的考核成绩
        :param project_id:
        :param user_id:
        :return: tuple (总分,得分)
        """
        ret = None
        url = "https://%s.stu.t-px.cn/scoreStudent/findProjectPhaseScoreAndDetail" % self.project_code
        # url = "https://%s.stu.t-px.cn/scoreStudent/findProjectPhaseScore" % self.project_code
        # id=2974&projectPhaseId=642
        # params = {"id": user_id, "projectPhaseId": user_id}
        headers = {"Cookie": await self.cookie_to_str() + f";student_userId_cookie={user_id};projectId={project_id}",
                   "User-Agent": await self.user_agent(),
                   "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                   "Referer": "https://%s.stu.t-px.cn/scoreStudent/intoScoreStudent" % self.project_code,
                   "Origin": "https://%s.stu.t-px.cn" % self.project_code
                   }
        try:
            # resp = requests.post(url, data=params, headers=headers)
            # resp = requests.post(url, headers=headers)
            # async with httpx.AsyncClient() as client:
            #     resp = await client.post(url, headers=headers)
            resp = await self.context.request.post(url, headers=headers)
        except:
            self.logger.error("获取考核结果异常")
            raise
        else:
            resp_json = await resp.json()
            # ret = resp_json["data"]["projectPhaseScoreList"][0]["qualifiedPoint"], \
            #     resp_json["data"]["projectPhaseScoreList"][0]["onLineScore"]
            if resp_json.get("isSuccess") != 0:
                ret = resp_json["data"]["scoreDetailInfoList"][0]["scoreDetailDTO"]["contentTypeCourse"][
                    "courseMaxScore"], \
                    resp_json["data"]["scoreDetailInfoList"][0]["scoreDetailDTO"]["contentTypeCourse"]["courseScore"]
        return ret

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(2))
    async def _get_course_score2(self, study_plan_id, project_phase_id) -> Optional[tuple]:
        """
        获取课程的考核成绩
        :param study_plan_id:
        :param project_phase_id:
        :return: tuple (总分,得分)
        """
        ret = None
        url = "https://%s.stu.t-px.cn/scoreStudent/findScoreStudentListByStudyPlanIdAndProjectPhaseId" % self.project_code
        # id=2974&projectPhaseId=642
        params = {"id": study_plan_id, "projectPhaseId": project_phase_id}
        headers = {"Cookie": await self.cookie_to_str(), "User-Agent": await self.user_agent(),
                   "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                   "Referer": "https://%s.stu.t-px.cn/scoreStudent/intoScoreStudent" % self.project_code,
                   "Origin": "https://%s.stu.t-px.cn" % self.project_code
                   }
        try:
            resp = await self.context.request.post(url, data=params, headers=headers)
        except:
            self.logger.error("获取考核结果异常")
            raise
        else:
            resp_json = await resp.json()
            if resp_json.get("isSuccess") != 0:
                ret = resp_json["data"]["scoreDetailDTO"]["contentTypeCourse"]["courseMaxScore"], \
                    resp_json["data"]["scoreDetailDTO"]["contentTypeCourse"]["courseScore"]
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

    async def _handle_choose_course(self):
        for chapter_name in self.chapter_name_list:
            # 获取未选课的章节
            first_unchoose_chapter = await self.get_elem_with_wait_by_xpath(5,
                                                                            f"(//li[.//h2[text()='{chapter_name}']]//a[text()='去选课'])[1]",
                                                                            False)
            if first_unchoose_chapter:
                # 处理选课
                await self._enter_choose_course(chapter_name, first_unchoose_chapter)

    async def _enter_choose_course(self, chapter_name, first_unchoose_chapter):

        if not await first_unchoose_chapter.is_visible():
            chapter_title_elem = await self.get_elem_with_wait_by_xpath(10, f"//li[.//h2[text()='{chapter_name}']]")
            await chapter_title_elem.click()

        # 等待元素可见
        await self.wait_for_visible(10, first_unchoose_chapter)
        if not await first_unchoose_chapter.is_visible():
            raise BusinessException(f"选课模块{chapter_name}不可见，点击不了！")
        # 点击元素
        await asyncio.sleep(2)
        # time.sleep(2)
        unchoose_module = await self.get_relative_elem_by_xpath(first_unchoose_chapter, "./preceding-sibling::a")
        unchoose_module_name = await unchoose_module.text_content()
        self.logger.info(f"{chapter_name}-{unchoose_module_name}，开始选课...")

        await first_unchoose_chapter.click()
        max_count = 20
        cycle_count = 0
        while cycle_count < max_count:
            cycle_count += 1
            await asyncio.sleep(0.4)
            # time.sleep(0.4)
            if "intoSelectCourseList" in await self.get_current_url():
                break
        if cycle_count == max_count:
            raise BusinessException("进入选课页面失败")

        await asyncio.sleep(2)
        # 获取选课规则
        course_course_rule = await self.get_elems_with_wait_by_xpath(10,
                                                                     "//div[@id='selectRule']//span[@class='c_orange']")
        if not course_course_rule:
            raise BusinessException("获取选课规则失败")
        total_course_count = int(await course_course_rule[1].text_content())
        min_course_count = int(await course_course_rule[0].text_content())
        need_choose_course_count = min_course_count
        if min_course_count <= total_course_count - 1:
            need_choose_course_count = min_course_count + 1

        courses = await self.get_elems_with_wait_by_xpath(10, "//td[@class='fristchild']")
        need_choose_course_count = len(courses) if need_choose_course_count > len(courses) else need_choose_course_count

        for i in range(need_choose_course_count):
            course_check_box = await self.get_elem_with_wait_by_xpath(10, f"(//input[@name='ids'])[{i + 1}]")
            if not course_check_box:
                pass
                # raise BusinessException("获取选课选择框失败")
            else:
                if not await course_check_box.is_visible():
                    await course_check_box.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                    # time.sleep(0.5)
                await course_check_box.click()

            await asyncio.sleep(1.5)
            # time.sleep(1.5)

        # 确认选课按钮
        confirm_choose_btn = await self.get_elem_with_wait_by_xpath(10, "//button[@id='submitCourse']")
        if not confirm_choose_btn:
            raise BusinessException("获取选课确认按钮失败")

        if not await confirm_choose_btn.is_visible():
            await confirm_choose_btn.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            # time.sleep(0.5)
        await confirm_choose_btn.click()

        max_count = 20
        cycle_count = 0
        while cycle_count < max_count:
            cycle_count += 1
            await asyncio.sleep(0.4)
            # time.sleep(0.4)
            if "intoStudentStudy" in await self.get_current_url():
                break
        if cycle_count == max_count:
            raise BusinessException("进入课程页面失败")
        else:
            self.logger.info(f"{chapter_name}-{unchoose_module_name}，选课成功！")
            first_unchoose_chapter = await self.get_elem_with_wait_by_xpath(10,
                                                                            f"(//li[.//h2[text()='{chapter_name}']]//a[text()='去选课'])[1]",
                                                                            visible=False)
            if first_unchoose_chapter:
                await self._enter_choose_course(chapter_name, first_unchoose_chapter)
            else:
                return

    async def _handle_content_pause_tips(self):
        confirm_btn = await self.get_elem_by_xpath(
            "//div[contains(@class,'layui-layer layui-layer-dialog')][.//*[contains(text(),'视频暂停')]]//a[text()='Ok，我知道了！']")

        if confirm_btn and await confirm_btn.is_enabled() and await confirm_btn.is_visible():
            try:
                await confirm_btn.click()
            except:
                pass
            else:
                # 等待确认按钮消失
                await self.wait_for_disappeared(2, confirm_btn)
                # 等待蒙版消失
                await self._wait_for_shade_disappear()

    async def _handle_content_finished_tips(self):
        ret = False
        xpath = "//div[contains(@class,'layui-layer layui-layer-dialog')][.//*[contains(text(),'视频已播放完成')]]//a[text()='Ok，我知道了！']"
        if "hxwysqy2025" in self.project_code:
            xpath = "//div[contains(@class,'layui-layer layui-layer-dialog')]//a[text()='Ok，我知道了！']"

        confirm_btn = await self.get_elem_by_xpath(xpath)
        if confirm_btn and await confirm_btn.is_enabled() and await confirm_btn.is_visible():
            await confirm_btn.click()
            # 等待对话框消失
            await self.wait_for_disappeared(2, confirm_btn)
            # 等待蒙版消失
            await self._wait_for_shade_disappear()
            ret = True
        return ret
