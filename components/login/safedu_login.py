import asyncio
import time
import random
from typing import Tuple

from src.frame.base.base_login_node import BaseLoginTaskNode


class SFEDULogin(BaseLoginTaskNode):
    """
    safedu登录
    中国教育发展战略学会
    https://www.safedu.org.cn/login
    """

    async def do_login(self) -> Tuple[bool, str]:
        # 切换tab
        login_tab = await self.get_elem_with_wait_by_xpath(10, "//div[@class='text_font_active']")
        if not login_tab:
            self.logger.error("未找到登录框")
            return False, "未找到登录框"
        if (await login_tab.text_content()).strip() != "密码登录":
            login_tab = self.get_elem_by_xpath("//div[contains(text(),'密码登录')]")
            if not login_tab:
                return False, "未找到密码登录方式"
            await login_tab.click()
            await asyncio.sleep(random.randint(1, 3))
            # time.sleep(random.randint(1, 3))  # 等带切换


        username_input = await self.get_elem_with_wait_by_xpath(10, "//input[@type='text']")
        password_input = await self.get_elem_with_wait_by_xpath(10, "//input[@type='password']")
        btn_login = await self.get_elem_with_wait_by_xpath(10, "//div[@class='login_btn']")
        await username_input.clear()
        await username_input.fill(self.username)
        await password_input.clear()
        await password_input.fill(self.password)
        await asyncio.sleep(random.randint(1, 3))
        await btn_login.click()
        error_tips = await self.get_elem_with_wait_by_xpath(3, "//div[contains(@class, 'el-message--error')]")
        if error_tips:
            self.logger.error("登录失败：%s" % await error_tips.text_content())
            return False, await error_tips.text_content()
        return True, ""
