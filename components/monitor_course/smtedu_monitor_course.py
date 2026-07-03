import asyncio
import decimal
import random
from dataclasses import dataclass, field
from pathlib import Path

from playwright.async_api import Page

from src.frame.base import BaseMonitorCourseTaskNode
from src.frame.common.exceptions import BusinessException
from src.utils import SysPathUtils


@dataclass(init=False)
class SMTEDUMonitorCourse(BaseMonitorCourseTaskNode):
    # 课程信息，课程名称：{duration:课程时长，id:课程ID}
    course_info: dict = field(default_factory=dict)
    # 课程页面窗口句柄
    course_page_window_handler: Page = None
    # 视频页面窗口句柄
    video_page_window_handler: Page = None
    # 培训ID
    train_id: str = ""
    # 用户ID
    user_id: str = ""
    # 当前专题的要求学时
    phase_period_hour_limit: decimal.Decimal = decimal.Decimal(0)
    # 学时修正偏差值
    time_fix_deviation: decimal.Decimal = decimal.Decimal("0.3")

    async def prepare_before_poll_monitor_course(self):
        self.video_page_window_handler = self.get_prev_output().get("video_page")
        self.course_page_window_handler = self.get_prev_output().get("course_page")
        self.course_info = self.get_prev_output().get("course_info")
        self.train_id = self.get_prev_output().get("train_id", "")
        self.phase_period_hour_limit = decimal.Decimal(
            self.get_prev_output().get("phase_period_hour_limit", decimal.Decimal(0)))
        self.user_id = self.get_prev_output().get("user_id", "")
        await self.switch_to_window(self.video_page_window_handler)
        await self._trigger_first_content()

    async def single_poll_monitor(self):

        if await self.is_current_video_ended():
            self.logger.info("【%s】视频已结束，准备切换到一个目录", self.content_name)
            # 切换到下一个目录
            await self._switch_to_next_content()
            return

        await self.handle_exercise()
        await self.handle_pause()

        played_time, total_time = await self._get_played_time_and_total_time()
        self.logger.info("【%s】总时长%s，已学习%s", self.content_name, total_time, played_time)

    async def handle_exercise(self):
        exercise_window = await self.get_elem_by_xpath("//div[@class='index-module_box_blt8G']")
        while exercise_window:
            items = await self.get_elems_with_wait_by_xpath(3, "//li[@class='nqti-option _qp-option']")
            if items:
                try:
                    await items[random.randint(0, len(items) - 1)].click()
                except:
                    self.logger.exception("看视频【%s】做练习失败(选项点击不了)，请人工介入检查", self.content_name)
                    raise BusinessException("做练习失败(选项点击不了)")
                else:
                    next_subject_btn = await self.get_elem_with_wait_by_xpath(5,
                                                                              "//button[@class='fish-btn fish-btn-primary']")
                    if next_subject_btn:
                        try:
                            await next_subject_btn.click()
                        except:
                            self.logger.error("看视频【%s】做练习失败(下一题点击不了)，请人工介入检查", self.content_name)
                            raise BusinessException("做练习失败(下一题点击不了)")
                        else:
                            exercise_window = await self.get_elem_with_wait_by_xpath(3,
                                                                                     "//div[@class='index-module_box_blt8G']")

    async def handle_pause(self):
        btn_i_known = await self.get_elem_by_xpath("//div[@class='fish-modal-content']//button[.//text()='我知道了']")
        if btn_i_known:
            await self.js_click(btn_i_known)
        await self.play_video("video.vjs-tech")
        # pause_btn = await self.is_elem_visible("//button[contains(@class,'vjs-paused')]")
        # if pause_btn:
        #     try:
        #         await pause_btn.click()
        #     except:
        #         pass

    async def is_current_video_ended(self):
        ret = False
        is_video_ended = await self.is_video_ended("video.vjs-tech")
        xpath = "//div[contains(@class,'resource-item resource-item-train resource-item-active')]//i"
        current_content_finished_flag = await self.get_elem_by_xpath(xpath)
        if is_video_ended or (current_content_finished_flag and (
        await current_content_finished_flag.get_attribute("title")) == "已学完"):
            ret = True
        return ret

    async def _get_video_progress(self):
        ret = False
        # 在正常学习的状态
        played_time, total_time = await self._get_played_time_and_total_time()
        if played_time and total_time and len(played_time) > 0 and len(total_time) > 0 \
                and total_time != "00:00" \
                and (played_time if played_time.count(":") == 2 else "00:" + played_time) >= (
                total_time if total_time.count(":") == 2 else "00:" + total_time):
            # 时间相等了，说明已经播放完成
            ret = True
        return ret, played_time, total_time

    async def _get_played_time_and_total_time(self):
        ret = None, None
        try:
            played_time_js = "document.querySelector(\"%s\").textContent" % "span[class='vjs-current-time-display']"
            total_time_js = "document.querySelector(\"%s\").textContent" % "span[class='vjs-duration-display']"
            played_time = await self.execute_js(played_time_js)
            total_time = await self.execute_js(total_time_js)
        except:
            # 没有找到已经播放完的时间
            self.logger.error("【%s】没有获取到时间，页面出现异常！" % self.content_name)
        else:
            ret = played_time.rjust(5, "0"), total_time.rjust(5, "0")
        return ret

    async def _switch_to_next_content(self):
        # 刷新窗口，让右侧目录栏更新
        # self.web_browser.refresh()
        await asyncio.sleep(2)
        # 由于不需要把课程中所有的目录都读完，所以读完第一个目录后，需要刷新课程页面，用于判断当前课程是否完成
        finished_info: dict = await self._get_finished_info()
        # 没有认定的课程，则直接读完所有课程
        if decimal.Decimal(finished_info.get(self.course_info["phase_id"], "0.0")) >= decimal.Decimal(
                self.phase_period_hour_limit) + self.time_fix_deviation:  # 多加0.5学时避免学时不够！
            # 判定当前专题是否已经完成了
            self.terminate("已完成")
            return

        if decimal.Decimal(self.course_info["max_period"]) > decimal.Decimal(0):  # 针对有认定的课程
            if decimal.Decimal(finished_info.get(self.course_info["id"], "0.0")) < decimal.Decimal(
                    self.course_info["max_period"]) + self.time_fix_deviation:
                # 还未达到学时要求，需要读下一个目录
                await self._trigger_first_content()
            else:
                self.terminate("已完成")
        else:  # 针对没有认定的课程
            if decimal.Decimal(finished_info.get(self.course_info["id"], "0.0")) < decimal.Decimal(
                    self.course_info["total_period"]) + self.time_fix_deviation:
                # 判定当前课程是否已经完成了
                # 还未达到学时要求，需要读下一个目录
                await self._trigger_first_content()
            else:
                self.terminate("已完成")

    async def _get_finished_info(self):
        # 获取课程的完成情况
        url = f"https://elearning-train-api.ykt.eduyun.cn/v1/users/{self.user_id}/trains/{self.train_id}/courses_period/actions/list"
        headers = {"User-Agent": await self.user_agent(), "Cookies": await self.cookie_to_str()}
        try:
            finished_info = await self.context.request.get(url=url, headers=headers)
        except:
            self.logger.error("获取用户信息失败")
            raise

        return await finished_info.json()

    async def get_every_course_study_progress(self):
        await self.switch_to_window(self.course_page_window_handler)
        await self.refresh()
        await asyncio.sleep(3)
        course_names = list(self.course_info.keys())
        # xpath_expr_list = []
        # for course_name in course_names:
        #     xpath_expr_list.append(Constants.SMTEDU_LEARNED_DURATION_TMPL_XPATH % course_name)
        # xpath_expr = "|".join(xpath_expr_list)
        xpath_expr = "//div[@class='index-module_processC_0VNia'][contains(text(),'已认定')]//span[@class='index-module_processCMy_kp+Ww']"
        courses_learned_time = await self.get_elems_with_wait_by_xpath(20, xpath_expr, visible=False)
        if courses_learned_time:
            return {course_names[i]: float(await courses_learned_time[i].text_content()) for i in
                    range(len(course_names))}
        else:
            if sign_in_btn := await self.is_elem_visible_by_xpath("//div[text()='立即报名']"):
                self.logger.info("未报名，开始报名")
                await sign_in_btn.click()
                await asyncio.sleep(3)
                if not await self.is_elem_visible_by_xpath("//div[text()='立即报名']"):
                    self.logger.info(f"报名成功")
            else:
                self.logger.error("加载课程页面失败")
                raise BusinessException("加载课程页面失败")

    async def _trigger_first_content(self):
        await self.switch_to_window(self.video_page_window_handler)
        # 学习第一个目录
        # 点击章节，展开所有的目录
        await self._expand_all_chapters()
        first_content = await self.get_elem_with_wait_by_xpath(12,
                                                               "(//div[contains(@class,'resource-item-train')][.//i[@title='未开始' or @title='进行中']])[1]",
                                                               False)
        if not first_content:
            first_content = await self.get_elem_by_xpath(
                "(//div[contains(@class,'resource-item-train')][.//i[contains(@class,'icon_checkbox_linear')]][.//i[@title='已学完']])[1]")
            if not first_content:
                await self.screenshot(Path(SysPathUtils.get_tmp_file_dir(), self.username + "-error" + str(
                    random.randint(0, 100000)) + ".png"))
                self.logger.error("未找到可读的目录")
                raise BusinessException("未找到可读的目录")
        # if not await first_content.is_visible():
        #     lecture_title = await self.get_relative_elem_by_xpath(first_content,
        #                                                           "./ancestor::div[contains(@class,'fish-collapse-item')]")
        #     if lecture_title:
        #         try:
        #             # await lecture_title.click()
        #             await self.js_click(lecture_title)
        #         except:
        #             pass
        #         else:
        #             await self.wait_for_visible(10, first_content)
        #             if not await first_content.is_visible():
        #                 self.logger.error("目录不可见，页面加载异常")
        #                 raise BusinessException("目录不可见，页面加载异常")
        if not first_content:
            self.logger.error("所有目录已读完")
            raise BusinessException("所有目录已读完")

        self.content_name = self.course_name + "-" + await first_content.text_content()
        try:
            # await first_content.click()
            await self.js_click(first_content)
        except:
            self.logger.exception("点击目录失败")
            raise BusinessException("点击目录失败")
        # else:
        #     video = await self.get_elem_with_wait_by_xpath(10, "//button[@class='vjs-big-play-button']")
        #     if video:
        #         try:
        #             await video.click()
        #         except:
        #             self.logger.exception("点击播放视频失败")
        #         else:
        #             await self.handle_test_tips()

    async def handle_test_tips(self):
        i_known_elem = await self.get_elem_with_wait_by_xpath(3, "//button[@class='vjs-big-play-button']")
        if i_known_elem:
            try:
                await i_known_elem.click()
            except:
                pass

    async def _expand_all_chapters(self):
        # 展开所有章节的目的：获取章节下的所有目录，否则不会获取到被折叠的目录
        chapters = await self.get_elems_with_wait_by_xpath(20, "//div[@class='fish-collapse-header']")
        if chapters:
            for chapter in chapters:
                if (await chapter.get_attribute("aria-expanded")) == "false":
                    try:
                        await chapter.click()
                        await asyncio.sleep(1)
                        max_time = 10
                        while (await chapter.get_attribute("aria-expanded")) != "true" and max_time > 0:
                            await asyncio.sleep(1)
                            max_time -= 1
                    except:
                        self.logger.exception("展开章节失败")
