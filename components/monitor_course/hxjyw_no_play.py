import asyncio
from dataclasses import dataclass
from typing import Dict, Any

from src.frame.base.base_monitor_course_node import BaseMonitorCourseTaskNode


@dataclass
class HXJYWNoPlay(BaseMonitorCourseTaskNode):
    """
    海西教育网无需播放自动计时版本！仙游和涵江的支持该版本
    """
    project_code: str = ""  # 项目编码

    async def handle_prev_output(self, prev_output: Dict[str, Any]):
        project_code = prev_output.get("project_code", "")
        if project_code and project_code.strip():
            self.project_code = project_code.strip()

    async def single_poll_monitor(self):
        if await self._is_current_course_finished():
            # 课程结束
            self.terminate("已学完！")
            return

        # 处理弹窗大问题，各种弹窗！
        await self._handle_content_pause_tips()
        if await self._handle_content_finished_tips():
            # 等待蒙版消失
            await asyncio.sleep(2)
            # time.sleep(2)

        # 处理“我还在听”
        await self._handle_i_am_here()
        # 处理被暂停，莫名的
        await self._handle_pause()

        total_time_elem = await self.get_elem_with_wait_by_xpath(3, "//span[@id='courseStudyBestMinutesNumber']")
        learned_time_elem = await self.get_elem_with_wait_by_xpath(3, "//span[@id='courseStudyMinutesNumber']")
        self.logger.info(
            f"用户【{self.username_showed}】【{self.course_name}】，总时间：{await total_time_elem.text_content()}分钟，已学习时间：{await learned_time_elem.text_content()}分钟")

    async def _is_current_course_finished(self):
        finished_tips_elem = await self.get_elem_with_wait_by_xpath(3, "//span[@id='bestMinutesTips']", False)
        return True if finished_tips_elem and await finished_tips_elem.is_visible() else False

    async def _handle_content_pause_tips(self):
        confirm_btn = self.get_elem_by_xpath(
            "//div[contains(@class,'layui-layer layui-layer-dialog')][.//*[contains(text(),'视频暂停')]]//a[text()='Ok，我知道了！']")

        if confirm_btn and await confirm_btn.is_enabled() and await confirm_btn.is_visible():
            try:
                await confirm_btn.click()
            except:
                pass
            else:
                # 等待确认按钮消失
                await self.wait_for_disappeared(2, confirm_btn)
                # 等待蒙版消失
                await self._wait_for_shade_disappear()

    async def _handle_content_finished_tips(self):
        ret = False
        xpath = "//div[contains(@class,'layui-layer layui-layer-dialog')][.//*[contains(text(),'视频已播放完成')]]//a[text()='Ok，我知道了！']"
        confirm_btn = self.get_elem_by_xpath(xpath)
        if confirm_btn and await confirm_btn.is_enabled() and await confirm_btn.is_visible():
            await confirm_btn.click()
            # 等待对话框消失
            await self.wait_for_disappeared(2, confirm_btn)
            # 等待蒙版消失
            await self._wait_for_shade_disappear()
            ret = True
        return ret

    async def _wait_for_shade_disappear(self):
        await self.wait_for_disappeared_by_xpath(2, "//div[@class='layui-layer-shade']")

    async def _handle_i_am_here(self):
        # 处理弹窗“你还在认真学习吗？”
        if self.get_elem_by_xpath("//div[contains(@class,'layui-layer layui-layer-page')]"):
            # 弹出了“你还在认真学习吗？”的对话框
            verify_code_val = await self.get_elem_by_xpath(
                "//div[contains(@class,'layui-layer layui-layer-page')]//span[@id='codespan']").text_content()
            await self.get_elem_by_xpath(
                "//div[contains(@class,'layui-layer layui-layer-page')]//input[@id='code']").fill(
                verify_code_val)
            await self.get_elem_by_xpath("//div[contains(@class,'layui-layer layui-layer-page')]//a[text()='提交']").click()
            self.logger.info(f"用户【{self.username_showed}】处理“您还在认真学习吗？“弹窗成功")

    async def _handle_pause(self):
        # 点击弹窗中的确认按钮之后，再点击播放按钮，视频才能正常播放
        await self.play_video("div.ccH5playerBox video")
