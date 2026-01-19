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

    def do_login(self) -> Tuple[bool, str]:
        # 切换tab
        login_tab = self.get_elem_with_wait_by_xpath(10, "//div[@class='text_font_active']")
        if not login_tab:
            self.logger.error("未找到登录框")
            return False, "未找到登录框"
        if login_tab.text.strip() != "密码登录":
            login_tab = self.get_elem_by_xpath("//div[contains(text(),'密码登录')]")
            if not login_tab:
                return False, "未找到密码登录方式"
            login_tab.click()
            time.sleep(random.randint(1, 3))  # 等带切换

        username_input = self.get_elem_with_wait_by_xpath(10, "//input[@type='text']")
        password_input = self.get_elem_with_wait_by_xpath(10, "//input[@type='password']")
        btn_login = self.get_elem_with_wait_by_xpath(10, "//div[@class='login_btn']")
        username_input.clear()
        username_input.send_keys(self.username)
        password_input.clear()
        password_input.send_keys(self.password)
        time.sleep(random.randint(1, 3))
        btn_login.click()
        error_tips = self.get_elem_with_wait_by_xpath(3, "//div[contains(@class, 'el-message--error')]")
        if error_tips:
            self.logger.error("登录失败：%s" % error_tips.text)
            return False, error_tips.text
        return True, ""
