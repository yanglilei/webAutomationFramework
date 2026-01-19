"""
海西教育网登录
"""
import time
from dataclasses import dataclass
from typing import Tuple

from selenium.webdriver.remote.webelement import WebElement

from src.frame.base.base_login_node import BaseLoginTaskNode
from src.frame.common.qt_log_redirector import LOG
from src.utils import basic
from src.utils.ocr_utils import DdddOcr


@dataclass(init=False)
class HXJYWLoginTaskNode(BaseLoginTaskNode):
    """
    海西教育网登录节点组件
    """
    project_code: str = ""

    def do_login(self) -> Tuple[bool, str]:
        # 在此处编写登录逻辑
        return self._login()

    def _login(self) -> Tuple[bool, str]:
        ret = True, "登录成功"

        # 登录对话框触发按钮
        btn_trigger_login_dialogue: WebElement = self.get_elem_with_wait_by_xpath(10, "//span[@id='login']")
        if btn_trigger_login_dialogue and btn_trigger_login_dialogue.is_enabled() and btn_trigger_login_dialogue.is_displayed():
            btn_trigger_login_dialogue.click()
            # 登录对话框
            login_dialogue = self.get_elem_with_wait_by_xpath(10,
                                                              "//div[@class='layui-layer layui-layer-page  layer-anim']")
            if login_dialogue:
                if basic.is_phone_no(self.username):
                    ret = self._common_login(self.username, self.password,
                                             "//span[@id='yonghumingloginn']",
                                             "//input[@id='user']",
                                             "//input[@id='pwd']",
                                             "//img[@id='captchaImage']",
                                             "//input[@id='identify']",
                                             "//input[@id='itemIndexlogin']")
                else:
                    ret = self._common_login(self.username, self.password,
                                             "//span[@id='shoujihaologinn']",
                                             "//input[@id='userr']",
                                             "//input[@id='pwdd']",
                                             "//img[@id='captchaImagee']",
                                             "//input[@id='identifyy']",
                                             "//input[@id='itemIndexlogintwo']",
                                             "//input[@id='projectCode']")
            else:
                ret = False, "登录对话框加载失败"
        else:
            ret = False, "页面加载异常"

        self.set_output_data("project_code", self.project_code)
        return ret

    def _common_login(self, username, password, login_tab_xpath, username_input_xpath, password_input_xpath,
                      captcha_img_xpath, verify_code_input_xpath, login_btn_xpath, project_code_xpath="",
                      retry_count=20):
        ret = True, "登录成功"
        tab = self.get_elem_with_wait_by_xpath(10, login_tab_xpath)
        tab.click()
        username_input = self.get_elem_with_wait_by_xpath(10, username_input_xpath)
        if not username_input:
            return False, "用户名输入框找不到"

        password_input = self.get_elem_with_wait_by_xpath(10, password_input_xpath)
        if not password_input:
            return False, "密码输入框找不到"

        login_btn = self.get_elem_with_wait_by_xpath(10, login_btn_xpath)
        if not login_btn:
            return False, "登录按钮找不到"

        username_input.send_keys(username)
        password_input.send_keys(password)

        self.project_code = self.node_config.get("node_params", {}).get("project_code")
        if not self.project_code:
            return False, "项目编号未配置"

        project_code_input = self.get_elem_with_wait_by_xpath(10, project_code_xpath)
        if project_code_input:
            project_code_input.send_keys(self.project_code)

        while retry_count > 0:
            retry_count -= 1
            captcha_img_elem = self.get_elem_with_wait_by_xpath(10, captcha_img_xpath)
            if captcha_img_elem:
                verify_code_input = self.get_elem_with_wait_by_xpath(10, verify_code_input_xpath)
                # 提取图片中的验证码
                try:
                    code = DdddOcr.extract_verify_code_from_bytes(captcha_img_elem.screenshot_as_png)
                except:
                    LOG.error("用户【%s】提取图片中的验证码失败，重试提取.." % self.username_showed)
                    time.sleep(1)
                    continue
                else:
                    verify_code_input.clear()
                    # 写入验证码
                    verify_code_input.send_keys(code)
            # 点击登录
            login_btn.click()
            # 此处一定要等待，否则，若上一次发生了验证码错误，提示框还没消失，这一次再登录的话，即使登录成功了，但是获取到的是上一次的错误提示框信息，
            # 导致的结果是：页面上虽然登录成功了，但是代码这边还在一直尝试登录
            # 补充：此处不宜显式等待，否则登录失败了，无法获取到失败的提示框
            # time.sleep(3)
            xpath = "//div[@class='layui-layer-content layui-layer-padding'][./i[@class='layui-layer-ico layui-layer-ico2']]"
            fail_tips = self.get_elem_with_wait_by_xpath(3, xpath)
            if not fail_tips:
                # 登录成功
                break
            else:
                fail_desc = fail_tips.text
                # 非常重要，等待提示框消失，否则下次循环的时候，会重新获取到旧的提示框！！
                self.wait_for_disappeared_by_xpath(10, xpath)
                # 验证码错误，或者验证码为空等，与验证码有关的错误！需要重试
                if not "验证码" in fail_desc:
                    # 与验证码无关的错误，可能是密码错误，或者用户名错误等问题
                    ret = False, fail_desc
                    break
                time.sleep(1)
        else:
            LOG.error("用户【%s】验证码验证失败（达到重试最大次数%d次），人工介入检查" % (
                self.username_showed, retry_count))
            ret = False, "验证码过不了"

        return ret
