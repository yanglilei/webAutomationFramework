import asyncio
import os.path
from dataclasses import dataclass
from typing import Tuple

import cv2
from PIL import Image
import numpy as np

from src.frame.base import BaseLoginTaskNode
from src.utils import SliderVerifyUtils, SysPathUtils


@dataclass(init=False)
class FJRCLoginTaskNode(BaseLoginTaskNode):
    target_img_path: str = ""
    background_img_path: str = ""

    async def do_login(self) -> Tuple[bool, str]:
        status, desc = await self._do_login()
        real_name = await self.get_user_real_name()
        # 更新用户姓名
        self.user_manager.update_record_by_username(self.username, {2: real_name})
        return status, desc

    async def _do_login(self) -> Tuple[bool, str]:
        """
        1.滑块验证
        2.输入用户名、密码
        3.点击登录
        :return: (True, "登录成功") (False, "登录失败")
        """
        self.target_img_path = str(os.path.join(SysPathUtils.get_tmp_file_dir(), self.username + "_2.png"))
        self.background_img_path = str(os.path.join(SysPathUtils.get_tmp_file_dir(), self.username + "_1.png"))
        # 去除弹窗
        if await self.get_elem_with_wait_by_xpath(3, "//div[@id='annunciate']"):
            btn_close = await self.get_elem_with_wait_by_xpath(3,
                                                               "//div[@class='annunciateImg-close'] | //div[@class='annunciate-close']")
            if btn_close:
                await btn_close.click()
            else:
                self.logger.warning("没有找到弹窗关闭按钮，关闭弹窗失败")
                return False, "没有找到弹窗关闭按钮，关闭弹窗失败"

        # 延迟2秒
        await asyncio.sleep(2)
        ret = True, "登录成功"
        # 处理滑块验证码，处理好了滑块，再填写用户名和密码，再登录
        slider_verify_result = await self._slider_verify()
        if slider_verify_result:
            # 验证成功
            try:
                username_elem = await self.get_elem_with_wait_by_xpath(10, "//input[@id='login_account']")
            except:
                self.logger.error("没有找到用户名输入框，页面加载失败，可能网络问题！")
                ret = False, "网络问题（没有加载出用户名输入框）"
            else:
                # 填写用户名
                await username_elem.fill(self.username)
                # 此处的代码健壮性不够，可能抛出未捕获的异常
                # 填写密码
                try:
                    password_elem = await self.get_elem_by_xpath("//input[@id='login_password']")
                    await password_elem.fill(self.password)
                except:
                    self.logger.error("没有找到密码输入框，页面加载失败，可能网络问题！")
                    ret = False, "网络问题（没有加载出密码输入框）"
                else:
                    try:
                        # 点击登录按钮
                        btn_login = await self.get_elem_with_wait_by_xpath(10, "//input[@id='login_submit']")
                        await btn_login.click()
                    except:
                        self.logger.exception("点击登录按钮失败")
                        ret = False, "点击登录按钮失败"
                    else:
                        # TODO 此处的逻辑需要更改，先获取失败的信息，后判断是否页面跳转！
                        # 延迟2秒，让浏览器加载
                        try:
                            await self.wait_for_url_changed(lambda url : "usersCenter" in url, 2)
                            ret = True, "登录成功"
                        except TimeoutError:
                            try:
                                # 登录失败，获取失败提示信息
                                # fail_tips_elem = await self.get_elem_by_xpath("//form[@id='pc-form']//div[@idx='0']//label[@class='error password-error']")
                                fail_tips_elem = await self.get_elem_by_xpath("//div[@class='c-fa']")
                            except:
                                self.logger.error("获取不到登录失败提示信息")
                                ret = False, "登录失败（原因未知）"
                            else:
                                ret = False, await fail_tips_elem.text_content()
        else:
            # 滑块验证码验证失败
            self.logger.error("登录失败！滑块验证码过不去，请人工介入检查！")
            ret = False, "登录失败（滑块验证失败）"

        return ret

    async def _slider_verify(self):
        """
        滑块验证
        :return:
        """
        SLIDER_TARGET_IMG_WIDTH = 50
        SLIDER_MOVE_BUTTON_WIDTH = 38
        ret = False
        count = 0
        while True:
            if count == 20:
                self.logger.error("滑块验证码，验证失败达20次，请人工介入检查")
                ret = False
                break
            else:
                count = count + 1
                try:
                    # 移动到上方显示出滑块
                    btn_slider = await self.get_elem_with_wait_by_xpath(10,
                                                                             "//div[contains(@class,'ui-slider-btn')]")
                except:
                    self.logger.error("没有找到滑块验证码的按钮，可能页面未加载完，尝试重新查找", exc_info=True)
                    continue
                else:
                    box = await btn_slider.bounding_box()
                    start_x = box["x"]
                    start_y = box["y"]
                    mouse = self.get_current_page().mouse
                    await mouse.move(start_x + 1, start_y + 1)
                    # await btn_slider.hover(position={"x": 0.0, "y": 0.0})
                    # await mouse.move(start_x, start_y)
                    await mouse.down()
                    await asyncio.sleep(1)
                    try:
                        target_img_elem = await self.wait_for_visible_by_xpath(10, "//img[@class='ui-slider-img-drag']")
                        await self.screenshot(self.target_img_path, target_img_elem)
                    except:
                        self.logger.error("没有找到滑块，可能页面未加载完，尝试重新查找")
                        continue
                    else:
                        background_img_elem = await self.get_elem_by_xpath("//img[@class='ui-slider-img-back']")
                        await self.screenshot(self.background_img_path, background_img_elem)

                        # 截图验证码模块
                        ret = self._shot_img(self.background_img_path, self.background_img_path, SLIDER_TARGET_IMG_WIDTH + 1, 0, 298, 120)
                    if not ret:
                        # 截图保存失败
                        self.logger.error("请检查滑块图片的路径是否存在！")
                        ret = False
                        break
                    else:
                        # 计算滑块到缺口的距离
                        try:
                            x = self._cal_distance(self.target_img_path, self.background_img_path)
                        except:
                            self.logger.error("计算滑块和缺口的距离失败，原因：", exc_info=True)
                            ret = False
                            break
                        # 滑块需要移动的距离。移动的距离需要加上按钮的一半宽度，因为鼠标拖动按钮一半的距离之后，按钮才会动起来！所以实际鼠标要移动的距离要加上按钮的一半宽度
                        # move_x = int(SLIDER_TARGET_IMG_WIDTH + x + SLIDER_MOVE_BUTTON_WIDTH / 2)
                        move_x = int(SLIDER_TARGET_IMG_WIDTH + x)
                        await SliderVerifyUtils.move_slider_slowly_pw_version(move_x, btn_slider, self.get_current_page())
                        await asyncio.sleep(2)
                        verify_result_elem = await self.get_elem_by_xpath("//div[contains(@class,'ui-slider-text')]")
                        text = await verify_result_elem.text_content()
                        if "验证成功" in text:
                            # 验证成功
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
            self.logger.exception("截图失败，原因：")
            ret = False
        finally:
            if img is not None:
                img.close()
            if region is not None:
                region.close()
        return ret

    def _cal_distance(self, target_img, base_img):
        # target_img_rgb = cv2.imread(target_img)
        target_img_gray = cv2.imdecode(np.fromfile(target_img, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        # target_img_gray = cv2.cvtColor(target_img_rgb, cv2.COLOR_BGR2GRAY)
        # base_img_rgb = cv2.imread(base_img, 0)
        base_img_gray = cv2.imdecode(np.fromfile(base_img, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        # res = cv2.matchTemplate(target_img_gray, base_img_rgb, cv2.TM_CCOEFF_NORMED)
        res = cv2.matchTemplate(target_img_gray, base_img_gray, cv2.TM_CCOEFF_NORMED)
        value = cv2.minMaxLoc(res)
        a, b, c, d = value
        if abs(a) >= abs(b):
            distance = c[0]
        else:
            distance = d[0]
        return distance

    async def get_user_real_name(self):
        real_name = None
        headers = {"cookie": await self.cookie_to_str(), "User-Agent": await self.user_agent()}
        try:
            resp = await self.context.request.post(url="https://fj.rcpxpt.com/usersFront/userInfo", headers=headers)
        except:
            self.logger.error("获取用户信息失败")
        else:
            resp_json = await resp.json()
            real_name = resp_json.get("realName", "")
        return real_name