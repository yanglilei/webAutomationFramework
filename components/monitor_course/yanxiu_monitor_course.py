import asyncio
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from playwright.async_api import Locator, Page

from src.frame.base import BaseMonitorCourseTaskNode


class CourseStatus(Enum):
    FINISHED_ALL_COURSES = 1
    LEARNING = 2
    ERROR = 3


@dataclass(init=False)
class YanxiuMonitorCourse(BaseMonitorCourseTaskNode):
    content_name: str
    learn_course_window_handle: Page = None

    async def prepare_before_poll_monitor_course(self):
        self.content_name = ""
        self.learn_course_window_handle = self.get_latest_window()
        await self.switch_to_latest_window()

    async def single_poll_monitor(self):
        await self.monitor_learning_status()

    async def monitor_learning_status(self):
        await self.handle_pause()
        await self.force_switch_next_content()
        await self.handle_do_exam()
        # 处理“送星星”的弹窗
        await self._send_stars()

        # 判断当前课程是否学习完
        if await self._is_current_course_finished():
            # 当前课程学习完了
            self.logger.info("课程学习完毕，退出！")
            await self.do_after_finished_current_course()
            return

        # 处理“继续学习”的弹窗
        if continue_learn := await self.is_elem_visible_by_xpath("//div[@class='alarmClock-wrapper']/div"):
            # 退出学习
            self.logger.info("点击继续学习...")
            try:
                await continue_learn.click()
            except:
                self.logger.exception("点击继续学习按钮失败，请检查！")
                raise

        # 判断是否为视频
        if await self.is_elem_visible_by_xpath("//section[@class='media']//video"):
            # 视频
            # 窗口正常打开的情况
            # 切换到新窗口
            is_finished, played_time, total_time = await self._is_cur_content_finished()
            if is_finished:
                # 已经播放完成
                self.logger.info(f"【{self.content_name}】已经学习完，准备切到下一个目录...")
                # 不是最后一个目录
                # 课程播放完成，点击下一页按钮
                next_content = await self._get_next_content()
                if next_content:
                    # 下一节课程
                    try:
                        await next_content.click()
                    except:
                        self.logger.error("点击“观看下一节课程”失败，请检查！")
                else:
                    # 最后一个课程了，关闭窗口，停止学习
                    self.logger.info("课程学习完毕，退出！")
                    await self.do_after_finished_current_course()
            else:
                if not self.content_name:
                    # 目录名称为空的话则，重新获取目录名称
                    self.content_name = await self._get_content_name()
                self.logger.info("【%s】总共%s，已学习%s" % (self.content_name, total_time, played_time))

        else:
            # 文件
            # 获取下一个视频
            next_course = await self.get_elem_by_xpath(
                "//li[@class='res-item active']//following::li[@class='res-item'][.//i[@class='res-icon icon-media']]")
            if not next_course:
                if await self._is_current_course_finished():
                    self.logger.info("课程学习完毕，退出！")
                    await self.do_after_finished_current_course()
                else:
                    self.logger.info("没有未学的视频，时间未满足，挂机等待时间满足！")
            else:
                try:
                    await next_course.click()
                except:
                    self.logger.error("点击下一课程失败，请检查！")
                    raise

    async def _get_next_content(self):
        return await self.get_elem_with_wait_by_xpath(3, "//p[@class='next']")

    async def _get_content_name(self):
        ret = None
        try:
            ret = await self.get_elem_with_wait_by_xpath(10, "//li[@class='res-item active']//p")
        except:
            self.logger.error(f"【{self.content_name}】没有获取到课程名称，页面出现异常！")
        else:
            ret = await ret.text_content()
        return ret

    async def handle_pause(self):
        await self.play_video('div.vcp-player video')
        # if play_status_elem := await self.execute_js("() => {return document.querySelector('div.vcp-player');}"):
        #     if await play_status_elem.is_visible() and "vcp-playing" not in await play_status_elem.get_attribute(
        #             "class"):
        #         btn_play = await self.execute_js("() => {return document.querySelector('div.vcp-bigplay');}")
        #         if btn_play and await btn_play.is_visible():
        #             await self.js_click(btn_play)

    async def force_switch_next_content(self):
        if btn_next_content := await self.get_elem_by_css("p.next"):
            if await btn_next_content.is_visible():
                await self.js_click(btn_next_content)
        # if btn_next_content := await self.execute_js("() => {return document.querySelector('p.next');}"):
        #     if await btn_next_content.is_visible():
        #         await self.js_click(btn_next_content)

    async def handle_do_exam(self):
        question_window_xpath = "//div[@class='answerCard-wrapper']//div[@class='question current']"
        question_window = await self.get_elem_by_xpath(question_window_xpath)
        if question_window:  # 弹窗
            el_finish_condition = await self.get_elem_with_wait_by_xpath(3,
                                                                         "//div[@class='answerCard-wrapper']//div[@class='question current']//h4[@class='subTitle']")
            if el_finish_condition:
                await self._get_answer_from_remote(question_window_xpath)
            else:
                await self._random_choose(question_window)

    async def _random_choose(self, question_window):
        self.logger.info("开始做课程中的习题！")
        labels = await self.get_elems_by_xpath(
            "//div[@class='answerCard-wrapper']//div[@class='question']//label//input")
        if labels:
            # 选择选项
            await labels[0].click()
            btn_commit = await self.get_elem_by_xpath(
                "//div[@class='answerCard-wrapper']//div[@class='question']//button[.//text()='提交']")
            if btn_commit:
                await btn_commit.click()
                self.logger.info("提交了习题！")

            await self.wait_for_disappeared(3, question_window)
            if await self.is_elem_visible(question_window):
                # if await self.get_elem_by_xpath(question_alert_xpath):
                # 选项错误！
                btn_continue = await self.get_elem_by_xpath(
                    "//div[@class='answerCard-wrapper']//div[@class='question']//button[.//text()='继续看课']")
                if btn_continue:
                    await btn_continue.click()

    async def _get_answer_from_remote(self, question_alert_xpath):
        self.logger.info("开始做课程中的习题！")
        el_total_question_count = await self.get_elem_with_wait_by_xpath(2,
                                                                         "//div[@class='question current']//span[@class='total']")
        total_question_count = int((await el_total_question_count.text_content()).strip())
        el_idx = await self.get_elem_with_wait_by_xpath(2, "//div[@class='question current']//span[@class='index']")
        question_idx = int((await el_idx.text_content()).strip())

        for idx in range(question_idx, total_question_count+1):
            el_question = await self.get_elem_with_wait_by_xpath(3,
                                                                      "//div[@class='question current']//div[@class='question-stem']")
            html = await el_question.inner_html()
            # prompt = f"回答以下问题，要求：返回答案的选项的顺序（起始为 0）多个答案用英文逗号分隔，例如：0,1,2。\n=====\n{html}"
            # 请求答题大模型
            answers_str = await self._request_answer(html)

            xpath = "(//div[@class='question current']//div[@class='question-options']//label)[%d]"
            for answer in answers_str.split(","):
                el_answer = await self.get_elem_with_wait_by_xpath(2, xpath % (int(answer) + 1,))
                await el_answer.click()
                await asyncio.sleep(0.5)

            btn_commit = await self.get_elem_by_xpath(
                "//div[@class='question current']//div[@class='actions']//button")
            if btn_commit:
                await btn_commit.click()
                self.logger.info(f"第{idx}题，提交了答案！")
            if await self.get_elem_with_wait_by_xpath(3, "//div[@class='question current']//div[@class='error']"):
                btn_commit = await self.get_elem_with_wait_by_xpath(3,
                    "//div[@class='question current']//div[@class='actions']//button")
                if btn_commit:
                    await btn_commit.click()
                    self.logger.info(f"第{idx}题，答案错误，切换到下一题！")

            # await self.wait_for_disappeared(4, el_question)
            if idx == total_question_count:
                btn_iknown = await self.get_elem_with_wait_by_xpath(3, "//div[@id='result']//button")
                if btn_iknown:
                    await btn_iknown.click()
            await asyncio.sleep(3)

    async def _request_answer(self, question_html, wrong_answer=""):
        url = "https://j7p33zdfmw.coze.site/run"
        headers = {
            "Authorization": "Bearer eyJhbGciOiJSUzI1NiIsImtpZCI6ImY3NTBlMmYxLWQyN2MtNGIxMC05NzRjLWM2NDczYWJlYzk3ZiJ9.eyJpc3MiOiJodHRwczovL2FwaS5jb3plLmNuIiwiYXVkIjpbIlVXTzM2VFI5c2NWVno1aVI3a0xTSlN3QldNYkdEQnI2Il0sImV4cCI6ODIxMDI2Njg3Njc5OSwiaWF0IjoxNzg3MzIxMzc3LCJzdWIiOiJzcGlmZmU6Ly9hcGkuY296ZS5jbi93b3JrbG9hZF9pZGVudGl0eS9pZDo3Njc2NDg1MjUyMzUyNTczNTAzIiwic3JjIjoiaW5ib3VuZF9hdXRoX2FjY2Vzc190b2tlbl9pZDo3Njc2NDg2ODYyODM5NDgwMzYwIn0.XC4GVCdSgMiHNIPTeJUTvnIDOYYDdFxCMhUFNKZ1MhBm33crOIT8QW-17v13ZOxPRM-ZNVmaU3Lc4dKTgN_IrMPepsFIwPYm7BIr6AlKdWqW-MhhpkrFGeW3CW_OHUpRW2di3-QIT1qrV29GHfTVk0UKtUv4eyJdn-_AhkZy9Je0b5F8b6n8XoB3Xw8qyVk8nTLjq6O5yWkkHUATtq8yJbAWDR8mNuxib6YLcdtxzagGHaL0rbnLdPJXqDXB_6lTSiPtl1qFcOWFNAn6JNb9S-1Bmh_Ug6Of7IEzy8Gf9xQuUpRDtLcrlBKwZkS8n94CyfdBowK73Wu6o7lK0reEkg",
            "Content-Type": "application/json",
        }
        response = await self.context.request.post(url, headers=headers, data={
            "question_html": f"{question_html}",
            "wrong_answer": wrong_answer
        })
        resp_json = await response.json()
        return resp_json.get("correct_answer")

    async def _send_stars(self):
        # 送星星（评分）
        if await self.is_elem_visible_by_xpath("//div[@class='scoring-wrapper']"):
            five_stars = await self.get_elem_with_wait_by_xpath(3,
                                                                "//div[@class='scoring-wrapper']//span[@class='rate-item'][5]")
            if five_stars:
                try:
                    await five_stars.click()
                except:
                    self.logger.error("点击“5星”失败，请检查！")
                    raise Exception("点击“5星”失败，请检查！")
                else:
                    self.logger.info(f"给课程【{self.content_name}】评分5星成功！")
                    await asyncio.sleep(1)
                    commit = await self.get_elem_with_wait_by_xpath(2, "//div[@class='scoring-wrapper']//button")

                    try:
                        await commit.click()
                    except:
                        self.logger.error("5星好评后点击“提交”失败，请检查！")
                        raise Exception("5星好评后点击“提交”失败，请检查！")

    async def _is_current_course_finished(self):
        script = """() => {const progress = document.querySelector(\"%s\");
return progress != null ? progress.style['stroke-dashoffset'] : 'xxpx';}""" % "div[class='action-timer'] svg path:nth-child(2)"
        progress = await self.execute_js(script)
        # style = await progress.get_attribute("style")
        # progress_str = re.findall("stroke-dashoffset:(.*)px", style)[0]
        return True if progress.strip().lower() == "0px" else False

    async def do_after_finished_current_course(self):
        # 关闭当前学习窗口
        await self.close_window(self.learn_course_window_handle)
        self.terminate("已学完！")

    async def _is_cur_content_finished(self):
        ret = False
        # 在正常学习的状态
        played_time, total_time = await self._get_played_time_and_total_time()
        if await self.is_elem_visible_by_xpath("//div[@class='ended-mask']"):
            ret = True
        return ret, played_time, total_time

    async def _get_played_time_and_total_time(self):
        ret = None, None
        try:
            time_label_js = "() => {return document.querySelector(\"%s\").textContent}" % "span[class='vcp-timelabel']"
            time_str = await self.execute_js(time_label_js)
            played_time, total_time = time_str.split("/")
        except:
            # 没有找到已经播放完的时间
            self.logger.error(f"【{self.content_name}】没有获取到时间，页面出现异常！")
        else:
            ret = played_time.strip(), total_time.strip()
        return ret

    async def _get_first_unfinished_topic(self) -> Optional[Locator]:
        # 获取未完成的专题
        score_page = await self.get_elem_with_wait_by_xpath(10, "//li[.//text()='我的学情']")
        await score_page.click()

        score_panels = await self.get_elems_with_wait_by_xpath(10,
                                                               "//div[@class='left'][./img[@src='https://d1.3ren.cn/static/spring-train2-web/img/learn_course.2cfd4ca5.png']]//following-sibling::div[@class='right']")
        if score_panels:
            for score_panel in score_panels:
                # 获取第一个课程的成绩
                learn_score = await self.get_relative_elem_by_xpath(score_panel,
                                                                    ".//span[@class='strong-color strong-span']")
                total_score = await self.get_relative_elem_by_xpath(score_panel, ".//span[@class='amount-score']")
                if learn_score:
                    if float(await learn_score.text_content()) < float(await total_score.text_content()[1:-1]):
                        # 学习第一个课程，返回
                        return await self.get_relative_elem_by_xpath(score_panel, ".//button")
                    else:
                        continue
                else:
                    raise Exception("获取课程成绩失败！")
        else:
            return None

    async def _get_first_unfinished_course(self):
        # 获取第一个未完成的课程
        watch_video_btn_xpath = "//div[@class='item-content'][.//div[@class='learn-status']//text()!='已观看 100%' or not(.//div[@class='learn-status'])]//div[@class='learn-btn']"
        first_course = await self.get_elem_with_wait_by_xpath(10, watch_video_btn_xpath, visible=False)
        while not first_course:
            # 翻页获取下一个课程
            # next_page_button_xpath = "//div[@class='pack-info'][.//div[contains(text(),'专业课程')]]/following-sibling::div//li[@aria-current='true']//following::li[@class='number']"
            next_page_button_xpath = "//div[@class='course-item-pane']//li[@aria-current='true']//following-sibling::li[@class='number']"
            next_page_buttons = await self.get_elems_with_wait_by_xpath(10, next_page_button_xpath)
            if not next_page_buttons:
                break
            else:
                try:
                    next_page_button = next_page_buttons[0]
                    if not await next_page_button.is_visible():
                        await next_page_button.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)
                    await next_page_button.click()
                except:
                    self.logger.error("点击下一页按钮失败，请检查！")
                    raise
                else:
                    first_course = await self.get_elem_with_wait_by_xpath(10, watch_video_btn_xpath, visible=False)
        return first_course
