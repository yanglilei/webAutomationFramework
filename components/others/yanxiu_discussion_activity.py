import asyncio
import random
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict
from typing import Tuple, List

from playwright.async_api import Page

from src.frame.base.base_task_node import BasePYNode
from src.utils.doc_utils import DocReader


@dataclass(init=False)
class YanxiuDiscussionActivityTask(BasePYNode):
    """
    研修网研讨活动
    """
    activity_page_window_handle: Page = None

    happiness_index_file_content: list = field(default_factory=list)
    happiness_secret_file_content: list = field(default_factory=list)
    ai_support_file_content: list = field(default_factory=list)

    happiness_index_file = Path(f"C:\\Users\\lovel\\Desktop\\自测幸福指数.txt")
    happiness_secret_file = Path(f"C:\\Users\\lovel\\Desktop\\辨析幸福的秘诀.txt")
    ai_support_file = Path(f"C:\\Users\\lovel\\Desktop\\AI赋能教育——融合创新与教学转型.txt")

    def read_answer_from_question_bank(self):
        self.happiness_index_file_content = []
        self.happiness_secret_file_content = []
        self.ai_support_file_content = []

        with open(self.happiness_index_file, "r", encoding="utf-8") as f:
            self.happiness_index_file_content = [line.strip() for line in f.readlines()]

        with open(self.happiness_secret_file, "r", encoding="utf-8") as f:
            self.happiness_secret_file_content = [line.strip() for line in f.readlines()]

        with open(self.ai_support_file, "r", encoding="utf-8") as f:
            self.ai_support_file_content = [line.strip() for line in f.readlines()]


    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        # 获取第一个未完成的项目
        project_name = self.node_config.get("node_params", {}).get("project_name", "")
        if not project_name:
            return False, "请配置项目名称！"
        xpath = f"//div[@class='home-project-pane'][.//div[@class='project-name' and text()='{project_name}']]//div[@class='btn-group']//button"

        btn_enter_project = await self.get_elem_with_wait_by_xpath(10, xpath)
        if not btn_enter_project:
            return False, "没找到课程！"

        self.read_answer_from_question_bank()  # 读取答案
        # 进入课程
        await btn_enter_project.click()
        await self.wait_for_url_changed(re.compile(r"workspace/\d+/"))
        tab_my_learning_status = await self.get_elem_with_wait_by_xpath(10, "//li[.//text()='我的学情']")
        if not tab_my_learning_status:
            return False, "没找到我的学情！"
        await tab_my_learning_status.click()

        return True, "已进入课程！"

    async def execute(self, context: Dict) -> bool:
        task_result = ""
        status, desc = await self.prepare_before_first_enter_course()
        if not status:
            self.logger.error(f"用户【{self.username}】进入培训失败！")
            return False

        status, desc = await self.enter_activity()
        if not status:
            self.logger.error(f"用户【{self.username}】进入研讨活动失败：{desc}")
            return False

        await asyncio.sleep(3)
        await self.switch_to_window_by_url_key("guide/activity/list")
        self.activity_page_window_handle = self.get_current_page()
        await self._do_activity()

        self.user_manager.update_record_by_username(self.username, {5: "研讨活动已完成！"})
        return True

    async def enter_activity(self):
        xpath = "//div[contains(@class, 'tool-card')][.//div[@class='left'][.//p[contains(text(), '研讨活动')]]][.//div[@class='right']/span[text()!=20]]"
        btn_enter_activity = await self.get_elem_with_wait_by_xpath(10, xpath)
        if not btn_enter_activity:
            self.logger.info(f"用户【{self.username}】研讨活动已合格！")
            return True, "研讨活动已合格"
        try:
            await btn_enter_activity.click()
        except:
            return False, "点击进入研讨活动失败！"

        return True, "进入研讨活动成功！"


    async def _do_activity(self):
        xpath = "//div[@class='train-item is-pointer'][.//h3[contains(@class, 'incomplete')]]"
        activities = await self.get_elems_with_wait_by_xpath(10, xpath)
        for activity in activities:
            await activity.click()
            await asyncio.sleep(3)
            await self.switch_to_window_by_url_key("schoolCenter/activity")
            # 点击我要参加
            btn_sign_in = await self.get_elem_with_wait_by_xpath(5, "//div[@class='sign']/span[text()='我要参加']")
            if btn_sign_in:
                await btn_sign_in.click()
                await asyncio.sleep(3)
            # 获取多个活动环节，遍历活动：
            # 点击进入活动
            first_progress = await self.get_elem_with_wait_by_xpath(5, "(//div[@class='point-list']//li)[1]")
            if not first_progress:
                self.logger.info(f"用户【{self.username}】未找到活动！")
                await self.close_window(self.get_current_page())
                await self.switch_to_window(self.activity_page_window_handle)
                continue

            await first_progress.click()
            progresses = await self.get_elems_with_wait_by_xpath(5, "//div[@class='items-list']//li[./p[@class='tache-name' and contains(text(), '讨论')]]")
            for progress in progresses:
                await progress.click()
                el_title = await self.get_elem_with_wait_by_xpath(3, "//div[@class='task-tle']/h2")
                title = await el_title.text_content()
                if "AI融入教学的实践思考" in title:
                    answer = random.choice(self.ai_support_file_content)
                elif "自测幸福指数" in title:
                    answer = random.choice(self.happiness_index_file_content)
                elif "辨析幸福的秘诀" in title:
                    answer = random.choice(self.happiness_secret_file_content)
                else:
                    self.logger.info(f"用户【{self.username}】未处理活动【{title}】")
                    continue

                answer_input = await self.get_elem_with_wait_by_xpath(10, "//div[@class='add_text']/textarea")
                await answer_input.fill(answer)
                btn_commit = await self.get_elem_with_wait_by_xpath(10, "//label[@class='commitBtn']")
                await asyncio.sleep(1)
                await btn_commit.click()
                self.logger.info(f"用户【{self.username}】提交活动【{title}】成功！提交的答案是【{answer}】")
                await asyncio.sleep(1)

            await self.close_window(self.get_current_page())
            await self.switch_to_window(self.activity_page_window_handle)

        self.logger.info(f"用户【{self.username}】所有活动已提交！")
