import asyncio
from dataclasses import dataclass
from typing import Tuple

from playwright.async_api import Page

from src.frame.base import BaseEnterCourseTaskNode


@dataclass(init=False)
class HNGBEnterCourse(BaseEnterCourseTaskNode):
    video_page: Page = None
    main_page: Page = None

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        await self._handle_tips()
        self.main_page = self.get_current_page()
        return True, ""

    async def enter_course(self) -> Tuple[bool, str]:
        course_id, course_name = await self._get_first_unfinished_course()
        if not course_id:
            self.logger.error(f"未找到未完成的课程")
            return False, "已完成"
        url = f"https://0736.hngbjy.cn/#/play?id={course_id}"
        await self.open_in_new_window(url)
        await asyncio.sleep(2)
        pages = await self.get_windows_by_url_key("play?id")
        if pages:
            self.video_page = pages[0]
        else:
            self.logger.error(f"打开新的课程失败：{url}")
            return False, "打开新的课程失败"

        self.set_output_data("video_page", self.video_page)

        return True, course_name

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        await self.close_window(self.video_page)
        await self.switch_to_window(self.main_page)
        return True, ""

    async def _handle_tips(self):
        btn_cancel = await self.get_elem_with_wait_by_xpath(3,
                                                            "//div[@class='el-dialog courseDialog']//span[text()='取 消']")
        if btn_cancel:
            await btn_cancel.click()

    async def _get_unfinished_course_paginate(self, page_num=1, page_size=3):
        url = "https://0736.hngbjy.cn/api/Page/MyCenter"
        # 请求内容：page=1&rows=3&sort=ActiveDate&order=desc&titleNav=%E4%B8%AA%E4%BA%BA%E4%B8%AD%E5%BF%83&courseType=Unfinish&title=
        params = {
            "page": page_num,
            "rows": page_size,
            "sort": "ActiveDate",
            "order": "desc",
            "titleNav": "个人中心",
            "courseType": "Unfinish",
            "title": ""
        }
        headers = {"cookie": await self.cookie_to_str(),
                   "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.90 Safari/537.36 Edg/89.0.774.54"}
        response = await self.context.request.post(url, form=params, headers=headers)
        response = await response.json()
        if response.get("Status") == 200:
            course_infos = response.get("Data", {})
            return course_infos
        else:
            self.logger.error(f"获取失败未完成的课程失败：{response.get('Message', '')}")
            return []

    async def _get_first_unfinished_course(self):
        page_num = 1
        page_size = 3
        unfinished_course = await self._get_unfinished_course_paginate(page_num=page_num, page_size=page_size)
        total_page = self.get_total_page(total_count=unfinished_course.get("UnfinishCount"), page_size=page_size)
        target_course = None
        while page_num <= total_page:
            target_course = self._get_video_course(unfinished_course)
            if target_course:
                break
            page_num += 1
            unfinished_course = await self._get_unfinished_course_paginate(page_num=page_num, page_size=page_size)

        return (target_course.get("Id"), target_course.get("Name")) if target_course else ("", "")

    def _get_video_course(self, unfinished_course_info):
        ret = None
        for unfinished_course in unfinished_course_info.get("ListData", {}).get("UnfinishModel", []):
            if unfinished_course.get("Type") == "SingleCourse":
                ret = unfinished_course
        return ret

    def get_total_page(self, total_count: int, page_size: int) -> int:
        """
        计算分页总页数（向上取整）
        :param total_count: 数据总条数
        :param page_size: 每页条数
        :return: 总页数
        """
        # 边界校验：每页条数必须大于0
        if page_size <= 0:
            raise ValueError("page_size 必须大于 0")
        # 边界校验：无数据时总页数为0
        if total_count <= 0:
            return 0
        # 核心公式：向上取整 (total_count + page_size - 1) // page_size
        return (total_count + page_size - 1) // page_size
