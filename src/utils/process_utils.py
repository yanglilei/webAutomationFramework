import logging

import psutil


class ProcessUtils:
    @classmethod
    def _get_app_child_processes(cls, parent_pid: int) -> list[psutil.Process]:
        """
        递归获取指定 PID 的所有子进程（子进程 + 孙进程 + 曾孙进程）
        :param parent_pid: PyQt 主进程 PID
        :return: 所有子进程列表
        """
        child_procs = []
        try:
            parent_proc = psutil.Process(parent_pid)
            # 获取直接子进程
            children = parent_proc.children(recursive=False)
            child_procs.extend(children)
            # 递归获取孙进程
            for child in children:
                child_procs.extend(cls._get_app_child_processes(child.pid))
        except psutil.NoSuchProcess:
            logging.warning(f"进程 {parent_pid} 不存在，停止递归")
        except Exception:
            logging.exception(f"获取进程 {parent_pid} 的子进程失败")
        return child_procs

    @classmethod
    def _get_app_chrome_processes(cls, app_pid: int) -> list[psutil.Process]:
        """
        精准获取当前 PyQt 应用启动的所有 Chrome 进程
        核心：只清理属于当前应用子进程树的 Chrome
        """
        # 1. 获取当前应用的所有子进程
        all_child_procs = cls._get_app_child_processes(app_pid)
        # 2. 筛选出 Chrome 进程
        chrome_procs = []
        for proc in all_child_procs:
            try:
                # proc_name = proc.name().lower()
                # if 'chrome.exe' in proc_name or 'chromedriver.exe' in proc_name:
                chrome_procs.append(proc)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return chrome_procs

    @classmethod
    def get_app_chrome_processes(cls, app_pid: int) -> set[int]:
        """
        精准获取当前 PyQt 应用启动的所有 Chrome 进程
        核心：只清理属于当前应用子进程树的 Chrome
        """
        return cls.get_processes_by_names(app_pid, ['chrome.exe', 'chromedriver.exe'])

    @classmethod
    def get_app_firefox_processes(cls, app_pid: int) -> set[int]:
        """
        精准获取当前 PyQt 应用启动的所有 Chrome 进程
        核心：只清理属于当前应用子进程树的 Chrome
        """
        return cls.get_processes_by_names(app_pid, ['firefox.exe'])

    @classmethod
    def get_processes_by_names(cls, app_pid: int, names: list[str]) -> set[int]:
        """
        精准获取当前 PyQt 应用启动的所有 Chrome 进程
        核心：只清理属于当前应用子进程树的 Chrome
        """
        # 1. 获取当前应用的所有子进程
        all_child_procs = cls._get_app_child_processes(app_pid)
        # 2. 筛选出 Chrome 进程
        chrome_procs = set()
        for proc in all_child_procs:
            try:
                proc_name = proc.name().lower()
                if any([proc_name in name for name in names]):
                    chrome_procs.add(proc.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return chrome_procs

    @classmethod
    def kill_residual_chrome(cls, app_pid):
        """重构：仅清理当前 PyQt 应用启动的 Chrome 进程（精准无误杀）"""
        logging.debug(f"开始清理 PyQt 应用（PID:{app_pid}）启动的 Chrome 残留进程")
        # 1. 获取当前应用的所有 Chrome 子进程
        chrome_procs = cls._get_app_chrome_processes(app_pid)
        if not chrome_procs:
            logging.debug("未检测到应用启动的 Chrome 残留进程")
            return

        # 2. 递归杀死每个 Chrome 进程的进程树
        for proc in chrome_procs:
            try:
                cls._kill_process_tree(proc.pid)
                logging.debug(f"清理应用内 Chrome 进程：PID={proc.pid}")
            except Exception as e:
                logging.warning(f"清理进程 {proc.pid} 失败：{e}")

        logging.debug(f"共清理 {len(chrome_procs)} 个应用内 Chrome 残留进程")

    @classmethod
    def _kill_process_tree(cls, pid: int):
        """递归杀死进程树（主进程 + 所有子进程）"""
        try:
            parent = psutil.Process(pid)
            # 获取所有子进程
            children = parent.children(recursive=True)
            # 先杀子进程
            for child in children:
                try:
                    child.kill()
                    logging.info(f"杀死Chrome子进程：PID={child.pid}")
                except:
                    pass
            # 再杀主进程
            try:
                parent.kill()
                logging.info(f"杀死Chrome主进程：PID={parent.pid}")
            except:
                pass
        except:
            logging.warning(f"无法杀死进程树：PID={pid}")
