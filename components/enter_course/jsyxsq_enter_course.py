import asyncio
import random
from dataclasses import dataclass, field
from random import random
from typing import Tuple, List, Any

from playwright.async_api import Page
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.frame.base import BaseEnterCourseTaskNode


@dataclass(init=False)
class JSYXSQEnterCourse(BaseEnterCourseTaskNode):
    """
    教师研修社区，进入课程
    http://cas.study.yanxiu.jsyxsq.com/auth/selfHost/studyPlace/index.html#/stu/newCourse/list?ptCode=34601&stageId=1185&menuRefId=241855&isOption=
    """
    # 请求头
    headers: dict[str, Any] = field(default_factory=dict)
    video_page: Page = None
    workspace_page: Page = None
    course_url: str = ""

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        # 异步监听请求
        self.headers = {}
        async def handle_request(request):
            url = request.url
            if "/api/menu/getMenu" in url or "/api/system/getPermissionList" in url:
                visitor_id = request.headers.get("visitorid")
                self.headers = {"visitorid": visitor_id}

        self.get_current_page().on("request", handle_request)
        self.headers[
            "user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"

        self.workspace_page = self.get_current_page()
        status, score = await self._get_score()
        if status:
            self.logger.info(f"已合格，得分：{score}")
            return False, f"已合格，得分：{score}"
        else:
            self.logger.info(f"未合格，得分：{score}")
            return True, f"未合格，得分：{score}"

    async def enter_course(self) -> Tuple[bool, str]:
        if self.get_prev_output().get("restart_flag", False) and self.course_url:
            return await self._learn_new_course(self.course_url, self.course_name)
        else:
            self.course_url, course_name = await self._get_first_unfinished_course()
            if not self.course_url:
                self.logger.info("所有课程已学完！")
                return False, "所有课程已学完！"
            else:
                return await self._learn_new_course(self.course_url, course_name)

    async def _learn_new_course(self, course_url, course_name):
        # 打开新课程
        await self.open_in_new_window(course_url, referer=await self.get_current_url())
        await asyncio.sleep(3)
        pages = await self.get_windows_by_url_key(course_url)
        if not pages:
            return False, "打开新课程失败！"
        self.video_page = pages[0]
        self.set_output_data("video_page", self.video_page)
        self.set_output_data("headers", self.headers)
        return True, course_name

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        # await self.close_window(self.video_page)
        # await asyncio.sleep(2)
        await self.switch_to_window(self.workspace_page)
        return True, ""

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _get_personal_stage_list(self) -> List:
        """
        获取个人专题列表
        :return:
        """
        url = "http://cas.study.yanxiu.jsyxsq.com/api/outline/personalStatistics?all=0&taskDetail=1"
        response = await self.context.request.get(url, headers=self.headers)
        response_json = await response.json()
        if response_json["code"] == 0:
            return response_json["data"]["detail"]
        else:
            return []

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _get_personal_course_list(self, stage_id: str, pt_code="34601", page_num=1, page_size=10) -> List:
        """
        获取课程列表
        :param stage_id:
        :param pt_code:
        :param page_num:
        :param page_size:
        :return:
        """
        url = r"http://cas.study.yanxiu.jsyxsq.com/api/newCourse/getStudentNewCourseList"
        # {"category":1,"courseName":"","currentPage":1,"dimensionId":null,"environmentId":null,"isOption":"","pageSize":10,"ptCode":"34601","stageId":"1173","status":null,"subjectId":null}
        # 基础请求体模板
        base_payload = {"category": 1, "courseName": "", "currentPage": page_num, "dimensionId": None,
                        "environmentId": None,
                        "isOption": "", "pageSize": page_size, "ptCode": pt_code, "stageId": stage_id,
                        "status": None,
                        "subjectId": None}

        all_data = []
        current_page = 1

        try:
            while True:
                payload = base_payload.copy()
                payload["currentPage"] = current_page
                response = await self.context.request.post(url, data=payload, headers=self.headers)
                res_json = await response.json()

                if res_json.get("code") != 0 or not res_json.get("success"):
                    self.logger.error(f"接口返回异常：{res_json}")
                    break

                data = res_json.get("data", {})
                page_list = data.get("list", [])
                total_count = data.get("totalCount", 0)
                page_size = data.get("pageSize", 10)

                if not page_list:
                    self.logger.error(f"第 {current_page} 页无数据，结束")
                    break

                all_data.extend(page_list)
                self.logger.debug(f"第 {current_page} 页获取成功，本页 {len(page_list)} 条，累计 {len(all_data)} 条")

                # 计算总页数
                total_pages = (total_count + page_size - 1) // page_size
                if current_page >= total_pages:
                    self.logger.debug(f"已到最后一页（共 {total_pages} 页），结束")
                    break

                current_page += 1
                await asyncio.sleep(random.uniform(0.1, 3))  # 礼貌延时，防止封禁

        except Exception as e:
            self.logger.error(f"请求出错：{e}")
            raise
        return all_data

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _transfer_course_id(self, course_id):
        url = f"http://cas.study.yanxiu.jsyxsq.com/api/uccourse/hasSectionFlag?ptcode=34601&courseId={course_id}"
        response = await self.context.request.get(url, headers=self.headers)
        response_json = await response.json()
        if response_json["code"] == 0:
            return response_json["data"]
        else:
            return ""

    async def _get_all_unfinished_courses(self, stage_id: str):
        """
        获取某个专题下所有未完成的课程
        :param stage_id: 专题ID
        :return:
        """
        courses = await self._get_personal_course_list(stage_id)
        return [course for course in courses if course["watchPercentage"] != "1"]

    async def _get_all_stages_contains_online_video(self):
        """
        获取所有包含视频的专题
        :return:
        """
        personal_stage_list = await self._get_personal_stage_list()
        topics_contains_video = []
        for topic in personal_stage_list:
            for pt in topic["detail"]:
                if pt["title"] == "课程学习":
                    topics_contains_video.append(topic)
                    break
        target_topics = []
        for topic in topics_contains_video:
            # 排除掉已经合格的课程
            if await self.is_study_qualified(topic["stageId"]):
                await asyncio.sleep(random.uniform(0.3, 2))
                continue
            else:
                target_topics.append(topic)
        return target_topics

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def is_study_qualified(self, stage_id: str, pt_code="34601"):
        """
        判断当前阶段学习是否合格
        返回：tuple (是否合格:bool, 详细信息:dict)
        """
        url = "http://cas.study.yanxiu.jsyxsq.com/api/newCourse/getCourseStudyInfo"

        payload = {
            "stageId": stage_id,
            "ptCode": pt_code,
            "isOption": ""
        }

        try:
            resp = await self.context.request.post(url, data=payload, headers=self.headers)
            res = await resp.json()

            # 接口请求失败
            if not res.get("success") or res.get("code") != 0:
                raise Exception(res.get("msg"))
            data = res.get("data", {})
            grade = data.get("grade", 0.0)  # 当前得分
            pass_score = data.get("passScore", 0.0)  # 合格线
            # dead_line = data.get("deadLineTime")  # 截止时间

            # 核心：是否合格
            is_pass = grade >= pass_score

            # 附加信息
            # info = {
            #     "当前得分": grade,
            #     "合格分数线": pass_score,
            #     "截止时间": dead_line,
            #     "已选课程数": data.get("hasSelCourseCount", 0),
            #     "总学习时长": data.get("studyAllTime", 0),
            #     "是否合格": is_pass
            # }

            return is_pass

        except Exception as e:
            self.logger.error(f"请求出错：{e}")
            raise e

    async def _get_first_unfinished_course(self):
        """
        获取第一个未完成的课程，返回课程的url
        :return:
        """
        stages = await self._get_all_stages_contains_online_video()
        course_info = None
        stage_id = None
        for stage in stages:
            stage_id = stage["stageId"]
            courses = await self._get_all_unfinished_courses(stage_id)
            if courses:
                course_info = courses[0]
                break

        course_id = course_info["courseId"]
        course_name = course_info["courseName"]
        category = course_info["category"]
        if not await self._is_course_ok(course_id):  # 上一个课程未正确完成，当前的课程不能学习，要进入学完！
            course_id, course_name = await self._get_unfinished_recent_course()

        if course_info:
            # new_course_id = await self._transfer_course_id(course_id)
            new_course_id = await self._has_section(course_id)
            # url = f"http://cas.study.yanxiu.jsyxsq.com/auth/selfHost/studyPlace/index.html#/stu/studyNew?isTime=1&id={course_id}&stageId={stage_id}&ucCourseId={new_course_id}&category={category}&ptCode=34601"
            url = f"http://cas.study.yanxiu.jsyxsq.com/auth/selfHost/studyPlace/index.html#/stu/studyNew?isTime=1&id={course_id}&ucCourseId={new_course_id}&category={category}&ptCode=34601"
            return url, course_name
        else:
            return None, ""

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _get_score(self):
        """
        获取学习成绩
        :return: (bool, float) (状态-合格；不合格, 得分)
        """
        url = "http://cas.study.yanxiu.jsyxsq.com/api/outline/personGrade"
        try:
            resp = await self.context.request.get(url, headers=self.headers)
            res = await resp.json()
            # 接口请求失败
            if not res.get("success") or res.get("code") != 0:
                raise Exception(res.get("msg"))
            data = res.get("data", {})
            grade = data.get("grade", 0.0)  # 当前得分
            status = data.get("hgStatus")  # 合格线
            return status, grade
        except Exception as e:
            self.logger.error(f"获取成绩失败：{e}")
            raise

    async def _is_course_ok(self, course_id):
        url = f"http://cas.study.yanxiu.jsyxsq.com/api/newCourse/windowCourse?courseId={course_id}"
        try:
            response = await self.context.request.get(url, headers=self.headers)
            res = await response.json()
            # 接口请求失败
            if not res.get("success") or res.get("code") != 0:
                raise Exception(res.get("msg"))
            return res.get("data")
        except Exception as e:
            self.logger.error(f"获取成绩失败：{e}")
            raise

    async def _get_unfinished_recent_course(self):
        url = "http://cas.study.yanxiu.jsyxsq.com/api/newCourse/study/record"
        try:
            response = await self.context.request.get(url, headers=self.headers)
            res = await response.json()
            # 接口请求失败
            if not res.get("success") or res.get("code") != 0:
                raise Exception(res.get("msg"))
            data = res.get("data")
            return data.get("courseId"), data.get("courseName")
        except Exception as e:
            self.logger.error(f"获取成绩失败：{e}")
            raise

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _has_section(self, course_id):
        url = f"http://cas.study.yanxiu.jsyxsq.com/api/uccourse/hasSectionFlag?ptcode=34601&courseId={course_id}"
        try:
            response = await self.context.request.get(url, headers=self.headers)
            res = await response.json()
            # 接口请求失败
            if not res.get("success") or res.get("code") != 0:
                raise Exception(res.get("msg"))
            return res.get("data")
        except Exception as e:
            self.logger.error(f"获取成绩失败：{e}")
            raise
