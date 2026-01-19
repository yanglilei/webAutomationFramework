from typing import List, Tuple

from src.frame.common.question_bank.base_question_bank import BaseQuestionBankHandler


class FixedQuestionBankHandler(BaseQuestionBankHandler):
    """
    固定答案的题库。
    示例题库配置如下：
    ------
    ax_jx_小学语文 = B,B,B,B,B,B,B,AC,B,B,ABC,B,C,B,B,B,B,C,B,C
    ------
    其中：
    question_bank_key = "ax_jx_小学语文"
    question_bank_value = "B,B,B,B,B,B,B,AC,B,B,ABC,B,C,B,B,B,B,C,B,C"

    备注：
    多选题的多个答案直接拼在一起，例如：ABCD
    """

    def analyze_question_bank(self, question_bank_value) -> List[str]:
        """
        解析题库，把题库解析成可以分析的格式
        :param question_bank_value: 题库的路径，如果是相对路径，请相对于conf目录，最好放在conf目录下！
        :return:
        """
        if not question_bank_value or not question_bank_value.strip():
            raise ValueError("题库配置项不能为空")
        return question_bank_value.split(",")

    def get_answer_from_question_bank(self, question_bank_value: List[str], question_desc: str,
                                      options: List[str] = [], question_no="") -> Tuple[str, ...]:
        return self.answer_str_2_tuple(question_bank_value[int(question_no) - 1])
