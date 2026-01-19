
class BusinessException(Exception):
    """业务异常"""
    def __init__(self, error_desc):
        super().__init__(error_desc)
        self.error_desc = error_desc

class ParamError(Exception):
    """参数错误"""
    def __init__(self, error_desc):
        super().__init__(error_desc)
        self.error_desc = error_desc

class SessionExpiredException(Exception):
    """会话过期异常：触发自动重登"""
    def __init__(self, msg: str = "会话已过期，请重新登录"):
        super().__init__(msg)
        self.msg = msg

class NeedReloginException(Exception):
    """通用需要重登异常：触发自动重登"""
    def __init__(self, msg: str = "发生关键错误，需要重新登录"):
        super().__init__(msg)
        self.msg = msg