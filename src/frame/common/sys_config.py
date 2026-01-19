from src.frame.dao.db_manager import db


class SysConfig:

    @classmethod
    def save_value(cls, key: str, value: str):
        # ConfigFileReader.set_val(key, value)
        db.data_dict_dao.update_by_key(key, value)

    @classmethod
    def get_value(cls, key: str) -> dict:
        """
        获取数据字典配置
        :param key: 键
        :return: {"key": key, "value": "xx", "name": "xxx", "remark": "cvc"}
        """
        return db.data_dict_dao.get_by_key(key)
