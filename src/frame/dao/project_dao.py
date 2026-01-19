from typing import Dict, Optional, Any, List, Tuple

from src.frame.common.decorator.singleton import singleton
from src.frame.common.exceptions import BusinessException
from src.frame.dao.base_db import BaseDB
from src.frame.dao.task_tmpl_dao import TaskTmplDAO


@singleton
class ProjectDAO(BaseDB):
    """tb_project 表专属操作类"""

    def get_init_sql(self) -> str:
        """返回完整的建表/索引/触发器SQL"""
        sql = """
CREATE TABLE IF NOT EXISTS tb_project (
    id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 数据库自增主键（内部关联用）
    name TEXT NOT NULL,
    remark TEXT DEFAULT '',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
        return sql.strip()

    def add_one(self, project_info: Dict[str, Any]) -> int | None:
        if not project_info.get("name") or not project_info.get("name").strip():
            raise BusinessException("请填写项目名称！")
        if self.get_by_name(project_info["name"]):
            raise BusinessException("该项目已存在！")

        sql = """INSERT INTO tb_project (name, remark) VALUES (?, ?)"""
        params = (project_info["name"], project_info["remark"])
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                new_project_id = cursor.lastrowid
            return new_project_id
        except:
            self.logger.exception(f"新增项目失败 | 项目名称：{project_info['name']}")
            return None

    def get_by_name(self, project_name: str) -> Optional[Dict[str, Any]]:
        sql = """SELECT * FROM tb_project WHERE name = ?"""
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (project_name,)).fetchone()
            node = self.dict_from_row(row)
        return node

    def get_by_id(self, project_id: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM tb_project WHERE id = ?"
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (project_id,)).fetchone()
            node = self.dict_from_row(row)
        return node

    def delete_one(self, project_id: int) -> bool:
        """删除项目时，先检查该项目是否被任务引用，如果被引用则不允许删除"""
        if any([len(row) != 0 for row in TaskTmplDAO().get_by_project_id(project_id)]):
            self.logger.error(f"删除项目失败 | 项目ID：{project_id} 正在被任务引用，请先解除引用关系")
            return False

        sql = """DELETE FROM tb_project WHERE id = ?"""
        try:
            with self.get_db_connection() as conn:
                conn.execute(sql, (project_id,))
            return True
        except:
            self.logger.exception(f"删除项目失败 | 项目ID：{project_id}")
            return False

    def update_by_id(self, project_id: str, update_info: Dict[str, Any]):
        """
        通用项目更新方法【推荐】：支持更新任意字段（主键id除外）
        :param project_id: 项目主键ID（必传，不可修改）
        :param update_info: 待更新字段字典，支持：name/remark
        :return: 操作结果 True/False
        """
        # 1. 安全校验：禁止修改主键ID
        if "id" in update_info:
            raise ValueError("项目主键ID不可修改！")

        record = self.get_by_id(project_id)
        if not record:
            raise BusinessException("项目不存在！")

        if record.get("name") != update_info.get("name") and self.get_by_name(update_info.get("name")):
            raise BusinessException("该项目已存在！")

        # 2. 过滤空字段，组装更新SQL
        update_fields = []
        params = []
        for field, value in update_info.items():
            update_fields.append(f"{field} = ?")
            params.append(value)

        if update_fields:
            update_fields.append("update_time = datetime('now', 'localtime')")
        # 3. 拼接主键条件
        params.append(project_id)
        sql = f"UPDATE tb_project SET {','.join(update_fields)} WHERE id = ?"
        # 4. 执行更新
        with self.get_db_connection() as conn:
            conn.execute(sql, params)

    def get_total_count(self, name: Optional[str] = None) -> int:
        """获取项目总条数（支持按名称模糊筛选，分页必备）"""
        sql = "SELECT COUNT(*) AS total FROM tb_project"
        params = []
        where_conditions = []  # 条件集合，自动拼接

        # 条件1：新增任务名称模糊筛选（核心优化）
        if name and name.strip():
            where_conditions.append("name LIKE ?")
            params.append(f"%{name.strip()}%")

        # 拼接多条件（多个条件用AND连接，无则不拼接）
        if where_conditions:
            sql += " WHERE " + " ".join(where_conditions)

        with self.get_db_connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return row["total"] if row else 0

    def get_list_by_page(self,
                         page_num: int = 1,
                         page_size: int = 10,
                         name: Optional[str] = None) -> List[Dict]:
        """
        分页查询项目列表（核心翻页方法）
        :param page_num: 当前页码，默认1（前端UI通用规则，从1开始）
        :param page_size: 每页条数，默认10
        :param name: 可选，按任务名称筛选，支持全模糊查询，None则查全部
        :return: 当前页任务数据列表
        """
        # 边界值校验（防异常）
        if page_num < 1: page_num = 1
        if page_size < 1 or page_size > 100: page_size = 10  # 限制最大页条数，防性能问题

        # SQLite分页核心语法：LIMIT 条数 OFFSET 偏移量（偏移量=(页码-1)*页大小）
        offset = (page_num - 1) * page_size
        sql = "SELECT * FROM tb_project"
        params = []
        where_conditions = []

        # 拼接筛选条件
        if name and name.strip():
            where_conditions.append("name LIKE ?")
            params.append(f"%{name.strip()}%")

        if where_conditions:
            sql += " WHERE " + " ".join(where_conditions)
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
                      name: Optional[str] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        ✅ 对外统一调用【推荐】- 标准化分页数据返回（Qt UI直接绑定）
        :return: 包含总条数、总页数、分页参数、数据的完整字典
        """
        total_count = self.get_total_count(name)  # 总条数
        # total_page = math.ceil(total_count / page_size) if total_count > 0 else 1  # 总页数
        task_list = self.get_list_by_page(page_num, page_size, name)  # 当前页数据
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
        sql = """SELECT * FROM tb_project"""
        with self.get_db_connection() as conn:
            rows = conn.execute(sql).fetchall()
            rows_ = [self.dict_from_row(row) for row in rows]
            return rows_

    def delete_by_ids(self, project_ids: List[int]):
        with self.get_db_connection() as conn:
            project_ids_placeholders = ','.join(['?'] * len(project_ids))
            sql = """select * from tb_task_tmpl where project_id in (%s)""" % project_ids_placeholders
            rows = conn.execute(sql, project_ids).fetchall()
            task_list = [self.dict_from_row(row) for row in rows]
            if any([len(task)>0 for task in task_list]):
                raise BusinessException(f"项目ID：{project_ids} 正在被任务引用，请先解除引用关系")
            sql = """DELETE FROM tb_project WHERE id IN (%s)""" % project_ids_placeholders
            conn.execute(sql, project_ids)