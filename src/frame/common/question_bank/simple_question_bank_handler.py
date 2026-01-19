import logging
import re
from pathlib import Path
from typing import List, Tuple

from rapidfuzz import fuzz

from src.frame.common.question_bank.base_question_bank import BaseQuestionBankHandler
from src.utils.sys_path_utils import SysPathUtils


class SimpleQuestionBankHandler(BaseQuestionBankHandler):
    """
    最简单的题库，需匹配题目，答案固定。
    示例题库配置如下：
    ------
    xkb_question_bank_high_ts = 19167_question_bank.txt
    ------
    其中：
    question_bank_key = "xkb_question_bank_high_ts"
    question_bank_value = "19167_question_bank.txt"

    [19167_question_bank.txt]文档中的格式如下：
    ------
    联合国教科文组织于（）年发布了《重新思考教育》。###C###
    根据2016年CNNIC《国家信息化发展评价报告》，中国信息化发展指数位列全球第（）名。###D###
    “三全两高一大”中“三全”的含义不包括（）。###C###
    《关于推进高等教育学分认定和转换工作的意见》是教育部在（）年发布的。###B###
    国内首批在线开放课程认定证书是（）年出现的。###C###
    ------
    """

    def analyze_question_bank(self, question_bank_value) -> List[str]:
        """
        解析题库，把题库解析成可以分析的格式
        :param question_bank_value: 题库的路径，如果是相对路径，请相对于conf目录，最好放在conf目录下！
        :return:
        """
        if not question_bank_value or not question_bank_value.strip():
            raise ValueError("题库配置项不能为空")

        question_bank_path = Path(question_bank_value)
        if not question_bank_path.is_absolute():  # 如果是相对路径，相对于conf目录下
            question_bank_path = Path(SysPathUtils.get_config_file_dir(), question_bank_path)  # 题库文件的位置
        if not question_bank_path.exists():
            logging.error(f"【{question_bank_value}】题库文件不存在，如果是相对路径，请相对于conf目录，最好放在conf目录下！")
            raise ValueError("题库文件不存在")

        with open(question_bank_path, "r", encoding="utf-8") as f:
            subject_list = [line for line in f.readlines() if len(line.strip()) > 0]  # 过滤空行
        return subject_list

    def get_answer_from_question_bank(self, question_bank_value: List[str], question_desc: str,
                                      options: List[str] = [], question_no="") -> Tuple[str, ...]:
        answers = self.match_answer_from_question_bank(question_desc, question_bank_value)
        return self.answer_str_2_tuple(answers)

    def match_answer_from_question_bank(self, question_desc, subject_list) -> str:
        # 从题库中获取答案
        answer = None
        for subject in subject_list:
            # 先匹配问题，匹配值大于84说明匹配到题目了
            val = fuzz.partial_ratio(question_desc, subject)
            if val >= 80:
                # 匹配到问题了
                pattern = ".*###(.*)###"
                answer = re.match(pattern, subject).group(1)
                break
        return answer
