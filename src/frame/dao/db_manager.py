import json
import logging

from src.frame.common.qt_log_redirector import LOG
from src.frame.dao.action_dao import ActionDAO
from src.frame.dao.node_dao import NodeDAO
from src.frame.common.decorator.singleton import singleton
from src.frame.dao.base_db import BaseDB
from src.frame.dao.data_dict_dao import DataDictDAO
from src.frame.dao.project_dao import ProjectDAO
from src.frame.dao.task_batch_dao import TaskBatchDAO
from src.frame.dao.task_tmpl_dao import TaskTmplDAO
from src.frame.dao.task_node_mapping_dao import TaskTmplNodeMappingDAO
from src.frame.dao.task_tmpl_config_dao import TaskTmplConfigDAO
from typing import Dict, Any, List


@singleton
class DBManager(BaseDB):
    """业务聚合层：封装跨表核心业务，上层PyQt仅需调用此类"""
    def __init__(self, logger=logging):
        super().__init__(logger)
        self.node_dao = NodeDAO(logger)
        self.project_dao = ProjectDAO(logger)
        self.task_tmpl_dao = TaskTmplDAO(logger)
        self.task_tmpl_node_mapping_dao = TaskTmplNodeMappingDAO(logger)
        self.task_tmpl_config_dao = TaskTmplConfigDAO(logger)
        self.data_dict_dao = DataDictDAO(logger)
        self.task_batch_dao = TaskBatchDAO(logger)
        self.action_dao = ActionDAO(logger)

    def get_init_sql(self):
        return "select 1;"

    # 核心跨表业务：合并节点固有参数+任务动态参数
    def get_merged_node_params(self, task_tmpl_id: str, node_id: str) -> Dict[str, Any]:
        native_params = self.node_dao.get_by_id(node_id).get("node_params", {})
        task_params = self.task_tmpl_node_mapping_dao.get_task_node_params(task_tmpl_id, node_id)
        return {**native_params, **task_params}

    # 其他跨表业务可在此追加（如：删除任务+清理映射+清理配置）
    # ========== ✅ 新增核心：根据task_tmpl_id获取已配置节点完整详情（关联查询） ==========
    def get_task_configured_nodes_detail(self, task_tmpl_id: int) -> List[Dict]:
        """
        根据任务模板ID，查询该任务已配置的所有节点完整信息（关联查询核心方法）
        :param task_tmpl_id: 任务模板自增主键ID
        :return: 节点详情列表（包含绑定关系+节点原生信息，JSON自动反序列化）
        """
        # ✅ 核心关联SQL：左连接保证绑定的节点全部查出，关联条件：task_node.node_id = node.id
        sql = """
            SELECT 
                t1.id, t1.domain, t1.business_type, t1.name, t1.login_interval, t1.is_quit_browser_when_finished, 
                t1.start_node_id, t1.start_mode,
                t2.task_tmpl_id, t2.node_id, t2.pre_node_id, t2.next_node_id, t2.node_params AS bind_node_params,
                n.code AS node_code, n.name AS node_name, n.component_path, n.type AS node_type, 
                n.description AS node_description,
                n.node_params AS native_node_params 
            FROM tb_task_tmpl t1 
            left join tb_task_tmpl_node_mapping t2 on t1.id=t2.task_tmpl_id
            LEFT JOIN tb_node t3 ON t2.node_id = t3.id
            WHERE t1.id = ?
            ORDER BY t2.create_time ASC
        """
        try:
            with self.get_db_connection() as conn:
                rows = conn.execute(sql, (task_tmpl_id,)).fetchall()

            # 数据二次加工：JSON字符串反序列化为字典 + 字段整合（UI直接使用）
            result_list = []
            for row in rows:
                row_dict = self.dict_from_row(row)  # 转为字典（复用BaseDB的方法）
                # JSON反序列化（绑定参数+节点原生参数）
                row_dict["bind_node_params"] = json.loads(row_dict["bind_node_params"]) if row_dict[
                    "bind_node_params"] else {}
                row_dict["native_node_params"] = json.loads(row_dict["native_node_params"]) if row_dict[
                    "native_node_params"] else {}
                result_list.append(row_dict)
            return result_list
        except Exception as e:
            self.logger.error(f"关联查询任务节点详情失败：{str(e)}")
            return []

# 全局唯一数据管理器
db = DBManager(LOG)

if __name__ == '__main__':
    # logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    # logger = logging.getLogger("BaseDB")
    # db_manager = DBManager(logging)
    # node_id = db_manager.node_dao.add_node({"code": "t0003", "name": "百度", "component_path": "baidu", "type": "task", "description": "百度", "node_params": {"a": 1, "b": 2}})
    # if not node_id:
    #     node_id = db_manager.node_dao.get_by_code("t0003")["id"]
    # task_tmpl_id = db_manager.task_tmpl_dao.add_task({"domain": "https://www.baidu.com", "business_type": "baidu", "name": "百度", "login_interval": 1, "is_quit_browser_when_finished": 0, "start_node_id": 1})
    # db_manager.task_tmpl_config_dao.save_task_config(task_tmpl_id, {"a": 1, "b": 2})
    # db_manager.task_node_dao.bind_task_node({"task_tmpl_id": task_tmpl_id, "node_id": node_id, "pre_node_id": "", "next_node_id": "", "node_params": {"a": 1, "b": 2}})

    task = db.task_tmpl_dao.get_by_id(1)
    print(task)