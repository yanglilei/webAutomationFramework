"""
基础教师教育培训网
"""
import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Tuple, List, Literal
from urllib.parse import urlparse, parse_qs

from lxml import etree
from lxml.etree import _Element
from playwright.async_api import Page
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.frame.base import BaseEnterCourseTaskNode
from src.frame.common.exceptions import BusinessException


@dataclass(init=False)
class BETTEnterCourse(BaseEnterCourseTaskNode):
    project_id: str = ""
    all_courses: list[tuple[str, str]] = field(default_factory=list)
    excluded_courses: list[str] = field(default_factory=list)
    project_page: Page = None

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        project_name = self.node_config.get("node_params", {}).get("project_name", "")
        await self._enter_project(project_name)

        await self.wait_for_url_changed("https://px.chinabett.com/PersonalCenter", 10)
        topic_name = self.node_config.get("node_params", {}).get("topic_name")
        if not topic_name:
            raise BusinessException("请配置节点参数：topic_name[专题名称]")
        await self._enter_one_topic(topic_name)
        # https://px.chinabett.com/PrjStudent?prjId=d43c13c4ba744f6d9950b3cd0142ee7f&memberType=0&wgId=93ad2b19dc854203966bb3d100a6aee7
        # 获取url中的prjId
        self.project_id = self._get_param_val(await self.get_current_url())
        await self.close_other_windows(self.project_page)
        return True, ""

    async def enter_course(self) -> Tuple[bool, str]:
        await self.switch_to_window(self.project_page)
        self.all_courses = await self._get_all_unfinished_courses(self.project_id)
        if self.all_courses:
            stage_id, course_id = self.all_courses[0]
            # course_url = f"https://vc.chinabett.com/StudyDuration/Index?pid={self.project_id}&cid={course_id}&ui={uid}&t=1"
            course_url = await self._get_course_url(stage_id, course_id)
            await self.open_in_new_window(course_url)
            await asyncio.sleep(2)
            await self.switch_to_window_by_url_key("StudyDuration/Index")
            self.set_output_data("project_id", self.project_id)
            self.set_output_data("course_id", course_id)
            self.set_output_data("project_page", self.project_page)
            self.set_output_data("uid", self._get_param_val(await self.get_current_url(), "uid"))
            return True, await self._get_course_name()
        else:
            return False, "已完成"

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        return True, ""

    async def _get_course_name(self):
        course_name_elem = await self.get_elem_with_wait_by_xpath(10, "//div[@class='play_title']")
        course_name = (await course_name_elem.text_content()).split("-")[0] if course_name_elem else ""
        return course_name

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(2))
    async def _get_course_url(self, stage_id, course_id):
        url = "https://px.chinabett.com/PrjStudent/GetCourseProgress"
        headers = {"cookie": await self.cookie_to_str(),
                   "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                   "referer": await self.get_current_url()}
        response = await self.context.request.post(url, form={"stageId": stage_id, "courseid": course_id},
                                                   headers=headers)
        resp_html = await response.text()
        elem: _Element = etree.HTML(resp_html)
        return elem.xpath("(//tr[.//span[@class='fa6' and text() != '100%']]//a[@class='star'])[1]/@href")[0]

    async def _handle_alert(self, dialog):
        await dialog.accept()
        await asyncio.sleep(1)
        await self.load_url("https://mingshi8.hbte.com.cn/index.php/Home/Project/index.html")

    async def _enter_project(self, project_name: str):
        await self.register_alert_handler(self._handle_alert)
        if await self.get_current_url() != "https://mingshi8.hbte.com.cn/index.php/Home/Project/index.html":
            await self.load_url("https://mingshi8.hbte.com.cn/index.php/Home/Project/index.html")
            await asyncio.sleep(1)

        if project_name:
            xpath = f"//a[contains(@class, 'jinxingProductA')][./div[contains(@title, '{project_name}')]]"
        else:
            xpath = "(//a[contains(@class, 'jinxingProductA')])[last()]"
        btn_show_project = await self.get_elem_with_wait_by_xpath(20, xpath)
        await self.js_click(btn_show_project)
        btn_enter_project = await self.get_elem_with_wait_by_xpath(20, "//a[@id='tiao']")
        await self.js_click(btn_enter_project)

    async def _enter_one_topic(self, project_name: str):
        xpath = f"(//div[@class='project-summary project-summaryPanel']//li[.//a[contains(text(), '{project_name}')]]//div[@class='prjbtnPanel']//a)[last()]"
        btn_enter_course = await self.get_elem_by_xpath(xpath)
        await btn_enter_course.click()
        await asyncio.sleep(2)  # 等待弹出窗口
        await self.switch_to_latest_window()
        self.project_page = self.get_latest_window()

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(2))
    async def _get_stages(self, project_id, exclude_stages: list[str]):
        url = f"https://px.chinabett.com/PrjStudent/GetStageInfo?prjId={project_id}"
        response = await self.context.request.get(url, headers={"cookie": await self.cookie_to_str()})
        text = await response.text()
        try:
            resp_json = json.loads(text)
            # resp_json = await response.json()
        except:
            self.logger.error(f"获取项目信息失败：{text}")
            return []
        else:
            stage_ids = []
            for module in resp_json.get("Data", []):
                if module["StageName"] in exclude_stages:
                    continue
                stage_ids.append(module["StageId"])
            return stage_ids

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(2))
    async def _get_stage_info(self, project_id: str, stage_id: str) -> _Element:
        url = f"https://px.chinabett.com/PrjPublicInfo/GetPrjWatchCourse"
        # prjId=09ea123b67c84accbb07b3bb00e60978&stageId=655a3bbf2e884ac69c67b3bb00e64e62&memberType=0&prjIsOver=0
        params = {
            "prjId": project_id,
            "stageId": stage_id,
            "memberType": 0,
            "prjIsOver": 0
        }
        headers = {"cookie": await self.cookie_to_str(),
                   "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
        response = await self.context.request.post(url, form=params, headers=headers)
        resp_html = await response.text()
        return etree.HTML(resp_html)

    def _is_stage_finished(self, stage_info: _Element):
        desc = "".join(stage_info.xpath("//div[@class='note']//p/text() | //p//span/text()"))
        return True if "恭喜" in desc else False

    def _cal_remaining_class_hour(self, stage_info: _Element) -> Tuple[float, float]:
        # 返回必修小时和选修小时
        text_ = "".join(stage_info.xpath("//div[@class='note']//p/text() | //p//span/text()"))
        idx = text_.find("还差")
        if idx == -1:
            return 0.0, 0.0
        else:
            remaining_class_hour_desc = text_[idx:]
            required_hours = re.findall("必修\s*:\s*(\d+\.?\d*)", remaining_class_hour_desc)[0].strip()
            elective_hours = re.findall("选修\s*:\s*(\d+\.?\d*)", remaining_class_hour_desc)[0].strip()
            return float(required_hours), float(elective_hours)

    async def _get_all_courses(self, stage_info: _Element, course_type: str,
                               finished_status: Literal["已完成", "开始学习", "继续学习"] = "已完成") -> \
            List[Tuple[float, str]]:
        # 课程类型：必修、选修
        # 返回：[(学时, 课程id), (学时, 课程id), ...]
        courses = []
        xpath = f"//table[@id='watchcourseTable']//tr[.//td[contains(text(), '{course_type}')]][.//td[last()][./a[text()='{finished_status}']]]"
        # 第一个课程
        first_tr = stage_info.xpath(xpath)
        first_tr = first_tr[0] if first_tr else None
        # first_tr = await self.get_elem_by_xpath(xpath)
        if first_tr:
            # 获取学时
            # class_hour = await self.get_relative_elem_by_xpath(first_tr, ".//td[last()-3]")
            # btn_enter_course = await self.get_relative_elem_by_xpath(first_tr, ".//td[last()]//a")
            # course_id = self._get_course_id(await btn_enter_course.get_attribute("onclick"))
            # courses.append((float(await class_hour.text_content()), course_id[1:-1]))
            class_hour = first_tr.xpath(".//td[last()-3]")[0]
            btn_enter_course = first_tr.xpath(".//td[last()]//a")[0]
            course_id = self._get_course_id(btn_enter_course.get("onclick"))
            courses.append((float(class_hour.text), course_id[1:-1]))

        # xpath = f"//table[@id='watchcourseTable']//tr[.//td[contains(text(), '{course_type}')]]/following-sibling::tr[.//td[last()][./a[text()='{finished_status}']]]"
        # # 第二个之后的课程
        # other_trs = stage_info.xpath(xpath)
        # # other_trs = await self.get_elems_by_xpath(xpath)
        # for tr in other_trs[:50 if len(other_trs) > 100 else -1]:
        #     # class_hour = await self.get_relative_elem_by_xpath(tr, ".//td[last()-3]")
        #     # btn_enter_course = await self.get_relative_elem_by_xpath(tr, ".//td[last()]//a")
        #     # course_id = self._get_course_id(await btn_enter_course.get_attribute("onclick"))
        #     # courses.append((float(await class_hour.text_content()), course_id[1:-1]))
        #     class_hour = tr.xpath(".//td[last()-3]")[0]
        #     btn_enter_course = tr.xpath(".//td[last()]//a")[0]
        #     course_id = self._get_course_id(btn_enter_course.get("onclick"))
        #     courses.append((float(class_hour.text), course_id[1:-1]))
        return courses

    async def _get_unfinished_courses_best_combination(self, project_id, stage_id: str):
        # 获取某个阶段下未完成的课程组合
        # 返回：必修课程ID列表, 选修课程ID列表
        stage_info = await self._get_stage_info(project_id, stage_id)
        if self._is_stage_finished(stage_info):
            return []

        remaining_required_hours, remaining_elective_hours = self._cal_remaining_class_hour(stage_info)
        # finished_required_courses = await self._get_all_courses("必修", "已完成")
        # 统计已完成的所有必修课程
        # required_hours = sum(h for h, _ in finished_required_courses) if finished_required_courses else 0
        #
        # remaining_required_hours = 0
        # if target_required_hours - required_hours > 0:
        #     remaining_required_hours = target_required_hours - required_hours
        #
        # finished_elective_courses = await self._get_all_courses("选修", "已完成")
        # # 统计已完成的所有必修课程
        # elective_hours = sum(h for h, _ in finished_elective_courses) if finished_elective_courses else 0
        # remaining_elective_hours = 0
        # if target_elective_hours - required_hours > 0:
        #     remaining_elective_hours = target_elective_hours - elective_hours

        target_courses = []
        if remaining_required_hours > 0:
            target_courses.extend(await self._get_all_courses(stage_info, "必修", "继续学习"))
            target_courses.extend(await self._get_all_courses(stage_info, "必修", "开始学习"))
            # target_courses = await self._choose_best_combination(remaining_required_hours,
            #                                                               await self._get_all_courses("必修",
            #                                                                                           "开始学习"))

        if remaining_elective_hours > 0:
            target_courses.extend(await self._get_all_courses(stage_info, "选修", "继续学习"))
            target_courses.extend(await self._get_all_courses(stage_info, "选修", "开始学习"))
            # target_elective_courses = await self._choose_best_combination(remaining_elective_hours,
            #                                                               await self._get_all_courses("选修",
            #                                                                                           "开始学习"))

        return [cid for _, cid in target_courses] if target_courses else []

    async def _get_all_unfinished_courses(self, project_id):
        stage_ids = await self._get_stages(project_id, ["实践作业", "研修活动", "研修作业"])

        course_info = []
        for stage_id in stage_ids:
            course_ids = await self._get_unfinished_courses_best_combination(project_id, stage_id)
            for course_id in course_ids:
                course_info.append((stage_id, course_id))
            await asyncio.sleep(1)

        return course_info

    async def _choose_best_combination(self, target_hours: float, courses: list[tuple[float, str]]) -> list[
        tuple[float, str]]:
        # 让AI实现，最优获取课程的组合！
        combo, total, diff = self._find_best_course_combination_dp(target_hours, courses)
        if diff < 0:
            self.logger.error(f"课程总学时，不满足要求学时：{target_hours}，请人工介入检查！")
            raise BusinessException(f"课程总学时，不满足要求学时：{target_hours}")
        return combo

    def _get_course_id(self, on_click_desc: str) -> str:
        return on_click_desc.split(",")[2]

    def _get_param_val(self, url, param_name="prjId"):
        parsed_url = urlparse(url)
        query_params = parse_qs(parsed_url.query)
        return query_params.get(param_name, [""])[0]

    def _find_best_course_combination_dp(self,
                                         target_hours: float,
                                         courses: List[Tuple[float, str]],
                                         scale: int = 100  # 浮点数缩放倍数，保留2位小数
                                         ) -> Tuple[List[Tuple[float, str]], float, float]:
        """
        动态规划寻找最优课程组合（总学时 ≥ 目标值，且总学时最小）
        :param target_hours: 目标总学时（float）
        :param courses: 课程列表，格式 [(学时, 课程ID), ...]
        :param scale: 浮点数缩放倍数，避免浮点精度问题
        :return: 最优组合列表、组合总学时、与目标学时的差值
        """
        # 边界处理
        if not courses or target_hours <= 0:
            return [], 0.0, 0.0 if target_hours <= 0 else target_hours

        # 浮点数缩放为整数（解决DP浮点误差）
        target_int = int(round(target_hours * scale))
        course_list = [(int(round(h * scale)), idx) for h, idx in courses]
        total_sum_int = sum(h for h, _ in course_list)  # 所有课程总学时（缩放后）

        # DP数组：dp[j] = 是否能组合出缩放后学时为j
        dp = [False] * (total_sum_int + 1)
        dp[0] = True
        path = [None] * (total_sum_int + 1)  # 回溯路径

        # 0-1背包核心逻辑
        for h, idx in course_list:
            for j in range(total_sum_int, h - 1, -1):
                if dp[j - h] and not dp[j]:
                    dp[j] = True
                    path[j] = (h, idx)

        # 寻找最优值：≥目标的最小可达学时
        best_int = None
        for j in range(target_int, total_sum_int + 1):
            if dp[j]:
                best_int = j
                break
        # 无满足条件的组合，取最大可达学时
        if best_int is None:
            best_int = max(j for j, val in enumerate(dp) if val)

        # 回溯组合
        best_combo = []
        current = best_int
        while current > 0 and path[current] is not None:
            h, idx = path[current]
            best_combo.append((h / scale, idx))
            current -= h

        best_total = best_int / scale
        best_diff = round(best_total - target_hours, 2)
        return best_combo, round(best_total, 2), best_diff
