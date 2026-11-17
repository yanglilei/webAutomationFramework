from dataclasses import dataclass

from src.frame.base import BaseMonitorCourseTaskNode

@dataclass(init=False)
class EstudyEnaeaMonitorCourse(BaseMonitorCourseTaskNode):
    """
    新版学习公社监听课程
    estudy.enaea.edu.cn
    https://estudy.enaea.edu.cn/web/player/project?activity_id=2070327433989517313&plan_id=2070327433565892608&version=202606261006199&path=requiredCourse&business_id=2070327433486200832&course_id=2047211365296291840&template_id=104&project_id=2070327433486200832&title=%E5%BF%85%E4%BF%AE%E8%AF%BE%E7%A8%8B&resource_id=2047211365459869697
    """
    video_css = "div#player video"
    speed_up_play_cmd = """// 获取video元素
    const video = document.querySelector('%s');

    if (video) {
        // 获取当前播放速度
        const currentPlaybackRate = video.playbackRate;

        // 判断：等于1(常速)，设置为2倍速
        if (currentPlaybackRate == 1) {
            video.playbackRate = 2;
        }
    }""" % video_css

    async def prepare_before_poll_monitor_course(self):
        course_page = self.get_prev_output().get("course_page")
        await self.switch_to_window(course_page)

    async def single_poll_monitor(self):
        await self._handle_pause()
        btn_confirm = await self.get_elem_by_css("div[role=dialog] button")
        if btn_confirm:
            await self.js_click(btn_confirm)
        content_name = await self._get_content_name()
        progress = await self._get_current_content_progress()
        if progress == "完成":
            await self._switch_next_content()
            return
        self.logger.info(f"【{content_name}】进度：{progress}")
        await self.execute_js(self.speed_up_play_cmd)

    async def _handle_pause(self):
        await self.play_video(self.video_css)

    async def _is_current_content_ended(self):
        return await self._get_current_content_progress() == "完成"

    async def _get_current_content_progress(self):
        xpath = "//div[contains(@class, 'play-list')]//div[contains(@class, 'item-wrap')][.//span[@data-checked='true']]//span[contains(@class, 'rate-span')]"
        el_progress = await self.get_elem_by_xpath(xpath)
        if el_progress:
            progress_val = await el_progress.text_content()
            return progress_val
        return ""

    async def _switch_next_content(self):
        if not await self._trigger_first_unfinished_content():
            self.logger.warn("没有未完成的内容，退出学习")
            self.terminate("没有未完成的内容")
            return

    async def _trigger_first_unfinished_content(self):
        content = await self._get_first_unfinished_content()
        if not content:
            return False
        await self.js_click(content)
        return True

    async def _get_first_unfinished_content(self):
        xpath = "(//div[contains(@class, 'play-list')]//div[contains(@class, 'item-wrap')][.//div[@role='progressbar' and @aria-valuenow != 100]])[1]"
        return await self.get_elem_with_wait_by_xpath(10, xpath)

    async def _get_content_name(self):
        xpath = "//div[contains(@class, 'play-list')]//div[contains(@class, 'item-wrap')][.//span[@data-checked='true']]//span[contains(@class, 'name-span')]"
        content_name = ""
        el_content_name = await self.get_elem_by_xpath(xpath)
        if el_content_name:
            content_name = await el_content_name.text_content()
        return content_name

