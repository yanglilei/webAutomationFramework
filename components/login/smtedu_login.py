import asyncio
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

from playwright.async_api import FrameLocator, APIResponse

from src.frame.base import BaseLoginTaskNode
from src.frame.common.exceptions import BusinessException
from src.frame.common.qt_log_redirector import LOG
from src.utils.slider_verify_utils import SliderVerifyUtils
from src.utils.sys_path_utils import SysPathUtils


@dataclass(init=False)
class SMTEDULogin(BaseLoginTaskNode):
    """
    智慧平台登录（https://auth.smartedu.cn/uias/login）
    自动获取authorization和sdp-app-id
    可配置参数：
    is_update_user_info（是否更新用户信息）：true-获取用户信息更新到表格中；false-不更新到表格中
    版本：V0.0.1
    """
    slider_img_path: str = ""
    background_img_path: str = ""
    user_info: dict = field(default_factory=dict)

    # 异步监听请求
    async def handle_request(self, request):
        if "v1.1/person_accounts" in request.url:
            authorization = request.headers.get("authorization")
            headers = {"authorization": authorization}
            self.set_output_data("headers", headers)

    async def handle_response(self, response):
        request = response.request
        if request.url.startswith(
                "https://uc-gateway.ykt.eduyun.cn/v1.1/users/") and "with_ext=true&session_id=" in request.url:
            headers = {"authorization": request.headers.get("authorization"),
                       "sdp-app-id": request.headers.get("sdp-app-id")}
            self.set_output_data("headers", headers)
            response_json = await response.json()
            self.user_info = {"id": str(response_json.get("account_id")), "real_name": response_json.get("real_name"),
                              "school": response_json.get("ext_by_standard", {}).get("x_school_name", "")}
            self.set_output_data("user_info", self.user_info)

    def set_up(self):
        slider_img_dir = self._create_slider_verify_img_dir()
        self.slider_img_path: str = str(slider_img_dir.joinpath(self.username + "_2.png"))
        self.background_img_path: str = str(slider_img_dir.joinpath(self.username + "_1.png"))

    async def do_login(self) -> Tuple[bool, str]:
        # self.get_current_page().on("request", self.handle_request)
        self.get_current_page().on("response", self.handle_response)
        ret = await self._start_login()
        is_get_user_info = self.node_config.get("node_params", {}).get("is_update_user_info", False)
        if is_get_user_info:
            self.user_manager.update_record_by_username(self.username, {2: self.user_info.get("real_name"), 3: self.user_info.get("school")})
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

                response: APIResponse = await self.context.request.get(img_url)
                with open(self.background_img_path, "wb") as f:
                    f.write(await response.body())
                # async with httpx.AsyncClient() as client:
                #     img = await client.get(img_url, headers=headers)
                #     LOG.info(f"用户【{self.username_showed}】下载图片验证码成功！")
                #     with open(self.background_img_path, "wb") as f:
                #         f.write(img.content)

                btn_sliders = captcha_iframe.locator(".tc-fg-item")
                btn_slider = None
                for i in range(await btn_sliders.count()):
                    elem = btn_sliders.nth(i)
                    box = await elem.bounding_box()
                    # start_x = box["x"] + box["width"] / 2
                    # start_y = box["y"] + box["height"] / 2
                    # if await elem.is_visible() and "tc-slider-normal" in await elem.get_attribute("class"):
                    if abs(int(box["width"]) - int(box["height"])) < 5:
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

                back_ground_img_elem = await self.get_elem_with_wait_by_xpath(2, "//div[@id='slideBg']",
                                                                              iframe=captcha_iframe)
                box = await back_ground_img_elem.bounding_box()
                ratio = 672 / box['width']
                # 实际移动的距离=该方法计算出的距离/缩放比例 - 滑块的起始距离
                move_x = int(x / ratio - 30 / ratio * 2.4)
                page = self.get_current_page()
                await SliderVerifyUtils.move_slider_slowly_pw_version(move_x, btn_slider, page)
                await asyncio.sleep(6)

                back_ground_img_elem = await self.get_elem_with_wait_by_xpath(2, "//div[@id='slideBg']",
                                                                              iframe=captcha_iframe)

                if back_ground_img_elem:
                    # 验证失败，刷新验证码
                    LOG.error(f"滑块验证失败，开始重试，重试次数：{count}")
                    await self.screenshot(Path(SysPathUtils.get_tmp_file_dir(), f"{self.username}_{count}.png"))
                    await captcha_iframe.locator("#e_reload").click()
                    await asyncio.sleep(2)
                else:
                    # 验证成功
                    await self.screenshot(Path(SysPathUtils.get_tmp_file_dir(), f"{self.username}_{count}.png"))
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
