import math
from typing import Dict, Any, Optional, List, Tuple

from src.frame.common.exceptions import BusinessException
from src.frame.dao.base_db import BaseDB


class DataDictDAO(BaseDB):

    def get_init_sql(self):
        """返回完整的建表/索引/触发器SQL"""
        sql = """
        -- 数据字典主表
        CREATE TABLE IF NOT EXISTS tb_data_dict (    
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            key TEXT NOT NULL,
            value TEXT DEFAULT '',
            name TEXT NOT NULL,
            remark TEXT DEFAULT NULL,
            create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );"""
        return sql.strip()

    def add_one(self, data_dict_info: Dict[str, Any]) -> int | None:
        sql = """INSERT INTO tb_data_dict (key, value, name, remark) VALUES (?, ?, ?, ?)"""
        params = (
        data_dict_info["key"], data_dict_info["value"], data_dict_info["name"], data_dict_info.get("remark", None))
        try:
            with self.get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql, params)
                new_data_dict_id = cursor.lastrowid  # ✅ 获取最新生成的自增ID
            return new_data_dict_id  # ✅ 返回自增主键
        except Exception as e:
            self.logger.error(f"新增数据字典失败：{str(e)}")
            return None

    def update_by_key(self, key: str, value: str):
        if not key:
            raise ValueError("数据字典key不能为空！")
        sql = """UPDATE tb_data_dict SET value = ? WHERE key = ?"""
        try:
            with self.get_db_connection() as conn:
                conn.execute(sql, (value, key))
                return True
        except Exception as e:
            self.logger.error(f"更新数据字典失败：{str(e)}")
            return False

    def update_data_dict(self, data_dict_id: str, update_info: Dict[str, Any]) -> bool:
        """
        通用数据字典更新方法【推荐】：支持更新任意字段（主键id除外）
        :param data_dict_id: 数据字典主键ID（必传，不可修改）
        :param update_info: 待更新字段字典，支持：key/value/name/remark
        :return: 操作结果 True/False
        """
        # 1. 安全校验：禁止修改主键ID
        if "id" in update_info:
            raise ValueError("数据字典主键ID不可修改！")
        # 2. 组装更新SQL
        update_fields = []
        params = []
        for field, value in update_info.items():
            update_fields.append(f"{field} = ?")
            params.append(value)

        # 3. 拼接主键条件
        params.append(data_dict_id)
        sql = f"UPDATE tb_data_dict SET {','.join(update_fields)} WHERE id = ?"
        # 4. 执行更新
        try:
            with self.get_db_connection() as conn:
                conn.execute(sql, params)
                return True
        except Exception as e:
            self.logger.exception(f"更新任务失败 | 任务编号：{data_dict_id}")
            return False

    def get_by_id(self, data_dict_id: str):
        sql = """SELECT * FROM tb_data_dict WHERE id = ?"""
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (data_dict_id,)).fetchone()
            return self.dict_from_row(row)

    def update_by_id(self, project_id: str, update_info: Dict[str, Any]):
        """
        通用项目更新方法【推荐】：支持更新任意字段（主键id除外）
        :param project_id: 项目主键ID（必传，不可修改）
        :param update_info: 待更新字段字典，支持：name/remark
        :return: 操作结果 True/False
        """
        # 1. 安全校验：禁止修改主键ID
        if "id" in update_info:
            raise ValueError("主键ID不可修改！")

        record = self.get_by_id(project_id)
        if not record:
            raise BusinessException("记录不存在！")

        if record.get("key") != update_info.get("key") and self.get_by_key(update_info.get("key")):
            raise BusinessException("该关键字已存在！")

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
        sql = f"UPDATE tb_data_dict SET {','.join(update_fields)} WHERE id = ?"
        # 4. 执行更新
        with self.get_db_connection() as conn:
            conn.execute(sql, params)

    def get_by_key(self, key: str) -> Optional[Dict[str, Any]]:
        sql = "SELECT * FROM tb_data_dict WHERE key = ?"
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (key,)).fetchone()
        return self.dict_from_row(row)

    def get_all(self) -> List[Dict]:
        """
        获取所有的数据
        :return:
        """
        sql = "select * from tb_data_dict"
        with self.get_db_connection() as conn:
            rows = conn.execute(sql).fetchall()
        return [self.dict_from_row(row) for row in rows]

    # ========== ✅ 核心：分页查询3个方法（翻页专用，重点） ==========
    def get_total_count(self, filter_key: Optional[str] = None) -> int:
        """
        获取数据字典总条数（分页必备）
        :param filter_key: 可选筛选条件 - 按字典key模糊匹配，None查全部
        :return: 符合条件的总条数
        """
        sql = "SELECT COUNT(*) AS total FROM tb_data_dict"
        params = []
        # 支持按key模糊筛选（数据字典高频筛选场景）
        if filter_key and filter_key.strip():
            sql += " WHERE `key` LIKE ?"
            params.append(f"%{filter_key.strip()}%")

        with self.get_db_connection() as conn:
            row = conn.execute(sql, params).fetchone()
        return row["total"] if row else 0

    def get_list_by_page(self,
                         page_num: int = 1,
                         page_size: int = 10,
                         filter_key: Optional[str] = None) -> List[Dict]:
        """
        分页查询数据字典列表（底层方法）
        :param page_num: 当前页码，默认1（UI通用，从1开始）
        :param page_size: 每页条数，默认10
        :param filter_key: 按key模糊筛选，None查全部
        :return: 当前页数据列表
        """
        # 边界校验（防异常，生产级必备）
        if page_num < 1:
            page_num = 1
        if page_size < 1 or page_size > 100:  # 限制最大页条数，保护性能
            page_size = 10

        # SQLite分页核心：LIMIT 条数 OFFSET 偏移量（偏移量=(页码-1)*页大小）
        offset = (page_num - 1) * page_size
        sql = "SELECT * FROM tb_data_dict"
        params = []

        # 拼接筛选条件
        if filter_key and filter_key.strip():
            sql += " WHERE `key` LIKE ?"
            params.append(f"%{filter_key.strip()}%")

        # 排序+分页（按创建时间倒序，最新新增的在前）
        sql += " ORDER BY create_time DESC LIMIT ? OFFSET ?"
        params.extend([page_size, offset])

        with self.get_db_connection() as conn:
            rows = conn.execute(sql, params).fetchall()
        return [self.dict_from_row(row) for row in rows]

    def get_page_data(self,
                      page_num: int = 1,
                      page_size: int = 10,
                      filter_key: Optional[str] = None) -> Tuple[List[Dict[str, Any]], int]:
        """
        ✅ 对外统一调用【推荐】- 标准化分页返回（Qt UI直接绑定，无需二次处理）
        :return: 包含分页全量信息的字典，直接给UI使用
        """
        total_count = self.get_total_count(filter_key)
        # total_page = math.ceil(total_count / page_size) if total_count > 0 else 1
        dict_list = self.get_list_by_page(page_num, page_size, filter_key)

        # 标准化返回格式（和TaskDAO完全一致，UI调用零适配成本）
        return dict_list, total_count

    def delete_by_ids(self, data_dict_ids: List[int]):
        with self.get_db_connection() as conn:
            data_dict_ids_placeholders = ','.join(['?'] * len(data_dict_ids))
            sql = """DELETE FROM tb_data_dict WHERE id IN (%s)""" % data_dict_ids_placeholders
            conn.execute(sql, data_dict_ids)