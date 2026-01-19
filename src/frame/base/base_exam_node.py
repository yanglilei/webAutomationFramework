import os
import time
from abc import abstractmethod
from dataclasses import dataclass, field
from typing import Tuple, Dict, Any

from selenium.webdriver.remote.webelement import WebElement

from src.frame.base.base_task_node import BasePYNode
from src.frame.common.constants import NodeState, ControlCommand
from src.frame.common.question_bank.base_question_bank import BaseQuestionBankHandler


@dataclass(init=False)
class BaseMCQExamTaskNode(BasePYNode):
    """
    选择题考试任务基类
    MCQ：选择题
    全称：multiple-choice question（单数）/ multiple-choice questions（复数）
    """
    question_bank_handler: BaseQuestionBankHandler = None  # 题库处理器
    interval: float = 0  # 间隔时间
    is_test_mode: bool = False  # 测试模式
    # 当前题目信息
    current_question_info: Dict[str, Any] = field(default_factory=lambda: {
        "question_no": "",  # 题号
        "question_desc": "",  # 题目文本
        "question_elem": None,  # 题目元素
        "options": {}  # 选项信息
    })

    def register_builtin_commands(self):
        @self.register_command(ControlCommand.PAUSE)
        def pause():
            self.logger.info("考试暂停！")
            self.state = NodeState.PAUSED

        @self.register_command(ControlCommand.RESUME)
        def resume():
            self.logger.info("考试继续！")
            self.state = NodeState.RUNNING

    def set_up(self):
        self.interval = float(self.node_config.get("node_params", {}).get("interval"))  # 间隔时间
        self.is_test_mode = self.node_config.get("node_params", {}).get("is_test_mode")  # 测试模式
        self.question_bank_handler = self.init_question_bank_handler()

    @abstractmethod
    def init_question_bank_handler(self) -> BaseQuestionBankHandler:
        """
        初始化题库处理器
        返回题库处理器
        :return: BaseQuestionBankHandler
        """
        pass

    def execute(self, context: Dict) -> bool:
        self.logger.info("开始做题！")
        # 非常重要！如果遇到需要手动进入到考试页面的情况，则该处直接设置状态为PAUSED，等待手动点击开始按钮，发送继续的命令！
        self.state = NodeState.RUNNING
        ret = True
        # self.switch_to_latest_window()
        # self.switch_to_window_by_url_key("exam-ans")
        try:
            while True:
                if self.state == NodeState.PAUSED:
                    self.logger.info("考试暂停中，请确认已经在考试页面，要开始/继续考试，请手动点击开始按钮！")
                    time.sleep(2)
                    continue
                # 切到当前题目窗口
                self.switch_to_window_by_url_key("exam-ans")
                # 做当前题目
                if self.finish_current_question():
                    if not self.has_next_question():
                        # 完成了最后一题
                        break
                    # 等待若干秒
                    time.sleep(self.interval)
                    # 切到下一题
                    status, desc = self.go_next_question()
                    if status:
                        # 等待当前题目元素消失，防止卡顿导致切换下一题比较慢！必须等待当前题目元素消失，保证成功切换下一题
                        self.wait_for_disappeared(10, self.current_question_info.get("question_elem"))
                        # 切换到下一题了，重置当前题目信息
                        self.current_question_info = {"question_no": "", "question_desc": "", "question_elem": None,
                                                      "options分": {}}
                    else:
                        self.logger.error(f"切换到下一题失败[原因：{desc}]，等待20秒，请手动触发到下一题！！")
                        time.sleep(20)
                else:
                    # 做题失败
                    self.logger.error("做题失败：请手动选择答案！")
                    time.sleep(20)
        except:
            self.logger.exception("做题失败：")
            ret = False
        else:
            if ret:  # 答题正常完成，处理交卷
                self.logger.info("完成所有题目，准备交卷！")
                if self.node_config.get("node_params", {}).get("auto_commit", False):
                    # 根据节点参数 auto_commit 决定是否自动提交
                    try:
                        # 交卷
                        self.commit()
                        # 处理结果
                        self.handle_after_commit()
                    except:
                        self.logger.exception("交卷失败，请人工处理：")
                        ret = False
        finally:
            if not ret and self.global_config.get("driver_config", {}).get("headless_mode") != 1:
                # 考试属于特殊节点！
                # 若是考试失败了，在非无头模式下，避免浏览器被关了，由人工接手！
                self.task_config["is_quit_browser_when_finished"] = False
        return ret

    def clean_up(self):
        self.state = NodeState.READY

    @abstractmethod
    def has_next_question(self) -> bool:
        pass

    @abstractmethod
    def get_question_info(self) -> Tuple[str, str, WebElement]:
        """
        获取当前题目的信息：题号、题目文本、题目元素
        :return: (题号, 题目文本，题目元素)
        """
        pass

    @abstractmethod
    def get_options(self) -> Dict[str, WebElement]:
        """
        获取所有选项
        返回字典：
        key-选项文本。匹配答案时会传入该选项文本，若是FullQuestionBankHandler则该参数是选项的文本内容（而不是ABCD），决定了能否匹配上答案。
        value-选项的元素，类型为WebElement。点击用！
        :return:
        """
        pass

    @abstractmethod
    def choose_options(self, answers: Tuple[str, ...], options: Dict[str, WebElement]):
        """
        选择答案
        :param answers:  答案
        :param options: get_options方法的返回值
        :return:
        """
        pass

    @abstractmethod
    def go_next_question(self) -> Tuple[bool, str]:
        """
        到下一个题目
        :return: (True, "成功") or (False, [失败原因])
        """
        pass

    @abstractmethod
    def commit(self):
        """
        交卷
        :return:
        """
        pass

    @abstractmethod
    def handle_after_commit(self):
        """
        交卷后的处理逻辑，获取成绩、或者清理工作
        考试中不允许太快交卷，可在此做逻辑等待，例如：可以间隔轮训调用commit方法
        :return:
        """
        pass

    def get_answers(self, question_no="", question_desc="", options=[]) -> Tuple[str, ...]:
        """
        获取答案
        :param question_no: 题目编号
        :param question_desc: 问题描述
        :param options: 选项
        :return:tuple 格式：("A","B","C")或者("正确",)
        """
        return self.question_bank_handler.get_answer(question_no, question_desc, options)

    def finish_current_question(self) -> bool:
        # 整体思路，保证软件运行正常，且不会被卡住！
        try:
            # 获取当前题目信息
            question_no, question_desc, question_elem = self.get_question_info()
            if not question_desc:
                self.logger.info("没有获取到题目，请在20秒内重新刷新页面！")
                time.sleep(20)
                return True
            # 获取所有选项。题目有出来，选项会一起出来，所以此处无需再次判断
            options = self.get_options()
        except:
            self.logger.exception("获取题目或选项异常！请在30秒内手动完成当前题目！后续软件会做题继续！")
            time.sleep(30)
            return True

        # 保存当前题目信息
        self.current_question_info = {"question_no": question_no, "question_desc": question_desc,
                                      "question_elem": question_elem, "options": options}

        try:
            answer = self.get_answers(question_no, question_desc, list(options.keys()))
        except:
            self.logger.exception(f"【{question_desc}】获取答案异常！请在20秒内手动选择，并且点击下一题，软件会做题继续！")
            time.sleep(20)
            return True

        try:
            self.choose_options(answer, options)
            self.logger.info(f"【{question_no}.{question_desc}】选择答案：{answer}")
        except:
            self.logger.error(
                f"【{question_desc}】选择答案失败！请在20秒内手动选择，并且点击下一题，软件会做题继续！当前题目答案：{answer}")
            time.sleep(20)
            return True
        return True

    def record_subject(self, file_path, title, items):
        prefixes = (
            "A.", "B.", "C.", "D.", "E.", "F.", "G.", "H.", "I.", "J.", "K.", "L.", "M.", "N.", "O.", "P.", "Q.", "R.",
            "S.", "T.", "U.", "V.", "W.", "X.", "Y.", "Z.")
        with open(file_path, "a+", encoding="utf-8") as f:
            title = title.strip()
            f.write(title)
            if not title.endswith(os.linesep):
                f.write(os.linesep)
            for idx, item in enumerate(items):
                item_text = f"{prefixes[idx]}{item.text}".strip()
                f.write(item_text)
                if not item_text.endswith(os.linesep):
                    f.write(os.linesep)
            f.write(os.linesep)
