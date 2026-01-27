import logging
import time
from pathlib import Path
from typing import Optional, Tuple

import psutil
import pyautogui
from playwright.sync_api import Browser, BrowserContext, Page, Playwright

from src.frame.dto.driver_config import DriverConfig
from src.utils.sys_path_utils import SysPathUtils


class WebDriverMaker:
    """Playwright 版本的浏览器驱动创建器，替代原 Selenium 实现"""

    @classmethod
    def make(cls, playwright: Playwright, username: str, driver_config: DriverConfig) -> Tuple[
        Browser, BrowserContext, Page]:
        """
        创建 Playwright 浏览器实例、上下文、页面（替代原 WebDriver）
        :param username: 用户名（用于多用户数据目录）
        :param driver_config: 驱动配置项
        :return: (Browser实例, BrowserContext上下文, Page页面)
        """
        if driver_config.browser_type != "0":
            raise Exception("暂不支持edge浏览器，Playwright版本当前仅支持Chrome")

        # 1. 构建浏览器启动参数
        launch_options = cls._set_launch_options(username, driver_config)
        # 2. 启动浏览器（Chrome）
        browser = playwright.chromium.launch(**launch_options)
        val = cls.get_browser_process_info(browser)
        # 3. 构建上下文参数（替代原 ChromeOptions）
        context_options = cls._set_context_options(username, driver_config)
        # 4. 创建浏览器上下文（支持多用户、无痕等）
        context1 = browser.new_context(**context_options)
        # 5. 创建新页面（替代原 driver.get() 初始化）
        page1 = context1.new_page()
        context2 = browser.new_context(**context_options)
        page2 = context2.new_page()
        # # 4. 创建浏览器上下文（支持多用户、无痕等）
        # context = browser.new_context(**context_options)
        page3 = context1.new_page()

        # context1.close()
        # context2.close()

        # 5. 创建新页面（替代原 driver.get() 初始化）
        # 6. 绑定PID获取方法（兼容原逻辑）
        setattr(browser, '_get_chrome_pid', lambda: cls._get_chrome_browser_pid(browser))

        return browser, context1, context2

    @classmethod
    def get_browser_process_info(cls, browser):
        """
        兼容新版Playwright的进程信息获取
        :param browser: Playwright的Browser实例
        :return: 进程信息字典（pid/状态/命令行）
        """
        if not browser:
            return None

        # 新版Playwright通过 _process 内部属性获取Popen对象
        process = getattr(browser, '_process', None)
        if not process:
            return None

        return {
            "pid": process.pid,  # 进程ID（核心）
            "cmdline": ' '.join(process.args),  # 启动命令行
            "status": "running" if process.poll() is None else "exited"  # 进程状态
        }

    @staticmethod
    def _get_chrome_browser_pid(browser: Browser) -> Optional[int]:
        """
        Playwright 版本获取 Chrome 主进程PID
        :param browser: Playwright Browser实例
        :return: Chrome主进程PID | None
        """
        try:
            # Playwright 直接暴露浏览器进程PID
            browser_process_pid = browser.process.pid
            if not psutil.pid_exists(browser_process_pid):
                return None

            # 验证进程是否为Chrome（防止异常）
            process = psutil.Process(browser_process_pid)
            if "chrome" in process.name().lower():
                return browser_process_pid

            # 兼容部分系统进程命名差异
            for child in psutil.Process(browser_process_pid).children(recursive=True):
                if "chrome" in child.name().lower():
                    return child.pid
            return None
        except Exception as e:
            logging.error(f"获取Chrome PID失败: {e}")
            return None

    @classmethod
    def _set_launch_options(cls, username: str, driver_config: DriverConfig) -> dict:
        """
        构建 Playwright 浏览器启动参数
        :return: launch参数字典
        """
        launch_options = {
            "headless": driver_config.headless_mode == "1",  # Playwright 无头模式更简洁
            "args": [
                "--lang=zh-CN",  # 语言设置
                "--mute-audio",  # 静音
                "--disable-gpu",  # 禁用GPU（兼容低配置）
            ]
        }

        # 1. 配置Chrome可执行文件路径（替代原 chromedriver 路径）
        if driver_config.browser_exe_position:
            exe_path = driver_config.browser_exe_position
            if not Path(exe_path).is_absolute():
                exe_path = Path(SysPathUtils.get_root_dir(), exe_path)
            if Path(exe_path).exists():
                launch_options["executable_path"] = str(exe_path)
            else:
                raise ValueError(f"Chrome可执行文件不存在: {exe_path}")

        # 2. 调试端口（hook_port）
        if driver_config.hook_port:
            launch_options["args"].append(f"--remote-debugging-port={driver_config.hook_port}")

        # 3. 窗口大小（通过args传递，兼容原逻辑）
        width, height = pyautogui.size()
        launch_options["args"].append(f"--window-size={width},{height}")

        return launch_options

    @classmethod
    def _set_context_options(cls, username: str, driver_config: DriverConfig) -> dict:
        """
        构建 Playwright 浏览器上下文参数（核心配置项）
        :return: context参数字典
        """
        context_options = {
            # 窗口大小（Playwright 推荐在context设置）
            "viewport": {
                "width": pyautogui.size()[0],
                "height": pyautogui.size()[1]
            },
            # 语言设置
            "locale": "zh-CN",
            # 时区设置（可选，根据需要调整）
            "timezone_id": "Asia/Shanghai"
        }
        return context_options


from playwright.sync_api import sync_playwright


# 定义回调函数：浏览器断开时执行
def on_browser_disconnected(browser):
    """浏览器断开连接时的自定义逻辑"""
    # 获取进程ID（新版Playwright用startup_info）
    # pid = browser.startup_info().get("pid")
    print("....")
    # print(f"⚠️  浏览器进程（PID:{pid}）已断开连接！")
    # 这里可以加资源清理、日志记录等逻辑


if __name__ == '__main__':
    driver_config = DriverConfig(
        browser_exe_position=r"C:\Users\lovel\AppData\Local\ms-playwright\chromium-1200\chrome-win64\chrome.exe",
        headless_mode="0", incognito_mode="1", is_selenium_wire="0", browser_type="0",
        driver_path=r"C:\Users\lovel\AppData\Local\ms-playwright\chromium-1200\chromedriver.exe")

    # driver_manager = WebDriverManager(LOG)
    # val = driver_manager.create_user_driver("xxx", driver_config)
    # print(val)
    with sync_playwright() as p:
        browser, context, page = WebDriverMaker.make(p, "xx", driver_config)

        # context.close()
        browser.close()
        time.sleep(1)
