import logging
import os
from pathlib import Path
from typing import List, Any, Tuple, Dict

from rapidfuzz import fuzz

from src.frame.common.question_bank.base_question_bank import BaseQuestionBankHandler
from src.utils.sys_path_utils import SysPathUtils


class FullQuestionBankHandler(BaseQuestionBankHandler):
    """
    完整题库。需匹配题目和选项
    示例题库配置如下：
    ------
    xkb_question_bank_high_ts = 高中通识题库.txt
    ------
    其中：
    question_bank_key = "xkb_question_bank_high_ts"
    question_bank_value = "高中通识题库.txt"

    [高中通识题库.txt]文档中的格式如下：
    ------
    1. 课程标准解读可以釆取专家现场讲座、________学习的方式。
    A. 校际研讨
    B. 线上视频
    C. 现场交流
    D. 现场互动
    答案: B

    2. 初中化学实验技能的基本要求包括初步学习使用过滤、________ 的方法对混合物进行分离。
    A. 倾倒
    B. 抽取
    C. 蒸发
    D. 萃取
    答案: C

    3. 以下属于化学教材编写原则的是________。
    A. 合理把握内容的深度和广度
    B. 体现化学与人文的融合
    C. 以课程标准为依据,促进学生核心素养发展
    D. 密切联系社会生活经验
    答案: C
    ------
    """

    def analyze_question_bank(self, question_bank_value: str) -> List[Any]:
        """
        解析题库，把题库解析成可以分析的格式
        :param question_bank_value: 题库的路径，如果是相对路径，请相对于conf目录，最好放在conf目录下！
        :return:
        """
        question_bank_path = Path(question_bank_value)
        if not question_bank_path.is_absolute():  # 如果是相对路径，相对于conf目录下
            question_bank_path = Path(SysPathUtils.get_config_file_dir(), question_bank_path)  # 题库文件的位置
        if not question_bank_path.exists():
            logging.error(f"【{question_bank_value}】题库文件不存在，如果是相对路径，请相对于conf目录，最好放在conf目录下！")
            raise ValueError("题库文件不存在")

        with open(question_bank_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        title = []  # 题目
        item = {}  # 选项
        answer = []  # 答案
        subjects = []  # 解析后的数据
        if lines:
            for line in lines:
                try:
                    line = line.strip()
                    if line.startswith(("A", "B", "C", "D", "E", "F")):
                        # 选项开始
                        # segs = line.split(".")
                        dot_index = line.find(".")
                        if dot_index != -1:
                            item_code = line[0: dot_index]
                            item_desc = line[dot_index + 1:]
                            item[item_code] = self.strip(item_desc.strip(), omit_chas=("_",))
                        else:
                            item[line[0]] = self.strip(line[1:])
                    elif line.startswith("答案"):
                        # 答案开始
                        for ch in line:
                            if ch in ("A", "B", "C", "D", "E", "F"):
                                answer.append(ch)
                        # answer.append(line.strip()[-1])
                    elif line is None or len(line) == 0 or len(line.strip()) == 0:
                        # 一道题结束
                        if len(title) > 0 and len(item) > 0 and len(answer) > 0:
                            if len(title) > 1:
                                title[0] = os.linesep.join(title)
                            subjects.append({"title": title, "item": item, "answer": answer})
                        title = []
                        item = {}
                        answer = []
                    elif line.startswith("="):
                        # 分割符号忽略
                        continue
                    else:
                        if line.find(".", 0, 4) > 0:
                            title.append(self.strip(line[line.find(".") + 1:]))
                        else:
                            title.append(self.strip(line))
                except Exception as e:
                    logging.error("解析题库失败", exc_info=True)
        return subjects

    def get_answer_from_question_bank(self, question_bank_value: List[Any], question_desc: str,
                                      options: List[str] = [], question_no="") -> Tuple[str, ...]:
        ret = None
        if question_desc:
            question_desc = self.strip(question_desc)
            val_map: Dict = {"val": 0, "answer": ""}
            for subject in question_bank_value:
                # 先匹配问题，匹配值大于80说明匹配到题目了
                val = fuzz.ratio(question_desc, subject["title"][0])
                if val >= 90:
                    item_dict: dict = subject["item"]
                    # 匹配选项，选项取交集后，判断长度是否等于原来的选项，不相等，说明选项匹配不上，是不同的题目
                    if options:
                        if len((set(item_dict.values()) & set(options))) != len(options):
                            continue
                    # 匹配到问题了
                    if val > val_map["val"]:
                        val_map["val"] = val
                        val_map["answer"] = tuple([subject["item"][answer_item] for answer_item in subject["answer"]])
            if val_map["val"] != 0:
                ret = val_map["answer"]

        if not ret:
            # 只匹配题目，不匹配选项再来一次
            # ret = self.get_answer_from_question_bank(subject_list, question_desc, None)
            if question_desc:
                question_desc = self.strip(question_desc)
                val_map = {"val": 0, "answer": ""}
                for subject in question_bank_value:
                    # 先匹配问题，匹配值大于80说明匹配到题目了
                    val = fuzz.ratio(question_desc, subject["title"][0])
                    if val >= 90:
                        item_dict: dict = subject["item"]
                        # 匹配选项，选项取交集后，判断长度是否等于原来的选项，不相等，说明选项匹配不上，是不同的题目
                        # 匹配到问题了
                        if val > val_map["val"]:
                            val_map["val"] = val
                            val_map["answer"] = (subject["item"][subject["answer"][0]],)
                if val_map["val"] != 0:
                    ret = val_map["answer"]
        return ret

