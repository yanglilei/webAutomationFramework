import logging
import os
from pathlib import Path
from typing import Optional

import psutil
import pyautogui
from selenium.webdriver.chrome.service import Service
from seleniumwire.thirdparty.mitmproxy.options import Options
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
        if driver_config.browser_type == "0":
            # 谷歌浏览器

            if driver_config.is_selenium_wire == "1":
                # 暂时不支持selenium-wire
                from seleniumwire import webdriver
                # return webdriver.Chrome(service=Service(cls._create_driver_path(driver_config.driver_path)),
                #                         options=cls._set_chrome_options(webdriver.ChromeOptions(), username, driver_config))
                service = Service(cls._create_driver_path(driver_config.driver_path))
                driver = webdriver.Chrome(
                    service=service,
                    options=cls._set_chrome_options(webdriver.ChromeOptions(), username, driver_config))

                setattr(driver, '_get_chrome_pid', lambda: WebDriverMaker._get_chrome_browser_pid(service))
                return driver
            else:
                # from selenium import webdriver
                # 使用不被检测的浏览器驱动
                import undetected_chromedriver as webdriver
                return webdriver.Chrome(
                    driver_executable_path=cls._create_driver_path(driver_config.driver_path),
                    options=cls._set_chrome_options(webdriver.ChromeOptions(), username, driver_config))
        else:
            # edge浏览器，暂时不支持
            raise Exception("暂不支持edge浏览器")
            # return webdriver.Edge(options=cls._set_edge_options(webdriver.EdgeOptions(), username, driver_config))

    @staticmethod
    def _get_chrome_browser_pid(driver_service: Service) -> Optional[int]:
        """
        兼容不同Selenium版本，获取Chrome浏览器主进程PID
        原理：chromedriver是Chrome的子进程，通过psutil找到其父进程（即Chrome）
        """
        try:
            # 1. 获取chromedriver进程对象
            chromedriver_process = driver_service.process
            if not chromedriver_process:
                return None
            chromedriver_pid = chromedriver_process.pid
            child_processes = []
            for process in psutil.process_iter():
                if process.ppid() == chromedriver_pid:
                    return process.pid
                    # if psutil.pid_exists(child_process.pid):
                    #     LOG.info("杀死子进程：%s，进程ID：%d，父进程ID：%d" % (
                    #         child_process.name(), child_process.pid, child_process.ppid()))
                    #     child_process.kill()
            return None
        except Exception as e:
            logging.error(f"获取Chrome PID失败: {e}")
            return None

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
    def _set_chrome_options(cls, options: ChromeOptions | Options, username, driver_config: DriverConfig):
        # 创建chrome的用户数据文件夹，chrome多开用到
        # options.add_argument(r"--user-data-dir=%s" % cls._make_user_data_dir(username))
        # 无头模式
        if driver_config.headless_mode == "1":
            # options.add_argument('--headless=new')
            options.add_argument('--headless')

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
        if driver_config.is_selenium_wire == "1":
            options.add_experimental_option('excludeSwitches', ['enable-logging', 'enable-automation'])
        if driver_config.hook_port:
            # options.add_experimental_option("debuggerAddress", f"127.0.0.1:{driver_config.hook_port}")  # 前面设置的端口号
            # options.add_argument(f"debugger_address=127.0.0.1:{driver_config.hook_port}")  # 前面设置的端口号
            options.debugger_address = f"127.0.0.1:{driver_config.hook_port}"
        return options

    @classmethod
    def _make_user_data_dir(cls, username: str):
        user_data_dir = Path(SysPathUtils.get_root_dir(), "user_data", username)
        user_data_dir.mkdir(parents=True, exist_ok=True)
        return str(user_data_dir)
