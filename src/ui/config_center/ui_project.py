from typing import List, Tuple, Dict, Callable

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QLabel

from src.frame.base.ui.base_table_widget import BaseTableWidget, EditableField, BaseAsyncImportWorker, TableHeader, \
    QueryField
from src.frame.dao.db_manager import db


class ProjectPage(BaseTableWidget):
    # 数据更新成功信号
    data_changed_signal = pyqtSignal(list)
    # 类属性：记录方法调用次数
    method_call_count = {}

    def __init__(self):
        self.dao = db.project_dao
        super().__init__(is_need_search=True)

    def get_headers(self) -> List[TableHeader]:
        return [
            TableHeader('ID', 'id'),
            TableHeader('项目名称', 'name'),
            TableHeader('备注信息', 'remark'),
            TableHeader('更新时间', 'update_time'),
            TableHeader('创建时间', 'create_time')
        ]

    # def notify_change(self):
    #     # 中间层：接收被装饰函数
    #     def decorator(self, *args, **kwargs):
    #         def wrapper(func, *args, **kwargs):
    #             status, _ =  func(*args, **kwargs)
    #             if status:
    #                 # 数据更新成功，发送数据更新信号，通知UI更新数据
    #                 self.data_changed_signal.emit(self.dao.get_all())
    #         return wrapper
    #
    #     return decorator

    # @classmethod
    # def notify_change(cls, func):
    #     """类内类方法：装饰器，统计方法调用次数（存到类属性）"""
    #     # 初始化该方法的调用次数
    #     cls.method_call_count[func.__name__] = 0
    #
    #     def wrapper(self, *args, **kwargs):
    #         # 访问类属性，累加调用次数
    #         cls.method_call_count[func.__name__] += 1
    #         result = func(self, *args, **kwargs)
    #         print(f"方法 {func.__name__} 已调用 {cls.method_call_count[func.__name__]} 次")
    #         # 数据更新成功，发送数据更新信号，通知UI更新数据
    #         self.data_changed_signal.emit(self.dao.get_all())
    #         return result
    #     return wrapper

    def get_records(self, condition: dict, page=1, page_size=0) -> Tuple[List[dict], int]:
        if page_size > 0:
            return self.dao.get_page_data(page, page_size, condition.get("name"))
        else:
            records = self.dao.get_all()
            return records, len(records)

    def get_update_callable(self) -> Callable:
        return self.dao.update_by_id

    def on_update_result(self, success: bool, msg: str, payloads):
        super().on_update_result(success, msg, payloads)
        if success:
            # 数据更新成功，发送数据更新信号，通知UI更新数据
            self.data_changed_signal.emit(self.dao.get_all())

    def get_delete_data_callable(self) -> Callable:
        return self.dao.delete_by_ids

    def on_delete_result(self, success: bool, msg: str, payloads):
        super().on_delete_result(success, msg, payloads)
        if success:
            # 数据更新成功，发送数据更新信号，通知UI更新数据
            self.data_changed_signal.emit(self.dao.get_all())

    def _is_empty(self, val):
        return True if val is None or not str(val).strip() else False

    def validate_new_data(self, data):
        # 示例：验证必填字段
        if (self._is_empty(data.get('name'))):
            QMessageBox.warning(self, "验证错误", "必要字段不能为空！")
            return False
        return True

    # def add_one(self, data):
    #     self.async_task_scheduler.submit_task(self.dao.add_one, data,
    #                                              finished_callback=self.on_add_one_result,
    #                                              fail_callback=self.on_add_one_result)

    def get_add_one_callable(self) -> Callable:
        return self.dao.add_one

    def on_add_one_result(self, success: bool, msg: str, payloads):
        super().on_add_one_result(success, msg, payloads)
        if success:
            # 数据更新成功，发送数据更新信号，通知UI更新数据
            self.data_changed_signal.emit(self.dao.get_all())

    def batch_insert(self, data_list: List[Dict]):
        # 批量插入数据，没开通
        pass

    def get_edit_metadata(self) -> dict:
        return {"update_time": EditableField("update_time", "hide"),
                "create_time": EditableField("create_time", "hide")}

    def get_add_metadata(self) -> dict:
        return self.get_edit_metadata()

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
        return [QueryField('text', '项目名称', 'name')]
