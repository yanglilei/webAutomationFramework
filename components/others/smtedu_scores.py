import asyncio
import json
from dataclasses import dataclass, field
from typing import Dict

from playwright.async_api import Page

from src.frame.base.base_task_node import BasePYNode


@dataclass(init=False)
class SMTEDUScores(BasePYNode):
    """
    智慧平台获取项目的分数
    必配置参数：
    project_id（项目ID）

    """
    # 项目地址模板
    PROJECT_URL_TMPL = "https://basic.smartedu.cn/training/%s"
    # 培训信息
    train_info: dict = field(default_factory=dict)
    # 课程页面窗口句柄
    course_page_window_handler: Page = None
    project_id: str = ""
    user_id: str = ""
    auth_headers: Dict = field(default_factory=dict)

    async def execute(self, context: Dict) -> bool:
        headers = self.get_prev_output().get("headers")
        self.auth_headers = headers if headers else {}

        # 切换到中小学智慧平台
        self.project_id = await self.get_project_id()
        if not self.project_id:
            self.logger.error("未找到项目ID")
            return False
        project_url = self.PROJECT_URL_TMPL % self.project_id
        await self.open_in_new_window(project_url)
        await asyncio.sleep(3)
        await self.switch_to_window_by_url_key(project_url)
        self.course_page_window_handler = self.get_current_page()
        await self.close_other_windows(self.course_page_window_handler)

        user_info = self.get_prev_output().get("user_info", {})
        if not user_info.get("id"):
            self.user_id = await self._get_user_id()
        else:
            self.user_id = user_info.get("id")

        # 获取培训进度信息
        train_progress = await self._get_train_progress_info()

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
        finished_info = await self._get_finished_info()

        exam_score = None
        train_exam_ids = self.train_info.get("train_exam_ids")
        if not train_exam_ids:
            self.logger.error("没有考试")
        else:
            exam_id = train_exam_ids[0]  # 目前仅获取第一个考试信息
            exam_score = finished_info.get(exam_id, "0")

        score_ = f"完成进度：{train_progress if train_progress else '未报名'}，考试分数：{exam_score}"

        self.logger.info(score_)
        self.user_manager.update_record_by_username(self.username, {5: score_})

        return True

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

    async def _get_user_id(self):
        user_id = await self.execute_js("localStorage.getItem('_X_STAT_EVENT_SESSION_LAST_USER');")
        if not user_id:
            user_info = await self.execute_js("localStorage.getItem('X-EDU-WEB-USER');")
            user_id = json.loads(user_info)["user_id"]
        return user_id

    async def get_project_id(self):
        return self.node_config.get("node_params", {}).get("project_id", "")

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

    async def get_user_info(self):
        url = "https://x-user-profile.ykt.eduyun.cn/v2/teacher/profile"
        headers = {"User-Agent": await self.user_agent(), "Cookies": await self.cookie_to_str()}
        headers.update(self.auth_headers)
        try:
            user_info = await self.context.request.get(url=url, headers=headers)
        except:
            self.logger.error("获取用户信息失败")
            raise
        else:
            return await user_info.json()

    async def train_exams(self):
        """
        [
            {
                "train_id": "d5ad802b-c9d4-4743-a9ac-28d171dc1ca1",
                "exam_id": "0b6ae01e-0ab1-493f-a648-2c11d7f74795",
                "access_rule": "{\"require_hour\":50.0,\"option_hour\":0.0,\"require_effective_hour\":50.0,\"option_effective_hour\":null}",
                "title": "2026年莆田市直中小学教师岗位全员继续教育远程网络培训测评",
                "cover_url": "https://bdcs-file-2.ykt.cbern.com.cn/xedu_cs_online_exam/培训测评封面1200x704_1781243214191.jpg",
                "description": "",
                "begin_time": "2026-06-15T00:00:00.000+0800",
                "end_time": "2026-08-31T23:59:00.000+0800",
                "duration": 1800,
                "total_score": 100.0,
                "passing_score": 60.0,
                "exam_chance": -1,
                "phase_id": null
            }
        ]
        :return:
        """
        url = f"https://s-file-1.ykt.cbern.com.cn/teach/api_static/trains/{self.project_id}/train_exams.json"
        headers = {"User-Agent": await self.user_agent(), "Cookies": await self.cookie_to_str()}
        try:
            exam_info = await self.context.request.get(url=url, headers=headers)
        except:
            self.logger.error("获取用户信息失败")
            raise
        else:
            return await exam_info.json()

    async def _get_train_progress_info(self):
        el_train_progress = await self.get_elem_with_wait_by_css(10, "span.fish-progress-text div div")
        if not el_train_progress:
            return ""
        else:
            await asyncio.sleep(2)
            el_train_progress = await self.get_elem_by_css("span.fish-progress-text div div")
            return await el_train_progress.text_content() if el_train_progress else "获取失败"
