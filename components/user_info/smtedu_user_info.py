from dataclasses import dataclass, field
from typing import Dict

from src.frame.base.base_task_node import BasePYNode
from src.utils import SMTEduSignUtils, RequestMethod


@dataclass(init=False)
class SMTEduUserInfo(BasePYNode):
    sdp_app_id: str = ""
    user_agent: str = ""
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
        name, school_name = await self.get_user_info()
        self.logger.info(f"获取用户信息成功：{name}，{school_name}")
        if self.user_manager:
            self.user_manager.update_record_by_username(self.username, {3: name, 4: school_name})

        return True

    async def get_user_info(self):
        # 获取用户信息
        url = r"https://x-user-profile.ykt.eduyun.cn/v2/teacher/profile"
        self._set_authorization(url, RequestMethod.GET)
        try:
            resp = await self.context.request.get(url, headers=self.headers)
            json = await resp.json()
            return json["name"], json["school"]["school_name"]
        except Exception as e:
            self.logger.exception("获取用户信息失败：")
            return None

    def _set_authorization(self, url, request_method):
        self.headers["authorization"] = SMTEduSignUtils.gen_authorization(url, self.access_token, self.mac_key,
                                                                          request_method)
