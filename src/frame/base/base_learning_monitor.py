import threading
import time
from queue import Empty, Queue
from typing import List

import psutil

from src.frame.base.base_learning_task import BaseLearningTask
from src.frame.common.config_file_reader import ConfigFileReader
from src.frame.common.constants import Constants, QueueMsg, MsgCmd
from src.frame.common.qt_log_redirector import LOG


class Worker:
    def __init__(self, task_list: List[BaseLearningTask], queue: Queue, id: int):
        self.task_list: List = task_list
        self.queue: Queue = queue
        self.id: int = id


class LearningTaskMonitor:
    """
    学习任务监控
    多线程监听，线程数量由配置文件中的default_processor_count决定
    """
    _lock = threading.Lock()
    _instance = None

    def __new__(cls, *args, **kwargs):
        with cls._lock:  # 加锁，确保同一时间只有一个线程执行
            if cls._instance is None:
                cls._instance = super().__new__(cls, *args, **kwargs)
        return cls._instance

    def __init__(self, *args, **kwargs):
        # 任务数量
        self.task_count = 0
        self.worker_list: List[Worker] = list()
        self.work_threads: List[threading.Thread] = list()
        # 工作线程数量
        thread_count = ConfigFileReader.get_val(Constants.ConfigFileKey.DEFAULT_PROCESSOR_COUNT,
                                                ConfigFileReader.base_section_name)
        # 最大限制在(逻辑cpu核/2)内
        thread_count = min(int(1 if not thread_count else thread_count), psutil.cpu_count(logical=True) // 2)
        for index in range(thread_count):
            self.worker_list.append(Worker(list(), Queue(), index))

    # def detect_best_thread_num(self):
    #     """
    #     检测电脑性能，推荐最优线程数（即 WebDriver 实例数）
    #     :return: 最优线程数
    #     """
    #     # 获取 CPU 逻辑核心数
    #     cpu_core = psutil.cpu_count(logical=True)
    #     # 获取可用内存（转换为 MB）
    #     available_mem = psutil.virtual_memory().available // (1024 * 1024)
    #
    #     # 基于资源计算最大支持线程数
    #     max_thread_by_cpu = int(cpu_core // SINGLE_CHROME_CPU_CORE)
    #     max_thread_by_mem = int(available_mem // SINGLE_CHROME_MEM_USED)
    #
    #     # 最优线程数取两者最小值，且不小于1、不大于8（避免过高并发）
    #     best_thread_num = min(max_thread_by_cpu, max_thread_by_mem)
    #     best_thread_num = max(best_thread_num, 1)
    #     best_thread_num = min(best_thread_num, 8)
    #
    #     with print_lock:
    #         print(f"===== 性能检测结果 =====")
    #         print(f"CPU 逻辑核心数: {cpu_core}")
    #         print(f"可用内存: {available_mem} MB")
    #         print(f"基于CPU计算最大线程数: {max_thread_by_cpu}")
    #         print(f"基于内存计算最大线程数: {max_thread_by_mem}")
    #         print(f"✅ 推荐最优线程数: {best_thread_num}")
    #         print(f"=======================\n")
    #
    #     return best_thread_num

    @staticmethod
    def work(work_param: Worker):
        while True:
            try:
                msg: QueueMsg = work_param.queue.get(block=False)
            except Empty:
                pass
            else:
                if msg.get_msg_cmd().value == MsgCmd.WORK_THREAD_EXIT.value:
                    # 获取到退出指令
                    break

            if len(work_param.task_list) > 0:
                for task in work_param.task_list:
                    # 遍历任务
                    try:
                        task.run()
                    except:
                        LOG.error("用户【%s】学习过程发生异常，退出学习" % task.username, exc_info=True)
                        work_param.task_list.remove(task)

                    time.sleep(1)

            time.sleep(1)

    def is_empty(self):
        ret = True
        for worker in self.worker_list:
            if len(worker.task_list) != 0:
                ret = False
                break
        return ret

    def add_task(self, task: BaseLearningTask):
        with self._lock:
            is_new_task = True
            worker = self.worker_list[self.task_count % len(self.worker_list)]
            # 保证同一个用户在固定一个线程下执行
            for item in self.worker_list:
                for tl in item.task_list:
                    if task.username == tl.username:
                        worker = item
                        is_new_task = False
                        break
            worker.task_list.append(task)
            # 新的任务
            if is_new_task:
                self.task_count += 1

    def remove_task(self, task):
        for worker in self.worker_list:
            if task in worker.task_list:
                worker.task_list.remove(task)
                break

    def is_in(self, task):
        ret = False
        for worker in self.worker_list:
            if task in worker.task_list:
                ret = True
                break
        return ret

    def run(self) -> None:
        for worker in self.worker_list:
            work_thread = threading.Thread(target=LearningTaskMonitor.work, args=(worker,),
                                           name="任务轮训线程%d" % self.worker_list.index(worker))
            self.work_threads.append(work_thread)
            work_thread.start()

    def wait_for_exit(self):
        while not self.is_empty():
            # 还有任务在运行，则不退出，每隔2秒扫描一次
            time.sleep(2)
        else:
            for worker in self.worker_list:
                worker.queue.put(QueueMsg(MsgCmd.WORK_THREAD_EXIT))
            for wt in self.work_threads:
                wt.join()

    def notify_all_works_exit(self):
        for worker in self.worker_list:
            worker.queue.put(QueueMsg(MsgCmd.WORK_THREAD_EXIT))
        for wt in self.work_threads:
            wt.join()

# if __name__ == '__main__':
#     print(psutil.cpu_count(logical=True))
