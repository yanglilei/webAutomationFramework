# 后台任务管理器（负责任务执行，通过信号与UI通信）
from typing import Dict, List

from PyQt5.QtCore import QObject, pyqtSignal

from src.frame.common.chrome_process_manager import chrome_process_manager
from src.frame.common.exceptions import BusinessException
from src.frame.dao.db_manager import db
from src.frame.task_batch_executor import TaskBatchExecutor


class TaskManager(QObject):
    # 定义信号（跨线程通信）
    log_signal = pyqtSignal(str)  # 日志信号
    user_task_finished_signal = pyqtSignal(str, bool)  # 单个用户任务完成信号
    all_task_finished_signal = pyqtSignal()  # 所有任务完成信号
    progress_update_signal = pyqtSignal(int)  # 进度更新信号

    def __init__(self, logger):
        super().__init__()
        self.is_running = False  # 任务运行状态，还有任务在运行时返回True，没有任务时返回False
        self.logger = logger  # 日志实例
        self.db = db  # 数据库管理器
        self.task_batch_executors: Dict[int, TaskBatchExecutor] = {}  # 任务动作信息，key：批次号，value：任务执行器

    def load_config(self, task_batches: List[Dict]) -> List[Dict]:
        """
        加载任务模板配置和用户列表
        :param : [(任务批次配置, 全局配置), (任务批次配置, 全局配置)]
        任务批次配置：dict,
        key：
        batch_no：批次号
        batch_info：批次信息。tb_task_batch表的内容
        task_tmpl：任务模板。相关的tb_task_tmpl表的内容
        task_nodes：任务节点。相关的tb_node表的内容
        task_tmpl_config：任务模板配置。相关的tb_task_tmpl_config表的内容

        示例：[({"batch_no": "xxx", "batch_info": {}, "task_tmpl": {}, "task_nodes": {}, "task_tmpl_config": {}}),(...)]
        """
        task_batch_configs = []  # {批次号: 任务模板信息}
        # 按照优先级排序，值越小优先级越高，优先运行
        sorted_task_batches = sorted(task_batches, key=lambda x: x["priority"])

        for task_batch in sorted_task_batches:
            # 校验
            if task_batch.get("execute_status") != 0:
                self.logger.error(f"任务批次状态异常，跳过任务！任务批次ID：{task_batch.get('id')}")
                continue
            task_tmpl_id = task_batch.get("task_tmpl_id")
            task_tmpl = db.task_tmpl_dao.get_by_id(task_tmpl_id)
            if not task_tmpl:
                self.logger.error(
                    f"未找到任务模板，跳过任务！任务批次ID：{task_batch.get('id')}，任务模板ID：{task_tmpl_id}")
                continue
            if task_tmpl.get("status") == 0:
                self.logger.error(
                    f"任务模板未启用，跳过任务！任务模板ID：{task_batch.get('task_tmpl_id')}，任务模板ID：{task_tmpl_id}")
                continue

            # 批次号
            # batch_no = task_batch.get("batch_no")
            task_batch_configs.append((task_batch, task_tmpl))

        if not task_batch_configs:
            raise BusinessException("没有待运行任务批次！")

        try:
            # 任务批次配置信息
            # 元素内容{"batch_no": "", "batch_info": {}, "task_tmpl": {}, "task_nodes": {}, "task_tmpl_config": {}}
            task_batches_config = []
            # 按照任务值从小到大排序，值越小优先级越高，优先运行
            # task_tmpl_ids = sorted(self.task_tmpl_ids.keys(), key=lambda x: self.task_tmpl_ids[x])
            # task_tmpls = [self.db.task_tmpl_dao.get_by_id(task_tmpl_id) for task_tmpl_id in task_tmpl_ids]
            # 获取全局配置信息
            # datas = self.db.data_dict_dao.get_all()
            # global_config = {data.get("key"): data.get("value") for data in datas}

            # 加载模板配置信息
            for task_batch, task_tmpl in task_batch_configs:
                # 加入任务模板信息
                task_config = {"batch_no": task_batch.get("batch_no"), "batch_info": task_batch, "task_tmpl": task_tmpl}
                # task_config.update(task_tmpl)
                # 获取节点信息
                task_tmpl_id = task_tmpl.get("id")
                nodes = self.db.node_dao.get_by_task_tmpl_id(task_tmpl_id)
                if not nodes:
                    self.logger.error(f"未找到节点，任务模板ID：{task_tmpl_id}，未配置节点！")
                    continue
                task_config["task_nodes"] = nodes
                # 获取任务模板配置信息
                config = self.db.task_tmpl_config_dao.get_by_task_tmpl_id(task_tmpl_id)
                task_config["task_tmpl_config"] = config
                # task_batches_config.append((task_config, global_config))
                task_batches_config.append(task_config)

            if not task_batches_config:
                raise BusinessException("配置有误，请检查任务模板是否配置了节点！")
            return task_batches_config
        except Exception as e:
            self.logger.error(f"加载配置失败：{str(e)}")
            raise e

    def start_task(self, task_batches: List[Dict]):
        """
        启动批量任务（无阻塞线程池调度）
        每次提交并行执行
        若一次提交中含多个批次，则每个批次顺序执行
        :param task_batches: 任务批次信息 看tb_task_batch表
        """
        self.is_running = True
        self.logger.debug(f"准备加载的任务批次配置配置：{task_batches}")
        # 1.加载配置
        task_batches_config = self.load_config(task_batches)
        # 2.启动任务线程
        executor = TaskBatchExecutor(task_batches_config, self.logger)
        # 一次提交的任务中，action_id相同
        self.task_batch_executors[task_batches[0].get("action_id")] = executor
        executor.one_task_batch_finished.connect(self.on_one_task_batch_finished)
        executor.all_task_batch_finished.connect(self.on_all_task_batch_finished)
        self.logger.debug(f"加载成功！任务批次配置：{task_batches_config}")
        executor.start()

    def free_resource(self, batch_nos: List[str]):
        """
        释放资源
        设计逻辑：
        直接取消协程任务！让线程退出，回调all_task_batch_finished方法，设置TaskManager的is_running=False
        外部的ResourceMonitor线程会死浏览器进程！
        :param batch_nos: 任务批次号
        :return:
        """
        #### 关闭协程 ####
        for task_batch_executor in self.task_batch_executors.values():
            # 说明批次已经运行了（运行中或者已结束)
            if batch_nos:
                for batch_no in batch_nos:
                    coroutine_scheduler = task_batch_executor.coroutine_schedulers.get(batch_no)
                    if coroutine_scheduler:
                        # 取消批次中所有的任务！采用协程的方式取消任务！
                        coroutine_scheduler.cancel()
                break
            else:  # 无指定批次为清除所有的资源
                for coroutine_scheduler in task_batch_executor.coroutine_schedulers.values():
                    coroutine_scheduler.cancel()

        #### 关闭浏览器 ####
        for batch_no in batch_nos:
            chrome_process_manager.clean_batch_processes(batch_no)

        # task_batches = db.task_batch_dao.get_by_batch_nos(batch_nos)
        # for task_batch in task_batches:
        #     task_tmpl = db.task_tmpl_dao.get_by_id(task_batch.get("task_tmpl_id"))
        #     if not task_tmpl.get("is_quit_browser_when_finished"):
        #         # 针对不能自动退出浏览器的任务，当手动点击释放资源时，需清理浏览器资源
        #         chrome_process_manager.clean_batch_processes(task_batch.get("batch_no"))
        return "释放资源成功！"

    def on_all_task_batch_finished(self, action_id: int, batch_nos: List[str], is_support_auto_free: bool):
        """
        所有批次完成
        :param action_id: 动作ID
        :param batch_nos: 批次号列表
        :param is_support_auto_free: 是否支持自动释放
        :return:
        """
        # 移除任务批次
        self.task_batch_executors.pop(action_id)
        if not self.task_batch_executors:
            self.logger.debug("所有任务批次完成！")
            # 不支持自动释放，则设置is_running=True，只能手动
            self.is_running = False

    def on_one_task_batch_finished(self, action_id: int, batch_no: str):
        """
        一个批次完成
        :param action_id: 动作ID
        :param batch_no: 批次号
        """
        pass

    def terminate_task(self, batch_no: str = "", task_uuid: str = "", reason="手动强制停止"):
        """
        终止任务
        :param batch_no: 批次号
        :param task_uuid: 任务ID
        :param reason: 终止原因
        :return:
        """
        for executor in self.task_batch_executors.values():
            executor.terminate_task(batch_no, task_uuid, reason)

    def terminate_all(self):
        """
        终止所有任务
        :return:
        """
        for executor in self.task_batch_executors.values():
            executor.terminate_all()

    # def update_progress(self):
    #     self.running_status_signal.emit(self.is_running)

    def pause_task(self, batch_no: str = "", task_uuid: str = "", reason: str = ""):
        """
        暂停任务
        :param batch_no: 批次号
        :param task_uuid: 任务ID
        :param reason: 暂停原因
        :return:
        """
        for executor in self.task_batch_executors.values():
            executor.pause_task(batch_no, task_uuid, reason)

    def resume_task(self, batch_no: str = "", task_uuid: str = "", reason: str = ""):
        """
        恢复任务
        :param batch_no: 批次号
        :param task_uuid: 任务ID
        :param reason: 恢复原因
        :return:
        """
        for executor in self.task_batch_executors.values():
            executor.pause_task(batch_no, task_uuid, reason)
