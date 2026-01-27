# ./framework/driver_manager.py
import asyncio
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Any, Tuple

import psutil
from playwright.async_api import BrowserContext
from playwright.async_api import async_playwright, Browser
from playwright_stealth import Stealth

from src.frame.dto.driver_config import DriverConfig
from src.utils import basic
from src.utils.sys_path_utils import SysPathUtils


# @singleton
class WebDriverManager:
    """网页驱动映射管理器：确保一个用户名对应一个Driver"""

    def __init__(self, logger):
        # 扩展映射结构：(用户名, 批次号) -> {driver: Chrome, chrome_pid: int, driver_service: Service, monitor_thread: threading.Thread, is_running: bool}
        self.user_driver_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        # 协程锁
        self.lock = asyncio.Lock()
        self.logger = logger
        self._playwright = None
        self._browser: Optional[Browser] = None

    async def _init_playwright(self):
        """初始化Playwright上下文（全局唯一）"""
        if self._playwright is None:
            self._playwright = await async_playwright().start()

    async def _init_browser(self, driver_config: DriverConfig):
        if not self._browser:
            # 1. 构建浏览器启动参数
            launch_options = await self._set_launch_options(driver_config)
            # 2. 启动浏览器（Chrome）
            self._browser = await self._playwright.chromium.launch(**launch_options)

    async def create_user_driver(self, username: str, batch_no: str, driver_config: DriverConfig) -> BrowserContext:
        """
        为指定用户创建专属Driver（已存在则返回现有Driver），并启动进程监控
        :param username: 用户名
        :param driver_config: 浏览器配置
        :param batch_no: 任务批次号
        :return: 用户专属Driver
        """
        # TODO 思考是否需要加入batch_no，考虑是否支持释放某个批次和所有的资源！pause by zcy 20260126
        async with self.lock:  # 加锁保证线程安全
            key = (username, batch_no)
            # 若用户已存在Driver且处于运行状态，直接返回
            if key in self.user_driver_map and self.user_driver_map[key]['is_running']:
                self.logger.info(f"已存在Context，直接返回")
                return self.user_driver_map[key]['context']

            driver_info = await self.create_new_context(driver_config)
            self.user_driver_map[key] = driver_info
            self.logger.info(f"创建Context成功！")
            return driver_info.get('context')

    async def create_new_context(self, driver_config: DriverConfig):
        """
        创建playwright的context
        :param driver_config: 驱动配置信息
        :return:
        返回格式：{
            'context': context,
            'chrome_pid': '',
            'monitor_thread': None,
            'is_running': True
        }
        """
        await self._init_playwright()
        await self._init_browser(driver_config)
        # 3. 构建上下文参数
        context_options = await self._set_context_options(driver_config)
        # 4. 创建浏览器上下文（支持多用户、无痕等）
        context: BrowserContext = await self._browser.new_context(**context_options)
        # 5.关键：为上下文绑定自动stealth
        await self.setup_stealth_for_context(context)
        # 5. 创建新页面（替代原 driver.get() 初始化）
        await context.new_page()

        # 封装用户Driver相关信息
        driver_info = {
            'context': context,
            'chrome_pid': '',
            'monitor_thread': None,
            'is_running': True
        }
        return driver_info

    async def setup_stealth_for_context(self, context: BrowserContext):
        """封装函数：为上下文绑定自动stealth"""

        async def apply_stealth(page):
            # 页面创建后立即应用stealth
            await Stealth().apply_stealth_async(page)

        # 绑定事件：所有通过该context新建的页面，都会自动执行apply_stealth
        context.on("page", apply_stealth)

    async def close(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def get_user_driver(self, username: str, batch_no: str) -> Optional[BrowserContext]:
        """获取用户专属Driver（仅返回运行中的Driver）"""
        async with self.lock:
            driver_info = self.user_driver_map.get((username, batch_no))
            if driver_info and driver_info['is_running']:
                return driver_info['context']
            return None

    async def _set_launch_options(self, driver_config: DriverConfig) -> dict:
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
                "--start-maximized"  # 窗口最大化。配合context的no_viewport=True属性实现最大化
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
        # width, height = pyautogui.size()
        # launch_options["args"].append(f"--window-size={width},{height}")

        return launch_options

    async def _set_context_options(self, driver_config: DriverConfig) -> dict:
        """
        构建 Playwright 浏览器上下文参数（核心配置项）
        :return: context参数字典
        """
        context_options = {
            # 语言设置
            "locale": "zh-CN",
            # 时区设置（可选，根据需要调整）
            "timezone_id": "Asia/Shanghai",
            # 最大化窗口的配置
            "no_viewport": True
        }
        return context_options

    async def remove_user_driver(self, batch_no: Optional[str] = None, username: Optional[str] = None):
        """
        移除用户Driver映射（并关闭Driver、终止进程、停止监控）
        :param batch_no: 批次号
        :param username: 用户名
        :return:
        """
        self.logger.info(f"开始移除Context")
        # if not batch_no or not username:
        #     self.logger.error("请指定用户和批次号")
        #     return
        # elif not batch_no:
        async with self.lock:
            if username:
                keys = [key for key in self.user_driver_map.keys() if key[0] == username]
            elif batch_no:
                keys = [key for key in self.user_driver_map.keys() if key[1] == batch_no]
            else:
                # 均不传，则不清除
                return

            for key in keys:
                await self._cleanup_driver(key)

    async def clear_all_drivers(self):
        """清空所有用户的Driver（批量清理）"""
        self.logger.info("开始清空所有用户的Context")
        async with self.lock:
            for key in list(self.user_driver_map.keys()):
                await self._cleanup_driver(key)

    async def _start_monitor_thread(self, username: str, batch_no: str):
        """为指定用户启动浏览器监控线程（后台检测浏览器是否被手动关闭）"""
        key = (username, batch_no,)

        # 定义监控逻辑
        async def monitor_func():
            while True:
                # 每次循环先检查锁，确认用户Driver是否仍在运行
                async with self.lock:
                    driver_info = self.user_driver_map.get(key)
                    # 终止条件：用户Driver已被清理/不再运行
                    if not driver_info or not driver_info['is_running']:
                        self.logger.info(f"监控线程：Context已停止，退出监控")
                        return

                try:
                    # 1. 检测Chrome浏览器进程是否存活
                    if not psutil.pid_exists(driver_info['chrome_pid']):
                        self.logger.warning(
                            f"Chrome浏览器（PID:{driver_info['chrome_pid']}）已被手动关闭")
                        # 自动清理该用户的Driver
                        async with self.lock:
                            await self._cleanup_driver(key)
                        return

                    # 2. 额外检测：Driver是否还能正常通信（防止进程存在但浏览器无响应）
                    try:
                        # TODO 此处有bug，从selenium搬过来的！未修改！
                        driver_info['context'].current_url
                    except Exception:
                        self.logger.warning(f"Context与浏览器通信失败")
                        async with self.lock:
                            await self._cleanup_driver(key)
                        return

                    time.sleep(1)  # 每秒检测一次，可根据需求调整
                except Exception:
                    self.logger.exception(f"监控线程异常：")
                    async with self.lock:
                        await self._cleanup_driver(key)
                    return

        # 启动守护线程（主程序退出时自动结束）
        monitor_thread = threading.Thread(target=monitor_func, name=f"Monitor-[{basic.mask_username(username)}]")
        monitor_thread.daemon = True
        self.user_driver_map[key]['monitor_thread'] = monitor_thread
        monitor_thread.start()
        self.logger.info(f"浏览器监控线程已启动")

    def is_empty(self) -> bool:
        """判断驱动是否为空"""
        return not self.user_driver_map

    # def batch_nos(self) -> List[str]:
    #     """获取所有批次号"""
    #
    #     return [key[1] for key in self.user_driver_map.keys()]

    async def _cleanup_driver(self, key: Tuple[str, str]):
        """内部方法：清理单个用户的Driver资源（关闭Driver、终止进程、停止监控）"""
        driver_info = self.user_driver_map.get(key)
        if not driver_info:
            return
        username = key[0]
        # 标记为停止运行（防止监控线程继续执行）
        driver_info['is_running'] = False
        # 1. 关闭Driver
        context: BrowserContext = driver_info.get('context')
        if context:
            try:
                await context.close()
                self.logger.info(f"Context已正常退出")
            except Exception:
                self.logger.warning(f"Context正常退出失败，尝试强制终止进程")

        # 2. 强制终止chromedriver进程
        # driver_service = driver_info.get('driver_service')
        # if driver_service and driver_service.process:
        #     try:
        #         driver_service.process.terminate()
        #         self.logger.info(f"用户[{basic.mask_username(username)}]的ChromeDriver进程已强制终止")
        #     except Exception:
        #         self.logger.warning(f"用户[{basic.mask_username(username)}]的ChromeDriver进程强制终止失败")

        # 3. 移除用户映射（最后操作，避免监控线程重复处理）
        self.user_driver_map.pop(key)
        self.logger.info(f"Context映射已移除，资源清理完成")

    async def kill_residual_chromedriver(self):
        """兜底方案：杀死所有残留的chromedriver.exe进程（可选）"""
        try:
            for proc in psutil.process_iter(['pid', 'name']):
                if proc.info['name'] and 'chromedriver.exe' in proc.info['name'].lower():
                    try:
                        proc.terminate()
                        self.logger.info(f"已终止残留的chromedriver进程，PID: {proc.info['pid']}")
                    except Exception:
                        self.logger.warning(f"终止残留chromedriver进程（PID:{proc.info['pid']}）失败")
        except Exception:
            self.logger.exception("清理残留chromedriver进程时异常")
