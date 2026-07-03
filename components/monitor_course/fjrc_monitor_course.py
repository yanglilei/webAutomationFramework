import asyncio
from dataclasses import dataclass

import time

from src.frame.base import BaseMonitorCourseTaskNode


@dataclass(init=False)
class FJRCMonitorCourse(BaseMonitorCourseTaskNode):
    content_name: str = ""
    # 线程启动的时间。用于判断学习过程中是否卡住了。实际时间有更新，但是学习时间没有更新，则认为当前学习卡住了。需要刷新页面或者重启学习线程。
    first_sys_time: int = 0
    cur_sys_time: int = 0
    # 第一次计算时间的标志
    first_cal_time_flag: bool = True
    pre_learned_time: int = 0
    cur_learned_time: int = 0
    # 是否需要刷新页面
    is_page_load_error: bool = False
    pre_refresh_time: int = 0
    cur_refresh_time: int = 0

    async def prepare_before_poll_monitor_course(self):
        self.content_name = self.course_name

    async def single_poll_monitor(self):
        # 处理一天学习太多的弹窗
        if await self.is_elem_visible_by_xpath(
                "//div[@class='layer-un-package-cont'][.//div[contains(text(), '您太勤奋了')]]"):
            # 退出学习
            self.logger.info("今天学习太多了，退出学习...")
            self.terminate("学习太多", True)
            return

        # 处理非正常关闭其他课件
        if btn_play := await self.is_elem_visible_by_xpath("//a[@id='mutableAlertViewOk']"):
            await asyncio.sleep(1)
            await btn_play.click()

        # //a[@class='btnOk packageGoBtn']
        if btn_play := await self.is_elem_visible_by_xpath("//a[@class='btnOk packageGoBtn']"):
            await asyncio.sleep(1)
            await btn_play.click()

        await self.play_video("div#video video.pv-video")

        # 窗口正常打开的情况
        # 切换到新窗口
        is_finished, played_time, total_time = await self._is_cur_content_finished()
        if is_finished:
            # 时间相等了，说明已经播放完成
            self.logger.info("已经学习完，准备切到下一个目录...")
            self.terminate("已学完")
            return

        # 目前目录未学习完成，
        # 检查学习过程中是否有弹窗等异常信息
        # 目前课程不会出现弹窗，所以不处理
        # if not self.content_name:
        #     # 目录名称为空的话则，重新获取目录名称
        #     self.content_name = await self._get_content_name()

        self.logger.info("【%s】总共%s，已学习%s" % (self.content_name, total_time, played_time))
        # 判断有没有异常出现
        # played_time: str = self._get_played_time_and_total_time()[0]
        if not played_time or not total_time:
            # 获取时间失败，判断用户是否在线
            if not await self._is_user_online():
                self.logger.error("可能在别处登录了，退出学习！")
                # self.stop_learning_flag = True
                # FJRCLearningTaskMonitor.instance().remove_task(self)
                self.terminate("在别处登录", True)
                return

            if not self.is_page_load_error:
                self.is_page_load_error = True
                self.pre_refresh_time = int(time.time())
            else:
                self.cur_refresh_time = int(time.time())
                if self.cur_refresh_time - self.pre_refresh_time > 60:
                    self.is_page_load_error = False
                    # 获取时间失败（页面卡住每刷新出来），则重启该页面
                    self.logger.info("【%s】获取时间失败，准备重启..." % self.content_name)
                    # 退出当前的监听轮训，外部会重启
                    self.pre_refresh_time = 0
                    self.cur_refresh_time = 0
                    self.terminate("获取视频时间失败！")
                    return
        else:
            self.is_page_load_error = False
            time_segs = played_time.split(":")
            if self.first_cal_time_flag:
                hour = 0
                minute = time_segs[0]
                seconds = time_segs[1]
                if len(time_segs) > 2:
                    hour = time_segs[0]
                    minute = time_segs[1]
                    seconds = time_segs[2]

                self.first_sys_time = int(time.time())
                self.pre_learned_time = int(hour) * 3600 + int(minute) * 60 + int(seconds)
                self.first_cal_time_flag = False
            else:
                hour = 0
                minute = time_segs[0]
                seconds = time_segs[1]
                if len(time_segs) > 2:
                    hour = time_segs[0]
                    minute = time_segs[1]
                    seconds = time_segs[2]

                self.cur_sys_time = int(time.time())
                # 计算时间过去了多久，单位秒
                sys_time_span = self.cur_sys_time - self.first_sys_time
                self.cur_learned_time = int(hour) * 3600 + int(minute) * 60 + int(seconds)
                learned_time_span = self.cur_learned_time - self.pre_learned_time
                content_name = await self._get_content_name()

                if sys_time_span - learned_time_span > 60 and learned_time_span == 0 and self.content_name == content_name:
                    # 1分钟了，学习时间没有更新了，则重启该页面
                    self.logger.info("【%s】卡住1分钟了，准备重启..." % self.content_name)
                    # 退出当前的监听轮训，外部会重启
                    self.cur_learned_time = 0
                    self.pre_learned_time = 0
                    self.cur_sys_time = 0
                    self.first_sys_time = 0
                    self.first_cal_time_flag = True
                    self.terminate("学习时间没有更新！")
                    return

                if self.content_name != content_name:
                    # TODO 发现切换了目录，则要结束当前目录，退出后继续学习下一个目录，外部有对课程的类型进行判断，不是所有的课程都是看视频，也有做测验，需要另外处理！！！
                    # TODO pause by zcy 20260616
                    self.logger.info(f"【{self.content_name}】已学习完，自动切到下一个目录【{content_name}】")
                    self.content_name = content_name
                    return

    async def _is_cur_content_finished(self):
        ret = False
        # 在正常学习的状态
        played_time, total_time = await self._get_played_time_and_total_time()
        if played_time is not None and total_time is not None and len(played_time) > 0 and len(total_time) > 0 \
                and played_time == total_time:
            ret = True
        return ret, played_time, total_time

    async def _get_played_time_and_total_time(self):
        ret = None, None
        try:
            played_time_js = "document.querySelector(\"%s\").textContent" % "div[class='pv-time-wrap pv-xxsmall-hide'] span:nth-child(1)"
            total_time_js = "document.querySelector(\"%s\").textContent" % "div[class='pv-time-wrap pv-xxsmall-hide'] span:nth-child(3)"
            played_time = await self.execute_js(played_time_js)
            total_time = await self.execute_js(total_time_js)
        except:
            # 没有找到已经播放完的时间
            self.logger.error("【%s】没有获取到时间，页面出现异常！" % self.content_name)
        else:
            ret = played_time, total_time
        return ret

    async def _get_content_name(self):
        ret = None
        try:
            ret = await self.get_elem_with_wait_by_xpath(5, "//em[@id='shipin']")
        except:
            self.logger.error("【%s】没有获取到课程名称，页面出现异常！" % self.content_name)
        else:
            ret = await ret.text_content()
        return ret

    async def _is_user_online(self):
        """
        检测客户在学习过程中是否出现了会话过期
        :return:
        """
        # 页面跳回到首页，则会话过期了，账号在别处登录
        return "https://fj.rcpxpt.com/" != await self.get_current_url()