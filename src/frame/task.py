import os
import threading
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import shortuuid

from src.frame.base.base_task_node import BaseNode, JSNode, BasePYNode
from src.frame.common.constants import NodeState
from src.frame.common.playwright_driver_manager import WebDriverManager
from src.frame.component_manager import GeneralComponentManager
from src.frame.dto.driver_config import DriverConfigFormatter
from src.utils.async_utils import get_event_loop_safely
from src.utils.clazz_utils import ClazzUtils
from src.utils.sys_path_utils import SysPathUtils


class Task:
    # 热加载锁
    # 用途：保证执行过程中，热加载的节点在下次执行时一定是最新的！
    # 背景：循环执行的任务中：A->B->A循环执行
    # 描述：若是B节点正在运行中，被修改了代码，若是hot_reload（热加载方法）执行较慢，会导致B节点stop()之后A节点，再返回到旧的B节点，导致B节点热加载失败。
    # 结果：因此需要加锁，保证执行过程中，B节点在下次执行时一定是热加载过的。
    hot_reload_lock = threading.Lock()

    def __init__(self, driver, user_config: Tuple[str, str], task_config, logger,
                 user_manager=None):
        self.driver = driver  # 浏览器驱动
        # self.driver_manager: WebDriverManager = WebDriverManager(logger)
        self.task_config = task_config  # 任务配置
        self.global_config = task_config.get("batch_info").get("global_config")  # 全局配置
        self.logger = logger  # 日志
        self.batch_no = self.task_config.get("batch_no")  # 任务所属的批次号
        self.task_tmpl = self.task_config.get("task_tmpl")  # 任务模板
        self.task_tmpl_id = self.task_tmpl.get("id")  # 任务模板ID，用于区分不同任务，每个任务的运行都是基于某个任务模板
        short_id = shortuuid.ShortUUID().random(length=8)  # 生成一个7字符的短UUID
        self.task_uuid = f'{self.batch_no}_{self.task_tmpl_id}_{short_id}'  # 任务ID=uuid4_[任务模板ID]
        self.nodes: Dict[int, BaseNode] = {}  # 节点注册表：key=node_id, value=BaseTaskNode实例
        self.context: Dict[str, Any] = {}  # 任务上下文，用于节点间数据传递
        self.start_node_id: Optional[int] = None  # 流程起始节点ID
        self.component_manager = GeneralComponentManager()  # 组件管理器
        self.executed_nodes: List[str] = []  # 记录已执行的节点ID（执行链路）
        self.current_node_id = None  # 当前执行节点ID
        self.user_manager = user_manager  # 用户管理器，用于操作用户数据
        self.user_config: Tuple[str, str] = user_config  # 用户配置, 格式：(用户名, 密码)
        if len(user_config) < 1:
            raise ValueError("用户配置错误，用户名不能为空")
        self.username = user_config[0]  # 用户名必传，即使是无用户任务，也要传用户名
        self.support_hot_reload_nodes = []  # 支持热加载节点
        self.hot_reloaded_nodes = []  # 已热加载的节点列表
        self.init_nodes()  # 初始化节点

    def init_nodes(self):
        """
        从配置字典加载节点（可扩展为从JSON/YAML文件加载）
        配置格式示例：
        {
            "start_node_id": "t0001",
            "task_nodes": [
                {
                    "component_path": "components/login/hxjyw_login.py",
                    "description": "海西教育网登录逻辑",
                    "next_node_id": "t0002",
                    "node_id": "t0001",
                    "node_name": "海西教育网登录",
                    "node_params": {
                        "login_url": "https://hxjywyxpt.t-px.cn/",
                        "project_code": "hxxy2025"
                    },
                    "node_type": "login"
                },
                {
                    "component_path": "components/enter_course/hxjyw_enter_course.py",
                    "description": "导航到目标课程页面",
                    "next_node_id": "t0003",
                    "node_id": "t0002",
                    "node_name": "海西教育网进入课程",
                    "node_params": {
                        "course_type": "公需课|1",
                        "project_code": "hxxy2025"
                    },
                    "node_type": "enter_course"
                },
                {
                    "component_path": "./components/monitor_course/general_monitor_course_handler.py",
                    "description": "执行课程学习监控逻辑",
                    "hot_reload": 1,
                    "next_node_id": "t0002",
                    "node_id": "t0003",
                    "node_name": "通用课程监控",
                    "node_params": {
                        "adapter": "./components/switch_course/enterprise_switch_course_handler.py"
                    },
                    "node_type": "monitor"
                }
            ]
        }
        """
        self.start_node_id = self.task_tmpl.get("start_node_id")
        if not self.start_node_id:
            raise ValueError("配置中必须指定start_node_id")

        # 根据配置创建节点实例并注册
        node_configs = self.task_config.get("task_nodes", [])

        for node_cfg in node_configs:
            # 创建节点实例
            node_instance = self.create_node_instance(node_cfg)
            # 注册节点实例
            self.register_node(node_instance)
            # 注册热加载节点
            if node_cfg.get("node_params", {}).get("is_support_hot_reload"):
                self.support_hot_reload_nodes.append(node_instance.node_id)

        if self.start_node_id not in self.nodes:
            raise ValueError(f"配置中指定的start_node_id：{self.start_node_id} 不在该任务下")

    def register_node(self, node: BaseNode):
        """
        注册节点到调度器
        :param node: 节点
        :return:
        """
        node_id = node.node_id
        # if node_id in self.nodes:
        #     raise ValueError(f"节点ID {node_id} 已存在，无法重复注册")
        self.nodes[node_id] = node
        node.bind_task(self)

    def create_node_instance(self, node_cfg: Dict[str, Any]) -> BaseNode:
        """
        创建节点实例
        :param node_cfg: 节点配置信息 tb_node表
        """
        # 创建浏览器驱动，一个用户对应一个浏览器驱动，不能在协程中创建！！！
        # driver = await self.driver_manager.create_user_driver(self.username, self.batch_no, DriverConfigFormatter.format(self.global_config))
        # 填充完整组件路径
        component_path = self._complete_component_path(node_cfg["component_path"])
        # 更新组件路径
        node_cfg["component_path"] = component_path
        component_ext = os.path.splitext(component_path)[1].lower()
        # 支持2中类型的组件：Python组件、JavaScript组件。
        # python组件中也可支持调用JS组件，但JS组件无法调用Python组件。
        if component_ext == ".py":
            # 加载Python组件（支持热更新）
            component_cls = self.component_manager.load_component(component_path, BasePYNode,
                                                                  str(Path(SysPathUtils.get_root_dir(),
                                                                           "components_deps")))
            # 创建python节点实例
            node_instance = component_cls(
                driver=self.driver,
                user_manager=self.user_manager,
                global_config=self.global_config,
                task_config=self.task_config,
                node_config=node_cfg,
                user_config=self.user_config,
                logger=self.logger,
            )

        elif component_ext == ".js":
            # 创建js节点实例
            node_instance = JSNode(
                driver=self.driver,
                user_manager=self.user_manager,
                js_component_path=component_path,
                global_config=self.global_config,
                task_config=self.task_config,
                node_config=node_cfg,
                user_config=self.user_config,
                logger=self.logger)
        else:
            raise Exception(f"不支持的组件类型：{component_ext}，加载失败的组件：{component_path}")

        return node_instance

    async def run(self, reset_context: bool = True) -> bool:
        """
        执行整个任务流程
        :return : True-成功；False-失败
        """
        if reset_context:
            self.context = {}
            self.executed_nodes = []  # 重置执行链路
        task_name = f"{self.task_config.get('batch_info').get('project_name')} - {self.task_tmpl.get('name')}"
        self.logger.info(f"===== 启动【{task_name}】任务 =====")
        # 任务成功标志
        is_success = True
        try:
            # 任务整体最大重登次数
            max_task_relogin_times = self.task_config.get("task_tmpl_config", {}).get("relogin_config", {}).get(
                "max_task_relogin_times", 3)
            # 设置当前执行节点ID为起始节点
            self.current_node_id = self.start_node_id
            # 任务整体重登次数（从头执行的次数）
            task_relogin_count = 0
            # 核心调度逻辑：按next_node_id循环执行
            while self.current_node_id is not None:
                # 1.获取当前节点（load_config方法中实例化了所有节点）
                current_node = self.nodes.get(self.current_node_id)
                if not current_node:
                    self.logger.error(f"节点 {self.current_node_id} 不存在，流程终止")
                    break

                node_name = current_node.node_name
                node_params = current_node.node_config.get("node_params", {})

                self.logger.info(f"开始执行节点: {self.current_node_id} ({node_name})")
                # 2.执行当前节点
                node_success = await current_node.execute(self.context)
                with self.hot_reload_lock:  # 加锁目的：有热更新节点时，等待热更新执行完毕
                    # 3.清理当前节点，非常重要！节点中需要清理的资源，如变量、文件、数据库连接等
                    await current_node.clean_up()
                    if self.current_node_id in self.hot_reloaded_nodes:
                        # 清空热更新节点列表
                        self.hot_reloaded_nodes = []
                        # 被热更新了，则重新执行当前节点（在hot_reload中当前节点的实例已经被更新了）
                        self.current_node_id = current_node.node_id
                        continue

                if not node_success:
                    self.logger.info(f"节点 {self.current_node_id} ({node_name}) 执行完毕！发出结束信号，流程终止！")
                    break

                self.logger.info(f"节点 {self.current_node_id} ({node_name}) 执行完毕！准备执行下一个节点！")
                # 将当前节点加入执行链路
                self.executed_nodes.append(self.current_node_id)
                # 获取节点执行结果
                node_result = current_node.get_node_result()
                # 3.处理重登，通过错误消息匹配重登关键词，且任务重登次数未超限
                # 节点中遇到需要重登的情况时需要特殊返回：execute()返回True，且node_result中is_success=True，并设置error_msg，此处会去匹配关键词
                if self._is_need_relogin(node_params, node_result.get("error_msg", "")):
                    if task_relogin_count < max_task_relogin_times:
                        self.logger.warning(f"节点{node_name}匹配重登关键词，准备任务重登")
                        task_relogin_count += 1
                        self.logger.info(f"任务重登次数更新为：{task_relogin_count}，即将执行登录节点（一次登录）")
                        self.current_node_id = node_params.get("relogin_node_id")
                    else:
                        self.logger.error(f"任务整体重登次数已达上限（{max_task_relogin_times}次），任务失败！")
                        is_success = False
                        break
                else:
                    # 获取下一个节点ID
                    self.current_node_id = current_node.next_node_id

        except Exception as e:
            # self.logger.debug(f"任务执行异常：", exc_info=True)
            self.logger.error(f"任务执行异常：{str(e)}", exc_info=True)
            is_success = False
        finally:
            # if self.task_tmpl.get("is_quit_browser_when_finished", True):
            #     # self.logger.info(f"关闭Context")
            #     await self.driver_manager.remove_user_driver(self.batch_no, self.username)
            # else:
            #     self.logger.info(f"任务执行完毕，不关闭当前用户的浏览器，请用户手动关闭！")
            self.logger.info(f"===== 任务【{task_name}】执行完成，状态：{'成功' if is_success else '失败'} =====")
        return is_success

    def hot_reload(self, component_path: str):
        """
        热加载
        找到需要热加载的节点，重载代码，创建实例，并将该实例加入到节点列表。
        :param component_path: 组件路径
        :return:
        """
        target_task_node = None
        for task_node_id in self.support_hot_reload_nodes:
            if component_path == self.nodes[task_node_id].node_config.get("component_path"):
                target_task_node = self.nodes[task_node_id]
                break

        if not target_task_node:
            self.logger.info(f"任务【{self.task_uuid}】忽略热更新，原因：未找到组件路径:{component_path}")
            return

        with self.hot_reload_lock:
            # 1.中断旧组件
            if target_task_node.state == NodeState.RUNNING:
                # 以课程监控节点为例，当调用stop()时会触发中断，会正常退出，返回True，自动执行下一个节点的逻辑
                # 因此热更新时，此处仅需要中断，不需要任何逻辑，但是可能存在一个bug，创建新的节点实例速度较慢，而旧节点的下一个节点已经执行完了，就会重新执行旧的节点，导致热加载失败！
                if hasattr(target_task_node, "terminate"):
                    target_task_node.terminate("热加载中断")
                # TODO 待解决！为何此处clean_up后会导致热加载不会退出！20260107 20:48
                # if hasattr(target_task_node, "clean_up"):
                #     target_task_node.clean_up()
            # 2.重新加载组件，创建新的组件实例
            new_node_instance = get_event_loop_safely().run_until_complete(
                self.create_node_instance(target_task_node.node_config)
            )
            # 3.复制属性
            ClazzUtils.copy_object_attributes(target_task_node, new_node_instance, False)
            # 3.重新注册节点
            self.register_node(new_node_instance)
            # 4.加入需要热加载的节点列表，在run方法中用到
            self.hot_reloaded_nodes.append(target_task_node.node_id)
            self.logger.info(f"任务【{self.task_uuid}】节点【{target_task_node.node_name}】热更新成功")

    def get_node(self, node_id: int) -> Optional[BaseNode]:
        """
        获取任务内指定节点
        :param node_id: 节点ID
        """
        return self.nodes.get(node_id)

    def _is_need_relogin(self, node_params, error_msg: str) -> bool:
        """
        判断是否需要触发重登
        :param node_params: 节点参数
        :param error_msg: 错误消息，用于匹配是否需要重登
        :return:
        """
        if not node_params.get("is_support_relogin") or not error_msg or not error_msg.strip():
            return False
        trigger_errors = self.task_config.get("task_tmpl_config", {}).get("relogin_config", {}).get(
            "relogin_trigger_errors",
            [])
        for error_keyword in trigger_errors:
            if error_keyword.lower() in error_msg.lower():
                return True
        return False

    def _complete_component_path(self, component_path: str):
        if not Path(component_path).is_absolute():
            component_path = str(Path(SysPathUtils.get_root_dir(), component_path))
        return component_path
