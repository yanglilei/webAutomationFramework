from typing import Dict, Optional, Any, List, Tuple

from src.frame.common.decorator.singleton import singleton
from src.frame.common.exceptions import BusinessException
from src.frame.dao.base_db import BaseDB


@singleton
class ActionDAO(BaseDB):
    """tb_action 表专属操作类"""

    def get_init_sql(self) -> str:
        """返回完整的建表/索引/触发器SQL"""
        sql = """
CREATE TABLE IF NOT EXISTS tb_action (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_ids TEXT NOT NULL,  -- tb_task_batch表的ID，逗号分割，例如：1,2,3,4
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
        return sql.strip()

    def add_one(self, action: Dict[str, Any]) -> int:
        sql = """INSERT INTO tb_action (batch_ids) VALUES (?)"""
        params = (action.get("batch_ids"),)
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.lastrowid

    def get_by_id(self, action_id: int) -> Optional[Dict[str, Any]]:
        """根据主键ID获取记录"""
        sql = "SELECT * FROM tb_action WHERE id = ?"
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (action_id,)).fetchone()
            node = self.dict_from_row(row)
        return node

    def get_total_count(self, batch_no: Optional[str] = None, project_id: Optional[int] = None) -> int:
        """
        获取任务批次总条数
        :param batch_no: 可选，按批次号筛选，支持全模糊查询，None则查全部
        :param project_id: 可选，按项目ID筛选，None则查全部
        """
        sql = "SELECT COUNT(*) AS total FROM tb_action"
        where_criteria, params = self.create_query_criteria(batch_no, project_id)
        sql += where_criteria
        with self.get_db_connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return row["total"] if row else 0

    def create_query_criteria(self, batch_no: Optional[str] = None, project_id: Optional[int] = None) -> Tuple[
        str, List[Any]]:
        """
        创建查询条件
        :param batch_no: 可选，按批次号筛选，支持全模糊查询，None则查全部
        :param project_id: 可选，按项目ID筛选，None则查全部
        :return: Tuple[str, List[Any]] (where子句, 查询参数列表)
        """
        where_conditions = []
        params = []
        # 拼接筛选条件
        if batch_no and batch_no.strip():
            where_conditions.append("batch_no LIKE ?")
            params.append(f"%{batch_no.strip()}%")
        if project_id is not None:
            where_conditions.append("project_id=?")
            params.append(f"%{project_id}%")

        sql = ""
        if where_conditions:
            sql += " WHERE " + " ".join(where_conditions)

        return sql, params

    def get_list_by_page(self,
                         page_num: int = 1,
                         page_size: int = 10,
                         batch_no: Optional[str] = None,
                         project_id: Optional[int] = None) -> List[Dict]:
        """
        分页查询任务批次列表（核心翻页方法）
        :param page_num: 当前页码，默认1（前端UI通用规则，从1开始）
        :param page_size: 每页条数，默认10
        :param batch_no: 可选，按批次号筛选，支持全模糊查询，None则查全部
        :param project_id: 可选，按项目ID筛选，None则查全部
        :return: 当前页任务数据列表
        """
        # 边界值校验（防异常）
        if page_num < 1: page_num = 1
        if page_size < 1 or page_size > 100: page_size = 10  # 限制最大页条数，防性能问题
        # SQLite分页核心语法：LIMIT 条数 OFFSET 偏移量（偏移量=(页码-1)*页大小）
        offset = (page_num - 1) * page_size

        sql = "SELECT * FROM tb_action"
        where_criteria, params = self.create_query_criteria(batch_no, project_id)
        sql += where_criteria

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
                      batch_no: Optional[str] = None,
                      project_id: Optional[int] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        ✅ 对外统一调用【推荐】- 标准化分页数据返回（Qt UI直接绑定）
        :return: 包含总条数、总页数、分页参数、数据的完整字典
        """
        total_count = self.get_total_count(batch_no, project_id)  # 总条数
        # total_page = math.ceil(total_count / page_size) if total_count > 0 else 1  # 总页数
        task_list = self.get_list_by_page(page_num, page_size, batch_no, project_id)  # 当前页数据
        return task_list, total_count
        # 标准化返回格式（UI端无需二次处理，直接取值）
        # return {
        #     "page_num": page_num,  # 当前页码
        #     "page_size": page_size,  # 每页条数
        #     "total_count": total_count,  # 数据总条数
        #     "total_page": total_page,  # 总页数
        #     "has_next": page_num < total_page,  # 是否有下一页
        #     "has_prev": page_num > 1,  # 是否有上一页
        #     "data": task_list  # 当前页任务数据列表
        # }

    def get_all(self) -> List[Dict[str, Any]]:
        sql = """SELECT * FROM tb_action"""
        with self.get_db_connection() as conn:
            rows = conn.execute(sql).fetchall()
            rows_ = [self.dict_from_row(row) for row in rows]
            return rows_

    def delete_by_ids(self, batch_ids: List[int]):
        with self.get_db_connection() as conn:
            batch_ids_placeholders = ','.join(['?'] * len(batch_ids))
            sql = """DELETE FROM tb_action WHERE id IN (%s)""" % batch_ids_placeholders
            conn.execute(sql, batch_ids)
