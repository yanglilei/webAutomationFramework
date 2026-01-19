import os
from pathlib import Path
from typing import Optional

# 项目名称，若是项目名称有变化，则需要修改此处
PROJECT_DIR_NAME = "webAutomationFramework"

class PathUtils:
    @staticmethod
    def upper_search_file(cur_dir: Path, filename: str | Path, recursive_count=5) -> Optional[str]:
        # 向上回溯直到找到根目录
        while not (cur_dir / filename).exists() and recursive_count > 0:
            recursive_count -= 1
            cur_dir = cur_dir.parent
        return str(cur_dir / filename) if (cur_dir / filename).exists() else ""


class SysPathUtils:
    """
    路径工具，获取配置文件存放目录和数据文件存放目录
    """
    @classmethod
    def get_root_dir(cls):
        import sys
        if getattr(sys, 'frozen', False):
            # 如果是打包后的可执行文件
            return os.path.dirname(sys.executable)
        else:
            # 如果是开发环境中的 Python 脚本
            # return os.path.dirname(os.path.abspath(__file__))
            return PathUtils.upper_search_file(Path.cwd(), PROJECT_DIR_NAME)

    @classmethod
    def get_config_file_dir(cls):
        """
        获取配置文件的目录
        当前文件的绝对路径下的conf目录
        若该方法或者文件移动到别处，则有影响！请注意！
        :return: str
        """
        return os.path.join(cls.get_root_dir(), "conf")

    @classmethod
    def get_tmp_file_dir(cls):
        """
        获取临时文件的目录
        当前文件的绝对路径下的tmp目录
        :return: str
        """
        return os.path.join(cls.get_root_dir(), "tmp")

    @classmethod
    def get_data_file_dir(cls):
        """
        获取数据文件的目录
        当前文件的绝对路径下的data目录
        若该方法或者文件移动到别处，则有影响！请注意！
        :return:
        """
        return os.path.join(cls.get_root_dir(), "data")

    @classmethod
    def get_icon_file_dir(cls):
        """
        获取图标文件的目录
        当前文件的绝对路径一致
        :return:
        """
        return cls.get_root_dir()

    @classmethod
    def get_signature_file(cls):
        """
        获取签名文件
        :return: str
        """
        return os.path.join(cls.get_config_file_dir(), "signature.txt")

# if __name__ == '__main__':
#     print(PathUtils.upper_search_file(Path.cwd(), "requirements.txt"))