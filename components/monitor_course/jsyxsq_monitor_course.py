from dataclasses import dataclass, field
from urllib.parse import urlparse, parse_qs

from playwright.async_api import Page
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.frame.base import BaseMonitorCourseTaskNode


@dataclass(init=False)
class JSYXSQMonitorCourse(BaseMonitorCourseTaskNode):
    course_id: str = ""
    stage_id: str = ""
    headers: dict = field(default_factory=dict)
    pre_seconds: int = 0
    video_page: Page = None

    async def prepare_before_poll_monitor_course(self):
        self.video_page = self.get_prev_output().get("video_page")
        await self.switch_to_window(self.video_page)
        self.headers = self.get_prev_output().get("headers")
        self.course_id, self.stage_id = self.extract_id_and_stageid(await self.get_current_url())

    async def single_poll_monitor(self):
        await self._handle_pause()

        if self.poll_count != 0 and self.poll_count % 100 == 0:
            # 每隔2分钟查询一次课程的进度
            is_finished, study_seconds = await self._is_course_finished()
            if is_finished: # 视频满足时间了或者时间没变化（触发挂机检测）
                btn_finish = await self.get_elem_with_wait_by_xpath(2, "//div[@class='header_btn']")
                if btn_finish:
                    await self.js_click(btn_finish)  # 点击后会自动关闭当前窗口

                    # 获取提示的文本
                    tips_elem = await self.get_elem_with_wait_by_xpath(3, "//div[@class='el-message-box__message']/p")
                    if tips_elem and "挂机" in await tips_elem.text_content():
                        self.set_output_data("restart_flag", True)

                    btn_confirm = await self.get_elem_with_wait_by_css(3, "div.el-message-box__btns button:last-child")
                    if btn_confirm and await btn_confirm.is_visible():
                        await btn_confirm.click()
                    self.terminate("已学完！")
            elif study_seconds == self.pre_seconds:
                # 时间没变，触发了挂机检测，外部重新进入该课程
                # self.terminate("已触发挂机检测！")
                self.terminate("触发了挂机检测！")
                await self.close_window(self.video_page)
                self.set_output_data("restart_flag", True)
            else:
                self.pre_seconds = study_seconds


        content_name = await self._get_content_name()
        played_time, total_time = await self._get_played_time_and_total_time()
        self.logger.info(f"【{content_name}】已播放：{played_time}，总时长：{total_time}")

    async def _get_played_time_and_total_time(self):
        ret = None, None
        try:
            played_time_js = "document.querySelector('em[class=ccH5TimeCurrent]').textContent"
            total_time_js = "document.querySelector('em[class=ccH5TimeTotal]').textContent"
            played_time = await self.execute_js(played_time_js)
            total_time = await self.execute_js(total_time_js)
        except:
            # 没有找到已经播放完的时间
            self.logger.error("没有获取到时间，页面出现异常！")
        else:
            ret = played_time, total_time
        return ret

    async def _get_content_name(self):
        content_name_elem = await self.get_elem_by_xpath("//div[@class='step green']//span[@class='step_top_name']")
        return await content_name_elem.text_content() if content_name_elem else ""

    async def _handle_pause(self):
        await self.play_video("div.CCH5playerContainer video")
        btn_confirm = await self.get_elem_by_css("div.el-message-box__btns button:last-child")
        if btn_confirm and await btn_confirm.is_visible():
            await btn_confirm.click()

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _is_course_finished(self):
        """
        判断课程是否完成
        :return:
        """
        # url = f"http://cas.study.yanxiu.jsyxsq.com/api/newCourse/courseDetail?stageId={self.stage_id}&courseId={self.course_id}"
        url = f"http://cas.study.yanxiu.jsyxsq.com/api/newCourse/courseDetail?courseId={self.course_id}"
        response = await self.context.request.get(url, headers=self.headers)
        response_json = await response.json()
        data = response_json.get("data", {})
        study_seconds = data.get("studySecond")
        duration = data.get("duration") * 60
        return study_seconds >= duration, study_seconds

    def extract_id_and_stageid(self, url: str):
        """
        从指定URL中提取 id 和 stageId
        :param url: 带参数的完整链接
        :return: 字典 {id: xxx, stageId: xxx}，无参数则为None
        """
        # 解析URL，分离 # 后面的 fragment 部分
        parsed = urlparse(url)
        # 解析 fragment 里的查询参数
        query_params = parse_qs(parsed.fragment)

        # 提取参数，parse_qs 返回的是列表，取第一个值
        course_id = query_params.get('id', [None])[0]
        stage_id = query_params.get('stageId', [None])[0]

        return course_id, stage_id
