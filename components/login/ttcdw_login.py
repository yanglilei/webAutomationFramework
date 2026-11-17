import asyncio
from dataclasses import dataclass
from typing import Tuple

from src.frame.base import BaseLoginTaskNode
from src.utils import MyDdddOcr


@dataclass(init=False)
class TTCDWLogin(BaseLoginTaskNode):
    """
    学习公社登录
    https://www.ttcdw.cn/p/uc/login?service=https%3A%2F%2Fwww.ttcdw.cn%2Fp%2Fuc%2Fhome

    """
    async def do_login(self) -> Tuple[bool, str]:
        el_username = await self.get_elem_with_wait_by_css(10, "input#phone_it")
        if not el_username:
            self.logger.error("未找到用户名输入框")
            return False, "未找到用户名输入框"
        el_password = await self.get_elem_with_wait_by_css(10, "input#phone_pass")
        if not el_password:
            self.logger.error("未找到密码输入框")
            return False, "未找到密码输入框"
        btn_login = await self.get_elem_with_wait_by_xpath(10, "(//button[contains(@class, 'btn')])[1]")
        if not btn_login:
            self.logger.error("未找到登录按钮")
            return False, "未找到登录按钮"

        await el_username.fill(self.username)
        await asyncio.sleep(1)
        await el_password.fill(self.password)
        await asyncio.sleep(1)
        await btn_login.click()

        # 如果遇到需要输入验证码的，则点击登录后才会弹出验证码，然后输入验证码再次登录
        el_captcha = await self.get_elem_by_xpath( "//div[@class='tab_nav']//div[@class='wrap']//img")
        if el_captcha:
            code = MyDdddOcr.extract_verify_code_from_bytes(await self.screenshot(element=el_captcha))
            input_code = await self.get_elem_with_wait_by_xpath(3, "//div[@class='tab_nav']//div[@class='wrap']//input")
            await input_code.fill(code)
            await btn_login.click()

        error_desc = await self.wait_error_text(3)
        if error_desc:
            self.logger.error(f"登录失败：{error_desc}")
            return False, error_desc

        await self.wait_for_url_changed(lambda url : url.startswith("https://www.ttcdw.cn/p/uc/home"), 20)

        return True, "登录成功"


    async def wait_error_text(self, timeout=5):
        error_loc = await self.get_elem_by_xpath("//label[@class='error']")
        try:
            await self.get_current_page().wait_for_function("""
                () => {
                    const el = document.querySelector("label.error");
                    return el.textContent.trim().length > 0;
                }
            """, timeout=timeout*1000)
            return (await error_loc.text_content()).strip()
        except:
            return ""

