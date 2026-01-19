# 后台任务管理器（负责任务执行，通过信号与UI通信）
from concurrent.futures.thread import ThreadPoolExecutor
from typing import Dict, Any, Optional, Tuple, List

from PyQt5.QtCore import QObject, pyqtSignal

from src.frame.common.exceptions import BusinessException
from src.frame.dao.db_manager import db
from src.frame.task_batch_executor import TaskBatchExecutor


class TaskManager(QObject):
    # 定义信号（跨线程通信）
    log_signal = pyqtSignal(str)  # 日志信号
    user_task_finished_signal = pyqtSignal(str, bool)  # 单个用户任务完成信号
    all_task_finished_signal = pyqtSignal()  # 所有任务完成信号
    progress_update_signal = pyqtSignal(int)  # 进度更新信号
    # running_status_signal = pyqtSignal(bool)  # 任务运行状态信号。True-运行中，False-未运行

    def __init__(self, logger):
        super().__init__()
        self.running_status = False  # 任务运行状态，还有任务在运行时返回True，没有任务时返回False
        self.task_batches_configs = []  # 任务批次配置信息
        self.task_batches: Optional[Dict[str, Tuple[Dict, Dict]]] = {}  # 任务批次信息，key: 任务批次号（batch_no）；value：任务批次信息
        self.logger = logger  # 日志实例
        self.is_task_running = False  # 任务运行状态
        self.task_config: Optional[Dict[str, Any]] = None  # 任务模板配置
        self.future_list = []  # 任务执行结果列表
        self.db = db  # 数据库管理器
        self.task_batch_executor = ThreadPoolExecutor(max_workers=20)  # 任务批次线程池，最大并发数20
        self.task_executors: Dict[int, TaskBatchExecutor] = {}  # 任务动作信息
        #### 定义定时器，向外发送任务进度 ####
        # self.timer = QTimer()
        # self.timer.timeout.connect(self.update_progress)
        # self.timer.start(2000)

    def load_config(self, task_batches: List[Dict]) -> List[Tuple[Dict, Dict]]:
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
            batch_no = task_batch.get("batch_no")
            self.task_batches[batch_no] = task_batch, task_tmpl
            task_batch_configs.append((task_batch, task_tmpl))

        if not self.task_batches:
            raise BusinessException("没有待运行的任务批次！")

        try:
            task_batches_config = []
            # 按照任务值从小到大排序，值越小优先级越高，优先运行
            # task_tmpl_ids = sorted(self.task_tmpl_ids.keys(), key=lambda x: self.task_tmpl_ids[x])
            # task_tmpls = [self.db.task_tmpl_dao.get_by_id(task_tmpl_id) for task_tmpl_id in task_tmpl_ids]
            # 获取全局配置信息
            datas = self.db.data_dict_dao.get_all()
            global_config = {data.get("key"): data.get("value") for data in datas}

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
                # task_batches_config.append(task_config)
                task_batches_config.append((task_config, global_config))
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
        self.logger.debug(f"准备加载的任务批次配置配置：{task_batches}")
        # 1.加载配置
        task_batches_config = self.load_config(task_batches)
        # 2.启动任务
        executor = TaskBatchExecutor(task_batches_config, self.logger)
        # 一次提交的任务中，action_id相同
        self.task_executors[task_batches[0].get("action_id")] = executor
        executor.task_batch_finished_signal.connect(self.on_task_batch_finished)
        self.logger.debug(f"加载成功！任务批次配置：{task_batches_config}")
        executor.start()
        self.running_status = True

    def terminate_task(self, batch_no: str = "", task_uuid: str = "", reason="手动强制停止"):
        """
        终止任务
        :param batch_no: 批次号
        :param task_uuid: 任务ID
        :param reason: 终止原因
        :return:
        """
        for executor in self.task_executors.values():
            executor.terminate_task(batch_no, task_uuid, reason)

    def terminate_all(self):
        """
        终止所有任务
        :return:
        """
        for executor in self.task_executors.values():
            executor.terminate_all()

    def on_task_batch_finished(self, action_id: int):
        """
        任务批次完成
        :param action_id: 动作ID
        """
        # 移除任务批次
        self.task_executors.pop(action_id)
        if not self.task_executors:
            self.logger.debug("所有任务批次完成！")
            self.running_status = False
            # self.running_status_signal.emit(False)

    # def update_progress(self):
    #     self.running_status_signal.emit(self.running_status)

    def pause_task(self, batch_no: str = "", task_uuid: str = "", reason: str = ""):
        """
        暂停任务
        :param batch_no: 批次号
        :param task_uuid: 任务ID
        :param reason: 暂停原因
        :return:
        """
        for executor in self.task_executors.values():
            executor.pause_task(batch_no, task_uuid, reason)

    def resume_task(self, batch_no: str = "", task_uuid: str = "", reason: str = ""):
        """
        恢复任务
        :param batch_no: 批次号
        :param task_uuid: 任务ID
        :param reason: 恢复原因
        :return:
        """
        for executor in self.task_executors.values():
            executor.pause_task(batch_no, task_uuid, reason)