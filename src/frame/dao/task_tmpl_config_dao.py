from typing import Dict, Any

from src.frame.dao.base_db import BaseDB


class TaskTmplConfigDAO(BaseDB):
    """tb_task_tmpl_config 表专属操作类"""

    def get_init_sql(self):
        sql = """
        -- 任务模板全局配置表
CREATE TABLE IF NOT EXISTS tb_task_tmpl_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_tmpl_id INTEGER NOT NULL,
    task_tmpl_global_config_json TEXT NOT NULL DEFAULT '{}',
    create_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    update_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (task_tmpl_id) REFERENCES tb_task_tmpl(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_tb_task_tmpl_config_task_tmpl_id ON tb_task_tmpl_config(task_tmpl_id);"""
        return sql.strip()

    def save_task_tmpl_config(self, task_tmpl_id: int, config_dict: Dict[str, Any]) -> bool:
        sql = """INSERT OR REPLACE INTO tb_task_tmpl_config (task_tmpl_id, task_tmpl_global_config_json)
                 VALUES (?, ?)"""
        with self.get_db_connection() as conn:
            conn.execute(sql, (task_tmpl_id, self.json_serialize(config_dict)))
        return True

    def get_by_task_tmpl_id(self, task_tmpl_id: int) -> Dict[str, Any]:
        sql = "SELECT task_tmpl_global_config_json FROM tb_task_tmpl_config WHERE task_tmpl_id = ?"
        with self.get_db_connection() as conn:
            row = conn.execute(sql, (task_tmpl_id,)).fetchone()
        return self.json_deserialize(row["task_tmpl_global_config_json"]) if row else {}

    def get_single_task_tmpl_config(self, task_tmpl_id: int, config_key: str) -> Dict[str, Any]:
        return self.get_by_task_tmpl_id(task_tmpl_id).get(config_key, {})

    def update_task_tmpl_config(self, task_tmpl_id: int, new_config: Dict[str, Any], is_cover: bool = False) -> bool:
        """
        【通用更新】更新任务模板全局配置（推荐）
        :param task_tmpl_id: 任务模板ID（主键）
        :param new_config: 待更新的配置字典（可全量/可局部）
        :param is_cover: 是否全量覆盖（False=局部合并【默认】，True=全量替换）
        :return: 操作结果 True/False
        """
        # 安全校验：禁止传入task_tmpl_id试图修改主键
        if "task_tmpl_id" in new_config:
            raise ValueError("任务模板配置主键task_tmpl_id不可修改！")

        # 两种更新模式：局部合并 / 全量覆盖
        if is_cover:
            # 模式1：全量覆盖 → 直接调用原有方法即可
            return self.save_task_tmpl_config(task_tmpl_id, new_config)
        else:
            # 模式2：局部合并【默认】→ 原有配置 + 新配置覆盖（新增配置项自动追加）
            old_config = self.get_by_task_tmpl_id(task_tmpl_id)
            merge_config = {**old_config, **new_config}  # 新配置优先级更高，覆盖原有同键配置
            return self.save_task_tmpl_config(task_tmpl_id, merge_config)

    def update_single_config_item(self, task_tmpl_id: int, config_key: str, item_value: Dict | str) -> bool:
        """
        【快捷更新】单独更新某一个配置项（高频使用，无需传全量配置）
        :param task_tmpl_id: 任务模板ID
        :param config_key: 单个配置项键名（如relogin_config/proxy_config/log_config）
        :param item_value: 配置项对应的值（字典格式）
        :return: 操作结果 True/False
        """
        # 读取原有配置 → 单独更新指定项 → 重新保存
        old_config = self.get_by_task_tmpl_id(task_tmpl_id)
        old_config[config_key] = item_value  # 追加/覆盖单个配置项
        return self.save_task_tmpl_config(task_tmpl_id, old_config)

    # ========== ✅ 新增：标准删除方法（完整CRUD必备） ==========
    def delete_task_tmpl_config(self, task_tmpl_id: str) -> bool:
        """
        删除指定任务模板的全局配置
        ✅ 备注：删除tb_task_tmpl任务模板时，会触发外键级联删除此表数据；此方法用于手动单独删除
        """
        sql = "DELETE FROM tb_task_tmpl_config WHERE task_tmpl_id = ?"
        try:
            with self.get_db_connection() as conn:
                conn.execute(sql, (task_tmpl_id,))
            return True
        except:
            self.logger.exception(f"删除任务模板全局配置失败 | 任务模板ID：{task_tmpl_id}")
            return False
