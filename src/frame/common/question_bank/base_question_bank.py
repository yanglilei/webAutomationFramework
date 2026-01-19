from abc import abstractmethod, ABC
from typing import List, Tuple, Any


class BaseQuestionBankHandler(ABC):
    """
    题库处理器基类
    """
    def __init__(self, question_bank_key: str, question_bank_value: str):
        # 题库（格式化后的）。key为题库编号，value为题库内容为List[str]格式，一道题目对应一个元素
        self.question_bank = {}
        # 题库的key，通常为题库名称，保证全局唯一
        self.question_bank_key = question_bank_key
        # 题库内容（未格式化）
        self.question_bank_value = question_bank_value
        # 加载题库
        self._load_question_bank()

    def _load_question_bank(self):
        self.question_bank[self.question_bank_key] = self.analyze_question_bank(self.question_bank_value)

    def get_answer(self, question_no="", question_desc="", options=[]) -> Tuple[str, ...]:
        """
        获得答案
        :param question_no: 题目编号
        :param question_desc:str 问题描述
        :param options: 选项
        :return:tuple 格式：("A","B","C")或者("正确",)
        """
        return self.get_answer_from_question_bank(self.question_bank[self.question_bank_key], question_desc, options, str(question_no))

    @abstractmethod
    def analyze_question_bank(self, question_bank_value: str) -> List[Any]:
        """
        解析题库，把题库解析成可以分析的格式
        返回数组，一道题目对应一个元素
        :param question_bank_value: 题库内容。__init__方法中的question_bank_value参数内容
        :return: List[str]
        """
        pass

    @abstractmethod
    def get_answer_from_question_bank(self, question_bank_value: List[Any], question_desc: str,
                                      options: List[str] = [], question_no="") -> Tuple[str, ...]:
        """
        从题库中获取答案
        :param question_bank_value: 经过analyze_question_bank方法解析后的题库信息
        :param question_desc: 考试题目
        :param options: 选项列表
        :param question_no: 题目编号。有些题库用题号匹配答案
        :return: Tuple[str, ...] 返回的答案，例如：('A', 'B', ...)
        """
        pass

    def get_answer_from_question_str(self, answer_str, question_no: int):
        answer_list = answer_str.split(",")
        return self.answer_str_2_tuple(answer_list[question_no - 1])

    def answer_str_2_list(self, answer_str: str):
        ret = []
        if answer_str is not None and len(answer_str) > 0:
            answer_list = answer_str.split(",")
            for answer in answer_list:
                if len(answer) > 0 and 65 <= ord(answer[0]) <= 90:
                    ret.append(tuple(answer))
                else:
                    ret.append((answer,))
        return ret

    def answer_str_2_tuple(self, answer_str: str):
        ret = ()
        if answer_str is not None and len(answer_str) > 0:
            answer_list = answer_str.split(",")
            for answer in answer_list:
                if len(answer) > 0 and 65 <= ord(answer[0]) <= 90:
                    ret = tuple(answer)
                else:
                    ret = (answer,)
        return ret

    def strip(self, line: str, omit_chas=(" ", "_")):
        # strip_chas = (" ", "_")
        origin_chas = ("，", "（", "）", "：", "；")
        target_chas = (",", "(", ")", ":", ";")

        cha_list = []
        if line:
            for ch in line.strip():
                if ch in omit_chas:
                    continue
                elif ch in origin_chas:
                    cha_list.append(target_chas[origin_chas.index(ch)])
                else:
                    cha_list.append(ch)
        return "".join(cha_list)

