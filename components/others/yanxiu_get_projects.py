from dataclasses import field, dataclass
from typing import Dict, Any
from urllib.parse import urlparse

from playwright.async_api import Page
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception

from src.frame.base.base_task_node import BasePYNode


@dataclass(init=False)
class YanxiuGetProjects(BasePYNode):
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
    api_netloc: str = ""

    # 异步监听请求
    async def handle_request(self, request):
        if "/user/getUserInfo" in request.url:
            authorization = request.headers.get("authorization")
            srxuserinfo = request.headers.get("srxuserinfo")
            accesstoken = request.headers.get("x-dt-accesstoken")
            client_id = request.headers.get("x-dt-clientid")

            headers = {"authorization": authorization, "srxuserinfo": srxuserinfo, "x-dt-accesstoken": accesstoken,
                       "x-dt-clientid": client_id}
            self.headers.update(headers)

    async def execute(self, context) -> bool:
        prev_output = self.get_prev_output()
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36"}
        # 更新请求头
        self.headers.update(prev_output.get("headers", {}))

        if not self.headers.get("authorization"):
            self.get_current_page().on("request", self.handle_request)
            self.logger.info("刷新页面，重新获取请求头...")
            await self.refresh()  # 刷新页面登录按钮重新获取请求头

        self._init_api_params(await self.get_current_url())
        unfinished_projects = await self._get_project_unfinished_projects()

        desc = [f"{len(unfinished_projects)}个项目："] if unfinished_projects else ["无项目"]

        for project in unfinished_projects:
            desc.append(project.get("projectName"))
            desc.append("；")

        # 去掉最后一个分号
        if desc[-1] == "；":
            desc.pop()
        desc = "".join(desc)
        self.logger.info(f"获取进行中的项目成功：【{desc}】")
        self.user_manager.update_record_by_username(self.username, {5: "".join(desc)})
        return True

    @retry(retry=retry_if_exception(lambda e: isinstance(e, Exception)), stop=stop_after_attempt(5), wait=wait_fixed(2))
    async def _get_project_unfinished_projects(self):
        all_course_info = []
        url = f"{self.url_scheme}://{self.api_netloc}/train-project-center/trainProject/personalProjectPage?pageIndex=1&pageSize=10&projectName=&trainStatus=2"
        try:
            response = await self.context.request.get(url, headers=self.headers)
            if response.status == 200:
                resp_json = await response.json()
                # 递归获取所有课程
                all_course_info = resp_json.get("data", {}).get("rows", [])
        except Exception as e:
            # 异常处理：避免单页请求失败导致整个递归中断
            self.logger.error(f"请求出错：{str(e)}")
        return all_course_info

    def _init_api_params(self, page_url):
        parsed_url = urlparse(page_url)
        self.url_scheme = parsed_url.scheme
        self.netloc = parsed_url.netloc
        netloc_segs = self.netloc.split(".")
        self.api_netloc = netloc_segs[0] + "-api" + self.netloc.replace(netloc_segs[0], "")
