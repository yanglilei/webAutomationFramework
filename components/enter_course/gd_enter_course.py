import asyncio
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from PIL import Image
from PIL.Image import Image
from playwright.async_api import Page, FrameLocator

from src.frame.base import BaseEnterCourseTaskNode
from src.frame.common.exceptions import BusinessException
from src.utils import SliderVerifyUtils, SysPathUtils


@dataclass(init=False)
class GDEnterCourse(BaseEnterCourseTaskNode):
    main_window_url: str = ""
    # 专题名称
    subject_name: str = ""
    # 专题页面
    course_page_window_handler: Page = None
    # 签到
    sign_in_flag: bool = False
    # 目录名称
    content_name: str = ""
    # 是否为拓展阅读
    is_expand_reading: bool = False
    # 是否观看视频
    is_watch_video: bool = False
    # 滑块验证码的滑块图片保存位置
    target_img_path: str = ""
    # 滑块验证码的背景图片保存位置
    background_img_path: str = ""

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        # 滑块验证码的滑块图片保存位置
        self.target_img_path = str(Path(SysPathUtils.get_tmp_file_dir(), self.username + "_2.png"))
        # 滑块验证码的背景图片保存位置
        self.background_img_path = str(Path(SysPathUtils.get_tmp_file_dir(), self.username + "_1.png"))
        self.subject_name = self.node_config.get("node_params", {}).get("subject_name")
        if not self.subject_name:
            return False, "没有指定专题名称：subject_name"
        self.main_window_url = await self.get_current_url()

        # 定位课程
        await self.enter_subject()
        await asyncio.sleep(2)
        await self.switch_to_window_by_url_key("mycourse")
        self.course_page_window_handler = self.get_current_page()
        await self.handle_tips()

        # 减慢速度
        await asyncio.sleep(random.randint(1, 3))
        self.set_output_data("course_page", self.course_page_window_handler)

        # 签到
        if not self.sign_in_flag:
            await self.sign_in()

        # 进入章节页面
        return await self.enter_chapters()

    async def enter_course(self) -> Tuple[bool, str]:
        return True, ""

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        await self.refresh()
        return True, ""

    async def enter_subject(self):
        course_tab = await self.get_elem_with_wait_by_xpath(20, "//div[@name='课程']", False)
        if course_tab:
            try:
                await self.js_click(course_tab)
            except:
                self.logger.error("进入课程页面失败")
                raise
            else:
                await asyncio.sleep(2)
                # self.web_browser.switch_to.default_content()
                # self.web_browser.switch_to.frame(0)
                iframe = self.switch_to_frame("iframe#frame_content")
                my_learn_course_tab = await self.get_elem_with_wait_by_xpath(20, "//div[contains(text(),'我学的课')]",
                                                                             iframe=iframe)
                if not my_learn_course_tab:
                    self.logger.error("没有加载出“我学的课”页面异常")
                    raise BusinessException("页面加载异常")

                if "current" not in await my_learn_course_tab.get_attribute("class"):
                    try:
                        await self.js_click(my_learn_course_tab)
                        # my_learn_course_tab.click()
                    except:
                        self.logger.error("进入“我学的课”失败")
                        raise
                await asyncio.sleep(2)
                target_course = await self.get_elem_with_wait_by_xpath(5,
                                                                       f"//span[contains(text(), '{self.subject_name}')]",
                                                                       iframe=iframe)
                if not target_course:
                    raise BusinessException("没有找到目标课程")
                try:
                    await self.js_click(target_course)
                except:
                    self.logger.exception("点击进入课程失败")
                    raise BusinessException("点击进入课程失败")
        else:
            self.logger.error("没有找到“课程”按钮")
            raise BusinessException("没有找到“课程”按钮")

    async def handle_tips(self):
        tips_window = await self.get_elem_by_xpath("//div[@class='commitment-content-dialog']")
        if tips_window and await tips_window.is_visible():
            i_am_read_cb = await self.get_elem_by_xpath("//input[@id='learnCommit-bottom-div']")
            if i_am_read_cb:
                # i_am_read_cb.click()
                await self.js_click(i_am_read_cb)
                start_learn_btn = await self.get_elem_by_xpath("//a[text()='开始学习'][2]")
                if start_learn_btn:
                    # start_learn_btn.click()
                    await self.js_click(start_learn_btn)
                    await self.wait_for_disappeared(10, tips_window)
                    # self.wait_for_disappeared(10, tips_window)

    async def enter_chapters(self):
        ret = True, ""
        chapter_tab_elem = await self.get_elem_by_xpath("//a[@title='章节']")
        if not chapter_tab_elem:
            self.logger.error("没有找到“章节”按钮")
            ret = False, "没有找到“章节”按钮"

        else:
            await self.js_click(chapter_tab_elem)
            # 找到第一个目录并且点击进入到章节详情页面
            await asyncio.sleep(2)

            first_unfinished_content = await self._get_first_unfinished_content()
            if first_unfinished_content:
                if not await first_unfinished_content.is_visible():
                    await first_unfinished_content.scroll_into_view_if_needed()
                # first_unfinished_content.click()
                await self.js_click(first_unfinished_content)
                await asyncio.sleep(2)
                # content_name_elem = await self.get_elem_with_wait_by_xpath(10, "//div[@class='prev_title']")
                # self.content_name = await content_name_elem.text_content()
                # if self.content_name == "拓展阅读":
                #     self.is_expand_reading = True
                #     self.is_watch_video = False
                #     await self.read()
                #     self.cur_content_start_time = int(time.time())
                # elif self._is_cur_content_contains_video():
                #     self.is_watch_video = True
                #     self.is_expand_reading = False
                #     # 播放视频
                #     await self._play_video()
                #     self.cur_content_start_time = int(time.time())
                # else:
                #     self.is_watch_video = False
                #     self.is_expand_reading = False
                #     self.cur_content_start_time = int(time.time())
            else:
                self.logger.info("没有未学的课程，任务退出")
                ret = False, "已学完"
        return ret

    async def _get_first_unfinished_content(self):
        iframe = self.switch_to_frame("iframe#frame_content-zj")
        first_unfinished_content = await self.get_elem_with_wait_by_xpath(5,
                                                                          "(//div[@class='catalog_title'][.//div[contains(@class,'catalog_tishi120')]])[1]",
                                                                          iframe=iframe)
        return first_unfinished_content

    async def read(self):
        # iframes = self.get_elems((By.TAG_NAME, "iframe"))
        outer_iframe = self.switch_to_frame("iframe#iframe")
        iframe1 = self.switch_to_frame("iframe", outer_iframe)
        iframe2 = self.switch_to_frame("iframe#frame_content", iframe1)
        read_btn = await self.get_elem_by_xpath("//span[text()='去阅读']", iframe=iframe2)
        # self.web_browser.maximize_window()
        # time.sleep(2)
        # self.web_browser.save_screenshot(os.path.join(os.getcwd(), self.username + "-error" + str(
        #     random.randint(0, 100000)) + ".png"))

        if read_btn:
            await self.js_click(read_btn)
            await asyncio.sleep(3)
            await self.switch_to_window_by_url_key("mooc-ans/course")
            first_chapter = await self.get_elem_with_wait_by_xpath(10,
                                                                   "(//ul//div[contains(@class,'chapterText')])[1]")
            if first_chapter:
                if not await first_chapter.is_visible():
                    await first_chapter.scroll_into_view_if_needed()
                    await asyncio.sleep(1)
                try:
                    await self.js_click(first_chapter)
                except:
                    pass
        else:
            self.logger.error("在“拓展阅读”页面没有找到“去阅读”的按钮，请人工介入检查，退出学习")
            self.terminate("页面异常", True)

    async def _is_cur_content_contains_video(self):
        ret = False
        outer_iframe = self.switch_to_frame("iframe#iframe")
        if len(await self.get_elems_by_css("iframe", outer_iframe)) > 0:
            ret = await self.is_elem_exists_by_xpath("//video", self.switch_to_frame("iframe", outer_iframe))
        return ret

    async def _play_video(self):
        outer_iframe = self.switch_to_frame("iframe#iframe")
        iframe = self.switch_to_frame("iframe", outer_iframe)
        play_btn = await self.get_elem_with_wait_by_xpath(4, "//button[@class='vjs-big-play-button']", True, iframe)
        if play_btn:
            await play_btn.click()
            # self.execute_js("arguments[0].click()", play_btn)

    async def sign_in(self):
        task_tab_elem = await self.get_elem_with_wait_by_xpath(5, "//a[@title='任务']")
        if task_tab_elem:
            await self.js_click(task_tab_elem)
        else:
            self.logger.error("没有找到到签到“任务”的标签，网络问题或者页面有变动")

        await asyncio.sleep(2)
        # 切换iframe
        outer_iframe = self.switch_to_frame("iframe#frame_content-hd")
        sign_in_elem = await self.get_elem_with_wait_by_xpath(3, "//li[@activestatus='1'][.//div[@aria-label='签到']]",
                                                              iframe=outer_iframe)
        if sign_in_elem:
            await self.js_click(sign_in_elem)
            await asyncio.sleep(2)
            # sign_in_elem.click()
            iframe = self.switch_to_frame("iframe#frame_content-hd")

            if await self.get_elem_with_wait_by_xpath(2, "//div[@class='sign-icon-con']", iframe=iframe):
                self.logger.info("✅已签到")
                await self._update_sign_time(iframe)
            else:
                # 签到
                if sign_btn_elem := await self.is_elem_exists_with_wait_by_xpath(3, "//div[@id='signButton']",
                                                                                 iframe=iframe):
                    await self.js_click(sign_btn_elem)
                    if await self.get_elem_with_wait_by_xpath(3, "//div[@id='eject']", True, iframe):
                        if await self._handler_slider(iframe):
                            if await self.is_elem_exists_with_wait_by_xpath(2, "//div[@id='signSuccessed']", iframe):
                                self.logger.info(f"✅签到成功")
                                await self._update_sign_time(iframe)
                            else:
                                self.logger.error(f"❌签到异常，请人工介入检查")
                        else:
                            self.logger.info(f"❌签到失败，滑块验证失败")
                    else:
                        self.logger.info(f"✅签到成功")
                        await self._update_sign_time(iframe)
                else:
                    self.logger.error("❌签到失败，没有找到签到按钮，请手动签到")

        else:
            self.logger.info("当天已签到！")
            self.sign_in_flag = True

    async def _update_sign_time(self, iframe):
        sign_time_elem = await self.get_elem_by_xpath("//p[contains(@class,'sign-time')]", iframe=iframe)
        sign_time_text = await sign_time_elem.text_content() if sign_time_elem else ""
        if self.user_manager:
            self.user_manager.update_record_by_username(self.username, {5: f"签到成功：{sign_time_text}"})

    async def _handler_slider(self, iframe: FrameLocator):
        count = 0
        ret = False
        while True:
            if count == 20:
                self.logger.error("滑块验证码，验证失败达20次，请人工介入检查")
                ret = False
                break
            else:
                count = count + 1
                # 获取滑动的图片
                target_img_elem = await self.get_elem_with_wait_by_xpath(3, "//div[@class='cx_imgBtn']/img",
                                                                         iframe=iframe)
                file_url = await target_img_elem.get_attribute("src")
                headers = {"Cookie": self.cookie_to_str(), "Content-Type": "application/json;charset=utf-8",
                           "User-Agent": self.user_agent()}
                img = await self.context.request.get(file_url, headers=headers)
                with open(self.target_img_path, "wb") as f:
                    f.write(await img.body())
                # 获取背景图片
                slider_background_elem = await self.get_elem_by_xpath("//canvas[@id='cx_obstacle_canvas']", iframe)
                await self.screenshot(self.background_img_path, slider_background_elem)

                # 截图验证码模块
                ret = self._shot_img(self.background_img_path, self.background_img_path,
                                     50 + 1, 0,
                                     320,
                                     160)
                if not ret:
                    # 截图保存失败
                    self.logger.error("请检查滑块图片的路径是否存在！")
                    ret = False
                    break
                else:
                    # 计算滑块到缺口的距离
                    try:
                        x = SliderVerifyUtils.cal_gap_x_distance_with_gap_img(self.background_img_path,
                                                                              self.target_img_path)
                    except:
                        self.logger.error("计算滑块和缺口的距离失败，原因：", exc_info=True)
                        ret = False
                        break
                    # 滑块需要移动的距离。移动的距离需要加上按钮的一半宽度，因为鼠标拖动按钮一半的距离之后，按钮才会动起来！所以实际鼠标要移动的距离要加上按钮的一半宽度
                    move_x = 50 + x + 10

                slider_btn_elem = await self.get_elem_with_wait_by_xpath(3, "//div[contains(@class, 'cx_rightBtn')]",
                                                                         visible=True, iframe=iframe)
                SliderVerifyUtils.move_slider_slowly(move_x, slider_btn_elem, self.get_current_page())

                await self.wait_for_disappeared(3, "//div[@id='eject']", context=iframe)
                if await self.get_elem_by_xpath("//div[@id='eject']", iframe=iframe):
                    ret = False
                    self.logger.info(f"签到，滑块验证失败，重试次数：{count}")
                else:
                    ret = True
                    break

        return ret

    def _shot_img(self, src_img_path, save_path, left, upper, right, lower):
        """
        截图
        :param src_img_path: 原始图片路径
        :param save_path:截图后保存的路径
        :param left:左边坐标
        :param upper:上方坐标
        :param right:右边坐标
        :param lower:下方坐标
        :return:bool True-截图保存成功；False-截图保存失败
        """
        ret = True
        img = None
        region = None
        try:
            img = Image.open(src_img_path)
            region = img.crop((left, upper, right, lower))
            region.save(save_path)
        except:
            self.logger.error("截图失败，原因：", exc_info=True)
            ret = False
        finally:
            if img is not None:
                img.close()
            if region is not None:
                region.close()
        return ret

    # def _handler_slider(self):
    #     count = 0
    #     ret = False
    #
    #     while True:
    #         self.web_browser.switch_to.default_content()
    #         self.web_browser.switch_to.frame("frame_content-hd")
    #         if count == 20:
    #             self.logger.error("滑块验证码，验证失败达20次，请人工介入检查")
    #             ret = False
    #             break
    #         else:
    #             count = count + 1
    #             try:
    #                 ac = ActionChains(self.web_browser)
    #             except:
    #                 self.logger.exception("没有找到滑块验证码的按钮，可能页面未加载完，尝试重新查找")
    #                 continue
    #             else:
    #                 # ac.move_to_element(slider_btn_elem)
    #                 # 有时候滑块不出来
    #                 slider_btn_elem = self.get_elem_with_wait(3, (By.XPATH, "//div[contains(@class, 'cx_rightBtn')]"), visible=True)
    #                 ac.click_and_hold(slider_btn_elem).perform()
    #                 t = "//div[@class='cx_imgBtn']/img"
    #                 target_img_elem = self.get_elem_with_wait(3, (By.XPATH, t))
    #                 file_url = target_img_elem.get_attribute("src")
    #                 headers = {"Cookie": self.cookie_to_str(), "Content-Type": "application/json;charset=utf-8",
    #                            "User-Agent": self.user_agent()}
    #                 img = requests.get(file_url, headers=headers)
    #                 with open(self.target_img_path, "wb") as f:
    #                     f.write(img.content)
    #
    #                 # 弹出了滑块验证码
    #                 self.web_browser.find_element(By.XPATH, "//canvas[@id='cx_obstacle_canvas']").screenshot(
    #                     self.background_img_path)
    #                 # 截图验证码模块
    #                 ret = self._shot_img(self.background_img_path, self.background_img_path,
    #                                      Constants.FJRC_SLIDER_TARGET_IMG_WIDTH + 1, 0,
    #                                      320,
    #                                      160)
    #                 if not ret:
    #                     # 截图保存失败
    #                     self.logger.error("请检查滑块图片的路径是否存在！")
    #                     ret = False
    #                     break
    #                 else:
    #                     # 计算滑块到缺口的距离
    #                     try:
    #                         x = self._cal_distance(self.target_img_path, self.background_img_path)
    #                     except:
    #                         self.logger.error("计算滑块和缺口的距离失败，原因：", exc_info=True)
    #                         ret = False
    #                         break
    #                     # 滑块需要移动的距离。移动的距离需要加上按钮的一半宽度，因为鼠标拖动按钮一半的距离之后，按钮才会动起来！所以实际鼠标要移动的距离要加上按钮的一半宽度
    #                     move_x = Constants.FJRC_SLIDER_TARGET_IMG_WIDTH + x + 10
    #
    #                     ac.move_by_offset(move_x, 0).perform()
    #                     time.sleep(1.5)
    #                     ac.release().perform()
    #                     self.wait_for_disappeared(3, (By.XPATH, "//div[@id='eject']"))
    #                     if self.get_elem((By.XPATH, "//div[@id='eject']")):
    #                         ret = False
    #                         self.logger.info(f"用户【{self.username_covered}】签到，滑块验证失败，重试次数：{count}")
    #                     else:
    #                         ret = True
    #                         # self.logger.info(f"用户【{self.username_covered}】签到，滑块验证成功，签到成功")
    #                         break
    #     return ret
