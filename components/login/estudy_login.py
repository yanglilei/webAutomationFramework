import asyncio
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Tuple

from playwright.async_api import APIResponse

from src.frame.base import BaseLoginTaskNode
from src.frame.common.exceptions import BusinessException
from src.frame.common.qt_log_redirector import LOG
from src.utils.slider_verify_utils import SliderVerifyUtils
from src.utils.sys_path_utils import SysPathUtils


@dataclass(init=False)
class SMTEDULogin(BaseLoginTaskNode):
    """
    中国教育干部网络学院登录（https://estudy.enaea.edu.cn/login）
    版本：V0.0.1
    """
    slider_img_path: str = ""
    background_img_path: str = ""
    all_projects: dict = field(default_factory=dict)
    user_info: dict = field(default_factory=dict)
    headers: dict = field(default_factory=dict)

    # 异步监听请求
    async def handle_request(self, request):
        if "v1.1/person_accounts" in request.url:
            authorization = request.headers.get("authorization")
            headers = {"authorization": authorization}
            self.set_output_data("headers", headers)

    async def handle_response(self, response):
        request = response.request
        # 异步监听请求：https://apaas.grtcloud.net/api/grt-user-center-service/user/business/v1/composite?business_id=2070327433486200832&template_id=104
        if "/api/grt-user-center-service/user/learn-business/v1/top-batch" in request.url:
            authorization = request.headers.get("authorization")
            xhmac_access_key = request.headers.get("x-hmac-access-key")
            xhmac_algorithm = request.headers.get("x-hmac-algorithm")
            xhmac_signature = request.headers.get("x-hmac-signature")
            xhmac_date = request.headers.get("x-hmac-date")
            xhmac_signed_headers = request.headers.get("x-hmac-Signed-Headers")
            xhmac_timestamp = request.headers.get("x-hmac-Timestamp")
            user_agent = request.headers.get("user-agent")
            # request_params = request.params
            # parsed = urlparse(response.url)
            # qs = parse_qs(parsed.query)
            # self.business_id = qs["business_id"][0]

            headers = {"authorization": authorization, "x-hmac-access-key": xhmac_access_key,
                       "x-hmac-algorithm": xhmac_algorithm, "x-hmac-signature": xhmac_signature,
                       "x-hmac-date": xhmac_date, "x-hmac-Signed-Headers": xhmac_signed_headers,
                       "x-hmac-Timestamp": xhmac_timestamp,
                       "user-agent": user_agent}
            self.headers.update(headers)

            response_json = await response.json()
            self.all_projects = response_json.get("data")

            self.set_output_data("headers", self.headers)
            self.set_output_data("all_projects", self.all_projects)

    def set_up(self):
        slider_img_dir = self._create_slider_verify_img_dir()
        self.slider_img_path: str = str(slider_img_dir.joinpath(self.username + "_2.png"))
        self.background_img_path: str = str(slider_img_dir.joinpath(self.username + "_1.png"))

    async def do_login(self) -> Tuple[bool, str]:
        self.headers = {}
        self.all_projects = {}
        # 拦截接口，获取项目信息
        self.get_current_page().on("response", self.handle_response)
        status, desc = await self._start_login()
        # 检查20秒，确保self.project_info不为空，避免后续操作依赖为空数据，
        if status and not await self.wait_for_project_info(timeout=20):
            self.logger.error("项目信息获取超时！")
            return False, "项目信息获取超时！"
        # is_get_user_info = self.node_config.get("node_params", {}).get("is_update_user_info", False)
        # if is_get_user_info:
        #     self.user_manager.update_record_by_username(self.username, {2: self.user_info.get("real_name"), 3: self.user_info.get("school")})
        return status, desc

    async def _start_login(self):
        ret = True, "登录成功"
        tab_pwd_login = await self.get_elem_with_wait_by_xpath(10, "//div[@data-node-key='password']/div[@role='tab']")
        if not tab_pwd_login:
            self.logger.error("密码登录选项找不到")
            return False, "密码登录选项找不到"

        await tab_pwd_login.click()
        await asyncio.sleep(random.randint(1, 3))
        username_input = await self.get_elem_with_wait_by_css(20, "input#accountLogin_name")
        if not username_input:
            return False, "用户名输入框找不到"

        password_input = await self.get_elem_by_css("input#accountLogin_password")
        if not password_input:
            return False, "密码输入框找不到"

        await username_input.fill(self.username)
        await asyncio.sleep(random.randint(1, 3))
        await password_input.fill(self.password)
        await asyncio.sleep(random.randint(1, 2))

        login_btn = await self.get_elem_by_xpath("//button[./span[text()='登 录']]")
        if not login_btn:
            return False, "登录按钮找不到到"

        try:
            await login_btn.click()
        except:
            LOG.exception("点击登录按钮失败：")
            raise BusinessException("点击登录按钮失败")
        else:
            fail_tips = await self.get_elem_with_wait_by_css(3, "div#dark-toast")
            if fail_tips:
                # 登录失败
                return False, await fail_tips.text_content()
            el_captcha = await self.get_elem_with_wait_by_css(3, "div#captcha")
            if el_captcha:
                if not await self._slider_verify():
                    raise BusinessException("滑块验证失败")
                else:
                    fail_tips = await self.get_elem_with_wait_by_css(3, "div#dark-toast", visible=False)
                    if fail_tips:
                        # 登录失败
                        return False, await fail_tips.text_content()

        return ret

    async def wait_for_project_info(self, timeout=20):
        """
        等待project_info不为空
        :return:
        """
        while timeout > 0:
            if self.all_projects:
                return True
            await asyncio.sleep(1)
            timeout -= 1
        return False

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
            try:
                el_background_img = await self.get_elem_with_wait_by_css(10, "div.bigImg img", visible=False)
                img_url = await el_background_img.get_attribute("src")
                headers = {"Cookie": await self.cookie_to_str(), "Content-Type": "application/json;charset=utf-8",
                           "User-Agent": await self.user_agent()}

                response: APIResponse = await self.context.request.get(img_url, headers=headers)
                with open(self.background_img_path, "wb") as f:
                    f.write(await response.body())

                el_gap_img = await self.get_elem_with_wait_by_css(10, "div.smallImg img")
                img_url = await el_gap_img.get_attribute("src")
                headers = {"Cookie": await self.cookie_to_str(), "Content-Type": "application/json;charset=utf-8",
                           "User-Agent": await self.user_agent()}

                response: APIResponse = await self.context.request.get(img_url, headers=headers)
                with open(self.slider_img_path, "wb") as f:
                    f.write(await response.body())

                btn_slider = await self.get_elem_by_css("div.slider")
                # 计算滑块到缺口的距离
                try:
                    x = SliderVerifyUtils.cal_gap_x_distance_with_gap_img(self.background_img_path,
                                                                          self.slider_img_path)
                except:
                    self.logger.exception("计算滑块和缺口的距离失败，原因：")
                    ret = False
                    break

                box = await el_background_img.bounding_box()
                # 实际移动的距离需要加上偏差12
                move_x = int(x + 12)
                await SliderVerifyUtils.move_slider_slowly_pw_version_v2(move_x, btn_slider, self.get_current_page(),
                                                                         free_interval=0.01)
                await asyncio.sleep(6)

                back_ground_img_elem = await self.get_elem_with_wait_by_css(2, "div.bigImg img")

                if back_ground_img_elem:
                    # 验证失败，刷新验证码
                    LOG.error(f"滑块验证失败，开始重试，重试次数：{count}")
                    await self.screenshot(Path(SysPathUtils.get_tmp_file_dir(), f"{self.username}_{count}.png"))
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
