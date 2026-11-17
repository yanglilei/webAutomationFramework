import asyncio
import decimal
import json
from dataclasses import dataclass, field
from datetime import date
from typing import Tuple, Dict, Any

from playwright.async_api import Page

from src.frame.base import BaseEnterCourseTaskNode
from src.frame.common.exceptions import BusinessException
from src.utils import SMTEduSignUtils, RequestMethod


@dataclass(init=False)
class SMTEDUEnterCourseV2(BaseEnterCourseTaskNode):
    """
    智慧平台进入课程
    支持指定课程，适配莆田2026暑假研修，根据日期配置课程
    可配参数：

    必配置参数：
    course_info
    配置参数：course_info:{
      "0825": [
        "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=75035aca-25ec-44c6-95e3-b8a62f48bef6",
        "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=6388a378-559c-4825-b4e3-8889ef455d81",
        "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=4c8dc8cc-b163-41ba-97ee-e77d3a659262",
        "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=af65b4b8-42bf-4e5a-a0a6-7b6035058399"
      ],
      "0826": [
        "https://basic.smartedu.cn/schoolService/detail?contentType=thematic_course&contentId=5f189f27-e5eb-4ba1-85bc-fe2741c38fd5&catalogType=schoolService&subCatalog=kpjy"
      ],
      "0827": {
        "特殊教育": [
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=e0e220cc-f886-4a4a-a522-13db076c77f4"
        ],
        "幼儿": [
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=2e3b6b8d-105a-4331-b6a3-4a980de23d07"
        ],
        "小学、初中": [
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=25d796be-4c1d-484c-ba68-d000dc72f7b2",
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=8f2fb67b-d08a-4aa1-a71c-00c02b69f5b6",
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=4490e502-d0e5-43c9-88c9-3b0c92306fb6"
        ],
        "高中": [
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=91c0dc21-28a0-49f6-9ca3-ab7124d3e95b",
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=1430b8c1-8171-4bb0-9e00-dc3dfabef874",
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=d33e22a7-5165-4067-93bc-48d417b4218c"
        ]
      },
      "0828": {
        "特殊教育": [
          ""
        ],
        "幼儿": [
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=0a23fe85-8201-4461-ab19-e3ed36e27383",
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=de812567-d786-4ecb-bc19-d575e9c4a646",
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=b2282a3d-b8ff-465a-a2c6-ae979fe78c20",
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=fca4bbbf-0bda-4e35-81cf-ebad5bd24c27"
        ],
        "小学、初中": [

        ],
        "高中": [

        ]
      },
      "0829": {
        "特殊教育": [
          ""
        ],
        "幼儿": [
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=48834733-cfff-4e41-a45b-02a80a1711ca",
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=dd0ee471-f694-44d0-ade2-16d8f8994829",
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=d438d28f-eb4f-46f7-aa37-2ac910f856ca",
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=36c0ff89-4f02-48f1-8088-c9da3853a08b",
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=98045102-dfeb-441a-a5a5-16d6433c91ca",
          "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=650cc676-1d02-4221-9eba-5ba54be03c75"
        ],
        "小学、初中": [

        ],
        "高中": [

        ]
      }
    }
    版本：V0.0.1
    """
    project_id: str = ""
    user_id: str = ""
    # 课程页面窗口句柄
    course_page_window_handler: Page = None
    # 视频页面窗口句柄
    video_page_window_handler: Page = None
    # 项目地址模板
    PROJECT_URL_TMPL = "https://basic.smartedu.cn/training/%s"
    # 项目课程信息模板
    SMTEDU_COURSES_TMPL = "smtedu_courses_%s"
    # 课程地址模板
    COURSE_URL_TMPL = "https://basic.smartedu.cn/teacherTraining/courseDetail?courseId=%s"
    # 智慧中小学平台的个人信息页面地址
    PERSONAL_INFO_URL = "https://basic.smartedu.cn/user/myInfo"
    # 培训信息
    train_info: dict = field(default_factory=dict)
    # 培训是否需要报名
    is_need_sign_in: bool = False
    # 学时修正偏差值
    time_fix_deviation: decimal.Decimal = decimal.Decimal("0.3")
    # 认证相关的请求头
    auth_headers: Dict = field(default_factory=dict)

    # 课程信息
    course_info: Dict[str, Any] = field(default_factory=dict)
    # 已经完成的课程url列表
    completed_course_urls: list = field(default_factory=list)
    # 当前的课程url
    course_url: str = ""
    # 学段信息
    grade_section_cn_name: str = ""
    # 学科信息
    subject_cn_name: str = ""

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        # 获取第一个未完成的项目
        self.completed_course_urls = []
        self.course_url = ""

        self.course_info = self.node_config.get("node_params", {}).get("course_info", {})
        if not self.course_info:
            return False, "请配置课程信息！"

        # 获取用户ID，必须在项目的页面中获取
        user_info = self.get_prev_output().get("user_info", {})
        if not user_info.get("id"):
            self.user_id = await self._get_user_id()
        else:
            self.user_id = user_info.get("id")

        # 跳转到智慧中小学平台的个人信息页面
        await self.load_url(self.PERSONAL_INFO_URL)
        self.course_page_window_handler = self.get_current_page()

        # 获取学段信息
        grade_section = await self._get_grade_section()
        subject_code = await self._get_subject_code()
        teacher_profile = await self._get_teacher_profile()
        self.grade_section_cn_name = grade_section.get(teacher_profile.get("teacher_verify_info").get("grade_section", "")).strip()
        self.subject_cn_name = subject_code.get(teacher_profile.get("teacher_verify_info").get("subject_code", "")).strip()

        return True, ""

    async def enter_course(self) -> Tuple[bool, str]:
        # 获取当天的日期
        # 格式化 MMDD，月份、日期自动补前导零
        mmdd = date.today().strftime("%m%d")
        course_config = self.course_info.get(mmdd)
        if not course_config:
            return False, f"未配置{mmdd}的课程！"

        course_urls = []
        if isinstance(course_config, dict):
            if mmdd == "0829":
                course_urls = await self._get_target_urls(course_config)
            else:
                # 根据学段信息获取课程
                for course_key in course_config.keys():
                    if self.grade_section_cn_name in course_key:
                        course_urls = course_config.get(course_key)
                        break
        else:
            course_urls = course_config

        # 课程配置为列表，则选择第一个未完成的课程
        if len(course_urls) < 1:
            self.logger.error("未配置课程！")
            return False, "未配置课程"

        # 选择第一个未完成的url列表
        for course_url in course_urls:
            if course_url not in self.completed_course_urls:
                self.course_url = course_url
                break

        if not self.course_url:
            self.logger.info(f"日期：{mmdd}课程已全部完成！")
            return False, f"日期：{mmdd}课程已全部完成！"

        await self.open_in_new_window(self.course_url, timeout=20, wait_until="networkidle")
        self.video_page_window_handler = self.get_current_page()
        self.set_output_data("video_page", self.video_page_window_handler)
        self.set_output_data("course_page", self.course_page_window_handler)
        self.set_output_data("user_id", self.user_id)
        # self._trigger_first_content()
        return True, self.course_name

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        await self.close_other_windows(self.course_page_window_handler)
        self.completed_course_urls.append(self.course_url)
        return True, ""

    async def _get_target_urls(self, course_config: dict):
        return course_config.get(self.grade_section_cn_name, {}).get(self.subject_cn_name, [])

    async def get_project_id(self):
        return self.node_config.get("node_params", {}).get("project_id", "")

    async def init_course_info(self):
        # smtedu_courses_2025hjpx = 学习贯彻全国教育大会精神#3;深化教育综合改革#2;推进教育国际交流合作#1
        # courses_config: str = self.node_config.get("node_params", {}).get(self.SMTEDU_COURSES_TMPL % project_id, "")
        # if courses_config:
        #     for course in courses_config.split(";"):
        #         ci = course.split("#")
        #         self.course_info[ci[0]] = {}
        #         self.course_info[ci[0]]["duration"] = float(ci[1])
        #         self.course_info[ci[0]]["name"] = ci[0]
        self.course_info = await self._get_course_info()

    async def _get_user_id(self):
        user_info = await self.execute_js("localStorage.getItem('X-EDU-WEB-USER');")
        # user_id = await self.execute_js("localStorage.getItem('_user_id');")
        return json.loads(user_info)["user_id"]

    async def _get_teacher_profile(self):
        # 获取用户签名信息
        self.user_id, self.mac_key, self.access_token, self.app_id = await SMTEduSignUtils.get_user_sign_params(
            self.execute_js)
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "sdp-app-id": self.app_id}
        return await self.get_user_info()

    async def get_user_info(self):
        # 获取用户信息
        url = r"https://x-user-profile.ykt.eduyun.cn/v2/teacher/profile"
        self._set_authorization(url, RequestMethod.GET)
        try:
            resp = await self.context.request.get(url, headers=self.headers)
            return await resp.json()
        except Exception as e:
            self.logger.exception("获取用户信息失败：")
            return {}

    def _set_authorization(self, url, request_method):
        self.headers["authorization"] = SMTEduSignUtils.gen_authorization(url, self.access_token, self.mac_key,
                                                                          request_method)
    async def _get_grade_section(self):
        url = f"https://bdcs-file-1.ykt.cbern.com.cn/bdxcloud/configs/gradeSection.json"
        headers = {"User-Agent": await self.user_agent(), "Cookies": await self.cookie_to_str()}
        try:
            resp = await self.context.request.get(url=url, headers=headers)
        except:
            self.logger.error("获取学段信息失败")
            raise
        else:
            return await resp.json()

    async def _get_subject_code(self):
        url = f"https://bdcs-file-2.ykt.cbern.com.cn/bdxcloud/configs/subjectCode.json"
        headers = {"User-Agent": await self.user_agent(), "Cookies": await self.cookie_to_str()}
        try:
            resp = await self.context.request.get(url=url, headers=headers)
        except:
            self.logger.error("获取学科信息失败")
            raise
        else:
            return await resp.json()

    async def _get_train_info(self):
        url = f"https://s-file-1.ykt.cbern.com.cn/teach/api_static/trains/{self.project_id}.json"
        headers = {"User-Agent": await self.user_agent(), "Cookies": await self.cookie_to_str()}
        try:
            train_info = await self.context.request.get(url=url, headers=headers)
        except:
            self.logger.error("获取用户信息失败")
            raise
        else:
            return await train_info.json()

    async def _get_finished_info(self):
        # 获取课程的完成情况
        train_id = self.train_info.get("train").get("id")
        url = f"https://elearning-train-api.ykt.eduyun.cn/v1/users/{self.user_id}/trains/{train_id}/courses_period/actions/list"
        headers = {"User-Agent": await self.user_agent(), "Cookies": await self.cookie_to_str()}
        try:
            finished_info = await self.context.request.get(url=url, headers=headers)
        except:
            self.logger.error("获取用户信息失败")
            raise

        return await finished_info.json()

    async def _get_course_info(self):
        finished_info = await self._get_finished_info()
        url = f"https://s-file-1.ykt.cbern.com.cn/teach/api_static/trains/{self.project_id}/train_courses.json"
        headers = {"User-Agent": await self.user_agent(), "Cookies": await self.cookie_to_str()}
        course_info = {}
        try:
            resp = await self.context.request.get(url=url, headers=headers)
        except:
            self.logger.error("获取课程信息失败")
            raise
        else:
            course_info_obj = await resp.json()
            for ci in course_info_obj:
                phase_id = ci["phase_id"]
                if phase_id not in course_info:
                    course_info[phase_id] = {}
                course_name = ci["title"].strip()

                if course_name not in course_info[phase_id]:
                    course_info[phase_id][course_name] = {}

                course_info[phase_id][course_name]["name"] = course_name
                course_info[phase_id][course_name]["id"] = ci["course_id"]
                course_info[phase_id][course_name]["max_period"] = ci["max_period"]
                course_info[phase_id][course_name]["finished_period"] = finished_info.get(ci["course_id"], 0.0)
                course_info[phase_id][course_name]["total_period"] = ci["total_period"]
                course_info[phase_id][course_name]["phase_id"] = phase_id

        return course_info

    def _get_phase_period_hour_limit(self, phase_id):
        ret = None
        for train_phase in self.train_info.get("train_phase_list"):
            if train_phase["id"] == phase_id:
                ret = train_phase["period_hour_limit"]
                break
        return ret

    async def _get_first_unfinished_phase_id(self):
        # 获取第一个未完成的阶段
        phase_id = None
        finished_info = await self._get_finished_info()
        for train_phase in self.train_info.get("train_phase_list"):
            if decimal.Decimal(finished_info.get(train_phase["id"], "0.0")) < decimal.Decimal(
                    train_phase["period_hour_limit"]) + self.time_fix_deviation:  # 多加0.3学时避免学时不够！
                phase_id = train_phase["id"]
                break
        return phase_id

    async def _remove_finished_phase(self):
        # 获取第一个未完成的阶段
        finished_info = await self._get_finished_info()
        for train_phase in self.train_info.get("train_phase_list"):
            if decimal.Decimal(finished_info.get(train_phase["id"], "0.0")) >= decimal.Decimal(
                    train_phase["period_hour_limit"]) + self.time_fix_deviation:  # 多加0.3学时避免学时不够！
                # 排除掉已完成的专题
                self.course_info.pop(train_phase["id"])

    async def _get_target_course_id(self):
        course_info = None
        is_found_target_course = False
        for phases in self.course_info.values():
            for course in phases.values():
                if decimal.Decimal(course["max_period"]) > decimal.Decimal(0):  # 针对有认定的课程
                    if decimal.Decimal(course["finished_period"]) < decimal.Decimal(
                            course["max_period"]) + self.time_fix_deviation:
                        # 未完成
                        course_info = course
                        is_found_target_course = True
                        break
                else:  # 没有认定的课程
                    if decimal.Decimal(course["finished_period"]) < decimal.Decimal(
                            course["total_period"]) + self.time_fix_deviation:
                        # 未完成
                        course_info = course
                        is_found_target_course = True
                        break

            if is_found_target_course:
                break
        return course_info

    async def _get_first_unfinished_course_id(self, phase_id):
        course_info = None
        for course in self.course_info.get(phase_id).values():
            if decimal.Decimal(course["max_period"]) > decimal.Decimal(0):  # 针对有认定的课程
                if decimal.Decimal(course["finished_period"]) < decimal.Decimal(
                        course["max_period"]) + self.time_fix_deviation:
                    # 未完成
                    course_info = course
                    break
            else:  # 没有认定的课程
                if decimal.Decimal(course["finished_period"]) < decimal.Decimal(
                        course["total_period"]) + self.time_fix_deviation:
                    # 未完成
                    course_info = course
                    break

        return course_info

    async def _get_target_course(self):
        # phase_id = await self._get_first_unfinished_phase_id()
        # if not phase_id:
        #     self.logger.info("所有课程已完成！")
        #     return None, None

        # course_info = await self._get_first_unfinished_course_id(phase_id)
        # if not course_info:
        #     self.logger.error("异常！课程的学习时间，不够认定的学时！")
        #     return None, None

        # 优化！有些专题没有在阶段下，所以self.course_info中的key为None，这个时候就不能用就旧方式来（获取第一个未完成的阶段）！
        # 反过来，要排除掉已完成的阶段！
        # 排除掉已完成的阶段，必须要执行该步骤，如果阶段上的学时满足了就不用再学该阶段下的课程！
        await self._remove_finished_phase()
        course_info = await self._get_target_course_id()

        target_course_url = None
        if course_info:
            self.course_name = course_info["name"]
            target_course_url = self.COURSE_URL_TMPL % course_info["id"]
        return target_course_url, course_info

    async def get_every_course_study_progress(self):
        await self.switch_to_window(self.course_page_window_handler)
        await self.refresh()
        await asyncio.sleep(3)
        course_names = list(self.course_info.keys())
        # xpath_expr_list = []
        # for course_name in course_names:
        #     xpath_expr_list.append(Constants.SMTEDU_LEARNED_DURATION_TMPL_XPATH % course_name)
        # xpath_expr = "|".join(xpath_expr_list)
        xpath_expr = "//div[@class='index-module_processC_0VNia'][contains(text(),'已认定')]//span[@class='index-module_processCMy_kp+Ww']"
        courses_learned_time = await self.get_elems_with_wait_by_xpath(20, xpath_expr, visible=False)
        if courses_learned_time:
            return {course_names[i]: float(await courses_learned_time[i].text_content()) for i in
                    range(len(course_names))}
        else:
            await self._sign_in()

    async def _sign_in(self):
        if sign_in_btn := await self.is_elem_visible_by_xpath("//div[text()='立即报名']"):
            self.logger.info("未报名，开始报名")
            await sign_in_btn.click()
            await asyncio.sleep(3)
            if not await self.is_elem_visible_by_xpath("//div[text()='立即报名']"):
                self.logger.info(f"报名成功")
        else:
            self.logger.error("加载课程页面失败")
            raise BusinessException("加载课程页面失败")
