import os
import os.path
from typing import List

import psutil

from src.frame.common.qt_log_redirector import LOG


def sys_runtime():
    pids = psutil.pids()
    for pid in pids:
        process = psutil.Process(pid)
        print("进程名称：%s，进程ID：%d，父进程ID：%d" % (process.name(), process.pid, process.ppid()))


def get_child_processes(parent_pid, child_processes: List[psutil.Process]):
    for process in psutil.process_iter():
        if process.ppid() == parent_pid:
            # print("进程名称：%s，进程ID：%d，父进程ID：%d" % (process.name(), process.pid, process.ppid()))
            child_processes.append(process)
            get_child_processes(process.pid, child_processes)

def get_processes_by_name(process_name):
    ret = list()
    process_iter = psutil.process_iter()
    for process in process_iter:
        if process.name() == process_name:
            ret.append(process)
    return


def release2():
    LOG.info("退出前释放资源")
    cur_pid = os.getpid()
    child_processes: List[psutil.Process] = list()
    get_child_processes(cur_pid, child_processes)
    if len(child_processes) > 0:
        for child_process in child_processes:
            if psutil.pid_exists(child_process.pid):
                LOG.info("杀死子进程：%s，进程ID：%d，父进程ID：%d" % (
                    child_process.name(), child_process.pid, child_process.ppid()))
                child_process.kill()


def release():
    LOG.info("退出前释放资源")
    cur_pid = os.getpid()
    if os.name == "nt":
        cmd = "taskkill /f /t /pid %s" % cur_pid
        # LOG.info("执行命令：%s杀死所有相关进程" % cmd)
        os.system(cmd)
    elif os.name == "posix":
        child_processes: List[psutil.Process] = list()
        get_child_processes(cur_pid, child_processes)
        if len(child_processes) > 0:
            for child_process in child_processes:
                if psutil.pid_exists(child_process.pid):
                    LOG.info("杀死子进程：%s，进程ID：%d，父进程ID：%d" % (
                        child_process.name(), child_process.pid, child_process.ppid()))
                    cmd = "kill -9 %s" % child_process.pid
                    os.system(cmd)
