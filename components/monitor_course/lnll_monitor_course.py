import asyncio
import random
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from playwright.async_api import Page
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.frame.base import BaseMonitorCourseTaskNode
from src.frame.common.exceptions import BusinessException
from src.utils import SysPathUtils


@dataclass(init=False)
class LNLLMonitorCourse(BaseMonitorCourseTaskNode):
    # 获取视频播放进度失败的次数
    fail_to_get_video_progress_count: int = 0
    # 域名
    net_location: str = ""
    # 第一次计算时间的标志
    first_cal_time_flag: bool = True
    # 前一次的视频进度
    pre_video_progress: str = ""
    # 第一次获取视频进度的时间
    first_sys_time: int = 0
    # 视频名称
    content_name: str = ""
    # 视频页面
    video_page_window_handler: Page = ""

    async def prepare_before_poll_monitor_course(self):
        self.net_location = self.get_prev_output().get("net_location")
        if not self.net_location:
            raise BusinessException("没有从上一个节点获取到网络地址")

        self.video_page_window_handler = self.get_prev_output().get("video_page_window_handler")
        await self.switch_to_window(self.video_page_window_handler)

    async def single_poll_monitor(self):
        # 处理弹窗大问题，各种弹窗！先处理弹窗问题，免得弹窗掩盖了课程时间，导致课程时间取不到
        # if self.web_browser.current_window_handle != self.video_page_window_handler:
        #     self.web_browser.switch_to.window(self.video_page_window_handler)
        # 处理被暂停，莫名的
        await self._handle_pause()
        # 处理“我还在听”
        # self._handle_i_am_here()
        # 获取当前视频的进度
        self.content_name = await self._get_content_name()
        cur_video_progress = await self._get_cur_video_progress()
        if not cur_video_progress:
            self.logger.error("%s - %s 没有获取到当前视频的学习进度", self.course_name,
                              self.content_name)
            await self.screenshot(Path(SysPathUtils.get_tmp_file_dir(), self.username + "-error" + str(
                random.randint(0, 100000)) + ".png"))
            self.fail_to_get_video_progress_count += 1
            if self.fail_to_get_video_progress_count == 10:
                self.terminate("获取视频进度失败，可能网页卡死！", True)
            else:
                # 刷新页面
                await self.refresh()
                # 获取播放按钮
                # self._play_video()
                # 更新学习的目录名称
                self.content_name = await self._get_content_name()
        else:
            self.logger.info(f"【{self.content_name}】视频进度：{cur_video_progress}")
            if await self._is_cur_course_finished(cur_video_progress):
                self.terminate("课程已结束！")
                return

            if self.first_cal_time_flag:
                self.first_cal_time_flag = False
                self.pre_video_progress = cur_video_progress
                # self.cur_video_progress = cur_video_progress
                self.first_sys_time = int(time.time())
            else:
                if int(time.time()) - self.first_sys_time >= 240:
                    self.first_cal_time_flag = True
                    # 4分钟检测一次进度是否有更新
                    if self.pre_video_progress == cur_video_progress:
                        self.logger.info("卡住超过4分钟，重启页面")
                        # 重启课程，不排除该课程
                        self.set_output_data("restart_course", True)
                        self.terminate("卡住超过4分钟，重启页面！")
                        return

                    # 检查课程学习进度
                    is_completed = await self._is_current_course_completed(await self._get_current_course_id())
                    if is_completed:
                        # 切换课程
                        self.terminate("课程已结束！")
                        return

    async def _handle_pause(self):
        btn_continue_learn = await self.is_elem_visible_by_xpath(
            "//div[@class='el-dialog__wrapper']//button[./span[text()='确 定']]")
        if btn_continue_learn:
            try:
                await btn_continue_learn.click()
            except:
                self.logger.exception("点击继续学习的确定按钮失败")

    async def _get_content_name(self):
        first_content = await self.get_elem_with_wait_by_xpath(10, "//p[@class='title']")
        return await first_content.text_content() if first_content else ""

    async def _get_cur_video_progress(self):
        return await self.execute_js("""() => {
        let time_expr = document.querySelector(\"div[class*='timetext']\");
        if (time_expr) {
            return time_expr.textContent;
        } else {
            return "";
        }}""")
        # progress_elem = self.get_elem_with_wait(2, (By.XPATH, "//div[contains(@class, 'timetext')]"), visible=False)
        # return progress_elem.text if progress_elem else ""

    async def _is_cur_course_finished(self, cur_video_progress):
        ret = False
        time_segs = cur_video_progress.split("/")
        if time_segs[0].strip() == time_segs[1].strip() and time_segs[0].strip() != "00:00":
            # 判断课程进度是否为100%
            is_completed = await self._is_current_course_completed(await self._get_current_course_id())
            if not is_completed:
                # 课程读完但是进度没有达到100%，重新播放！
                replay_btn = await self.get_elem_with_wait_by_css(3, "canvas[class*='pausecenter']")
                if replay_btn:
                    try:
                        await replay_btn.click()
                    except:
                        self.logger.exception("点击暂停按钮失败")
                        raise BusinessException("点击暂停按钮失败")
                    else:
                        await asyncio.sleep(1)
                        ret = False
                else:
                    self.logger.error("视频播放完后进度没有达到100%，没有找到播放按钮，即将学习下一个视频！")
                    ret = True
            else:
                ret = True
        return ret

    @retry(retry=retry_if_exception_type((BusinessException, Exception)), stop=stop_after_attempt(5),
           wait=wait_fixed(2))
    async def _is_current_course_completed(self, course_id: str):
        url = f"https://{self.net_location}/trainee/api/course/detail/{course_id}"
        cookie = await self.cookie_to_str()
        user_agent = r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        try:
            response = await self.context.request.get(url, headers={"cookie": cookie, "user-agent": user_agent})
        except Exception as e:
            self.logger.exception(e)
            raise BusinessException("获取课程学习进度失败！")
        else:
            ret = False
            response_obj = await response.json()
            if response_obj["code"] != 0:
                raise BusinessException(f"获取未完成的课程失败，原因：{response_obj['message']}")
            else:
                progress = response_obj["data"]["course"]["learning_progress"]
                ret = progress == "100"
            return ret

    async def _get_current_course_id(self):
        return re.findall("id=([^&]+)", await self.get_current_url())[0]
