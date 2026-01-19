from typing import Dict, List, Any

from src.frame.dao.base_db import BaseDB


class TaskTmplNodeMappingDAO(BaseDB):
    """tb_task_tmpl_node_mapping 表专属操作类"""

    def get_init_sql(self):
        sql = """
        -- 任务-节点映射表
CREATE TABLE IF NOT EXISTS tb_task_tmpl_node_mapping (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_tmpl_id INTEGER NOT NULL,
    node_id INTEGER NOT NULL,
    pre_node_id INTEGER DEFAULT NULL,
    next_node_id INTEGER DEFAULT NULL,
    node_params TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY (task_tmpl_id) REFERENCES tb_task_tmpl(id) ON DELETE CASCADE,
    FOREIGN KEY (node_id) REFERENCES tb_node(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS idx_tb_task_tmpl_node_mapping_task_tmpl_id ON tb_task_tmpl_node_mapping(task_tmpl_id);
CREATE INDEX IF NOT EXISTS idx_tb_task_tmpl_node_mapping_node_id ON tb_task_tmpl_node_mapping(node_id);
"""
        return sql.strip()

    def bind_task_node(self, mapping_info: Dict[str, Any]) -> bool:
        sql = """INSERT INTO tb_task_tmpl_node_mapping (task_tmpl_id, node_id, pre_node_id, next_node_id, node_params)
                 VALUES (?, ?, ?, ?, ?)"""
        params = (mapping_info["task_tmpl_id"], mapping_info["node_id"], mapping_info.get("pre_node_id", None),
                  mapping_info.get("next_node_id", None), self.json_serialize(mapping_info.get("node_params", {})))
        try:
            with self.get_db_connection() as conn:
                conn.execute(sql, params)
            return True
        except:
            self.logger.exception(
                f"任务-节点映射失败 | 任务编号：{mapping_info['task_tmpl_id']} 节点编号：{mapping_info['node_id']}")
            return False

    def get_task_node_mapping(self, task_tmpl_id: str) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM tb_task_tmpl_node_mapping WHERE task_tmpl_id = ?"
        with self.get_db_connection() as conn:
            rows = conn.execute(sql, (task_tmpl_id,)).fetchall()
        mapping_list = [self.dict_from_row(row) for row in rows]
        for mapping in mapping_list: mapping["node_params"] = self.json_deserialize(mapping["node_params"])
        return mapping_list

    def get_task_node_params(self, task_tmpl_id: str, node_id: str) -> Dict[str, Any]:
        sql = "SELECT node_params FROM tb_task_tmpl_node_mapping WHERE task_tmpl_id = ? AND node_id = ?"
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (task_tmpl_id, node_id)).fetchone()
        return self.json_deserialize(row["node_params"]) if row else {}

    def get_by_task_tmpl_id_and_node_id(self, task_tmpl_id: str, node_id: str) -> Dict[str, Any]:
        sql = "SELECT * FROM tb_task_tmpl_node_mapping WHERE task_tmpl_id = ? AND node_id = ?"
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (task_tmpl_id, node_id)).fetchone()
        return self.dict_from_row(row) if row else {}

    def get_by_node_id(self, node_id: str) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM tb_task_tmpl_node_mapping WHERE node_id = ?"
        with self.get_db_connection() as conn:
            rows = conn.execute(sql, (node_id,)).fetchall()
        mapping_list = [self.dict_from_row(row) for row in rows]
        for mapping in mapping_list: mapping["node_params"] = self.json_deserialize(mapping["node_params"])
        return mapping_list

    # ========== ✅ 新增核心：修改方法（3个高频实用） ==========
    def update_by_task_tmpl_id(self, task_tmpl_id: int, update_infos: List[Dict[str, Any]]) -> bool:
        """
        更新任务的节点配置
        :param task_tmpl_id: 表自增主键ID（必传，更新依据）
        :param update_infos: 待更新记录：node_id/pre_node_id/next_node_id/node_params
        :return: 操作结果 True/False
        """
        # 1.删除旧数据
        with self.get_db_connection() as conn:
            conn.execute("DELETE FROM tb_task_tmpl_node_mapping WHERE task_tmpl_id = ?", (task_tmpl_id,))
            # 2.批量插入
            sql = """INSERT INTO tb_task_tmpl_node_mapping (task_tmpl_id, node_id, pre_node_id, next_node_id, node_params)
                             VALUES (?, ?, ?, ?, ?)"""
            data_list = [(task_tmpl_id, update_info["node_id"], update_info.get("pre_node_id", ""),
                          update_info.get("next_node_id", ""), update_info.get("node_params", "{}"))
                         for
                         update_info in update_infos]
            try:
                conn.cursor().executemany(sql, data_list)
                return True
            except:
                self.logger.exception(f"任务-节点映射更新失败 | 任务编号：{task_tmpl_id} ")
                return False

    def update_by_id(self, record_id: int, update_info: Dict[str, Any]):
        """
        根据ID更新记录
        :param record_id: 记录ID
        :param update_info: 支持更新的字段：pre_node_id，next_node_id，node_params
        :return:
        """
        try:
            with self.get_db_connection() as conn:
                sql = """UPDATE tb_task_tmpl_node_mapping SET pre_node_id = ?, next_node_id = ?,
                                 node_params = ? WHERE id = ?"""
                node_params = update_info.get("bind_node_params", "")
                if node_params and isinstance(node_params, dict):
                    node_params = self.json_serialize(node_params)
                params = (update_info.get("pre_node_id", ""),
                          update_info.get("next_node_id", ""),
                          node_params, record_id)
                conn.execute(sql, params)
                return True
        except:
            self.logger.exception(f"任务-节点信息更新失败 | 记录ID：{record_id}")
            return False

    def delete_by_ids(self, ids: List[int]):
        sql = "DELETE FROM tb_task_tmpl_node_mapping WHERE id IN (%s)" % ",".join(["?"] * len(ids))
        try:
            with self.get_db_connection() as conn:
                conn.execute(sql, ids)
            return True
        except:
            self.logger.exception(f"任务-节点映射删除失败 | 节点ID：{ids}")
            return False

    def update_task_node_params(self, task_tmpl_id: str, node_id: str, node_params: Dict) -> bool:
        """
        仅更新任务节点绑定的动态参数
        :param task_tmpl_id: 任务模板ID
        :param node_id: 节点ID
        :param node_params: 新参数字典（自动序列化）
        :return: 操作结果 True/False
        """
        sql = "UPDATE tb_task_tmpl_node_mapping SET node_params = ? WHERE task_tmpl_id = ? AND node_id = ?"
        try:
            with self.get_db_connection() as conn:
                conn.execute(sql, (self.json_serialize(node_params), task_tmpl_id, node_id))
            return True
        except:
            self.logger.exception(f"任务-节点参数更新失败 | 任务模板ID：{task_tmpl_id} 节点ID：{node_id}")
            return False

    def update_task_node_topology(self, task_tmpl_id: str, node_id: str, pre_node_id: str, next_node_id: str) -> bool:
        """
        快捷更新【拓扑维度】- 单独修改前置/后置节点关系（核心业务高频）
        :param task_tmpl_id: 任务模板ID
        :param node_id: 节点ID
        :param pre_node_id: 新前置节点ID
        :param next_node_id: 新后置节点ID
        :return: 操作结果 True/False
        """
        sql = "UPDATE tb_task_tmpl_node_mapping SET pre_node_id = ?, next_node_id = ? WHERE task_tmpl_id = ? AND node_id = ?"
        with self.get_db_connection() as conn:
            conn.execute(sql, (pre_node_id, next_node_id, task_tmpl_id, node_id))
        return True
