import asyncio
import time
from dataclasses import dataclass, field
from typing import Optional

from playwright.sync_api import Locator

from src.frame.base.base_monitor_course_node import BaseMonitorCourseTaskNode


@dataclass(init=False)
class HXJYWMonitorCourse(BaseMonitorCourseTaskNode):
    """
    继教网正常版，需要播放学完全部视频和文档，视频可以自动切换下一个
    """
    mode: int = 0  # 模式；0-视频模式；1-无视频模式
    content_name: str = ""  # 目录名称
    is_cur_content_contains_video: bool = False  # 当前目录下是否有视频
    is_cur_course_contains_video: bool = False
    video_contents: list = field(default_factory=list)
    non_video_contents: list = field(default_factory=list)

    async def prepare_before_poll_monitor_course(self):
        await self.switch_to_window_by_url_key("course/intoSelectCourseVideo")
        # 获取所有视频目录和非视频目录
        self.video_contents, self.non_video_contents = await self._get_all_contents()
        if not self.video_contents and not self.non_video_contents:
            self.terminate("没有获取到目录！")
            return

        is_cur_course_contains_video = True if self.video_contents else False
        if is_cur_course_contains_video:
            self.mode = 0
            # 对于有视频的课程，把所有非视频的目录都点击一遍即可
            for content in self.non_video_contents:
                await content.click()
                await asyncio.sleep(1)
            current_content = self.video_contents[0]
        else: # 没有视频
            self.mode = 1
            current_content = self.non_video_contents[0]

        # 点击第一个目录开始学习
        await current_content.click()
        self.content_name = await current_content.get_attribute("title")


    async def single_poll_monitor(self):
        if self.mode == 0:
            # 处理弹窗大问题，各种弹窗！先处理弹窗问题，免得弹窗掩盖了课程时间，导致课程时间取不到
            await self._handle_content_pause_tips()
            if await self._handle_content_finished_tips():
                # 等待蒙版消息
                await asyncio.sleep(2)
                # time.sleep(2)

            # 处理“我还在听”
            await self._handle_i_am_here()
            # 处理被暂停，莫名的
            await self._handle_pause()

            current_content = await self.get_elem_by_xpath("//li[contains(@class, 'cur active')]")
            if current_content:
                self.content_name = await current_content.get_attribute("title")

            total_time = await self.get_course_total_time()
            learned_time = await self.get_course_learned_time()
            self.logger.info(f"【{self.course_name}】已学习：{learned_time}/{total_time}分钟")

            # 处理最后一个视频
            if await self.is_video_ended("div.ccH5playerBox video") and await self.is_last_video():
                self.logger.info(f"【{self.content_name}】已学完（最后一个），开始轮训播放视频...")
                video_contents, _ = await self._get_all_contents()
                await video_contents[0].click()
        else:
            # 挂机20分钟后（3秒轮训一次，400次为20分钟），切换到下一个目录
            if self.poll_count != 0 and self.poll_count % 400 == 0:
                self.logger.info(f"【{self.content_name}】已学完，挂机20分钟后，切换到下一个目录...")
                next_content = await self.get_next_non_video_content()
                if next_content:
                    await next_content.click()
                else:
                    # 没有下一个目录了，重新切换到第一个目录
                    _, non_video_contents = await self._get_all_contents()
                    await non_video_contents[0].click()

            total_time = await self.get_course_total_time()
            learned_time = await self.get_course_learned_time()
            self.logger.info(f"已学习时间：{learned_time}/{total_time}分钟")

        finished_tips_elem = await self.get_elem_by_xpath("//span[@id='bestMinutesTips']")
        if finished_tips_elem and await finished_tips_elem.is_visible():
            # 课程已学完
            self.logger.info(f"【{self.course_name}】达到最大学习时间，结束学习！")
            self.terminate("已学完！")

    async def get_course_learned_time(self):
        el_learned_time = await self.get_elem_by_xpath("//span[@id='courseStudyMinutesNumber']")
        return await el_learned_time.text_content() if el_learned_time else None

    async def get_course_total_time(self):
        el_total_time = await self.get_elem_by_xpath("//span[@id='courseStudyBestMinutesNumber']")
        return await el_total_time.text_content() if el_total_time else None

    async def is_last_video(self):
        xpath = "//li[contains(@class, 'cur active')]//following::li[contains(@class, 'type_1')]"
        return True if not await self.get_elem_by_xpath(xpath) else False

    async def is_last_non_video(self):
        return True if not await self.get_next_non_video_content() else False

    async def get_next_non_video_content(self):
        xpath = "//li[contains(@class, 'cur active')]//following::li[contains(@class, 'Learned0')]"
        return await self.get_elem_by_xpath(xpath)

    async def _get_all_contents(self):
        xpath = "//li[contains(@class, 'Learned0')]"
        all_contents = await self.get_elems_with_wait_by_xpath(5, xpath)
        video_contents = []
        non_video_contents = []
        for content in all_contents:
            if await self._is_cur_content_contains_video(content):
                video_contents.append(content)
            else:
                non_video_contents.append(content)
        return video_contents, non_video_contents

    async def _get_all_non_video_contents(self):
        xpath = "//li[contains(@class, 'type_2')]"
        non_video_contents = await self.get_elems_with_wait_by_xpath(5, xpath)
        return non_video_contents

    async def _is_current_course_finished(self):
        finished_tips_elem = await self.get_elem_with_wait_by_xpath(3, "//span[@id='bestMinutesTips']", False)
        return True if finished_tips_elem and await finished_tips_elem.is_visible() else False

    async def _handle_content_pause_tips(self):
        confirm_btn = await self.get_elem_by_xpath(
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
        xpath = "//div[contains(@class,'layui-layer layui-layer-dialog')]//a[text()='Ok，我知道了！']"
        confirm_btn = await self.get_elem_by_xpath(xpath)
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
        # 先处理视频倍暂停的弹窗提示
        # if "xy" in self.project_code:
        #     if self.get_elem((By.XPATH, "//div[@id='layui-layer1']")):
        #         # 弹出了“你还在认真学习吗？”的对话框
        #         verify_code_val = self.web_browser.find_element(By.XPATH,
        #                                                         Constants.FJHX_VERIFY_CODE_TEXT_IN_ALERT_XPATH).text
        #         self.web_browser.find_element(By.XPATH, Constants.FJHX_VERIFY_CODE_INPUT_IN_ALERT_XPATH).send_keys(
        #             verify_code_val)
        #         self.web_browser.find_element(By.XPATH, Constants.FJHX_COMMIT_BTN_IN_ALERT_XPATH).click()
        #         self.logger.info("处理“您还在认真学习吗？“弹窗成功")
        # else:
        #     if continue_learn := self._get_i_am_here_alert():
        #         if continue_learn.is_displayed():
        #             continue_learn.click()
        if await self.get_elem_by_xpath("//div[contains(@class,'layui-layer layui-layer-page')]"):
            # 弹出了“你还在认真学习吗？”的对话框
            verify_code_elem = await self.get_elem_by_xpath(
                "//div[contains(@class,'layui-layer layui-layer-page')]//span[@id='codespan']")
            verify_code_val = await verify_code_elem.text_content()
            await (await self.get_elem_by_xpath(
                "//div[contains(@class,'layui-layer layui-layer-page')]//input[@id='code']")).fill(
                verify_code_val)
            await (await self.get_elem_by_xpath(
                "//div[contains(@class,'layui-layer layui-layer-page')]//a[text()='提交']")).click()
            self.logger.info("处理“您还在认真学习吗？“弹窗成功")

    async def _handle_pause(self):
        # 点击弹窗中的确认按钮之后，再点击播放按钮，视频才能正常播放
        await self._play_video()

    async def _play_video(self):
        await self.play_video('div.ccH5playerBox video')

    # def _play_video(self):
    #     self.execute_js("""let css_expr = 'div.ccH5playerBox video';
    # let video = document.querySelector(css_expr);
    # if (video != null && !video.muted) {
    # 	video.muted = true;
    # }
    #
    # css_expr = 'div#replaybtn';
    # let play_button = document.querySelector(css_expr);
    # if (play_button != null && play_button.offsetParent !== null) {
    # 	play_button.click();
    # }""")

    async def _is_cur_content_contains_video(self, el_current_content):
        return True if "type_1" in await el_current_content.get_attribute("class") else False
        # return True if await self.get_elem_with_wait_by_xpath(3, "//div[@class='ccH5playerBox']", False) else False

    async def _is_cur_content_finished(self):
        ret = False
        # 在正常学习的状态
        played_time, total_time = await self._get_played_time_and_total_time()
        if played_time is not None and total_time is not None and len(played_time) > 0 and len(total_time) > 0 \
                and total_time != "00:00" \
                and (played_time if played_time.count(":") == 2 else "00:" + played_time) >= (
                total_time if total_time.count(":") == 2 else "00:" + total_time):
            # 时间相等了，说明已经播放完成
            ret = True
        return ret, played_time, total_time

    async def _get_played_time_and_total_time(self):
        ret = None, None
        try:
            played_time_js = "document.querySelector('div[class=ccH5Time] :nth-child(1)').textContent"
            total_time_js = "document.querySelector('div[class=ccH5Time] :nth-child(3)').textContent"
            played_time = await self.execute_js(played_time_js)
            total_time = await self.execute_js(total_time_js)
        except:
            # 没有找到已经播放完的时间
            self.logger.error("【%s】没有获取到时间，页面出现异常！" % self.content_name)
        else:
            ret = played_time, total_time
        return ret

    async def _get_first_content(self):
        if "hxwysqy2025" in self.version:
            # contents = await self.get_elems_with_wait_by_xpath(10,
            #                                                    "(//li[contains(@class, 'isStudy')])[last()]//following::li[contains(@class, 'type_1')]")
            # 下一个内容的xpath=//li[contains(@class, 'cur active')]//following::li
            contents = await self.get_elems_with_wait_by_xpath(10,
                                                               "//li[contains(@class, 'cur active')]//following::li")
            if contents:
                first_content = contents[0]
                if not await first_content.is_visible():
                    await first_content.scroll_into_view_if_needed()
                return first_content
            else:
                return None
        else:
            first_content = await self.get_elem_with_wait_by_xpath(3,
                                                                   "//div[@class='course-list-con']//li[contains(@class, 'cur')]//a",
                                                                   False)
            if first_content and not await first_content.is_visible():
                await first_content.scroll_into_view_if_needed()
                await asyncio.sleep(1)
                # time.sleep(1)
            return first_content


    async def _get_next_content(self) -> Optional[Locator]:
        # 返回第一个视频课程
        if "hxwysqy2025" in self.version:
            if not self.is_cur_content_contains_video:  # 上一个目录不是视频不会自动切换！需要手动点击，因此要返回下一个目录
                # TODO 2026年7月2日23:42:17 修改
                # xpath = "(//li[contains(@class, 'type_1') and contains(@class, 'isStudy')])[last()]//following::li[contains(@class, 'type_1')]"
                xpath = "//li[contains(@class, 'cur active')]/following::li"
                el_next_content = await self.get_elem_with_wait_by_xpath(3, xpath)
                if not el_next_content:  # 没有下一个目录了，则获取第一个视频
                    self.logger.info("没有获取到下一个目录！默认播放第一个视频")
                    xpath = "(//li[contains(@class, 'type_1')])[1]"
                    el_next_content = await self.get_elem_with_wait_by_xpath(3, xpath)
                    if not el_next_content:  # 没有视频，则获取第一个目录，最后肯定会找到一个
                        xpath = "(//li[contains(@class, 'Learned0')])[1]"
                        el_next_content = await self.get_elem_with_wait_by_xpath(3, xpath)
                return el_next_content
            else:  # 上一个目录是视频会自动切换！
                return None
        else:
            return await self._get_first_content()
