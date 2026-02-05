import threading
import time
from enum import Enum
from pathlib import Path
from typing import Dict, Optional, Any, Tuple

from DrissionPage import ChromiumOptions, Chromium
from DrissionPage.common import Settings
from src.frame.dto.driver_config import DriverConfig  # 保留你原有的配置类
from src.utils import basic, Md5Utils, ProcessUtils
from src.utils.sys_path_utils import SysPathUtils

Settings.set_language("zh_cn").set_raise_when_ele_not_found(True).set_raise_when_click_failed(True)

class DriverMode(Enum):
    """驱动模式枚举（适配DrissionPage的特性）"""
    INCOGNITO = "1"  # 无痕模式
    PERSISTENT = "0"  # 持久化模式

class WebDriverManager:
    """基于DrissionPage的网页驱动管理器：一个用户名对应一个Driver实例"""

    def __init__(self, logger):
        # 映射结构：(用户名, 批次号) -> {
        #   page: ChromiumPage,  # DrissionPage的核心对象（包含browser和context）
        #   driver: WebDriver,   # 底层WebDriver对象（用于进程管控）
        #   monitor_thread: threading.Thread,
        #   is_running: bool,
        #   mode: DriverMode,    # 驱动模式（无痕/持久化）
        #   user_data_dir: str   # 持久化模式的用户数据目录
        # }
        self.user_driver_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.lock = threading.Lock()  # 线程锁（DrissionPage为同步库，用线程锁即可）
        self.logger = logger

    def create_user_driver(self, username: str, batch_no: str, driver_config: DriverConfig) -> Chromium:
        """
        为指定用户创建专属Driver（已存在则返回现有Driver）
        :param username: 用户名
        :param batch_no: 任务批次号
        :param driver_config: 浏览器配置
        :return: 用户专属ChromiumPage实例
        """
        with self.lock:
            key = (username, batch_no)
            # 已存在且运行中，直接返回
            if key in self.user_driver_map and self.user_driver_map[key]['is_running']:
                self.logger.info(f"用户 {username} 批次 {batch_no} 已存在Driver，直接返回")
                return self.user_driver_map[key]['browser']

            # 创建新Driver实例
            driver_info = self._create_new_driver(username, driver_config)
            self.user_driver_map[key] = driver_info
            # 启动监控线程（可选，检测浏览器是否被手动关闭）
            # self._start_monitor_thread(username, batch_no)
            self.logger.info(f"用户 {username} 批次 {batch_no} 创建Driver成功！")
            return driver_info['browser']

    def _create_new_driver(self, username: str, driver_config: DriverConfig) -> Dict[str, Any]:
        """
        创建DrissionPage的Driver实例（区分无痕/持久化模式）
        :param username: 用户名
        :param driver_config: 驱动配置
        :return: driver_info字典
        """
        # 1. 初始化浏览器配置
        chrome_options = self._set_chrome_options(driver_config)
        user_data_dir = None
        browser: Optional[Chromium] = None
        # driver: Optional[Driver] = None
        mode = DriverMode(driver_config.incognito_mode)
        if mode == DriverMode.INCOGNITO:
            # 无痕模式：启动独立的无痕浏览器实例
            browser = Chromium(chrome_options)
        else:
            # 持久化模式：每个用户独立的用户数据目录
            user_data_root = Path(SysPathUtils.get_root_dir(), "user_data")
            user_data_dir = str(user_data_root / f"user_{Md5Utils.encrypt(username)}")
            # 创建目录（DrissionPage不会自动创建）
            Path(user_data_dir).mkdir(parents=True, exist_ok=True)

            # 启动持久化浏览器
            chrome_options.set_user_data_path(user_data_dir)
            browser = Chromium(chrome_options)

        # 获取元素默认不等待
        # browser.latest_tab.set.timeouts(0)
        # 最大化窗口
        browser.latest_tab.set.window.max()
        # 2. 基础配置（适配视频播放/页面优化）
        # self._optimize_page(browser, driver_config)
        # 封装返回信息
        return {
            'browser': browser,
            'driver': None,
            'monitor_thread': None,
            'is_running': True,
            'mode': mode,
            'process_id': browser.process_id,  # 获取进程ID
            'user_data_dir': user_data_dir
        }

    def _set_chrome_options(self, driver_config: DriverConfig) -> ChromiumOptions:
        """
        构建DrissionPage的Chrome配置（适配多实例低CPU占用）
        :param driver_config: 驱动配置
        :return: ChromiumOptions实例
        """
        chrome_options = ChromiumOptions().auto_port(True)
        if driver_config.incognito_mode == "1":
            chrome_options.incognito(True)

        if driver_config.headless_mode == "1":
            chrome_options.headless(True)

        # Chrome可执行文件路径（适配360极速浏览器等）
        if driver_config.browser_exe_position:
            exe_path = Path(driver_config.browser_exe_position)
            if not exe_path.is_absolute():
                exe_path = Path(SysPathUtils.get_root_dir(), driver_config.browser_exe_position)
            if exe_path.exists():
                chrome_options.set_browser_path(str(exe_path))
            else:
                raise ValueError(f"Chrome可执行文件不存在: {exe_path}")

        # 调试端口（如果配置）
        if driver_config.hook_port:
            chrome_options.set_local_port(driver_config.hook_port)

        chrome_options.mute(True)  # 静音

        # 核心优化参数（适配多实例、低CPU、视频播放）
        common_args = [
            # "--no-sandbox",  # 禁用沙箱（降低CPU占用）
            # "--disable-gpu",  # 禁用GPU（低配置兼容，视频播放可开启）
            "--disable-extensions",  # 禁用扩展
            "--disable-dev-shm-usage",  # 减少内存占用
            "--disable-background-timer-throttling",  # 禁用后台定时器节流
            "--enable-network-cache=true",  # 开启网络缓存
            "--disk-cache-size=1073741824",  # 缓存大小1G
            "--lang=zh-CN",
            "--accept-lang=zh-CN,zh;q=0.9,en;q=0.8",
        ]

        # 无头模式（如果配置开启）
        if driver_config.headless_mode == "1":
            common_args.extend([
                # "--disable-software-rasterizer"  # 禁用软件渲染
            ])

        # 添加自定义参数
        for arg in common_args:
            chrome_options.set_argument(arg)

        return chrome_options

    def _optimize_page(self, page: Chromium, driver_config: DriverConfig):
        """
        优化页面配置（适配视频播放、降低CPU）
        :param page: ChromiumPage实例
        :param driver_config: 驱动配置
        """
        # 1. 页面加载策略（优先加载核心资源，适配视频）
        page.set_load_strategy('eager')  # 不等待所有资源加载完成

        # 2. 禁用页面动画/广告（降低CPU）
        page.run_js("""
            // 禁用页面动画
            document.documentElement.style.animation = 'none';
            document.documentElement.style.transition = 'none';
            // 禁用广告脚本
            window.addEventListener('load', () => {
                document.querySelectorAll('script[src*=ad], script[src*=stat]').forEach(s => s.remove());
            });
        """)

        # 3. 视频播放优化（自动全屏/静音，可选）
        if driver_config.incognito_mode == "1":
            page.run_js("""
                // 自动播放视频（静音）
                const videos = document.querySelectorAll('video');
                videos.forEach(v => {
                    v.muted = true;
                    v.play().catch(e => console.log('视频自动播放失败:', e));
                });
            """)

    def _start_monitor_thread(self, username: str, batch_no: str):
        """启动浏览器监控线程（检测是否被手动关闭）"""
        key = (username, batch_no)

        def monitor_func():
            while True:
                with self.lock:
                    driver_info = self.user_driver_map.get(key)
                    if not driver_info or not driver_info['is_running']:
                        self.logger.info(f"监控线程：用户 {username} 批次 {batch_no} Driver已停止，退出监控")
                        return

                try:
                    # 检测浏览器是否存活
                    driver_info['browser'].latest_tab.title  # 简单检测页面是否可用
                    time.sleep(1)
                except Exception:
                    self.logger.warning(f"用户 {username} 批次 {batch_no} 浏览器已关闭/通信失败")
                    with self.lock:
                        self._cleanup_driver(key)
                    return

        # 启动守护线程
        monitor_thread = threading.Thread(
            target=monitor_func,
            name=f"Monitor-[{basic.mask_username(username)}]"
        )
        monitor_thread.daemon = True
        self.user_driver_map[key]['monitor_thread'] = monitor_thread
        monitor_thread.start()
        self.logger.info(f"用户 {username} 批次 {batch_no} 监控线程已启动")

    def get_user_driver(self, username: str, batch_no: str) -> Optional[Chromium]:
        """获取用户专属Driver（仅返回运行中的）"""
        with self.lock:
            driver_info = self.user_driver_map.get((username, batch_no))
            if driver_info and driver_info['is_running']:
                return driver_info['browser']
            return None

    def remove_user_driver(self, batch_no: Optional[str] = None, username: Optional[str] = None):
        """移除指定用户/批次的Driver"""
        self.logger.info(f"开始移除Driver (用户名: {username}, 批次: {batch_no})")
        with self.lock:
            if username:
                keys = [k for k in self.user_driver_map.keys() if k[0] == username]
            elif batch_no:
                keys = [k for k in self.user_driver_map.keys() if k[1] == batch_no]
            else:
                return

            for key in keys:
                self._cleanup_driver(key)

    def clear_all_drivers(self):
        """清空所有用户的Driver"""
        self.logger.debug("开始清空所有用户的Driver")
        with self.lock:
            for key in list(self.user_driver_map.keys()):
                self._cleanup_driver(key)

    def _cleanup_driver(self, key: Tuple[str, str]):
        """清理单个用户的Driver资源"""
        driver_info = self.user_driver_map.get(key)
        if not driver_info:
            return

        username, batch_no = key
        self.logger.debug(f"开始清理用户 {username} 批次 {batch_no} 的Driver资源")

        # 标记为停止运行
        driver_info['is_running'] = False

        # 1. 停止监控线程
        monitor_thread = driver_info.get('monitor_thread')
        if monitor_thread and monitor_thread.is_alive():
            # 线程是守护线程，无需手动终止，标记状态即可
            self.logger.debug(f"监控线程已停止")

        # 2. 关闭页面/浏览器
        try:
            page: Chromium = driver_info['browser']
            # 先关闭所有标签页
            for tab in page.get_tabs():
                tab.close()
            # 关闭浏览器进程（核心：DrissionPage的kill方法可强制终止进程）
            page.quit(force=True)  # force=True 强制杀死进程，避免残留
            self.logger.debug(f"用户 {username} 批次 {batch_no} Driver已正常关闭")
        except Exception as e:
            self.logger.warning(f"用户 {username} 批次 {batch_no} Driver关闭失败: {str(e)}")
            # 兜底：强制杀死浏览器进程和子进程
            ProcessUtils.kill_process_tree(driver_info['process_id'])

        # 3. 移除映射
        self.user_driver_map.pop(key)
        self.logger.debug(f"用户 {username} 批次 {batch_no} 资源清理完成")

    def close(self):
        """关闭所有资源"""
        self.clear_all_drivers()
        self.logger.info("所有Driver资源已清理完成")

    def is_empty(self) -> bool:
        """判断驱动是否为空"""
        return not self.user_driver_map
