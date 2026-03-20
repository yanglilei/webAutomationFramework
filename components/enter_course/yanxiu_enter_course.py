import asyncio
import re
from dataclasses import field, dataclass
from typing import Tuple, Dict, Any, Optional
from urllib.parse import urlparse, parse_qs

from playwright.async_api import Locator, Page
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception

from src.frame.base import BaseEnterCourseTaskNode


@dataclass(init=False)
class YanxiuEnterCourse(BaseEnterCourseTaskNode):
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

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        prev_output = self.get_prev_output()
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"}
        # 更新请求头
        self.headers.update(prev_output.get("headers", {}))
        # 获取第一个未完成的专题
        btn_enter_course = await self.get_elem_with_wait_by_xpath(10, "//div[@class='btn-group']//button")
        if not btn_enter_course:
            return False, "没找到课程！"
        # 进入课程
        await btn_enter_course.click()
        await self.wait_for_url_changed(re.compile(r"workspace/\d+/"))
        # 解析url，获取url参数
        self._parse_url(await self.get_current_url())
        # 获取学段和学科信息
        self.stage_subjects = await self._get_subject_info()
        # 获取课程信息
        # 学段 segment
        self.segment_name = self.node_config.get("node_params", {}).get("segment_name")
        # 学科名称
        self.subject_name = self.node_config.get("node_params", {}).get("subject_name")
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
        await asyncio.sleep(2)
        # 等待弹出新窗口
        self.course_page_window_handle = self.get_latest_window()
        await self.switch_to_latest_window()
        # 4.从url中获取参数
        self._parse_url(await self.get_current_url())
        # 5.获取项目下的模块信息
        self.modules = await self._get_course_modules(self.project_id, self.tool_id)
        # 关闭其他窗口
        await self.close_other_windows(self.course_page_window_handle)

        return True, ""

    async def enter_course(self) -> Tuple[bool, str]:
        if await self._is_finished(self.modules, self.project_id, self.tool_id, self.segment_id, self.subject_id):
            return False, f"{self.segment_name}{self.subject_name}-已学完"

        course_info = await self._get_one_unfinished_course(self.modules, self.project_id, self.tool_id, self.segment_id, self.subject_id)
        if not course_info:
            return False, f"{self.segment_name}{self.subject_name}-已学完"

        course_url = self._course_page_url(course_info.get("id"), self.project_id, self.stage_id, self.tool_id,
                                            course_info.get("course_source_id"))
        await self.open_in_new_window(course_url)
        return True, ""

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
