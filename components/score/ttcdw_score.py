import asyncio
import re
from dataclasses import dataclass
from typing import Dict
from urllib.parse import urlparse

from playwright.async_api import Page
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.frame.base.base_task_node import BasePYNode


@dataclass(init=False)
class TTCDWScore(BasePYNode):
    """
    学习公社获取分数
    """

    course_page: Page = None

    async def execute(self, context: Dict) -> bool:
        # 点击项目
        tab_projects = await self.get_elem_with_wait_by_xpath(10,
                                                              "//div[contains(@class, 'sec-menu') and contains(text(), '项目')]")
        if tab_projects:
            await tab_projects.click()
        else:
            self.logger.error("未找到项目标签")
            return False

        btn_learn = await self.get_elem_with_wait_by_xpath(10,
                                                           "//div[@class='list']/div[contains(@class, 'item')]//a[@class='item_btn']")
        if not btn_learn:
            self.logger.error("未找到学习按钮")
            return False

        await btn_learn.click()
        await asyncio.sleep(2)
        # 打开新窗口
        await self.switch_to_window_by_url_key("uc/myClassroom")

        # 匹配路径中被 / 包裹的纯数字字符串
        pattern = r"/(\d+)(?=/)"
        # nums = re.findall(pattern, await self.get_current_url())
        # 分别取出两个值
        parsed = urlparse(await self.get_current_url())
        path_parts = parsed.path.split("/")
        # path_parts: ['', 'p', 'uc', 'myClassroom', '1135700848104415232', 'center', '1135762202482638848']
        room_id = path_parts[4]
        course_id = path_parts[6]

        await self._request_score(room_id, course_id)
        self.logger.info("获取成绩成功")
        return True

    async def wait_text(self, locator_xpath: str, timeout=5):
        error_loc = await self.get_elem_with_wait_by_xpath(10, locator_xpath)
        if not error_loc:
            await self.refresh()
            error_loc = await self.get_elem_with_wait_by_xpath(10, locator_xpath)

        # 每个0.5秒检测一次元素的textContent，当时间超过timeout，则返回""
        while True:
            if (await error_loc.text_content()).strip():
                return (await error_loc.text_content()).strip()
            await asyncio.sleep(0.5)
            timeout -= 0.5
            if timeout <= 0:
                return ""

    async def _get_score(self):


        t1 = await self.wait_text("(//div[@class='assess-tips']//div[@class='col-1']/span)[1]")
        t2 = await self.wait_text("(//div[@class='assess-tips']//div[@class='col-1']/span)[2]")
        t3 = await self.wait_text("(//div[@class='assess-tips']//div[@class='col-1']/span)[3]")
        self.logger.info(f"考核要求{t1}分钟，选课时长{t2}分钟，已完成{t3}分钟")
        self.user_manager.update_record_by_username(self.username,
                                                    {5: f"要求{t1}分钟", 6: f"选课{t2}分钟", 7: f"已完成{t3}分钟"})
        # return t1, t2, t3

    @retry(retry=retry_if_exception_type((Exception)), stop=stop_after_attempt(3),
           wait=wait_fixed(2))
    async def _request_score(self, room_id, course_id):
        url = f"https://www.ttcdw.cn/p/uc/services/member/project/study_f/ass_data/{room_id}/{course_id}/-1"
        headers = {"cookie": await self.cookie_to_str(), "user-agent": await self.user_agent()}
        try:
            resp = await self.context.request.get(url, headers=headers)
        except:
            self.logger.exception("获取成绩失败：")
            raise

        resp_json = await resp.json()
        segment_study_info = resp_json.get("data").get("studyFile").get("segmentStudyFiles")[0]
        total_score = f"阶段成绩：{segment_study_info.get('totalScore')}"
        offset_cell_count = 3
        item_result = {offset_cell_count + 0: total_score}
        for idx, item in enumerate(segment_study_info.get("itemStudyFileVos")):
            unit = "分钟" if item.get('itemName') == "自主选学" else "个"
            item_result[
                offset_cell_count + idx + 1] = f"{item.get('itemName')}：已完成{item.get('finish')}{unit}，成绩：{item.get('score')}"

        self.user_manager.update_record_by_username(self.username, item_result)
