from typing import Tuple

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from src.frame.base.base_login_node import BaseLoginTaskNode


class AXJXJYLoginTaskNode(BaseLoginTaskNode):

    def do_login(self) -> Tuple[bool, str]:
        ret = True, "登录成功"
        # 找到用户名的输入框
        username_input: WebElement = self.get_elem_with_wait_by_xpath(10, "//input[@aria-label='账号为身份证号']")
        if not username_input:
            self.logger.error("用户名输入框的位置超时了[10秒]，请检查网络")
            return False, "用户名输入框的位置超时了[10秒]"

        # 设置用户名
        username_input.send_keys(self.username)
        # 找到密码的输入框
        password_input: WebElement = self.get_elem_by_xpath("//input[@aria-label='密码']")
        # 设置密码
        password_input.send_keys(self.password)
        # 定位登录按钮
        login_btn_element: WebElement = self.get_elem(
            (By.XPATH, "//div[@aria-label='登录']//div[@class='btn-inner style-wrap']"))
        try:
            login_btn_element.click()
        except:
            self.logger.exception("点击登录异常：")
            ret = False, "点击登录异常"
        else:
            error_tips = self.wait_for_visible(2, (By.XPATH, "//div[text()='用户名或密码错误']"))
            if error_tips:
                ret = False, "用户名或密码错误"
        return ret
