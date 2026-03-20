import asyncio
import random
from typing import Tuple
from src.frame.base import BaseLoginTaskNode


class YanxiuLogin(BaseLoginTaskNode):

    async def do_login(self) -> Tuple[bool, str]:

        # 异步监听请求
        async def handle_request(request):
            if "/user/getUserInfo" in request.url:
                authorization = request.headers.get("authorization")
                srxuserinfo = request.headers.get("srxuserinfo")
                accesstoken = request.headers.get("x-dt-accesstoken")
                client_id = request.headers.get("x-dt-clientid")

                headers = {"authorization": authorization, "srxuserinfo": srxuserinfo, "x-dt-accesstoken": accesstoken,
                            "x-dt-clientid": client_id}
                self.set_output_data("headers", headers)

        self.get_current_page().on("request", handle_request)

        return await self._login()

    async def _login(self) -> Tuple[bool, str]:
        """
        1.输入用户名、密码
        2.点击登录
        :return:bool-True登录成功。str-失败信息
        """
        status = False
        desc = ""

        # 验证成功
        try:
            username_elem = await self.get_elem_with_wait_by_xpath(10,
                                                                   "//div[@class='login-content']//input[@type='text']")
        except:
            self.logger.error("没有找到用户名输入框，页面加载失败，可能网络问题！")
            desc = "网络问题（没有加载出用户名输入框）"
        else:
            # 填写用户名
            await username_elem.fill(self.username)
            await asyncio.sleep(random.uniform(0.5, 2))
            # 此处的代码健壮性不够，可能抛出未捕获的异常
            # 填写密码
            try:
                password_input = await self.get_elem_with_wait_by_xpath(10,
                                                                        "//div[@class='login-content']//input[@type='password']")
                await password_input.fill(self.password)
            except:
                self.logger.error("没有找到密码输入框，页面加载失败，可能网络问题！")
                desc = "网络问题（没有加载出密码输入框）"
            else:
                await asyncio.sleep(random.uniform(0.5, 2))
                try:
                    # 点击登录按钮
                    btn_login = await self.get_elem_with_wait(10, "//div[@class='login-content']//a[text()='登录']")
                    await btn_login.click()
                except:
                    self.logger.error("没有找到登录按钮，页面加载失败，可能网络问题！")
                    desc = "网络问题（没有加载出登录按钮）"
                else:
                    # 延迟3秒，让浏览器加载
                    await asyncio.sleep(3)
                    if "/home" in await self.get_current_url():
                        # 登录成功之后跳转地址：https://fj.rcpxpt.com/usersCenter
                        # 页面发生了跳转，跳转到用户中心页面，则表示，登录成功
                        status = True
                    else:
                        try:
                            # 登录失败，获取失败提示信息
                            fail_tips_elem = await self.get_elem("//div[@class='login-content']//div[@class='error-msg']//span")
                        except:
                            self.logger.error("获取不到登录失败提示信息")
                            desc = "登录失败（原因未知）"
                        else:
                            if not fail_tips_elem:
                                # 等待3秒后，未获取到登录失败提示信息，则表示登录失败
                                desc = "登录失败（点击登录后页面未跳转）"
                            else:
                                desc = await fail_tips_elem.text_content()
        return status, desc
