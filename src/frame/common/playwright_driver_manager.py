# ./framework/driver_manager.py
import asyncio
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Any, Tuple

import psutil
from playwright.async_api import BrowserContext, Playwright
from playwright.async_api import async_playwright, Browser

from src.frame.common.playwright_stealth.stealth import Stealth
from src.frame.dto.driver_config import DriverConfig
from src.utils import basic, Md5Utils
from src.utils.sys_path_utils import SysPathUtils


class WebDriverManager:
    """网页驱动映射管理器：确保一个用户名对应一个Driver"""

    def __init__(self, logger):
        # 扩展映射结构：(用户名, 批次号) -> {
        #   driver: BrowserContext/Browser,
        #   chrome_pid: int,
        #   monitor_thread: threading.Thread,
        #   is_running: bool,
        #   is_persistent: bool,  # 是否为持久化模式
        #   playwright: Playwright  # 每个用户独立的playwright实例（持久化模式）
        # }
        self.user_driver_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        # 协程锁
        self.lock = asyncio.Lock()
        self.logger = logger
        # self._playwright = None
        # self._browser: Optional[Browser] = None
        # 全局playwright（仅用于无痕模式）
        self._global_playwright: Optional[Playwright] = None
        self._global_browser: Optional[Browser] = None

    async def _init_playwright(self):
        """初始化Playwright上下文（全局唯一）"""
        if self._playwright is None:
            self._playwright = await async_playwright().start()

    async def _init_browser(self, driver_config: DriverConfig):
        if not self._browser:
            # 1. 构建浏览器启动参数
            launch_options = await self._set_launch_options(driver_config)
            # 2. 启动浏览器（Chrome）
            if driver_config.incognito_mode == "1":
                self._browser = await self._playwright.chromium.launch(**launch_options)
            else:
                user_data_dir = Path(SysPathUtils.get_root_dir(), "userData")
                self._browser = await self._playwright.chromium.launch_persistent_context(user_data_dir=user_data_dir,
                                                                                          **launch_options)

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

            driver_info = await self.create_new_context(username, driver_config)
            self.user_driver_map[key] = driver_info
            self.logger.info(f"批次 {batch_no} 创建Context成功！")
            return driver_info.get('context')

    async def create_new_context_bak(self, driver_config: DriverConfig):
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

    async def create_new_context(self, username: str, driver_config: DriverConfig) -> Dict[str, Any]:
        """
        创建playwright的context（区分无痕/非无痕模式）
        :param username: 用户名（用于生成独立的持久化目录）
        :param driver_config: 驱动配置信息
        :return: driver_info字典
        """
        is_incognito = driver_config.incognito_mode == "1"
        context: Optional[BrowserContext] = None
        chrome_pid = 0
        playwright_instance: Optional[Playwright] = None

        # 1. 构建启动参数
        launch_options = await self._set_launch_options(driver_config)

        if is_incognito:
            # 无痕模式：使用全局browser创建context
            await self._init_global_playwright()
            if not self._global_browser:
                self._global_browser = await self._global_playwright.chromium.launch(**launch_options)

            # 创建无痕上下文
            context_options = await self._set_context_options(driver_config)
            context = await self._global_browser.new_context(**context_options)
            # 获取浏览器进程PID
            # chrome_pid = self._global_browser.process.pid if self._global_browser.process else 0
        else:
            # 非无痕模式：创建持久化上下文（每个用户独立）
            playwright_instance = await async_playwright().start()

            # 为每个用户创建独立的持久化目录
            user_data_root = Path(SysPathUtils.get_root_dir(), "user_data")
            user_data_dir = user_data_root / f"user_{Md5Utils.encrypt(username)}"
            user_data_dir.mkdir(parents=True, exist_ok=True)

            # 启动持久化浏览器（返回的是BrowserContext类型）
            context = await playwright_instance.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                # user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
                **launch_options,
                **await self._set_context_options(driver_config)
            )
            # 获取进程PID
            # chrome_pid = context.browser.process.pid if context.browser and context.browser.process else 0

        # 2. 应用stealth
        # await self.setup_stealth_for_context(context)

        # 3. 非无痕模式下如果没有页面，才创建新页面（避免重复创建）
        if not context.pages:
            await context.new_page()

        # 封装返回信息
        driver_info = {
            'context': context,
            'chrome_pid': "",
            'monitor_thread': None,
            'is_running': True,
            'is_persistent': not is_incognito,
            'playwright': playwright_instance  # 持久化模式保存playwright实例
        }
        return driver_info

    async def _init_global_playwright(self):
        """初始化全局Playwright（仅用于无痕模式）"""
        if self._global_playwright is None:
            self._global_playwright = await async_playwright().start()

    async def setup_stealth_for_context(self, context: BrowserContext):
        """封装函数：为上下文绑定自动stealth"""

        async def apply_stealth(page):
            # 页面创建后立即应用stealth
            await Stealth().apply_stealth_async(page)

        # 1. 先为已存在的页面（非无痕模式的默认页面）主动应用stealth
        for page in context.pages:
            await apply_stealth(page)

        # 2. 绑定事件：所有通过该context新建的页面，都会自动执行apply_stealth
        context.on("page", apply_stealth)

    async def close_bak(self):
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()

    async def close(self):
        """关闭全局资源"""
        # 先清理所有用户driver
        await self.clear_all_drivers()

        # 关闭全局browser和playwright
        if self._global_browser:
            await self._global_browser.close()
        if self._global_playwright:
            await self._global_playwright.stop()

    async def get_user_driver(self, username: str, batch_no: str) -> Optional[BrowserContext]:
        """获取用户专属Driver（仅返回运行中的Driver）"""
        async with self.lock:
            driver_info = self.user_driver_map.get((username, batch_no))
            if driver_info and driver_info['is_running']:
                return driver_info['context']
            return None

    async def _set_launch_options_bak(self, driver_config: DriverConfig) -> dict:
        """
        构建 Playwright 浏览器启动参数
        :return: launch参数字典
        """
        launch_options = {
            "headless": driver_config.headless_mode == "1",  # Playwright 无头模式更简洁
            "args": [
                "--lang=zh-CN",  # 语言设置
                # 设置接受的语言优先级（中文第一，英文兜底）
                "--accept-lang=zh-CN,zh;q=0.9,en;q=0.8",
                # 禁用语言自动检测（可选，避免覆盖手动设置）
                "--disable-features=TranslateUI,LanguageDetection"
                "--mute-audio",  # 静音
                "--disable-gpu",  # 禁用GPU（兼容低配置）
                "--start-maximized",  # 窗口最大化。配合context的no_viewport=True属性实现最大化
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

    async def _set_launch_options(self, driver_config: DriverConfig) -> dict:
        """构建 Playwright 浏览器启动参数（自动区分无痕/非无痕模式参数）"""
        is_incognito = driver_config.incognito_mode == "1"

        # 1. 通用参数（所有模式都生效）
        common_args = [
            "--lang=zh-CN",  # 语言设置
            # 设置接受的语言优先级（中文第一，英文兜底）
            # "--accept-lang=zh-CN,zh;q=0.9,en;q=0.8",
            # 禁用语言自动检测（可选，避免覆盖手动设置）
            # "--disable-features=TranslateUI,LanguageDetection"
            "--mute-audio",  # 静音
            # "--disable-gpu",  # 禁用GPU（兼容低配置）
            "--start-maximized",  # 窗口最大化。配合context的no_viewport=True属性实现最大化
            "--disable-popup-blocking"  # 禁用弹窗拦截（防止新窗口被拦截）
            # 核心反检测（必须保留）
            # "--disable-blink-features=AutomationControlled",
            # 通用兼容参数
            # "--no-sandbox",
            # "--disable-dev-shm-usage",
            # "--disable-extensions",
            # "--disable-web-security",
            # "--ignore-certificate-errors",
            # "--no-service-autorun",
            # "--password-store=basic",
        ]

        # 2. 仅非无痕模式生效的参数
        non_incognito_args = [
            # "--disable-infobars",  # 关闭自动化提示栏（无痕模式无此提示）
            # "--no-first-run",  # 禁用首次运行提示
            # "--no-default-browser-check"  # 禁用默认浏览器检测
        ]

        # 3. 合并参数（根据模式自动筛选）
        final_args = common_args
        if not is_incognito:
            final_args.extend(non_incognito_args)

        # 4. 构建最终启动参数
        launch_options = {
            "headless": driver_config.headless_mode == "1",
            "args": final_args,
            # 核心：禁用Playwright默认自动化参数（所有模式通用）
            # "channel": "msedge",
            "channel": "chrome",
            # "ignore_default_args": ["--enable-automation"]
        }

        # Chrome可执行文件路径（通用逻辑）
        if driver_config.browser_exe_position:
            exe_path = Path(driver_config.browser_exe_position)
            if not exe_path.is_absolute():
                exe_path = Path(SysPathUtils.get_root_dir(), driver_config.browser_exe_position)
            if exe_path.exists():
                launch_options["executable_path"] = str(exe_path)
            else:
                raise ValueError(f"Chrome可执行文件不存在: {exe_path}")

        # 调试端口（通用逻辑）
        if driver_config.hook_port:
            launch_options["args"].append(f"--remote-debugging-port={driver_config.hook_port}")

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
            # "timezone_id": "Asia/Shanghai",
            # 最大化窗口的配置
            "no_viewport": True,
            # "extra_http_headers": {
            #     "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"  # 对所有请求强制中文
            # }
        }
        return context_options

    async def remove_user_driver(self, batch_no: Optional[str] = None, username: Optional[str] = None):
        """
        移除用户Driver映射（并关闭Driver、终止进程、停止监控）
        :param batch_no: 批次号
        :param username: 用户名
        :return:
        """
        self.logger.info(f"开始移除Context (用户名: {username}, 批次: {batch_no})")
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
        self.logger.debug("开始清空所有用户的Context")
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

    async def _cleanup_driver_bak(self, key: Tuple[str, str]):
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

    async def _cleanup_driver(self, key: Tuple[str, str]):
        """清理单个用户的Driver资源"""
        driver_info = self.user_driver_map.get(key)
        if not driver_info:
            return

        username, batch_no = key
        self.logger.debug(f"开始清理用户 {username} 批次 {batch_no} 的Driver资源")

        # 标记为停止运行
        driver_info['is_running'] = False

        # 1. 关闭Context/Browser
        context: BrowserContext = driver_info.get('context')
        if context:
            try:
                await context.close()
                self.logger.debug(f"Context已正常关闭")
            except Exception as e:
                self.logger.warning(f"Context关闭失败: {str(e)}")

        # 2. 停止持久化模式的playwright实例
        if driver_info.get('is_persistent'):
            playwright_instance = driver_info.get('playwright')
            if playwright_instance:
                try:
                    await playwright_instance.stop()
                    self.logger.debug(f"Playwright实例已停止")
                except Exception as e:
                    self.logger.warning(f"Playwright实例停止失败: {str(e)}")

        # 3. 终止浏览器进程（兜底）
        # chrome_pid = driver_info.get('chrome_pid')
        # if chrome_pid and psutil.pid_exists(chrome_pid):
        #     try:
        #         proc = psutil.Process(chrome_pid)
        #         proc.terminate()
        #         self.logger.info(f"Chrome进程(PID:{chrome_pid})已终止")
        #     except Exception as e:
        #         self.logger.warning(f"终止Chrome进程失败: {str(e)}")

        # 4. 移除映射
        self.user_driver_map.pop(key)
        self.logger.debug(f"用户 {username} 批次 {batch_no} 资源清理完成")

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


class WebDriverManagerBak:
    """网页驱动映射管理器：确保一个用户名对应一个Driver"""

    def __init__(self, logger):
        # 扩展映射结构：(用户名, 批次号) -> {
        #   driver: BrowserContext/Browser,
        #   monitor_thread: threading.Thread,
        #   is_running: bool,
        #   is_persistent: bool,  # 是否为持久化模式
        #   playwright: Playwright  # 每个用户独立的playwright实例（所有模式）
        #   browser: Browser  # 每个用户独立的Browser实例（仅无痕模式）
        # }
        self.user_driver_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        # 协程锁
        self.lock = asyncio.Lock()
        self.logger = logger

    async def create_user_driver(self, username: str, batch_no: str, driver_config: DriverConfig) -> BrowserContext:
        """
        为指定用户创建专属Driver（已存在则返回现有Driver），并启动进程监控
        :param username: 用户名
        :param driver_config: 浏览器配置
        :param batch_no: 任务批次号
        :return: 用户专属Driver
        """
        async with self.lock:  # 加锁保证线程安全
            key = (username, batch_no)
            # 若用户已存在Driver且处于运行状态，直接返回
            if key in self.user_driver_map and self.user_driver_map[key]['is_running']:
                self.logger.info(f"用户 {username} 批次 {batch_no} 已存在Context，直接返回")
                return self.user_driver_map[key]['context']

            driver_info = await self.create_new_context(username, driver_config)
            self.user_driver_map[key] = driver_info
            self.logger.info(f"用户 {username} 批次 {batch_no} 创建Context成功！")
            return driver_info.get('context')

    async def create_new_context(self, username: str, driver_config: DriverConfig) -> Dict[str, Any]:
        """
        创建playwright的context（所有模式都使用独立的Playwright实例）
        :param username: 用户名（用于生成独立的持久化目录）
        :param driver_config: 驱动配置信息
        :return: driver_info字典
        """
        is_incognito = driver_config.incognito_mode == "1"
        context: Optional[BrowserContext] = None
        playwright_instance: Optional[Playwright] = None
        browser_instance: Optional[Browser] = None

        # 1. 为每个用户启动独立的Playwright实例（无论是否无痕）
        playwright_instance = await async_playwright().start()

        # 2. 构建启动参数
        launch_options = await self._set_launch_options(driver_config)

        if is_incognito:
            # 无痕模式：每个用户独立的Browser + Context
            browser_instance = await playwright_instance.chromium.launch(**launch_options)

            # 创建无痕上下文
            context_options = await self._set_context_options(driver_config)
            context = await browser_instance.new_context(**context_options)
        else:
            # 非无痕模式：创建持久化上下文（每个用户独立）
            # 为每个用户创建独立的持久化目录
            user_data_root = Path(SysPathUtils.get_root_dir(), "user_data")
            user_data_dir = user_data_root / f"user_{Md5Utils.encrypt(username)}"
            user_data_dir.mkdir(parents=True, exist_ok=True)

            # 启动持久化浏览器（返回的是BrowserContext类型）
            context = await playwright_instance.chromium.launch_persistent_context(
                user_data_dir=str(user_data_dir),
                **launch_options,
                **await self._set_context_options(driver_config)
            )

        # 3. 应用stealth
        await self.setup_stealth_for_context(context)

        # 4. 如果没有页面，创建新页面（避免重复创建）
        if not context.pages:
            await context.new_page()

        # 封装返回信息
        driver_info = {
            'context': context,
            'monitor_thread': None,
            'is_running': True,
            'is_persistent': not is_incognito,
            'playwright': playwright_instance,  # 所有模式都保存playwright实例
            'browser': browser_instance  # 仅无痕模式有值
        }
        return driver_info

    async def setup_stealth_for_context(self, context: BrowserContext):
        """封装函数：为上下文绑定自动stealth"""

        async def apply_stealth(page):
            # 页面创建后立即应用stealth
            await Stealth().apply_stealth_async(page)

        # 1. 先为已存在的页面主动应用stealth
        for page in context.pages:
            await apply_stealth(page)

        # 2. 绑定事件：所有通过该context新建的页面，都会自动执行apply_stealth
        context.on("page", apply_stealth)

    async def close(self):
        """关闭所有资源"""
        # 先清理所有用户driver
        await self.clear_all_drivers()

    async def get_user_driver(self, username: str, batch_no: str) -> Optional[BrowserContext]:
        """获取用户专属Driver（仅返回运行中的Driver）"""
        async with self.lock:
            driver_info = self.user_driver_map.get((username, batch_no))
            if driver_info and driver_info['is_running']:
                return driver_info['context']
            return None

    async def _set_launch_options(self, driver_config: DriverConfig) -> dict:
        """构建 Playwright 浏览器启动参数（自动区分无痕/非无痕模式参数）"""
        is_incognito = driver_config.incognito_mode == "1"

        # 1. 通用参数（所有模式都生效）
        common_args = [
            "--lang=zh-CN",  # 语言设置
            # 设置接受的语言优先级（中文第一，英文兜底）
            "--accept-lang=zh-CN,zh;q=0.9,en;q=0.8",
            # 禁用语言自动检测（可选，避免覆盖手动设置）
            "--disable-features=TranslateUI,LanguageDetection"
            "--mute-audio",  # 静音
            "--start-maximized",  # 窗口最大化。配合context的no_viewport=True属性实现最大化

            # 核心：禁用沙箱（最大的CPU开销之一，测试/自用场景完全可关）
            "--no-sandbox",
            "--disable-setuid-sandbox",
            # 禁用自动化相关开销
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",  # 禁用/dev/shm使用，减少进程通信开销
            "--disable-extensions",  # 禁用扩展框架
            "--disable-extensions-except=",
            "--disable-plugin-power-saver",  # 禁用插件节能（无插件时无用）
            # 渲染层优化（视频播放核心）
            "--enable-gpu-hardware-aceleration",  # 强制开启GPU硬件加速，把绘制/解码交给显卡
            "--gpu-rasterization-msaa-sample-count=0",  # 关闭抗锯齿，减少GPU/CPU开销
            "--disable-software-rasterizer",  # 禁用软件渲染，强制用GPU
            # 网络层优化（共享连接/缓存，视频复用核心）
            "--enable-network-cache=true",  # 开启网络缓存
            "--disk-cache-size=1073741824",  # 设置缓存大小1G，足够存视频资源
            "--keep-alive-timeout=300",  # 延长连接池超时，复用HTTP连接
            # 裁剪无用功能
            "--disable-background-timer-throttling",  # 禁用后台定时器节流（视频播放无需）
            "--disable-backgrounding-occluded-windows",  # 禁用窗口遮挡时的后台化
            "--disable-features=TranslateUI,LanguageDetection,PrintPreview",
            "--disable-logging",  # 禁用Chrome日志
            "--disable-v8-idle-tasks",  # 禁用V8引擎的空闲任务，减少CPU空转
        ]

        # 2. 仅非无痕模式生效的参数
        non_incognito_args = [
            # "--disable-infobars",  # 关闭自动化提示栏（无痕模式无此提示）
            # "--no-first-run",  # 禁用首次运行提示
            # "--no-default-browser-check"  # 禁用默认浏览器检测
        ]

        # 3. 合并参数（根据模式自动筛选）
        final_args = common_args
        if not is_incognito:
            final_args.extend(non_incognito_args)

        # 4. 构建最终启动参数
        launch_options = {
            "headless": driver_config.headless_mode == "1",
            "args": final_args,
            # 核心：禁用Playwright默认自动化参数（所有模式通用）
            "channel": "chrome",
            # "ignore_default_args": ["--enable-automation"]
        }

        # Chrome可执行文件路径（通用逻辑）
        if driver_config.browser_exe_position:
            exe_path = Path(driver_config.browser_exe_position)
            if not exe_path.is_absolute():
                exe_path = Path(SysPathUtils.get_root_dir(), driver_config.browser_exe_position)
            if exe_path.exists():
                launch_options["executable_path"] = str(exe_path)
            else:
                raise ValueError(f"Chrome可执行文件不存在: {exe_path}")

        # 调试端口（通用逻辑）
        if driver_config.hook_port:
            launch_options["args"].append(f"--remote-debugging-port={driver_config.hook_port}")

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
            "no_viewport": True,
        }
        return context_options

    async def remove_user_driver(self, batch_no: Optional[str] = None, username: Optional[str] = None):
        """
        移除用户Driver映射（并关闭Driver、终止进程、停止监控）
        :param batch_no: 批次号
        :param username: 用户名
        :return:
        """
        self.logger.info(f"开始移除Context (用户名: {username}, 批次: {batch_no})")
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
        self.logger.debug("开始清空所有用户的Context")
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
                        self.logger.info(f"监控线程：用户 {username} 批次 {batch_no} Context已停止，退出监控")
                        return

                try:
                    # 检测Driver是否还能正常通信
                    try:
                        # 简单检测context是否可用
                        _ = len(driver_info['context'].pages)
                    except Exception:
                        self.logger.warning(f"用户 {username} 批次 {batch_no} Context与浏览器通信失败")
                        async with self.lock:
                            await self._cleanup_driver(key)
                        return

                    await asyncio.sleep(1)  # 每秒检测一次，可根据需求调整
                except Exception:
                    self.logger.exception(f"用户 {username} 批次 {batch_no} 监控线程异常：")
                    async with self.lock:
                        await self._cleanup_driver(key)
                    return

        # 启动监控任务（使用asyncio而非threading，避免线程/协程混用问题）
        asyncio.create_task(monitor_func())
        self.logger.info(f"用户 {username} 批次 {batch_no} 浏览器监控任务已启动")

    def is_empty(self) -> bool:
        """判断驱动是否为空"""
        return not self.user_driver_map

    async def _cleanup_driver(self, key: Tuple[str, str]):
        """清理单个用户的Driver资源"""
        driver_info = self.user_driver_map.get(key)
        if not driver_info:
            return

        username, batch_no = key
        self.logger.debug(f"开始清理用户 {username} 批次 {batch_no} 的Driver资源")

        # 标记为停止运行
        driver_info['is_running'] = False

        # 1. 关闭Context
        context: BrowserContext = driver_info.get('context')
        if context:
            try:
                await context.close()
                self.logger.debug(f"用户 {username} 批次 {batch_no} Context已正常关闭")
            except Exception as e:
                self.logger.warning(f"用户 {username} 批次 {batch_no} Context关闭失败: {str(e)}")

        # 2. 关闭无痕模式的Browser实例
        browser: Browser = driver_info.get('browser')
        if browser:
            try:
                await browser.close()
                self.logger.debug(f"用户 {username} 批次 {batch_no} Browser已正常关闭")
            except Exception as e:
                self.logger.warning(f"用户 {username} 批次 {batch_no} Browser关闭失败: {str(e)}")

        # 3. 停止当前用户的Playwright实例（所有模式都需要）
        playwright_instance = driver_info.get('playwright')
        if playwright_instance:
            try:
                await playwright_instance.stop()
                self.logger.debug(f"用户 {username} 批次 {batch_no} Playwright实例已停止")
            except Exception as e:
                self.logger.warning(f"用户 {username} 批次 {batch_no} Playwright实例停止失败: {str(e)}")

        # 4. 移除映射
        self.user_driver_map.pop(key)
        self.logger.debug(f"用户 {username} 批次 {batch_no} 资源清理完成")