import time
from dataclasses import dataclass
from typing import Tuple, Dict

from selenium.webdriver.remote.webelement import WebElement

from src.frame.base.base_exam_node import BaseMCQExamTaskNode
from src.frame.common.question_bank.base_question_bank import BaseQuestionBankHandler
from src.frame.common.question_bank.fixed_question_bank_handler import FixedQuestionBankHandler


@dataclass(init=False)
class AXJXJYExamTaskNode(BaseMCQExamTaskNode):
    teach_course_name: str = ""  # 老师教的课程
    # 新课标题目编号
    XKB_QUESTION_NO = "//div[@class='splitS-left']//span"
    # 新课标下一题
    XKB_NEXT_QUESTION = "//a[text()='下一题']"
    # 新课标测试的题目
    XKB_QUESTION_DESC = "//div[@class='splitS-left']//div"
    # 新课标所有选项的文本，备选1
    XKB_ALL_OPTION_TEXT = "//div[contains(@class, 'clearfix answerBg')]/div"
    # 新课标所有选项的字母，备选2
    XKB_ALL_OPTION_LETTERS = "//div[contains(@class, 'clearfix answerBg')]/span"

    def set_up(self):
        self.teach_course_name = self.user_manager.get_cell_val(self.username, 2)
        super().set_up()

    def init_question_bank_handler(self) -> BaseQuestionBankHandler:
        question_bank_key = f"ax_{self.teach_course_name}"
        question_bank_value = self.node_config.get("node_params", {}).get(question_bank_key)
        if not question_bank_value:
            raise ValueError(f"节点参数中未找到题库配置项：{question_bank_key}")
        # 安溪继续教育采用固定答案的题库
        return FixedQuestionBankHandler(question_bank_key, question_bank_value)

    def has_next_question(self) -> bool:
        return True if self.get_elem_with_wait_by_xpath(3, self.XKB_NEXT_QUESTION) else False

    def get_question_info(self) -> Tuple[str, str, WebElement]:
        # 获取题目编号，固定顺序和编号的情况
        question_no_elem: WebElement = self.get_elem_with_wait_by_xpath(3, self.XKB_QUESTION_NO)
        question_elem: WebElement = self.get_elem_with_wait_by_xpath(3, self.XKB_QUESTION_DESC)
        return question_no_elem.get_attribute("aria-label").split(".")[0].strip(), question_elem.text, question_elem

    def get_options(self) -> Dict[str, WebElement]:
        ret = self.get_elems_by_xpath(self.XKB_ALL_OPTION_LETTERS)
        if not ret:
            ret = self.get_elems_by_xpath(self.XKB_ALL_OPTION_TEXT)

        return {self.question_bank_handler.strip(i.text.strip()): i for i in ret} if ret else {}

    def choose_options(self, answers: Tuple[str, ...], options=Dict[str, WebElement]):
        # 根据答案内容，获取选项
        if answers:
            try:
                for answer in answers:
                    option = options.get(answer)
                    option.click()
                    time.sleep(0.5)
            except:
                self.logger.error(
                    f"{self.current_question_info.get('question_desc')}，选项：{answers}，点击不了，请在20秒内人工点击该选项")
                time.sleep(20)
        else:
            # 题目写入本地
            # self.record_subject(Path(SysPathUtils.get_config_file_dir(), "new_questions.txt"),
            #                     self.current_question_info.get('question_desc'),
            #                     self.current_question_info.get('options', {}).keys())

            self.logger.warning(f"{self.current_question_info.get('question_desc')}，未找到答案，默认选C")
            try:
                options.get("C").click()
            except:
                self.logger.error(
                    f"{self.current_question_info.get('question_desc')}，选项：{answers}，点击不了请人工点击，仅有20秒时间")
                time.sleep(20)

    def go_next_question(self) -> Tuple[bool, str]:
        next_elem: WebElement = self.get_elem_by_xpath(self.XKB_NEXT_QUESTION)
        if next_elem:
            try:
                next_elem.click()
                return True, "成功"
            except:
                self.logger.error("点击下一题按钮失败，请检查！")
                return False, "点击下一题按钮失败"
        else:
            self.logger.info("没有找到下一题的按钮，请在20秒内，手动触发到下一题")
            return False, "没有找到下一题的按钮"

    def commit(self):
        btn_commit = self.get_elem_with_wait_by_xpath(10, "//div[@class='sub-button fr']/a")
        try:
            btn_commit.click()
        except:
            self.logger.exception(f"用户【{self.username_showed}】交卷失败，稍后会再处理！")
        else:
            # 硬性等待
            time.sleep(1)
            btn_confirm = self.get_elem_with_wait_by_xpath(10,
                                                           "//p[text()='确认交卷？']/following-sibling::div[@class='popBottom']/a[text()='确定']")
            try:
                btn_confirm.click()
            except:
                self.logger.exception(f"用户【{self.username_showed}】交卷失败，稍后会再处理！")

    def get_score(self):
        return self.get_elem_with_wait_by_xpath(120,
                                                "//div[@class='result_Main']//h2[contains(@class,'result_number')]")

    def handle_after_commit(self):
        score_elem = self.get_score()
        while not score_elem:
            self.commit()
            score_elem = self.get_score()
        else:
            score = score_elem.text
            self.logger.info(f"用户【{self.username_showed}】交卷成功！考试分数：{score}")
            # 更新用户表中的考试分数
            self.user_manager.update_learning_status(self.username, score)
