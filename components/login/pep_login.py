import asyncio
import random
import time
from typing import Tuple

from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed, RetryCallState

from src.frame.base import BaseLoginTaskNode
from src.frame.common.exceptions import BusinessException
from src.frame.common.qt_log_redirector import LOG
from src.utils import MyDdddOcr


def before_relogin(retry_state: RetryCallState):
    LOG.info(f"即将重新尝试登录，重试次数：{retry_state.attempt_number}")


class PEPLogin(BaseLoginTaskNode):

    def do_login(self) -> Tuple[bool, str]:
        return self._do_login(self.username, self.password)

    @retry(retry=retry_if_exception_type(BusinessException), stop=stop_after_attempt(10), wait=wait_fixed(1),
           before_sleep=before_relogin)
    def _do_login(self, username, password) -> Tuple[bool, str]:
        login_tab = self.get_elem_with_wait_by_xpath(10, "//li[@id='login1']")
        if "active" not in login_tab.attr("class"):
            login_tab.click()
            asyncio.sleep(2)  # 等待切换登录方式

        username_input = self.get_elem_with_wait_by_xpath(10, "//input[@id='regName']")
        if not username_input:
            # raise LoginFailException("用户名输入框找不到")
            return False, "用户名输入框找不到"

        password_input = self.get_elem_by_xpath("//input[@id='passwd']")
        if not password_input:
            return False, "密码输入框找不到"

        username_input.input(username)
        time.sleep(random.uniform(0.5, 3))
        password_input.input(password)
        time.sleep(random.uniform(0.5, 3))

        login_btn = self.get_elem_with_wait_by_xpath(2, "//form[@name='loginForm']//img[@id='imgLogin']")
        if not login_btn:
            return False, "登录按钮找不到到"

        verify_code_input = self.get_elem_by_xpath("//input[@id='validcode2']")
        if not verify_code_input:
            return False, "验证码输入框找不到"

        verify_code_img = self.get_elem_with_wait_by_xpath(5, "//img[@id='imgValidCode']")
        if not verify_code_img:
            # 刷新页面
            self.refresh()
            self.logger.error("获取验证码图片失败！")
            raise BusinessException("验证码图片获取失败！")

        verify_code = MyDdddOcr.extract_verify_code_from_bytes(self.screenshot(element=verify_code_img, as_bytes=True))
        verify_code_input.input(verify_code)
        time.sleep(random.uniform(0.5, 3))
        login_btn.click()
        # 强制等待3秒
        time.sleep(3)
        fail_tips = self.get_elem_with_wait_by_xpath(3, "//li[@id='errmsg1']")
        if fail_tips:
            if "验证码不正确" in fail_tips.text:
                # 验证码不正确
                self.logger.error("验证码不正确！")
                raise BusinessException("验证码不正确！")
            elif "px/index" in self.get_current_url() or not fail_tips.text:
                return True, "登录成功"
            else:
                self.logger.error(f"登录失败：{fail_tips.text}")
                return False, f"登录失败：{fail_tips.text}"
        else:
            return True, "登录成功"
