import asyncio
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Dict

from PIL import Image
from PIL.Image import Image
from playwright.async_api import Page, FrameLocator

from src.frame.base.base_task_node import BasePYNode
from src.frame.common.exceptions import BusinessException
from src.utils import SliderVerifyUtils, SysPathUtils


@dataclass(init=False)
class GDSignIn(BasePYNode):
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

    async def execute(self, context: Dict) -> bool:
        # 滑块验证码的滑块图片保存位置
        self.target_img_path = str(Path(SysPathUtils.get_tmp_file_dir(), self.username + "_2.png"))
        # 滑块验证码的背景图片保存位置
        self.background_img_path = str(Path(SysPathUtils.get_tmp_file_dir(), self.username + "_1.png"))
        self.subject_name = self.node_config.get("node_params", {}).get("subject_name")
        if not self.subject_name:
            self.logger.error("没有指定专题名称：subject_name")
            return False
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

        return True

    async def enter_subject(self):
        course_tab = await self.get_elem_with_wait_by_xpath(20, "//div[@name='课程'] | //div[@name='我的课程']", False)
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

                # 计算滑块到缺口的距离
                try:
                    x = SliderVerifyUtils.cal_gap_x_pos(self.background_img_path)
                except:
                    self.logger.error("计算滑块和缺口的距离失败，原因：", exc_info=True)
                    ret = False
                    break
                target_img_elem = await self.get_elem_with_wait_by_xpath(3, "//div[@class='cx_imgBtn']/img",
                                                                         iframe=iframe)
                file_url = await target_img_elem.get_attribute("src")
                headers = {"Cookie": self.cookie_to_str(), "Content-Type": "application/json;charset=utf-8",
                           "User-Agent": self.user_agent()}
                img = await self.context.request.get(file_url, headers=headers)
                with open(self.target_img_path, "wb") as f:
                    f.write(await img.body())

                # 弹出了滑块验证码
                slider_background_elem = await self.get_elem_by_xpath("//canvas[@id='cx_obstacle_canvas']", iframe)
                await self.screenshot(self.target_img_path, slider_background_elem)

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
