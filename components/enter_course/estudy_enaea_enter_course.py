import asyncio
import random
import re
import time
from dataclasses import dataclass, field
from typing import Tuple, List, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

from lxml import etree
from playwright.async_api import Page
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.frame.base import BaseEnterCourseTaskNode
from src.frame.common.exceptions import BusinessException


@dataclass
class StudyParam:
    inner_username: str = ""
    syllabus_id: str = ""
    circle_id: str = ""
    type: str = ""


@dataclass(init=False)
class EstudyEnterCourse(BaseEnterCourseTaskNode):
    """
    中国教育干部网络学院进入课程
    从estudy进入到study或者estudy课程
    登录网址：https://estudy.enaea.edu.cn/login
    可选参数：
    project_name：项目名称，若无指定则默认选择第一个项目

    版本：V0.0.2
    时间：2026-10-21 1:19
    """

    # 请求头
    headers: dict = field(default_factory=dict)
    # 所有项目信息
    all_projects: dict = field(default_factory=dict)
    # 目标项目信息
    target_project_info: dict = field(default_factory=dict)
    # 新版参数（未启用）
    estudy_params: dict = field(default_factory=dict)
    business_id: str = ""
    estudy_course_url_tmpl = "https://estudy.enaea.edu.cn/web/player/project?activity_id=%s&plan_id=%s&version=%s&path=%s&business_id=%s&template_id=%s&course_id=%s&project_id=%s"
    # event: asyncio.Event = asyncio.Event()
    course_page: Page = None
    # 项目类型。1-study（旧版）；2-estudy（新版）
    project_type: int = 0
    # 旧版参数
    study_params: Optional[StudyParam] = None
    # 指定的项目名称，若无指定则默认选择第一个项目
    project_name: str = ""

    async def handle_response(self, response):
        request = response.request
        # 异步监听请求：https://apaas.grtcloud.net/api/grt-user-center-service/user/business/v1/composite?business_id=2070327433486200832&template_id=104
        if "/api/grt-user-center-service/user/learn-business/v1/top-batch" in request.url:
            authorization = request.headers.get("authorization")
            xhmac_access_key = request.headers.get("x-hmac-access-key")
            xhmac_algorithm = request.headers.get("x-hmac-algorithm")
            xhmac_signature = request.headers.get("x-hmac-signature")
            xhmac_date = request.headers.get("x-hmac-date")
            xhmac_signed_headers = request.headers.get("x-hmac-Signed-Headers")
            xhmac_timestamp = request.headers.get("x-hmac-Timestamp")
            user_agent = request.headers.get("user-agent")
            # request_params = request.params
            # parsed = urlparse(response.url)
            # qs = parse_qs(parsed.query)
            # self.business_id = qs["business_id"][0]

            headers = {"authorization": authorization, "x-hmac-access-key": xhmac_access_key,
                       "x-hmac-algorithm": xhmac_algorithm, "x-hmac-signature": xhmac_signature,
                       "x-hmac-date": xhmac_date, "x-hmac-Signed-Headers": xhmac_signed_headers,
                       "x-hmac-Timestamp": xhmac_timestamp,
                       "user-agent": user_agent}
            self.headers.update(headers)

            response_json = await response.json()
            self.all_projects = response_json.get("data")

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        self.headers = self.get_prev_output().get("headers", {})
        self.all_projects = self.get_prev_output().get("all_projects", {})
        self.project_name = self.node_config.get("node_params", {}).get("project_name", "")
        self.target_project_info = {}
        return True, ""

    async def enter_course(self) -> Tuple[bool, str]:
        project_url = await self._get_project_first_project()
        if not project_url:
            return False, "项目URL获取失败！"
        status, course_name = await self._enter_first_unfinished_course(project_url)
        if not status:
            return False, "无未完成的课程！"

        self.set_output_data("course_page", self.course_page)
        await self.close_other_windows(self.course_page)
        return True, course_name

    async def _enter_first_unfinished_course(self, project_url: str) -> tuple[bool, str]:
        await self.open_in_new_window(project_url)
        if project_url.startswith("https://study.enaea.edu.cn"):
            # 旧版学习公社的项目
            self.project_type = 1
            return await self._enter_first_unfinished_course_study()
        elif project_url.startswith("https://estudy.enaea.edu.cn"):
            # 新版学习公社的项目
            self.project_type = 2
            return await self._enter_first_unfinished_course_estudy()
        else:
            # 不能解析的项目类型
            self.logger.error("不能解析的项目类型")
            self.project_type = 0
            return False, "不能解析的项目类型"

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        # target_score, finished_score = await self._get_progress_v2(self.study_params.get("inner_username"), self.study_params.get("circle_id"), self.study_params.get("syllabus_id"))
        # if finished_score >= target_score:
        #     self.logger.info(f"已学完，目标时间：{target_score}，完成时间：{finished_score}！")  # 已学完，达到目标时间：100.0！
        #     return False, "已学完"
        return True, ""

    async def _get_project_first_project(self):
        # 没有指定项目名称，则选择第一个项目
        project_url = ""
        for project_info in self.all_projects:
            project_payloads = project_info.get("list")
            for project_payload in project_payloads:
                if self.project_name and self.project_name != project_payload.get("title"):
                    continue
                # 没有指定项目名称，则选择第一个项目
                template_id = project_payload.get("template_id")
                business_id = project_payload.get("business_id")
                self.business_id = business_id
                project_url = project_payload.get("wy_url") if template_id == "104" and project_payload.get("wy_flag") else f"https://estudy.enaea.edu.cn/web/{template_id}/{business_id}/home"
                new_project_info = await self._complete_project_info(self.business_id, template_id)
                project_payload.update(new_project_info.get("data"))
                self.target_project_info = project_payload
                break
            if project_url:
                break

        return project_url

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3), wait=wait_fixed(3))
    async def _complete_project_info(self, business_id, template_id):
        url = f"https://apaas.grtcloud.net/api/grt-user-center-service/user/business/v1/composite?business_id={business_id}&template_id={template_id}"
        self.headers["cookie"] = f"Authorization={self.headers['authorization']}"
        self.headers["referer"] = "https://estudy.enaea.edu.cn/"
        response = await self.context.request.get(url, headers=self.headers)
        if response.status == 200:
            return await response.json()
        else:
            raise BusinessException(f"获取项目信息失败，状态码：{response.status}")

    async def _enter_first_unfinished_course_study(self):
        # 目前默认学习第一个课程，没有可配置的选项
        target_item = None
        assess_items = await self.get_elems_with_wait_by_xpath(10, "//div[@class='kc']")
        for assess_item in assess_items:
            # 1.排除掉非视频专题，例如：个别是直播答疑（需要人工学习）
            btn_view = await self.get_relative_elem_by_xpath(assess_item, ".//a[@class='btnBig2']")
            href_str = await btn_view.get_attribute("href")
            # https://study.enaea.edu.cn/circleIndexRedirect.do?action=toNewMyClass&type=courseCategory4jwu&circleId=390548&syllabusId=2294032&isRequired=false&studentProgress=0
            parsed = urlparse(href_str)
            qs = parse_qs(parsed.query)
            course_type = qs["type"][0]
            if "liveCourse" in course_type:
                self.logger.error("直播答疑专题，需要人工学习！跳过该专题！")
                continue

            # 2.排除掉时间已满足的专题
            el_assess_desc = await self.get_relative_elem_by_xpath(assess_item, "./strong")
            res = re.search(r'考核要求：(\d+)分钟.*已完成：(\d+)分钟', await el_assess_desc.text_content())
            if not res:
                continue
            require_min = int(res.group(1))
            finish_min = int(res.group(2))
            if require_min > 0 and require_min > finish_min:
                # 未完成
                target_item = assess_item
                break

        if not target_item:
            return False, "所有课程已完成！"

        # view_button = await self.get_elem_with_wait_by_xpath(10, f"(//div[@class='kc']//a[@class='btnBig2'])[1]")
        btn_view = await self.get_relative_elem_by_xpath(target_item, ".//a[@class='btnBig2']")
        href_str = await btn_view.get_attribute("href")
        # https://study.enaea.edu.cn/circleIndexRedirect.do?action=toNewMyClass&type=courseCategory4jwu&circleId=390548&syllabusId=2294032&isRequired=false&studentProgress=0
        parsed = urlparse(href_str)
        qs = parse_qs(parsed.query)
        syllabus_id = qs["syllabusId"][0]
        circle_id = qs["circleId"][0]
        course_type = qs["type"][0]

        parsed = urlparse(await self.get_current_url())
        # scheme=https  netloc=study.enaea.edu.cn
        base_url = f"{parsed.scheme}://{parsed.netloc}"
        # 获取用户信息
        _, inner_username = await self.get_username()
        self.study_params = StudyParam(inner_username=inner_username, circle_id=circle_id, syllabus_id=syllabus_id,
                                       type=course_type)
        # target_score, finished_score = await self._get_progress_v2(self.study_params.get("inner_username"), self.study_params.get("circle_id"), self.study_params.get("syllabus_id"), self.study_params.get("type"))
        target_score, finished_score = await self._get_progress_v2(f"{base_url}/{href_str}", self.study_params)
        if finished_score >= target_score:
            self.logger.info(f"已学完，目标时间：{target_score}，完成时间：{finished_score}！")  # 已学完，达到目标时间：100.0！
            return False, "已学完"

        while True:
            course_url, course_name = await self._get_first_course_info(self.study_params)
            if course_url:
                await self.open_in_new_window(course_url)
                self.course_page = self.get_current_page()
                await self.close_other_windows(self.course_page)
                self.set_output_data("course_page", self.course_page)
                break
            else:
                # 没有课程，可能要选课
                if not await self._choose_optional_course(circle_id, syllabus_id):
                    self.logger.error("课程时间未满足，且没有可选的课程，人工介入检查！")
                    return False, "无可学的课程！"
        return True, course_name

    async def _get_first_course_info(self, study_params: StudyParam):
        course_info = await self._get_unfinished_course_info_study(study_params.inner_username, study_params.circle_id,
                                                                   study_params.syllabus_id,
                                                                   action="getMyClassForCategory4jwu" if study_params.type == "courseCategory4jwu" else "getMyClass")
        # if not course_info["result"]["list"]:
        #     course_info = await self._get_unfinished_course_info_study(study_params.inner_username, study_params.circle_id, study_params.   syllabus_id, action="getMyClassForCategory4jwu")
        url = None
        course_name = None
        for course_info in course_info["result"]["list"]:
            course_detail = course_info["studyCenterDTO"]
            if course_detail['coursecontentType'] != 'video':
                self.logger.error(f"课程【{course_detail['courseTitle']}】为非视频，需要人工学习！")
                continue
            else:
                content_id = str(course_detail["courseId"])
                course_name = course_detail["courseTitle"]
                url = r"https://study.enaea.edu.cn/viewerforccvideo.do?courseId=%s&circleId=%s" % (
                    content_id, study_params.circle_id)
                break
                # name = course_info_json_obj["result"]["list"][0]["studyCenterDTO"]["courseTitle"]
        return url, course_name

    async def _enter_first_unfinished_course_estudy(self):
        """
        新版的进入第一个未完成的课程
        estudy.enaea.edu.cn进入第一个未完成的课程
        :return:
        """
        # 获取学习信息，必修课+选修课
        module_infos = await self.get_module_infos(template_id=self.target_project_info["template_id"],
                                                   plan_id=self.target_project_info["plan_id"],
                                                   business_id=self.business_id,
                                                   version=self.target_project_info["version"])
        target_course = None
        target_module = None
        for target_module in module_infos:
            courses = await self.fetch_all_non_completed_courses_required(business_id=self.business_id,
                                                                          plan_id=target_module["plan_id"],
                                                                          activity_id=target_module["activity_id"],
                                                                          version=target_module["version"],
                                                                          template_id=self.target_project_info[
                                                                              "template_id"])

            if not courses:
                courses = await self.fetch_all_non_completed_courses_elective(business_id=self.business_id,
                                                                              plan_id=target_module["plan_id"],
                                                                              activity_id=target_module["activity_id"],
                                                                              version=target_module["version"],
                                                                              template_id=self.target_project_info[
                                                                                  "template_id"])

            if courses:
                target_course = courses[0]
                break

        if not target_course:
            self.logger.info("所有课程已完成！")
            return False, "所有课程已完成！"

        if "必修课" in target_module["name"]:
            path_name = "requiredCourse"
        else:
            path_name = " electiveCourses"

        course_url_tmpl = self.estudy_course_url_tmpl % (
            target_module['activity_id'], target_module['plan_id'], target_module['version'], path_name,
            self.target_project_info['business_id'], self.target_project_info['template_id'],
            target_course['course_id'], self.target_project_info['business_id'])
        await self.open_in_new_window(course_url_tmpl)
        self.course_page = self.get_current_page()
        return True, target_course["course_name"]

    async def wait_for_project_info(self, timeout=20):
        """
        等待project_info不为空
        :return:
        """
        while timeout > 0:
            if self.all_projects:
                return True
            await asyncio.sleep(1)
            timeout -= 1
        return False

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(3))
    async def _get_unfinished_projects(self) -> list:
        """
        获取未完成的项目
        返回未完成的项目列表
        :return:
        """
        projects = []
        url = "https://study.enaea.edu.cn/assessment.do?action=getMyCircleCourses&start=0&limit=3&isFinished=false&_%d" % int(
            time.time() * 1000)
        # "action=getMyCircleCourses&start=0&limit=3&isFinished=false&_=1686883890774"
        headers = {"cookie": await self.cookie_to_str()}
        try:
            resp = await self.context.request.get(url=url, headers=headers)
        except Exception as e:
            self.logger.exception("获取项目信息失败！")
            raise e
        else:
            resp_json_obj = await resp.json()
            items = resp_json_obj["result"]["list"]
            if items is not None and len(items) > 0:
                for item in items:
                    projects.append((item["circleId"], item["clusterName"], item["studyUrl"]))
            return projects

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(3))
    async def get_module_infos(self, template_id: str,
                               plan_id: str,
                               business_id: str,
                               version: str,
                               learning_method: str = "1",
                               timeout: int = 10) -> List[Dict]:
        """
        获取模块信息
        返回必修课+选修课的两个模块的信息
        :param template_id:
        :param plan_id:
        :param business_id:
        :param version:
        :param learning_method:
        :param timeout:
        :return:
        """
        url = "https://apaas.grtcloud.net/api/grt-user-center-service/user/plan-tree/v1"
        params = {
            "template_id": template_id,
            "plan_id": plan_id,
            "business_id": business_id,
            "version": version,
            "learning_method": learning_method
        }
        self.headers["cookie"] = f"Authorization={self.headers['authorization']}"
        self.headers["referer"] = "https://estudy.enaea.edu.cn/"
        try:
            resp = await self.context.request.get(url, params=params, headers=self.headers, timeout=timeout * 1000)
        except Exception:
            self.logger.exception("获取项目信息失败！")
            raise

        json_data = await resp.json()
        if not json_data.get("success") or json_data.get("code") != "00000":
            raise BusinessException("获取项目信息失败！返回报文异常：%s" % json_data.get("message"))

        result = []
        for item in json_data.get("data", []):
            di = item.get("data", {})
            if di.get("activity_type") == 1 and di.get("is_finish") == 0:
                result.append({
                    "activity_id": di.get("activity_id"),
                    "plan_id": di.get("plan_id"),
                    "version": di.get("version"),
                    "setting_count": di.get("setting_count"),
                    "name": di.get("name"),
                    "rate": di.get("rate"),
                    "is_finish": di.get("is_finish")
                })
        return result

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(3))
    async def fetch_all_non_completed_courses_required(self,
                                                       business_id: str,
                                                       plan_id: str,
                                                       activity_id: str,
                                                       version: str,
                                                       template_id: str = "104",
                                                       page_size: int = 12
                                                       ) -> List[Dict[str, Any]]:
        """
        翻页获取接口全部数据，并只保留 rate != 100 的课程对象

        :param business_id: 业务id
        :param plan_id: 计划id
        :param activity_id: 活动id
        :param version: 版本号
        :param template_id: 模板id，默认104
        :param page_size: 每页大小，默认12
        :return: 所有页中 rate != 100 的 course_list 对象合并结果
        """
        url = "https://apaas.grtcloud.net/api/grt-user-center-service/user/teaching-item/course/v2"
        self.headers["cookie"] = await self.cookie_to_str()
        self.headers["referer"] = "https://estudy.enaea.edu.cn/"
        base_payload = {
            "template_id": template_id,
            "business_id": business_id,
            "plan_id": plan_id,
            "activity_id": activity_id,
            "version": version,
            "level_id": None,
            "status": "",
            "point_id": "",
            "module_id": "",
            "page_num": 1,
            "page_size": page_size
        }

        all_courses = []
        try:
            resp = await self.context.request.post(url, data=base_payload, headers=self.headers, timeout=30 * 1000)
        except Exception:
            self.logger.exception("获取必须or选修的课程失败！")
            raise

        json_resp = await resp.json()

        if not json_resp.get("success"):
            raise Exception(f"接口请求失败: {json_resp.get('msg')}, code:{json_resp.get('code')}")

        page_data = json_resp.get("data", [])

        for module in page_data:
            for course in module.get("course_list", []):
                if course.get("courseware_type") == 0 and course.get("rate") != 100:
                    all_courses.append(course)

        # 该接口翻页无效，都会获取到全部数据
        # page_num = 1
        #
        # while True:
        #     payload = base_payload.copy()
        #     payload["page_num"] = page_num
        #
        #     resp = await self.context.request.post(url, data=payload, headers=self.headers, timeout=30*1000)
        #     json_resp = await resp.json()
        #
        #     if not json_resp.get("success"):
        #         raise BusinessException(f"接口请求失败: {json_resp.get('msg')}, code:{json_resp.get('code')}")
        #
        #     page_data = json_resp.get("data", [])
        #     if not page_data:
        #         break
        #
        #     for module in page_data:
        #         for course in module.get("course_list", []):
        #             if course.get("courseware_type") == 0 and course.get("rate") != 100:
        #                 all_courses.append(course)
        #
        #     page_num += 1

        return all_courses

    async def fetch_all_non_completed_courses_elective(self,
                                                       business_id: str,
                                                       plan_id: str,
                                                       activity_id: str,
                                                       version: str,
                                                       template_id: str = "104",
                                                       page_size: int = 12
                                                       ) -> List[Dict[str, Any]]:
        records = await self._fetch_all_non_completed_courses_elective(business_id, plan_id, activity_id, version, 2,
                                                                       template_id, page_size)
        if not records:
            records = await self._fetch_all_non_completed_courses_elective(business_id, plan_id, activity_id, version,
                                                                           1, template_id, page_size)
        return records

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(3))
    async def _fetch_all_non_completed_courses_elective(self,
                                                        business_id: str,
                                                        plan_id: str,
                                                        activity_id: str,
                                                        version: str,
                                                        status: int = 2,
                                                        template_id: str = "104",
                                                        page_size: int = 12
                                                        ) -> List[Dict[str, Any]]:
        """
        翻页获取接口全部数据，并只保留 rate != 100 的课程对象

        :param business_id: 业务id
        :param plan_id: 计划id
        :param activity_id: 活动id
        :param version: 版本号
        :param status: 状态。1-学习中；2-未开始
        :param template_id: 模板id，默认104
        :param page_size: 每页大小，默认12
        :return: 所有页中 rate != 100 的 course_list 对象合并结果
        """
        url = "https://apaas.grtcloud.net/api/grt-user-center-service/user/teaching-item/elective"
        self.headers["cookie"] = await self.cookie_to_str()
        self.headers["referer"] = "https://estudy.enaea.edu.cn/"
        base_payload = {
            "template_id": template_id,
            "business_id": business_id,
            "category_id": "",
            "plan_id": plan_id,
            "activity_id": activity_id,
            "version": version,
            "status": status,
            "module_id": "",
            "page_num": 1,
            "page_size": page_size
        }

        all_courses = []
        # try:
        #     resp = await self.context.request.post(url, data=base_payload, headers=self.headers, timeout=30*1000)
        # except Exception:
        #     self.logger.exception("获取必须or选修的课程失败！")
        #     raise
        #
        # json_resp = await resp.json()
        #
        # if not json_resp.get("success"):
        #     raise Exception(f"接口请求失败: {json_resp.get('msg')}, code:{json_resp.get('code')}")
        #
        # page_data = json_resp.get("data", [])
        #
        # for course in page_data:
        #     if course.get("courseware_type") == 0 and course.get("rate") != 100:
        #         all_courses.append(course)

        # 该接口翻页无效，都会获取到全部数据
        page_num = 1

        while True:
            payload = base_payload.copy()
            payload["page_num"] = page_num
            try:
                resp = await self.context.request.post(url, data=payload, headers=self.headers, timeout=30 * 1000)
            except Exception:
                self.logger.exception("获取必须or选修的课程失败！")
                raise
            json_resp = await resp.json()

            if not json_resp.get("success"):
                raise Exception(f"接口请求失败: {json_resp.get('msg')}, code:{json_resp.get('code')}")

            page_data = json_resp.get("data", [])
            if not page_data:
                break

            for course in page_data:
                if course.get("courseware_type") == 0 and course.get("rate") != 100:
                    all_courses.append(course)

            page_num += 1

            await asyncio.sleep(random.uniform(0.5, 3))

        return all_courses

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(3))
    async def get_username(self) -> tuple:
        """
        获取用户名
        :return:tuple，第一个用户真名，第二个内部用户名标识
        """
        user_agent = await self.user_agent()
        try:
            user_info = await self.context.request.get(
                url="https://study.enaea.edu.cn/getCurrentUser.do?_%d" % int(time.time() * 1000),
                headers={"User-Agent": user_agent,
                         "Cookie": await self.cookie_to_str()})
        except:
            self.logger.exception("获取用户信息失败！")
            raise

        user_info_json_obj = await user_info.json()
        user_realname = user_info_json_obj["screenName"]
        inner_username = user_info_json_obj["username"]
        user_realname = user_realname if user_realname is not None else ""
        inner_username = inner_username if inner_username is not None else ""
        return user_realname, inner_username

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(3))
    async def _get_unfinished_course_info_study(self, inner_username, circle_id, syllabus_id, action="getMyClass"):
        ts = int(time.time() * 1000)
        url = r"https://study.enaea.edu.cn/circleIndex.do?action=%s&start=0&limit=100&isCompleted=false&circleId=%s&syllabusId=%s&categoryRemark=all&_=%d" % (
        action,
        circle_id, syllabus_id, ts)
        # url = r"https://study.enaea.edu.cn/circleIndex.do?action=getMyClass&start=0&limit=20&isCompleted=false&circleId=191614&syllabusId=1141868&categoryRemark=all&_=1686224205765&_=1686224205765"
        # action=getMyClass&start=0&limit=20&isCompleted=false&circleId=191614&syllabusId=1141868&categoryRemark=all&_=1686131626914
        user_agent = await self.user_agent()
        try:
            cookie_str = (await self.cookie_to_str()) + (
                    ";hasUnReadAnwser=false; hasUnreadNotice=false; hasUnreadPlan=false; hasUnreadBrief=false; hasUnreadManual=false; LOGIN_USER_NAME=%s" % inner_username)
            unfinished_course_resp = await self.context.request.get(url=url, headers={"User-Agent": user_agent,
                                                                                      "Cookie": cookie_str})
            return await unfinished_course_resp.json()
        except Exception as e:
            self.logger.exception("获取未读完的课程失败！")
            raise

    # async def _get_progress_v2(self, inner_username, circle_id, syllabus_id, type):
    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3),
           wait=wait_fixed(3))
    async def _get_progress_v2(self, url, study_params: StudyParam):
        # url = f"https://study.enaea.edu.cn/circleIndexRedirect.do?action=toNewMyClass&type={type}&circleId={circle_id}&syllabusId={syllabus_id}"
        user_agent = await self.user_agent()
        # user_agent = r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
        try:
            cookie_str = (
                         await self.cookie_to_str()) + ";hasUnReadAnwser=false; hasUnreadNotice=false; hasUnreadPlan=false; hasUnreadBrief=false; hasUnreadManual=false; LOGIN_USER_NAME=%s" % study_params.inner_username
            response = await self.context.request.get(url=url, headers={"User-Agent": user_agent, "Cookie": cookie_str})
            # 解析html
            tree = etree.HTML(await response.text())
            texts = tree.xpath("//p[@class='require']/text()")
            target_score = texts[0].split("：")[1].replace("分钟", "")
            finished_score = texts[1].split("：")[1].replace("分钟", "")
            return int(target_score), int(finished_score)
        except:
            self.logger.exception("获取课程进度失败，原因：")
            raise

    async def _choose_optional_course(self, circle_id, syllabus_id):
        ret = True
        url = f"https://study.enaea.edu.cn/circleIndexRedirect.do?action=toSelectCourse&circleId={circle_id}&organizationId=7&syllabusId={syllabus_id}"
        await self.open_in_new_window(url)

        while True:
            courses = await self.get_elems_with_wait_by_xpath(10, "//label[@class='course-item' and not(@title)]")
            if not courses:
                # 翻页
                btn_next_page = await self.get_elem_with_wait_by_css(10, "a.next.paginate_button", visible=False)
                if not await btn_next_page.is_enabled():
                    self.logger.error("没有下一页的课程了，无法选择课程！")
                    ret = False
                    break
                await self.js_click(btn_next_page)
            else:
                for course in courses:
                    if not await course.is_visible():
                        await course.scroll_into_view_if_needed()
                    await course.click()
                    await asyncio.sleep(0.4)

                btn_submit = await self.get_elem_with_wait_by_xpath(10, "//a[@class='submit-btn']")
                await self.js_click(btn_submit)
                await asyncio.sleep(0.4)
                confirm_btn = await self.get_elem_with_wait_by_xpath(3,
                                                                     "//td[@class='td-content']//button[text()='确定']")
                if confirm_btn:
                    await self.js_click(confirm_btn)

                # 选择一页即可，后续课程不足再选一页
                break

        return ret
