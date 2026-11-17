from dataclasses import dataclass

from src.frame.base import BaseMonitorCourseTaskNode


@dataclass(init=False)
class StudyEnaeaMonitorCourse(BaseMonitorCourseTaskNode):
    """
    旧版学习公社监听课程
    study.enaea.edu.cn
    https://study.enaea.edu.cn/viewerforccvideo.do?courseId=311605&circleId=390548
    """
    video_css = "div#J_CC_videoPlayerDiv video"
    speed_up_play_cmd = """// 获取video元素
    const video = document.querySelector('%s');

    if (video) {
        // 获取当前播放速度
        const currentPlaybackRate = video.playbackRate;

        // 判断：等于1(常速)，设置为4倍速
        if (currentPlaybackRate == 1) {
            video.playbackRate = 4;
        }
    }""" % video_css

    async def prepare_before_poll_monitor_course(self):
        course_page = self.get_prev_output().get("course_page")
        await self.switch_to_window(course_page)

    async def single_poll_monitor(self):
        await self._handle_pause()
        content_name = await self._get_content_name()
        progress = await self._get_current_content_progress()
        if progress == "100%":
            await self._switch_next_content()
            return
        self.logger.info(f"【{self.course_name}】【{content_name}】进度：{progress}")

        is_error = await self.is_video_load_error()
        if is_error:
            self.logger.error("视频加载错误，跳过该课程！")
            self.terminate("视频加载错误，跳过该课程！")
            self.set_output_data("exclude_course_flag", True)
            return

        await self.execute_js(self.speed_up_play_cmd)

    async def _handle_pause(self):
        # 检查学习过程中是否有弹窗等异常信息
        is_continue, desc = await self.handle_alert()
        if not is_continue:
            self.terminate(desc)
            return
        await self.play_video(self.video_css)

    async def handle_alert(self):
        """
        处理休息提醒，课程联系学习超过20分钟会提示休息，此时需要点击确定按钮，让课程继续
        :return:
        """
        continue_flag = True
        desc = ""
        btn_continue = await self.get_elem_by_xpath("//td[@class='td-content']//button")
        el_tips = await self.get_elem_by_xpath("//td[@class='td-content']//div[@class='dialog-content']")
        if el_tips and "您的帐号已退出或已在其它地点登录" in await el_tips.text_content():
            self.logger.info("帐号已退出或已在其它地点登录，学习结束！")
            continue_flag = False
            desc = "帐号已退出或已在其它地点登录"

        if btn_continue:
            await btn_continue.click()
            self.logger.info("点击”继续学习“按钮")

        return continue_flag, desc

    async def is_video_load_error(self):
        is_error = False
        if self.poll_count > 10:
            el_video = await self.get_elem_by_css(self.video_css)
            if not el_video:
                # 出现了视频加载错误
                is_error = True
        return is_error

    async def _is_current_content_ended(self):
        return await self._get_current_content_progress() == "100%"

    async def _get_current_content_progress(self):
        xpath = "//li[contains(@class,'current')]//div[@class='cvtb-MCK-CsCt-studyProgress']"
        el_progress = await self.get_elem_by_xpath(xpath)
        if el_progress:
            progress_val = await el_progress.text_content()
            return progress_val
        return ""

    async def _switch_next_content(self):
        if not await self._trigger_first_unfinished_content():
            self.logger.warn("课程下的所有内容已学完，切换下一个课程！")
            self.terminate("切换下一个课程！")
            return

    async def _trigger_first_unfinished_content(self):
        content = await self._get_first_unfinished_content()
        if not content:
            return False
        await self.js_click(content)
        return True

    async def _get_first_unfinished_content(self):
        xpath = "(//li[contains(@class,'cvtb-MCK-course-content')][.//div[@class='cvtb-MCK-CsCt-studyProgress'][text()!='100%']])[1]"
        return await self.get_elem_with_wait_by_xpath(10, xpath)

    async def _get_content_name(self):
        xpath = "//li[contains(@class,'current')]//div[@class='cvtb-MCK-CsCt-title cvtb-text-ellipsis']"
        content_name = ""
        el_content_name = await self.get_elem_by_xpath(xpath)
        if el_content_name:
            content_name = await el_content_name.text_content()
        return content_name
