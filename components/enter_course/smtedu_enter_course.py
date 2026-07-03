import asyncio
import decimal
from dataclasses import dataclass, field
from typing import Tuple

from playwright.async_api import Page

from src.frame.base import BaseEnterCourseTaskNode
from src.frame.common.exceptions import BusinessException


@dataclass(init=False)
class SMTEDUEnterCourse(BaseEnterCourseTaskNode):
    # 课程信息，课程名称：{duration:课程时长，id:课程ID}
    course_info: dict = field(default_factory=dict)
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
    # 培训信息
    train_info: dict = field(default_factory=dict)
    # 培训是否需要报名
    is_need_sign_in: bool = False
    # 学时修正偏差值
    time_fix_deviation: decimal.Decimal = decimal.Decimal("0.3")

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        # 切换到中小学智慧平台
        self.course_info = {}
        self.train_info = {}
        self.is_need_sign_in = self.node_config.get("node_params", {}).get("is_need_sign_in", False)
        self.project_id = await self.get_project_id()
        if not self.project_id:
            return False, "未找到项目ID"

        self.user_id = await self._get_user_id()
        project_url = self.PROJECT_URL_TMPL % self.project_id
        await self.open_in_new_window(project_url)
        await asyncio.sleep(3)
        await self.switch_to_window_by_url_key(project_url)
        self.course_page_window_handler = self.get_current_page()
        await self.close_other_windows(self.course_page_window_handler)
        # 获取培训信息
        """
        {
    "train": {
        "id": "d5ad802b-c9d4-4743-a9ac-28d171dc1ca1",
        "project_id": 500,
        "title": "2026年莆田市直中小学教师岗位全员继续教育远程网络培训（50学时）",
        "description": "",
        "cover_url": "https://s-file-1.ykt.cbern.com.cn/teach/train/500/培训封面1200x704.jpg",
        "cover": "7fada699-bc7b-4ab5-b810-a5acd25ad247",
        "attention": "",
        "sort_number": 101,
        "is_top": false,
        "sort_time": "2026-05-27T18:14:17.000+0800",
        "enabled": true,
        "enabled_time": null,
        "disabled_time": null,
        "create_time": "2026-05-25T14:08:51.000+0800",
        "create_user": 452315580589,
        "visible_config": 0,
        "study_time_limit_type": 0,
        "study_start_time": "2026-06-15T00:00:00.000+0800",
        "study_end_time": "2026-08-31T23:59:59.000+0800",
        "study_days": null,
        "context_id": "library:d145b19a-eecc-41f2-a6cc-6c4c63ae2bfb",
        "allow_study_num": 0,
        "provider": "",
        "max_period": 50.0,
        "action_rule": "https://elearning-train-gateway.ykt.eduyun.cn/v3/spi/trains/action_rules?current_train_id=d5ad802b-c9d4-4743-a9ac-28d171dc1ca1&action=${action}&rule_json=true&with_zz=true",
        "train_mode": 0,
        "period_conversion_ratio": 2700
    },
    "train_operation": {
        "id": "d5ad802b-c9d4-4743-a9ac-28d171dc1ca1",
        "tenant_id": 730285,
        "short_name": "2026fjptjswlpx",
        "banner_web": "c8fdc93b-d163-4bfe-958f-6c7a52b8735f",
        "banner_web_url": "https://s-file-2.ykt.cbern.com.cn/teach/train/500/培训主页banner-web更新.jpg",
        "banner_mobile": "5b6fa5e4-ebb8-4362-b127-ec8b9a5fd978",
        "banner_mobile_url": "https://s-file-2.ykt.cbern.com.cn/teach/train/500/培训专题页banner图-APP 750x314.jpg",
        "attention": "",
        "tutorial": "<p style=\"text-align:center;\">\n\t<br />\n</p>\n<p style=\"text-align:center;color:rgba(0, 0, 0, 0.85);font-family:-apple-system, BlinkMacSystemFont, &quot;font-size:16px;text-indent:2em;\">\n\t<img src=\"https://s-file-2.ykt.cbern.com.cn/auxo_channel_api/download[1]_1701346054748.png\" alt=\"\" width=\"151\" height=\"36\" title=\"\" align=\"\" style=\"height:36px;\" /> \n</p>\n<p class=\"line-dashed\" style=\"color:rgba(0, 0, 0, 0.85);font-size:16px;font-family:-apple-system, BlinkMacSystemFont;text-indent:2em;\">\n\t<br />\n</p>\n<p class=\"MsoNormal\" style=\"text-indent:21pt;\">\n\t<span> </span> \n</p>\n<p class=\"MsoNormal\" style=\"text-indent:21pt;\">\n\t您好！欢迎参加2026年莆田市直中小学教师岗位全员继续教育远程网络培训，本培训仅为莆田市直中小学教师开放。为帮助您尽快了解学习方式，请仔细阅读以下内容。\n</p>\n<p>\n\t<br />\n</p>\n<table cellpadding=\"15\" cellspacing=\"0\" border=\"0\" class=\"ke-zeroborder\" bordercolor=\"#FFFFFF\" style=\"font-family:-apple-system, BlinkMacSystemFont, &quot;width:621px;\">\n\t<tbody>\n\t\t<tr>\n\t\t\t<td>\n\t\t\t\t<span><span><span><img src=\"https://s-file-1.ykt.cbern.com.cn/teach/train/500/1.注册.png\" alt=\"\" /><br />\n</span> </span> </span> \n\t\t\t</td>\n\t\t\t<td>\n\t\t\t\t<p>\n\t\t\t\t\t<span><span><span>未在国家中小学智慧教育平台注册的教师，请按照平台要求，填写完整个人真实信息，完成注册。</span> </span> </span> \n\t\t\t\t</p>\n\t\t\t</td>\n\t\t</tr>\n\t\t<tr>\n\t\t\t<td>\n\t\t\t\t<span><span><span><img src=\"https://s-file-1.ykt.cbern.com.cn/teach/train/500/2.自主选学.png\" alt=\"\" /><br />\n</span> </span> </span> \n\t\t\t</td>\n\t\t\t<td>\n\t\t\t\t<p>\n\t\t\t\t\t<span><span><span><span>本专题分为公共课程、专业课程、实践案例三个模块，每个模块提供多个学习资源，教师可以按需选学。</span></span> </span> </span> \n\t\t\t\t</p>\n\t\t\t</td>\n\t\t</tr>\n\t\t<tr>\n\t\t\t<td>\n\t\t\t\t<span><span><span><img src=\"https://s-file-1.ykt.cbern.com.cn/teach/train/500/3.提交测评.png\" alt=\"\" /><br />\n</span> </span> </span> \n\t\t\t</td>\n\t\t\t<td>\n\t\t\t\t<p>\n\t\t\t\t\t<span><span><span>完成三个模块学习后，要参加考试测评，测评60分及以上为合格。</span></span></span> \n\t\t\t\t</p>\n\t\t\t</td>\n\t\t</tr>\n\t\t<tr>\n\t\t\t<td>\n\t\t\t\t<span><span><span><img src=\"https://s-file-1.ykt.cbern.com.cn/teach/train/500/4.学时认定.png\" alt=\"\" /><br />\n</span> </span> </span> \n\t\t\t</td>\n\t\t\t<td>\n\t\t\t\t<span><span><span><span>完成本专题学习平台为教师认定50学时。其中公共课程认定16学时、专业课程认定14学时、实践案例认定20学时。必须完整观看完所选视频，才可获得该资源对应的认定学时。</span><br />\n</span> </span> </span> \n\t\t\t</td>\n\t\t</tr>\n\t\t<tr>\n\t\t\t<td>\n\t\t\t\t<span><span><span><img src=\"https://s-file-1.ykt.cbern.com.cn/teach/train/500/5.获取电子证书.png\" alt=\"\" /><br />\n</span> </span> </span> \n\t\t\t</td>\n\t\t\t<td>\n\t\t\t\t<span><span><span>研修截止时间为2026年8月31日。从8月31日起，平台将为获得50个认定学时，且考试测评成绩合格并通过学校管理员审核认证后的教师提供电子学习证书。<br />\n</span> </span> </span> \n\t\t\t</td>\n\t\t</tr>\n\t</tbody>\n</table>",
        "tutorial_mobile": "<p style=\"text-align:center;\">\n\t<img src=\"https://s-file-2.ykt.cbern.com.cn/auxo_channel_api/download[1]_1701346054748.png\" alt=\"\" width=\"151\" height=\"36\" title=\"\" align=\"\" style=\"height:36px;\" /> \n</p>\n<p style=\"text-align:center;\">\n\t<br />\n</p>\n<div style=\"font-size:16px;\">\n\t<p class=\"MsoNormal\" style=\"text-indent:21pt;\">\n\t\t您好！欢迎参加2026年莆田市直中小学教师岗位全员继续教育远程网络培训，本培训仅为莆田市直中小学教师开放。为帮助您尽快了解学习方式，请仔细阅读以下内容。\n\t</p>\n</div>\n<p style=\"font-size:16px;\">\n\t<span style=\"font-weight:700;\">1.注册</span><br />\n未在国家中小学智慧教育平台注册的教师，请按照平台要求，填写完整个人真实信息，完成注册。\n</p>\n<p style=\"font-size:16px;\">\n\t<span style=\"font-weight:700;\">2.自主选学</span><br />\n<span>本专题分为公共课程、专业课程、实践案例三个模块，每个模块提供多个学习资源，教师可以按需选学。</span><br />\n<span></span> \n</p>\n<p style=\"font-size:16px;\">\n\t<span style=\"font-weight:700;\">3.提交测评</span><br />\n完成三个模块学习后，要参加考试测评，测评60分及以上为合格。\n</p>\n<p style=\"font-size:16px;\">\n\t<span style=\"font-weight:700;\">4.学时认定</span><br />\n完成本专题学习平台为教师认定50学时。其中公共课程认定16学时、专业课程认定14学时、实践案例认定20学时。必须完整观看完所选视频，才可获得该资源对应的认定学时。\n</p>\n<p style=\"font-size:16px;\">\n\t<span style=\"font-weight:700;\">5.获取电子证书</span><br />\n研修截止时间为2026年8月31日。从8月31日起，平台将为获得50个认定学时，且考试测评成绩合格并通过学校管理员审核认证后的教师提供电子学习证书。\n</p>",
        "affirm_period_show_type": 1,
        "train_type": 1,
        "opt_manual_id": "bbc3d2d3-8ff7-4092-b56a-1aad7dba4ee6",
        "opt_manual_url": "https://s-file-2.ykt.cbern.com.cn/teach/train/500/莆田培训操作手册20260615.pdf",
        "opt_manual_name": "莆田培训操作手册20260615.pdf",
        "opt_manual": "{\"enabled\":\"1\",\"type\":\"3\",\"resource_id\":\"\",\"resource_name\":\"\",\"url\":\"\"}",
        "questionnaire_url": "",
        "train_action_rule_url": "https://elearning-train-gateway.ykt.eduyun.cn/v3/spi/trains/action_rules?current_train_id=%s&action=${action}&rule_json=true&with_zz=true",
        "train_course_action_rule_url": "https://elearning-train-gateway.ykt.eduyun.cn/v3/spi/trains/%s/course/bs_action_rules?action=${action}&course_id=%s",
        "train_work_action_rule_url": "",
        "dynamics_config": {
            "question_vote": {
                "url": "",
                "enable": "0"
            },
            "study_dynamics": {
                "enable": "0",
                "library_ids": ","
            },
            "question_collect": {
                "url": "",
                "enable": "0"
            }
        },
        "self_tab_config": {
            "url": "",
            "enable": "0",
            "web_picture_url": "",
            "mobile_picture_url": ""
        },
        "category_info": "{\"channel_code\":\"localChannel\",\"data\":{\"menu_name\":\"福建\",\"code\":\"fj\",\"navi_image\":\"https://bdcs-file-1.ykt.cbern.com.cn/e_teacher_studio/area_sites/covers/2024/地区=福建_1726841538272.png\",\"domain\":\"fj\",\"zone\":\"350000\",\"name\":\"福建频道\",\"site_type\":0,\"site_level\":1,\"site_rela_id\":594033008559,\"site_rela_path\":\"594033008559\",\"home_channel_id\":\"21ad97ec-2c6a-4fa3-b03d-8911748fe4a6\",\"sort_number\":24,\"h5_url\":null,\"new_recommend_on\":false,\"new_recommend_start_time\":null,\"new_recommend_end_time\":null,\"site_rela_parent\":\"\"}}",
        "area_specific": 594033008945,
        "allow_proxy_sign": false
    },
    "train_phase_list": [
        {
            "id": "47fdbb70-8faa-4dd3-ac3d-a965fd12cbaf",
            "title": "实践案例",
            "attention": "",
            "train_id": "d5ad802b-c9d4-4743-a9ac-28d171dc1ca1",
            "period_limit": 54000,
            "period_hour_limit": 20.0,
            "total_period": 54000,
            "total_period_hour": 20.0,
            "sort_number": 3
        },
        {
            "id": "b2963a96-5166-4230-95e5-d3e40efeb882",
            "title": "专业课程",
            "attention": "",
            "train_id": "d5ad802b-c9d4-4743-a9ac-28d171dc1ca1",
            "period_limit": 37800,
            "period_hour_limit": 14.0,
            "total_period": 37800,
            "total_period_hour": 14.0,
            "sort_number": 2
        },
        {
            "id": "d1852e6f-e351-4cf9-9cf6-a532a9bf51b1",
            "title": "公共课程",
            "attention": "",
            "train_id": "d5ad802b-c9d4-4743-a9ac-28d171dc1ca1",
            "period_limit": 43200,
            "period_hour_limit": 16.0,
            "total_period": 43200,
            "total_period_hour": 16.0,
            "sort_number": 1
        }
    ],
    "pass_rule": {
        "period_rule_type": "$stipulated",
        "overall_pass": false,
        "exam_rule_type": "$all"
    },
    "train_course_ids": [
        "b9794def-9e0e-40db-b696-0eee39584db5",
        "2b23d41c-a9d1-4048-8a38-218f0f3479e3",
        "01743cf9-7249-471e-9c51-fc126030f0c1",
        "6e258c3f-b6c2-4d56-b48a-8a83ed0ef9f7",
        "0d79320a-8f57-408e-b40e-26b86a8c8ce7",
        "c7523296-e588-4c12-a6e4-32dfe2d6a892",
        "294c8ef4-0c8d-4aa6-afc2-675f0f6c321f",
        "fb17aee0-5eb3-4507-8da9-128131a981ec",
        "1c3c7fdc-d1be-43c1-9568-71d1d8660b94",
        "a3969644-06a5-4390-80da-80d63eacd77b",
        "29fdc9a3-b911-4a16-bdb4-042783b34ace",
        "f3904b96-3c95-46f9-b4fe-549e778a7553",
        "b54b5fb5-d819-473e-aada-73a6bee166ff",
        "39078ca9-2336-42ec-b6e5-350ca18c1ace",
        "8f07e1db-9a83-4c1e-8476-1c7830cd84aa"
    ],
    "train_exam_ids": [
        "0b6ae01e-0ab1-493f-a648-2c11d7f74795"
    ],
    "train_work_ids": []
}"""
        self.train_info = await self._get_train_info()
        # 报名
        if self.is_need_sign_in:
            await self._sign_in()
        return True, ""

    async def enter_course(self) -> Tuple[bool, str]:
        await self.init_course_info()
        target_course_url, course_info = await self._get_target_course()
        if not target_course_url:
            self.logger.info("没有找到未完成的课程，课程结束")
            return False, "已学完"
        else:
            await self.open_in_new_window(target_course_url)
            self.video_page_window_handler = self.get_current_page()
            self.set_output_data("video_page", self.video_page_window_handler)
            self.set_output_data("course_page", self.course_page_window_handler)
            self.set_output_data("course_info", course_info)
            self.set_output_data("train_id", self.train_info.get("train").get("id"))
            self.set_output_data("phase_period_hour_limit", self._get_phase_period_hour_limit(course_info["phase_id"]))
            self.set_output_data("user_id", self.user_id)
            # self._trigger_first_content()
            return True, self.course_name

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        await self.close_other_windows(self.course_page_window_handler)
        return True, ""

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
        await self._get_course_info()

    async def _get_user_id(self):
        return await self.execute_js("localStorage.getItem('_user_id');")

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

        try:
            course_info = await self.context.request.get(url=url, headers=headers)
        except:
            self.logger.error("获取用户信息失败")
            raise
        else:
            course_info_obj = await course_info.json()
            for ci in course_info_obj:
                phase_id = ci["phase_id"]
                if phase_id not in self.course_info:
                    self.course_info[phase_id] = {}
                course_name = ci["title"].strip()

                if course_name not in self.course_info[phase_id]:
                    self.course_info[phase_id][course_name] = {}

                self.course_info[phase_id][course_name]["name"] = course_name
                self.course_info[phase_id][course_name]["id"] = ci["course_id"]
                self.course_info[phase_id][course_name]["max_period"] = ci["max_period"]
                self.course_info[phase_id][course_name]["finished_period"] = finished_info.get(ci["course_id"], 0.0)
                self.course_info[phase_id][course_name]["total_period"] = ci["total_period"]
                self.course_info[phase_id][course_name]["phase_id"] = phase_id

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
            if decimal.Decimal(finished_info.get(train_phase["id"], "0.0")) < decimal.Decimal(train_phase["period_hour_limit"]) + self.time_fix_deviation:  # 多加0.3学时避免学时不够！
                phase_id = train_phase["id"]
                break
        return phase_id

    async def _get_first_unfinished_course_id(self, phase_id):
        course_info = None
        for course in self.course_info.get(phase_id).values():
            if decimal.Decimal(course["max_period"]) > decimal.Decimal(0):  # 针对有认定的课程
                if decimal.Decimal(course["finished_period"]) < decimal.Decimal(course["max_period"]) + self.time_fix_deviation:
                    # 未完成
                    course_info = course
                    break
            else:  # 没有认定的课程
                if decimal.Decimal(course["finished_period"]) < decimal.Decimal(course["total_period"]) + self.time_fix_deviation:
                    # 未完成
                    course_info = course
                    break

        return course_info

    async def _get_target_course(self):
        phase_id = await self._get_first_unfinished_phase_id()
        if not phase_id:
            self.logger.info("所有课程已完成！")
            return None, None

        course_info = await self._get_first_unfinished_course_id(phase_id)
        if not course_info:
            self.logger.error("异常！课程的学习时间，不够认定的学时！")
            return None, None

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