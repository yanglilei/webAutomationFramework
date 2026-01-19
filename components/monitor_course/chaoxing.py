import os
import random
import time
from dataclasses import dataclass
from typing import Tuple, List

from cozepy import MessageObjectString, Message
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement

from src.frame.base.base_monitor_course_node import BaseMonitorCourseTaskNode
from src.utils.coze_api import CommonEDUAgent
from src.utils.qiniu_utils import FileOperatorResult, UploadFileOperator
from src.utils.sys_path_utils import SysPathUtils


class ChaoXingExamHandler:
    def __init__(self, web_operator, username_showed, course_name, content_name, logger):
        """
        超星测验处理器
        CX=超星
        需要先切换到任务点下的iframe
        :param web_operator: web_operator
        """
        self.web_operator = web_operator
        self.username_showed = username_showed
        self.course_name = course_name
        self.content_name = content_name
        self.logger = logger

    def _switch_to_exam_iframe(self):
        """
        切换到测验的iframe
        :return:
        """
        ret = True
        exam_iframe = self.web_operator.get_elem((By.XPATH, "//iframe[@id='frame_content']"))
        if not exam_iframe:
            ret = False
        self.web_operator.switch_to_frame(exam_iframe)
        return ret

    def _get_all_questions(self) -> List[Tuple[str, WebElement]]:
        all_questions = self.web_operator.get_elems((By.XPATH, "//div[contains(@class, 'singleQuesId')]"))
        return [(question.text, question) for question in all_questions]

    def do_exam(self) -> bool:
        """
        做测验，需要先切换到任务点下的iframe
        :return:  True-做测验成功；False-做测验失败
        """
        ret = True
        try:
            if not self._switch_to_exam_iframe():
                self.logger.info(
                    "用户【%s】切换到测验的iframe（//iframe[@id='frame_content']）失败，退出测验！" % self.username_showed)
                ret = False
            else:
                # 获取所有的题目
                self.all_questions = self._get_all_questions()
                if self.all_questions:
                    for question_text, question_elem in self.all_questions:
                        if not question_elem.is_displayed():
                            question_elem.location_once_scrolled_into_view
                            time.sleep(0.5)
                        if "单选题" in question_text:
                            # 做单选题
                            ret = self._do_single_answer(question_elem)
                        elif "多选题" in question_text:
                            # 做多选题
                            ret = self._do_multiple_answer(question_elem)
                        elif "判断题" in question_text:
                            # 做判断题
                            ret = self._do_judge_answer(question_elem)
                        elif "填空题" in question_text:
                            # 做填空题
                            ret = False
                            self.logger.error(
                                "填空题未实现：%s，位置：【%s】_【%s】" % (question_text, self.course_name, self.content_name))
                            break
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
                        time.sleep(1)
                    # 提交
                    ret = self.submit()
        except:
            self.logger.exception(
                "用户【%s】在做测验出错！位置：【%s】_【%s】" % (self.username_showed, self.course_name, self.content_name))
            ret = False
        finally:
            self.web_operator.web_browser.switch_to.default_content()
        return ret

    def submit(self) -> bool:
        """
        提交
        :return: bool True-提交成功；False-提交失败
        """
        # 提交
        ret = True
        btn_submit = self.web_operator.get_elem((By.XPATH, "//a[@class='btnSubmit workBtnIndex']"))
        if btn_submit:
            if not btn_submit.is_displayed():
                btn_submit.location_once_scrolled_into_view
                time.sleep(0.5)
            btn_submit.click()
            self.web_operator.web_browser.switch_to.default_content()
            if commit_confirm := self.web_operator.wait_for_visible(3, (By.XPATH, "//a[@id='popok']")):
                self.web_operator.execute_js("arguments[0].click()", commit_confirm)
                # commit_confirm.click()
        else:
            self.logger.error("未找到提交按钮")
            ret = False
        return ret

    def _do_single_answer(self, question_elem: WebElement):
        # 单选题
        ret = False
        try:
            # 获取选项
            all_options = self.web_operator.get_relative_elems(question_elem,
                                                               (By.XPATH, ".//span[contains(@class, 'num_option')]"))
            # 1.获取正确答案，此处采用随机选择一个选项
            target_option = random.sample(all_options, 1)
            # 2.选择选项
            if not target_option[0].is_displayed():
                target_option[0].location_once_scrolled_into_view
                time.sleep(0.5)
            target_option[0].click()
            time.sleep(0.5)
        except:
            self.logger.exception(
                "用户【%s】在做测验出错！位置：【%s】_【%s】" % (self.username_showed, self.course_name, self.content_name))
            ret = False
        return ret

    def _do_multiple_answer(self, question_elem: WebElement):
        # 多选题
        ret = False
        try:
            # 获取选项
            all_options = self.web_operator.get_relative_elems(question_elem,
                                                               (By.XPATH, ".//span[contains(@class, 'num_option')]"))
            # 1.获取正确答案，此处采用随机选择一个选项
            target_options = random.sample(all_options, random.randint(1, len(all_options)))
            # 2.选择选项
            for target_option in target_options:
                if not target_option.is_displayed():
                    target_option.location_once_scrolled_into_view
                    time.sleep(0.5)
                target_option.click()
                time.sleep(0.5)
        except:
            self.logger.exception(
                "用户【%s】在做测验出错！位置：【%s】_【%s】" % (self.username_showed, self.course_name, self.content_name))
            ret = False

        return ret

    def _do_judge_answer(self, question_elem: WebElement):
        # 判断题
        return self._do_single_answer(question_elem)

    def _do_fill_answer(self, question_elem: WebElement):
        # 填空题
        pass

    def _do_short_answer(self, question_elem: WebElement):
        # TODO 待完善！简答题
        xpath = "//div[@class='clearfix font-cxsecret fontLabel']"
        ret = False
        try:
            # 获取选项
            title_elem = self.web_operator.get_relative_elem(question_elem, (By.XPATH, xpath))
            # 1.截图
            filename = self.username_showed + str(random.randint(10000000, 99999999)) + ".png"
            local_file = os.path.join(SysPathUtils.get_root_dir(), filename)
            self.web_operator.web_browser.save_screenshot(local_file)
            # 2.上传到七牛
            result: FileOperatorResult = UploadFileOperator().upload(str(local_file), filename)
            # result.resource_url
            # 3.发送给智能体
            MessageObjectString.build_image(result.resource_url)
            reply_content = CommonEDUAgent().get_reply(
                [Message.build_user_question_objects([MessageObjectString.build_image(file_url=result.resource_url),
                                                      MessageObjectString.build_text(
                                                          "我是一位中小学教师，附件的图中是一道题目，请以我的视角解答。要求：直接输出文字，不添加任何格式（包括markdown格式）")]),
                 ])

            paragraphs = reply_content.split("\n")
            formatted_prompts = []
            for paragraph in paragraphs:
                formatted_prompts.append(f"<p>{paragraph.strip()}</p>")
            # 3.填写答案
            # 切换到输入框iframe
            xpath = ".//div[@id='edui1']//iframe"
            editor_iframe = self.web_operator.get_relative_elem(question_elem, (By.XPATH, xpath))
            self.web_operator.switch_to_frame(editor_iframe)
            input_body = self.web_operator.get_elem((By.XPATH, "//body[@class='view']"))
            js_code = f"arguments[0].innerHTML='{''.join(formatted_prompts)}'"
            # 写入输入框
            # 往body中写入内容，添加<p>标签的内容作为一个段落。
            self.web_operator.web_browser.execute_script(js_code, input_body)
        except:
            self.logger.exception(
                "用户【%s】在做测验出错！位置：【%s】_【%s】" % (self.username_showed, self.course_name, self.content_name))
            ret = False

        return ret

    def _choose_options(self, all_options: List[WebElement]):
        pass


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

    def single_poll_monitor(self):
        # 目录名称
        self.content_name = self.get_current_content_name()
        # 处理在别处登录
        if not self.handle_login_in_other_place():
            self.terminate("在别处登录")
            return

        if self._is_current_tab_finished():
            self._switch_next_task_point()
            return

        flag, task_point_elem = self._is_task_point_contains_video()
        if flag:  # 包含视频
            self.handle_exam_in_video()  # 处理视频中含有测验（选择题）
            self.handle_pause()  # 处理视频暂停
            self.cur_job_id = self._get_job_id()
            if not self.pre_job_id:
                self.pre_job_id = self.cur_job_id
            # 当前视频的播放时间
            played_time, total_time = self._get_played_time_and_total_time()

            self.logger.info("用户【%s】【%s】总时长%s，已学习%s" % (
                self.username_showed, self.content_name, total_time, played_time))

            if played_time is None or total_time is None:
                if not self.is_page_load_error:
                    self.is_page_load_error = True
                    self.pre_refresh_time = int(time.time())
                else:
                    self.cur_refresh_time = int(time.time())
                    if self.cur_refresh_time - self.pre_refresh_time > 60:
                        self.is_page_load_error = False
                        # 获取时间失败（页面卡住没刷新出来），则重启该页面
                        self.logger.info(f"用户【{self.username_showed}】【{self.content_name}】获取时间失败，准备重启...")
                        self.terminate("获取时间失败，需要重启！")
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
                        self.logger.info("用户【%s】切换了视频任务点【%s】" % (self.username_showed, self.cur_job_id))
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
                        self.logger.info(
                            "用户【%s】【%s】卡住8分钟了，准备重启..." % (self.username_showed, self.content_name))
                        self.terminate("视频卡住8分钟了，需要重启！")
                        return
        else:  # 非视频，阅读文档或做测验等
            self._switch_to_main_iframe()
            iframe = self.get_relative_elem(task_point_elem, (By.XPATH, "./iframe"))
            if iframe and "insertdoc-online-pdf" in iframe.get_attribute("class"):
                # 阅读文档
                object_id = iframe.get_attribute("objectid")
                self.switch_to_frame(iframe)
                self._is_task_point_contains_read_docs(object_id)
            else:
                # 做测验
                self.handle_exam_task_point()

    def clean_up(self):
        super().clean_up()
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

    def get_current_content_name(self):
        current_content = self.get_elem_with_wait(10, (By.XPATH,
                                                       "//div[@class='posCatalog_select posCatalog_active']//span[@class='posCatalog_name']"),
                                                  False)
        if not current_content.is_displayed():
            current_content.location_once_scrolled_into_view
            time.sleep(0.5)
        return current_content.text if current_content else ""

    def handle_promission_tips(self):
        tips_elem = self.get_elem_with_wait(3, (By.XPATH, "//div[@class='popDiv course-pop']"))
        if tips_elem:
            self.get_elem((By.XPATH, "//input[@class='agreeButton']")).click()
            time.sleep(1)
            self.get_elem((By.XPATH, "//a[contains(@class, 'agreeStart') and text()='开始学习'][2]")).click()

    def handle_login_in_other_place(self):
        # 返回学习状态，False-退出学习；True-继续学习
        no_need_exit = True
        # detect.chaoxing.com 显示您的账号于14:48在一台谷歌内核浏览器设备登入章节页面。多终端登录可能会被判定异常学习。如非本人操作，请尽快修改密码
        if alert := self.is_alert_present():
            if "多终端登录" in alert.text:
                # 在别处登录了，退出当前学习
                no_need_exit = False
        return no_need_exit

    def _is_current_tab_finished(self):
        # 是否当前页面中的所有任务点都已完成
        ret = True
        all_unfinished_task_points = self._get_all_unfinished_task_points()
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

    def is_current_content_contains_tab(self):
        if tab_elem := self.get_elem((By.XPATH, "//div[@id='prev_tab']")):
            if tab_elem and tab_elem.is_displayed():
                return True
        return False

    def has_next_tab(self):
        return True if self.get_next_tab() else False

    def switch_tab(self):
        # 切换到下一个tab
        ret = False
        if next_tab_elem := self.get_next_tab():
            if not next_tab_elem.is_displayed():
                next_tab_elem.location_once_scrolled_into_view
                time.sleep(0.5)
            try:
                next_tab_elem.click()
                ret = True
            except:
                self.logger.error("用户【%s】切换tab失败！" % self.username_showed)
        return ret

    def get_next_tab(self):
        return self.get_elem((By.XPATH, "//div[@id='prev_tab']//li[@class='active']/following-sibling::li[1]"))

    def _is_task_point_contains_video(self, target_iframe_container_elem: WebElement = None) -> Tuple[
        bool, WebElement]:
        """
        判断第一个未完成的任务点是否包含视频，且返回任务点元素
        :param target_iframe_container_elem:  xpath=//div[contains(@class, 'ans-attach-ct')]的元素，若没传则默认判断第一个未完成的任务点是否包含视频
        :return:
        """
        try:
            ret = False
            first_unfinished_task_point = None
            if self._switch_to_main_iframe():
                first_unfinished_task_point = self._get_first_unfinished_task_point() if not target_iframe_container_elem else target_iframe_container_elem
                if first_unfinished_task_point:
                    class_attr = first_unfinished_task_point.get_attribute("class")
                    if "videoContainer" in class_attr:
                        ret = True
            return ret, first_unfinished_task_point
        finally:
            self.switch_to_default_content()

    def _switch_to_main_iframe(self):
        ret = False
        try:
            self.switch_to_default_content()
            iframe_elem = self.get_elem((By.XPATH, "//iframe[@id='iframe']"))
            if iframe_elem:
                self.switch_to_frame(iframe_elem)
                ret = True
        except:
            self.logger.error("用户【%s】切换 //iframe[@id='iframe'] 失败" % self.username_showed)
            raise

        return ret

    def _get_first_unfinished_task_point(self):
        # 获取第一个未完成的任务点，调用该方法前需要切换到id="iframe"的iframe
        ret = None
        task_point_elems = self.get_elems(
            (By.XPATH, "//div[contains(@class, 'ans-attach-ct')][./div[contains(@class,'ans-job-icon')]]"))
        for task_point_elem in task_point_elems:
            class_attr = task_point_elem.get_attribute("class")
            if "ans-job-finished" in class_attr:
                # 已完成
                continue
            else:
                ret = task_point_elem
                break
        return ret

    def handle_exam_in_video(self):
        # 处理视频中含有考试
        try:
            self.switch_to_default_content()
            self.switch_to_frame("iframe")
            first_unfinished_task_point = self._get_first_unfinished_task_point()
            if first_unfinished_task_point:
                class_attr = first_unfinished_task_point.get_attribute("class")
                if "videoContainer" in class_attr:
                    # 任务点包含视频，找到目标任务点，处理暂停
                    target_iframe = self.get_relative_elem(first_unfinished_task_point, (By.XPATH, ".//iframe"))
                    # target_iframe = self.get_elem((By.XPATH, "//iframe[@class='ans-attach-online ans-insertvideo-online']"))
                    if target_iframe:
                        self.switch_to_frame(target_iframe)
                        # 每个在视频中弹出的题目上都有题目类型，此处获取题目类型，作为是否弹出做题的判断依据
                        xpath = "//div[@class='x-container ans-timelineobjects x-container-default']//div[@class='tkTopic_title']"
                        if exam_type_elem := self.is_elem_visible((By.XPATH, xpath)):
                            # 有做题
                            # 1.判断是多选还是单选
                            if "单选题" in exam_type_elem.text or "判断题" in exam_type_elem.text:
                                # 获取选项
                                self._choose_options()
                                # 选择完之后，再判断题目是否消失了，没有消失需要人工介入
                                if self.is_elem_visible((By.XPATH, xpath)):
                                    self.logger.error("用户【%s】自动做题失败，请人工处理！" % self.username_showed)
                            else:
                                # 多选题
                                exam_type = "多选题"
                                # 多选题未实现，后续完成
                                self.logger.error("用户【%s】做题失败，多选题未实现，请人工处理！" % self.username_showed)
        finally:
            self.switch_to_default_content()

    def handle_pause(self):
        try:
            if not self._switch_to_main_iframe():
                return

            first_unfinished_task_point = self._get_first_unfinished_task_point()
            if first_unfinished_task_point:
                # 任务点包含视频，找到目标任务点，处理暂停
                video_iframe = self.get_relative_elem(first_unfinished_task_point, (By.XPATH, ".//iframe"))
                self.switch_to_frame(video_iframe)
                # 处理“继续学习”
                xpath = "//div[@class='sp_video_pic']//a[text()='继续学习']"
                if btn_continue := self.get_elem((By.XPATH, xpath)):
                    btn_continue.click()
                    self.first_cal_time_flag = True
                    self.logger.info("用户【%s】处理【继续学习】成功！" % self.username_showed)
                    time.sleep(1)  # 等待处理完成
                    return  # 处理完直接返回，有其他的暂停后续再处理

                # 处理“暂停”
                video_container = self.get_elem((By.XPATH, "//div[@id='reader']/div"))
                if not video_container:
                    return

                class_attr = video_container.get_attribute("class")
                if "vjs-has-started" not in class_attr:
                    # 播放未开始，说明目前处在暂停状态
                    xpath = "//button[@class='vjs-big-play-button']"
                    btn_play = self.get_elem((By.XPATH, xpath))
                    self.wait_for_disappeared(2, btn_play)
                    video_container = self.get_elem((By.XPATH, "//div[@id='reader']/div"))
                    class_attr = video_container.get_attribute("class")
                    if "vjs-has-started" not in class_attr:
                        btn_play = self.get_elem((By.XPATH, xpath))
                        if btn_play and btn_play.is_enabled():
                            if not btn_play.is_displayed():
                                btn_play.location_once_scrolled_into_view
                                time.sleep(0.5)
                            btn_play.click()
                            self.first_cal_time_flag = True
                            self.logger.info("用户【%s】处理【暂停】成功！" % self.username_showed)
                else:
                    # 播放已开始，处理视频中途被暂停的情况
                    if btn_pause := self.is_elem_visible(
                            (By.XPATH, "//div[@class='vjs-control-bar']/button[contains(@class,'vjs-paused')]")):
                        btn_pause.click()
                        self.first_cal_time_flag = True
                        self.logger.info("用户【%s】处理【暂停】成功！" % self.username_showed)
        finally:
            self.switch_to_default_content()

    def _get_job_id(self):
        job_id = ""
        try:
            self.switch_to_default_content()
            self.switch_to_frame("iframe")
            first_unfinished_task_point = self._get_first_unfinished_task_point()
            if first_unfinished_task_point:
                # 任务点包含视频，找到目标任务点
                task_point_iframe = self.get_relative_elem(first_unfinished_task_point, (By.XPATH, ".//iframe"))
                job_id = task_point_iframe.get_attribute("jobid")

            return job_id
        finally:
            self.switch_to_default_content()

    def _get_played_time_and_total_time(self):
        ret = None, None
        try:
            self.switch_to_default_content()
            self.switch_to_frame("iframe")
            first_unfinished_task_point = self._get_first_unfinished_task_point()
            if first_unfinished_task_point:
                # 任务点包含视频，找到目标任务点，处理暂停
                video_iframe = self.get_relative_elem(first_unfinished_task_point, (By.XPATH, ".//iframe"))
                self.switch_to_frame(video_iframe)
                played_time_js = "return document.querySelector(\"%s\").textContent" % "span[class='vjs-current-time-display']"
                total_time_js = "return document.querySelector(\"%s\").textContent" % "span[class='vjs-duration-display']"
                played_time: str = self.web_browser.execute_script(played_time_js)
                total_time: str = self.web_browser.execute_script(total_time_js)
                ret = self.format_time(played_time), self.format_time(total_time)
        except:
            # 没有找到已经播放完的时间
            self.logger.error("用户【%s】【%s】没有获取到时间，可能为非视频页面，或者页面出现异常！" % (self.username_showed,
                                                                                                 self.content_name))
            # 刷新一次页面
            self.refresh()
        finally:
            self.switch_to_default_content()

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

    def get_next_content(self):
        xpath = "//li[./div[@class='posCatalog_select posCatalog_active']]/following::li[./div[@class='posCatalog_select']][.//span[@class='orangeNew' and text()>0]][1]"
        return self.get_elem((By.XPATH, xpath))


    def enter_next_content(self):
        ret = False
        if next_content := self.get_next_content():
            if not next_content.is_displayed():
                next_content.location_once_scrolled_into_view
                time.sleep(0.5)
            next_content.click()
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

    def _is_task_point_contains_read_docs(self, iframe_object_id):
        # 需要先切换到任务点的iframe下
        docs_iframe = self.get_elem((By.XPATH, "//iframe[@id='panView']"))
        if not docs_iframe:
            self.logger.error("用户【%s】没有找到文档的iframe：//iframe[@id='panView']" % self.username_showed)
            return False

        while not self._is_current_point_task_finished(iframe_object_id):
            # 切换到文档的iframe下
            self._switch_to_main_iframe()
            self.switch_to_frame(0)
            self.switch_to_frame(docs_iframe)
            # 滚动页面
            scroll_len = random.randint(200, 600)
            self.web_browser.execute_script("window.scrollBy(0,%d)" % scroll_len)
            time.sleep(2)

        self.logger.info("用户【%s】已读完文档" % self.username_showed)

    def _is_current_point_task_finished(self, object_id):
        ret = False
        self._switch_to_main_iframe()
        xpath = f"//iframe[@objectid='{object_id}']/parent::div"
        if task_point_div := self.get_elem((By.XPATH, xpath)):
            if "ans-job-finished" in task_point_div.get_attribute("class"):
                ret = True
        self.switch_to_default_content()
        return ret

    def handle_exam_task_point(self):
        # 处理测验的任务点
        self._switch_to_main_iframe()
        self.switch_to_frame(0)
        result = ChaoXingExamHandler(self, self.username_showed, self.course_name, self.content_name, self.logger).do_exam()
        if not result:
            # 跳过课程，将课程名写入输出数据中
            self.set_output_data("skip_course", self.course_name)
            # 处理测验失败！，目前采用跳过处理
            self.user_manager.update_record_by_username(self.username,
                                                        {5: "处理非视频任务点失败，需人工完成！"},
                                                        False)
            # 防止还有未完成的测验，导致死循环！处理方式：切换到下一个任务点
            self._switch_next_task_point()

    def _switch_next_task_point(self):
        if self.is_current_content_contains_tab() and self.has_next_tab():
            # 处理带有多个tab的页面
            self.switch_tab()
        elif next_content := self.get_next_content():
            try:
                # 点击下一个目录
                self.execute_js("arguments[0].click();", next_content)
                self.first_cal_time_flag = True
            except:
                self.logger.info(
                    f"用户【{self.username_showed}】在【{self.course_name}】课程中【{self.content_name}】点击下一个目录失败，请手动点击！")
        else:
            # 达到最大时间，且没有下一个任务，则退出
            self.terminate("当前课程已完成！")

    def _get_all_unfinished_task_points(self):
        # 获取当前页面中未完成的任务点
        ret = list()
        try:
            if self._switch_to_main_iframe():
                task_points = self.get_elems(
                    (By.XPATH, "//div[contains(@class, 'ans-attach-ct')][./div[contains(@class,'ans-job-icon')]]"))
                for task_point in task_points:
                    class_attr = task_point.get_attribute("class")
                    if "ans-job-finished" in class_attr:
                        continue
                    else:
                        # 未完成的添加到返回列表中
                        ret.append(task_point)
            return ret
        finally:
            self.switch_to_default_content()

    def _choose_options(self):
        submit_btn = self._get_submit_button()
        pre_title = self._get_exam_title()
        options = self._get_exam_options()
        for option in options:
            max_retry_count = 10
            option.click()
            time.sleep(0.5)
            submit_btn.click()
            time.sleep(0.5)
            while max_retry_count > 0:
                # 最多等待5秒，检测回答是否正确
                if self._is_answer_correct(pre_title):  # 答案正确，跳出循环
                    return
                time.sleep(0.5)
                max_retry_count -= 1
            # 获取回答错误的提示，没有提示错误，说明回答正确
            # error_tip = self.get_elem_with_wait(2, (By.XPATH, "//span[@id='spanNot']"), True)
            # if not error_tip:
            #     break
            # time.sleep(0.5)

    def _get_submit_button(self):
        return self.get_elem((By.XPATH,
                              "//div[@class='x-container ans-timelineobjects x-container-default']//a[@id='videoquiz-submit']"))

    def _get_exam_title(self):
        # 获取题目
        title_elem = self.get_elem((By.XPATH,
                                    "//div[@class='x-container ans-timelineobjects x-container-default']//div[@class='tkItem_title']"))
        return "" if not title_elem else title_elem.text

    def _get_exam_options(self):
        return self.get_elems((By.XPATH,
                               "//div[@class='x-container ans-timelineobjects x-container-default']//li[@class='ans-videoquiz-opt']//span[@class='tkRadio']"))

    def _is_exam_title_changed(self, pre_exam_title):
        return True if pre_exam_title != self._get_exam_title() else False

    def _is_answer_correct(self, pre_exam_title):
        return self._is_exam_title_changed(pre_exam_title)


if __name__ == '__main__':
    obj = ChaoXingExamHandler("", "", "", "", "")
    print(obj)