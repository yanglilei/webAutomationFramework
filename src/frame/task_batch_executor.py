import json
from typing import Tuple, List, Any, Optional, Dict

import shortuuid
from PyQt5.QtCore import QThread, pyqtSignal

from src.frame.common.coroutine_scheduler import CoroutineScheduler
from src.frame.common.exceptions import ParamError
from src.frame.common.playwright_driver_manager import WebDriverManager
from src.frame.common.qt_log_redirector import qt_logger
from src.frame.common.user_manager import UserManager, UserInfoLocation
from src.frame.dao.db_manager import db
from src.frame.dto.driver_config import DriverConfigFormatter, DriverConfig
from src.frame.hot_reload_manager import NodeHotReloadManager
from src.frame.task import Task
from src.frame.task_scheduler import TaskScheduler
from src.utils import basic
from src.utils.async_utils import get_event_loop_safely


class TaskBatchExecutor(QThread):
    # 所有任务完成的信号
    one_task_batch_finished = pyqtSignal(int, str)
    all_task_batch_finished = pyqtSignal(int, list, set)

    def __init__(self, task_batches_config: List[dict], logger):
        super().__init__()
        # 获取所有的批次号
        self.logger = logger  # 日志
        self.batch_nos = [task_batch_config.get("batch_info").get("batch_no") for task_batch_config in
                          task_batches_config]
        self.task_batches_config: List[dict] = task_batches_config  # 任务批次配置
        self.action_id = task_batches_config[0].get("batch_info").get("action_id")  # 动作ID，每次执行唯一
        self.task_scheduler = TaskScheduler(logger)  # 任务调度器
        ###
        ### 热加载器依然作为单例存在，热加载器中注册任务调度器，用于热加载！
        ### 任务调度器废除单例模式！一个线程一个任务调度器，避免跨线程的协程共用！
        ###
        self.hot_reload_manager = NodeHotReloadManager(logger)
        self.db = db  # 数据库管理器
        self.future_list = []  # 任务执行结果列表
        self.total_task_count = 0  # 任务总数
        #### 预留未实现 ####
        # self.completed_task_count = 0  # 已完成任务数
        # self.success_task_count = 0  # 成功任务数
        # self.fail_task_count = 0  # 失败任务数
        self.coroutine_schedulers: Dict[str, CoroutineScheduler] = {}  # 协程调度器列表，批次号->协程调度器
        self.web_driver_manager_holder: Dict[str, WebDriverManager] = {}  # web驱动管理器。批次号->web驱动管理器
        self.has_unreleased_resource_holder: Dict[str, bool] = {}  # 用于记录每个批次中是否还有未释放的资源。批次号->bool

    def _reset(self):
        self.future_list = []  # 任务执行结果列表
        self.total_task_count = 0  # 任务总数
        # self.completed_task_count = 0  # 已完成任务数
        # self.success_task_count = 0  # 成功任务数
        # self.fail_task_count = 0  # 失败任务数

    def run(self):
        # 思路：一次提交多个批次，则顺序执行
        try:
            for task_batch_config in self.task_batches_config:
                # 重置数据
                self._reset()
                web_driver_manager = WebDriverManager(self.logger)
                batch_no = task_batch_config.get("batch_info").get("batch_no")
                self.has_unreleased_resource_holder[batch_no] = False
                self.web_driver_manager_holder[batch_no] = web_driver_manager
                try:
                    # 支持多个任务顺序执行
                    if task_batch_config.get("batch_info").get("user_mode") in (1, 2):
                        # 单用户或多用户任务
                        self.run_multi_user_mode(task_batch_config)
                    else:
                        # 无用户任务
                        self.run_no_user_mode(task_batch_config)
                finally:
                    if not self.has_unreleased_resource_holder.get(batch_no):
                        # 没有未释放的资源，则关闭驱动（playwright实例1个，browser实例1个，context实例n个）
                        get_event_loop_safely().run_until_complete(web_driver_manager.close())
                        # 已经释放了资源，则移除掉
                        self.has_unreleased_resource_holder.pop(batch_no)
                        # 移除web驱动管理器
                        self.web_driver_manager_holder.pop(batch_no)
        finally:
            self.all_task_batch_finished.emit(self.action_id, self.batch_nos,
                                              set(self.has_unreleased_resource_holder.keys()))

    def run_multi_user_mode(self, task_batch_config: Dict[str, Any]):
        """
        运行多用户模式（用户任务）
        :param task_batch_config: 任务批次配置
        :return:
        """
        batch_info = task_batch_config.get("batch_info")  # 批次信息
        batch_no = batch_info.get("batch_no")  # 批次号
        self.logger.debug(f"任务批次号【{batch_no}】 | 启动任务")
        try:
            unfinished_users, user_manager = self._format_user_info(batch_info.get("user_mode"),
                                                                    batch_info.get("user_info", {}))
            if not unfinished_users:
                self.logger.info(f"任务批次：{batch_no} | 无待处理用户，任务退出！")
                return

            ok_users = []
            for unfinished_user in unfinished_users:
                if not unfinished_user or len(unfinished_user) < 1:
                    self.logger.warning(f"任务批次：{batch_no} | 存在用户信息格式错误，请检查：{unfinished_user}")
                    continue
                ok_users.append(unfinished_user)

            # 待处理用户数
            self.total_task_count = len(unfinished_users)
            # 更新批次信息
            self.db.task_batch_dao.update_by_batch_no(batch_no,
                                                      {"total_user": self.total_task_count, "execute_status": 1})
            self.logger.info(
                f"启动批量任务 | 任务批次：{batch_no} | 待处理用户数：{self.total_task_count} | 最大并发数：{self.total_task_count}")
            coro_funcs = []
            for user in ok_users:
                coro_funcs.append(
                    (self.execute_single_user_task, (user_manager, user, task_batch_config, self.logger), {}))
            # 执行协程
            get_event_loop_safely().run_until_complete(
                self._execute_one_task_batch(coro_funcs, task_batch_config))
        except Exception as e:
            self.logger.error(f"任务批次号：{batch_no} | 启动任务失败：{str(e)}")
            self.db.task_batch_dao.update_by_batch_no(batch_no, {"execute_status": 2, "remark": str(e)})

    async def _execute_one_task_batch(self, coro_funcs, task_batch_config):
        """执行一个批次任务"""
        # 创建一个协程调度器
        batch_info = task_batch_config.get("batch_info")
        batch_no = batch_info.get("batch_no")
        login_interval = self.get_login_interval(task_batch_config)
        scheduler = CoroutineScheduler(batch_no)
        self.coroutine_schedulers[batch_no] = scheduler
        # 当所有任务完成后该方法才会返回
        await scheduler.add_tasks_with_interval(coro_funcs=coro_funcs, interval=login_interval,
                                                callback=lambda task_id, status, result,
                                                                exec, args, kwargs: self.on_one_task_finished(
                                                    task_id, status, result, exec, task_batch_config,
                                                    batch_info.get("global_config", {}), *args, **kwargs),
                                                )
        self.logger.info(f"任务批次号：{batch_no} | 所有任务执行完毕！")
        # 一个批次中所有的任务都完成了，更新批次状态
        self.db.task_batch_dao.update_status(batch_no, 2)
        self.one_task_batch_finished.emit(self.action_id, batch_no)

    def on_one_task_finished(self, task_id: str, status: str, result: Any, exc: Optional[Exception],
                             task_batch_config: dict, global_config: dict, *args, **kwargs):
        # 一个批次中单个任务的回调，若是页面上操作释放资源，则协程会被取消，会回调该方法！
        batch_no = task_batch_config.get("batch_info").get("batch_no")
        if status == "completed":
            if not isinstance(result, tuple) or len(result) != 2:
                self.logger.error(f"任务批次号：{batch_no} | 任务执行结果格式错误无法解析：{result}")
                return

            username, is_success = result
            try:
                if is_success:
                    self.logger.info(f"任务批次号：{batch_no} | 用户任务执行完成，状态：成功")
                    self.db.task_batch_dao.add_one_success_user(batch_no)
                else:
                    self.logger.info(f"任务批次号：{batch_no} | 用户任务执行完成，状态：失败")
                    self.db.task_batch_dao.add_one_fail_user(batch_no)
            except Exception as e:
                self.logger.error(f"处理任务回调异常：{str(e)}")
            finally:
                # 任务执行完毕，关闭当前用户的浏览器
                if task_batch_config.get("task_tmpl").get("is_quit_browser_when_finished", True):
                    self.logger.debug(f"关闭专属Context")
                    get_event_loop_safely().run_until_complete(
                        self.web_driver_manager_holder.get(batch_no).remove_user_driver(batch_no, username))
                else:
                    self.logger.info(f"任务执行完毕，不关闭当前用户的浏览器，请用户手动关闭！")
                    self.has_unreleased_resource_holder[batch_no] = True  # 不能自动释放，需要手动释放
        elif status == "cancelled":
            # 任务被取消，往往是因为用户操作取消了，比如：用户操作点击了“释放资源”的按钮！目前的逻辑是：直接释放资源（关闭驱动）！
            username = args[1][0]
            get_event_loop_safely().run_until_complete(
                self.web_driver_manager_holder.get(batch_no).remove_user_driver(batch_no, username))
            self.logger.info(f"任务批次号：{batch_no} | 用户任务执行完成，状态：取消")
            self.db.task_batch_dao.add_one_fail_user(batch_no)
        else:  # 异常
            self.logger.debug(f"任务批次号：{batch_no} | 用户任务执行完成，状态：异常", exec_info=exc)
            self.logger.info(f"任务批次号：{batch_no} | 用户任务执行完成，状态：异常，原因：{str(exc)}")
            self.db.task_batch_dao.add_one_fail_user(batch_no)

    def run_no_user_mode(self, task_batch_config):
        """
        无用户模式（无用户任务）
        必定是逐个执行的！
        :param task_batch_config: 任务批次配置
        """
        try:
            batch_info = task_batch_config.get("batch_info")  # 批次信息
            # global_config = batch_info.get("global_config")  # 全局配置
            batch_no = batch_info.get("batch_no")  # 批次号
            self.logger.debug(f"任务批次号【{batch_no}】 | 启动任务")
            coro_funcs = [(self.execute_no_user_task, (task_batch_config, self.logger), {})]
            get_event_loop_safely().run_until_complete(
                self._execute_one_task_batch(coro_funcs, task_batch_config))
        except Exception as e:
            self.logger.error(f"任务执行失败：{str(e)}")

    def get_login_interval(self, task_batch_config):
        # 获取登录间隔
        global_login_interval = int(
            task_batch_config.get("batch_info", {}).get("global_config", {}).get("default_login_interval", 8))
        task_login_interval = int(task_batch_config.get("task_tmpl", {}).get("login_interval", 0))
        return task_login_interval if task_login_interval is not None and task_login_interval > 0 else global_login_interval

    async def execute_single_user_task(self, user_manager,
                                       user_config: Tuple[str, str],
                                       task_batch_config: dict,
                                       logger):
        """执行单个用户任务（Driver外部创建+重登后从头执行）"""
        task_success = False
        task = None
        if not isinstance(user_config, Tuple) or len(user_config) < 2:
            self.logger.error(f"用户配置：user_config格式错误，必须为元组至少含2个元素，例：(用户名, 密码, )")
            return "", False
        username = user_config[0]
        batch_no = task_batch_config.get("batch_info", {}).get("batch_no")
        global_config = task_batch_config.get("batch_info", {}).get("global_config")
        try:
            # 设置日志显示的用户名
            qt_logger.set_current_user(basic.mask_username(username))
            # 创建浏览器驱动
            driver = await self._create_driver(username, batch_no, DriverConfigFormatter.format(global_config))
            # 创建任务
            task = Task(driver, user_config, task_batch_config, logger, user_manager)
            # 提交任务
            self.task_scheduler.submit_task(task)
            # 注册任务到热加载器中，热加载器负责回调任务调度器的热加载方法！pause by zcy! 20260127!
            self._register_hot_reload(task)
            # 启动任务
            task_success = await self.task_scheduler.start_task(task.task_uuid)
        except Exception as e:
            logger.exception(f"任务执行异常：")
        finally:
            # 移除任务
            self.task_scheduler.remove_task(task)
            # TODO 此处需结合UI测试能否在线程中发送信号
            # 发送进度更新信号
            # self.progress_update_signal.emit(int((self.completed_task_count / self.total_task_count) * 100))
            # # 发送任务完成信号
            # self.user_task_finished_signal.emit(username, task_success)
        return username, task_success

    def _register_hot_reload(self, task: Task):
        for node in task.nodes.values():
            node_cfg = node.node_config
            if node_cfg.get("node_params", {}).get("is_support_hot_reload"):
                # 添加到热加载节点列表
                # 在create_node_instance方法中component_path被修改了，所以这里需要重新获取
                component_path = node_cfg.get("component_path")
                # 需要热加载的组件，添加到看门狗.
                self.hot_reload_manager.watch_node_file(
                    node_identifier=node_cfg.get("node_id"),
                    node_file_path=component_path,
                    reload_callback=self._task_reload_callback
                )

    def _task_reload_callback(self, component_path: str):
        """文件变更回调：中断旧任务+重启新任务"""
        self.logger.info(f"开始执行热更新，组件路径：{component_path}")
        for task in self.task_scheduler.tasks.values():
            task.hot_reload(component_path)
        self.logger.info(f"结束热更新，组件路径：{component_path}")

    async def execute_no_user_task(self, task_batch_config: dict, logger):
        """执行单个用户任务（Driver外部创建+重登后从头执行）"""
        username = f"NO_USER_{shortuuid.ShortUUID().random(length=7)}"
        qt_logger.set_current_user(basic.mask_username(username))
        # 初始化变量
        task_success = False
        task = None
        try:
            batch_info = task_batch_config.get("batch_info", {})
            driver = await self._create_driver(username, batch_info.get("batch_no"),
                                               DriverConfigFormatter.format(batch_info.get("global_config")))
            task = Task(driver, (username, ''), task_batch_config, logger)
            self.task_scheduler.submit_task(task)
            task_success = await self.task_scheduler.start_task(task.task_uuid)
        except Exception as e:
            logger.exception(f"任务执行异常：")
        finally:
            # 移除任务
            self.task_scheduler.remove_task(task.task_uuid)
            # 更新任务进度
            # self.completed_task_count += 1
            # TODO 此处需结合UI测试能否在线程中发送信号
            # 发送进度更新信号，无用户模式只能逐个用户完成任务，所以任务进度为100%
            # self.progress_update_signal.emit(100)
            # # 发送任务完成信号
            # self.user_task_finished_signal.emit(username, task_success)
        return username, task_success

    async def _create_driver(self, username, batch_no, driver_config: DriverConfig):
        # 设置日志显示的用户名
        qt_logger.set_current_user(basic.mask_username(username))
        # 步骤1：注册批次
        if driver_config.browser_type == "0":
            # chrome
            from src.frame.common.browser_process_manager import chrome_process_manager as process_manager
        elif driver_config.browser_type == "1":
            # firefox
            from src.frame.common.browser_process_manager import firefox_process_manager as process_manager
        else:
            raise ParamError(f"不支持的浏览器类型：{driver_config.browser_type}")

        process_manager.register_batch(batch_no)
        # 步骤2：创建进程捕获器（记录操作前的Chrome进程池）
        capture_func = process_manager.capture_new_browser_processes(batch_no)
        # 步骤3：创建用户浏览器
        driver = await self.web_driver_manager_holder.get(batch_no).create_user_driver(username, batch_no,
                                                                                       driver_config)
        # 步骤4：执行捕获，获取新增的Chrome进程组
        capture_func()
        return driver

    def _format_user_info(self, user_mode, user_info):
        # 返回数据：([(用户名, 密码)], Optional[UserManager])
        # 用户信息。保存在excel中，或者保存在文本中
        if isinstance(user_info, str):
            user_info = json.loads(user_info)
        unfinished_users = []
        user_manager = None
        if user_mode == 1:
            user_manager = UserManager(UserInfoLocation(**user_info))
            unfinished_users = user_manager.get_users()
        elif user_mode == 2:
            # 文本模式下user_info的格式：[{"username": "xxx", "password": "xxx"}]
            for info in user_info:
                unfinished_users.append((info.get("username", ""), info.get("password", "")))
        elif user_mode == 0:
            pass
        # 过滤掉重复值
        unfinished_users = list(dict.fromkeys(unfinished_users))
        return unfinished_users, user_manager

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
