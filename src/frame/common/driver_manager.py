# ./framework/driver_manager.py
import logging
from typing import Dict, Optional

from undetected_chromedriver import Chrome

from src.frame.common.decorator.singleton import singleton
from src.frame.common.web_driver_maker import WebDriverMaker
from src.frame.dto.driver_config import DriverConfig


@singleton
class WebDriverManager:
    """网页驱动映射管理器：确保一个用户名对应一个Driver"""

    def __init__(self):
        self.user_driver_map: Dict[str, Chrome] = {}  # 用户名->Driver映射

    def create_user_driver(self, username: str, driver_config: DriverConfig) -> Optional[Chrome]:
        """
        为指定用户创建专属Driver（已存在则返回现有Driver）
        :param username: 用户名
        :param driver_config: 浏览器配置
        :return: 用户专属Driver
        """
        # 若用户已存在Driver，直接返回
        if username in self.user_driver_map:
            return self.user_driver_map[username]

        try:
            driver = WebDriverMaker.make(username, driver_config)
            self.user_driver_map[username] = driver  # 绑定用户名与Driver
            return driver
        except:
            logging.exception(f"为用户{username}创建Driver失败：")
            return None

    def get_user_driver(self, username: str) -> Optional[Chrome]:
        """获取用户专属Driver"""
        return self.user_driver_map.get(username)

    def remove_user_driver(self, username: str):
        """移除用户Driver映射（并关闭Driver）"""
        driver = self.user_driver_map.pop(username, None)
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    def clear_all_drivers(self):
        """清空所有Driver"""
        for username in list(self.user_driver_map.keys()):
            self.remove_user_driver(username)
