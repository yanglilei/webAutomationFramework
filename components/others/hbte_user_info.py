import asyncio
from dataclasses import dataclass
from typing import Dict

from src.frame.base.base_task_node import BasePYNode


@dataclass(init=False)
class HXJYWUpdateSubjectTaskNode(BasePYNode):
    """
    河北教师教育网更新学科信息
    """
    async def execute(self, context: Dict) -> bool:
        await self._get_subject()
        return True

    async def _handle_alert(self, dialog):
        await dialog.accept()
        await asyncio.sleep(1)
        await self.load_url("https://mingshi8.hbte.com.cn/index.php/Home/Project/index.html")

    async def _get_subject(self):
        await self.register_alert_handler(self._handle_alert)
        if await self.get_current_url() != "https://mingshi8.hbte.com.cn/index.php/Home/Project/index.html":
            await self.load_url("https://mingshi8.hbte.com.cn/index.php/Home/Project/index.html")
            await asyncio.sleep(1)
        btn_show_project = await self.get_elem_with_wait_by_xpath(20,
                                                                  "(//a[contains(@class, 'jinxingProductA')])[last()]")
        await self.js_click(btn_show_project)
        subject_elem = await self.get_elem_with_wait_by_xpath(10, "//div[contains(text(), '受训学段学科')]")
        if subject_elem:
            subject = await subject_elem.text_content()
            subject = subject.replace("受训学段学科：", "").strip()

            if self.user_manager:
                self.user_manager.update_record_by_username(self.username, {3: subject})
                self.logger.info(f"✅ 更新用户学科成功！学科：{subject}")
        else:
            self.logger.error("获取学科信息失败！")
