# ./components/login/general_login_handler.py
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time

from src.frame.base.base_task_node import BasePYNode


class DemoLoginNode(BasePYNode):
    """通用登录任务节点（内置重试逻辑，避免二次登录）"""
    def execute(self) -> bool:
        # 判断是否为任务重登后的登录（通过任务重登次数标识）
        is_task_relogin = self.node_result.get("is_task_relogin", False)
        login_log_prefix = "【任务重登-登录节点】" if is_task_relogin else "【首次登录-登录节点】"
        self.logger.info(f"{login_log_prefix}开始执行登录逻辑（使用用户专属Driver）")

        # 获取登录节点内部重试配置
        max_login_retry = self.node_config.get("relogin_config", {}).get("login_max_retry_times", 3)
        retry_interval = self.node_config.get("relogin_config", {}).get("retry_interval", 2)

        for retry_idx in range(1, max_login_retry + 1):
            try:
                # 1. 校验Driver是否有效
                if not self.driver:
                    self.node_result["error_msg"] = "未获取到有效用户专属Driver"
                    self.logger.error(f"{login_log_prefix}{self.node_result['error_msg']}")
                    if retry_idx < max_login_retry:
                        self.logger.warning(f"{login_log_prefix}第{retry_idx}次登录失败，{retry_interval}秒后重试")
                        time.sleep(retry_interval)
                        continue
                    return False

                # 2. 获取登录配置
                login_config = self.node_config
                required_login_keys = ["login_url"]
                if not all(key in login_config for key in required_login_keys):
                    self.node_result["error_msg"] = f"登录配置缺失，需包含：{','.join(required_login_keys)}"
                    self.logger.error(f"{login_log_prefix}{self.node_result['error_msg']}")

                # 3. 执行登录操作
                self.driver.get(login_config["login_url"])
                time.sleep(2)

                # 输入账号密码
                self._input_element_value(login_config["username_selector"], self.user_config["username"])
                self._input_element_value(login_config["password_selector"], self.user_config["password"])
                self.logger.info(f"{login_log_prefix}账号密码输入完成")

                # 点击登录
                self._click_element(login_config["login_btn_selector"])
                self.logger.info(f"{login_log_prefix}登录按钮点击完成")

                # 验证登录成功
                if "success_selector" in login_config:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located(self._parse_selector(login_config["success_selector"]))
                    )
                    self.logger.info(f"{login_log_prefix}第{retry_idx}次登录成功验证通过")

                # 4. 设置节点结果（登录成功，终止重试）
                self.node_result["is_success"] = True
                self.node_result["output_data"] = {
                    "login_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "login_url": login_config["login_url"],
                    "current_url": self.driver.current_url,
                    "username": self.user_config["username"],
                    "is_task_relogin": is_task_relogin
                }
                self.logger.info(f"{login_log_prefix}执行成功（共重试{retry_idx-1}次）")
                return True

            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"{login_log_prefix}第{retry_idx}次登录失败：{error_msg}")
                # 未达到最大重试次数，等待后重试
                if retry_idx < max_login_retry:
                    self.logger.warning(f"{login_log_prefix}{retry_interval}秒后进行第{retry_idx+1}次重试")
                    time.sleep(retry_interval)
                    continue
                # 达到最大重试次数，返回失败
                self.node_result["error_msg"] = error_msg
                self.node_result["is_success"] = False
                return False

    # 辅助方法不变（直接使用self.driver）
    def _parse_selector(self, selector: str):
        return (By.XPATH, selector) if selector.startswith("//") else (By.CSS_SELECTOR, selector)

    def _input_element_value(self, selector: str, value: str):
        locator = self._parse_selector(selector)
        element = WebDriverWait(self.driver, 15).until(EC.presence_of_element_located(locator))
        element.clear()
        element.send_keys(value)

    def _click_element(self, selector: str):
        locator = self._parse_selector(selector)
        element = WebDriverWait(self.driver, 15).until(EC.element_to_be_clickable(locator))
        element.click()



class TestLoginNode(BasePYNode):
    """通用登录任务节点（内置重试逻辑，避免二次登录）"""
    def execute(self) -> bool:
        # 判断是否为任务重登后的登录（通过任务重登次数标识）
        is_task_relogin = self.node_result.get("is_task_relogin", False)
        login_log_prefix = "【任务重登-登录节点】" if is_task_relogin else "【首次登录-登录节点】"
        self.logger.info(f"{login_log_prefix}开始执行登录逻辑（使用用户专属Driver）")

        # 获取登录节点内部重试配置
        max_login_retry = self.node_config.get("relogin_config", {}).get("login_max_retry_times", 3)
        retry_interval = self.node_config.get("relogin_config", {}).get("retry_interval", 2)

        for retry_idx in range(1, max_login_retry + 1):
            try:
                # 1. 校验Driver是否有效
                # if not self.driver:
                #     self.node_result["error_msg"] = "未获取到有效用户专属Driver"
                #     self.logger.error(f"{login_log_prefix}{self.node_result['error_msg']}")
                #     return False

                # 2. 获取登录配置
                login_config = self.node_config
                required_login_keys = ["login_url"]
                if not all(key in login_config for key in required_login_keys):
                    self.node_result["error_msg"] = f"登录配置缺失，需包含：{','.join(required_login_keys)}"
                    self.logger.error(f"{login_log_prefix}{self.node_result['error_msg']}")

                # 3. 执行登录操作
                self.load_url(login_config["login_url"])
                time.sleep(2)

                # 4. 设置节点结果（登录成功，终止重试）
                self.node_result["is_success"] = True
                self.node_result["output_data"] = {
                    "login_time": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "login_url": login_config["login_url"],
                    "current_url": self.driver.current_url,
                    "username": self.user_config["username"],
                    "is_task_relogin": is_task_relogin
                }
                self.logger.info(f"{login_log_prefix}执行成功（共重试{retry_idx-1}次）")
                return True

            except Exception as e:
                error_msg = str(e)
                self.logger.error(f"{login_log_prefix}第{retry_idx}次登录失败：{error_msg}")
                # 未达到最大重试次数，等待后重试
                if retry_idx < max_login_retry:
                    self.logger.warning(f"{login_log_prefix}{retry_interval}秒后进行第{retry_idx+1}次重试")
                    time.sleep(retry_interval)
                    continue
                # 达到最大重试次数，返回失败
                self.node_result["error_msg"] = error_msg
                self.node_result["is_success"] = False
                return False
