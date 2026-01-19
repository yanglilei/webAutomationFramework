import time
from dataclasses import dataclass
from typing import Dict, Any

from selenium.webdriver.remote.webelement import WebElement

from src.frame.base.base_monitor_course_node import BaseMonitorCourseTaskNode


@dataclass
class HXJYWMonitorCourse(BaseMonitorCourseTaskNode):
    """
    海西教育网正常版，需要播放学完全部视频和文档
    """
    project_code: str = ""  # 项目编码
    content_name: str = ""  # 目录名称
    is_cur_content_contains_video: bool = False  # 当前目录下是否有视频

    def handle_prev_output(self, prev_output: Dict[str, Any]):
        project_code = prev_output.get("project_code", "")
        if project_code and project_code.strip():
            self.project_code = project_code.strip()

    def single_poll_monitor(self):
        # 处理弹窗大问题，各种弹窗！先处理弹窗问题，免得弹窗掩盖了课程时间，导致课程时间取不到
        self._handle_content_pause_tips()
        if self._handle_content_finished_tips():
            # 等待蒙版消息
            time.sleep(2)

        # 处理“我还在听”
        self._handle_i_am_here()
        # 处理被暂停，莫名的
        self._handle_pause()

        if self.is_cur_content_contains_video:
            # 当前目录下有视频，处理逻辑和无视频不一样
            is_finished, played_time, total_time = self._is_cur_content_finished()
            if is_finished:
                # 读完之后需要点击“OK，我知道了！”按钮
                self._handle_content_finished_tips()
                self.logger.info(
                    "用户【%s】【%s】学习完成，准备切换到一个目录..." % (self.username_showed, self.content_name))
                self._switch_to_next_content()
            else:
                if not total_time:
                    # 没有获取到时间，刷新页面
                    self.logger.info("用户【%s】【%s】没有获取到时间，重启！" % (self.username_showed, self.content_name))
                    self.terminate("视频没有获取到时间，需重启！")
                else:
                    # 有可能存在一种情况：播放时间和总时间不相等，但是弹出了课程结束的提示。
                    if self._handle_content_finished_tips():
                        self.logger.info("用户【%s】【%s】学习完成，准备切换到一个目录..." % (
                            self.username_showed, self.content_name))
                        self._switch_to_next_content()
                    else:
                        self._handle_pause()
                        # 当前视频未结束
                        self.logger.info("用户【%s】【%s】总时长%s，已学习%s" % (
                            self.username_showed, self.content_name, total_time, played_time))
        else:
            # 挂机，等时间满足
            learned_time_elem = self.get_elem_with_wait_by_xpath(3, "//span[@id='courseStudyMinutesNumber']")
            finished_tips_elem = self.get_elem_with_wait_by_xpath(3, "//span[@id='bestMinutesTips']",False)
            if finished_tips_elem and finished_tips_elem.is_displayed():
                # 课程已学完
                self.logger.info("用户【%s】【%s】中达到最大学习时间，跳过学习" % (self.username_showed, self.course_name))
                self.terminate("已学完！")
            else:
                # 视频都学完了，但是时间未满足！
                self.logger.info("用户【%s】【%s】（挂），已学习时间：%s分钟" % (
                    self.username_showed, self.course_name, learned_time_elem.text))


    def _is_current_course_finished(self):
        finished_tips_elem = self.get_elem_with_wait_by_xpath(3, "//span[@id='bestMinutesTips']", False)
        return True if finished_tips_elem and finished_tips_elem.is_displayed() else False

    def _handle_content_pause_tips(self):
        confirm_btn = self.get_elem_by_xpath(
            "//div[contains(@class,'layui-layer layui-layer-dialog')][.//*[contains(text(),'视频暂停')]]//a[text()='Ok，我知道了！']")

        if confirm_btn and confirm_btn.is_enabled() and confirm_btn.is_displayed():
            try:
                confirm_btn.click()
            except:
                pass
            else:
                # 等待确认按钮消失
                self.wait_for_disappeared(2, confirm_btn)
                # 等待蒙版消失
                self._wait_for_shade_disappear()

    def _handle_content_finished_tips(self):
        ret = False
        xpath = "//div[contains(@class,'layui-layer layui-layer-dialog')][.//*[contains(text(),'视频已播放完成')]]//a[text()='Ok，我知道了！']"
        if "hxwysqy2025" in self.project_code:
            xpath = "//div[contains(@class,'layui-layer layui-layer-dialog')]//a[text()='Ok，我知道了！']"

        confirm_btn = self.get_elem_by_xpath(xpath)
        if confirm_btn and confirm_btn.is_enabled() and confirm_btn.is_displayed():
            confirm_btn.click()
            # 等待对话框消失
            self.wait_for_disappeared(2, confirm_btn)
            # 等待蒙版消失
            self._wait_for_shade_disappear()
            ret = True
        return ret

    def prepare_before_poll_monitor_course(self):
        self.content_name = self._get_content_name(self._get_first_content())
        self.is_cur_content_contains_video = self._is_cur_content_contains_video()

    def _wait_for_shade_disappear(self):
        self.wait_for_disappeared_by_xpath(2, "//div[@class='layui-layer-shade']")

    def _handle_i_am_here(self):
        # 处理弹窗“你还在认真学习吗？”
        # 先处理视频倍暂停的弹窗提示
        # if "xy" in self.project_code:
        #     if self.get_elem((By.XPATH, "//div[@id='layui-layer1']")):
        #         # 弹出了“你还在认真学习吗？”的对话框
        #         verify_code_val = self.web_browser.find_element(By.XPATH,
        #                                                         Constants.FJHX_VERIFY_CODE_TEXT_IN_ALERT_XPATH).text
        #         self.web_browser.find_element(By.XPATH, Constants.FJHX_VERIFY_CODE_INPUT_IN_ALERT_XPATH).send_keys(
        #             verify_code_val)
        #         self.web_browser.find_element(By.XPATH, Constants.FJHX_COMMIT_BTN_IN_ALERT_XPATH).click()
        #         self.logger.info("用户【%s】处理“您还在认真学习吗？“弹窗成功" % self.username_showed)
        # else:
        #     if continue_learn := self._get_i_am_here_alert():
        #         if continue_learn.is_displayed():
        #             continue_learn.click()
        if self.get_elem_by_xpath("//div[contains(@class,'layui-layer layui-layer-page')]"):
            # 弹出了“你还在认真学习吗？”的对话框
            verify_code_val = self.get_elem_by_xpath(
                "//div[contains(@class,'layui-layer layui-layer-page')]//span[@id='codespan']").text
            self.get_elem_by_xpath(
                "//div[contains(@class,'layui-layer layui-layer-page')]//input[@id='code']").send_keys(
                verify_code_val)
            self.get_elem_by_xpath("//div[contains(@class,'layui-layer layui-layer-page')]//a[text()='提交']").click()
            self.logger.info("用户【%s】处理“您还在认真学习吗？“弹窗成功" % self.username_showed)

    def _handle_pause(self):
        # 点击弹窗中的确认按钮之后，再点击播放按钮，视频才能正常播放
        self._play_video()

    def _play_video(self):
        self.execute_js("""let css_expr = 'div.ccH5playerBox video';
    let video = document.querySelector(css_expr);
    if (video != null && !video.muted) {
    	video.muted = true;
    }

    css_expr = 'div#replaybtn';
    let play_button = document.querySelector(css_expr);
    if (play_button != null && play_button.offsetParent !== null) {
    	play_button.click();
    }""")

    def _is_cur_content_contains_video(self):
        return True if self.get_elem_with_wait_by_xpath(3, "//div[@class='ccH5playerBox']", False) else False

    def _is_cur_content_finished(self):
        ret = False
        # 在正常学习的状态
        played_time, total_time = self._get_played_time_and_total_time()
        if played_time is not None and total_time is not None and len(played_time) > 0 and len(total_time) > 0 \
                and total_time != "00:00" \
                and (played_time if played_time.count(":") == 2 else "00:" + played_time) >= (
                total_time if total_time.count(":") == 2 else "00:" + total_time):
            # 时间相等了，说明已经播放完成
            ret = True
        return ret, played_time, total_time

    def _get_played_time_and_total_time(self):
        ret = None, None
        try:
            played_time_js = "return document.querySelector('div[class=ccH5Time] :nth-child(1)').textContent"
            total_time_js = "return document.querySelector('div[class=ccH5Time] :nth-child(3)').textContent"
            played_time = self.web_browser.execute_script(played_time_js)
            total_time = self.web_browser.execute_script(total_time_js)
        except:
            # 没有找到已经播放完的时间
            self.logger.error("用户【%s】【%s】没有获取到时间，页面出现异常！" % (self.username_showed, self.content_name))
        else:
            ret = played_time, total_time
        return ret

    def _get_first_content(self):
        if "hxwysqy2025" in self.project_code:
            contents = self.get_elems_with_wait_by_xpath(10,
                                                         "(//li[contains(@class, 'isStudy')])[last()]//following::li[contains(@class, 'type_1')]")
            if contents:
                first_content = contents[0]
                if not first_content.is_displayed():
                    first_content.location_once_scrolled_into_view
                return first_content
            else:
                return None
        else:
            first_content = self.get_elem_with_wait_by_xpath(3,
                                                             "//div[@class='course-list-con']//li[contains(@class, 'cur')]//a",
                                                             False)
            if first_content and not first_content.is_displayed():
                first_content.location_once_scrolled_into_view
                time.sleep(1)
            return first_content

    def _get_content_name(self, cur_content):
        ret = ""
        if not cur_content:
            self.logger.error("用户【%s】没有获取到当前课程，页面出现异常！" % (self.username_showed,))
            return ret
        if "hxwysqy2025" in self.project_code:
            ret = cur_content.get_attribute("title")
        else:
            course_name_elem = self.get_elem_with_wait_by_xpath(5, "//div[@class='course-info']//a")
            if not course_name_elem:
                self.logger.error("用户【%s】没有获取到课程名称，页面出现异常！" % (self.username_showed,))
            else:
                ret = course_name_elem.text + "(" + cur_content.text + ")"
        return ret

    def _switch_to_next_content(self):
        # 判断当前课程是否结束
        next_content = self._get_next_content()
        if not next_content:
            # 当做无视频处理
            self.is_cur_content_contains_video = False
        else:
            self.content_name = self._get_content_name(next_content)
            # 点击前需要再次判断是否有弹窗提示等等
            self._handle_content_finished_tips()
            # 点击下一个目录
            # 注意！当点击的时候会刷新页面，导致元素过期，后续不能再操作next_content元素
            next_content.click()
            self.cur_content_start_time = int(time.time())

            # 判断是否有视频，有视频：点击播放视频；没有视频-则不处理
            if self._is_cur_content_contains_video():
                self.is_cur_content_contains_video = True
                # 当前目录下有视频
                # 学习
                self._play_video()
                # 2倍播放
                # self._double_speed_play()
            else:
                self.is_cur_content_contains_video = False

    def _get_next_content(self) -> WebElement:
        # 返回第一个视频课程
        if "hxwysqy2025" in self.project_code:
            return self.get_elem_with_wait_by_xpath(3, "(//li[contains(@class, 'type_1') and contains(@class, 'isStudy')])[last()]//following::li[contains(@class, 'type_1')]")
        else:
            return self._get_first_content()
