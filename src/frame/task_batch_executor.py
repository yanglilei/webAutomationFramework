import json
import time
import uuid
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Tuple, List

from PyQt5.QtCore import QThread, pyqtSignal

from src.frame.common.driver_manager import WebDriverManager
from src.frame.common.qt_log_redirector import qt_logger
from src.frame.common.user_manager import UserManager, UserInfoLocation
from src.frame.dao.db_manager import db
from src.frame.dto.driver_config import DriverConfigFormatter
from src.frame.task import Task
from src.frame.task_scheduler import TaskScheduler
from src.utils import basic


class TaskBatchExecutor(QThread):
    # 所有任务完成的信号
    task_batch_finished_signal = pyqtSignal(int)

    def __init__(self, task_batches_config: List[Tuple[dict, dict]], logger):
        super().__init__()
        self.logger = logger  # 日志
        self.task_batches_config: List[Tuple[dict, dict]] = task_batches_config  # 任务批次配置
        self.action_id = task_batches_config[0][0].get("batch_info").get("action_id")  # 动作ID，每次执行唯一
        self.task_scheduler = TaskScheduler(logger)  # 任务调度器
        self.db = db  # 数据库管理器
        self.driver_manager = WebDriverManager()  # 用户-Driver管理器
        self.future_list = []  # 任务执行结果列表
        self.total_task_count = 0  # 任务总数
        self.completed_task_count = 0  # 已完成任务数
        self.success_task_count = 0  # 成功任务数
        self.fail_task_count = 0  # 失败任务数
        self.is_task_running = False  # 任务是否正在执行

    def _reset(self):
        self.future_list = []  # 任务执行结果列表
        self.total_task_count = 0  # 任务总数
        self.completed_task_count = 0  # 已完成任务数
        self.success_task_count = 0  # 成功任务数
        self.fail_task_count = 0  # 失败任务数
        self.is_task_running = False  # 任务是否正在执行

    def run(self):
        for task_batch_config, global_config in self.task_batches_config:
            # 重置数据
            self._reset()
            # 支持多个任务顺序执行
            if task_batch_config.get("batch_info").get("user_mode") in (1, 2):
                # 单用户或多用户任务
                self.run_multi_user_mode(task_batch_config, global_config)
            else:
                # 无用户任务
                self.run_no_user_mode(task_batch_config, global_config)

    def run_multi_user_mode(self, task_batch_config, global_config):
        """
        运行多用户模式（用户任务）
        :param task_batch_config: 任务批次配置
        :param global_config: 全局配置
        :return:
        """
        self.is_task_running = True
        batch_info = task_batch_config.get("batch_info")  # 批次信息
        batch_no = batch_info.get("batch_no")  # 批次号
        self.logger.debug(f"任务批次号【{batch_no}】 | 启动任务")
        try:
            # 用户信息。保存在excel中，或者保存在文本中
            user_info = batch_info.get("user_info", {})
            if isinstance(user_info, str):
                user_info = json.loads(user_info)
            unfinished_users = []
            user_mode = batch_info.get("user_mode")
            if user_mode == 1:
                user_manager = UserManager(UserInfoLocation(**user_info))
                unfinished_users = user_manager.get_users()
            elif user_mode == 2:
                user_manager = None
                # 文本模式下user_info的格式：[{"username": "xxx", "password": "xxx"}]
                for info in user_info:
                    unfinished_users.append((info.get("username"), info.get("password")))
            elif user_mode == 0:
                pass
            # 过滤掉重复值
            unfinished_users = list(dict.fromkeys(unfinished_users))
            if not unfinished_users:
                self.logger.info(f"任务批次：{batch_no} | 无待处理用户，任务退出！")
                return

            # 待处理用户数
            self.total_task_count = len(unfinished_users)
            # 更新批次信息
            self.db.task_batch_dao.update_by_batch_no(batch_no,
                                                      {"total_user": self.total_task_count, "execute_status": 1})
            self.logger.info(
                f"启动批量任务 | 任务批次：{batch_no} | 待处理用户数：{self.total_task_count} | 最大并发数：{self.total_task_count}")
            # 2. 初始化线程池（无界队列）
            with ThreadPoolExecutor(max_workers=self.total_task_count) as executor:
                # 提交所有用户任务（无阻塞，超出并发数自动排队）
                login_interval = self.get_login_interval(task_batch_config, global_config)
                for user_config in unfinished_users:
                    future = executor.submit(self.execute_single_user_task, user_manager, user_config,
                                             task_batch_config, global_config, self.logger)
                    self.future_list.append(future)
                    future.add_done_callback(lambda f: self.task_done_callback(f, (task_batch_config, global_config)))
                    # 登录间隔
                    time.sleep(login_interval)
        except Exception as e:
            self.logger.error(f"任务批次号：{batch_no} | 启动任务失败：{str(e)}")
            self.db.task_batch_dao.update_by_batch_no(batch_no, {"execute_status": 2, "remark": str(e)})
        finally:
            self.is_task_running = False

    def run_no_user_mode(self, task_batch_config, global_config):
        """
        无用户模式（无用户任务）
        必定是逐个执行的！
        """
        try:
            self.is_task_running = True
            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(self.execute_no_user_task, task_batch_config, global_config, self.logger)
                self.future_list.append(future)
                future.add_done_callback(lambda f: self.task_done_callback(f, (task_batch_config, global_config)))
        except Exception as e:
            self.logger.error(f"任务执行失败：{str(e)}")
        finally:
            self.is_task_running = False

    def get_login_interval(self, task_batch_config, global_config):
        # 获取登录间隔
        global_login_interval = global_config.get("default_login_interval", 8)
        task_login_interval = task_batch_config.get("task_tmpl").get("login_interval", 0)
        return task_login_interval if task_login_interval is not None and task_login_interval > 0 else global_login_interval

    def execute_single_user_task(self, user_manager, user_config: Tuple, task_batch_config: dict, global_config: dict,
                                 logger):
        """执行单个用户任务（Driver外部创建+重登后从头执行）"""
        if not isinstance(user_config, Tuple) or len(user_config) < 2:
            raise Exception("用户配置：user_config格式错误，必须为元组至少含2个元素，例：(用户名, 密码, )")
        username = user_config[0]
        qt_logger.set_current_user(basic.mask_username(username))
        logger.info(f"===== 启动用户任务 =====")

        # 初始化变量
        task_success = False
        driver = None
        task = None
        try:
            # 1. 登录节点外：创建用户专属Driver（与用户名绑定）
            driver = self.driver_manager.create_user_driver(username, DriverConfigFormatter.format(global_config))
            if not driver:
                raise Exception("用户专属Driver创建失败，终止任务")
            logger.info(f"已创建专属Driver，开始执行任务流程")
            task = Task(driver, user_manager, global_config, user_config, task_batch_config, logger)
            self.task_scheduler.submit_task(task)
            task_success = self.task_scheduler.start_task(task.task_uuid)
            # 创建任务调度器
            return username, task_success
        except Exception as e:
            logger.exception(f"任务执行异常：")
        finally:
            if task:
                # 移除任务
                self.task_scheduler.remove_task(task.task_uuid)
            # 关闭用户专属Driver，移除映射
            if driver and task_batch_config.get("task_tmpl").get("is_quit_browser_when_finished", True):
                logger.info(f"关闭专属Driver")
                self.driver_manager.remove_user_driver(username)
            # 更新任务进度
            self.completed_task_count += 1

            # TODO 此处需结合UI测试能否在线程中发送信号
            # 发送进度更新信号
            # self.progress_update_signal.emit(int((self.completed_task_count / self.total_task_count) * 100))
            # # 发送任务完成信号
            # self.user_task_finished_signal.emit(username, task_success)
            logger.info(f"===== 用户任务执行完成，整体状态：{'成功' if task_success else '失败'} =====")

    def execute_no_user_task(self, task_batch_config: dict, global_config: dict, logger):
        """执行单个用户任务（Driver外部创建+重登后从头执行）"""
        username = f"NO_USER_{str(uuid.uuid4())}"
        qt_logger.set_current_user(basic.mask_username(username))
        logger.info(f"===== 启动用户任务 =====")

        # 初始化变量
        task_success = False
        driver = None
        task = None
        try:
            # 1. 登录节点外：创建用户专属Driver（与用户名绑定）
            driver = self.driver_manager.create_user_driver(username, DriverConfigFormatter.format(global_config))
            if not driver:
                raise Exception("用户专属Driver创建失败，终止任务")
            logger.info(f"已创建专属Driver，开始执行任务流程")
            task = Task(driver, None, global_config, {}, task_batch_config, logger)
            self.task_scheduler.submit_task(task)
            task_success = self.task_scheduler.start_task(task.task_uuid)
            # 创建任务调度器
            return username, task_success
        except Exception as e:
            logger.exception(f"任务执行异常：")
        finally:
            if task:
                # 移除任务
                self.task_scheduler.remove_task(task.task_uuid)

            # 关闭用户专属Driver，移除映射
            if driver and task_batch_config.get("task_tmpl").get("is_quit_browser_when_finished", True):
                logger.info(f"关闭专属Driver")
                self.driver_manager.remove_user_driver(username)

            # TODO 此处需结合UI测试能否在线程中发送信号
            # 发送进度更新信号，无用户模式只能逐个用户完成任务，所以任务进度为100%
            # self.progress_update_signal.emit(100)
            # # 发送任务完成信号
            # self.user_task_finished_signal.emit(username, task_success)
            logger.info(f"===== 用户任务执行完成，整体状态：{'成功' if task_success else '失败'} =====")

    # 4. 监听任务完成（不阻塞UI线程）
    def task_done_callback(self, future, extra_arg):
        task_batch_config, _ = extra_arg
        batch_no = task_batch_config.get("batch_info").get("batch_no")
        try:
            username, is_success = future.result()  # 捕获任务异常
            if task_batch_config.get("task_tmpl").get("start_mode") == 1:
                # 有用户模式，更新任务批次信息
                if is_success:
                    self.logger.info(f"任务批次号：{batch_no} | 用户任务执行完成，用户：{username}，状态：成功")
                    self.success_task_count += 1
                    self.db.task_batch_dao.update_by_batch_no(batch_no, {"success_user": self.success_task_count})
                else:
                    self.logger.info(f"任务批次号：{batch_no} | 用户任务执行完成，用户：{username}，状态：失败")
                    self.fail_task_count += 1
                    self.db.task_batch_dao.update_by_batch_no(batch_no, {"fail_user": self.fail_task_count})
        except Exception as e:
            self.logger.exception(f"任务回调，执行异常：{str(e)}")
        finally:
            # 所有任务完成后触发信号
            if all([f.done() for f in self.future_list]) and self.task_batches_config.index(extra_arg) == len(
                    self.task_batches_config) - 1:
                self.logger.info(f"任务批次号：{batch_no} | 所有任务执行完毕！")
                # 一个批次中所有的任务都完成了，更新批次状态
                self.db.task_batch_dao.update_status(batch_no, 2)
                self.task_batch_finished_signal.emit(self.action_id)

    def terminate_task(self, batch_no: str = "", task_uuid: str = "", reason="手动强制停止"):
        """
        终止任务
        :param batch_no: 批次号
        :param task_uuid: 任务ID
        :param reason: 终止原因
        :return:
        """
        self.task_scheduler.terminate_task(batch_no, task_uuid, reason)

    def terminate_all(self):
        """
        终止所有任务
        :return:
        """
        self.task_scheduler.terminate_task()

    def pause_task(self, batch_no: str = "", task_uuid: str = "", reason=""):
        """
        暂停任务
        :param batch_no: 批次号
        :param task_uuid: 任务ID
        :param reason: 暂停原因
        :return:
        """
        self.task_scheduler.pause_task(batch_no, task_uuid, reason)

    def resume_task(self, batch_no: str = "", task_uuid: str = "", reason=""):
        """
        恢复任务
        :param batch_no: 批次号
        :param task_uuid: 任务ID
        :param reason: 恢复原因
        :return:
        """
        self.task_scheduler.resume_task(batch_no, task_uuid, reason)