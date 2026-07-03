import asyncio
from typing import Tuple

from playwright.async_api import Locator

from src.frame.base import BaseLoginTaskNode
from src.utils import MyDdddOcr


class LNLLLogin(BaseLoginTaskNode):
    async def do_login(self) -> Tuple[bool, str]:
        return await self._login()

    async def _login(self) -> Tuple[bool, str]:
        # 等待加载页面，出现登录窗口，username_input：用户名输入栏，password_input：密码输入栏
        # 登录返回值，登录成功返回True，登录失败返回失败的原因
        ret = True, "登录成功"
        await self.handle_notify_dialogue()

        username_input = await self.get_elem_with_wait_by_xpath(10, "//input[@placeholder='请输入用户名']")
        if not username_input:
            self.logger.error("用户名输入框的位置超时了[10秒]，请检查网络")
            return False, "用户名输入框的位置超时了[10秒]"

        retry_count = -1
        max_retry_count = 20
        while retry_count != max_retry_count:
            retry_count += 1
            # 设置用户名
            await username_input.clear()
            await asyncio.sleep(0.3)
            await username_input.fill(self.username)
            password_input = await self.get_elem_with_wait_by_xpath(10, "//input[@placeholder='请输入密码']")
            if not password_input:
                self.logger.error("密码输入框的位置超时了[10秒]，请检查网络")
                ret = False, "密码输入框的位置超时了[10秒]"
                break

            await password_input.clear()
            await asyncio.sleep(0.1)
            # 设置密码
            await password_input.fill(self.password)
            # 定位登录按钮
            login_btn = await self.get_elem_with_wait_by_xpath(10,  "//button[./span[text()='登录']]", visible=True)
            if not login_btn:
                self.logger.error("获取登录按钮的位置超时了[10秒]，请检查网络")
                ret = False, "登录失败（登录页面没有刷出来）"
                break

            # 图片验证码
            captcha_img_elem = await self.get_elem_with_wait_by_xpath(10, "(//div[@class='login_box']//img[@class='image'])[1]", visible=True)
            # 图片验证码输入框
            captcha_input = await self.get_elem_with_wait_by_xpath(10, "//input[@placeholder='请输入验证码']", visible=True)

            # 提取图片中的验证码
            try:
                code = MyDdddOcr.extract_verify_code_from_bytes(await captcha_img_elem.screenshot())
            except:
                self.logger.exception("提取图片中的验证码失败，重试提取..")
                # 点击切换验证码
                await captcha_img_elem.click()
                continue
            else:
                await captcha_input.clear()
                await asyncio.sleep(0.5)
                # 写入验证码
                await captcha_input.fill(code)
                await asyncio.sleep(0.5)

                try:
                    await login_btn.click()
                except:
                    self.logger.error("点击“登录”按钮失败，尝试重试！")
                    continue
                else:
                    # 获取提示信息
                    alert_text: Locator = await self.wait_for_visible_by_xpath(5, "//div[@role='alert']//p")
                    if alert_text:
                        text = await alert_text.text_content()
                        if text == "验证码填写有误":
                            self.logger.error("验证码错误，请重新输入")
                            # 重新获取图片验证码
                            captcha_img_elem = await self.get_elem_with_wait_by_xpath(10, ("(//div[@class='login_box']//img[@class='image'])[1]"))
                            # 点击图片验证码，让其切换
                            try:
                                await self.js_click(captcha_img_elem)
                                # 等待验证码的图片切换
                                await asyncio.sleep(0.5)
                            except:
                                self.logger.error("点击图片验证码失败，退出登录！")
                                ret = False, "登录失败-切换图片验证码失败"
                                break
                            continue
                        elif text == "用户名或密码填写有误":
                            self.logger.error("登录失败，用户名或密码填写有误")
                            ret = False, "用户名或密码填写有误"
                            break
                        elif text == "登录成功":
                            # 登录成功
                            ret = True, "登录成功！"
                            break
                        else:
                            self.logger.error(f"登录失败：{text}")
                            ret = False, text
                            break
                    else:
                        self.logger.error("登录异常，点击登录后页面没有反应，尝试重试！")
                        await self.refresh()
        else:
            self.logger.error(f"验证码验证失败（达到重试最大次数{max_retry_count}次），人工介入检查")
            ret = False, "验证码过不了"

        return ret

    async def handle_notify_dialogue(self):
        ret = True
        notify_dialogue = await self.get_elem_with_wait_by_xpath(5, "//div[contains(@class, 'el-dialog__wrapper m-notice-dialog')]")

        if notify_dialogue:
            close_btn = await self.get_elem_by_xpath("//div[contains(@class, 'el-dialog__wrapper m-notice-dialog')]//button[./span[text()='关闭']]")
            if close_btn:
                try:
                    await close_btn.click()
                except:
                    self.logger.exception("关闭通知对话框失败")
                    ret = False
            else:
                self.logger.error("没有找到关闭对话框的按钮，请人工介入检查")
                ret = False
        return ret
