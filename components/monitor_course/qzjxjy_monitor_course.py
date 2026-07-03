import time
from dataclasses import dataclass

from playwright.async_api import Page

from src.frame.base import BaseMonitorCourseTaskNode

@dataclass(init=False)
class QZJXJYMonitorCourse(BaseMonitorCourseTaskNode):
    video_page: Page = None
    content_name: str = ""
    fail_to_get_video_progress_count: int = 0
    # 第一次计算时间的标志
    first_cal_time_flag: bool = True
    # 前一次的视频进度
    pre_video_progress: str = ""
    # 当前的视频进度
    # self.cur_video_progress = ""
    # 第一次获取视频进度的时间
    first_sys_time: int = 0

    async def prepare_before_poll_monitor_course(self):
        self.video_page = self.get_prev_output().get("video_page")
        await self.switch_to_window(self.video_page)

    async def single_poll_monitor(self):
        # 处理莫名的被暂停，放在此处的原因：自动切换课程的时候会出现短暂的暂停按钮，防止被误点击拨付，导致重新再播放当前视频
        await self._handle_pause()
        # 获取当前视频的进度
        self.content_name = await self._get_content_name()
        cur_video_progress = await self._get_cur_video_progress()

        if not cur_video_progress:
            self.logger.error(f"【{self.course_name}】-【{self.content_name}】没有获取到当前视频的学习进度")

            self.fail_to_get_video_progress_count += 1

            if self.fail_to_get_video_progress_count == 10:
                self.terminate("获取视频进度失败，可能网页卡死！")
                return
            else:
                # 刷新页面
                await self.refresh()
                # 播放
                await self.play_video("div#player_box_id video")
                # 更新学习的目录名称
                self.content_name = await self._get_content_name()
        else:
            self.logger.info(f"【{self.course_name}】-【{self.content_name}】当前视频进度为：{cur_video_progress}")
            # 视频进度达到100%
            if await self._is_cur_course_finished(cur_video_progress):
                # 课程已结束则切换课程
                self.terminate("课程已结束！")
                return
            else:
                if self.first_cal_time_flag:
                    self.first_cal_time_flag = False
                    self.pre_video_progress = cur_video_progress
                    # self.cur_video_progress = cur_video_progress
                    self.first_sys_time = int(time.time())
                else:
                    if int(time.time()) - self.first_sys_time >= 60:
                        self.first_cal_time_flag = True
                        # 1分钟检测一次进度是否有更新
                        if self.pre_video_progress == cur_video_progress and "100" in cur_video_progress:
                            self.logger.info("100%%进度卡住超过1分钟，切换下一个视频...")
                            # 视频进度达到100%，但是课程未结束，说明还有未完成的视频一直没播放
                            first_unfinished_content = await self._get_unfinished_content()
                            if first_unfinished_content:
                                await self.js_click(first_unfinished_content)
                            else:
                                self.terminate("课程已结束！")
                                return

    async def _handle_pause(self):
        play_btn = await self.is_elem_visible_by_xpath("//button[@class='vjs-big-play-button']")
        if play_btn:
            try:
                await play_btn.click()
            except:
                self.logger.exception("点击播放按钮失败")


        xpath = "//div[contains(@class,'playing')]//div[@class='course-name']/p"

    async def _get_content_name(self):
        first_content = await self.get_elem_with_wait_by_xpath(10, "//div[contains(@class,'playing')]//div[@class='course-name']/p")
        return await first_content.text_content() if first_content else ""

    async def _get_cur_video_progress(self):
        progress_elem = await self.get_elem_by_xpath("//div[contains(@class,'playing')]//span[@class='progress-num f-mr10']")
        return await progress_elem.text_content() if progress_elem else ""

    async def _is_cur_course_finished(self, cur_video_progress):
        ret = False
        if await self._is_show_course_finished_tips() or ("100" in cur_video_progress and await self._is_playing_last_video()):
            ret = True
        return ret

    async def _is_show_course_finished_tips(self):
        return await self.is_elem_visible_by_xpath("//div[@class='txt' and text()='您已学完当前课程']")

    async def _is_playing_last_video(self):
        last_video = await self.get_elem_by_xpath("(//div[@class='el-collapse-item__content']//div[contains(@class, 'item')])[last()]")
        return True if last_video and "playing" in await last_video.get_attribute("class") else False

    async def _get_unfinished_content(self):
        ret = None
        first_unfinished_content_xpath = "//div[@class='item'][.//span[@class='progress-num f-mr10' and text()!='已学 100%']]"
        collapsed_elem_xpath = f"{first_unfinished_content_xpath}/ancestor::div[@class='el-collapse-item']"
        collapsed_elem = await self.get_elem_with_wait_by_xpath(5, collapsed_elem_xpath, False)
        if collapsed_elem:
            if not await collapsed_elem.is_visible():
                await collapsed_elem.scroll_into_view_if_needed()
                await self.js_click(collapsed_elem)
                # 等待加载完毕
                time.sleep(1)

            first_unfinished_content = await self.get_elem_with_wait_by_xpath(5, first_unfinished_content_xpath, False)
            if not await first_unfinished_content.is_visible():
                await first_unfinished_content.scroll_into_view_if_needed()
            ret = first_unfinished_content
        return ret