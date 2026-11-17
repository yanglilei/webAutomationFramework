from dataclasses import dataclass, field
from typing import Dict

from src.frame.base.base_task_node import BasePYNode
from src.utils import SMTEduSignUtils, RequestMethod


@dataclass(init=False)
class SMTEduUserInfo(BasePYNode):
    """
    智慧平台获取用户信息
    获取用户名和学校信息，更新到表格中
    版本：V0.0.1
    """
    sdp_app_id: str = ""
    # ["X-ND-AUTH"]请求头
    x_nd_auth_tmpl: str = 'MAC id="%s",nonce="0",mac="0"'
    # 请求头
    headers: Dict[str, str] = field(default_factory=dict)
    # 用户id
    user_id: str = ""
    # mac_key
    mac_key: str = ""
    # token
    access_token: str = ""
    # app_id
    app_id: str = ""

    async def execute(self, context: Dict) -> bool:
        # 获取用户签名信息
        self.user_id, self.mac_key, self.access_token, self.app_id = await SMTEduSignUtils.get_user_sign_params(
            self.execute_js)
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "sdp-app-id": self.app_id}
        user_info = await self.get_user_info()
        grade_section = await self._get_grade_section()
        subject_code = await self._get_subject_code()
        grade_section_cn_name = grade_section.get(user_info.get("teacher_verify_info").get("grade_section"))
        subject_cn_name = subject_code.get(user_info.get("teacher_verify_info").get("subject_code"))
        name = user_info["name"]
        school_name = user_info["school"]["school_name"]

        self.logger.info(f"获取用户信息成功：{name}，{school_name}，{grade_section_cn_name}，{subject_cn_name}")
        if self.user_manager:
            self.user_manager.update_record_by_username(self.username,
                                                        {3: name, 4: school_name, 5: grade_section_cn_name,
                                                         6: subject_cn_name})

        return True

    async def get_user_info(self):
        # 获取用户信息
        url = r"https://x-user-profile.ykt.eduyun.cn/v2/teacher/profile"
        self._set_authorization(url, RequestMethod.GET)
        try:
            resp = await self.context.request.get(url, headers=self.headers)
            return await resp.json()
            # json = await resp.json()
            # return json["name"], json["school"]["school_name"]
        except Exception as e:
            self.logger.exception("获取用户信息失败：")
            return None

    def _set_authorization(self, url, request_method):
        self.headers["authorization"] = SMTEduSignUtils.gen_authorization(url, self.access_token, self.mac_key,
                                                                          request_method)

    async def _get_grade_section(self):
        url = f"https://bdcs-file-1.ykt.cbern.com.cn/bdxcloud/configs/gradeSection.json"
        headers = {"User-Agent": await self.user_agent(), "Cookies": await self.cookie_to_str()}
        try:
            resp = await self.context.request.get(url=url, headers=headers)
        except:
            self.logger.error("获取学段信息失败")
            raise
        else:
            return await resp.json()

    async def _get_subject_code(self):
        url = f"https://bdcs-file-2.ykt.cbern.com.cn/bdxcloud/configs/subjectCode.json"
        headers = {"User-Agent": await self.user_agent(), "Cookies": await self.cookie_to_str()}
        try:
            resp = await self.context.request.get(url=url, headers=headers)
        except:
            self.logger.error("获取学科信息失败")
            raise
        else:
            return await resp.json()
