import asyncio
import random
from typing import Tuple

from src.frame.base.base_login_node import BaseLoginTaskNode
from src.utils import MyDdddOcr


class HNGBLoginTaskNode(BaseLoginTaskNode):

    async def do_login(self) -> Tuple[bool, str]:
        ret = True, "登录成功"
        retry_count = 20
        while retry_count > 0:
            # 找到用户名的输入框
            username_input = await self.get_elem_with_wait_by_xpath(10, "//input[@placeholder='用户名']")
            if not username_input:
                self.logger.error("用户名输入框的位置超时了[10秒]，请检查网络")
                return False, "用户名输入框的位置超时了[10秒]"

            # 设置用户名
            await username_input.clear()
            await username_input.fill(self.username)
            await asyncio.sleep(random.uniform(0.5, 2))
            # 找到密码的输入框
            password_input = await self.get_elem_by_xpath("//input[@placeholder='密码']")
            # 设置密码
            await password_input.clear()
            await password_input.fill(self.password)
            await asyncio.sleep(random.uniform(0.5, 2))

            retry_count -= 1
            # 图片验证码输入框
            captcha_input_elem = await self.get_elem_with_wait_by_xpath(10, "//input[@placeholder='验证码']")
            await captcha_input_elem.clear()
            await asyncio.sleep(random.uniform(0.5, 2))
            # 图片验证码
            captcha_img_elem = await self.get_elem_with_wait_by_xpath(10, "//img[@class='yzm']")
            # 提取图片中的验证码
            try:
                code = MyDdddOcr.extract_verify_code_from_bytes(await self.screenshot(element=captcha_img_elem))
            except:
                self.logger.error("提取图片中的验证码失败，重试提取..")
                await asyncio.sleep(1)
                continue
            else:
                # await captcha_input_elem.clear()
                # 写入验证码
                await captcha_input_elem.fill(code)

            # 定位登录按钮
            login_btn_element = await self.get_elem_by_xpath("//button[.//text()='立即登录']")
            try:
                await login_btn_element.click()
            except:
                self.logger.exception("点击登录异常：")
                # 刷新页面重试
                await self.refresh()
                await asyncio.sleep(1)
                ret = False, "点击登录异常"
            else:
                error_tips_elem = await self.get_elem_with_wait_by_xpath(3, "//div[@class='el-message el-message--error']//p[@class='el-message__content']")
                if error_tips_elem:
                    error_tips = await error_tips_elem.text_content()
                    if "登录成功" in error_tips:
                        break
                    elif "验证码" in error_tips:
                        # 验证码错误，点击返回按钮
                        await asyncio.sleep(1)
                        continue
                    else:
                        # 与验证码无关的错误，可能是密码错误，或者用户名错误等问题
                        ret = False, error_tips
                        break
                else:
                    # 没有错误提示消息，登录成功
                    break

        else:
            self.logger.error(
                f"用户【{self.username_showed}】验证码验证失败（达到重试最大次数 {retry_count} 次），人工介入检查")
            ret = False, "验证码过不了"
        return ret
