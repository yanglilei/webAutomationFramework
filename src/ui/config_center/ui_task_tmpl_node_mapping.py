import json
from typing import List, Tuple, Dict, Callable

from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import QWidget, QPushButton, QMessageBox

from src.frame.base.ui.base_table_widget import BaseTableWidget, EditableField, BaseAsyncImportWorker, TableHeader
from src.frame.dao.db_manager import db


class UITaskNodeMapping(BaseTableWidget):
    def __init__(self, task_tmpl_id: int, start_node_id: int):
        self.node_dao = db.node_dao
        self.task_tmpl_id = task_tmpl_id  # 任务模板ID
        self.start_node_id = start_node_id  # 起始节点ID
        self.task_node_mapping_dao = db.task_tmpl_node_mapping_dao  # 任务节点映射dao
        self.task_dao = db.task_tmpl_dao  # 任务dao
        self.start_node_background_color = QColor(255, 220, 220)
        super().__init__(is_support_import=False, is_need_search=False,
                         is_support_add=False, is_support_clear_all=False)

    def get_headers(self) -> List[TableHeader]:
        return [
            TableHeader('记录ID', 'id'),
            TableHeader('节点ID', 'node_id'),
            TableHeader('下一个节点ID', 'next_node_id'),
            TableHeader('上一个节点ID', 'pre_node_id'),
            TableHeader('节点名称', 'name'),
            TableHeader('任务参数', 'bind_node_params'),
            TableHeader('节点参数', 'native_node_params')
        ]

    def get_edit_metadata(self) -> dict:
        return {"bind_node_params": EditableField("bind_node_params", "textedit"),
                "native_node_params": EditableField("native_node_params", "textedit")
                }

    def after_first_render_table(self, payloads):
        """
        初次渲染表格成功后的回调
        :return:
        """
        # 定位行
        if self.start_node_id:
            record = self.task_node_mapping_dao.get_by_task_tmpl_id_and_node_id(self.task_tmpl_id, self.start_node_id)
            if record:
                for row in range(self.table.rowCount()):
                    if int(self.table.item(row, 1).text()) == record.get("id"):
                        self.set_row_background(row, self.start_node_background_color)
                        break

    def get_records(self, condition: dict, page=1, page_size=0) -> Tuple[List[dict], int]:
        nodes = self.node_dao.get_by_task_tmpl_id(self.task_tmpl_id)
        for node in nodes:
            node["bind_node_params"] = json.dumps(node.get("bind_node_params"), ensure_ascii=False)
            node["native_node_params"] = json.dumps(node.get("native_node_params"), ensure_ascii=False)
        return nodes, len(nodes)

    def get_add_one_callable(self) -> Callable:
        pass

    def get_update_callable(self) -> Callable:
        return self.task_node_mapping_dao.update_by_id

    def get_delete_data_callable(self) -> Callable:
        return self.task_node_mapping_dao.delete_by_ids

    def _is_empty(self, val):
        return True if val is None or not str(val).strip() else False

    def add_widget_to_toolbar(self) -> List[QWidget]:
        btn_save = QPushButton("设置起始节点")
        btn_save.clicked.connect(self.set_start_node)
        return [btn_save]

    def set_start_node(self):
        if not self.selected_rows or len(self.selected_rows) != 1:
            QMessageBox.warning(self, "提示", "请仅选择一个起始节点！")
        else:
            # 清空所有背景色
            self.clean_all_background()
            # 更新数据库
            try:
                status = self.task_dao.update_start_node_id(self.task_tmpl_id,
                                                            int(self.get_selected_rows()[0].get("node_id")))
                if status:
                    rows_ = list(self.selected_rows)[0]
                    self.set_row_background(rows_, color=self.start_node_background_color)
                    QMessageBox.information(self, "提示", "设置起始节点成功！")
                else:
                    QMessageBox.warning(self, "提示", "设置起始节点失败！")
            except Exception as e:
                QMessageBox.error(self, "提示", f"设置起始节点失败：{str(e)}")
        # self.task_tmpl_node_mapping_dao.set_start_node(self.task_tmpl_id, self.get_selected_rows()[0].get("id"))

    def validate_new_data(self, data):
        # 示例：验证必填字段
        # if (self._is_empty(data.get('name')) or self._is_empty(data.get('component_path'))
        #         or self._is_empty(data.get('code')) or self._is_empty(
        #             data.get('type'))):
        #     QMessageBox.warning(self, "验证错误", "必要字段不能为空！")
        #     return False
        return True

    def batch_insert(self, data_list: List[Dict]):
        # 批量插入数据，没开通
        pass

    def get_edit_field_attributes(self, field_name: str):
        return [
            EditableField("node_id", "readonly"),
            EditableField("name", "readonly"),
            EditableField("name", "readonly"),
            EditableField("native_node_params", "readonly"),
            EditableField("bind_node_params", "textedit"),
            EditableField("update_time", "readonly"),
            EditableField("create_time", "readonly"), ]

    def validate_import_data(self, data):
        # 验证导入数据的有效性
        # return bool(data.get('product_name'))
        return True

    def create_bulk_importer(self) -> BaseAsyncImportWorker:
        pass

    def delete_all(self):
        pass
