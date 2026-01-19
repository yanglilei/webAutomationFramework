import functools

from src.frame.common.exceptions import ParamError


def driver_config_validator(cls):
    @functools.wraps(cls)
    def wrapper(*args, **kwargs):
        # if not kwargs.get("browser_type") or kwargs.get("browser_type") == "0":
        #     if not kwargs.get("browser_exe_position"):
        #         raise ParamError("请指定浏览器位置")
        return cls(*args, **kwargs)
    return wrapper