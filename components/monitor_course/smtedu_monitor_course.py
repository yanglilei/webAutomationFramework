import asyncio
import decimal
import random
import time
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
    # 当前目录名称
    content_name: str = ""
    # 当前专题的要求学时
    phase_period_hour_limit: decimal.Decimal = decimal.Decimal(0)
    # 学时修正偏差值
    time_fix_deviation: decimal.Decimal = decimal.Decimal("0.3")

    #### 视频卡住，页面需要刷新用到的变量 ####
    # 线程启动的时间。用于判断学习过程中是否卡住了。实际时间有更新，但是学习时间没有更新，则认为当前学习卡住了。需要刷新页面或者重启学习线程。
    first_sys_time: int = 0
    cur_sys_time: int = 0
    # 第一次计算时间的标志
    first_cal_time_flag: bool = True
    pre_learned_time: int = 0
    cur_learned_time: int = 0
    #### 视频卡住，页面需要刷新用到的变量 ####

    #### 获取时间失败，需要刷新用到的变量 ####
    # 需要刷新状态标志
    is_get_time_fail: bool = False
    pre_poll_count: int = 0
    # 发现获取时间失败，最大轮询多少遍之后刷新页面，轮询一次耗时3秒
    max_poll_count = 10
    #### 获取时间失败，需要刷新用到的变量 ####

    # 当前url地址
    current_page_url: str = ""

    def init_params(self):
        self.first_sys_time = 0
        self.cur_sys_time = 0
        # 第一次计算时间的标志
        self.first_cal_time_flag = True
        self.pre_learned_time = 0
        self.cur_learned_time = 0
        self.is_get_time_fail = False

    async def prepare_before_poll_monitor_course(self):
        self.init_params()
        self.video_page_window_handler = self.get_prev_output().get("video_page")
        self.course_page_window_handler = self.get_prev_output().get("course_page")
        self.course_info = self.get_prev_output().get("course_info")
        self.train_id = self.get_prev_output().get("train_id", "")
        self.phase_period_hour_limit = decimal.Decimal(
            self.get_prev_output().get("phase_period_hour_limit", decimal.Decimal(0)))
        self.user_id = self.get_prev_output().get("user_id", "")
        await self.switch_to_window(self.video_page_window_handler)
        await self._trigger_first_content()
        self.current_page_url = await self.get_current_url()

    async def single_poll_monitor(self):

        if await self.is_current_video_ended():
            self.logger.info("【%s】视频已结束，准备切换到一个目录", self.content_name)
            # 切换到下一个目录
            await self._switch_to_next_content()
            return

        await self.handle_exercise()
        await self.handle_pause()
        # played_time, total_time = await self.get_video_after_playing(self.get_current_page(), "video.vjs-tech")
        played_time, total_time = await self._get_played_time_and_total_time()
        self.logger.info(f"【{self.content_name}】进度：{played_time}/{total_time}")
        if not played_time or not total_time or played_time == "00:00:00":
            if not self.is_get_time_fail:
                self.is_get_time_fail = True
                self.pre_poll_count = self.poll_count
            else:
                if self.poll_count > self.pre_poll_count + self.max_poll_count:
                    self.logger.info(f"页面卡住了{self.max_poll_count}轮，执行刷新操作！")
                    await self.refresh()
                    self.is_get_time_fail = False
                    self.pre_poll_count = 0
            return

        hour, minute, second = played_time.split(":")
        if self.poll_count > 5:  # self.poll_count > 5的作用是延迟计算时间，防止视频时间加载延迟导致播放的时间获取到为00:00:00
            if self.first_cal_time_flag:
                self.first_sys_time = int(time.time())
                self.pre_learned_time = int(hour) * 3600 + int(minute) * 60 + int(second)
                self.first_cal_time_flag = False
            else:
                self.cur_sys_time = int(time.time())
                # 计算时间过去了多久，单位秒
                sys_time_span = self.cur_sys_time - self.first_sys_time
                self.cur_learned_time = int(hour) * 3600 + int(minute) * 60 + int(second)
                learned_time_span = self.cur_learned_time - self.pre_learned_time

                if sys_time_span - learned_time_span > 60:
                    # 1分钟了，学习时间没有更新了，则重启该页面
                    self.logger.info("【%s】卡住1分钟了，刷新页面..." % self.content_name)
                    # 退出当前的监听轮训，外部会重启
                    await self._handle_stuck()
                    self.init_params()
                    # self.terminate("学习时间没有更新！")
                    return

    async def _handle_stuck(self):
        # 处理乱跳转，网站有个bug：会突然跳转到其他页面上
        if "teacherTraining/courseDetail" not in await self.get_current_url():
            await self.load_url(self.current_page_url)
        else:
            await self.refresh()

    def format_show_time(self, time: str):
        # 格式化时间为：HH:MM:SS
        ret = time
        if len(time) < 5:
            ret = "00:" + time.rjust(5, "0")
        elif len(time) < 6:
            ret = "00:" + time
        elif len(time) < 8:
            ret = time.rjust(8, "0")
        return ret

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
        xpath = "//div[@class='fish-modal-content']//button[.//text()='我知道了']"
        btn_i_known = await self.get_elem_by_xpath(xpath)
        if btn_i_known:
            await self.js_click(btn_i_known)
            await self.wait_for_disappeared_by_xpath(5, xpath)
            self.logger.warning("处理暂停成功！")

        xpath = "//div[@class='fish-modal-content'][.//div[@class='fish-modal-confirm-content' and contains(text(), '倍速播放')]]//button"
        btn_i_known = await self.get_elem_by_xpath(xpath)
        if btn_i_known:
            await self.js_click(btn_i_known)
            await self.wait_for_disappeared_by_xpath(5, xpath)
            self.logger.warning("处理倍速播放成功！")

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
            ret = self.format_show_time(played_time), self.format_show_time(total_time)
        return ret

    async def get_video_after_playing(self, page, video_selector: str = "video", timeout_ms: int = 8000):
        # 等待video DOM出现
        await page.wait_for_selector(video_selector, timeout=timeout_ms)

        # 固定JS字符串，选择器通过入参传入，杜绝f-string{}冲突
        wait_js = """
            (params) => {
            const sel = params[0];
            const timeout = params[1];
            return new Promise((resolve, reject) => {
                const video = document.querySelector(sel);
                if (!video) {
                    reject("找不到video标签");
                    return;
                }
                // 已经正常播放直接放行
                if (video.readyState >= 3 && !video.paused) {
                    resolve();
                    return;
                }
                function playingHandler() {
                    video.removeEventListener("playing", playingHandler);
                    resolve();
                }
                video.addEventListener("playing", playingHandler);
                // 超时兜底
                setTimeout(() => {
                    video.removeEventListener("playing", playingHandler);
                    resolve();
                }, timeout);
            })
        }
        """
        # 把选择器、超时数字当成参数传给JS，不拼接字符串
        await page.evaluate(wait_js, [video_selector, timeout_ms])

        # 获取时长，同样参数传递，不用f-string
        get_time_js = """
        (sel) => {
            const v = document.querySelector(sel);
            return {
                duration: v.duration,
                currentTime: v.currentTime
            }
        }
        """
        time_data = await page.evaluate(get_time_js, video_selector)

        def sec_to_hms(seconds: float):
            if seconds is None or seconds <= 0:
                return "00:00:00"
            s = int(seconds)
            h = s // 3600
            m = (s % 3600) // 60
            sec = s % 60
            return f"{h:02d}:{m:02d}:{sec:02d}"

        return sec_to_hms(time_data.get("currentTime")), sec_to_hms(time_data.get("duration"))

    async def _switch_to_next_content(self):
        # 刷新窗口，让右侧目录栏更新
        # self.web_browser.refresh()
        await asyncio.sleep(2)
        # 此处要刷新下前一个页面！
        await self.switch_to_window(self.course_page_window_handler)
        await self.refresh()
        await self.switch_to_window(self.video_page_window_handler)
        # 由于不需要把课程中所有的目录都读完，所以读完第一个目录后，需要刷新课程页面，用于判断当前课程是否完成
        finished_info: dict = await self._get_finished_info()
        # 没有认定的课程，则直接读完所有课程
        if decimal.Decimal(finished_info.get(self.course_info["phase_id"], "0.0")) >= decimal.Decimal(
                self.phase_period_hour_limit) + self.time_fix_deviation:  # 多加0.5学时避免学时不够！
            # 判定当前阶段是否已经完成了
            self.terminate("已完成")
            return

        if decimal.Decimal(self.course_info["max_period"]) > decimal.Decimal(0):  # 针对有认定的课程
            if decimal.Decimal(finished_info.get(self.course_info["id"], "0.0")) < decimal.Decimal(
                    self.course_info["max_period"]) + self.time_fix_deviation:
                # 还未达到学时要求，需要读下一个目录
                await self._trigger_first_content()
                # 切换目录后需要重置参数，保证卡住重启机制依然有效
                self.init_params()
            else:
                self.terminate("已完成")
        else:  # 针对没有认定的课程
            if decimal.Decimal(finished_info.get(self.course_info["id"], "0.0")) < decimal.Decimal(
                    self.course_info["total_period"]) + self.time_fix_deviation:
                # 判定当前课程是否已经完成了
                # 还未达到学时要求，需要读下一个目录
                await self._trigger_first_content()
                # 切换目录后需要重置参数，保证卡住重启机制依然有效
                self.init_params()
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
                self.logger.error(f"【{self.content_name}】未找到可读的目录")
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
