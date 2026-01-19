from typing import List, Tuple, Dict, Callable

from PyQt5.QtWidgets import QMessageBox

from src.frame.base.ui.base_table_widget import BaseTableWidget, EditableField, BaseAsyncImportWorker, TableHeader, \
    QueryField
from src.frame.dao.db_manager import db


class DataDictPage(BaseTableWidget):

    def __init__(self):
        self.dao = db.data_dict_dao
        super().__init__(is_need_search=True)

    def get_headers(self) -> List[TableHeader]:
        return [
            TableHeader('ID', 'id'),
            TableHeader('名称', 'name'),
            TableHeader('关键字', 'key'),
            TableHeader('值', 'value'),
            TableHeader('备注', 'remark'),
            TableHeader('更新时间', 'update_time'),
            TableHeader('创建时间', 'create_time')
        ]

    def get_records(self, condition: dict, page=1, page_size=0) -> Tuple[List[dict], int]:
        if page_size > 0:
            return self.dao.get_page_data(page, page_size, condition.get("key"))
        else:
            records = self.dao.get_all()
            return records, len(records)

    def get_update_callable(self) -> Callable:
        return self.dao.update_by_id

    def get_delete_data_callable(self) -> Callable:
        return self.dao.delete_by_ids

    def get_add_one_callable(self) -> Callable:
        return self.dao.add_one

    def _is_empty(self, val):
        return True if val is None or not str(val).strip() else False

    def validate_new_data(self, data):
        # 示例：验证必填字段
        if (self._is_empty(data.get('key')) or self._is_empty(data.get('name')) or self._is_empty(data.get('value'))):
            QMessageBox.warning(self, "验证错误", "必要字段不能为空！")
            return False
        return True

    def batch_insert(self, data_list: List[Dict]):
        # 批量插入数据，没开通
        pass

    def get_add_field_attributes(self, field_name: str):
        return [
            EditableField("update_time", "hide"),
            EditableField("create_time", "hide"), ]

    def get_edit_field_attributes(self, field_name: str):
        return [
            EditableField("update_time", "readonly"),
            EditableField("create_time", "readonly"), ]

    def validate_import_data(self, data):
        # 验证导入数据的有效性
        # return bool(data.get('product_name'))
        return True

    def create_bulk_importer(self) -> BaseAsyncImportWorker:
        pass
        # return AsyncImportWorker(self)

    def delete_all(self) -> Tuple[bool, str]:
        pass

    def get_query_fields(self) -> List[QueryField]:
        return [QueryField('text', '关键字', 'key')]
