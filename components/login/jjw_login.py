import asyncio
from typing import Tuple

from playwright.async_api import Locator

from src.frame.base import BaseLoginTaskNode


class JJWLogin(BaseLoginTaskNode):
    """
    全国中小学教师继续教育网，简称：继教网
    https://office.teacher.com.cn/views/loginAndRegister/login/login.html
    """

    async def do_login(self) -> Tuple[bool, str]:
        return await self._login()

    async def _login(self) -> Tuple[bool, str]:
        """
        用户登录
        :param username:用户名
        :param password:密码
        :return:登录成功返回True，登录失败返回失败提示
        """
        # 等待加载页面，出现登录窗口，username_input：用户名输入栏，password_input：密码输入栏
        # 登录返回值，登录成功返回True，登录失败返回失败的原因
        username_elem: Locator = await self.get_elem_with_wait_by_xpath(10, "//input[@id='mobile']")
        if not username_elem:
            self.logger.error("获取“用户名输入框”失败，页面异常")
            return False, "获取“用户名输入框”失败，页面异常"
        await username_elem.fill(self.username)
        password_elem = await self.get_elem_with_wait_by_xpath(10, "//input[@id='password']")
        await password_elem.fill(self.password)
        try:
            btn_login = await self.get_elem_with_wait_by_xpath(10, "//span[@id='login']")
            await btn_login.click()
        except Exception as e:
            self.logger.error(f"点击登录按钮失败，请检查页面元素是否正常，错误信息：{e}")
            return False, "点击登录按钮失败，请检查页面元素是否正常"
        # 等待跳转
        await asyncio.sleep(5)
        await self.wait_for_url_changed(lambda url : "learningViews" in url, 10)
        current_url = await self.get_current_url(self.get_latest_window())
        if "learningViews" not in current_url:
            return False, "登录失败[用户名或密码错误]"
        return True, "登录成功"
