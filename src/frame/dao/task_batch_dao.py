from typing import Dict, Optional, Any, List, Tuple

from src.frame.common.decorator.singleton import singleton
from src.frame.common.exceptions import BusinessException
from src.frame.dao.base_db import BaseDB


@singleton
class TaskBatchDAO(BaseDB):
    """tb_task_batch 表专属操作类"""

    def get_init_sql(self) -> str:
        """返回完整的建表/索引/触发器SQL"""
        sql = """
CREATE TABLE IF NOT EXISTS tb_task_batch (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_tmpl_id INTEGER NOT NULL,  -- 关联tb_task_tmpl的主键ID
    task_tmpl_name TEXT NOT NULL,  -- 任务模板名
    business_type TEXT NOT NULL,  -- 业务类型
    project_id INTEGER NOT NULL,
    project_name TEXT NOT NULL,
    user_info TEXT NOT NULL,  -- 用户信息，json格式，格式：{"type": 1, "workbook_addr": "", "sheet_name": "", "username_start_cell":"", "username_end_cell": "", "password_start_cell": "", "password_end_cell": ""} type=1-表格存储；{"type": 2, "username": "", "password": ""} type=2-文本存储
    priority INTEGER NOT NULL DEFAULT 5,  -- 批次优先级：1-最高，10-最低
    queue_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,  -- 加入批次队列的时间
    execute_status INTEGER NOT NULL DEFAULT 0,  -- 批次状态：0-待运行 1-运行中 2-已结束 3-已取消
    run_mode INTEGER NOT NULL DEFAULT 1,  -- 批次状态：1-全自动 2-半自动
    user_mode INTEGER NOT NULL DEFAULT 1,  -- 用户模式：0-无用户 1-表格 2-文本
    global_config Text,  -- 全局配置
    batch_no VARCHAR(50) NOT NULL UNIQUE,  -- 唯一批次号（如B20260111001）
    action_id INTEGER,  -- 动作ID，用于标识是不是同时运行的，非常重要
    total_user INTEGER,  -- 该批次总用户数
    success_user INTEGER,  -- 执行成功的用户数
    fail_user INTEGER,  -- 执行失败的用户数
    remark TEXT DEFAULT '',  -- 备注信息
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_tmpl_id) REFERENCES tb_task_tmpl(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tb_task_batch_tmpl_id ON tb_task_batch(task_tmpl_id);
CREATE INDEX IF NOT EXISTS idx_tb_task_batch_batch_no ON tb_task_batch(batch_no);
CREATE INDEX IF NOT EXISTS idx_tb_task_batch_status ON tb_task_batch(execute_status);
"""
        return sql.strip()

    def add_one(self, task_batch: Dict[str, Any]) -> int:
        if self.get_by_batch_no(task_batch["batch_no"]):
            raise BusinessException("该任务批次已存在！")

        sql = """INSERT INTO tb_task_batch (task_tmpl_id, task_tmpl_name, business_type, project_id, project_name, user_info, priority, 
        queue_time, execute_status, user_mode, run_mode, batch_no, global_config, total_user, success_user, fail_user) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        params = (task_batch.get("task_tmpl_id"), task_batch.get("task_tmpl_name"),
                  task_batch.get("business_type"),
                  task_batch.get("project_id"), task_batch.get("project_name"),
                  task_batch.get("user_info"),
                  task_batch.get("priority"), task_batch.get("queue_time"), task_batch.get("execute_status"),
                  task_batch.get("user_mode"), task_batch.get("run_mode"),
                  task_batch.get("batch_no"), task_batch.get("global_config"), task_batch.get("total_user"),
                  task_batch.get("success_user"), task_batch.get("fail_user"))
        with self.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.lastrowid

    def batch_add(self, task_batches: List[Dict[str, Any]]):
        sql = """INSERT INTO tb_task_batch (task_tmpl_id, task_tmpl_name, business_type, project_id, project_name, user_info, priority, 
        queue_time, execute_status, user_mode, run_mode, batch_no, global_config, total_user, success_user, fail_user) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"""
        data_tuples = []
        for task_batch in task_batches:
            data_tuple = (task_batch.get("task_tmpl_id"), task_batch.get("task_tmpl_name"),
                          task_batch.get("business_type"), task_batch.get("project_id"), task_batch.get("project_name"),
                          task_batch.get("user_info"),
                          task_batch.get("priority"), task_batch.get("queue_time"), task_batch.get("execute_status"),
                          task_batch.get("user_mode"), task_batch.get("run_mode"),
                          task_batch.get("batch_no"), task_batch.get("global_config"), task_batch.get("total_user"),
                          task_batch.get("success_user"), task_batch.get("fail_user"))
            data_tuples.append(data_tuple)

        with self.get_db_connection() as conn:
            conn.cursor().executemany(sql, data_tuples)

    def get_by_batch_no(self, batch_no: str) -> Optional[Dict[str, Any]]:
        sql = """SELECT * FROM tb_task_batch WHERE batch_no = ?"""
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (batch_no,)).fetchone()
            row_ = self.dict_from_row(row)
            if row_:
                row_["user_info"] = self.json_deserialize(row_["user_info"])
                row_["global_config"] = self.json_deserialize(row_["global_config"])
        return row_

    def get_by_batch_nos(self, batch_nos: List[str]) -> List[Dict[str, Any]]:
        """根据批次号列表批量获取记录"""
        sql = "SELECT * FROM tb_task_batch WHERE batch_no IN ({})".format(", ".join(["?"] * len(batch_nos)))
        with self.get_db_connection() as conn:
            rows = conn.execute(sql, batch_nos).fetchall()
            rows_ = [self.dict_from_row(row) for row in rows]
            for row in rows_:
                row["user_info"] = self.json_deserialize(row["user_info"])
                row["global_config"] = self.json_deserialize(row["global_config"])
        return rows_

    def get_by_id(self, batch_id: str) -> Optional[Dict[str, Any]]:
        """根据主键ID获取记录"""
        sql = "SELECT * FROM tb_task_batch WHERE id = ?"
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (batch_id,)).fetchone()
            row_ = self.dict_from_row(row)
            if row_:
                row_["user_info"] = self.json_deserialize(row_["user_info"])
                row_["global_config"] = self.json_deserialize(row_["global_config"])
        return row_

    def get_by_ids(self, batch_ids: List[str]) -> List[Dict[str, Any]]:
        """根据主键ID列表批量获取记录"""
        sql = "SELECT * FROM tb_task_batch WHERE id IN ({})".format(", ".join(["?"] * len(batch_ids)))
        with self.get_db_connection() as conn:
            rows = conn.execute(sql, batch_ids).fetchall()
            rows_ = [self.dict_from_row(row) for row in rows]
            for row in rows_:
                row["user_info"] = self.json_deserialize(row["user_info"])
                row["global_config"] = self.json_deserialize(row["global_config"])
        return rows_

    def delete_one(self, batch_id: int) -> bool:
        """删除任务批次"""
        sql = """DELETE FROM tb_task_batch WHERE id = ?"""
        try:
            with self.get_db_connection() as conn:
                conn.execute(sql, (batch_id,))
            return True
        except:
            self.logger.exception(f"删除任务批次失败 | 任务批次ID：{batch_id}")
            return False

    def update_by_id(self, batch_id: str, update_info: Dict[str, Any]):
        """
        通用任务批次更新方法【推荐】：支持更新任意字段（主键id除外）
        :param batch_id: 任务批次主键ID（必传，不可修改）
        :param update_info: 待更新字段字典
        :return: 操作结果 True/False
        """
        # 1. 安全校验：禁止修改主键ID
        if "id" in update_info:
            raise ValueError("任务批次主键ID不可修改！")

        record = self.get_by_id(batch_id)
        if not record:
            raise BusinessException("任务批次不存在！")

        # if record.get("batch_no") != update_info.get("batch_no") and self.get_by_batch_no(update_info.get("batch_no")):
        #     raise BusinessException("该任务批次已存在！")

        # 2. 过滤空字段，组装更新SQL
        update_fields = []
        params = []
        for field, value in update_info.items():
            if field == "batch_no":
                # 批次号不可修改
                continue
            update_fields.append(f"{field} = ?")
            params.append(value)
        if update_fields:
            update_fields.append("update_time = datetime('now', 'localtime')")
        # 3. 拼接主键条件
        params.append(batch_id)
        sql = f"UPDATE tb_task_batch SET {','.join(update_fields)} WHERE id = ?"
        # 4. 执行更新
        with self.get_db_connection() as conn:
            conn.execute(sql, params)

    def update_by_batch_no(self, batch_no: str, update_info: Dict[str, Any]):
        """
        通用任务批次更新方法【推荐】：支持更新任意字段（主键id除外）
        :param batch_no: 任务批次号（必传，不可修改）
        :param update_info: 待更新字段字典
        :return: 操作结果 True/False
        """
        # 1. 安全校验：禁止修改主键ID
        if "id" in update_info:
            update_info.pop("id")
        if "batch_no" in update_info:
            update_info.pop("batch_no")

        record = self.get_by_batch_no(batch_no)
        if not record:
            raise BusinessException("任务批次不存在！")

        # 2. 过滤空字段，组装更新SQL
        update_fields = []
        params = []
        for field, value in update_info.items():
            update_fields.append(f"{field} = ?")
            params.append(value)
        if update_fields:
            update_fields.append("update_time = datetime('now', 'localtime')")
        # 3. 拼接主键条件
        params.append(batch_no)
        sql = f"UPDATE tb_task_batch SET {','.join(update_fields)} WHERE batch_no = ?"
        # 4. 执行更新
        with self.get_db_connection() as conn:
            conn.execute(sql, params)

    def update_status(self, batch_no: str, execute_status: int):
        """更新任务批次状态"""
        sql = """UPDATE tb_task_batch SET execute_status = ?, update_time = datetime('now', 'localtime') WHERE batch_no = ?"""
        with self.get_db_connection() as conn:
            conn.execute(sql, (execute_status, batch_no))

    def update_action_id(self, batch_ids: List[int], action_id: int):
        """更新任务批次的动作ID"""
        batch_ids_placeholders = ','.join(['?'] * len(batch_ids))
        sql = """UPDATE tb_task_batch SET action_id = ?, update_time = datetime('now', 'localtime') WHERE id in(%s)""" % batch_ids_placeholders
        with self.get_db_connection() as conn:
            conn.execute(sql, (action_id, batch_ids))

    def get_total_count(self, batch_no: Optional[str] = None, project_name: Optional[str] = None,
                        project_id: Optional[int] = None, run_mode: Optional[int] = None) -> int:
        """
        获取任务批次总条数
        :param batch_no: 可选，按批次号筛选，支持全模糊查询，None则查全部
        :param project_name: 可选，按项目名称筛选，支持模糊查询，None则查全部
        :param project_id: 可选，按项目ID筛选，None则查全部
        :param run_mode: 可选，运行模式，None则查全部
        """
        sql = "SELECT COUNT(*) AS total FROM tb_task_batch"
        where_criteria, params = self.create_query_criteria(batch_no, project_name, project_id, run_mode)
        sql += where_criteria
        with self.get_db_connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return row["total"] if row else 0

    def create_query_criteria(self, batch_no: Optional[str] = None, project_name: Optional[str] = None,
                              project_id: Optional[int] = None, run_mode: Optional[int] = None) -> Tuple[
        str, List[Any]]:
        """
        创建查询条件
        :param batch_no: 可选，按批次号筛选，支持全模糊查询，None则查全部
        :param project_name: 可选，按项目名称筛选，支持全模糊查询，None则查全部
        :param project_id: 可选，按项目ID筛选，None则查全部
        :param run_mode: 可选，运行模式，None则查全部
        :return: Tuple[str, List[Any]] (where子句, 查询参数列表)
        """
        where_conditions = []
        params = []
        # 拼接筛选条件
        if batch_no and batch_no.strip():
            where_conditions.append("batch_no LIKE ?")
            params.append(f"%{batch_no.strip()}%")
        if project_name and project_name.strip():
            where_conditions.append("project_name LIKE ?")
            params.append(f"%{project_name.strip()}%")
        if project_id is not None:
            where_conditions.append("project_id=?")
            params.append(f"%{project_id}%")
        if run_mode is not None:
            where_conditions.append("run_mode=?")
            params.append(f"{run_mode}")

        sql = ""
        if where_conditions:
            sql += " WHERE " + " ".join(where_conditions)

        return sql, params

    def get_list_by_page(self,
                         page_num: int = 1,
                         page_size: int = 10,
                         batch_no: Optional[str] = None,
                         project_name: Optional[str] = None,
                         project_id: Optional[int] = None,
                         run_mode: Optional[int] = None) -> List[Dict]:
        """
        分页查询任务批次列表（核心翻页方法）
        :param page_num: 当前页码，默认1（前端UI通用规则，从1开始）
        :param page_size: 每页条数，默认10
        :param batch_no: 可选，按批次号筛选，支持全模糊查询，None则查全部
        :param project_name: 可选，按项目名称筛选，支持模糊查询，None则查全部
        :param project_id: 可选，按项目ID筛选，None则查全部
        :param run_mode: 可选，运行模式，None则查全部
        :return: 当前页任务数据列表
        """
        # 边界值校验（防异常）
        if page_num < 1: page_num = 1
        if page_size < 1 or page_size > 100: page_size = 10  # 限制最大页条数，防性能问题
        # SQLite分页核心语法：LIMIT 条数 OFFSET 偏移量（偏移量=(页码-1)*页大小）
        offset = (page_num - 1) * page_size

        sql = "SELECT * FROM tb_task_batch"
        where_criteria, params = self.create_query_criteria(batch_no, project_name, project_id, run_mode)
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
                      project_name: Optional[str] = None,
                      project_id: Optional[int] = None,
                      run_mode: Optional[int] = None
                      ) -> Tuple[List[Dict[str, Any]], int]:
        """
        ✅ 对外统一调用【推荐】- 标准化分页数据返回（Qt UI直接绑定）
        :param page_num: 当前页码，默认1（前端UI通用规则，从1开始）
        :param page_size: 每页条数，默认10
        :param batch_no: 可选，按批次号筛选，支持全模糊查询，None则查全部
        :param project_name: 可选，按项目名称筛选，支持模糊查询，None则查全部
        :param project_id: 可选，按项目ID筛选，None则查全部
        :param run_mode: 可选，运行模式，None则查全部
        :return: 包含总条数、总页数、分页参数、数据的完整字典
        """
        total_count = self.get_total_count(batch_no, project_name, project_id, run_mode)  # 总条数
        # total_page = math.ceil(total_count / page_size) if total_count > 0 else 1  # 总页数
        task_list = self.get_list_by_page(page_num, page_size, batch_no, project_name, project_id, run_mode)  # 当前页数据
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
        sql = """SELECT * FROM tb_task_batch"""
        with self.get_db_connection() as conn:
            rows = conn.execute(sql).fetchall()
            rows_ = [self.dict_from_row(row) for row in rows]
            for row in rows_:
                row["user_info"] = self.json_deserialize(row["user_info"])
                row["global_config"] = self.json_deserialize(row["global_config"])
            return rows_

    def delete_by_ids(self, batch_ids: List[int]):
        with self.get_db_connection() as conn:
            batch_ids_placeholders = ','.join(['?'] * len(batch_ids))
            sql = """DELETE FROM tb_task_batch WHERE id IN (%s)""" % batch_ids_placeholders
            conn.execute(sql, batch_ids)
