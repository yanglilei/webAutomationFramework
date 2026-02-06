import asyncio
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

import httpx
from playwright.async_api import FrameLocator

from src.frame.base import BaseLoginTaskNode
from src.frame.common.exceptions import BusinessException
from src.frame.common.qt_log_redirector import LOG
from src.utils.slider_verify_utils import SliderVerifyUtils
from src.utils.sys_path_utils import SysPathUtils


@dataclass(init=False)
class SMTEDULogin(BaseLoginTaskNode):
    slider_img_path: str = ""
    background_img_path: str = ""

    def set_up(self):
        slider_img_dir = self._create_slider_verify_img_dir()
        self.slider_img_path: str = str(slider_img_dir.joinpath(self.username + "_2.png"))
        self.background_img_path: str = str(slider_img_dir.joinpath(self.username + "_1.png"))

    async def do_login(self) -> Tuple[bool, str]:
        ret = await self._start_login()
        # 2. 新增：捕获并筛选网络请求（核心差异）
        # for request in self.web_browser.requests:  # 遍历所有捕获的请求
        #     print("=" * 50)
        #     print("请求URL：", request.url)  # 打印请求地址
        #     print("请求方法：", request.method)  # GET/POST
        #     print("响应状态码：", request.response.status_code)  # 200/404等
        #     # print("响应内容：", request.response.body.decode('utf-8'))  # 接口返回的JSON数据
        #     break
        return ret

    async def _start_login(self):
        ret = True, "登录成功"
        username_input = await self.get_elem_with_wait_by_xpath(20, "//input[@id='username']")
        if not username_input:
            ret = False, "用户名输入框找不到"
        else:
            password_input = await self.get_elem_by_xpath("//input[@id='tmpPassword']")
            if not password_input:
                ret = False, "密码输入框找不到"
            else:
                await username_input.fill(self.username)
                await asyncio.sleep(random.randint(1, 3))
                await password_input.fill(self.password)
                await asyncio.sleep(random.randint(1, 2))
                agree_cb = await self.get_elem_by_xpath("//input[@id='agreementCheckbox']")
                if agree_cb:
                    await agree_cb.click()

                await asyncio.sleep(random.randint(1, 2))
                login_btn = await self.get_elem_by_xpath("//button[@id='loginBtn']")
                if not login_btn:
                    ret = False, "登录按钮找不到到"
                else:
                    try:
                        await login_btn.click()
                    except:
                        LOG.exception("点击登录按钮失败：")
                        raise BusinessException("点击登录按钮失败")
                    else:
                        if not await self._slider_verify():
                            raise BusinessException("滑块验证失败")

                        fail_tips = await self.get_elem_with_wait_by_xpath(2, "//p[@id='loginFormError']")
                        if fail_tips:
                            # 登录失败
                            ret = False, await fail_tips.text_content()
                        await self.handle_week_password_alert()
                        await self.handle_accept_agreement()
                        # 获得认证串
                        # self.auth_str = self.get_auth_str()
        return ret

    async def _slider_verify(self):
        """
        滑块验证
        :return:
        """
        ret = False
        count = 0
        while True:
            if count == 20:
                LOG.error("滑块验证码，验证失败达20次，请人工介入检查")
                ret = False
                break

            count = count + 1
            # self.web_browser.switch_to.default_content()
            # captcha_iframe = self.get_elem_with_wait(3, (By.XPATH,
            #                                              "//div[@class='flx_loginbox fr flx_loginbox2 ipad_logbox']//iframe[@id='tcaptcha_iframe_dy']"))
            # self.web_browser.switch_to.iframe(captcha_iframe)
            # locator_expr = "xpath=//div[@class='flx_loginbox fr flx_loginbox2 ipad_logbox']//iframe[@id='tcaptcha_iframe_dy']"
            # locator_expr = "//iframe[@id='tcaptcha_iframe_dy']"
            captcha_iframe: FrameLocator = self.switch_to_frame("div#tcaptcha_transform_dy iframe#tcaptcha_iframe_dy")
            back_ground_img_elem = await self.get_elem_with_wait_by_xpath(10, "//div[@id='slideBg']",
                                                                          iframe=captcha_iframe)
            try:
                style_str = await back_ground_img_elem.get_attribute("style")
                start_idx = style_str.find("url(\"") + len("url(\"")
                end_idx = style_str.find("\");", start_idx)
                img_url = style_str[start_idx: end_idx]
                headers = {"Cookie": await self.cookie_to_str(), "Content-Type": "application/json;charset=utf-8",
                           "User-Agent": await self.user_agent()}

                async with httpx.AsyncClient() as client:
                    img = await client.get(img_url, headers=headers)
                    LOG.info(f"用户【{self.username_showed}】下载图片验证码成功！")
                    with open(self.background_img_path, "wb") as f:
                        f.write(img.content)

                btn_sliders = captcha_iframe.locator(".tc-fg-item")
                btn_slider = None
                for i in range(await btn_sliders.count()):
                    elem = btn_sliders.nth(i)
                    box = await elem.bounding_box()
                    # start_x = box["x"] + box["width"] / 2
                    # start_y = box["y"] + box["height"] / 2
                    # if await elem.is_visible() and "tc-slider-normal" in await elem.get_attribute("class"):
                    if 49<= int(box["width"]) <= 51:
                        btn_slider = elem
                        break
                if not btn_slider:
                    await captcha_iframe.locator("#e_reload").click()
                    await asyncio.sleep(2)
                    continue

                # btn_slider = captcha_iframe.locator("/html/body/div/div[3]/div[2]/div[7]")
                # await btn_slider.focus()

                # iframe = await self.get_frame(iframe_name="tcaptcha_iframe_dy")
                # iframe = await self.get_frame(iframe_name="https://turing.captcha.qcloud.com")
                # btn_sliders = await iframe.evaluate('document.querySelectorAll(".tc-fg-item");')
                # btn_sliders = await self.execute_js('document.querySelectorAll(".tc-fg-item");', iframe=iframe)
                # btn_slider = btn_sliders[1]
                # btn_slider = self.get_elems_with_wait(10, (By.XPATH, "//div[@class='btn_slider']"))[0]
                # style_str = btn_slider.get_attribute("style")
                # start_idx = style_str.find("url(\"") + len("url(\"")
                # end_idx = style_str.find("\");", start_idx)
                # img_url = style_str[start_idx: end_idx]
                # headers = {"Cookie": self.cookie_to_str(), "Content-Type": "application/json;charset=utf-8",
                #            "User-Agent": self.user_agent()}
                # img = requests.get(img_url, headers=headers)
                # LOG.info(f"下载图片验证码成功！")
                # with open(self.slider_img_path, "wb") as f:
                #     f.write(img.content)

                # 计算滑块到缺口的距离
                try:
                    x = SliderVerifyUtils.cal_gap_x_pos(self.background_img_path)
                except:
                    LOG.error("计算滑块和缺口的距离失败，原因：", exc_info=True)
                    ret = False
                    break

                # 实际移动的距离=该方法计算出的距离/缩放比例 - 滑块的起始距离
                move_x = int(x / 2.4 - 30)
                page = self.get_current_page()
                await SliderVerifyUtils.move_slider_slowly_pw_version(move_x, btn_slider, page)
                await asyncio.sleep(2)
                back_ground_img_elem = await self.get_elem_with_wait_by_xpath(2, "//div[@id='slideBg']",
                                                                              iframe=captcha_iframe)
                if back_ground_img_elem:
                    # 验证失败，刷新验证码
                    LOG.error(f"滑块验证失败，开始重试，重试次数：{count}")
                    await captcha_iframe.locator("#e_reload").click()
                    await asyncio.sleep(2)
                else:
                    # 验证成功
                    LOG.info(f"滑块验证成功")
                    ret = True
                    break
            except Exception as e:
                LOG.error(f"滑块验证失败：{str(e)}，开始重试！")
        return ret

    async def handle_week_password_alert(self):
        alert = await self.get_elem_with_wait_by_xpath(3, "//div[@id='modify__tips_wrapper']")
        if alert:
            skip_btn = await self.get_elem_by_xpath("//button[@id='cancel_sdk']")
            try:
                await skip_btn.click()
            except:
                LOG.error("忽略弱密码提示失败，登录失败")
                raise BusinessException("忽略弱密码提示失败")

    async def handle_accept_agreement(self):
        accept_btn = await self.get_elem_with_wait_by_xpath(3, "//button[@id='gotologon_sdk']")
        if accept_btn:
            try:
                await accept_btn.click()
            except:
                LOG.error("同意更新协议失败")
                raise BusinessException("同意更新协议失败")

    def _create_slider_verify_img_dir(self) -> Path:
        tmp_dir = Path(SysPathUtils.get_root_dir(), "tmp")
        tmp_dir.mkdir(parents=True, exist_ok=True)
        return tmp_dir


