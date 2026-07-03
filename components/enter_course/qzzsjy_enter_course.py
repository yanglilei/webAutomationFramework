import asyncio
import random
import re
from dataclasses import dataclass, field
from typing import Tuple, List, Dict, Any

from playwright.async_api import Page, Locator
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.frame.base.base_enter_course_node import BaseEnterCourseTaskNode
from src.frame.common.exceptions import BusinessException


@dataclass(init=False)
class JJJXJYEnterCourseTaskNode(BaseEnterCourseTaskNode):
    """
    泉州终身教育大数据平台学进入课程
    https://qzzsjy.mh.chaoxing.com/
    """
    # 工作空间窗口句柄
    workspace_page: Page = None
    # 学习课程窗口句柄
    course_page: Page = None
    # 跳过的课程列表
    skip_plan_list: List = field(default_factory=list)
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
    # 班级名称
    class_name: str = ""
    # 学生ID
    student_id: str = ""
    # 用户工作空间url
    workspace_url: str = ""
    # 目标页面（学习、考试页面）的url key
    target_page_url_key: str = ""
    # 课程类型。-1-未知的类型；0-学习视频；1-大测验
    course_type: int = 0
    # 排除掉的班级ID
    excluded_courses: List = field(default_factory=list)

    COURSE_URL_KEY = "mooc2-ans/mycourse/stu"
    EXAM_URL_KEY = "exam-ans/exam"

    async def handle_prev_output(self, prev_output: Dict[str, Any]):
        skip_course_name = self.get_prev_output().get("skip_course")
        if skip_course_name and skip_course_name.strip():
            self.skip_plan_list.append(skip_course_name.strip())

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        self.skip_plan_list = []
        self.excluded_courses = []
        self.workspace_page = self.get_latest_window()
        self.class_name = self.node_config.get("node_params", {}).get("class_name", "")
        self.workspace_url = self.node_config.get("node_params", {}).get("workspace_url", "")
        if not self.workspace_url:
            return False, "未指定空间地址"
        else:
            await self.load_url(self.workspace_url)
            await asyncio.sleep(2)
        return True, ""

    async def _enter_one_plan(self, class_elem: Locator):
        if not await class_elem.is_visible():
            await class_elem.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
        await class_elem.click()

        # 获取班级名字
        class_name_elem = await self.get_elem_with_wait_by_xpath(10, "//h3[@id='className']",
                                                                 iframe=self.switch_to_frame(
                                                                     "iframe#frame_content"))
        if class_name_elem:
            class_name = await class_name_elem.text_content()
        else:
            self.logger.error(f"获取班级名称失败，可能页面元素发生变动！")
            # continue
            return False, "获取班级名称失败"

        # TODO 此处要设置class_name，否则获取class_id和student_id会失败
        # 获取某个班级
        class_id, self.student_id = await self._get_target_running_class(class_name)
        if not class_id or not self.student_id:
            return False, "未找到班级"

        # 进入有效的学习计划
        status, desc = await self._enter_valid_plan(class_id, self.student_id)
        return status, desc

    async def enter_course(self) -> Tuple[bool, str]:
        # 进入课程
        is_enter_one_plan = False
        iframe = self.switch_to_frame("iframe#frame_content")
        if not self.class_name:
            # 不指定班级名称，则学习所有的班级
            xpath = "//div[@class='l_tcourse_center h120'][.//dt[contains(text(), '培训')]][.//dd[4][contains(.//text(), '未合格') or contains(.//text()[2], '未合格')]]/preceding-sibling::div[@class='l_tcourse_right fr clearf']//a[contains(@onclick, 'projectPlanListUI')]"
            class_list = await self.get_elems_with_wait_by_xpath(10, xpath, iframe=iframe)
            if not class_list:
                return False, "所有课程已完成"

            for idx, class_elem in enumerate(class_list):
                if self.excluded_courses and idx in self.excluded_courses:
                    continue
                # 进入有效的学习计划
                status, desc = await self._enter_one_plan(class_elem)
                if not status:  # 学习完了，但是状态未更新的跳过，后续会自动进入下一个班级
                    self.excluded_courses.append(idx)  # 跳过，进入下一个班级
                    await self.go_back()
                    continue
                else:
                    # 进入了一个学习计划中
                    is_enter_one_plan = True
                    break
        else: # 指定班级名称
            xpath = f"(//div[@class='l_tcourse_center h120'][.//dt[contains(text(), '{self.class_name}')]]/preceding-sibling::div[@class='l_tcourse_right fr clearf']//a)[1]"
            class_elem = await self.get_elem_with_wait_by_xpath(10, xpath, iframe=iframe)
            # 进入有效的学习计划
            status, desc = await self._enter_one_plan(class_elem)
            if not status:
                # 跳过，进入下一个班级
                return status, desc
            else:
                # 进入了一个学习计划中
                is_enter_one_plan = True

        if not is_enter_one_plan:
            return False, "进入课程失败"

        # 切换窗口
        await self.switch_to_window_by_url_key(self.target_page_url_key)
        if self.course_type == 0:
            await self.handle_promission_tips()
            await asyncio.sleep(1)
            # 获取课程名称
            course_name = await self.get_course_name()
            # 点击第一个视频开始学习
            if not await self.enter_course_detail_page():
                # 进入课程详情页面失败
                # 关掉课程详情页面，回到工作空间，重新尝试
                await self.close_window(self.get_current_page())
                await self.switch_to_window(self.workspace_page)
                # 刷新当前页面
                await self.refresh()
                return await self.enter_course()
            # 等待跳转
            await asyncio.sleep(2)
            self.course_page = self.get_current_page()
            self.set_output_data("course_page", self.course_page)
        elif self.course_type == 1:
            # 大测验
            course_name = "大测验"
            self.course_page = self.get_current_page()
            self.set_output_data("course_page", self.course_page)
        else:
            return False, "未知的课程类型"

        # time.sleep(2)
        return True, course_name

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        """
        一个课程结束后的操作逻辑
        :return: 切换成功返回：(True, 成功)；切换失败返回：(False, 失败原因)
        """
        await self.close_window(self.course_page)
        await self.switch_to_window(self.workspace_page)
        # 刷新当前页面
        await self.refresh()
        return True, "切换成功"

    async def enter_workspace(self):
        ret = True
        btn_enter_workspace = await self.get_elem_with_wait_by_xpath(10, "//div[@aria-label='去学习']/div")
        try:
            await btn_enter_workspace.click()
            # self.execute_js("arguments[0].click();", btn_enter_workspace)
        except:
            self.logger.error("用户【%s】点击【去学习】按钮失败" % self.username_showed)
            ret = False

        return ret

    async def has_chosen_course(self):
        iframe = self.switch_to_frame("iframe#frame_content")
        # self.web_browser.switch_to.iframe("frame_content")
        sign = await self.get_elem_with_wait_by_xpath(10, "//li[@class='curr']//a", iframe=iframe)
        if not sign or await sign.text_content() in ["进行中 (0)", "Processing (0)"]:
            # self.web_browser.switch_to.default_content()
            return False
        else:
            # self.web_browser.switch_to.default_content()
            return True

    async def choose_course(self) -> Tuple[bool, str]:
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
        grade_item = await self.get_elem_with_wait_by_xpath(10, xpath)
        try:
            if not await grade_item.is_visible():
                await grade_item.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                # time.sleep(1)
            await grade_item.click()
            # self.execute_js("arguments[0].click();", grade_item)
        except:
            self.logger.error("用户【%s】点击【年段】按钮失败" % self.username_showed)
            return False, f"选课失败-进入【年段】失败"
        # 等待弹出新浏览器tab
        await asyncio.sleep(3)
        # time.sleep(3)

        await self.switch_to_latest_window()

        target_course = await self.get_elem_with_wait_by_xpath(10,
                                                               f"//div[@class='content overflowHidMultiLine'][starts-with(text(), '{self.teach_course_name}')]",
                                                               False)
        while not target_course:
            btn_next_page = await self.get_elem_with_wait_by_xpath(10, "//button[@class='btn-next']", False)
            if btn_next_page and await btn_next_page.is_enabled():
                # 跳到下一页
                await self.js_click(btn_next_page)
                await asyncio.sleep(2)
                # time.sleep(2)
                target_course = await self.get_elem_with_wait_by_xpath(10,
                                                                       f"//div[@class='content overflowHidMultiLine'][text()='{self.teach_course_name}']",
                                                                       False)
            else:
                # 到了最后一页，没有更多课程了，说明没有找到该课程
                self.logger.error("选课失败：没有找到【%s】课程" % self.teach_course_name)
                return False, f"选课失败-没有【{self.teach_course_name}】课程"

        await self.js_click(target_course)
        await asyncio.sleep(2)
        # time.sleep(2)
        btn_sign_up = await self.get_elem_with_wait_by_xpath(10, "//a[contains(text(),'报名')]")
        await btn_sign_up.click()

        await self.wait_for_visible_by_xpath(10, "//p[@class='px_tree_stit overhidden']")

        btn_commit_info = await self.get_elem_with_wait_by_xpath(10, "//a[@id='submit']")
        await btn_commit_info.click()
        if await self.wait_for_visible_by_xpath(10, "//div[@class='w_paystatus_pic']"):
            self.logger.info("用户【%s】选课成功" % self.username_showed)

        return True, "选课成功"

    async def get_first_unfinished_class(self, class_name=""):
        iframe = self.switch_to_frame("iframe#frame_content")
        if class_name:
            xpath = f"(//div[@class='l_tcourse_center h120'][.//dt[contains(text(), '{class_name}')]]/preceding-sibling::div[@class='l_tcourse_right fr clearf']//a)[1]"
        else:
            xpath_tmp = "(//div[@class='l_tcourse_center h120'][.//dt[contains(text(), '培训')]][.//dd[4][contains(.//text(), '%s') or contains(.//text()[2], '%s')]]/preceding-sibling::div[@class='l_tcourse_right fr clearf']//a)[1]"
            xpath = xpath_tmp % ('未合格', '未合格')

        return await self.get_elem_with_wait_by_xpath(10, xpath, iframe=iframe)

    async def enter_plan_list(self, class_name=""):
        status = True
        desc = ""

        iframe = self.switch_to_frame("iframe#frame_content")

        if class_name:
            xpath = f"(//div[@class='l_tcourse_center h120'][.//dt[contains(text(), '{class_name}')]]/preceding-sibling::div[@class='l_tcourse_right fr clearf']//a)[1]"
        else:
            xpath_tmp = "(//div[@class='l_tcourse_center h120'][.//dt[contains(text(), '培训')]][.//dd[4][contains(.//text(), '%s') or contains(.//text()[2], '%s')]]/preceding-sibling::div[@class='l_tcourse_right fr clearf']//a)[1]"
            xpath = xpath_tmp % ('未合格', '未合格')

        first_subject = await self.get_elem_with_wait_by_xpath(10, xpath, iframe=iframe)
        if not first_subject:
            status = False
            desc = "已合格"
            # if await self.get_elem_by_xpath(xpath_tmp % ('已合格', '已合格')):
            #     # 学习已合格了，截图保存
            #     succ_dir = Path(SysPathUtils.get_root_dir(), "succ")
            #     succ_dir.mkdir(parents=True, exist_ok=True)
            #     await self.screenshot(succ_dir.joinpath(self.username + "-succ.png"))
            #     status = False
            #     desc = "已合格"
            # else:
            #     # 进入课程失败截图
            #     error_dir = Path(SysPathUtils.get_root_dir(), "error", "安溪继续教育")
            #     error_dir.mkdir(parents=True, exist_ok=True)
            #     await self.screenshot(error_dir.joinpath(self.username + "-error" + str(
            #         random.randint(0, 100000)) + ".png"))
            #     status = False
            #     desc = "进入异常"
        else:
            if not await first_subject.is_visible():
                await first_subject.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
            await first_subject.click()
        return status, desc

    @retry(retry=retry_if_exception_type((BusinessException, Exception)), stop=stop_after_attempt(3),
           wait=wait_fixed(1))
    async def _get_running_classes(self):
        url = "https://qzkd.px.chaoxing.com/studentspace/projectClass/getData?searchKey=&status=1&isShowCrossUnitData=0&page=1&limit=8"
        headers = {"cookie": await self.cookie_to_str(),
                   "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"}
        response = await self.context.request.get(url, headers=headers)
        response_obj = await response.json()
        if response_obj.get("success"):
            return response_obj.get("data")
        else:
            self.logger.error(f"获取进行中的项目失败：{response_obj.get('msg')}")
        return []

    async def _get_target_running_class(self, class_name=""):
        running_classes = await self._get_running_classes()
        ret = "", ""
        if running_classes:
            if class_name:
                for running_class in running_classes:
                    if running_class.get("name") == class_name:
                        ret = running_class.get("id"), running_class.get("projectClassStudent").get("studentId")
                        break
            else:
                ret = running_classes[0].get("id"), running_classes[0].get("projectClassStudent").get("studentId")
        return ret

    @retry(retry=retry_if_exception_type((BusinessException, Exception)), stop=stop_after_attempt(3),
           wait=wait_fixed(1))
    async def _get_plan_list(self, class_id, student_id, page_num=1, page_size=10):
        """
        {
            "success": true,
            "msg": "success",
            "code": 200,
            "data": [
                {
                "id": "69d60984c4bb486b411c230c",
                "projectPlanObjectId": null,
                "planType": 2,
                "cover": null,
                "categoryId": 1,
                "name": "人工智能技术在教学中的融入与应用、AI辅助教学设计、AI强化教学支持",
                },
                {}
            ]
            "PageCount": 1,
            "totalCount": 7,
            "page": 1,
            "suspension": 0,
            "projectClassStatus": 1,
            "isStudyDeadLine": true
        }
        :param class_id: 班级ID
        :param student_id: 学生ID
        :param page_num: 页码
        :param page_size: 页大小
        :return:
        """
        url = f"https://qzkd.px.chaoxing.com/studentspace/projectPlan/getProjectPlanData?classId={class_id}&studentId={student_id}&projectPlanType=-1&page={page_num}&limit={page_size}"
        headers = {"cookie": await self.cookie_to_str(),
                   "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"}

        response = await self.context.request.get(url, headers=headers)
        response_obj = await response.json()
        if response_obj.get("success"):
            return response_obj
        else:
            self.logger.error(f"获取进行中的项目失败：{response_obj.get('msg')}")
        return {}

    async def _exclude_plans(self, plans):
        """
        排除掉计划！
        :param plans: 计划列表，从班级中查询出来的所有计划列表
        :return:
        """
        tmp_need_remove_plans = []
        plan_ids = []
        for plan in plans:  # 排除掉未解锁的课程
            plan_ids.append(plan.get("id"))
            if not plan.get("allowStudyPlan"):
                # 未解锁
                tmp_need_remove_plans.append(plan)

        plan_progress_info = await self._get_plan_progress(plan_ids, self.student_id)
        for plan_progress in plan_progress_info:
            if int(plan_progress.get("taskCount")) == 100:
                # 已经满分了
                for plan in plans:
                    if plan_progress.get("planId") == plan.get("id"):
                        tmp_need_remove_plans.append(plan)
                        break

        if self.skip_plan_list:
            for plan_name in self.skip_plan_list:
                for plan in plans:
                    if plan_name == plan.get("name"):
                        tmp_need_remove_plans.append(plan)

        return [plan for plan in plans if plan not in tmp_need_remove_plans]

    @retry(retry=retry_if_exception_type((BusinessException, Exception)), stop=stop_after_attempt(3),
           wait=wait_fixed(1))
    async def _get_plan_progress(self, plan_ids, student_id):
        url = "https://qzkd.px.chaoxing.com/studentspace/projectPlan/getBatchMoocCourseMessage"
        form = {"planIds": ",".join(plan_ids), "studentId": student_id}
        headers = {"cookie": await self.cookie_to_str(),
                   "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"}
        response = await self.context.request.post(url, form=form, headers=headers)
        response_obj = await response.json()
        if response_obj.get("success"):
            return response_obj.get("moocCourseMessageVoList")
        else:
            self.logger.error(f"获取学习计划的进度失败：{response_obj.get('msg')}")
        return {}

    async def _search_paginate_v2(self, class_id, student_id):
        """
        返回班级下所有页的教学计划，一个元素表示一页的教学计划内容
        :param class_id: 班级ID
        :param student_id: 学生ID
        :return: list[dict]
        """
        plan_pagination_info = []
        plan_info = await self._get_plan_list(class_id, student_id, 1, 10)
        if plan_info:
            # 排除掉未解锁和点不开的学习计划
            plans = await self._exclude_plans(plan_info.get("data"))
            plan_info["data"] = plans
            plan_pagination_info.append(plan_info)
            page_num = plan_info.get("page")
            while plan_info.get("PageCount") > page_num:  # 有下一页
                await asyncio.sleep(random.uniform(0.3, 2))
                plan_info = await self._get_plan_list(class_id, student_id, page_num + 1, 10)
                if plan_info:
                    # 排除掉未解锁和点不开的学习计划
                    plans = await self._exclude_plans(plan_info.get("data"))
                    plan_info["data"] = plans
                    plan_pagination_info.append(plan_info)
                else:
                    self.logger.info(f"没有查询到第{page_num + 1}页的数据，可能丢失数据！")
        else:
            self.logger.info("没有查询到第1页的数据，可能丢失数据！")
        return plan_pagination_info

    async def _enter_valid_plan(self, class_id, student_id):
        plan_info_paginations = await self._search_paginate_v2(class_id, student_id)
        if not plan_info_paginations:
            self.logger.warning("未找到可以学习的计划，准备退出！")
            return False, "未找到可以学习的计划！"

        is_enter_target_plan = False
        if plan_info_paginations:
            for plan_info_pagination in plan_info_paginations:
                if is_enter_target_plan:
                    break
                # 翻页到指定页面
                page_num = plan_info_pagination.get("page")
                await self._jump_to_target_page(page_num)

                for plan in plan_info_pagination.get("data"):
                    plan_id = plan.get('id')
                    plan_name = plan.get("name")
                    category_id = plan.get("categoryId")
                    if category_id == 1:
                        # 视频
                        self.course_type = 0
                        self.target_page_url_key = self.COURSE_URL_KEY
                        xpath = f"//div[@class='px_form_btn l_sform_btn fr' and contains(@onclick, '{plan_id}')]"
                    elif category_id == 3:
                        # TODO 考试
                        self.course_type = 1
                        self.target_page_url_key = self.EXAM_URL_KEY
                        xpath = f"//div[@class='px_form_btn l_sform_btn fr']//a[contains(@onclick, '{plan_id}') and text()='去考试']"
                    else:
                        self.course_type = -1
                        self.logger.error(f"未知的课程类型：{category_id}")
                        return False, "未知的课程类型"

                    btn_enter_plan = await self.get_elem_with_wait_by_xpath(10, xpath, False,
                                                                            iframe=self.switch_to_frame(
                                                                                "iframe#frame_content"))
                    if not btn_enter_plan:
                        if self.course_type == 0:
                            # 翻页到指定页面后，没有找到该课程，异常！
                            self.logger.error(f"在第{page_num}页没有找到课程：{plan_name}，学习异常，退出！")
                            return False, f"在第{page_num}页没有找到课程：{plan_name}"
                        elif self.course_type == 1:
                            # 考试已考完，忽略该考试！
                            self.logger.warning(f"在第{page_num}页的考试已考完！")
                            self.skip_plan_list.append(plan_name)
                            continue

                    if not btn_enter_plan.is_visible():
                        await btn_enter_plan.scroll_into_view_if_needed()
                        await asyncio.sleep(1)

                    if not await self._preclick(btn_enter_plan):  # 预点击，若是不打开新的学习页面则该计划无法学习，忽略该计划
                        self.logger.error(f"学习计划：【{plan_name}】进入失败，排除！")
                        self.skip_plan_list.append(plan_name)
                    else:
                        is_enter_target_plan = True
                        break

        return (True, "") if is_enter_target_plan else (False, "没有可学习的计划！")

    async def _jump_to_target_page(self, page_num: int):
        iframe = self.switch_to_frame("iframe#frame_content")
        # 跳转到指定页面
        btn_page = await self.get_elem_with_wait_by_xpath(1, f"//div[@class='pageDiv']//li[text()='{page_num}']", False,
                                                          iframe)
        if btn_page:
            if not btn_page.is_visible():
                await btn_page.scroll_into_view_if_needed()
                await asyncio.sleep(1)

            await self.js_click(btn_page)
            await asyncio.sleep(2)

    async def get_first_unfinished_course(self):  # 返回第一个未完成课程和预点击状态，对每个课程都会做预点击操作，为什么这么做？因为有些课程点击了进不去（平台bug）。
        is_preclick_succ = False
        # self.web_browser.switch_to.iframe("frame_content")
        iframe = self.switch_to_frame("iframe#frame_content")
        # 获取第一个未完成的课程
        # xpath = "//li[@class='l_tcourse_list moocCourse clearf'][.//span[@class='l_sprogress_text mal10' and not(contains(text(), '100%'))]][1]//a"
        comm_xpath = "//li[@class='l_tcourse_list moocCourse clearf'][.//span[@class='l_sprogress_text mal10' and not(contains(text(), '100%'))]]"
        plan_name_xpath = f"{comm_xpath}//div[@class='l_tcourse_center studentCourse']//dt[1]"
        plan_button_xpath = f"{comm_xpath}//div[@class='px_form_btn l_sform_btn fr']"

        # TODO 关键测试xxxxx
        # xpath = "//li[@class='l_tcourse_list moocCourse clearf'][.//span[@class='l_sprogress_text mal10' and not(contains(text(), '100%'))]]//div[@class='px_form_btn l_sform_btn fr'][contains(@onclick, '师生沟通的艺术')]"
        course_elems = await self.get_elems_with_wait_by_xpath(10, plan_button_xpath, False, iframe)
        # 去掉被排除的课程！
        course_elems = await self._exclude_courses(course_elems)
        course_elems = await self._search_paginate(course_elems, plan_button_xpath, iframe)
        if course_elems:
            # 1.预点击，检查是否弹出新窗口
            while not await self._preclick(course_elems[0]):
                # 2.没有弹出新窗口，则排除该课程
                self.skip_plan_list.append(await self._get_course_name_in_course_list(course_elems[0]))
                course_elems = await self._exclude_courses(course_elems)
                # 3.重新搜索
                course_elems = await self._search_paginate(course_elems, plan_button_xpath, iframe)
                if not course_elems:
                    break

            # 预点击成功，外头不要再点击，否则会出现元素过期的bug
            is_preclick_succ = True
            # self.close_latest_window()
            # self.switch_to_window(self.workspace_page)
        if not course_elems:
            return None, is_preclick_succ
        else:
            return course_elems[0], is_preclick_succ

    async def _exclude_courses(self, course_elems: List[Locator]):
        tmp_need_remove_elems = []
        if self.skip_plan_list:
            for course_name in self.skip_plan_list:
                for course_elem in course_elems:
                    if course_name in await course_elem.get_attribute("onclick"):
                        tmp_need_remove_elems.append(course_elem)
        course_elems = [course_elem for course_elem in course_elems if course_elem not in tmp_need_remove_elems]
        return course_elems

    async def _search_paginate(self, course_elems, xpath, iframe):
        while not course_elems:
            is_succ = await self.go_next_course_page(iframe)
            if is_succ:
                # 强制等待页面加载完成
                await asyncio.sleep(2)
                # time.sleep(2)
                course_elems = await self.get_elems_with_wait_by_xpath(10, xpath, False, iframe)
                # 去掉被排除的课程！
                course_elems = await self._exclude_courses(course_elems)
            else:
                # 翻页失败，或则没有下一页了，则没有未读课程
                break
            # 等待页面加载完成
            await asyncio.sleep(2)
            # time.sleep(2)
        return course_elems

    async def go_next_course_page(self, iframe):
        # True-翻页成功；False-翻页失败
        # self.web_browser.switch_to.iframe("frame_content")
        ret = True
        btn_next_page = await self.get_elem_with_wait_by_xpath(10, "//li[@class='xl-nextPage']", False, iframe)
        if not btn_next_page or not await btn_next_page.is_enabled():
            ret = False
        else:
            if not await btn_next_page.is_visible():
                await btn_next_page.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                # time.sleep(1)
            try:
                await btn_next_page.click()
            except:
                self.logger.exception("用户【%s】点击【下一页】按钮失败" % self.username_showed)
                ret = False
        return ret

    async def _preclick(self, elem):
        ret = False
        # 预点击
        if not await elem.is_visible():
            await elem.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
            # time.sleep(0.5)
        await elem.click()

        # 等待新窗口打开
        max_wait_count = 10
        # 最多等待10秒
        while max_wait_count > 0:
            await asyncio.sleep(1)
            # 等待弹出新窗口
            if await self.get_windows_by_url_key(self.COURSE_URL_KEY) or await self.get_windows_by_url_key(
                    self.EXAM_URL_KEY):
                ret = True
                break
            max_wait_count -= 1

        return ret

    async def _get_course_name_in_course_list(self, elem):
        # onclick = "isAllowGoStudy('68f60c39048f4e00504d0bbb','2025年安溪县“初中信息科技”（职校）教师远程继续教育培训_《信息科技课程各学段学业质量标准分析》','1')"
        maches = re.findall(r"'(.*?)'", await elem.get_attribute("onclick"), re.S)
        return maches[1].split("_")[1].strip()

    async def handle_promission_tips(self):
        tips_elem = await self.get_elem_with_wait_by_xpath(3, "//div[@class='popDiv course-pop']")
        if tips_elem:
            btn_agree_elem = await self.get_elem_by_xpath("//input[@class='agreeButton']")
            await btn_agree_elem.click()
            await asyncio.sleep(1)
            # time.sleep(1)
            start_learn_elem = await self.get_elem_by_xpath(
                "//a[contains(@class, 'agreeStart') and text()='开始学习'][2]")
            await start_learn_elem.click()

    async def get_course_name(self):
        course_name_elem = await self.get_elem_with_wait_by_xpath(10, "//dd[@class='textHidden colorDeep']")
        return "" if not course_name_elem else await course_name_elem.get_attribute("title")

    async def enter_course_detail_page(self):
        # self.web_browser.switch_to.iframe("frame_content-zj")
        iframe = self.switch_to_frame("#frame_content-zj")
        # 获取第一个任务点>0的课程
        # xpath = "//li[./div[@class='chapter_item']//span[@class='catalog_points_yi' and text()>0]]"
        xpath = "//li[./div[@class='chapter_item']//span[@class='catalog_points_yi']]"
        contents = await self.get_elems_with_wait_by_xpath(10, xpath, iframe=iframe)
        if contents:
            if not await contents[0].is_visible():
                await contents[0].scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
                # time.sleep(0.5)
            await contents[0].click()
            return True
        else:
            return False

    async def refresh_plan_list_current_page(self):
        # self.web_browser.switch_to.iframe("frame_content")
        iframe = self.switch_to_frame("#frame_content")
        btn_refresh = await self.get_elem_with_wait_by_xpath(1, "//div[@class='pagination']//li[@class='xl-active']",
                                                             False, iframe)
        if btn_refresh:
            # 有多页的情况
            if not await btn_refresh.is_visible():
                await btn_refresh.scroll_into_view_if_needed()
                await asyncio.sleep(1)
            await self.js_click(btn_refresh)
        else:
            # 没有多页的情况，刷新当前页面
            await self.refresh()
