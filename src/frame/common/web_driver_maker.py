import os
from pathlib import Path

import pyautogui
from undetected_chromedriver import ChromeOptions

from src.frame.dto.driver_config import DriverConfig
from src.utils.sys_path_utils import SysPathUtils


class WebDriverMaker:

    @classmethod
    def make(cls, username: str, driver_config: DriverConfig):
        """
        创建浏览器驱动
        :return:WebDriver，返回浏览器驱动
        """
        if driver_config.is_selenium_wire == "1":
            # 暂时不支持selenium-wire
            raise Exception("暂不支持selenium-wire")
            # from seleniumwire import webdriver
        else:
            # from selenium import webdriver
            # 使用不被检测的浏览器驱动
            import undetected_chromedriver as webdriver

        if driver_config.browser_type == "0":
            # 谷歌浏览器
            # return webdriver.Chrome(service=Service(cls._get_driver() if not driver_config.driver_path else driver_config.driver_path),
            #                         options=cls._set_chrome_options(webdriver.ChromeOptions(), username, driver_config))
            return webdriver.Chrome(
                driver_executable_path=cls._create_driver_path(driver_config.driver_path),
                options=cls._set_chrome_options(webdriver.ChromeOptions(), username, driver_config))
        else:
            # edge浏览器，暂时不支持
            raise Exception("暂不支持edge浏览器")
            # return webdriver.Edge(options=cls._set_edge_options(webdriver.EdgeOptions(), username, driver_config))

    @classmethod
    def _create_driver_path(cls, driver_path: str):
        if not driver_path or not driver_path.strip():
            driver_path = Path(SysPathUtils.get_config_file_dir(), "chromedriver.exe")
        elif not Path(driver_path).is_absolute():
            driver_path = Path(SysPathUtils.get_config_file_dir(), driver_path)

        if not Path(driver_path).exists():
            raise ValueError("驱动路径不存在，请配置driver_path的参数或在conf目录下存放chromedriver.exe文件")
        return str(driver_path)

    @classmethod
    def _set_edge_options(cls, options, username, driver_config: DriverConfig):
        # 创建chrome的用户数据文件夹，chrome多开用到
        options.add_argument(r"--user-data-dir=%s" % cls._make_user_data_dir(username))
        # 后台静音
        options.add_argument("--mute-audio")
        # 无头模式
        if driver_config.headless_mode == 1:
            options.add_argument('--headless=new')

        options.add_argument('--disable-gpu')
        # 开启无痕模拟，不需要清除缓存
        if driver_config.incognito_mode == 1:
            options.add_argument("-inprivate")
        width, height = pyautogui.size()
        options.add_argument("--window-size=%d,%d" % (width, height))
        options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        return options

    @classmethod
    def _set_chrome_options(cls, options: ChromeOptions, username, driver_config: DriverConfig):
        # 创建chrome的用户数据文件夹，chrome多开用到
        options.add_argument(r"--user-data-dir=%s" % cls._make_user_data_dir(username))
        # 无头模式
        if driver_config.headless_mode == "1":
            options.add_argument('--headless=new')

        options.add_argument('--lang=zh-CN')
        # options.add_argument("--mute-audio")
        # options.add_argument('--disable-plugins')
        # options.add_argument('--single-process')
        # options.add_argument('--in-process-plugins')
        # 开启无痕模拟，不需要清除缓存
        if driver_config.incognito_mode == "1":
            options.add_argument("--incognito")

        if driver_config.browser_exe_position:
            # Chrome的位置默认打包在项目根目录下，配置的时候需要填写相对根目录的相对路径
            binary_location = str(
                os.path.join(SysPathUtils.get_root_dir(), driver_config.browser_exe_position)) if not os.path.isabs(
                driver_config.browser_exe_position) else driver_config.browser_exe_position
            options.binary_location = binary_location

        width, height = pyautogui.size()
        options.add_argument("--window-size=%d,%d" % (width, height))
        # options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        if driver_config.hook_port:
            # options.add_experimental_option("debuggerAddress", f"127.0.0.1:{driver_config.hook_port}")  # 前面设置的端口号
            # options.add_argument(f"debugger_address=127.0.0.1:{driver_config.hook_port}")  # 前面设置的端口号
            options.debugger_address = f"127.0.0.1:{driver_config.hook_port}"
        return options

    @classmethod
    def _make_user_data_dir(cls, username: str):
        user_data_dir = Path(SysPathUtils.get_root_dir(), "cache", username)
        user_data_dir.mkdir(parents=True, exist_ok=True)
        return str(user_data_dir)
