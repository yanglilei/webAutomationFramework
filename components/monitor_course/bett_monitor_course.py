import time
from dataclasses import dataclass
from pathlib import Path

from playwright.async_api import Page

from src.frame.base import BaseMonitorCourseTaskNode
from src.frame.common.sys_config import SysConfig
from src.utils import SysPathUtils


@dataclass(init=False)
class BETTMonitorCourse(BaseMonitorCourseTaskNode):
    project_id: str = ""
    course_id: str = ""
    uid: str = ""
    video_page: Page = None
    project_page: Page = None

    async def _get_course_name(self):
        course_name_elem = await self.get_elem_with_wait_by_xpath(10, "//div[@class='play_title']")
        course_name = (await course_name_elem.text_content()).split("-")[0] if course_name_elem else ""
        return course_name

    async def prepare_before_poll_monitor_course(self):
        await self.switch_to_window_by_url_key("StudyDuration/Index")
        self.video_page = self.get_current_page()

        if btn_switch := await self.get_elem_with_wait_by_xpath(5, "//a[text()='切换']"):
            await btn_switch.click()

        if not self.course_name:
            self.course_name = await self._get_course_name()

        self.project_id = self.get_prev_output().get("project_id")
        self.course_id = self.get_prev_output().get("course_id")
        self.uid = self.get_prev_output().get("uid")
        self.project_page = self.get_prev_output().get("project_page")
        # 处理暂停
        video = await self.get_elem_by_css("div.CCH5playerContainer video")
        if video and bool(await video.evaluate("el => el.paused")):
            await self.js_click(video)

    async def single_poll_monitor(self):
        # await self.play_video("div.CCH5playerContainer video")

        # 处理切换下一个视频
        btn_next_content = await self.get_elem_by_css("a.layui-layer-btn0")
        if btn_next_content and await btn_next_content.is_visible():
            await self.js_click(btn_next_content)
            return

        # 处理我在
        btn_im_here = await self.get_elem_by_css("div#divProof a.btn-ProofOk")
        if btn_im_here and await btn_im_here.is_visible():
            await self.js_click(btn_im_here)
            return

        # 处理暂停
        video = await self.get_elem_by_css("div.CCH5playerContainer video")
        # 执行JS获取 paused 属性（核心代码）
        if video and bool(await video.evaluate("el => el.paused")):
            # if await self._is_course_finished():
            #     await self.close_latest_window()
            #     self.logger.info(f"课程【{self.course_name}】已完成！准备切换到下一个课程！")
            #     self.terminate("已完成")
            #     return
            # else:
            await self.js_click(video)

        if self.poll_count % 100 == 0:
            if await self._is_course_finished_v2():
                await self.close_latest_window()
                self.logger.info(f"课程【{self.course_name}】已完成！准备切换到下一个课程！")
                self.terminate("已完成")
                return

        activate_content = await self.get_elem_by_xpath("//dd/a[@class='dd_active']")
        content_name = await activate_content.get_attribute("title") if activate_content else ""
        played_time, total_time = await self._get_played_time_and_total_time()
        self.logger.info(f"【{content_name}】播放进度：{played_time}/{total_time}")

    async def _is_course_finished(self):
        try:
            # https://vc.chinabett.com/StudyDuration/GetProgress?uid=a977c9aed998491588efddafbf3336fd&cid=a92b83780b764570bcd8b3b700f4ee58&tno=1&pid=09ea123b67c84accbb07b3bb00e60978&tim=1774576516738
            # url = f"https://vc.chinabett.com/StudyDuration/GetProgress?uid={self.uid}&cid={self.course_id}&tno=1&pid={self.project_id}&tim={int(time.time() * 1000)}"
            url = f"https://vc.chinabett.com/StudyDuration/GetProgress"
            params = {"uid": self.uid, "cid": self.course_id, "tno": 1, "pid": self.project_id,
                      "tim": int(time.time() * 1000)}
            headers = {"cookie": await self.cookie_to_str(),
                       "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
                       "referer": await self.get_current_url()}
            response = await self.get_current_page().request.get(url, params=params, headers=headers)
            val = await response.text()
            return True if val.strip() == "100" else False
        except Exception as e:
            self.logger.error(f"获取课程进度失败：{str(e)}")

    async def _is_course_finished_v2(self):
        await self.switch_to_window(self.project_page)  # 刷新防止掉线
        await self.refresh()
        await self.switch_to_window(self.video_page)
        await self.refresh()
        progress_elem = await self.get_elem_by_css("#panProgress span")
        if progress_elem:
            progress = await progress_elem.text_content()
            return True if progress.strip() == "100%" else False
        return False

    async def _get_played_time_and_total_time(self):
        ret = None, None
        try:
            played_time_js = "document.querySelector('em[class=ccH5TimeCurrent]').textContent"
            total_time_js = "document.querySelector('em[class=ccH5TimeTotal]').textContent"
            played_time = await self.execute_js(played_time_js)
            total_time = await self.execute_js(total_time_js)
        except:
            # 没有找到已经播放完的时间
            await self.screenshot(Path(SysPathUtils.get_tmp_file_dir(), f"{self.username}_{str(time.time())}.png"))
            self.logger.error("没有获取到时间，页面出现异常！")
        else:
            ret = played_time, total_time
        return ret
