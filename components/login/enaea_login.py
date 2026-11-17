import asyncio
from typing import Tuple
import random
from src.frame.base import BaseLoginTaskNode


class EneaLogin(BaseLoginTaskNode):
    """
    学习公社登录（旧版学习公社）
    登录地址：https://study.enaea.edu.cn/login.do
    """
    async def do_login(self) -> Tuple[bool, str]:
        return await self._login()

    async def _login(self) -> Tuple[bool, str]:
        # 等待加载页面，出现登录窗口，username_input：用户名输入栏，password_input：密码输入栏
        # 登录返回值，登录成功返回True，登录失败返回失败的原因
        tab_pwd_login = await self.get_elem_with_wait_by_xpath(10, "//div[@id='pc-wrap']//span[contains(@class,'form-item-psw')]")
        if not tab_pwd_login:
            return False, "登录失败-页面错误"

        if "cur" not in await tab_pwd_login.get_attribute("class"):
            await tab_pwd_login.click()

        username_input = await self.get_elem_with_wait_by_xpath(10, "//form[@id='pc-form']//div[@idx='0']//input[@name='username']")
        if not username_input:
            return False, "用户名输入框找不到"
        password_input = await self.get_elem_by_xpath("//form[@id='pc-form']//div[@idx='0']//input[@name='password']")
        if not password_input:
            return False, "密码输入框找不到"

        await username_input.fill(self.username)
        await asyncio.sleep(random.randint(1, 3))
        await password_input.fill(self.password)
        login_btn = await self.get_elem_by_xpath("//form[@id='pc-form']//div[@idx='0']//button")
        if not login_btn:
            return False, "登录按钮找不到到"
        await asyncio.sleep(random.randint(1, 3))
        await login_btn.click()
        fail_tips = await self.get_elem_with_wait_by_xpath(3, "//form[@id='pc-form']//div[@idx='0']//label[@class='error password-error']")
        if fail_tips:
            # 登录失败
            return False, await fail_tips.text_content()

        return True, "登录成功"