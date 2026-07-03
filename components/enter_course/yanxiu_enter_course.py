import asyncio
import decimal
import re
from dataclasses import field, dataclass
from typing import Tuple, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

from playwright.async_api import Locator, Page
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception

from src.frame.base import BaseEnterCourseTaskNode


@dataclass(init=False)
class YanxiuEnterCourse(BaseEnterCourseTaskNode):
    """
    研修网中project_id, stage_id, tool_id，module_id的关系：1:n:n:n
    """
    # 请求头
    headers: Dict[str, Any] = field(default_factory=dict)
    # 课程页面句柄
    course_page_window_handle: Page = None
    # 课程信息
    stage_subjects: list = field(default_factory=list)
    # url协议
    url_scheme: str = ""
    # 域名+端口
    netloc: str = ""
    project_id: str = ""
    tool_id: str = ""
    stage_id: str = ""
    api_netloc: str = ""
    # 学段ID
    segment_id: str = ""
    # 科目ID
    subject_id: str = ""
    # 学段名称
    segment_name: str = ""
    # 科目名称
    subject_name: str = ""
    # 模块IDS
    modules: list = field(default_factory=list)
    # 最大时间（分钟）
    max_time: int = 600
    # 是否需要修改科目
    need_change_subject: bool = False
    # 用户ID
    user_id: str = ""

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        self.segment_id = ""
        prev_output = self.get_prev_output()
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"}
        # 更新请求头
        self.headers.update(prev_output.get("headers", {}))
        # 获取第一个未完成的项目
        project_name = self.node_config.get("node_params", {}).get("project_name", "")
        if not project_name:
            return False, "请配置项目名称！"
        xpath = f"//div[@class='home-project-pane'][.//div[@class='project-name' and text()='{project_name}']]//div[@class='btn-group']//button"
        btn_enter_project = await self.get_elem_with_wait_by_xpath(10, xpath)
        if not btn_enter_project:
            return False, "没找到课程！"
        # 进入课程
        await btn_enter_project.click()
        await self.wait_for_url_changed(re.compile(r"workspace/\d+/"))
        self.course_page_window_handle = self.get_current_page()
        # 解析url，获取url参数
        self._init_api_params(await self.get_current_url())
        # 获取project_id
        self.project_id = self._get_project_id(await self.get_current_url())
        if not self.project_id:
            return False, "项目ID获取失败！"
        user_info = await self._get_user_info_in_project(self.project_id)
        self.user_id = user_info.get("userId")
        self.subject_id = user_info.get("subjectId")
        ########################################
        # 是否需要修改科目，适配小学道法培训内容
        ########################################
        self.need_change_subject = self.node_config.get("node_params", {}).get("need_change_subject", False)
        if self.need_change_subject:
            # 获取学段和学科信息
            self.stage_subjects = await self._get_subject_info()
            # 获取课程信息
            # 学段 segment
            self.segment_name = self.node_config.get("node_params", {}).get("segment_name")
            # 学科名称
            self.subject_name = self.node_config.get("node_params", {}).get("subject_name")
            # 最大学习时长
            self.max_time = self.node_config.get("node_params", {}).get("max_time", 600)
            if not self.segment_name or not self.subject_name:
                return False, "请配置参数：segment_name、subject_name"

            # 1.获取年段ID和科目ID
            self.segment_id, self.subject_id = self._filter_segment_subject(self.segment_name, self.subject_name)
            if not self.segment_id or not self.subject_id:
                return False, "学段名称或学科名称错误！"

            # 2.修改科目
            if not await self._update_user_info(self.project_id, self.segment_id, self.segment_name, self.subject_id,
                                                self.subject_name):
                # 更新用户信息失败
                self.logger.error(f"修改科目信息失败！{self.segment_name}-{self.subject_name}")
            else:
                self.logger.info(f"修改科目信息成功：{self.segment_name}-{self.subject_name}")

            # 3.进入第一个专题
            await self._enter_first_topic()
            # 等待弹出新窗口
            await asyncio.sleep(2)
            await self.switch_to_window_by_url_key(lambda url: "course/list/member" in url)
            self.course_page_window_handle = self.get_current_page()
            self.tool_id, self.stage_id = self._get_tool_id_and_state_id(await self.get_current_url())
            # 关闭其他窗口
            await self.close_other_windows(self.course_page_window_handle)

        return True, ""

    async def enter_course(self) -> Tuple[bool, str]:
        if self.need_change_subject:  # 修改科目模式，仅有一个专题
            # 获取项目下的模块信息
            self.modules = await self._get_course_modules(self.project_id, self.tool_id)
            if not self.modules:
                return False, "获取模块信息失败！"
            # 利用学习时间来判断和别处不同！一个专题中所有课程的时间总和和配置的时间作比较！
            if await self._is_finished(self.modules, self.project_id, self.tool_id, self.segment_id, self.subject_id):
                return False, f"{self.segment_name}{self.subject_name}-已学完"
        else:  # 普通模式，需要学完多个专题
            unfinished_topics = await self._get_unfinished_topics()
            if not unfinished_topics:
                return False, "已学完"

            # 第一个专题
            self.tool_id, self.stage_id = unfinished_topics[0]
            self.modules = await self._get_course_modules(self.project_id, self.tool_id)
            if not self.modules:
                return False, "获取模块信息失败！"

        course_info = await self._get_one_unfinished_course(self.modules, self.project_id, self.tool_id,
                                                            self.segment_id, self.subject_id)
        if not course_info:
            return False, "已学完"

        course_url = self._course_page_url(course_info.get("id"), self.project_id, self.stage_id, self.tool_id,
                                           course_info.get("course_source_id"))
        await self.open_in_new_window(course_url)
        return True, ""

        # total_score, finished_score = await self._get_topic_score(self.project_id, self.tool_id)
        # if total_score and finished_score >= total_score:
        #     return False, f"已学完"

    def _parse_url(self, page_url):
        parsed_url = urlparse(page_url)
        self.url_scheme = parsed_url.scheme
        self.netloc = parsed_url.netloc
        netloc_segs = self.netloc.split(".")
        self.api_netloc = netloc_segs[0] + "-api" + self.netloc.replace(netloc_segs[0], "")
        # 正则匹配规则：匹配workspace/后的任意长度纯数字
        pattern = r'workspace/(\d+)/'
        # 查找匹配结果
        match = re.search(pattern, parsed_url.path)
        if match:
            self.project_id = match.group(1)
        else:
            self.logger.error("未匹配到目标数字")
        query_dict = parse_qs(parsed_url.query)
        # self.project_id = query_dict.get("projectId", [""])[0]
        self.tool_id = query_dict.get("toolId", [""])[0]
        self.state_id = query_dict.get("stageId", [""])[0]

    def _get_project_id(self, page_url):
        parsed_url = urlparse(page_url)
        # 正则匹配规则：匹配workspace/后的任意长度纯数字
        pattern = r'workspace/(\d+)/'
        match = re.search(pattern, parsed_url.path)
        return match.group(1) if match else ""

    def _get_tool_id_and_state_id(self, page_url):
        parsed_url = urlparse(page_url)
        query_dict = parse_qs(parsed_url.query)
        return query_dict.get("toolId", [""])[0], query_dict.get("stageId", [""])[0]

    def _init_api_params(self, page_url):
        parsed_url = urlparse(page_url)
        self.url_scheme = parsed_url.scheme
        self.netloc = parsed_url.netloc
        netloc_segs = self.netloc.split(".")
        self.api_netloc = netloc_segs[0] + "-api" + self.netloc.replace(netloc_segs[0], "")

    @retry(retry=retry_if_exception(lambda e: isinstance(e, Exception)), stop=stop_after_attempt(5), wait=wait_fixed(2))
    async def _get_course_modules(self, project_id, tool_id):
        url = f"{self.url_scheme}://{self.api_netloc}/task-center/course/V1/userCourseModule?projectId={project_id}&toolId={tool_id}"
        modules = []
        response = await self.context.request.get(url, headers=self.headers)
        if response.status == 200:
            data = await response.json()
            modules = data.get("data", {}).get("modules", [])
            modules = [module.get("moduleId") for module in modules]
            # for module in modules:
            #     module_id = module.get("moduleId")
            # segments = dict(zip(module.get("segmentId").split(" "), module.get("segmentName").split(" ")))
            # subjects = dict(zip(module.get("subjectId").split(" "), module.get("subjectName").split(" ")))
            # modules[module_id] = {
            #     "segments": segments,
            #     "subjects": subjects
            # }
        return modules

    @retry(retry=retry_if_exception(lambda e: isinstance(e, Exception)), stop=stop_after_attempt(5), wait=wait_fixed(2))
    async def _get_all_courses_in_one_module(self, project_id, tool_id, module_id, segment_id, subject_id,
                                             page_idx=1) -> list:
        all_course_info = []
        url = f"{self.url_scheme}://{self.api_netloc}/task-center/course/V1/queryCourseList?projectId={project_id}&toolId={tool_id}&moduleId={module_id}&roleKey=100&pageIndex={page_idx}&pageSize=12&courseType=&segmentId={segment_id}&subjectId={subject_id}&learnStatus=0&courseName="
        # 去掉segmentId
        url = f"{self.url_scheme}://{self.api_netloc}/task-center/course/V1/queryCourseList?projectId={project_id}&toolId={tool_id}&moduleId={module_id}&roleKey=100&pageIndex={page_idx}&pageSize=12&courseType=&subjectId={subject_id}&learnStatus=0&courseName="
        try:
            response = await self.context.request.get(url, headers=self.headers)
            if response.status == 200:
                resp_json = await response.json()
                # 递归获取所有课程
                data = resp_json.get("data", {})
                all_course_info.extend(data.get("rows", []))
                if data.get("total", 0) > 0 and data.get("pageIndex") != data.get("totalPage"):
                    await asyncio.sleep(1)
                    all_course_info.extend(
                        await self._get_all_courses_in_one_module(project_id, tool_id, module_id, segment_id,
                                                                  subject_id, page_idx + 1))
        except Exception as e:
            # 异常处理：避免单页请求失败导致整个递归中断
            self.logger(f"页码 {page_idx} 请求出错：{str(e)}")
        return all_course_info

    async def _get_one_unfinished_course(self, module_ids, project_id, tool_id, segment_id, subject_id):
        for module_id in module_ids:
            course_info = await self._get_one_unfinished_course_in_one_module(project_id, tool_id, module_id,
                                                                            segment_id, subject_id)
            if course_info:
                return course_info
        return {}

    async def _get_one_unfinished_course_in_one_module(self, project_id, tool_id, module_id, segment_id,
                                                       subject_id) -> dict:
        all_course_info = await self._get_all_courses_in_one_module(project_id, tool_id, module_id, segment_id,
                                                                    subject_id)
        for course_info in all_course_info:
            if course_info.get("completeRate") != 100:
                return {"id": course_info.get("id"), "course_source_id": course_info.get("courseSourceId")}
        return {}

    async def _is_finished(self, module_ids, project_id, tool_id, segment_id, subject_id):
        if await self._cal_total_learned_time(module_ids, project_id, tool_id, segment_id, subject_id) > self.max_time:
            return True
        return False

    async def _cal_total_learned_time(self, module_ids, project_id, tool_id, segment_id, subject_id):
        all_course_info = []
        for module_id in module_ids:
            all_course_info.extend(await self._get_all_courses_in_one_module(project_id, tool_id, module_id, segment_id,
                                                        subject_id))
        total_learned_time = 0
        for course_info in all_course_info:
            if course_info.get("completeRate") == 100:
                total_learned_time += course_info.get("totalDuration")
        return int(total_learned_time / 60)

    def _course_page_url(self, course_id, project_id, stage_id, tool_id, course_source_id):
        url = f"{self.url_scheme}://{self.netloc}/grain/course/{course_id}/detail?projectId={project_id}&phaseId={stage_id}&toolId={tool_id}&courseSourceId={course_source_id}&role=100"
        return url

    @retry(retry=retry_if_exception(lambda e: isinstance(e, Exception)), stop=stop_after_attempt(5), wait=wait_fixed(2))
    async def _get_user_info_in_project(self, project_id):
        url = f"{self.url_scheme}://{self.api_netloc}/train-project-center/trainProject/detail?id={project_id}"
        response = await self.context.request.get(url, headers=self.headers)
        if response.status == 200:
            data = await response.json()
            return data.get("data", {}).get("trainProjectUserVO", {})
        else:
            return {}

    @retry(retry=retry_if_exception(lambda e: isinstance(e, Exception)), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _update_user_info(self, project_id, segment_id, segment_name, subject_id, subject_name):
        user_info = await self._get_user_info_in_project(project_id)
        if user_info and user_info.get("subjectId") == subject_id and user_info.get("stageId") == segment_id:
            # 阶段、科目一致，不需要修改
            return True
        """
        {
"trainProjectId": "6289627417674086459",
"layerId": "0",
"educateId": "",
"trainUserId": "6645050220709519400",
"userId": "6645050220709519400",
"userName": "陈燕双",
"phoneNo": "18760509032",
"idNo": "350321199008218442",
"provinceId": 350000,
"provinceName": "福建省",
"cityId": 350300,
"cityName": "莆田市",
"districtId": 350304,
"districtName": "荔城区",
"schoolId": "380082978",
"schoolName": "莆田市荔城区黄石西洪小学",
"creatorId": "6618427195910381595",
"headUrl": "https://srt-read-online.3ren.cn/basebusiness/headimg/20200901/15989405961568CQAZrWPhQ.png",
"sex": 2
}"""
        target_attrs = ["trainProjectId", "layerId", "educateId", "trainUserId", "userId",
                        "userName", "phoneNo", "idNo",
                        "provinceId", "provinceName", "cityId", "cityName", "districtId",
                        "districtName", "schoolId", "schoolName", "creatorId", "headUrl", "sex"]
        request_obj = {k: v for k, v in user_info.items() if k in target_attrs}
        request_obj["subjectId"] = subject_id
        request_obj["subjectName"] = subject_name
        request_obj["stageId"] = segment_id
        request_obj["stageName"] = segment_name
        url = f"{self.url_scheme}://{self.api_netloc}/train-project-center/trainProject/user/update"
        response = await self.context.request.post(url, data=request_obj, headers=self.headers)
        if response.status == 200:
            data = await response.json()
            if str(data.get("status").get("code")) == "200":
                # 更新成功
                return True
        return False

    @retry(retry=retry_if_exception(lambda e: isinstance(e, Exception)), stop=stop_after_attempt(5), wait=wait_fixed(2))
    async def _get_subject_info(self):
        """{
            "stage": 1201,
            "stageName": "学前",
            "subjects": [
                {
                    "code": 1128,
                    "name": "幼儿教育",
                    "unique": true
                }
            ]
            },{...}"""
        url = f"{self.url_scheme}://{self.api_netloc}/train-project-center/listStageRefSubject"
        response = await self.context.request.get(url, headers=self.headers)
        if response.status == 200:
            data = await response.json()
            return data.get("data", [])
        else:
            return []

    @retry(retry=retry_if_exception(lambda e: isinstance(e, Exception)), stop=stop_after_attempt(5), wait=wait_fixed(2))
    async def _get_topic_score(self):
        """
        获取某个专题的分数
        :return:
        """
        """{
        "status": {
            "code": 200
        },
        "data": {
            "settingResults": [
                {
                    "require": "统一按时长考核 （必修、选修） 观看课程560分钟，总分35分",
                    "finish": "已学习4分钟，已得0.26分",
                    "optionId": "0",
                    "requireScore": "35.0",
                    "finishScore": "0.26",
                    "requireNum": "560",
                    "finishNum": "4",
                    "examineRequestType": 0
                }
            ],
            "toolId": "676388017611382791",
            "userId": "680120556792488010",
            "toolName": "课程学习",
            "desc": "",
            "totalRequireScore": "35",
            "totalFinishScore": "0.26",
            "needExamine": true
        },
        "timestamp": 1782186457205
    }"""
        url = f"{self.url_scheme}://{self.api_netloc}/task-center/examine/result/tool/query"
        # {"examineSubstance":"MEMBER","examineSubstanceRole":"MEMBER","projectId":"6289627417674088509","userId":"680120556792488010","classId":"","examineType":"tool","toolId":"676388017611382791"}
        request_obj = {"examineSubstance": "MEMBER", "examineSubstanceRole": "MEMBER", "projectId": self.project_id,
                        "userId": self.user_id, "classId": "", "examineType": "tool", "toolId": self.tool_id}

        response = await self.context.request.post(url, headers=self.headers, data=request_obj)
        if response.status == 200:
            data = await response.json()
            return decimal.Decimal(data.get("data").get("totalRequireScore")), decimal.Decimal(data.get("data").get("totalFinishScore"))
        else:
            return None, None


    def _filter_segment_subject(self, segment_name, subject_name):
        for stage_subject in self.stage_subjects:
            if stage_subject.get("stageName") == segment_name:
                for subject in stage_subject.get("subjects", []):
                    if subject.get("name") == subject_name:
                        return stage_subject.get("stage"), subject.get("code")
        return None, None

    async def _enter_first_topic(self):
        first_topic = await self._get_first_unfinished_topic()
        if not first_topic:
            return False, "未找到课程（专业课、选修课）！"

        if not await first_topic.is_visible():
            await first_topic.scroll_into_view_if_needed()

        await first_topic.click()

    async def _get_first_unfinished_topic(self) -> Optional[Locator]:
        score_page = await self.get_elem_with_wait_by_xpath(10, "//li[.//text()='我的学情']")
        await score_page.click()

        score_panels = await self.get_elems_with_wait_by_xpath(10,
                                                               "//div[@class='left'][./img[@src='https://d1.3ren.cn/static/spring-train2-web/img/learn_course.2cfd4ca5.png']]//following-sibling::div[@class='right']")
        if score_panels:
            return await self.get_relative_elem_by_xpath(score_panels[0], ".//button")
        else:
            return None

    @retry(retry=retry_if_exception(lambda e: isinstance(e, Exception)), stop=stop_after_attempt(5),
           wait=wait_fixed(2))
    async def _get_my_learning_status(self):
        # 获取我的学情数据
        """{
    "status": {
        "code": 200
    },
    "data": {
        "totalScore": 100,
        "userScore": 25.26,
        "userScorePercent": 0.25,
        "projectId": "6289627417674088509",
        "phaseExamineResultVOList": [
            {
                "totalScore": 25,
                "userScore": 25.00,
                "userScorePercent": 1.00,
                "phaseType": "web",
                "phaseId": "676255726176215042",
                "phaseName": "通识课程",
                "typeToolExamineResultVOList": [
                    {
                        "packId": 676385666116820992,
                        "packName": "通识课程",
                        "toolId": "676385700476526597",
                        "toolName": "课程学习",
                        "totalRequireScore": "25",
                        "totalFinishScore": "25",
                        "finishState": 1,
                        "toolFunction": "learn_course"
                    }
                ],
                "ifOpen": "fullyOpen",
                "ifUnlock": true
            },
            {
                "totalScore": 35,
                "userScore": 0.26,
                "userScorePercent": 0.00,
                "phaseType": "web",
                "phaseId": "676255743356117005",
                "phaseName": "专业课程",
                "typeToolExamineResultVOList": [
                    {
                        "packId": 676385687591624705,
                        "packName": "专业课程",
                        "toolId": "676388017611382791",
                        "toolName": "课程学习",
                        "totalRequireScore": "35",
                        "totalFinishScore": "0.26",
                        "finishState": 0,
                        "toolFunction": "learn_course"
                    }
                ],
                "ifOpen": "fullyOpen",
                "ifUnlock": true
            },
            {
                "totalScore": 10,
                "userScore": 0.00,
                "userScorePercent": 0.00,
                "phaseType": "web",
                "phaseId": "676244514164088840",
                "phaseName": "研修活动",
                "typeToolExamineResultVOList": [
                    {
                        "packId": 676244859908988939,
                        "packName": "研修活动",
                        "toolId": "676245020970262537",
                        "toolName": "活动",
                        "totalRequireScore": "10",
                        "totalFinishScore": "0",
                        "finishState": 0,
                        "toolFunction": "activity"
                    }
                ],
                "ifOpen": "fullyOpen",
                "ifUnlock": true
            },
            {
                "totalScore": 30,
                "userScore": 0.00,
                "userScorePercent": 0.00,
                "phaseType": "web",
                "phaseId": "676244554966310912",
                "phaseName": "研修作业",
                "typeToolExamineResultVOList": [
                    {
                        "packId": 676244879236308997,
                        "packName": "研修作业",
                        "toolId": "676246260068294663",
                        "toolName": "作业1",
                        "totalRequireScore": "8",
                        "totalFinishScore": "0",
                        "finishState": 0,
                        "toolFunction": "homework"
                    },
                    {
                        "packId": 676244879236308997,
                        "packName": "研修作业",
                        "toolId": "676246268658229258",
                        "toolName": "作业2（教学设计）",
                        "totalRequireScore": "22",
                        "totalFinishScore": "0",
                        "finishState": 0,
                        "toolFunction": "homework"
                    }
                ],
                "ifOpen": "fullyOpen",
                "ifUnlock": true
            }
        ]
    },
    "timestamp": 1782187890985
}"""
        url = f"{self.url_scheme}://{self.api_netloc}/task-center/examine/result/phase/query/new"

        request_obj = {"examineSubstance": "MEMBER", "examineSubstanceRole": "MEMBER", "phaseType": "web", "projectId": self.project_id,
                       "userId": self.user_id, "selectType": 2}

        response = await self.context.request.post(url, headers=self.headers, data=request_obj)
        if response.status == 200:
            data = await response.json()
            return data.get("data").get("phaseExamineResultVOList")
        else:
            return []

    async def _get_unfinished_topics(self) -> list[tuple[str, str]]:
        # 获取未完成的专题，返回列表[(tool_id, stage_id)]
        course_urls = []
        # course_url_tmpl = f"https://ipx.yanxiu.com/train2/workspace/{self.project_id}/course/list/member?projectId={self.project_id}&role=100&toolId=%s&stageId=%s&barId=&taskId=&examineSubstanceRole=0&examineSubstance=MEMBER"
        course_info = await self._get_my_learning_status()  # 获取我的学情数据
        for course in course_info:
            vo_list_ = course.get("typeToolExamineResultVOList")
            # https://ipx.yanxiu.com/train2/workspace/6289627417674088509/course/list/member?projectId=6289627417674088509&role=100&toolId=676388017611382791&stageId=676255743356117005&barId=&taskId=&examineSubstanceRole=0&examineSubstance=MEMBER
            stage_id = course.get("phaseId")
            for vo in vo_list_:
                if vo.get("toolFunction") == "learn_course" and vo.get("finishState") == 0:
                    tool_id = vo.get("toolId")
                    # course_urls.append(course_url_tmpl % (tool_id, stage_id))
                    course_urls.append((tool_id, stage_id))
        return course_urls

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        # # 关闭其他窗口
        # await self.close_other_windows(self.course_page_window_handle)
        # # 刷新页面
        # await self.refresh()
        # # 等待页面加载完成
        # await asyncio.sleep(2)
        await self.switch_to_window(self.course_page_window_handle)
        # time.sleep(2)
        return True, ""
