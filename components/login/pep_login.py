import asyncio
from typing import Tuple

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed, RetryCallState

from src.frame.base import BaseLoginTaskNode
from src.frame.common.exceptions import BusinessException
from src.frame.common.qt_log_redirector import LOG
from src.utils import MyDdddOcr


def before_relogin(retry_state: RetryCallState):
    LOG.info(f"即将重新尝试登录，重试次数：{retry_state.attempt_number}")


class PEPLogin(BaseLoginTaskNode):

    async def do_login(self) -> Tuple[bool, str]:
        return await self._do_login(self.username, self.password)

    @retry(retry=retry_if_exception_type(BusinessException), stop=stop_after_attempt(10), wait=wait_fixed(1),
           before_sleep=before_relogin)
    async def _do_login(self, username, password) -> Tuple[bool, str]:
        login_tab = await self.get_elem_with_wait_by_xpath(10, "//li[@id='login1']")
        if "active" not in await login_tab.get_attribute("class"):
            await login_tab.click()
            await asyncio.sleep(2)  # 等待切换登录方式

        username_input = await self.get_elem_with_wait_by_xpath(10, "//input[@id='regName']")
        if not username_input:
            # raise LoginFailException("用户名输入框找不到")
            return False, "用户名输入框找不到"

        password_input = await self.get_elem_by_xpath("//input[@id='passwd']")
        if not password_input:
            return False, "密码输入框找不到"

        await username_input.fill(username)
        await password_input.fill(password)

        login_btn = await self.get_elem_with_wait(2, "//form[@name='loginForm']//img[@id='imgLogin']")
        if not login_btn:
            return False, "登录按钮找不到到"

        verify_code_input = await self.get_elem("//input[@id='validcode2']")
        if not verify_code_input:
            return False, "验证码输入框找不到"

        verify_code_img = await self.get_elem_with_wait(5, "//img[@id='imgValidCode']")
        if not verify_code_img:
            # 刷新页面
            await self.refresh()
            self.logger.error("获取验证码图片失败！")
            raise BusinessException("验证码图片获取失败！")

        verify_code = MyDdddOcr.extract_verify_code_from_bytes(await verify_code_img.screenshot())
        await verify_code_input.fill(verify_code)

        await login_btn.click()
        await asyncio.sleep(3)
        fail_tips = await self.get_elem_with_wait_by_xpath(3, "//li[@id='errmsg1']")
        if fail_tips:
            if "验证码不正确" in await fail_tips.text_content():
                # 验证码不正确
                self.logger.error("验证码不正确！")
                raise BusinessException("验证码不正确！")
            elif "px/index" in await self.get_current_url():
                return True, "登录成功"
            else:
                self.logger.error(f"登录失败：{await fail_tips.text_content()}")
                return False, f"登录失败：{await fail_tips.text_content()}"
        else:
            return True, "登录成功"
