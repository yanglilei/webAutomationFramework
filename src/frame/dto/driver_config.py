import os
from dataclasses import dataclass
from typing import Optional, Any, Dict

from src.frame.common.exceptions import ParamError
from src.utils.sys_path_utils import SysPathUtils


@dataclass
class DriverConfig:
    # 浏览器可执行文件的位置，谷歌浏览器必须填写，edge浏览器可以不填写
    browser_exe_position: str = ""
    # hook端口
    hook_port: Optional[str] = None
    # 1-无界面；0-有界面
    headless_mode: str = "1"
    # 是否使用无痕模式。1-使用无痕模式；0-使用普通模式
    incognito_mode: str = "1"
    # 是否使用selenium-wire。1-使用selenium-wire；0-不使用selenium-wire
    is_selenium_wire: str = "0"
    # 浏览器类型。0：chrome；1：firefox
    browser_type: str = "0"
    # 驱动位置
    driver_path: str = ""


class DriverConfigFormatter:
    @classmethod
    def format(cls, driver_config: Dict[str, Any]) -> DriverConfig:
        """
        格式化驱动参数
        :param driver_config: 接收参数 browser_type/browser_exe_position/hook_port/headless_mode/incognito_mode/is_selenium_wire/driver_path
        :raise: ParamError
        :return:
        """
        browser_type = cls._format_param(driver_config, "browser_type", "0", optional_val=("0", "1"))
        browser_exe_position = driver_config.get("browser_exe_position")
        # if browser_type == "0":
            # if not browser_exe_position or not browser_exe_position.strip():
            #     raise ParamError("请指定浏览器位置")
            # elif not os.path.isabs(browser_exe_position):
            #     # 相对路径
            #     browser_exe_position = os.path.join(SysPathUtils.get_root_dir(), browser_exe_position)

            # browser_exe_position = browser_exe_position.strip()
            # # 绝对路径
            # if not os.path.exists(browser_exe_position):
            #     raise ParamError("请指定正确的浏览器位置")

        hook_port = driver_config.get("hook_port")
        if hook_port:
            try:
                int(hook_port)
            except:
                raise ParamError("请指定正确的hook端口")

        headless_mode = cls._format_param(driver_config, "headless_mode", "1", optional_val=("0", "1"))
        incognito_mode = cls._format_param(driver_config, "incognito_mode", "1", optional_val=("0", "1"))
        is_selenium_wire = cls._format_param(driver_config, "is_selenium_wire", "0", optional_val=("0", "1"))
        return DriverConfig(browser_exe_position, hook_port, headless_mode, incognito_mode,
                            is_selenium_wire, browser_type, driver_config.get("driver_path").strip())

    @classmethod
    def _format_param(cls, driver_config, param_name, default_val, optional_val=("0", "1")):
        val = driver_config.get(param_name, default_val)
        if val not in optional_val:
            raise ParamError(f"{param_name}只能为：{optional_val}")
        return val
