import asyncio
import json
from typing import Tuple

from playwright.async_api import Request

from src.frame.base import BaseLoginTaskNode
from src.utils import MyDdddOcr


class FJLLLogin(BaseLoginTaskNode):
    """
    福建干部培训网
    """

    async def do_login(self) -> Tuple[bool, str]:

        # 异步监听请求
        async def handle_request(request: Request):
            if "/studentArchives/student" in request.url:
                authorization = request.headers.get("authorization")
                refreshauthorization = request.headers.get("refreshauthorization")
                post_data = request.post_data
                user_id = json.loads(post_data).get("id")
                headers = {"authorization": authorization, "refreshauthorization": refreshauthorization}
                self.set_output_data("headers", headers)
                self.set_output_data("user_id", user_id)

        self.get_current_page().on("request", handle_request)

        return await self._login()

    async def _login(self) -> Tuple[bool, str]:
        # 等待加载页面，出现登录窗口，username_input：用户名输入栏，password_input：密码输入栏
        # 登录返回值，登录成功返回True，登录失败返回失败的原因
        ret = True, "登录成功"

        username_input = await self.get_elem_with_wait_by_xpath(10, "(//div[@class='login_dialog']//input)[1]")
        if not username_input:
            self.logger.error("用户名输入框的位置超时了[10秒]，请检查网络")
            return False, "用户名输入框的位置超时了[10秒]"
        # 设置用户名
        await username_input.fill(self.username)

        # 找到密码的输入框
        password_input = await self.get_elem_with_wait_by_xpath(10, "(//div[@class='login_dialog']//input)[2]")
        # 设置密码
        await password_input.fill(self.password)
        # 输入验证码
        verify_code_input = await self.get_elem_with_wait_by_xpath(10, "(//div[@class='login_dialog']//input)[3]")

        verify_code_img = await self.get_elem_with_wait_by_xpath(10, "//img[@class='code']")
        code = MyDdddOcr.extract_verify_code_from_bytes(await self.screenshot(element=verify_code_img))
        await verify_code_input.fill(code)

        btn_login = await self.get_elem_with_wait_by_xpath(10, "//button[contains(@class, 'loginBtn')]")
        try:
            await btn_login.click()
        except Exception as e:
            self.logger.error("点击登录按钮超时--", e)
        # 登录按钮可以点击，则点击登录
        # 判断页面是否发生了跳转，判断页面的标题是否发生变化。原有标题
        # print("点击登录按钮之后，页面的标题：%s" % self.web_browser.title)
        # 延迟3秒再判断标题是否发生变化
        else:
            # 延迟3秒，判断是否发生了跳转
            error_msg = await self.get_elem_with_wait_by_css(3,  "div[role='alert'] p.el-message__content")
            if error_msg:
                msg_ = f"登录失败（{await error_msg.text_content()}）"
                self.logger.error(msg_)
                ret = False, msg_
        return ret

