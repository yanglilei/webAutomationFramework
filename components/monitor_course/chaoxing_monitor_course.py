import asyncio
import random
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Tuple, List

from cozepy import MessageObjectString, Message
from playwright.async_api import Locator, FrameLocator, Page

from src.frame.base.base_monitor_course_node import BaseMonitorCourseTaskNode
from src.frame.base.playwright_web_operator import PlaywrightWebOperator
from src.frame.common.exceptions import BusinessException
from src.frame.common.question_bank import BaseQuestionBankHandler, SimpleQuestionBankHandler
from src.frame.common.validator_handler import CXImageValidatorHandler
from src.utils.coze_api import AsyncCozeAgent
from src.utils.qiniu_utils import FileOperatorResult, UploadFileOperator
from src.utils.sys_path_utils import SysPathUtils


class CourseType(Enum):
    # 拓展阅读
    EXTEND_READING = "拓展阅读"
    # 视频课程
    VIDEO_COURSE = "视频课程"
    # 讨论分享
    DISCUSSION_SHARE = "讨论分享"
    # 直播课
    LIVE_COURSE = "直播课"
    # 问卷调研
    QUESTION_RESEARCH = "问卷调研"
    # 大测验，像新课标考试
    MOOC1_EXAM = "大测验"
    # 其他
    OTHER = "其他"


class ChaoXingExamHandler:
    def __init__(self, web_operator, username, course_name, content_name, logger):
        """
        超星测验处理器
        CX=超星
        需要先切换到任务点下的iframe
        :param web_operator: web_operator
        """
        self.web_operator: PlaywrightWebOperator = web_operator
        self.username = username
        self.course_name = course_name
        self.content_name = content_name
        self.logger = logger
        self.all_questions = []

    def _switch_to_exam_iframe(self, outter_iframe: FrameLocator) -> FrameLocator:
        """
        切换到测验的iframe
        :return:
        """
        return self.web_operator.switch_to_frame("xpath=//iframe[@id='frame_content']", outter_iframe)

    async def _get_all_questions(self, exam_iframe: FrameLocator) -> List[Tuple[str, Locator]]:
        all_questions = await (exam_iframe.locator("xpath=//div[@class='singleQuesId']")).all()
        # all_questions = self.web_operator.get_elems_by_xpath("//div[contains(@class, 'singleQuesId')]")
        return [(await question.text_content(), question) for question in all_questions]

    async def do_exam(self, iframe: FrameLocator) -> bool:
        """
        做测验，需要先切换到任务点下的iframe
        :return:  True-做测验成功；False-做测验失败
        """
        exam_iframe = self._switch_to_exam_iframe(iframe)
        if not exam_iframe:
            self.logger.info("切换到测验的iframe（//iframe[@id='frame_content']）失败，退出测验！")
            return False

        ret = True
        try:
            # 获取所有的题目
            self.all_questions = await self._get_all_questions(exam_iframe)
            if self.all_questions:
                for question_text, question_elem in self.all_questions:
                    if not await question_elem.is_visible():
                        await question_elem.scroll_into_view_if_needed()
                        await asyncio.sleep(0.5)
                    if "单选题" in question_text:
                        # 做单选题
                        ret = await self._do_single_answer(question_elem)
                    elif "多选题" in question_text:
                        # 做多选题
                        ret = await self._do_multiple_answer(question_elem)
                    elif "判断题" in question_text:
                        # 做判断题
                        ret = await self._do_judge_answer(question_elem)
                    elif "填空题" in question_text:
                        # 做填空题
                        ret = await self._do_fill_answer(question_elem)
                        # ret = False
                        # self.logger.error(
                        #     "填空题未实现：%s，位置：【%s】_【%s】" % (question_text, self.course_name, self.content_name))
                        # break
                    elif "简答题" in question_text:
                        # 做简答题
                        # ret = self._do_short_answer(question_elem)
                        ret = False
                        self.logger.info(
                            "简答题未实现：%s，位置：【%s】_【%s】" % (question_text, self.course_name, self.content_name))
                        break
                    else:
                        ret = False
                        self.logger.error(
                            "未知的题型：%s，位置：【%s】_【%s】" % (question_text, self.course_name, self.content_name))
                        break
                    await asyncio.sleep(1)
                # 提交
                ret = await self.submit(exam_iframe)
        except:
            self.logger.exception(
                "在做测验出错！位置：【%s】_【%s】" % (self.course_name, self.content_name))
            ret = False
        finally:
            pass
            # self.web_operator.web_browser.switch_to.default_content()
        return ret

    async def submit(self, iframe: FrameLocator) -> bool:
        """
        提交
        :return: bool True-提交成功；False-提交失败
        """
        # 提交
        ret = True
        btn_submit = await self.web_operator.get_elem_by_xpath("//a[@class='btnSubmit workBtnIndex']", iframe=iframe)
        if btn_submit:
            if not await btn_submit.is_visible():
                await btn_submit.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
            await btn_submit.click()
            # self.web_operator.switch_to.default_content()
            if commit_confirm := await self.web_operator.wait_for_visible_by_xpath(3, "//a[@id='popok']"):
                await self.web_operator.js_click(commit_confirm)
                # commit_confirm.click()
        else:
            self.logger.error("未找到提交按钮")
            ret = False
        return ret

    async def _do_single_answer(self, question_elem: Locator):
        # 单选题
        ret = False
        try:
            # 获取选项
            all_options = await self.web_operator.get_relative_elems_by_xpath(question_elem,
                                                                              ".//span[contains(@class, 'num_option')]")
            # 1.获取正确答案，此处采用随机选择一个选项
            target_option = random.sample(all_options, 1)
            # 2.选择选项
            if not await target_option[0].is_visible():
                await target_option[0].scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
            await target_option[0].click()
            await asyncio.sleep(0.5)
        except:
            self.logger.exception(
                "做测验出错！位置：【%s】_【%s】" % (self.course_name, self.content_name))
            ret = False
        return ret

    async def _do_multiple_answer(self, question_elem: Locator):
        # 多选题
        ret = False
        try:
            # 获取选项
            all_options = await self.web_operator.get_relative_elems_by_xpath(question_elem,
                                                                              ".//span[contains(@class, 'num_option')]")
            # 1.获取正确答案，此处采用随机选择一个选项
            target_options = random.sample(all_options, random.randint(1, len(all_options)))
            # 2.选择选项
            for target_option in target_options:
                if not await target_option.is_visible():
                    await target_option.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                await target_option.click()
                await asyncio.sleep(0.5)
        except:
            self.logger.exception(
                "做测验出错！位置：【%s】_【%s】" % (self.course_name, self.content_name))
            ret = False

        return ret

    async def _do_judge_answer(self, question_elem: Locator):
        # 判断题
        return await self._do_single_answer(question_elem)

    async def _do_fill_answer(self, question_elem: Locator):
        # 填空题
        xpath = ".//div[@class='clearfix font-cxsecret fontLabel']"
        ret = False
        try:
            # 获取选项
            title_elem = await self.web_operator.get_relative_elem_by_xpath(question_elem, xpath)
            # 1.截图
            filename = self.username + str(random.randint(10000000, 99999999)) + ".png"
            local_file = Path(SysPathUtils.get_tmp_file_dir(), filename)
            await title_elem.screenshot(path=local_file)

            # 2.上传到七牛
            result: FileOperatorResult = UploadFileOperator().upload(str(local_file), filename)
            # result.resource_url
            # 3.发送给智能体
            MessageObjectString.build_image(result.resource_url)
            async_coze_client = AsyncCozeAgent()
            reply_content = await async_coze_client.get_reply(
                [Message.build_user_question_objects([MessageObjectString.build_image(file_url=result.resource_url),
                                                      MessageObjectString.build_text(
                                                          "我是一位中小学教师，附件的图中是一道题目，请以我的视角解答。要求：直接输出文字，不添加任何格式（包括markdown格式）")]),
                 ])

            paragraphs = reply_content.split("\n")
            reply_html_segs = []
            for paragraph in paragraphs:
                reply_html_segs.append(f"<p>{paragraph.strip()}</p>")
            reply_html = ''.join(reply_html_segs)
            # 3.填写答案
            # 切换到输入框iframe
            editor_iframe: FrameLocator = question_elem.frame_locator("iframe").nth(0)
            input_body = editor_iframe.locator("//body[@class='view']")
            # 写入输入框
            await input_body.evaluate(f"""(elem) => {{elem.innerHTML='{reply_html}'}}""")
        except:
            self.logger.exception("做测验出错！位置：【%s】_【%s】" % (self.course_name, self.content_name))
            ret = False

        return ret


    async def _do_short_answer(self, question_elem: Locator):
        # TODO 待完善！简答题
        xpath = ".//div[@class='clearfix font-cxsecret fontLabel']"
        ret = False
        try:
            # 获取选项
            title_elem = await self.web_operator.get_relative_elem_by_xpath(question_elem, xpath)
            # 1.截图
            filename = self.username + str(random.randint(10000000, 99999999)) + ".png"
            local_file = Path(SysPathUtils.get_tmp_file_dir(), filename)
            await title_elem.screenshot(path=local_file)

            # 2.上传到七牛
            result: FileOperatorResult = UploadFileOperator().upload(str(local_file), filename)
            # result.resource_url
            # 3.发送给智能体
            MessageObjectString.build_image(result.resource_url)
            async_coze_client = AsyncCozeAgent()
            reply_content = await async_coze_client.get_reply(
                [Message.build_user_question_objects([MessageObjectString.build_image(file_url=result.resource_url),
                                                      MessageObjectString.build_text(
                                                          "我是一位中小学教师，附件的图中是一道题目，请以我的视角解答。要求：直接输出文字，不添加任何格式（包括markdown格式）")]),
                 ])

            paragraphs = reply_content.split("\n")
            reply_html_segs = []
            for paragraph in paragraphs:
                reply_html_segs.append(f"<p>{paragraph.strip()}</p>")
            reply_html = ''.join(reply_html_segs)
            # 3.填写答案
            # 切换到输入框iframe
            xpath = ".//div[@id='edui1']//iframe"
            # editor_iframe = self.web_operator.get_relative_elem(question_elem, (By.XPATH, xpath))
            editor_iframe: FrameLocator = question_elem.frame_locator(f"{xpath}")
            # self.web_operator.switch_to_frame(editor_iframe)
            input_body = editor_iframe.locator("//body[@class='view']")
            # 写入输入框
            await input_body.evaluate(f"(elem) => {{elem.innerHTML=`{reply_html}`}}")
        except:
            self.logger.exception("做测验出错！位置：【%s】_【%s】" % (self.course_name, self.content_name))
            ret = False

        return ret

    def _choose_options(self, all_options: List[Locator]):
        pass


class ChaoXingMooc1ExamHandler:
    """
    超星中mooc1考试处理器，和新课标考试一样
    https://mooc1.chaoxing.com/exam-ans/exam/test/examcode/examnotes?courseId=264491641&classId=148678605&examId=9937737&enc=ded343599d6febdeb0c90c3814bf00dd
    """
    def __init__(self, web_operator: PlaywrightWebOperator, question_bank_handler: BaseQuestionBankHandler, username: str, logger):
        self.web_operator: PlaywrightWebOperator = web_operator
        self.username = username
        self.logger = logger
        # 测验答案类
        self.question_bank_handler = question_bank_handler
        # 最大刷新次数
        self.max_refresh_times = 3

    async def handle(self) -> None:
        await self.do_exercise()

    async def do_exercise(self) -> None:
        # 切换窗口！
        agree_cb = await self.web_operator.get_elem_with_wait_by_xpath(10, "//i[@class='agree_check']")
        if not agree_cb:
            self.logger.error("做测验异常，找不到“我已阅读并同意”单选框，刷新页面，发起重试！")
            # 刷新页面
            if self.max_refresh_times > 0:
                self.max_refresh_times -= 1
                await self.web_operator.refresh()
                # 继续学习，此刻学习监控线程会发现，测验未完成会重新触发做测验的任务
                await self.do_exercise()
            else:
                self.logger.error(f"做测验异常，找不到“我已阅读并同意”单选框，达到最大刷新次数3，刷新页面失败！")
                raise BusinessException("做测验异常，找不到“我已阅读并同意”单选框，刷新页面失败！")

        try:
            await agree_cb.click()
        except:
            self.logger.exception("点击“我已阅读并同意”单选框失败")
            raise BusinessException("点击“我已阅读并同意”单选框失败")
        else:
            await asyncio.sleep(2)
            btn_start_exam = await self.web_operator.get_elem_by_xpath("//a[@id='startBtn']")
            if not btn_start_exam:
                self.logger.error("“开始考试”按钮找不到")
                raise BusinessException("“开始考试”按钮找不到")

            if not await btn_start_exam.is_enabled():
                self.logger.error("“开始考试”按钮不能点击")
                raise BusinessException("“开始考试”按钮不能点击")

            try:
                await btn_start_exam.click()
            except:
                self.logger.exception("点击“进入考试”按钮失败")
                raise BusinessException("点击“进入考试”按钮失败")
            else:
                # 确认考试
                confirm_start_exam_btn = await self.web_operator.get_elem_with_wait_by_xpath(5, "//a[@id='tabIntoexam2']")
                if not confirm_start_exam_btn:
                    self.logger.error("“确认考试”按钮找不到")
                    raise BusinessException("“确认考试”按钮找不到")

                try:
                    await confirm_start_exam_btn.click()
                except:
                    self.logger.exception("点击提示框中的“进入考试”按钮失败")
                    raise BusinessException("点击提示框中的“进入考试”按钮失败")
                else:
                    image_validate_elem = await self.web_operator.get_elem_with_wait_by_xpath(5, "//div[@class='cx_comImageValidate']")
                    if image_validate_elem:
                        cx_image_validator_handler = CXImageValidatorHandler(self.username, self.web_operator, self.logger)
                        is_validate_succ = await cx_image_validator_handler.handle_cx_image_validate(self.web_operator.get_current_page())
                        if is_validate_succ:
                            try:
                                await self._do_exercise()
                            except Exception as e:
                                # 此处必须捕获，否则会抛出异常，导致任务结束，退出网页人工无法介入
                                if isinstance(e, BusinessException) and len(e.args) > 0:
                                    self.logger.error("做测验异常，异常信息：", e.args[0])
                                else:
                                    self.logger.exception("做测验异常，异常信息：")

    async def _do_exercise(self):
        while True:
            try:
                # 1.获取题目编号
                question_no_elem = await self.web_operator.get_elem_with_wait_by_xpath(10, "//li[@class=' current ']")
            except Exception as e:
                self.logger.exception("做测验，加载题目失败，可能网络问题，退出！")
                raise e
            else:
                question_desc_elem = await self.web_operator.get_elem_with_wait_by_xpath(10, "//div[@class='splitS-left']//div")
                question_desc_str = await question_desc_elem.text_content()
                question_desc_str = question_desc_str.strip()
                question_no = await question_no_elem.text_content()
                question_no = int(question_no.strip())
                options = await self.web_operator.get_elems_with_wait_by_xpath(10, "//div[contains(@class, 'clearfix answerBg')]//div")
                options = [await option.text_content() for option in options]
                answers = self.question_bank_handler.get_answer(question_no, question_desc_str, options)
                if answers is None:
                    self.logger.info(f"题目：{question_desc_str}，没有找到答案，默认选第一个答案")
                    answer_item_elem = None
                    try:
                        answer_item_elem = await self.web_operator.get_elem_with_wait_by_xpath(5, "//span[text()='A']")
                    except:
                        pass
                    else:
                        try:
                            await answer_item_elem.click()
                        except:
                            self.logger.info(f"做测验异常，第{question_no}题，选择第一个答案失败")
                            raise

                    self.logger.info("做测验，第%d题选：%s", question_no, answer_item_elem.get_attribute("data"))
                else:
                    for answer in answers:
                        click_item_xpath = "//span[text()='%s']" % answer
                        # 点击答案
                        try:
                            await (await self.web_operator.get_elem_by_xpath(click_item_xpath)).click()
                        except:
                            # 一般是点击出现异常！重试一次
                            try:
                                await (await self.web_operator.get_elem_with_wait_by_xpath(5, click_item_xpath)).click()
                            except:
                                self.logger.info("做测验异常，第%d题，选择答案%s失败", question_no, answer)
                                raise

                        # 延迟200ms
                        await asyncio.sleep(0.2)
                    self.logger.info("做测验，第%d题选：%s" % (question_no, "".join(answers)))

                await asyncio.sleep(random.randint(1, 3))

                next_answer_btn = await self.web_operator.get_elem_by_xpath("//a[@class='jb_btn jb_btn_92 fs14']")
                if not next_answer_btn:
                    await self.web_operator.refresh()
                    await asyncio.sleep(2)
                    next_answer_btn = await self.web_operator.get_elem_with_wait_by_xpath(10, "//a[@class='jb_btn jb_btn_92 fs14']")
                    if not next_answer_btn:
                        self.logger.error("没有找到“下一题”的按钮，做测验异常，退出测验，请人工介入检查！")
                        raise BusinessException("没有找到“下一题”按钮")

                next_answer_text = await next_answer_btn.text_content()
                if next_answer_text == "下一题":
                    try:
                        await next_answer_btn.click()
                    except:
                        self.logger.error("点击“下一题“按钮失败，做测验异常，退出测验，请人工介入检查！")
                        raise
                    else:
                        try:
                            # 等待旧题目消失
                            await self.web_operator.wait_for_disappeared_by_xpath(10, f"//li[@class=' current ' and text()={question_no}]")
                        except:
                            pass
                elif next_answer_text == "下一步":
                    # 最后一道题目
                    try:
                        await next_answer_btn.click()
                    except:
                        self.logger.error("点击“下一题“按钮失败，做测验异常，退出测验，请人工介入检查！")
                        raise
                    else:
                        try:
                            # 点击交卷
                            commit_elem = await self.web_operator.get_elem_with_wait_by_xpath(10, "//a[text()='交卷']")
                        except:
                            self.logger.error("没有找到“交卷”的按钮，做测验异常，退出测验，请人工介入检查！")
                            raise
                        else:
                            try:
                                await commit_elem.click()
                            except:
                                self.logger.error("没有找到“交卷”的按钮，做测验异常，退出测验，请人工介入检查！")
                                raise
                            else:
                                confirm_commit_elem = await self.web_operator.get_elem_with_wait_by_xpath(10, "//a[@class='jb_btn jb_btn_92 fr fs14 confirm'][text()='确定']")
                                if confirm_commit_elem:
                                    await confirm_commit_elem.click()
                                # 等待出结果
                                await asyncio.sleep(3.5)
                                try:
                                    # 成绩
                                    score_elem = await self.web_operator.get_elem_with_wait_by_xpath(10, "//h2[contains(@class,'result_number')]/b")
                                except:
                                    self.logger.error("获取测验结果失败！")
                                else:
                                    self.logger.info("做测验完成，分数为：%s，" % await score_elem.text_content())
                                finally:
                                    break


@dataclass(init=False)
class ChaoXingMonitorCourse(BaseMonitorCourseTaskNode):
    """超星监控课程节点，处理新版超新的学习页面，完整可用，已对接AI，可自动做测验！"""
    ############## 视频卡顿了，刷新视频作用！###########
    # cur_sys_time-first_sys_time的差值（实际经历的时间）与cur_learned_time-pre_learned_time的差值（视频走过的时间）做对比，若是超过了5分钟，认为视频卡顿了，则退出学习页面重新进入！
    # 第一次计算时间的标志
    first_cal_time_flag: bool = True
    # 上一次视频的学习时间
    pre_learned_time: int = 0
    # 当前视频的学习时间
    cur_learned_time: int = 0
    # 第一次系统时间
    first_sys_time: int = 0
    # 当前系统时间
    cur_sys_time: int = 0
    ############## 视频卡顿了，刷新视频作用！###########

    ############## 视频时间没有加载出来，刷新视频用！###########
    # cur_refresh_time-pre_refresh_time>60秒，则退出学习页面重新进入！
    # 是否需要刷新页面
    is_page_load_error: bool = False
    # 记录第一次视频时间没有加载出来的时刻
    pre_refresh_time: int = 0
    # 记录第二次视频时间没有加载出来的时刻
    cur_refresh_time: int = 0
    ############## 视频时间没有加载出来，刷新视频用！###########

    ############## 用于记录是否切换了视频 ##############
    pre_job_id: str = ""  # 前一个任务ID
    cur_job_id: str = ""  # 当前任务ID
    ############## 用于记录是否切换了视频 ##############

    # 当前学习的目录名称
    content_name: str = ""
    ############## 拓展阅读 ##############
    # 在学习拓展阅读
    is_reading: bool = False
    # 学习要求时间
    read_time_require: int = 0
    # 学习起始时间
    read_start_time: int = 0
    # 学习结束时间
    read_end_time: int = 0
    # 阅读页面
    reading_page: Page = None
    # 课程页面
    course_page: Page = None
    # 总滚动高度
    total_scroll_count: int = 0

    ############## 拓展阅读 ##############
    # 是否为拓展阅读的标志位
    is_expand_reading: bool = False
    # 是否为观看视频的标志位
    is_watch_video: bool = False
    # 是否为讨论分享的标志位
    is_discussion_share: bool = False

    #### 课程类型 ####
    course_type: CourseType = None
    COURSE_URL_KEY = "mooc2-ans/mycourse/stu"
    EXAM_URL_KEY = "exam-ans/exam"

    async def prepare_before_poll_monitor_course(self):
        self.course_page = self.get_prev_output().get("course_page")
        if not self.course_page:
            self.terminate("课程页面不存在", True)
            return
        read_time_require = self.node_config.get("node_params").get("read_time_require", 600)
        self.read_time_require = int(read_time_require)
        await self.switch_to_window(self.course_page)
        page_url = await self.get_current_url()
        if self.EXAM_URL_KEY in page_url:
            # 大测验，和新课标考试一样，https://mooc1.chaoxing.com/exam-ans/exam/test/examcode/examnotes?courseId=264491641&classId=148678605&examId=9937737&enc=eaf074743c0db8795df2af3fa2b2056c
            # 大测验结束后，直接terminate，无需执行single_poll_monitor
            # TODO 执行大测验！pause by zcy20260614
            question_bank_key = self.node_config.get("node_params").get("question_bank_key")
            question_bank_value = self.node_config.get("node_params").get("question_bank_value")

            question_bank_handler = SimpleQuestionBankHandler(question_bank_key, question_bank_value)
            mooc1_exam_handler = ChaoXingMooc1ExamHandler(self, question_bank_handler, self.username, self.logger)
            await mooc1_exam_handler.handle()
            self.terminate("已完成")
            return

    async def single_poll_monitor(self):
        # 目录名称
        self.content_name = await self.get_current_content_name()

        # 处理在别处登录
        if not await self.handle_login_in_other_place():
            self.terminate("在别处登录", True)
            return

        # 有些页面中既有视频也有测验，可能还有其他的，
        if await self._is_current_tab_finished():
            await self._switch_next_task_point()
            return

        flag, task_point_elem = await self._is_task_point_contains_video()
        if flag:  # 包含视频
            await self.handle_exam_in_video()  # 处理视频中含有测验（选择题）
            await self.handle_pause()  # 处理视频暂停
            self.cur_job_id = await self._get_job_id()
            if not self.pre_job_id:
                self.pre_job_id = self.cur_job_id
            # 当前视频的播放时间
            played_time, total_time = await self._get_played_time_and_total_time()

            self.logger.info("【%s】总时长%s，已学习%s" % (self.content_name, total_time, played_time))

            if played_time is None or total_time is None:
                if not self.is_page_load_error:
                    self.is_page_load_error = True
                    self.pre_refresh_time = int(time.time())
                else:
                    self.cur_refresh_time = int(time.time())
                    if self.cur_refresh_time - self.pre_refresh_time > 60:
                        self.is_page_load_error = False
                        # 获取时间失败（页面卡住没刷新出来），则重启该页面
                        self.logger.info(f"【{self.content_name}】获取时间失败，准备重启...")
                        # self.terminate("获取时间失败，需要重启！")
                        # 获取时间失败，刷新页面
                        await self.refresh()
                        return
            else:
                # TODO PAUSE BY ZCY 20251229 此处多余！任务点完成后会自动切换到下一个任务点！而不是直接切换到下一个目录！
                # if played_time != "00:00:00" and total_time != "00:00:00" and played_time >= total_time:
                #     # 时间相等了，说明已经播放完成
                #     if next_content := self.get_next_content():
                #         # 有下一个任务，则点击下一个任务
                #         try:
                #             self.execute_js("arguments[0].click();", next_content)
                #             self.first_cal_time_flag = True
                #         except:
                #             self.logger.info("点击下一个任务失败，请手动点击")
                #     else:
                #         # 达到最大时间，且没有下一个任务，则退出
                #         self.stop("当前课程已完成！")
                #         return
                if self.first_cal_time_flag:
                    self.first_sys_time = int(time.time())
                    self.pre_learned_time = self._cal_time(played_time)
                    self.first_cal_time_flag = False
                else:
                    self.cur_learned_time = self._cal_time(played_time)
                    self.cur_sys_time = int(time.time())

                    if self.pre_job_id and self.cur_job_id and self.pre_job_id != self.cur_job_id:
                        self.logger.info("切换了视频任务点【%s】" % self.cur_job_id)
                        # 切换了视频
                        self.pre_learned_time = self.cur_learned_time
                        self.first_sys_time = self.cur_sys_time
                        # 更新前一个视频任务点的ID
                        self.pre_job_id = self.cur_job_id

                    # 计算视频的时间过去了多久，单位秒
                    learned_time_span = self.cur_learned_time - self.pre_learned_time
                    # 计算时间过去了多久，单位秒
                    sys_time_span = self.cur_sys_time - self.first_sys_time
                    if sys_time_span - learned_time_span > 480:
                        # 8分钟了，学习时间没有更新了，则重启该页面
                        self.logger.info("【%s】卡住8分钟了，准备重启..." % self.content_name)
                        # self.terminate("视频卡住8分钟了，需要重启！")
                        # 视频卡住8分钟了，刷新页面
                        await self.refresh()
                        return
        else:  # 非视频，阅读文档或做测验等
            # self._switch_to_main_iframe()
            # iframe = self.get_relative_elem(task_point_elem, (By.XPATH, "./iframe"))
            # window = self.get_latest_window()
            # window.get_attribute()

            if task_point_elem:
                # 包含任务点
                iframe = task_point_elem.locator("xpath=./iframe").first
                if iframe:
                    class_desc = await iframe.get_attribute("class")
                    job_id = await iframe.get_attribute("jobid")
                    if class_desc and "insertdoc-online-pdf" in class_desc:
                        # 阅读文档
                        object_id = await iframe.get_attribute("objectid")
                        # self.switch_to_frame(iframe)
                        target_iframe = task_point_elem.frame_locator(f"xpath=./iframe")
                        await self._read_docs(target_iframe, object_id)
                        return
                    if job_id:
                        if "read" in job_id:
                            # 拓展阅读
                            self.course_type = CourseType.EXTEND_READING
                            target_iframe = task_point_elem.frame_locator(f"xpath=./iframe").frame_locator(
                                "iframe#frame_content")
                            await self._handle_extend_reading(target_iframe)
                        elif "work" in job_id:
                            # 做测验
                            await self.handle_exam_task_point()
                        else:
                            self.logger.info(f"未知任务点【{job_id}】，人工介入检查！")
                        return
                    if not class_desc and not job_id:
                        # self.logger.info("问卷调查或者考试")
                        self.content_name = await self.get_current_content_name()
                        if "问卷调研" in self.content_name:
                            self.logger.info("进入问卷调研，跳过！")
                            await self._handle_question_research()
                            await self._switch_next_task_point()
                        elif "讨论分享" in self.content_name:
                            self.logger.info("进入讨论分享，跳过！")
                            await self._handle_discussion_share()
                            await self._switch_next_task_point()
                        else:
                            self.logger.info(f"未知任务点【{job_id}】，人工介入检查！")
                            # 防止还有未完成的测验，导致死循环！处理方式：切换到下一个任务点
                        return
                else:
                    self.logger.error("没有找到任务点对应的iframe")
                    # 切换到下一个任务点
                    await self._switch_next_task_point()
            else:
                # 不包含任务点
                # 获取目录名
                self.content_name = await self.get_current_content_name()
                await self._judge_course_type(self.content_name)

                if self.course_type == CourseType.LIVE_COURSE:
                    # 直播课
                    self.logger.info("直播课，不处理")
                    await self._switch_next_task_point()

    async def clean_up(self):
        await super().clean_up()
        self.first_cal_time_flag: bool = True
        # 上一次视频的学习时间
        self.pre_learned_time: int = 0
        # 当前视频的学习时间
        self.cur_learned_time: int = 0
        # 第一次系统时间
        self.first_sys_time: int = 0
        # 当前系统时间
        self.cur_sys_time: int = 0
        ############## 视频卡顿了，刷新视频作用！###########

        ############## 视频时间没有加载出来，刷新视频用！###########
        # cur_refresh_time-pre_refresh_time>60秒，则退出学习页面重新进入！
        # 是否需要刷新页面
        self.is_page_load_error: bool = False
        # 记录第一次视频时间没有加载出来的时刻
        self.pre_refresh_time: int = 0
        # 记录第二次视频时间没有加载出来的时刻
        self.cur_refresh_time: int = 0
        ############## 视频时间没有加载出来，刷新视频用！###########

        ############## 用于记录是否切换了视频 ##############
        self.pre_job_id: str = ""  # 前一个任务ID
        self.cur_job_id: str = ""  # 当前任务ID
        ############## 用于记录是否切换了视频 ##############

        # 当前学习的目录名称
        self.content_name: str = ""

    async def _judge_course_type(self, content_name):
        if "课程学习" in content_name:
            self.course_type = CourseType.VIDEO_COURSE
        elif "拓展阅读" in self.content_name:
            self.course_type = CourseType.EXTEND_READING
            # await self._enter_read_page()
        elif "讨论分享" in self.content_name:
            self.course_type = CourseType.DISCUSSION_SHARE
        elif "问卷调研" in self.content_name:
            self.course_type = CourseType.QUESTION_RESEARCH
        else:
            self.course_type = CourseType.OTHER

    # @retry(retry=retry_if_exception_type(BusinessException), stop=stop_after_attempt(10), wait=wait_fixed(1),
    #        before_sleep=before_relogin)
    async def get_current_content_name(self):
        current_content = await self.get_elem_with_wait_by_xpath(10,
                                                                 "//div[@class='posCatalog_select posCatalog_active']//span[@class='posCatalog_name']",
                                                                 False)
        if not current_content:
            await self.refresh()
            # raise BusinessException("可能页面卡住，刷新重试！")
        if not await current_content.is_visible():
            await current_content.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)
        return await current_content.text_content() if current_content else ""

    async def handle_promission_tips(self):
        tips_elem = await self.get_elem_with_wait_by_xpath(3, "//div[@class='popDiv course-pop']")
        if tips_elem:
            xpath = await self.get_elem_by_xpath("//input[@class='agreeButton']")
            await xpath.click()
            await asyncio.sleep(1)
            await self.get_elem_by_xpath("//a[contains(@class, 'agreeStart') and text()='开始学习'][2]").click()

    async def handle_login_in_other_place(self):
        # 返回学习状态，False-退出学习；True-继续学习
        no_need_exit = True
        # detect.chaoxing.com 显示您的账号于14:48在一台谷歌内核浏览器设备登入章节页面。多终端登录可能会被判定异常学习。如非本人操作，请尽快修改密码
        if alert := await self.is_alert_present():
            if "多终端登录" in alert.message:
                # 在别处登录了，退出当前学习
                no_need_exit = False
        return no_need_exit

    async def _is_current_tab_finished(self):
        # 是否当前页面中的所有任务点都已完成
        ret = True
        all_unfinished_task_points = await self._get_all_unfinished_task_points()
        if all_unfinished_task_points:
            ret = False
            # TODO 目前对测验的处理逻辑是先跳过测验，所以此处认为遇到非视频的任务点都跳过！
            # for unfinished_task_point in all_unfinished_task_points:
            #     if self._is_task_point_contains_video(unfinished_task_point)[0]:
            #         # 含有视频
            #         ret = False
            #         break
            #     else:
            #         # TODO 不含有视频，可能是测验，目前的处理逻辑是跳过，所以认为完成了，后续要处理测验内容，需要在此处修改逻辑！
            #         continue
        return ret

    async def is_current_content_contains_tab(self):
        if tab_elem := await self.get_elem_by_xpath("//div[@id='prev_tab']"):
            if tab_elem and await tab_elem.is_visible():
                return True
        return False

    async def has_next_tab(self):
        return True if await self.get_next_tab() else False

    async def switch_tab(self):
        # 切换到下一个tab
        ret = False
        if next_tab_elem := await self.get_next_tab():
            if not await next_tab_elem.is_visible():
                await next_tab_elem.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
            try:
                await next_tab_elem.click()
                ret = True
            except:
                self.logger.error("切换tab失败！")
        return ret

    async def get_next_tab(self):
        return await self.get_elem_by_xpath("//div[@id='prev_tab']//li[@class='active']/following-sibling::li[1]")

    async def _is_task_point_contains_video(self, target_iframe_container_elem: Locator = None) -> Tuple[
        bool, Locator]:
        """
        判断第一个未完成的任务点是否包含视频，且返回任务点元素
        :param target_iframe_container_elem:  xpath=//div[contains(@class, 'ans-attach-ct')]的元素，若没传则默认判断第一个未完成的任务点是否包含视频
        :return:
        """
        try:
            ret = False
            first_unfinished_task_point = None
            main_iframe = self._switch_to_main_iframe()
            if main_iframe:
                first_unfinished_task_point = await self._get_first_unfinished_task_point(
                    main_iframe) if not target_iframe_container_elem else target_iframe_container_elem
                if first_unfinished_task_point:
                    class_attr = await first_unfinished_task_point.get_attribute("class")
                    if "videoContainer" in class_attr:
                        ret = True
            return ret, first_unfinished_task_point
        finally:
            # self.switch_to_default_content()
            pass

    def _switch_to_main_iframe(self):
        ret = False
        try:
            # self.switch_to_default_content()
            # iframe_elem = await self.get_elem_by_xpath("//iframe[@id='iframe']")
            # if iframe_elem:
            #     self.switch_to_frame(iframe_elem)
            #     ret = True
            ret = self.switch_to_frame("xpath=//iframe[@id='iframe']")
        except:
            self.logger.error("切换 //iframe[@id='iframe'] 失败")
            raise

        return ret

    async def _get_first_unfinished_task_point(self, iframe: FrameLocator = None) -> Locator:
        # 获取第一个未完成的任务点，调用该方法前需要切换到id="iframe"的iframe
        ret = None
        task_point_elems = await self.get_elems_by_xpath(
            "//div[contains(@class, 'ans-attach-ct')][./div[contains(@class,'ans-job-icon')]]", iframe)
        for task_point_elem in task_point_elems:
            class_attr = await task_point_elem.get_attribute("class")
            if "ans-job-finished" in class_attr:
                # 已完成
                continue
            else:
                ret = task_point_elem
                break
        return ret

    async def handle_exam_in_video(self):
        # 处理视频中含有考试
        try:
            # self.switch_to_default_content()
            # self.switch_to_frame("iframe")
            iframe = self._switch_to_main_iframe()
            first_unfinished_task_point = await self._get_first_unfinished_task_point(iframe)
            if first_unfinished_task_point:
                class_attr = await first_unfinished_task_point.get_attribute("class")
                if "videoContainer" in class_attr:
                    # 任务点包含视频，找到目标任务点，处理暂停
                    # target_iframe = self.get_relative_elem_by_xpath(first_unfinished_task_point, ".//iframe")
                    target_iframe = first_unfinished_task_point.frame_locator("xpath=.//iframe")
                    # target_iframe = self.get_elem((By.XPATH, "//iframe[@class='ans-attach-online ans-insertvideo-online']"))
                    if target_iframe:
                        # self.switch_to_frame(target_iframe)
                        # 每个在视频中弹出的题目上都有题目类型，此处获取题目类型，作为是否弹出做题的判断依据
                        xpath = "//div[@class='x-container ans-timelineobjects x-container-default']//div[@class='tkTopic_title']"
                        # if exam_type_elem := self.is_elem_visible((By.XPATH, xpath)):
                        if exam_type_elem := await self.is_elem_visible_by_xpath(xpath, target_iframe):
                            # 有做题
                            # 1.判断是多选还是单选
                            if "单选题" in await exam_type_elem.text_content() or "判断题" in await exam_type_elem.text_content():
                                # 获取选项
                                await self._choose_options(target_iframe)
                                # 选择完之后，再判断题目是否消失了，没有消失需要人工介入
                                if await self.is_elem_visible_by_xpath(xpath, target_iframe):
                                    self.logger.error("自动做题失败，请人工处理！")
                            else:
                                # 多选题
                                exam_type = "多选题"
                                # 多选题未实现，后续完成
                                self.logger.error("做题失败，多选题未实现，请人工处理！")
        finally:
            # self.switch_to_default_content()
            pass

    async def handle_pause(self):
        try:
            main_iframe = self._switch_to_main_iframe()
            if not main_iframe:
                return

            first_unfinished_task_point = await self._get_first_unfinished_task_point(main_iframe)
            if first_unfinished_task_point:
                # 任务点包含视频，找到目标任务点，处理暂停
                # video_iframe = self.get_relative_elem(first_unfinished_task_point, (By.XPATH, ".//iframe"))
                video_iframe = self.switch_to_frame("xpath=.//iframe", first_unfinished_task_point)
                # self.switch_to_frame(video_iframe)
                # 处理“继续学习”
                xpath = "//div[@class='sp_video_pic']//a[text()='继续学习']"
                if btn_continue := await self.get_elem_by_xpath(xpath, video_iframe):
                    await btn_continue.click()
                    self.first_cal_time_flag = True
                    self.logger.info("处理【继续学习】成功！")
                    await asyncio.sleep(1)  # 等待处理完成
                    return  # 处理完直接返回，有其他的暂停后续再处理

                # 处理“暂停”
                video_container = await self.get_elem_by_xpath("//div[@id='reader']/div", video_iframe)
                if not video_container:
                    return

                class_attr = await video_container.get_attribute("class")
                if "vjs-has-started" not in class_attr:
                    # 播放未开始，说明目前处在暂停状态
                    xpath = "//button[@class='vjs-big-play-button']"
                    btn_play = await self.get_elem_by_xpath(xpath, video_iframe)
                    await self.wait_for_disappeared(2, btn_play)
                    video_container = await self.get_elem_by_xpath("//div[@id='reader']/div", video_iframe)
                    class_attr = await video_container.get_attribute("class")
                    if "vjs-has-started" not in class_attr:
                        btn_play = await self.get_elem_by_xpath(xpath, video_iframe)
                        if btn_play and await btn_play.is_enabled():
                            if not await btn_play.is_visible():
                                await btn_play.scroll_into_view_if_needed()
                                await asyncio.sleep(0.5)
                            await btn_play.click()
                            self.first_cal_time_flag = True
                            self.logger.info("处理【暂停】成功！")
                else:
                    # 播放已开始，处理视频中途被暂停的情况
                    if btn_pause := await self.is_elem_visible_by_xpath(
                            "//div[@class='vjs-control-bar']/button[contains(@class,'vjs-paused')]", video_iframe):
                        await btn_pause.click()
                        self.first_cal_time_flag = True
                        self.logger.info("处理【暂停】成功！")
        finally:
            # self.switch_to_default_content()
            pass

    async def _get_job_id(self):
        job_id = ""
        try:
            # self.switch_to_default_content()
            # self.switch_to_frame("iframe")
            iframe = self._switch_to_main_iframe()
            first_unfinished_task_point = await self._get_first_unfinished_task_point(iframe)
            if first_unfinished_task_point:
                # 任务点包含视频，找到目标任务点
                task_point_iframe = await self.get_relative_elem_by_xpath(first_unfinished_task_point, ".//iframe")
                job_id = await task_point_iframe.get_attribute("jobid")
            return job_id
        finally:
            # self.switch_to_default_content()
            pass

    async def _get_played_time_and_total_time(self):
        ret = None, None
        try:
            # self.switch_to_default_content()
            # self.switch_to_frame("iframe")
            iframe = self._switch_to_main_iframe()
            first_unfinished_task_point = await self._get_first_unfinished_task_point(iframe)
            if first_unfinished_task_point:
                # 任务点包含视频，找到目标任务点，处理暂停
                # video_iframe = self.get_relative_elem_by_xpath(first_unfinished_task_point, ".//iframe")
                video_iframe = self.switch_to_frame("iframe", first_unfinished_task_point)
                # self.switch_to_frame(video_iframe)
                played_time_js = "document.querySelector(\"%s\").textContent}" % "span[class='vjs-current-time-display']"
                total_time_js = "document.querySelector(\"%s\").textContent}" % "span[class='vjs-duration-display']"
                # played_time: str = self.execute_js(played_time_js, video_iframe)
                # total_time: str = self.execute_js(total_time_js, video_iframe)
                # video_iframe.evaluate(played_time_js)
                # played_time: str = await video_iframe.owner.evaluate(played_time_js)
                # total_time: str = await video_iframe.owner.evaluate(total_time_js)
                played_time_elem = await self.get_elem_by_css("span[class='vjs-current-time-display']", video_iframe)
                played_time: str = await played_time_elem.text_content()
                played_time_elem = await self.get_elem_by_css("span[class='vjs-duration-display']", video_iframe)
                total_time: str = await played_time_elem.text_content()
                ret = self.format_time(played_time), self.format_time(total_time)
        except:
            # 没有找到已经播放完的时间
            self.logger.exception(
                "【%s】没有获取到时间，可能为非视频页面，或者页面出现异常！" % self.content_name)
            # 刷新一次页面
            await self.refresh()
        finally:
            # self.switch_to_default_content()
            pass

        return ret

    def format_time(self, time: str):
        # 格式化时间为：HH:MM:SS
        ret = time
        if len(time) < 5:
            ret = "00:" + time.rjust(5, "0")
        elif len(time) < 6:
            ret = "00:" + time
        elif len(time) < 8:
            ret = time.rjust(8, "0")
        return ret

    async def get_next_content(self):
        # 该xpath会选择积分点大于1的目录
        # xpath = "//li[./div[@class='posCatalog_select posCatalog_active']]/following::li[./div[@class='posCatalog_select']][.//span[@class='orangeNew' and text()>0]][1]"
        # 该xpath会选择所有的目录
        xpath = "//li[./div[@class='posCatalog_select posCatalog_active']]/following::li[./div[@class='posCatalog_select']][.//span[@class='orangeNew']][1]"
        return await self.get_elem_by_xpath(xpath)

    async def enter_next_content(self):
        ret = False
        if next_content := await self.get_next_content():
            if not await next_content.is_visible():
                await next_content.scroll_into_view_if_needed()
                await asyncio.sleep(0.5)
            await next_content.click()
            self.first_cal_time_flag = True
            ret = True
        return ret

    def _cal_time(self, time_str) -> int:
        time_segs = time_str.split(":")
        hour = 0
        minute = time_segs[0]
        seconds = time_segs[1]
        if len(time_segs) > 2:
            hour, minute, seconds = time_segs
        return int(hour) * 3600 + int(minute) * 60 + int(seconds)

    async def _read_docs(self, iframe: FrameLocator, iframe_object_id):
        # 需要先切换到任务点的iframe下
        docs_iframe: FrameLocator = iframe.frame_locator("//iframe[@id='panView']")
        if not docs_iframe:
            self.logger.error("没有找到文档的iframe：//iframe[@id='panView']")
            return

        docs_iframe = self.switch_to_frame("xpath=//iframe[@id='panView']", iframe)
        body = await self.get_elem_with_wait_by_css(10,"body", iframe=docs_iframe)
        while not await self._is_current_point_task_finished(iframe_object_id):
            # 切换到文档的iframe下
            # self._switch_to_main_iframe()
            # self.switch_to_frame(0)
            # self.switch_to_frame(docs_iframe)
            # 滚动页面
            scroll_len = random.randint(200, 600)
            # self.web_browser.execute_script("window.scrollBy(0,%d)" % scroll_len)
            # await docs_iframe.owner.evaluate("window.scrollBy(0,%d)" % scroll_len)
            await body.evaluate("window.scrollBy(0,%d)" % scroll_len)
            await asyncio.sleep(2)

        self.logger.info("已读完文档")

    async def _is_current_point_task_finished(self, object_id):
        ret = False
        # self._switch_to_main_iframe()
        xpath = f"//iframe[@objectid='{object_id}']/parent::div"
        if task_point_div := await self.get_elem_by_xpath(xpath, iframe=self._switch_to_main_iframe()):
            if "ans-job-finished" in await task_point_div.get_attribute("class"):
                ret = True
        # self.switch_to_default_content()
        return ret

    async def handle_exam_task_point(self):
        # 处理测验的任务点
        # self._switch_to_main_iframe()
        # self.switch_to_frame(0)
        main_iframe = self._switch_to_main_iframe()
        target_iframe = main_iframe.frame_locator("iframe").nth(0)
        # target_iframe = self.switch_to_frame("iframe:nth-child(1)", main_iframe)
        handler = ChaoXingExamHandler(self, self.username, self.course_name, self.content_name, self.logger)
        result = await handler.do_exam(target_iframe)
        if not result:
            # 跳过课程，将课程名写入输出数据中
            self.set_output_data("skip_course", self.course_name)
            # 处理测验失败！，目前采用跳过处理
            if self.user_mode == 1:
                self.user_manager.update_record_by_username(self.username,
                                                            {5: "处理非视频任务点失败，需人工完成！"},
                                                            False)
            else:
                self.logger.warning("处理非视频任务点失败，需人工完成！")

    async def _switch_next_task_point(self):
        if await self.is_current_content_contains_tab() and await self.has_next_tab():
            # 处理带有多个tab的页面
            await self.switch_tab()
        else:
            await self.refresh()
            if next_content := await self.get_next_content():
                if not await next_content.is_visible():
                    await next_content.scroll_into_view_if_needed()
                    await asyncio.sleep(0.5)
                await next_content.click()
                await asyncio.sleep(2)
                # 目录名称
                self.content_name = await self.get_current_content_name()
                self.first_cal_time_flag = True
            else:
                # 没有下一个任务，则退出
                self.terminate("当前课程已完成！")

    async def _get_all_unfinished_task_points(self):
        # 获取当前页面中未完成的任务点
        ret = list()
        try:
            task_points = await self.get_elems_by_xpath(
                "//div[contains(@class, 'ans-attach-ct')][./div[contains(@class,'ans-job-icon')]]",
                self._switch_to_main_iframe())
            for task_point in task_points:
                class_attr = await task_point.get_attribute("class")
                if "ans-job-finished" in class_attr:
                    continue
                else:
                    # 未完成的添加到返回列表中
                    ret.append(task_point)
            return ret
        finally:
            # self.switch_to_default_content()
            pass

    async def _choose_options(self, iframe: FrameLocator):
        submit_btn = await self._get_submit_button(iframe)
        pre_title = await self._get_exam_title(iframe)
        options = await self._get_exam_options(iframe)
        for option in options:
            max_retry_count = 10
            await option.click()
            await asyncio.sleep(0.5)
            await submit_btn.click()
            await asyncio.sleep(0.5)
            while max_retry_count > 0:
                # 最多等待5秒，检测回答是否正确
                if await self._is_answer_correct(pre_title, iframe):  # 答案正确，跳出循环
                    return
                await asyncio.sleep(0.5)
                max_retry_count -= 1
            # 获取回答错误的提示，没有提示错误，说明回答正确
            # error_tip = self.get_elem_with_wait(2, (By.XPATH, "//span[@id='spanNot']"), True)
            # if not error_tip:
            #     break
            # time.sleep(0.5)

    async def _get_submit_button(self, iframe: FrameLocator):
        return await self.get_elem_by_xpath(
            "//div[@class='x-container ans-timelineobjects x-container-default']//a[@id='videoquiz-submit']", iframe)

    async def _get_exam_title(self, iframe):
        # 获取题目
        title_elem = await self.get_elem_by_xpath(
            "//div[@class='x-container ans-timelineobjects x-container-default']//div[@class='tkItem_title']", iframe)
        return "" if not title_elem else title_elem.text_content()

    async def _get_exam_options(self, iframe):
        return await self.get_elems_by_xpath(
            "//div[@class='x-container ans-timelineobjects x-container-default']//li[@class='ans-videoquiz-opt']//span[@class='tkRadio']",
            iframe)

    async def _is_exam_title_changed(self, pre_exam_title, iframe):
        return True if pre_exam_title != await self._get_exam_title(iframe) else False

    async def _is_answer_correct(self, pre_exam_title, iframe):
        return await self._is_exam_title_changed(pre_exam_title, iframe)

    async def _enter_read_page(self):
        outer_iframe = self.switch_to_frame("iframe#iframe")
        iframe1 = self.switch_to_frame("iframe", outer_iframe)
        iframe2 = self.switch_to_frame("iframe#frame_content", iframe1)
        read_btn = await self.get_elem_with_wait_by_xpath(20, "//span[text()='去阅读']", iframe=iframe2)
        if not read_btn:
            self.logger.error("在“拓展阅读”页面没有找到“去阅读”的按钮，刷新页面！")
            # self.terminate("页面异常", True)
            # “拓展阅读”页面没有找到“去阅读”按钮，刷新页面
            await self.refresh()
            return

        await self.js_click(read_btn)
        await asyncio.sleep(3)
        windows = await self.get_windows_by_url_key("mooc-ans")
        self.reading_page = windows[0]
        await self.switch_to_window(self.reading_page)
        first_chapter = await self.get_elem_with_wait_by_xpath(10, "(//ul//div[contains(@class,'chapterText')])[1]")
        if first_chapter:
            if not await first_chapter.is_visible():
                await first_chapter.scroll_into_view_if_needed()
                await asyncio.sleep(1)

            await self.js_click(first_chapter)

        self.read_start_time = int(time.time())
        self.read_end_time = self.read_start_time + self.read_time_require

    async def _handle_extend_reading(self, iframe):
        read_btn = await self.get_elem_with_wait_by_xpath(20, "//span[text()='去阅读']", iframe=iframe)
        if not read_btn:
            self.logger.error("在“拓展阅读”页面没有找到“去阅读”的按钮，刷新页面！")
            # self.terminate("页面异常", True)
            # “拓展阅读”页面没有找到“去阅读”按钮，刷新页面
            await self.refresh()
            return

        await self.js_click(read_btn)
        await asyncio.sleep(3)

        windows = await self.get_windows_by_url_key("mooc-ans")
        self.reading_page = windows[0]
        await self.switch_to_window(self.reading_page)

        first_chapter = await self.get_elem_with_wait_by_xpath(10, "(//ul//div[contains(@class,'chapterText')])[1]")
        if first_chapter:
            if not await first_chapter.is_visible():
                await first_chapter.scroll_into_view_if_needed()
                await asyncio.sleep(1)

            await self.js_click(first_chapter)
        # 阅读文档，等待self.read_time_require后退出
        await asyncio.sleep(1)
        await self._read_doc()
        await self.close_window(self.reading_page)
        await self.switch_to_window(self.course_page)
        await asyncio.sleep(0.5)
        await self.refresh()

    async def _read_doc(self):
        self.read_start_time = int(time.time())
        self.read_end_time = self.read_start_time + self.read_time_require
        while int(time.time()) < self.read_end_time:
            # 阅读逻辑
            scroll_len = random.randint(15, 40)
            await self.execute_js("() => {window.scrollBy(0, %d)}" % scroll_len)
            self.total_scroll_count += scroll_len
            next_page = await self.get_elem_by_xpath("//a[@class='ml40 nodeItem r'] | //a[@id='loadbutton']")
            if next_page and await next_page.is_enabled() and await next_page.is_visible():
                await next_page.click()
            self.logger.info(f"拓展阅读，已经阅读：{int(time.time())-self.read_start_time}秒")
            await asyncio.sleep(random.randint(1, 5))
        # if next_page:
        #     box = await next_page.bounding_box()
        #     if self.total_scroll_count >= box["y"]:
        #         try:
        #             # next_page.click()
        #             # self.execute_js("arguments[0].click()", next_page)
        #             await self.js_click(next_page)
        #         except:
        #             pass
        #         else:
        #             await asyncio.sleep(1)
        #             await self.wait_for_disappeared(4, next_page)
        # else:
        #     doc_content = await self.get_elem_with_wait_by_xpath(10, "//div[@id='caContentBox']")
        #     if not doc_content:
        #         raise Exception("【%s】目录页不存在" % self.content_name)
        #
        #     box = await doc_content.bounding_box()
        #     if self.total_scroll_count >= box["height"]:
        #         self._switch_to_next_content()

    async def _handle_discussion_share(self):
        """
        处理讨论分享！
        :return:
        """
        # 直接切换到下一个任务点
        # await self._switch_next_task_point()
        pass

    async def _handle_question_research(self):
        # 直接切换到下一个任务点
        # await self._switch_next_task_point()
        pass
