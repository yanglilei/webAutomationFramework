from configparser import RawConfigParser
from pathlib import Path
from typing import List


def search_config_file(cur_dir: Path, config_file_parent_dir, config_file_name, recursive_count=8) -> Path:
    # 向上回溯直到找到根目录
    while not (cur_dir / config_file_parent_dir / config_file_name).exists() and recursive_count > 0:
        recursive_count -= 1
        cur_dir = cur_dir.parent
    return cur_dir / config_file_parent_dir / config_file_name

class ConfigFileReader:
    base_section_name = "Base"  # 基本配置分段名称
    busi_section_name = "Busi"  # 业务配置分段名称
    config_file_name = "config.ini"
    file_encode = "utf-8-sig"
    config_parser = RawConfigParser()
    config_file_full_path = search_config_file(Path.cwd(), "conf", config_file_name)
    config_parser.read(config_file_full_path, encoding=file_encode)

    @staticmethod
    def get_val(key, section_name="Base"):
        ret = None
        if ConfigFileReader.config_parser.has_section(ConfigFileReader.base_section_name):
            ret = ConfigFileReader.config_parser.get(section_name, key, fallback=None)
        return ret

    @staticmethod
    def set_val(key, value, section_name="Base"):
        if not ConfigFileReader.config_parser.has_section(section_name):
            ConfigFileReader.config_parser.add_section(section_name)
        ConfigFileReader.config_parser.set(section_name, key, value)
        with open(ConfigFileReader.config_file_full_path, "w", encoding=ConfigFileReader.file_encode) as f:
            ConfigFileReader.config_parser.write(f)

    @staticmethod
    def get_options(section_name):
        return ConfigFileReader.config_parser.options(section_name)

