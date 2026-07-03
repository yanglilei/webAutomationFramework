import asyncio
from typing import Tuple
import random
from src.frame.base import BaseLoginTaskNode


class CXLogin(BaseLoginTaskNode):
    """
    超星登录
    """
    async def do_login(self) -> Tuple[bool, str]:
        return await self._login()

    async def _login(self) -> Tuple[bool, str]:
        # 等待加载页面，出现登录窗口，username_input：用户名输入栏，password_input：密码输入栏
        # 登录返回值，登录成功返回True，登录失败返回失败的原因
        ret = True, "登录成功"

        username_input = await self.get_elem_with_wait_by_xpath(10, "//input[@id='phone']")
        if not username_input:
            ret = False, "用户名输入框找不到"
        else:
            password_input = await self.get_elem_by_xpath("//input[@id='pwd']")
            if not password_input:
                ret = False, "密码输入框找不到"
            else:
                await username_input.fill(self.username)
                await asyncio.sleep(random.randint(1, 3))
                await password_input.fill(self.password)
                login_btn = await self.get_elem_by_xpath("//button[@id='loginBtn']")
                if not login_btn:
                    ret = False, "登录按钮找不到到"
                else:
                    await login_btn.click()
                    fail_tips = await self.get_elem_with_wait_by_xpath(3, "//p[@id='err-txt']")
                    if fail_tips:
                        # 登录失败
                        ret = False, await fail_tips.text_content()
        return ret