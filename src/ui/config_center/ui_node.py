from typing import List, Tuple, Dict, Callable

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QMessageBox, QWidget, QPushButton

from src.frame.base.ui.base_table_widget import BaseTableWidget, EditableField, BaseAsyncImportWorker, TableHeader, \
    QueryField
from src.frame.common.exceptions import BusinessException
from src.frame.dao.db_manager import db


class AsyncImportWorker(BaseAsyncImportWorker):
    def __init__(self, dao):
        super().__init__()
        self.dao = dao

    def bulk_insert(self, data_list):
        """执行批量插入"""
        try:
            # 通过table_widget访问DAO
            self.dao.batch_add(data_list)
        except Exception as e:
            error_msg = f"批量插入失败: {str(e)}"
            self.error.emit(error_msg, 0)
            raise  # 向上抛出以停止导入流程

    def validate_row(self, data):
        """基础数据验证（可扩展）"""
        return True


class NodePage(BaseTableWidget):
    def __init__(self):
        self.node_dao = db.node_dao
        self.node_type_mapping = {"login": "登录", "enter_course": "进入课程", "monitor": "监视学习",
                                  "score": "查询成绩",
                                  "choose_course": "选课", "exam": "考试", "upload": "上传作业", "download": "下载证书",
                                  "collect": "采集信息"}
        self.status_mapping = {0: "停用", 1: "启用"}
        super().__init__(is_support_import=False, is_need_search=True,
                         is_support_add=True, is_support_clear_all=False)

    def get_headers(self) -> List[TableHeader]:
        return [
            TableHeader('ID', 'id'),
            TableHeader('节点名称', 'name'),
            TableHeader('编号', 'code'),
            TableHeader('组件路径', 'component_path'),
            TableHeader('类型', 'type'),
            TableHeader('节点参数', 'node_params'),
            TableHeader('描述', 'description'),
            TableHeader('状态', 'status'),
            TableHeader('更新时间', 'update_time'),
            TableHeader('创建时间', 'create_time')
        ]

    def get_records(self, condition: dict, page=1, page_size=0) -> Tuple[List[dict], int]:
        if page_size > 0:
            return self.node_dao.get_page_data(page, page_size, condition.get("type"), condition.get("name"),
                                               condition.get("code"))
        else:
            records = self.node_dao.get_all()
            return records, len(records)

    def get_add_one_callable(self) -> Callable:
        return self.node_dao.add_one

    def get_update_callable(self) -> Callable:
        return self.node_dao.update_by_id

    def get_delete_data_callable(self) -> Callable:
        return self.node_dao.delete_by_ids

    def _is_empty(self, val):
        return True if val is None or not str(val).strip() else False

    def validate_new_data(self, data):
        # 示例：验证必填字段
        if (self._is_empty(data.get('name')) or self._is_empty(data.get('component_path'))
                or self._is_empty(data.get('code')) or self._is_empty(
                    data.get('type'))):
            QMessageBox.warning(self, "验证错误", "必要字段不能为空！")
            return False
        return True

    def batch_insert(self, data_list: List[Dict]):
        # 批量插入数据，没开通
        pass
        # self.node_dao.batch_add(data_list)

    def get_edit_metadata(self) -> dict:
        return {"type":
                    EditableField("type", "select", [(value, key) for key, value in self.node_type_mapping.items()]),
                "status": EditableField("status", "hide"),
                "node_params": EditableField("node_params", "textedit"),
                "update_time": EditableField("update_time", "hide"),
                "create_time": EditableField("create_time", "hide"), }

    def get_add_metadata(self) -> dict:
        return self.get_edit_metadata()

    def validate_import_data(self, data):
        # 验证导入数据的有效性
        # return bool(data.get('product_name'))
        return True

    def create_bulk_importer(self) -> BaseAsyncImportWorker:
        return AsyncImportWorker(self)

    def delete_all(self):
        pass

    def get_field_mapping(self) -> Dict:
        return {
            "type": self.node_type_mapping,
            "status": self.status_mapping
        }

    def get_query_fields(self) -> List[QueryField]:
        return [
            QueryField('select', '类型', 'type', [(value, key) for key, value in self.node_type_mapping.items()], None),
            QueryField('text', '节点名称', 'name'),
            QueryField('text', '编号', 'code')
            ]


class UINodeInTaskConfigPage(NodePage):
    # 完成了选择节点的信号
    chosen_node_signal = pyqtSignal()
    # 选择的节点发生了变化，发送信号，外部接收信号，刷新任务配置页面
    node_selection_changed_signal = pyqtSignal(list)

    def __init__(self, task_tmpl_id: int):
        self.task_node_mapping_dao = db.task_tmpl_node_mapping_dao
        self.task_dao = db.task_tmpl_dao
        self.task_tmpl_id = task_tmpl_id
        super().__init__()

    def get_headers(self) -> List[TableHeader]:
        return [
            TableHeader('ID', 'id'),
            TableHeader('节点名称', 'name'),
            TableHeader('编号', 'code'),
            TableHeader('组件路径', 'component_path'),
            TableHeader('类型', 'type'),
            TableHeader('节点参数', 'node_params'),
            TableHeader('描述', 'description'),
            TableHeader('状态', 'status'),
        ]

    def update_selection(self, state: int, row: int):
        super().update_selection(state, row)
        self.node_selection_changed_signal.emit(self.get_selected_rows())

    def add_widget_to_toolbar(self) -> List[QWidget]:
        btn_save = QPushButton("保存")
        btn_save.clicked.connect(self.save_task_config)
        return [btn_save]

    # def get_data(self, condition: dict, page=1, page_size=0) -> Tuple[List[dict], int]:
    #     nodes = self.node_dao.get_by_task_tmpl_id(self.task_tmpl_id)
    #     return nodes, len(nodes)

    def save_task_config(self):
        update_infos = []
        for record in self.get_selected_rows():
            mapping_info = {"task_tmpl_id": self.task_tmpl_id, "node_id": record.get("id")}
            update_infos.append(mapping_info)
        try:
            self.task_node_mapping_dao.update_by_task_tmpl_id(self.task_tmpl_id, update_infos)
            self.task_dao.update_start_node_id(self.task_tmpl_id, None)
        except BusinessException as e:
            QMessageBox.warning(self, "提示", f"配置节点失败：{e.error_desc}")
            return
        except Exception as e:
            QMessageBox.warning(self, "提示", f"配置节点失败：{str(e)}")
            return
        else:
            QMessageBox.information(self, "提示", "配置节点成功")
            self.chosen_node_signal.emit()

    def get_query_fields(self) -> List[QueryField]:
        return [QueryField('text', '名称', 'name'), QueryField('select', '类型', 'type', [(value, key) for key, value in self.node_type_mapping.items()])]
