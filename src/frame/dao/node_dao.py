import json
from typing import Dict, List, Optional, Any, Tuple

from sympy.physics.vector.printing import params

from src.frame.common.decorator.singleton import singleton
from src.frame.common.exceptions import BusinessException
from src.frame.dao.base_db import BaseDB
from src.frame.dao.task_node_mapping_dao import TaskTmplNodeMappingDAO


@singleton
class NodeDAO(BaseDB):
    """tb_node 表专属操作类"""

    def get_init_sql(self) -> str:
        """返回完整的建表/索引/触发器SQL"""
        sql = """
CREATE TABLE IF NOT EXISTS tb_node (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 数据库自增主键（内部关联用）
    code TEXT NOT NULL UNIQUE,        -- 自定义业务ID（t0001/monitor_01，人工管理用）
    name TEXT NOT NULL,
    component_path TEXT NOT NULL,
    type TEXT NOT NULL,  -- 节点类型。login/enter_course/monitor/score/choose_course/exam/upload/download/collect
    description TEXT DEFAULT '',
    node_params TEXT NOT NULL DEFAULT '{}',
    status INTEGER NOT NULL DEFAULT 1,  -- ✅ 新增：0-停用，1-启用
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tb_node_type ON tb_node(type);
CREATE INDEX IF NOT EXISTS idx_tb_code ON tb_node(code); -- 业务码加唯一索引
CREATE INDEX IF NOT EXISTS idx_tb_node_status ON tb_node(status); -- 新增状态索引，方便筛选启用节点
"""
        return sql.strip()

    def add_one(self, node_info: Dict[str, Any]) -> int | None:
        # ✅ 第一步：校验ID是否已存在
        if self.get_by_code(node_info["code"]):
            raise BusinessException(f"新增节点失败 | 节点编号：{node_info['code']} 已存在")
        sql = """INSERT INTO tb_node (code, name, component_path, type, description, node_params)
                 VALUES (?, ?, ?, ?, ?, ?)"""
        params = (node_info["code"], node_info["name"], node_info["component_path"], node_info["type"],
                  node_info.get("description", ""), self.json_serialize(node_info.get("node_params", {})))
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            new_node_id = cursor.lastrowid
        return new_node_id

    def get_by_id(self, node_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM tb_node WHERE id = ?"
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (node_id,)).fetchone()
            node = self.dict_from_row(row)
            if node: node["node_params"] = self.json_deserialize(node["node_params"])
        return node

    def get_by_task_tmpl_id(self, task_tmpl_id: int):
        sql = """
SELECT t2.id, t1.id as node_id, t1.code, t1.name, t1.component_path, t1.type, t1.description, t1.node_params as native_node_params, t1.status, 
t2.task_tmpl_id, t2.node_id, t2.pre_node_id, t2.next_node_id, t2.node_params as bind_node_params 
FROM tb_node t1 
LEFT JOIN tb_task_tmpl_node_mapping t2 ON t1.id = t2.node_id
WHERE t2.task_tmpl_id = ?
"""
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
            row_dict["node_params"] = {**row_dict["native_node_params"], **row_dict["bind_node_params"]}
            result_list.append(row_dict)
        return result_list

    def get_list(self, node_type: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM tb_node"
        params = []
        if node_type: sql += " WHERE type = ?"; params.append(node_type)
        with self.get_db_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        node_list = [self.dict_from_row(row) for row in rows]
        for node in node_list: node["node_params"] = self.json_deserialize(node["node_params"])
        return node_list

    def get_by_code(self, code: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM tb_node WHERE code = ?"
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (code,)).fetchone()
            node = self.dict_from_row(row)
            if node: node["node_params"] = self.json_deserialize(node["node_params"])
        return node

    def delete_node(self, node_id: str) -> bool:
        """删除节点时，先检查该节点是否被任务引用，如果被引用则不允许删除"""
        if TaskTmplNodeMappingDAO(self.logger).get_by_node_id(node_id):
            self.logger.error(f"删除节点失败 | 节点编号：{node_id} 正在被任务引用，请先解除引用关系")
            return False

        sql = """DELETE FROM tb_node WHERE id = ?"""
        try:
            with self.get_db_connection() as conn:
                conn.execute(sql, (node_id,))
            return True
        except:
            self.logger.exception(f"删除节点失败 | 节点编号：{node_id}")
            return False

    def update_by_id(self, node_id: str, update_info: Dict[str, Any]) -> bool:
        """
        通用节点更新方法【推荐】：支持更新任意字段（主键id除外）
        :param node_id: 节点主键ID（必传，不可修改）
        :param update_info: 待更新字段字典，支持：name/type/component_path/description/node_params/status
        :return: 操作结果 True/False
        """
        # 1. 安全校验：禁止修改主键ID
        if "id" in update_info:
            raise ValueError("节点主键ID不可修改！")

        record = self.get_by_id(node_id)
        if not record:
            raise BusinessException(f"更新节点失败 | 节点编号：{node_id} 不存在")

        if update_info.get("code") != record.get("code") and self.get_by_code(update_info["code"]):
                raise BusinessException(f"更新节点失败 | 节点编号：{update_info['code']} 已存在")

        # 2. 过滤空字段，组装更新SQL
        update_fields = []
        params = []
        for field, value in update_info.items():
            # JSON字段自动序列化：node_params → 字典转JSON字符串
            if field == "node_params" and isinstance(value, dict):
                value = self.json_serialize(value)
            update_fields.append(f"{field} = ?")
            params.append(value)
        # 3. 拼接主键条件
        params.append(node_id)
        sql = f"UPDATE tb_node SET {','.join(update_fields)} WHERE id = ?"
        # 4. 执行更新
        try:
            with self.get_db_connection() as conn:
                conn.execute(sql, params)
            return True
        except:
            self.logger.exception(f"更新节点失败 | 节点编号：{node_id}")
            return False

    def delete_by_ids(self, node_ids: List[int]):
        with self.get_db_connection() as conn:
            node_ids_placeholders = ','.join(['?'] * len(node_ids))
            sql = """select * from tb_task_tmpl_node_mapping where node_id in (%s) or pre_node_id in (%s) or next_node_id in (%s)""" % (node_ids_placeholders, node_ids_placeholders, node_ids_placeholders)
            params = []
            params.extend(node_ids)
            params.extend(node_ids)
            params.extend(node_ids)
            rows = conn.execute(sql, params).fetchall()
            node_list = [self.dict_from_row(row) for row in rows]
            if any([len(node)>0 for node in node_list]):
                raise BusinessException(f"节点ID={node_ids} 正在被任务引用，请先解除引用关系")
            sql = """DELETE FROM tb_node WHERE id IN (%s)""" % node_ids_placeholders
            conn.execute(sql, node_ids)

    def update_status(self, node_id: str, status: int) -> bool:
        """
        快捷方法：单独更新节点启用/停用状态【高频使用】
        :param node_id: 节点ID
        :param status: 0=停用，1=启用
        :return: 操作结果 True/False
        """
        if status not in [0, 1]:
            raise ValueError("节点状态仅支持 0(停用) / 1(启用)")
        sql = "UPDATE tb_node SET status = ? WHERE id = ?"
        try:
            with self.get_db_connection() as conn:
                conn.execute(sql, (status, node_id))
            return True
        except:
            self.logger.exception(f"更新节点失败 | 节点编号：{node_id}")
            return False

    def get_total_count(self, node_type: Optional[str] = None, name: Optional[str] = None, code: Optional[str] = None) -> int:
        """获取节点总条数（支持按业务类型筛选，分页必备）"""
        sql = "SELECT COUNT(*) AS total FROM tb_node"
        params = []
        where_conditions = []  # 条件集合，自动拼接

        # 条件1：业务类型精准筛选（原有）
        if node_type and node_type.strip():
            where_conditions.append("type = ?")
            params.append(node_type.strip())
        # 条件2：新增任务名称模糊筛选（核心优化）
        if name and name.strip():
            where_conditions.append("name LIKE ?")
            params.append(f"%{name.strip()}%")
        # 条件3：新增编号模糊筛选（核心优化）
        if code and code.strip():
            where_conditions.append("code LIKE ?")
            params.append(f"%{code.strip()}%")

        # 拼接多条件（多个条件用AND连接，无则不拼接）
        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)

        with self.get_db_connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return row["total"] if row else 0

    def get_list_by_page(self,
                         page_num: int = 1,
                         page_size: int = 10,
                         node_type: Optional[str] = None,
                         name: Optional[str] = None,
                         code: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        分页查询任务列表（核心翻页方法）
        :param page_num: 当前页码，默认1（前端UI通用规则，从1开始）
        :param page_size: 每页条数，默认10
        :param node_type: 可选，按业务类型筛选，None则查全部
        :param name: 可选，按任务名称筛选，支持全模糊查询，None则查全部
        :param code: 可选，按编号筛选，支持全模糊查询，None则查全部
        :return: 当前页任务数据列表
        """
        # 边界值校验（防异常）
        if page_num < 1: page_num = 1
        if page_size < 1 or page_size > 100: page_size = 10  # 限制最大页条数，防性能问题

        # SQLite分页核心语法：LIMIT 条数 OFFSET 偏移量（偏移量=(页码-1)*页大小）
        offset = (page_num - 1) * page_size
        sql = "SELECT * FROM tb_node"
        params = []
        where_conditions = []

        # 拼接筛选条件
        if node_type and node_type.strip():
            where_conditions.append("type = ?")
            params.append(node_type.strip())
        if name and name.strip():
            where_conditions.append("name LIKE ?")
            params.append(f"%{name.strip()}%")
        if code and code.strip():
            where_conditions.append("code LIKE ?")
            params.append(f"%{code.strip()}%")

        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)
        # 拼接分页+排序（按创建时间倒序，最新任务在前，符合业务习惯）
        sql += " ORDER BY create_time DESC LIMIT ? OFFSET ?"
        params.extend([page_size, offset])

        # 执行查询
        with self.get_db_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self.dict_from_row(row) for row in rows]

    def get_page_data(self,
                      page_num: int = 1,
                      page_size: int = 10,
                      node_type: Optional[str] = None,
                      name: Optional[str] = None,
                      code: Optional[str] = None,) -> Tuple[List[Dict[str, Any]], int]:
        """
        ✅ 对外统一调用【推荐】- 标准化分页数据返回（Qt UI直接绑定）
        :return: 包含总条数、总页数、分页参数、数据的完整字典
        """
        total_count = self.get_total_count(node_type, name, code)  # 总条数
        # total_page = math.ceil(total_count / page_size) if total_count > 0 else 1  # 总页数
        task_list = self.get_list_by_page(page_num, page_size, node_type, name, code)  # 当前页数据
        return task_list, total_count

    def get_all(self) -> List[Dict[str, Any]]:
        sql = """SELECT * FROM tb_node"""
        with self.get_db_connection() as conn:
            rows = conn.execute(sql).fetchall()
            rows_ = [self.dict_from_row(row) for row in rows]
            return rows_