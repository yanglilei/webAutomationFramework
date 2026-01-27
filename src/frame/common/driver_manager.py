# ./framework/driver_manager.py
import threading
import time
from typing import Dict, Optional, Any

import psutil
from selenium.common import WebDriverException
from undetected_chromedriver import Chrome

from src.frame.common.decorator.singleton import singleton
from src.frame.common.web_driver_maker import WebDriverMaker
from src.frame.dto.driver_config import DriverConfig
from src.utils import basic


@singleton
class WebDriverManager:
    """网页驱动映射管理器：确保一个用户名对应一个Driver"""

    def __init__(self, logger):
        # 扩展映射结构：用户名 -> {driver: Chrome, chrome_pid: int, driver_service: Service, monitor_thread: threading.Thread, is_running: bool}
        self.user_driver_map: Dict[str, Dict[str, Any]] = {}
        # 线程锁：保证多用户并发操作时的数据安全
        self.map_lock = threading.Lock()
        self.logger = logger

    def create_user_driver(self, username: str, driver_config: DriverConfig) -> Optional[Chrome]:
        """
        为指定用户创建专属Driver（已存在则返回现有Driver），并启动进程监控
        :param username: 用户名
        :param driver_config: 浏览器配置
        :return: 用户专属Driver
        """
        with self.map_lock:  # 加锁保证线程安全
            # 若用户已存在Driver且处于运行状态，直接返回
            if username in self.user_driver_map and self.user_driver_map[username]['is_running']:
                self.logger.info(f"用户[{basic.mask_username(username)}]已存在Driver，直接返回")
                return self.user_driver_map[username]['driver']

            try:
                # 创建Driver（复用原有WebDriverMaker逻辑）
                driver = WebDriverMaker.make(username, driver_config)
                driver.maximize_window()
                if not driver:
                    self.logger.error(f"用户[{basic.mask_username(username)}]创建Driver失败：WebDriverMaker返回空")
                    return None

                # 获取Chrome浏览器PID和Driver Service
                chrome_pid = driver._get_chrome_pid() if driver_config.is_selenium_wire == "1" else driver.browser_pid
                if not chrome_pid:
                    self.logger.warning(f"用户[{basic.mask_username(username)}]创建Driver成功，但未获取到Chrome PID")
                driver_service = driver.service

                # 封装用户Driver相关信息
                driver_info = {
                    'driver': driver,
                    'chrome_pid': chrome_pid,
                    'driver_service': driver_service,
                    'monitor_thread': None,
                    'is_running': True
                }
                self.user_driver_map[username] = driver_info
                self.logger.info(f"用户[{basic.mask_username(username)}]创建Driver成功，Chrome PID: {chrome_pid}")

                # 启动该用户的浏览器监控线程
                self._start_monitor_thread(username)
                return driver
            except Exception:
                self.logger.exception(f"为用户[{basic.mask_username(username)}]创建Driver失败：")
                # 清理创建过程中可能产生的残留
                self._cleanup_driver(username)
                return None

    def get_user_driver(self, username: str) -> Optional[Chrome]:
        """获取用户专属Driver（仅返回运行中的Driver）"""
        with self.map_lock:
            driver_info = self.user_driver_map.get(username)
            if driver_info and driver_info['is_running']:
                return driver_info['driver']
            return None

    def remove_user_driver(self, username: str):
        """移除用户Driver映射（并关闭Driver、终止进程、停止监控）"""
        self.logger.info(f"开始移除用户[{basic.mask_username(username)}]的Driver映射")
        with self.map_lock:
            self._cleanup_driver(username)

    def clear_all_drivers(self):
        """清空所有用户的Driver（批量清理）"""
        self.logger.info("开始清空所有用户的Driver")
        with self.map_lock:
            for username in list(self.user_driver_map.keys()):
                self._cleanup_driver(username)

    def _start_monitor_thread(self, username: str):
        """为指定用户启动浏览器监控线程（后台检测浏览器是否被手动关闭）"""

        # 定义监控逻辑
        def monitor_func():
            while True:
                # 每次循环先检查锁，确认用户Driver是否仍在运行
                with self.map_lock:
                    driver_info = self.user_driver_map.get(username)
                    # 终止条件：用户Driver已被清理/不再运行
                    if not driver_info or not driver_info['is_running']:
                        self.logger.info(f"用户[{basic.mask_username(username)}]的监控线程：Driver已停止，退出监控")
                        return

                try:
                    # 1. 检测Chrome浏览器进程是否存活
                    if not psutil.pid_exists(driver_info['chrome_pid']):
                        self.logger.warning(
                            f"用户[{basic.mask_username(username)}]的Chrome浏览器（PID:{driver_info['chrome_pid']}）已被手动关闭")
                        # 自动清理该用户的Driver
                        with self.map_lock:
                            self._cleanup_driver(username)
                        return

                    # 2. 额外检测：Driver是否还能正常通信（防止进程存在但浏览器无响应）
                    try:
                        driver_info['driver'].current_url
                    except WebDriverException:
                        self.logger.warning(f"用户[{basic.mask_username(username)}]的Driver与浏览器通信失败")
                        with self.map_lock:
                            self._cleanup_driver(username)
                        return

                    time.sleep(1)  # 每秒检测一次，可根据需求调整
                except Exception:
                    self.logger.exception(f"用户[{basic.mask_username(username)}]的监控线程异常")
                    with self.map_lock:
                        self._cleanup_driver(username)
                    return

        # 启动守护线程（主程序退出时自动结束）
        monitor_thread = threading.Thread(target=monitor_func, name=f"Monitor-[{basic.mask_username(username)}]")
        monitor_thread.daemon = True
        self.user_driver_map[username]['monitor_thread'] = monitor_thread
        monitor_thread.start()
        self.logger.info(f"用户[{basic.mask_username(username)}]的浏览器监控线程已启动")

    def _cleanup_driver(self, username: str):
        """内部方法：清理单个用户的Driver资源（关闭Driver、终止进程、停止监控）"""
        driver_info = self.user_driver_map.get(username)
        if not driver_info:
            return

        # 标记为停止运行（防止监控线程继续执行）
        driver_info['is_running'] = False

        # 1. 关闭Driver
        driver = driver_info.get('driver')
        if driver:
            try:
                driver.quit()
                self.logger.info(f"用户[{basic.mask_username(username)}]的Driver已正常退出")
            except Exception:
                self.logger.warning(f"用户[{basic.mask_username(username)}]的Driver正常退出失败，尝试强制终止进程")

        # 2. 强制终止chromedriver进程
        driver_service = driver_info.get('driver_service')
        if driver_service and driver_service.process:
            try:
                driver_service.process.terminate()
                self.logger.info(f"用户[{basic.mask_username(username)}]的ChromeDriver进程已强制终止")
            except Exception:
                self.logger.warning(f"用户[{basic.mask_username(username)}]的ChromeDriver进程强制终止失败")

        # 3. 移除用户映射（最后操作，避免监控线程重复处理）
        self.user_driver_map.pop(username, None)
        self.logger.info(f"用户[{basic.mask_username(username)}]的Driver映射已移除，资源清理完成")

    def kill_residual_chromedriver(self):
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
