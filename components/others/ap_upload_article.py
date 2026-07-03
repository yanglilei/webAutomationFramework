import asyncio
from dataclasses import dataclass, field
from typing import Tuple, Dict, Any

from playwright.async_api import Locator
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from components_deps.jinja2.async_utils import auto_aiter
from src.frame.base.base_enter_course_node import BaseEnterCourseTaskNode
from src.frame.base.base_task_node import BasePYNode
from src.frame.common.exceptions import BusinessException
from src.utils import UploadLocalFile


@dataclass(init=False)
class APUploadArticle(BasePYNode):
    """
    奥鹏上传作业
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
    # 上传本地文件的操作句柄
    upload_file_handle: UploadLocalFile = None

    def set_up(self):
        super().set_up()
        self.upload_file_handle = UploadLocalFile()

    async def execute(self, context: Dict) -> bool:
        pass

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        # self.main_window_url = "https://office.teacher.com.cn/views/learningViews/myOffice/index.html"
        # await self.open_in_new_window(self.main_window_url)
        await self._enter_project()

        await self.wait_for_url_changed(lambda url: "stu/index?projectId=32139" in url)

        # 进入实践性作业
        task_elem = await self.get_elem_with_wait_by_xpath(10, "//p[./span[text()='实践性作业']]")
        if task_elem:
            await task_elem.click()
        else:
            raise BusinessException("未找到【实践性作业】")
        commit_elem = await self.get_elem_with_wait_by_xpath(10, "//div[contains(@class, 'h-button-success')]")
        if commit_elem:
            await commit_elem.click()
        else:
            self.logger.error("未找到【去提交】按钮，可能作业已提交了")
            return False, ""

        await self.wait_for_url_changed(lambda url: "/stu/task/commit" in url)
        # TODO PAUSE BY ZCY
        content_input_iframe = self.switch_to_frame("//p[contains(text(), '正文内容')]/following-sibling::div//iframe[@class='tox-edit-area__iframe']")
        input_body = await self.get_elem_with_wait_by_xpath(10, "//body[@id='tinymce']", iframe=content_input_iframe)
        await input_body.evaluate("(el) => el.innerHTML += '<p>作业见附件！</p>'")
        btn_upload = await self.get_elem_with_wait_by_xpath(10, "//div[@class='add_file']")
        if btn_upload:
            await btn_upload.click()
            await asyncio.sleep(2)

            self.upload_file_handle.select_file()
        else:
            self.logger.error("未找到【上传作业】按钮")


        btn_commit = await self.get_elem_with_wait_by_xpath(10, "//div[text()='提交']")
        await btn_commit.click()
        return True

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

    async def _handle_alert(self, dialog):
        await dialog.accept()
        await asyncio.sleep(1)
        await self.load_url("https://mingshi8.hbte.com.cn/index.php/Home/Project/index.html")

    async def _enter_project(self):
        await self.register_alert_handler(self._handle_alert)
        if await self.get_current_url() != "https://mingshi8.hbte.com.cn/index.php/Home/Project/index.html":
            await self.load_url("https://mingshi8.hbte.com.cn/index.php/Home/Project/index.html")
            await asyncio.sleep(1)
        btn_show_project = await self.get_elem_with_wait_by_xpath(20,
                                                                  "(//a[contains(@class, 'jinxingProductA')])[last()]")
        await self.js_click(btn_show_project)
        btn_enter_project = await self.get_elem_with_wait_by_xpath(20, "//a[@id='tiao']")
        await self.js_click(btn_enter_project)

    async def handle_prev_output(self, prev_output: Dict[str, Any]):
        project_code = prev_output.get("project_code", "")
        if project_code and project_code.strip():
            self.project_code = project_code.strip()

    async def send_node_output(self):
        """
        传递输出数据，可调用set_output_data方法设置输出的参数
        """
        self.set_output_data("project_code", self.project_code)

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

    async def _wait_for_shade_disappear(self):
        await self.wait_for_disappeared_by_xpath(2, "//div[@class='layui-layer-shade']")

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
            self.logger.error(f"用户【{self.username_showed}】获取“进入学习”按钮失败，页面加载失败或者有变动")

    async def _enter_pro_project(self):
        # 进入专业课
        enter_study_btn = await self.get_elem_with_wait_by_xpath(10,
                                                                 "//a[@class='btn-start' and not(contains(@onclick, '14071'))]")
        if enter_study_btn:
            await enter_study_btn.click()
        else:
            self.logger.error(f"用户【{self.username_showed}】获取“进入学习”按钮失败，页面加载失败或者有变动")

    async def _handle_complete_info_tips(self):
        alert_complete_info = await self.wait_for_visible_by_xpath(3,
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
            resp = await self.context.request.get(url, headers=headers)
            # resp = requests.get(url, headers=headers)
        except:
            self.logger.error("用户【%s】获取考核结果异常" % self.username_showed)
            raise
        else:
            json_obj = await resp.json()
            user_info = json_obj["data"]["userInfo"]

        return user_info["name"], user_info["sectionName"] + user_info["subjectName"], user_info["mobile"], user_info[
            'idnumber'], user_info["path"], user_info["workUnit"]

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
        url = "https://pn202513034.stu.teacher.com.cn/scoreStudent/findProjectPhaseScoreAndDetail"
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

    async def _get_score2(self, study_plan_id, project_phase_id) -> tuple:
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
        headers = {"Cookie": await self.cookie_to_str(), "User-Agent": await self.user_agent(),
                   "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                   "Referer": "https://%s.stu.t-px.cn/scoreStudent/intoScoreStudent" % self.project_code,
                   "Origin": "https://%s.stu.t-px.cn" % self.project_code
                   }
        try:
            resp = await self.context.request.post(url, data=params, headers=headers)
        except:
            self.logger.error("用户【%s】获取考核结果异常" % self.username_showed)
            raise
        else:
            resp_json = await resp.json()
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
        self.logger.info(f"用户【{self.username_showed}】{chapter_name}-{unchoose_module_name}，开始选课...")

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
            self.logger.info(f"用户【{self.username_showed}】{chapter_name}-{unchoose_module_name}，选课成功！")
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
