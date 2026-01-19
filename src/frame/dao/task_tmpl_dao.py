from typing import Dict, List, Optional, Any, Tuple

from src.frame.common.decorator.singleton import singleton
from src.frame.dao.base_db import BaseDB


@singleton
class TaskTmplDAO(BaseDB):
    """tb_task_tmpl 表专属操作类"""

    def get_init_sql(self) -> str:
        """返回完整的建表/索引/触发器SQL"""
        sql = """
-- 任务模板表
CREATE TABLE IF NOT EXISTS tb_task_tmpl (    
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL,  -- 所属项目ID
    domain TEXT NOT NULL,  -- 域名
    business_type TEXT NOT NULL,  -- 业务类型：learning/exam/login/score/choose_course/upload/download/collect
    name TEXT NOT NULL,
    login_interval INTEGER NOT NULL,
    is_quit_browser_when_finished INTEGER NOT NULL DEFAULT 0,
    start_node_id INTEGER DEFAULT NULL,
    status INTEGER NOT NULL DEFAULT 1,  -- ✅ 新增：0-停用，1-启用
    start_mode INTEGER NOT NULL DEFAULT 1, -- 启动模式：0-无用户；1-有用户
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tb_task_tmpl_business_type ON tb_task_tmpl(business_type);
    """
        return sql.strip()

    def add_one(self, task_info: Dict[str, Any]) -> int:
        sql = """INSERT INTO tb_task_tmpl (project_id, domain, business_type, name, login_interval,
                                      is_quit_browser_when_finished, start_mode, start_node_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
        params = (task_info["project_id"], task_info["domain"], task_info["business_type"],
                  task_info["name"],
                  task_info["login_interval"], task_info.get("is_quit_browser_when_finished", 0),
                  task_info.get("start_mode", 1), task_info.get("start_node_id", None))
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.lastrowid  # ✅ 返回自增主键

    def batch_add(self, task_infos: List[Dict[str, Any]]) -> bool:
        sql = """INSERT INTO tb_task_tmpl (project_id, domain, business_type, name, login_interval,
                                      is_quit_browser_when_finished, start_mode, start_node_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?)"""
        data_tuples = []
        for data in task_infos:
            data_tuple = (
                data.get("project_id"),  # 必填
                data.get("domain"),  # 必填
                data.get("business_type"),  # 必填
                data.get("name"),  # 必填
                data.get("login_interval"),  # 必填
                # 可选字段：不传则用默认值0
                data.get("is_quit_browser_when_finished", 1),
                # 可选字段：不传则用默认值1
                data.get("start_mode", 1),
                # 可选字段：不传则用默认值None
                data.get("start_node_id")
            )
            data_tuples.append(data_tuple)

        with self.get_db_connection() as conn:
            conn.cursor().executemany(sql, data_tuples)

    # ✅ 新增快捷方法：单独更新起始节点（UI配置节点后调用，最常用）
    def update_start_node_id(self, task_tmpl_id: int, start_node_id: int) -> bool:
        """
        配置节点后，单独更新任务模板的起始节点ID
        :param task_tmpl_id: 任务模板自增主键ID
        :param start_node_id: 选中的首个节点ID
        :return: 操作结果True/False
        """
        sql = "UPDATE tb_task_tmpl SET start_node_id = ? , update_time = datetime('now', 'localtime')  WHERE id = ?"
        with self.get_db_connection() as conn:
            conn.execute(sql, (start_node_id, task_tmpl_id))
        return True

    def get_by_id(self, task_tmpl_id: int) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM tb_task_tmpl WHERE id = ?"
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (task_tmpl_id,)).fetchone()
        return self.dict_from_row(row)

    def get_by_project_id(self, project_id: int) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM tb_task_tmpl WHERE project_id = ?"
        with self.get_db_connection as conn:
            rows = conn.execute(sql, (project_id,)).fetchall()
            return [self.dict_from_row(row) for row in rows]

    def get_task_list(self, business_type: Optional[str] = None) -> List[Dict[str, Any]]:
        sql = "SELECT * FROM tb_task_tmpl"
        params = []
        if business_type: sql += " WHERE business_type = ?"; params.append(business_type)
        with self.get_db_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self.dict_from_row(row) for row in rows]

    # ========== ✅ 新增：分页核心方法（3个，完整支撑翻页） ==========
    def get_total_count(self, business_type: Optional[str] = None, name: Optional[str] = None) -> int:
        """获取任务模板总条数（支持按业务类型筛选，分页必备）"""
        sql = "SELECT COUNT(*) AS total FROM tb_task_tmpl"
        params = []
        where_conditions = []  # 条件集合，自动拼接

        # 条件1：业务类型精准筛选（原有）
        if business_type and business_type.strip():
            where_conditions.append("business_type = ?")
            params.append(business_type.strip())
        # 条件2：新增任务模板名称模糊筛选（核心优化）
        if name and name.strip():
            where_conditions.append("name LIKE ?")
            params.append(f"%{name.strip()}%")

        # 拼接多条件（多个条件用AND连接，无则不拼接）
        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)

        with self.get_db_connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return row["total"] if row else 0

    def get_list_by_page(self,
                         page_num: int = 1,
                         page_size: int = 10,
                         business_type: Optional[str] = None,
                         name: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        分页查询任务模板列表（核心翻页方法）
        :param page_num: 当前页码，默认1（前端UI通用规则，从1开始）
        :param page_size: 每页条数，默认10
        :param business_type: 可选，按业务类型筛选，None则查全部
        :param name: 可选，按任务模板名称筛选，支持全模糊查询，None则查全部
        :return: 当前页任务模板数据列表
        """
        # 边界值校验（防异常）
        if page_num < 1: page_num = 1
        if page_size < 1 or page_size > 100: page_size = 10  # 限制最大页条数，防性能问题

        # SQLite分页核心语法：LIMIT 条数 OFFSET 偏移量（偏移量=(页码-1)*页大小）
        offset = (page_num - 1) * page_size
        sql = "SELECT t1.*, t2.name as project_name FROM tb_task_tmpl t1 left join tb_project t2 on t1.project_id=t2.id"
        params = []
        where_conditions = []

        # 拼接筛选条件
        if business_type and business_type.strip():
            where_conditions.append("business_type = ?")
            params.append(business_type.strip())
        if name and name.strip():
            where_conditions.append("name LIKE ?")
            params.append(f"%{name.strip()}%")

        if where_conditions:
            sql += " WHERE " + " AND ".join(where_conditions)
        # 拼接分页+排序（按创建时间倒序，最新任务模板在前，符合业务习惯）
        sql += " ORDER BY create_time DESC LIMIT ? OFFSET ?"
        params.extend([page_size, offset])

        # 执行查询
        with self.get_db_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self.dict_from_row(row) for row in rows]

    def get_page_data(self,
                      page_num: int = 1,
                      page_size: int = 10,
                      business_type: Optional[str] = None,
                      name: Optional[str] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        ✅ 对外统一调用【推荐】- 标准化分页数据返回（Qt UI直接绑定）
        :return: 包含总条数、总页数、分页参数、数据的完整字典
        """
        total_count = self.get_total_count(business_type, name)  # 总条数
        # total_page = math.ceil(total_count / page_size) if total_count > 0 else 1  # 总页数
        task_list = self.get_list_by_page(page_num, page_size, business_type, name)  # 当前页数据
        return task_list, total_count
        # 标准化返回格式（UI端无需二次处理，直接取值）
        # return {
        #     "page_num": page_num,  # 当前页码
        #     "page_size": page_size,  # 每页条数
        #     "total_count": total_count,  # 数据总条数
        #     "total_page": total_page,  # 总页数
        #     "has_next": page_num < total_page,  # 是否有下一页
        #     "has_prev": page_num > 1,  # 是否有上一页
        #     "data": task_list  # 当前页任务模板数据列表
        # }

    def delete_by_id(self, task_tmpl_id: str) -> bool:
        sql = """DELETE FROM tb_task_tmpl WHERE id = ?"""
        with self.get_db_connection() as conn:
            conn.execute(sql, (task_tmpl_id,))
        return True

    def delete_by_ids(self, task_tmpl_ids: List[int]):
        with self.get_db_connection() as conn:
            task_tmpl_ids_placeholders = ','.join(['?'] * len(task_tmpl_ids))
            sql = """DELETE FROM tb_task_tmpl WHERE id IN (%s)""" % task_tmpl_ids_placeholders
            conn.execute(sql, task_tmpl_ids)
            sql = """delete from tb_task_tmpl_config where task_tmpl_id in (%s)""" % task_tmpl_ids_placeholders
            conn.execute(sql, task_tmpl_ids)
            sql = """delete from tb_task_tmpl_node_mapping where task_tmpl_id in (%s)""" % task_tmpl_ids_placeholders
            conn.execute(sql, task_tmpl_ids)

    def update_by_id(self, task_tmpl_id: str, update_info: Dict[str, Any]) -> bool:
        """
        通用任务模板更新方法【推荐】：支持更新任意字段（主键id除外）
        :param task_tmpl_id: 任务模板主键ID（必传，不可修改）
        :param update_info: 待更新字段字典，支持：domain/business_type/name/login_interval/is_quit_browser_when_finished/start_node_id
        :return: 操作结果 True/False
        """
        # 1. 安全校验：禁止修改主键ID
        if "id" in update_info:
            raise ValueError("任务模板主键ID不可修改！")
        # 2. 组装更新SQL
        update_fields = []
        params = []
        for field, value in update_info.items():
            update_fields.append(f"{field} = ?")
            params.append(value)

        if update_fields:
            update_fields.append("update_time = datetime('now', 'localtime')")

        # if not update_info.get("project_name"):
        #     update_fields.append("project_name = ?")
        #     # TODO 待完成！
        #     name = ProjectDAO().get_by_id(update_info.get("project_id")).get("name")
        #     params.append(name)
        # 3. 拼接主键条件
        params.append(task_tmpl_id)
        sql = f"UPDATE tb_task_tmpl SET {','.join(update_fields)} WHERE id = ?"
        # 4. 执行更新（自动触发外键校验：start_node_id必须存在）
        with self.get_db_connection() as conn:
            conn.execute(sql, params)
            return True

    def update_task_basic_info(self, task_tmpl_id: str, task_name: str = None, business_type: str = None) -> bool:
        """
        快捷方法：单独更新任务模板名称/业务类型【高频使用】
        :param task_tmpl_id: 任务模板ID
        :param task_name: 新任务模板名称（可选，不传则不更新）
        :param business_type: 新业务类型（可选，不传则不更新）
        :return: 操作结果 True/False
        """
        update_fields = []
        params = []
        if task_name:
            update_fields.append("name = ?")
            params.append(task_name)
        if business_type:
            update_fields.append("business_type = ?")
            params.append(business_type)

        if not update_fields:
            raise ValueError("请传入至少一个待更新字段：task_name / business_type")

        params.append(task_tmpl_id)

        update_fields.append("update_time = datetime('now', 'localtime')")
        sql = f"UPDATE tb_task_tmpl SET {','.join(update_fields)} WHERE id = ?"

        try:
            with self.get_db_connection() as conn:
                conn.execute(sql, params)
            return True
        except:
            self.logger.exception(f"更新任务模板基础信息失败 | 任务模板ID：{task_tmpl_id}")
            return False

    def get_all(self) -> List[Dict[str, Any]]:
        sql = """SELECT t1.*, t2.name as project_name FROM tb_task_tmpl t1 left join tb_project t2 on t1.project_id=t2.id"""
        with self.get_db_connection() as conn:
            rows = conn.execute(sql).fetchall()
            rows_ = [self.dict_from_row(row) for row in rows]
            return rows_
