from typing import List, Tuple, Dict, Callable, Optional

from PyQt5.QtWidgets import QPushButton

from src.frame.base.ui.base_table_widget import BaseTableWidget, EditableField, TableHeader, QueryField
from src.frame.dao.db_manager import db


class UITaskBatch(BaseTableWidget):
    """
    任务批次表
    """

    def __init__(self, run_mode: Optional[int] = None):
        self.run_mode = run_mode
        self.task_batch_dao = db.task_batch_dao
        self.project_dao = db.project_dao
        self.task_tmpl_dao = db.task_tmpl_dao
        self.execute_status_mapping = {0: "待运行", 1: "运行中", 2: "已结束", 3: "已取消"}
        self.business_type_mapping = {"learning": "学习", "exam": "考试", "login": "登录", "score": "查询成绩",
                                      "choose_course": "选课", "upload": "上传作业", "download": "下载证书",
                                      "collect": "采集信息"}
        self.user_mode_mapping = {0: "无用户", 1: "表格", 2: "文本"}
        self.run_mode_mapping = {1: "全自动", 2: "半自动"}
        self.project_options = []
        self.project_mapping = {}
        self.force_stop_action = None
        self.btn_force_terminate: Optional[QPushButton] = None  # 强制终止按钮
        super().__init__(is_need_search=True, is_support_clear_all=False, is_support_export=False, is_support_add=False)

    def get_headers(self) -> List[TableHeader]:
        return [
            TableHeader('ID', 'id'),
            TableHeader('项目名称', 'project_name'),
            TableHeader('任务模板名', 'task_tmpl_name'),
            TableHeader('业务类型', 'business_type'),
            TableHeader('批次号', 'batch_no'),
            TableHeader('状态', 'execute_status'),
            TableHeader('运行模式', 'run_mode'),
            TableHeader('用户模式', 'user_mode'),
            TableHeader('加入批次时间', 'queue_time'),
            TableHeader('用户列表', 'user_info'),
            TableHeader('全局参数', 'global_config'),
            TableHeader('优先级', 'priority'),
            TableHeader('总用户数', 'total_user'),
            TableHeader('成功用户数', 'success_user'),
            TableHeader('失败用户数', 'fail_user'),
            TableHeader('备注信息', 'remark'),
            # ('更新时间', 'update_time'),
            # ('创建时间', 'create_time')
        ]

    def build_query_condition(self) -> dict:
        ret = super().build_query_condition()
        ret["run_mode"] = self.run_mode
        return ret

    def first_load_data(self):
        self.async_task_scheduler.submit_task(self.project_dao.get_all,
                                              finished_callback=self.on_first_load_data_finished)

    def on_first_load_data_finished(self, status, msg, records):
        if status:
            self.update_project_info(records)
        super().first_load_data()

    def update_project_info(self, records: List[Dict]):
        self.project_options = [(record.get("name"), record.get("id")) for record in records]
        self.project_mapping = {record.get("id"): record.get("name") for record in records}

    def get_records(self, condition: dict, page=1, page_size=0) -> Tuple[List[dict], int]:
        if page_size > 0:
            return self.task_batch_dao.get_page_data(page, page_size,
                                                     condition.get("batch_no"),
                                                     condition.get("project_name"),
                                                     run_mode=condition.get("run_mode"))
        else:
            records = self.task_batch_dao.get_all()
            return records, len(records)

    def _is_empty(self, val):
        return True if val is None or not str(val).strip() else False

    # def add_widget_to_toolbar(self) -> List[QWidget]:
    #     """
    #     添加自定义控件到工具栏
    #     子类可自行扩展
    #     :return : List[QWidget] 控件列表
    #     """
    #     self.btn_force_terminate = QPushButton("强制终止")
    #     self.btn_force_terminate.clicked.connect(self.on_force_terminate_clicked)
    #     return [self.btn_force_terminate]

    # def on_force_terminate_clicked(self):
    #     rows = self.get_selected_rows()
    #     if not rows:
    #         QMessageBox.warning(self, "提示", "请选择要强制终止的批次")
    #         return
    #
    #     # TODO 处理强制终止的逻辑
    #     for row in rows:
    #         batch_id = row.get("id")
    #         # 发送信号给TaskManager
    #         # self.task_batch_dao.update_by_id(batch_id, {"execute_status": 4})

    def prepare_for_add(self, data):
        # 示例：验证必填字段
        # if (self._is_empty(data.get('name')) or self._is_empty(data.get('domain'))
        #         or self._is_empty(data.get('login_interval'))):
        #     QMessageBox.warning(self, "验证错误", "必要字段不能为空！")
        #     return False
        return True

    def get_add_one_callable(self) -> Callable:
        return self.task_batch_dao.add_one

    def get_update_callable(self) -> Callable:
        return self.task_batch_dao.update_by_id

    def get_delete_data_callable(self) -> Callable:
        return self.task_batch_dao.delete_by_ids

    def get_edit_metadata(self) -> dict:
        projects = self.project_dao.get_all()
        task_tmpls = self.task_tmpl_dao.get_all()
        project_options = [(project.get("name"), project.get("id")) for project in projects]
        task_tmpl_options = [(task_tmpl.get("name"), task_tmpl.get("id")) for task_tmpl in task_tmpls]

        metadata = {
                    # "project_name": EditableField("project_name", "select", project_options, "project_id",
                    #                             self.create_related_value_getter(project_options)),
                    "project_name": EditableField("project_name", "select", project_options, "project_id"),
                    "task_tmpl_name": EditableField("task_tmpl_name", "select", task_tmpl_options,
                                                           "task_tmpl_id"),
                    "business_type": EditableField("business_type", "select",
                                                   [(value, key) for key, value in
                                                             self.business_type_mapping.items()]),
                    "user_mode": EditableField("user_mode", "select",
                                               [(value, key) for key, value in
                                                         self.user_mode_mapping.items()]),
                    "run_mode": EditableField("run_mode", "select",
                                              [(value, key) for key, value in self.run_mode_mapping.items()]),
                    "execute_status": EditableField("execute_status", "select",
                                                    [(value, key) for key, value in
                                                              self.execute_status_mapping.items()]),
                    "user_info": EditableField("user_info", "textedit"),
                    "global_config": EditableField("global_config", "textedit"),
                    "queue_time": EditableField("queue_time", "label"),
                    "batch_no": EditableField("batch_no", "label"),
                    "total_user": EditableField("total_user", "label"),
                    "success_user": EditableField("success_user", "label"),
                    "fail_user": EditableField("fail_user", "label"),
                    }

        return metadata

    def get_add_metadata(self) -> dict:
        projects = self.project_dao.get_all()
        task_tmpls = self.task_tmpl_dao.get_all()
        project_options = [(project.get("name"), project.get("id")) for project in projects]
        task_tmpl_options = [(task_tmpl.get("name"), task_tmpl.get("id")) for task_tmpl in task_tmpls]

        metadata = {
            # "project_name": EditableField("project_name", "select", project_options, "project_id",
            #                             self.create_related_value_getter(project_options)),
            "project_name": EditableField("project_name", "select", project_options, "project_id"),
            "task_tmpl_name": EditableField("task_tmpl_name", "select", task_tmpl_options,
                                            "task_tmpl_id"),
            "business_type": EditableField("business_type", "select",
                                           [(value, key) for key, value in
                                            self.business_type_mapping.items()]),
            "user_mode": EditableField("user_mode", "select",
                                       [(value, key) for key, value in
                                        self.user_mode_mapping.items()]),
            "run_mode": EditableField("run_mode", "select",
                                      [(value, key) for key, value in self.run_mode_mapping.items()]),
            "execute_status": EditableField("execute_status", "select",
                                            [(value, key) for key, value in
                                             self.execute_status_mapping.items()], visible=False),
            "user_info": EditableField("user_info", "textedit"),
            "global_config": EditableField("global_config", "textedit"),
            "queue_time": EditableField("queue_time", visible=False),
            "batch_no": EditableField("batch_no", visible=False),
            "total_user": EditableField("total_user", visible=False),
            "success_user": EditableField("success_user", visible=False),
            "fail_user": EditableField("fail_user", visible=False),
        }

        return metadata

    def validate_import_data(self, data):
        # 验证导入数据的有效性
        # return bool(data.get('product_name'))
        return True

    def delete_all(self):
        pass

    def get_field_mapping(self) -> Dict:
        return {
            "execute_status": self.execute_status_mapping,
            "run_mode": self.run_mode_mapping,
            "user_mode": self.user_mode_mapping,
            "project_id": self.project_mapping,
            "business_type": self.business_type_mapping
        }
        # return {
        #         "start_mode": self.start_mode_mapping,
        #         "status": self.status_mapping,
        #         "project_id": self.project_mapping,
        #         "is_quit_browser_when_finished": self.is_quit_browser_when_finished_mapping,
        #         }

    def get_query_fields(self) -> List[QueryField]:
        return [QueryField('text', '项目名称','project_name'), QueryField('text', '批次号','batch_no')]

    def init_project_options(self):
        records = self.project_dao.get_all()
        return [(record.get("name"), record.get("id")) for record in records]

# # 重写菜单创建方法，添加自定义选项
# def create_context_menu(self):
#     # 创建菜单
#     menu = self.set_menu_style(QMenu(self))
#     # 添加分隔符，区分原有选项和自定义选项
#     # menu.addSeparator()
#     # 添加自定义菜单选项
#     self.force_stop_action = menu.addAction("强制停止")
#     # self.config_task_nodes_action = menu.addAction("启用")
#     return menu
#
# # 重写动作处理方法，处理自定义选项的逻辑
# def handle_menu_action(self, action, row):
#     # 处理子类自定义的菜单动作
#     if action == self.force_stop_action:
#         self.task_manager.force_stop_batch(row.get("id"))
