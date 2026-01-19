from typing import List, Tuple, Dict, Callable

from PyQt5.QtWidgets import QMessageBox, QDialog, QVBoxLayout

from src.frame.base.ui.base_table_widget import BaseTableWidget, EditableField, BaseAsyncImportWorker, TableHeader, \
    QueryField
from src.frame.common.exceptions import BusinessException
from src.frame.dao.db_manager import db
from src.ui.config_center.ui_config_task_node import UIConfigTaskNodes


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


class UITaskTmpl(BaseTableWidget):
    """
    任务模板表
    """

    def __init__(self):
        self.dao = db.task_tmpl_dao
        self.project_dao = db.project_dao
        self.task_tmpl_dao = db.task_tmpl_dao
        self.business_type_mapping = {"learning": "学习", "exam": "考试", "login": "登录", "score": "查询成绩",
                                      "choose_course": "选课", "upload": "上传作业", "download": "下载证书",
                                      "collect": "采集信息"}
        self.start_mode_mapping = {1: "有用户", 0: "无用户"}
        self.status_mapping = {1: "启用", 0: "停用"}
        self.is_quit_browser_when_finished_mapping = {1: "是", 0: "否"}
        self.project_mapping = {}
        self.project_options = []
        self.config_task_nodes_action = None
        super().__init__(False, True, True, False, True)

    def get_headers(self) -> List[TableHeader]:
        # TODO pause by zcy 必须要支持隐藏列，否则在编辑时，若project_id没传而改成传project_name会抛出异常
        return [
            TableHeader('ID', 'id'),
            TableHeader('项目名称', 'project_id', False),
            TableHeader('项目名称', 'project_name', is_add_visible=False, is_edit_visible=False),
            TableHeader('任务模板名称', 'name'),
            TableHeader('业务类型', 'business_type'),
            TableHeader('域名', 'domain'),
            TableHeader('登录间隔（秒）', 'login_interval'),
            TableHeader('退出浏览器', 'is_quit_browser_when_finished'),
            TableHeader('起始节点ID', 'start_node_id'),
            TableHeader('启动模式', 'start_mode'),
            TableHeader('状态', 'status'),
            TableHeader('更新时间', 'update_time'),
            TableHeader('创建时间', 'create_time')
        ]

    # def first_load_data(self):
    #     self.async_task_scheduler.submit_task(self.project_dao.get_all,
    #                                           finished_callback=self.on_first_load_data_finished)
    #
    # def on_first_load_data_finished(self, status, msg, records):
    #     if status:
    #         self.update_project_info(records)
    #     super().first_load_data()
    #
    # def update_project_info(self, records: List[Dict]):
    #     self.project_options = [(record.get("name"), record.get("id")) for record in records]
    #     self.project_mapping = {record.get("id"): record.get("name") for record in records}

    def get_records(self, condition: dict, page=1, page_size=0) -> Tuple[List[dict], int]:
        if page_size > 0:
            return self.dao.get_page_data(page, page_size, condition.get("business_type"), condition.get("name"))
        else:
            records = self.dao.get_all()
            return records, len(records)

    def _is_empty(self, val):
        return True if val is None or not str(val).strip() else False

    def validate_new_data(self, data):
        # 示例：验证必填字段
        if (self._is_empty(data.get('name')) or self._is_empty(data.get('domain'))
                or self._is_empty(data.get('login_interval'))):
            QMessageBox.warning(self, "验证错误", "必要字段不能为空！")
            return False
        return True

    def get_add_one_callable(self) -> Callable:
        return self.dao.add_one

    def get_update_callable(self) -> Callable:
        return self.dao.update_by_id

    def get_delete_data_callable(self) -> Callable:
        return self.dao.delete_by_ids

    def batch_insert(self, data_list: List[Dict]) -> Tuple[bool, str]:
        try:
            self.dao.batch_add(data_list)
            return True, ""
        except BusinessException as e:
            return False, e.error_desc
        except Exception as e:
            return False, str(e)

    def get_edit_metadata(self) -> dict:
        projects = self.project_dao.get_all()
        project_options = [(project.get("name"), project.get("id")) for project in projects]

        return {"project_id": EditableField("project_id", "select", project_options),
                "business_type": EditableField("business_type", "select",
                                               [(value, key) for key, value in self.business_type_mapping.items()]),
                "is_quit_browser_when_finished": EditableField("is_quit_browser_when_finished", "select",
                                                               [(value, key) for key, value in
                                                                self.is_quit_browser_when_finished_mapping.items()]),
                "start_mode": EditableField("start_mode", "select",
                                            [(value, key) for key, value in self.start_mode_mapping.items()]),
                "status": EditableField("status", "select",
                                        [(value, key) for key, value in self.status_mapping.items()]),
                "update_time": EditableField("update_time", "readonly"),
                "create_time": EditableField("create_time", "readonly"), }

    def get_add_metadata(self) -> dict:
        metadata = self.get_edit_metadata()
        metadata["status"].field_type = "hide"
        metadata["start_node_id"] = EditableField("start_node_id", "hide")
        return metadata

    def validate_import_data(self, data):
        # 验证导入数据的有效性
        # return bool(data.get('product_name'))
        return True

    def create_bulk_importer(self) -> BaseAsyncImportWorker:
        return AsyncImportWorker(self)

    def delete_all(self):
        pass

    def get_field_mapping(self) -> Dict:
        return {"business_type": self.business_type_mapping,
                "start_mode": self.start_mode_mapping,
                "status": self.status_mapping,
                # "project_id": self.project_mapping,
                "is_quit_browser_when_finished": self.is_quit_browser_when_finished_mapping,
                }

    def get_query_fields(self) -> List[QueryField]:
        return [
            QueryField('select', '业务类型', 'business_type', [(value, key) for key, value in self.business_type_mapping.items()]),
            QueryField('text', '任务模板名称', 'name', placeholder="请输入任务模板名称...")
        ]

    # 重写菜单创建方法，添加自定义选项
    def create_context_menu(self):
        # 先调用父类方法，获取基础菜单（保留“编辑”选项）
        menu = super().create_context_menu()
        # 添加分隔符，区分原有选项和自定义选项
        menu.addSeparator()
        # 添加自定义菜单选项
        self.config_task_nodes_action = menu.addAction("配置节点")
        return menu

    # 重写动作处理方法，处理自定义选项的逻辑
    def handle_menu_action(self, action, row):
        # 先调用父类的动作处理（保证“编辑”功能正常）
        super().handle_menu_action(action, row)
        # 处理子类自定义的菜单动作
        if action == self.config_task_nodes_action:
            self.show_config_dialog(row)

    def show_config_dialog(self, row):
        row_data = self._get_row_data(row)
        if not row_data:
            return

        task_tmpl_id = row_data["id"]

        def _show_dialog(status: bool, msg: str, payloads):
            config_task_nodes_dialog = QDialog(self)
            config_task_nodes_dialog.setWindowTitle(f"配置任务模板 | ID：{task_tmpl_id} | 名称：{payloads.get('name')}")
            # 关键：给Dialog设置最小尺寸，避免内容被压缩
            config_task_nodes_dialog.setMinimumSize(450, 400)
            layout = QVBoxLayout()

            config_widget = UIConfigTaskNodes(payloads.get("id"), payloads.get("start_node_id"))
            layout.addWidget(config_widget)
            config_task_nodes_dialog.setLayout(layout)
            config_task_nodes_dialog.exec_()

        self.async_task_scheduler.submit_task(self.task_tmpl_dao.get_by_id, task_tmpl_id,
                                              finished_callback=_show_dialog)
