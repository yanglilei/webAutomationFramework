from enum import Enum, auto

# 应用名称
APP_NAME = "小怪兽"
# 版本号
VERSION = "1.0.1"
# 是否需要激活
IS_NEED_ACTIVATION = False


class NodeState(Enum):
    """节点状态枚举"""
    READY = auto()
    RUNNING = auto()
    PAUSED = auto()
    WAITING = auto()
    COMPLETED = auto()
    FAILED = auto()


class ControlCommand(Enum):
    """外部控制命令枚举（可按需扩展）"""
    PAUSE = "暂停"  # 暂停节点
    RESUME = "继续"  # 继续节点
    WAKE_UP = "唤醒"  # 唤醒等待中的节点
    TERMINATE = "终止"  # 终止节点


class TaskResult(Enum):
    FINISHED = 0, "已学完！"
    CONTINUE = 1, "继续学习"


class SignUpSituation(Enum):
    """
    已注册
    未注册的情况，有两种
    """
    # 已注册
    COMPLETE_SIGN_UP = 0
    # 学校未知
    SCHOOL_UNKNOWN = 1
    # 信息未完善
    INFO_UNCOMPLETED = 2


class MsgCmd(Enum):
    """
    消息指令
    """
    # 切换课程
    CHANGE_COURSE = 1
    # 切换目录
    CHANGE_CONTENT = 2
    # 学习线程强制退出的指令。当目录切换线程异常退出的时候，通知学习线程强制退出
    LEARNING_THREAD_FORCE_EXIT = 3
    # 学习线收到线程强制退出指令的回复指令。学习线程收到目录切换线程的强制退出信号之后，给目录切换线程发出响应，确认收到强制退出的信号了
    LEARNING_THREAD_FORCE_EXIT_RESPONSE = 4
    # 目录切换线程退出的指令。当主线程（课程切换线）异常退出的时候，通知目录切换线程强制退出
    CHANGE_CONTENT_THREAD_FROCE_EXIT = 5
    # 目录切换收到线程强制退出指令的回复指令。
    CHANGE_CONTENT_THREAD_FORCE_EXIT_RESPONSE = 6
    # 课程切换线程退出
    CHANGE_COURSE_THREAD_FORCE_EXIT = 7
    # 目录切换线程需要重启的标志，当该线程异常退出的时候，会向父线程发送我需要重启的标志
    # 父线程收到该信息，会去重启子线程
    CHANGE_CONTENT_THREAD_NEED_TO_RESTART = 8
    # 学习线程需要重启的标志
    LEARNING_THREAD_NEED_TO_RESTART = 9
    # 任务监控线退出指令
    TASK_MONITOR_THREAD_EXIT = 10
    # 切换课程回复
    CHANGE_COURSE_RESPONSE = 11
    # 做作业
    FJRC_EXERCISE_MONITOR_THREAD_EXIT = 12
    # 跳过该课程
    SKIP_COURSE = 99
    # 工作线程退出指令
    WORK_THREAD_EXIT = 13


class QueueMsg():

    def __init__(self, msg_cmd: MsgCmd, *args):
        self.msg_cmd = msg_cmd
        self.args = args

    def get_args(self):
        return self.args

    def get_msg_cmd(self):
        return self.msg_cmd


class HXCourseType(Enum):
    """
    海西课程类型
    """
    PUB_COURSE = (1, "公需课")
    PRO_COURSE = (2, "专业课")


class Constants:
    """
    常量存放的位置
    """
    # 密钥，必须是16（AES-128）、24（AES-192）或32（AES-256）字节长
    SYS_KEY = "0F9C0D8F6F3EBFED55AAF185FDE3DF71"
    # 初始化向量，必须是16字节长
    SYS_IV = "834B6DB792870CCA"
    # 初始化向量，必须是16字节长
    iv = '834B6DB792870CCA'

    # mutex = Singleton.instance()
    # 鸿合获取当前目录学习完成的标志的key
    HONGHE_CURRENT_CONTENT_FINISHED_FLAG_KEY = "key_current_content_finished_flag"
    # 鸿合获取当前已完成的目录的名字的key
    HONGHE_CURRENT_FINISHED_CONTENT_NAME_KEY = "key_current_finished_content_name"
    # 鸿合获取当前课程学习完成的标志的key
    HONGHE_CURRENT_COURSE_FINISHED_FLAG_KEY = "key_current_course_finished_flag"

    # HONGHE_CURRENT_COURSE_FINISHED_FLAG_KEY = "key_current_course_finished_flag"
    # 鸿合获取用户名输入框的xpath表达式
    HONGHE_USERNAME_INPUT_XPATH = "//input[contains(@placeholder,'手机号') and @type='text']"
    # 鸿合获取密码输入框的xpath表达式
    HONGHE_PASSWORD_INPUT_XPATH = "//input[contains(@placeholder, '密码') and @type='password']"
    # 鸿合获取登录按钮的xpath表达式
    # HONGHE_LOGIN_BUTTON_XPATH = "//div/span[@class='btn_text']"
    HONGHE_LOGIN_BUTTON_XPATH = "(//div[contains(@class,'btn_c')])[1]"
    # 鸿合获取登录失败提示信息的xpath表达式
    HONGHE_LOGIN_ERROR_TIPS_XPATH = "//div[@class='error_tip']"

    # 鸿合获取姓名的xpath表达式：//div[@class='user']/span[1]/text()
    HONGHE_USER_REALNAME_XPATH = "(//div[@class='user']/span)[2]"

    # 用户未报名，弹窗的情况下，获取弹窗的xpath表达式：//div[@class='dialog_wrapper']
    HONGHE_USER_NO_SIGN_UP_COMPLETE_INFO_DIALOG = "//div[@class='dialog_wrapper']"

    # 鸿合获取当前目录学习完成的标志的xpath表达式
    HONGHE_CONTENT_LEARNING_FINISHED_XPATH = "//div[contains(@class,' selected') and  (./span[ contains(@class,'icon-radio-checked')])]"
    # 鸿合获取当前目录学习中提示框中的“我在“按钮的xpath表达式，需要点击”我在“按钮让学习继续
    HONGHE_CONTENT_LEARNING_INTERRUPT_IM_IN_XPATH = "//span[text()='我在']"
    # 鸿合获取当前学习目录的名字的xpath表达式
    HONGHE_CURRENT_LEARNING_CONTENT_NAME_XPATH = "./span[@class='common-s']"

    # 鸿合获取当前未完成的课程的xpath表达式
    HONGHE_CURRENT_UNFINISHED_COURSE_XPATH = "//div[@class='courseModuleBox' and not(child::div[contains(@class, " \
                                             "'cardShadeBox')]) and ((count(.//div[contains(@class," \
                                             "'learn_label_font')]//span)>1) or (count(.//div[contains(@class," \
                                             "'beforeDiv')]/div)=2))]"

    # 鸿合在课程页面，右上角名字处的xpath
    HONGHE_COURSE_PAGE_USERNAME_XPATH = "//app-userinfo[@class='userInfos']"
    # 获取提出按钮的xpath
    HONGHE_COURSE_PAGE_LOGOUT_XPATH = "//div[text()='退出']"
    # 鸿合课程中每个章节的位置xpath
    HONGHE_COURSE_CHAPTER_XPATH = "//div[contains(@class,'chaterpartent') and child::div[contains(@class,'iconClose')]]";
    # 鸿合获取课程中未读完的目录的xpath
    HONGHE_COURSE_UNFINISHED_CONTENTS_XPATH = "//div[./span[@class='icon-circle']]"
    # 鸿合获取视频重播按钮的xpath
    # HONGHE_CONTENT_REPEART_BUTTON_XPATH = "//span[text()='重播']"
    HONGHE_CONTENT_REPEART_BUTTON_XPATH = "//img[@src='assets/img/replay.svg']"
    # 鸿合用户未报名的情况下会出现立即报名的按钮的xpath
    HONGHE_USER_SIGN_UP_NOW_XPATH = "//span[@class='btn']"
    # 鸿合判断用户是否已经报名，页面上完成学时有出来表示已经报名成功了
    HONGHE_FINISHED_CLASS_HOUR_XPATH = "//span[@class='learnedHour']"
    # 下一页按钮
    HONGHE_LEARNING_PAGE_NEXT_CONTENT_BUTTON_XPATH = "//span[contains(@class,'nextBtn')]"
    # 当前正在读的目录名称
    HONGHE_LEARNING_PAGE_CURRENT_LEARNING_CONTENT_NAME_XPATH = "//div[contains(@class,'selected')]//span[contains(@class,'textTry')]"
    # 学习暂停按钮的xpath
    HONGHE_LEARNING_PAUSE_BUTTON_XPATH = "//img[@src='assets/img/pause.svg']"
    # 已经学完的时间的的xpath
    HONGHE_CURRENT_CONTENT_LEARN_SPEND_TIME_XPATH = "//*[@id='courseDetailBox']//span[@class='blueColor']"
    # 鸿合学习进度，有个百分比，100%表示学习完成，不确定任务是否完成
    HONGHE_USER_LEARNING_TOTAL_PROGRESS_XPATH = "//span[@class='studyPlanNumber']"
    # 研修分数
    HONGHE_USER_TRAINING_TASK_SCORE_XPATH = "//span[@class='star-des']"
    # 审核进度，未审核；已审核
    HONGHE_USER_TRAINING_AUDIT_PROGRESS_XPATH = "//span[contains(@class,'other')]"
    # 是否通过标志
    HONGHE_USER_LEARNING_PASS_XPATH = "//span[@class='passTxt']"
    #######
    # 急救 #
    #######
    # 用户名输入框xpath
    RCAT_USERNAME_INPUT_XPATH = "//input[@id='dd_user_name']"
    # 密码输入框xpath
    RCAT_PASSWORD_INPUT_XPATH = "//input[@id='dd_password']"
    # 登录按钮xpath
    RCAT_LOGIN_BUTTON_XPATH = "//a[@id='login_submit']"
    # 登录错误提示xpath
    RCAT_LOGIN_ERROR_TIPS_XPATH = "//div[contains(@class,'login-error-tip')]"
    # 获取用户基本信息的请求地址
    RCAT_USER_INFO_URL = "https://www.fjhszpx.com/fjhszpx/site/LoginAction!getUserPhoto.action"
    # 查看详情按钮的xpath，点击查看详情按钮进入到课程页面
    RCAT_COURSE_PAGE_XPATH = "(//a[text()='查看详情'])[1]"
    # 完善用户信息的页面地址
    RCAT_USER_INFO_COMPLETE_PAGE_URL = "https://www.fjhszpx.com/fjhszpx/site/VtcElectiveAction!completeMaterial.action?queryInfo.id=1023"
    # 课程中第一个未学完的目录的xpath
    RCAT_FIRST_LEARN_CONTENT_XPATH = "//div[contains(@class,'jindu_box')][not(div) or .//span[text()!=100]]/following-sibling::a[@class='study-vod']"
    # 课程中的第一节课的xpath，点击学习第一节课
    RCAT_FIRST_CONTENT_XPATH = "(//a[@class='study-vod'])[1]"
    # 当前目录已播放的时长
    RCAT_CURRENT_CONTENT_PLAY_TIME_XPATH = "//span[@class='dplayer-ptime']"
    # 当前目录总时长
    RCAT_CURRENT_CONTENT_TOTAL_TIME_XPATH = "//span[@class='dplayer-dtime']"
    # <span class="dplayer-time">
    # 	<span class="dplayer-ptime">03:27</span>
    # 	<span class="dplayer-dtime">21:12</span>
    # </span>
    # 第一个节点是已播放时长，第二个节点是总时长
    RCAT_CURRENT_CONTENT_PLAY_TIMES_XPATH = "//span[@class='dplayer-time']//span"
    # 点击下一节的按钮的xpath
    RCAT_NEXT_CONTENT_XPATH = "//a[@class='next-vod']"
    # 当前目录的信息
    RCAT_CURRENT_CONTENT_INFO_XPATH = "//li[contains(@class,'cur')]/a"
    # 最后一个目录的名称
    RCAT_LAST_CONTENT_NAME = "5.4开放性气胸的现场处理"
    # 视频的位置xpath
    RCAT_LEARN_PAGE_VIDEO_XPATH = "//video"
    # 当前目录的名称xpath
    RCAT_CURRENT_CONTENT_NAME_XPATH = "//h1"
    # 目录ID列表
    RCAT_CONTENT_ID_LIST = ["1242", "1264", "1241", "1263", "1262", "1284", "1240", "1261", "1283", "1260", "1282",
                            "1281", "1280", "1259", "1258", "1257", "1279", "1256", "1278", "1255", "1277", "1254",
                            "1276", "1253", "1275", "1252", "1274", "1251", "1273", "1250", "1272", "1271", "1270",
                            "1249", "1248", "1247", "1269", "1246", "1268", "1245", "1267", "1244", "1266", "1243",
                            "1265"]

    # class ExcpConstant:
    #     # 学习线程需要重启的标志，True-需要重启；False-不要重启。和上级的目录切换线程配合使用
    #     HONGHE_LEARNING_THREAD_NEED_TO_RESTART_FLAG = "learning_thread_need_to_restart_flag"
    #     # 目录切换线程需要重启的标志，True-需要重启；False-不要重启。和上级的课程切换线程配合使用
    #     HONGHE_CHANGE_CONTENTS_THREAD_NEED_TO_RESTART_FLAG = "change_contents_thread_need_to_restart_flag"
    #     # 学习线程需要退出的标志，True-退出；False-不退出
    #     HONGHE_LEARNING_THREAD_NEED_TO_EXIT_FLAG = "learning_thread_need_to_exit_flag"
    #     # 学习线程收到退出信号之后是否已回复的标志，目录切换线程需要等待获取到该标志，否则不能退出当前线程，True-已经回复；Fa4lse-未回复
    #     HONGHE_LEARNING_THREAD_EXIT_REPONSE_FLAG = "learning_thread_exit_response"

    ###########
    # 福建人才 #
    ##########
    # 滑块按钮的xpath，鼠标移至上方弹出滑块验证码
    FJRC_SLIDER_BUTTON_XPATH = r"//div[contains(@class,'ui-slider-btn')]"
    # 滑块图片的xpath
    FJRC_SLIDER_TARGET_IMG_XPATH = r"//img[@class='ui-slider-img-drag']"
    # 滑块验证码中背景图片的xpath
    FJRC_SLIDER_BACKGROUND_IMG_XPATH = r"//img[@class='ui-slider-img-back']"
    # 图片的宽度
    FJRC_SLIDER_TARGET_IMG_WIDTH = 50
    # 滑块移动按钮的宽度
    FJRC_SLIDER_MOVE_BUTTON_WIDTH = 38
    # 滑块验证码中背景图片的宽度
    FJRC_SLIDER_BACKGROUND_WIDTH = 298
    # 滑块验证码中背景图片的高度
    FJRC_SLIDER_BACKGROUND_HEIGHT = 120
    # 验证成功的xpath
    FJRC_SLIDER_VERIFY_SUCC_XPATH = r"//div[contains(@class,'ui-slider-text')]"
    # 用户名输入框xpath
    FJRC_USERNAME_INPUT_XPATH = r"//input[@id='login_account']"
    # 密码输入框xpath
    FJRC_PASSWORD_INPUT_XPATH = r"//input[@id='login_password']"
    # 登录按钮xpath
    FJRC_LOGIN_BUTTON_XPATH = r"//input[@id='login_submit']"
    # 登录失败的提示
    FJRC_LOGIN_FAIL_TIPS_XPATH = r"//p[@for='login_password']"

    # 未完成的包
    FJRC_UNFINISHED_PACKAGE_XPATH = "//ul[@class='list']/li[.//span[@class='exp-per'][text()!='100.00%']]"
    # 第一个要学习的课程
    FJRC_FIRST_LEARN_COURSE_XPATH = "(//ul[@class='list']/li)[1]"
    # 公告窗口
    # FJRC_ANNO_WINDOW_XPATH = "//div[@class='annunciate']"
    FJRC_ANNO_WINDOW_XPATH = "//div[@id='annunciate']"
    # 公告关闭按钮
    # FJRC_ANNO_CLOSE_BUTTON_XPATH = "//div[@class='annunciate-close']"
    FJRC_ANNO_CLOSE_BUTTON_XPATH = "//div[@class='annunciateImg-close'] | //div[@class='annunciate-close']"
    # https://fj.rcpxpt.com/classModule/video/1388178/1303011/5548262/0/0?videoIsBuy=0&pId=27170
    # https://fj.rcpxpt.com/classModule/video/1386473/1301306/5539516/0/0?videoIsBuy=0&pId=27170
    # 1386473：接口findPcLectrueById返回的报文中的moduleId字段
    # 1301306：接口findRequiredCourse返回的报文中的id字段
    # 5539516：接口queryLecturesByChapterId返回的报文中的id字段
    # pId：27170课程包ID
    FJRC_VIDEO_PAGE_URL_TMPL = "https://fj.rcpxpt.com/classModule/video/%s/%s/%s/0/0?videoIsBuy=0&pId=%s"

    FJRC_COURSE_DETAIL_PAGE_URL_TMPL = "https://fj.rcpxpt.com/sysConfigItem/selectDetail/%s?pId=%s"
    # 视频的位置xpath
    FJRC_LEARN_PAGE_VIDEO_XPATH = "//video"
    # 当前目录的名称xpath
    FJRC_CURRENT_CONTENT_NAME_XPATH = "//em[@id='shipin']"
    # 播放时间
    FJRC_CURRENT_CONTENT_PLAY_TIMES_XPATH = "//div[contains(@class,'pv-time-wrap')]/span"
    FJRC_CURRENT_CONTENT_PLAYED_TIME_CSS = "div[class='pv-time-wrap pv-xxsmall-hide'] span:nth-child(1)"
    FJRC_CURRENT_CONTENT_TOTAL_TIME_CSS = "div[class='pv-time-wrap pv-xxsmall-hide'] span:nth-child(3)"
    # 播放按钮
    FJRC_VIDEO_CENTER_PLAY_BUTTON_XPATH = "//span[contains(@class,'pv-icon-btn-play')]"
    # 打开多个学习窗口的时候，后打开的学习窗口在点击播放的时候会弹窗提示，此刻需要点击弹窗中的“我知道”按钮，让视频继续
    FJRC_ALERT_STOP_LEANING_I_KNOW_BUTTON_XPATH = "//a[contains(@class,'packageGoBtn')]"
    # 做题的时候提示是否继续做题，继续做题的按钮的xpath
    FJRC_CONTINUE_DO_EXERCISE_BUTTON_XPATH = "//button[contains(@class,'continue')]"
    # 弹出了暂停的对话框
    FJRC_PAUSE_ALERT_DISPLAY_XPATH = r"//div[contains(@class,'pause') and (@style='display: block;' or @style='')]"
    # 做题页面的地址
    # https://fj.rcpxpt.com/tikuUserBatch/keepTopic/33227843?testId=19103&commid=1327924
    # https://fj.rcpxpt.com/tikuUserBatch/keepTopic/33227844?testId=19002&commid=1323744
    # https://fj.rcpxpt.com/tikuUserBatch/keepTopic/33227845?testId=19103&commid=1327924
    FJRC_DO_EXERCISE_PAGE_URL = "https://fj.rcpxpt.com/tikuUserBatch/keepTopic/33201226"
    FJRC_READ_TOO_MUCH_ALERT = "//div[@class='layer-un-package-cont'][.//div[contains(text(), '您太勤奋了')]]"

    # 做题答案
    FJRC_EXERCISE_ANSWER = [("C",), ("B",), ("D",), ("A",), ("C",),
                            ("C",), ("D",), ("D",), ("B",), ("A",),
                            ("B",), ("A",), ("D",), ("B",), ("A",),
                            ("D",), ("A",), ("A",), ("C",), ("B",),
                            ("B", "C", "D"), ("A", "B", "C", "D", "E"),
                            ("C", "D", "E"), ("B", "E"), ("A", "B", "D"),
                            ("A", "C"), ("B", "C", "D"), ("A", "C", "D"),
                            ("A", "B", "C", "D", "E"), ("A", "D", "E"),
                            ("正确",), ("错误",), ("错误",), ("正确",), ("错误",), ("正确",), ("错误",), ("错误",),
                            ("正确",), ("错误",)]
    # 题目编号
    FJRC_EXERCISE_QUESTION_NO_XPATH = "//h5[@class='issueTitle']/b"
    # 题目描述信息，取text
    FJRC_EXERCISE_QUESTION_DESC_XPATH = "//h5[@class='issueTitle']"
    # 中的总共题目数
    FJRC_EXERCISE_TOTAL_COUNT_XPATH = "//b[@class='totalCount']"
    # 中的已经答题的数目
    FJRC_EXERCISE_ANSWER_COUNT_XPATH = "//i[@class='answerSize']"
    # 下一页按钮
    FJRC_EXERCISE_NEXT_QUESTION_XPATH = "//button[@class='next']"
    # 选择题的选项模板
    FJRC_EXERCISE_CHOICE_QUESTION_ITEM_TEMPL_XPATH = "//li[@optionno='%s']"
    # 判断题的选项模板
    FJRC_EXERCISE_TRUE_OR_FALSE_ITEM_TEMPL_XPATH = "//li[@optionno='%s']"
    # 已选的答案列表，获取text
    FJRC_EXERCISE_ANSWER_LIST_XPATH = "//div[@class='answer']//dd[@class='correct']//span"
    # 考试分数，获取text
    FJRC_EXERCISE_SCORE_XPATH = "//p[contains(@class,'resultWord')]/span[1]"

    # 课程列表页的地址，做的时候从这个页面点击做测验的位置进入到测验页面
    FJRC_COURSE_DETAIL_PAGE_URL = r"https://fj.rcpxpt.com/sysConfigItem/selectDetail/1323744?pId=26867"

    # 测验那一章节的标题xpath，点击展开之后才能获得测验的那一栏
    FJRC_CHAPTER_WITCH_CONTIANS_EXERCISE_XPATH = r"//a[following-sibling::ul//span[contains(@title, '测验')]]"
    # 所有章节的位置，都点击展开，目的为查到带有测验的目录
    FJRC_CHAPTER_XPATH = "//a[@class='chapter-btitle']"

    # 测验那一栏的xpath，点击进入做测验
    # FJRC_EXERCISE_CONTENT_XPATH = r"//li[contains(.//span/@title,'测验')]"
    FJRC_EXERCISE_CONTENT_XPATH = r"//li[.//em[contains(@class,'L-itest')]]"

    class ConfigFileKey:
        # 用户信息
        TOKEN = "token"
        # 全局
        GLOBAL_CHROME_POSITION = "global_chrome_position"
        # 激活状态
        ACTIVATE_STATUS = "activate_status"
        # 用户信息文件路径
        LATEST_USER_INFO_FILE_DIR_NAME = "user_info_file_dir"
        # 表格中最近打开的数据表路径
        LATEST_DATA_FILE_DIR_NAME = "latest_data_file_dir_name"
        # 默认登录间隔
        DEFAULT_LOGIN_INTERVAL = "default_login_interval"
        # 默认线程处理数量
        DEFAULT_PROCESSOR_COUNT = "default_processor_count"
        # 日志记录在本地文件的标志，1-记录
        LOG_LOCAL_FLAG = "log_local_flag"
        # 测验答案的key，%s为测验ID
        FJRC_EXERCISE_ANSWER_TMPL = "fjrc_answer_%s"
        # 课程包中选修课的课程名称，多个课程用英文逗号分割，%s为课程包ID
        FJRC_ELECTIVE_COURSES_TMPL = "fjrc_%s_elective_courses"
        # 课程中包含测验标志的key，%s为课程的commodityId。值=1标识，课程中包含测验
        FJRC_COURSE_CONTAINS_EXERCISE_FLAG_TMPL = "fjrc_course_%s_contains_exercise_flag"
        # 海峡证书保存目录
        FJRC_CERT_SAVE_DIR = "fjrc_cert_save_dir"
        # 海西章节名称
        FJHX_CHAPTER_NAMES_TMPL = "fjhx_%s_lecture_names"
        # 教育网选修课
        FJEDU_TEACHER_ELECTIVE_COURSES = "fjedu_teacher_elective_courses"
        # 学习公社课程类型
        XXGS_COURSE_TYPE = "xxgs_course_type"
        # edge和chrome切换
        WEB_DRIVER_TYPE = "webdriver_type"
        # 无头模式
        FJEDU_HEADLESS_MODE = "headless_mode"
        # 无痕模式
        INCOGNITO_MODE = "incognito_mode"
        # 教育网排除课程列表的key
        FJEDU_EXCLUDED_COURSES = "fjedu_exclude_courses"
        # 教育网登录间隔
        FJEDU_LOGIN_INTERVAL = "fjedu_login_interval"
        # 教育网目标项目ID
        FJEDU_TARGET_PROJECT_ID = "fjedu_target_project_id"
        # 海西登录间隔
        FJHX_LOGIN_INTERVAL = "fjhx_login_interval"
        # 海西任务处理器个数
        FJHX_TASK_PROCESSOR_COUNT = 'fjhx_task_processor_count'
        # 日志输出频率样本，样本值=3，表示每3次输出1次
        LOG_FREQUENCY_SAMPLE = "log_frequency_sample"
        # 新课标题库
        XKB_QUESTION_BANK_PREFIX = "xkb_question_bank_"
        # 新课标答题间隔
        XKB_INTERVAL = "xkb_interval"
        # 新课标题目编号
        XKB_QUESTION_NO = "xkb_exam_question_no_xpath"
        # 新课标下一题
        XKB_NEXT_SUBJECT = "xkb_exam_next_subject_btn_xpath"
        # 新课标测试的题目
        XKB_SUBJECT_TITLE = "xkb_exam_subject_title_xpath"
        # 新课标测试的所有选项，备选1
        XKB_ALL_ITEMS_1 = "xkb_exam_all_items_in_subject_1_xpath"
        # 新课标测试的所有选项，备选2
        XKB_ALL_ITEMS_2 = "xkb_exam_all_items_in_subject_2_xpath"
        # 新课标测试的答案模板
        XKB_ANSWER = "xkb_exam_answer_item_in_subject_xpath_tmpl"
        # 新课标测试的默认答案
        XKB_DEFAULT_ANSWER = "xkb_exam_default_answer_item_in_subject_xpath"
        # 新课标测试的课程类型
        XKB_PACKAGE_COURSE_TYPE = "xkb_package_course_type"
        # 新课标测试的chrome位置
        XKB_CHROME_POSITION = "xkb_chrome_position"
        # 新课标测试模式
        XKB_TEST_MODE = "xkb_test_mode"
        # 海西区域，多个值用英文逗号分开
        FJHX_AREAS = "fjhx_areas"
        # 59iedu区域
        EDU59I_AREAS = "edu59i_areas"
        # 59iedu课程名称
        EDU59I_COURSE_NAMES = "edu59i_course_names"
        # 福师大课程
        FJSD_PROJECT_NAME = "fjsd_project_name"
        # 共读登录间隔
        GD_LOGIN_INTERVAL = "gd_login_interval"
        # 智慧平台课程配置信息
        SMTEDU_COURSES_TMPL = "smtedu_courses_%s"
        # 项目ID
        SMTEDU_PROJECT_ID = "smtedu_project_id"
        # 继续教育-公共课题库
        FJJXEDU_GGK_ANSWER = "fjjxedu_ggk_answer"
        # 福建教育是否跳过文档的标志。1-跳过；0-不跳过
        FJJX_SKIP_DOC_FLAG = "fjjx_skip_doc_flag"
        # 福师大通识选课课程
        FJSD2_GE_CHOOSE_COURSE_NAMES = "fjsd2_ge_choose_course_names"
        # 福师大通识课最大选课数量
        FJSD2_GENERAL_COURSE_MAX_CHOOSE_COURSE_COUNT = "fjsd2_general_course_max_choose_course_count"
        # 福师大专业课最大选课数量
        FJSD2_PROFESSIONAL_COURSE_MAX_CHOOSE_COURSE_COUNT = "fjsd2_professional_course_max_choose_course_count"
        # 默认下注规则，1-2同号不买；2-正顺子不买；3-空心不买
        DONG_DEFAULT_BET_RULE_TYPES = "dong_default_bet_rule_types"
        # 倍投模式
        DONG_DOUBLING_DOWN_MODE = "dong_doubling_down_mode"
        # 金额基数
        DONG_BASE_AMT = "dong_base_amt"
        # 一次倍投
        DONG_ONCE_DOUBLING_DOWN = "dong_once_doubling_down"
        # 二次倍投
        DONG_TWICE_DOUBLING_DOWN = "dong_twice_doubling_down"
        # 输后复压倍数
        DONG_DS_EXPAND_TIMES = "dong_ds_expand_times"
        # 最大连续
        DONG_DS_MAX_CONTINUOUS_WIN_COUNT = "dong_ds_max_continuous_win_count"
        # 金额基数
        DONG_BASE_AMT_2 = "dong_base_amt_2"
        # 追投倍数
        DONG_CHASING_TIMES = "dong_chasing_times"
        # 追投最大盈利次数
        DONG_CHASING_MAX_CONTINUOUS_WIN_COUNT = "dong_chasing_max_continuous_win_count"
        # 教育学院选择的课程顺序
        JYXY_COURSE_NUMBER = "jyxy_course_number"
        # 教育学院登录地址
        JYXY_LOGIN_URL = "jyxy_login_url"
        # 辽宁干部网站类型
        LN_LEADER_WEB_TYPE = "ln_leader_web_type"

    ###############
    #### FJ干部 ####
    ###############

    # 用户名输入框
    FJLL_USERNAME_INPUT_XPATH = "(//div[@class='login_dialog']//input)[1]"
    # 密码输入框
    FJLL_PASSWORD_INPUT_XPATH = "(//div[@class='login_dialog']//input)[2]"
    # 获取验证码的节点，这个站点把验证码写在html中，服了！
    FJLL_VERIFY_CODE_XPATH = "(//div[@class='login_dialog']//input)[3]"
    # 验证码输入框
    FJLL_VERIFY_CODE_INPUT_XPATH = "//input[@id='loginValidationCode']"
    # 登录按钮
    FJLL_LOGIN_BUTTON_XPATH = "//div[@class='validation_left_login']"
    # 当前第一个未读的课程
    FJLL_CURRENT_UNFINISHED_COURSE_XPATH = "//div[@class='class_course_tab course_show']//ul[@class='list']/li[child::span[text() != '100.00%']][1]"
    # 学习中的弹窗，弹窗中有目录列表
    FJLL_STUDY_CONTENT_WINDOW_XPATH = "//div[@class='aui_state_focus aui_state_lock']"
    # 第一个未读的目录
    FJLL_STUDY_UNFINISHED_CONTENT_XPATH = "//div[@id='kcml']/ul/li[.//font[last()][text() != '[进度：100.00%]']][1]"
    # 学习的目录名称
    FJLL_STUDY_CONTENT_NAME_XPATH = "//div[@id='MainToper']/h5"
    # 弹窗中第一个未读的目录
    FJLL_STUDY_CONTENT_WINDOW_UNFINISHED_ONE_XPATH = "//ul[@id='start_to_list']//li[.//font[last()][text() != '[进度：100.00%]']][1]"

    # 学习时间
    FJLL_CURRENT_CONTENT_LEARN_SPEND_TIME_XPATH = "//div[@id='showProgress']"

    # 暂停按钮
    FJLL_VIDEO_PAUSE_BUTTON_XPATH = "//video[@id='myplayer']"

    # 班级列表按钮
    FJLL_CLASS_LIST_BUTTON_XPATH = "//li[@class='xxbc']"
    # 未结业的班级列表
    FJLL_UNFINISHED_CLASS_LIST_XPATH = "//div[text()='未结业']/..//a"
    # 视频结束的弹窗
    FJLL_CURRENT_CONTENT_FINISHED_ALERT_XPATH = "//div[@id='enddiv'][@style='display: block;']"
    # 视频学习的进度
    FJLL_CURRENT_CONTENT_LEARN_PROGRESS_XPATH = "//div[@id='kcml']//ul//li[not(a)]//font[last()]"

    #############
    ## 学习公社 ##
    ############
    # 用户名输入框
    XXGS_USERNAME_INPUT_XPATH = "//form[@id='pc-form']//div[@idx='0']//input[@name='username']"
    # 密码输入框
    XXGS_PASSWORD_INPUT_XPATH = "//form[@id='pc-form']//div[@idx='0']//input[@name='password']"
    # 登录按钮输入框
    XXGS_LOGIN_BUTTON_XPATH = "//form[@id='pc-form']//div[@idx='0']//button"
    # 登录失败提示
    XXGS_LOGIN_FAIL_TIPS_XPATH = "//form[@id='pc-form']//div[@idx='0']//label[@class='error password-error']"
    # 用户信息请求地址
    XXGS_USER_INFO_URL_TMPL = "https://study.enaea.edu.cn/getCurrentUser.do?_%d"
    # 第一个未学完的目录
    XXGS_FIRST_UNFINISHED_CONTENT_XPATH = "(//li[contains(@class,'cvtb-MCK-course-content')][.//div[@class='cvtb-MCK-CsCt-studyProgress'][text()!='100%']])[1]"
    # 学习时间
    XXGS_VIDEO_PLAY_TIME_XPATH = "//span[@class='xgplayer-time-current']"
    # XXGS_LEARN_TIME_XPATH = "//xg-time//span"
    XXGS_LEARN_TIME_CSS_EXPR = "xg-time[class='xgplayer-time'] span"
    # 学习20分钟之后，会有个休息提示，继续按钮
    XXGS_CONTINUE_BUTTON_XPATH = "//td[@class='td-content']//button"
    # 播放
    # XXGS_PLAY_BUTTON_XPATH = "//xg-start//div[@class='xgplayer-icon-play']/svg"
    # 提示信息
    XXGS_ALERT_INFO_XPATH = "//td[@class='td-content']//div[@class='dialog-content']"
    # 播放按钮的css表达式
    XXGS_PLAY_BUTTON_CSS_EXPR = "div[class='xgplayer-icon-play'] svg[width='70']"
    # 重播按钮的css表达式
    XXGS_REPLAY_BUTTON_CSS_EXPR = "svg[class='xgplayer-replay-svg']"
    # 目录名称
    XXGS_CONTENT_NAME_XPATH = "//li[@class='cvtb-top-list-item']/span"
    # 当前集的名称
    XXGS_GATHER_NAME_XPATH = "//li[contains(@class,'current')]//div[@class='cvtb-MCK-CsCt-title cvtb-text-ellipsis']"
    # 当前集的进度
    XXGS_GATHER_PROGRESS_XPATH = "//li[contains(@class,'current')]//div[@class='cvtb-MCK-CsCt-studyProgress']"

    #############
    ## FJ教育网 ##
    #############
    # 用户名输入框
    FJEDU_USERNAME_INPUT_XPATH = "//input[@id='loginId']"
    # FJEDU_USERNAME_INPUT_XPATH = "input[id='loginId']"
    # 密码输入框
    FJEDU_PASSWORD_INPUT_XPATH = "//input[@id='passwd']"
    # 登录按钮
    FJEDU_LOGIN_BUTTON_XPATH = "//a[@class='btn-primary mt16']"
    # 登录错误提示，获取text
    FJEDU_LOGIN_FAIL_TIPS_XPATH = "//div[@id='tbr-passwd-tip']/span"
    # 课程列表的“更多”按钮，点击进入课程列表
    FJEDU_COURSE_LIST_MORE_BUTTON_XPATH = "//div[@id='courseIndexList']//a[text()='更多']"
    # 左侧的“课程学习”按钮，点击进入课程列表
    FJEDU_ENTER_COURSE_PAGE_BUTTON_XPATH = "//a[text()='课程学习']"
    # 未完成课程列表
    FJEDU_ENTER_UNFINISHED_COURSES_BUTTONS_XPATH = "//div[@class='gp-classW5 gp-pull-left'][preceding-sibling::div[2][text()!='100.0%']]"
    # 第一个未完成的课程
    FJEDU_ENTER_FIRST_UNFINISHED_COURSE_BUTTON_XPATH = "(//div[@class='gp-classW5 gp-pull-left'][preceding-sibling::div[2][text()!='100.0%']])[1]"
    # 获取未完成的课程列表
    FJEDU_ENTER_UNFINISHED_COURSES_XPATH = "//div[contains(@class,'gp-classW1 gp-pull-left')][following-sibling::div[2][text()!='100.0%']]/a"
    # 必修课
    # FJEDU_REQUIRED_COURSES_XPATH = "//div[contains(@class,'gp-classW1 gp-pull-left')][following-sibling::div[2][text()!='100.0%']][.//span[contains(text(), '必修')]]//a"
    FJEDU_REQUIRED_COURSES_XPATH = "//div[contains(@class,'gp-classW1 gp-pull-left')][following-sibling::div[2]][.//span[contains(text(), '必修')]]//a"
    # 选修课
    # FJEDU_ELECTIVE_COURSES_XPATH = "//div[contains(@class,'gp-classW1 gp-pull-left')][following-sibling::div[2][text()!='100.0%']][.//span[contains(text(), '选修')]]//a"
    FJEDU_ELECTIVE_COURSES_XPATH = "//div[contains(@class,'gp-classW1 gp-pull-left')][following-sibling::div[2]][.//span[contains(text(), '选修')]]//a"
    # 观看视频页面的最外围iframe
    FJEDU_IFRAME_OUTTER_WHICH_CONTAINS_MAIN_FRAME_ID = "mainContent"
    # 观看视频页面的内围iframe，该iframe包含视频
    FJEDU_IFRAME_WHICH_CONTAINS_VIDEO_ID = "mainFrame"
    # 课程列表页面
    FJEDU_COURSE_LIST_SECTION_XPATH = "//section[@class='gp-bg1']"
    # 用户姓名
    FJEDU_REALNAME_XPATH = "//div[@id='userInfo']/h2"

    # 首页按钮
    FJEDU_MAIN_PAGE_BUTTON_XPATH = "//a[text()='首页']"
    # 分数信息：20/80分
    FJEDU_TOTAL_SCORE_DESC_XPATH = "//div[@id='learnTaskIndexNew']//li[div[contains(text(),'课程学习')]]//div[@class='bulletinW4 gp-pull-left']"

    # 视频播放页面的左侧的课件按钮，点此进入观看视频
    FJEDU_WATCH_VIDEO_BUTTON_XPATH = "//li[@id='courseware_main_menu']"
    # 获取正在播放的视频
    FJEDU_CURRENT_CONTENT_XPATH = "//div[@itemtype='video' and contains(@class, 's_pointerct')]"
    # 第一个未读的目录列表
    FJEDU_FIRST_UNFINISHED_CONTENT_XPATH = "(//div[@itemtype='video' and @completestate='0' and @class!='s_point s_pointerct'])[1]"
    # 除了当前目录之外其余的目录列表
    FJEDU_UNFINISHED_CONTENT_LIST_XPATH = "//div[@itemtype='video' and @class!='s_point s_pointerct']"
    # 已经播放时间
    FJEDU_CURRENT_CONTENT_PALYED_TIME_CSS = "div[class='screen-player-time'] span:nth-child(1)"
    # 总时长
    FJEDU_CURRENT_CONTENT_TOTAL_TIME_CSS = "div[class='screen-player-time'] span:nth-child(2)"
    # 视频
    FJEDU_VIDEO_XPATH = "//video"
    # 倍速播放按钮
    FJEDU_SPEED_UP_BUTTON_XPATH = "//span[@id='li_speedval_cur']"
    # 2倍播放按钮
    FJEDU_DOUBLE_SPEED_BUTTON_XPATH = "//li[@speedval='2']"
    # 观看超过30分钟提示框中的确定按钮
    FJEDU_CONFIRM_BUTTON_IN_TIPS_DIALOUE_XPATH = "//a[@class='layui-layer-btn0' and text()='确定']"
    # 视频播放按钮
    FJEDU_VIDEO_PLAY_BUTTON_XPATH = "//a[@id='player_pause']"
    # 选课中的选项
    FJEDU_CHOOSE_COURSE_ITEM_XPATH_TMPL = "//tr[contains(@class,'%s')][%d]//span"
    # 提交选课按钮
    FJEDU_COMMIT_CHOOSED_COURSES_BTN_XPATH = "//a[@id='savePerCou1']"
    # 确定选修课按钮
    # FJEDU_CONFIRM_CHOOSE_BTN_XPATH = "//a[@class='sel_btn btn1']"
    FJEDU_CONFIRM_CHOOSE_BTN_XPATH = "//a[@class='helper_btn btn1 l']"
    # 点击确定选课后，弹窗中的确认按钮
    FJEDU_RECONFIRM_BTN_XPATH = "//input[@class='ui_state_highlight']"
    # 课程未发布标志
    FJEDU_UNPUBLISH_COURSE_XPATH = "//p[text()='课件未发布,请稍后再来']"

    ###########
    ## FJ海西 ##
    ###########
    # 触发弹出登录对话框的按钮
    FJHX_LOGIN_DIALOGUE_TRIGGER_BTN_XPATH = "//span[@id='nameSpan']"
    # 登录对话框
    FJHX_LOGIN_DIALOGUE_XPATH = "//div[@class='layui-layer layui-layer-page  layer-anim']"
    # 手机登录标签，点击切换登录方式
    FJHX_TELEPHONE_LOGIN_TAB_XPATH = "//span[@id='yonghumingloginn']"
    # 手机登录用户名输入框
    FJHX_TELEPHONE_LOGIN_USERNAME_INPUT_XPATH = "//input[@id='user']"
    # 手机登录密码输入框
    FJHX_TELEPHONE_LOGIN_PASSWORD_INPUT_XPATH = "//input[@id='pwd']"
    # 手机登录验证码图片
    FJHX_TELEPHONE_LOGIN_CAPTCHA_IMG_XPATH = "//img[@id='captchaImage']"
    # 手机登录验证码输入框
    FJHX_TELEPHONE_LOGIN_CAPTCHA_INPUT_XPATH = "//input[@id='identify']"
    # 手机登录登录按钮
    FJHX_TELEPHONE_LOGIN_LOGIN_BTN_XPATH = "//input[@id='itemIndexlogin']"
    # 关闭登录框按钮
    JFHX_CLOSE_LOGGING_DIALOGUE_BTN_XPATH = "//a[contains(@class,'layui-layer-ico layui-layer-close')]"

    # 用户名登录标签，点击切换登录方式
    FJHX_ID_NO_LOGIN_TAB_XPATH = "//span[@id='shoujihaologinn']"
    # 用户名登录用户名输入框
    FJHX_ID_NO_LOGIN_USERNAME_INPUT_XPATH = "//input[@id='userr']"
    # 用户名登录密码输入框
    FJHX_ID_NO_LOGIN_PASSWORD_INPUT_XPATH = "//input[@id='pwdd']"
    # 用户名登录验证码图片
    FJHX_ID_NO_LOGIN_CAPTCHA_IMG_XPATH = "//img[@id='captchaImagee']"
    # 用户名登录验证码输入框
    FJHX_ID_NO_LOGIN_CAPTCHA_INPUT_XPATH = "//input[@id='identifyy']"
    # 用户名登录登录按钮
    FJHX_ID_NO_LOGIN_LOGIN_BTN_XPATH = "//input[@id='itemIndexlogintwo']"
    # 项目编码
    FJHX_ID_NO_LOGIN_PROJECT_CODE_XPATH = "//input[@id='projectCode']"
    # 错误提示信息
    FJHX_LOGIN_FAIL_TIPS_XPATH = "//div[@class='layui-layer-content layui-layer-padding'][./i[@class='layui-layer-ico layui-layer-ico2']]"

    # 用户信息弹窗，个别用户，会提示完善个人信息，不完善不能学习
    FJHX_COMPLETE_USER_INFO_DIALOGUE_XPATH = "//div[@class='layui-layer layui-layer-page'][./*[contains(text(),'补充个人信息')]]"
    # 补充个人信息弹窗中的工作单位，取text
    # <div class="controls" id="developStage">莆田市第小学</div>
    FJHX_WORK_PLACE_XPATH = "//div[@id='developStage']"
    # 工作单位输入框
    FJHX_WORK_PLACE_INPUT_XPATH = "//input[@name='workUnit']"
    # 补充个人信息对话框中的保存按钮
    FJHX_SAVE_BTN_IN_COMPLETE_INFO_DIALOGUE_XPATH = "//div[@class='layui-layer layui-layer-page']//input[@class='layui-btn layui-btn-normal' and @value='保存']"
    # 登录成功之后，跳转到项目页面，获取姓名的xpath，取text
    FJHX_USER_REALNAME_XPATH = "//span[@id='nameSpan']"
    # 登录成功之后，跳转到课程页面，获取姓名的xpath，取text
    FJHX_USER_REALNAME_XPATH2 = "//span[@id='commonUserNam']"
    # 公需课进入学习按钮
    FJHX_PUB_ENTER_STUDY_BTN_XPATH = "//a[@class='btn-start' and contains(@onclick, '14071')]"
    # 专业课进入学习按钮
    FJHX_PRO_ENTER_STUDY_BTN_XPATH = "//a[@class='btn-start' and not(contains(@onclick, '14071'))]"

    # user_id，<input type="hidden" id="studyPlanId" value="2974"> 取value
    FJHX_PLAN_ID_XPATH = "//input[@id='studyPlanId']"

    # 章节，获取章节元素模板，%s为章节名称，章节名称写在配置文件中，例如：//li[.//h2[text()='浸润师德师礼']]
    FJHX_CHAPTER_XPATH_TMPL = "//li[.//h2[text()='%s']]"
    # user_id，<input type="hidden" id="initProjectPhaseId" value="642"> 取value
    FJHX_PHASE_ID_XPATH = "//input[@id='initProjectPhaseId']"
    # 某个章节下第一个未完成的课程
    FJHX_UNFINISHED_COURSE_XPATH_TMPL = "//li[.//h2[text()='%s']]//li[./i[@class='icon_0' or @class='icon_2']][1]//a[@class='list-title']"
    # 某个章节下未完成的课程列表
    FJHX_UNFINISHED_COURSES_XPATH_TMPL = "//li[.//h2[text()='%s']]//li[./i[@class='icon_0' or @class='icon_2']]//a[@class='list-title']"
    # 章节下的所有课程，专业课
    FJHX_PRO_ALL_COURSES_IN_CHAPTER_XPATH = "//li[.//h2[text()='%s']]//li"
    # 公需课
    FJHX_PUB_ALL_COURSES_IN_CHAPTER_XPATH = "//a[text()='%s']"

    # 章节下已完成的课程
    FJHX_FINISHED_COURSES_IN_CHAPTER_XPATH = "//li[.//h2[text()='%s']]//i[@class='icon_1']"
    # 视频容器，有这个存在说明是视频
    FJHX_VIDEO_CONTAINER_XPATH = "//div[@class='ccH5playerBox']"
    # 视频播放按钮，这个按钮在html中一直存在，需要判断是否可见
    FJHX_VIDEO_PLAY_BTN_XPATH = "//div[@id='replaybtn']"
    # FJHX_VIDEO_PLAY_BTN_XPATH = "//div[@class='ccH5PlayBtn']"
    # 视频暂停提示框中的确定按钮，有这个出现说明视频暂停了
    FJHX_PAUSE_VIDEO_ALERT_CONFIRM_BTN_XPATH = "//div[contains(@class,'layui-layer layui-layer-dialog')][.//*[contains(text(),'视频暂停')]]//a[text()='Ok，我知道了！']"
    # 视频结束提示框中的确定按钮，有这个出现说明视频结束了
    FJHX_FINISHED_VIDEO_ALERT_CONFIRM_BTN_XPATH = "//div[contains(@class,'layui-layer layui-layer-dialog')][.//*[contains(text(),'视频已播放完成')]]//a[text()='Ok，我知道了！']"
    # //div[contains(@class,'layui-layer layui-layer-dialog')]//a[text()='Ok，我知道了！']
    FJHX_CONFIRM_BTN_IN_INFO_ALERT_XPATH = "//div[contains(@class,'layui-layer layui-layer-dialog')]//a[text()='确定']"

    # 当前播放视频的下一个视频
    FJHX_NEXT_VIDEO_XPATH = "//li[@class='ovd cur']/following::li[1]//a"
    # 视频页面中的返回按钮
    FJHX_GO_BACK_BTN_XPATH = "//div[@class='goback_href']"
    # 视频页面中的第一个视频
    # FJHX_FIRST_VIDEO_XPATH = "//div[@id='mCSB_1_container']//li[contains(@class,'type_1') and not(contains(@class,'isStudy'))][1]"
    FJHX_FIRST_VIDEO_XPATH = "//div[@class='course-list-con']//li[contains(@class, 'cur')]//a"
    # 页面弹窗，你还在认真学习吗？
    FJHX_VERIFY_ALERT_XPATH = "//div[@id='layui-layer1']//a[text()='继续学习']"
    # 验证码内容，取text
    FJHX_VERIFY_CODE_TEXT_IN_ALERT_XPATH = "//div[contains(@class,'layui-layer layui-layer-page')]//span[@id='codespan']"
    # 验证码输入框
    FJHX_VERIFY_CODE_INPUT_IN_ALERT_XPATH = "//div[contains(@class,'layui-layer layui-layer-page')]//input[@id='code']"
    # 提交按钮
    FJHX_COMMIT_BTN_IN_ALERT_XPATH = "//div[contains(@class,'layui-layer layui-layer-page')]//a[text()='提交']"
    # 提示框的蒙版
    FJHX_SHADE_WITH_TIPS_XPATH = "//div[@class='layui-layer-shade']"

    # 课程名称，取text
    FJHX_COURSE_NAME_XPATH = "//div[@class='course-info']//a"
    # 视频播放的时间
    FJHX_CURRENT_CONTENT_PALYED_TIME_CSS = "div[class=ccH5Time] :nth-child(1)"
    # 视频的全部时间
    FJHX_CURRENT_CONTENT_TOTAL_TIME_CSS = "div[class=ccH5Time] :nth-child(3)"

    # # 课程总共时间
    # FJHX_COURSE_TOTAL_TIME_XPATH = "//em[@class='ccH5TimeTotal']"
    # # 课程已学习的时间
    # FJHX_COURSE_LEARNED_TIME_XPATH = "//em[@class='ccH5TimeCurrent']"
    # 课程总时间和已学习的时间
    # FJHX_COURSE_TOTAL_TIME_AND_LEARNED_TIME_XPATH = "//span[@id='courseStudyBestMinutesNumber'] | //span[@id='courseStudyMinutesNumber']"

    # 课程页面的提示框
    FJHX_COURSE_PAGE_TIPS_XPATH = "//div[@id='pop_tips']"
    # 提示框中的确认按钮
    FJHX_CONFIRM_BTN_IN_COURSE_PAGE_TIPS_XPATH = "//a[@class='pop_btn']"

    ###############
    ### 新课标测验 ##
    ###############
    # 下一题按钮
    XKB_EXAM_NEXT_SUBJECT_BTN_XPATH = "//a[text()='下一题']"
    # 题目
    XKB_EXAM_SUBJECT_TITLE_XPATH = "//div[@class='splitS-left']//div"
    # 题目中的所有选的项xpath，备选1，根据页面的不同设置的
    XKB_EXAM_ALL_ITEMS_IN_SUBJECT_1_XPATH = "//div[contains(@class, 'clearfix answerBg')]//span"
    # 题目中的所有选项xpath，备选2，根据页面的不同设置的
    XKB_EXAM_ALL_ITEMS_IN_SUBJECT_2_XPATH = "//div[contains(@class, 'clearfix answerBg')]//div"
    # 答案选项的模板
    XKB_EXAM_ANSWER_ITEM_IN_SUBJECT_XPATH_TMPL = "//div[contains(@class, 'clearfix answerBg')][.//p[contains(text(),'%s')]] | //div[@class='clearfix answerBg'][.//div[contains(text(),'%s')]]"
    # 默认答案选项
    XKB_EXAM_DEFAULT_ANSWER_ITEM_IN_SUBJECT_XPATH = "//div[contains(@class, 'clearfix answerBg')][3]"

    ##########
    ## 共读 ##
    ##########
    # 用户名输入框
    GD_USERNAME_INPUT_XPATH = "//input[@id='phone']"
    # 密码输入框
    GD_PASSWORD_INPUT_XPATH = "//input[@id='pwd']"
    # 登录按钮
    GD_LOGIN_BUTTON_XPATH = "//button[@id='loginBtn']"
    # 登录失败提示信息
    GD_LOGIN_FAIL_TIPS_XPATH = "//p[@id='err-txt']"
    # 课程标签
    GD_COURSE_TAB_XPATH = "//div[@name='课程']"
    # 我学的课程标签
    GD_MY_LEARN_COURSE_TAB_XPATH = "//div[contains(text(),'我学的课')]"
    # 目标课程
    GD_TARGET_COURSE_XPATH = "//a[.//span[contains(text(), '教师共读')]]"
    # 签到任务标签
    GD_TASKS_TAB_XPATH = "//a[@title='任务']"
    # 签到
    GD_SIGN_IN_XPATH = "//li[@activestatus='1'][.//div[@aria-label='签到']]"
    # 签到成功提示
    GD_SIGN_IN_SUCC_FLAG_XPATH = "//div[@id='signSuccessed']"
    # 章节标签
    GD_CHAPTERS_TAB_XPATH = "//a[@title='章节']"
    # 章节页面中的第一个目录（目前无用）
    GD_FIRST_CONTENT_XPATH = "//div[@class='catalog_title']"
    # 章节页面中的第一个未完成的目录
    GD_FIRST_UNFINISHED_CONTENT_XPATH = "(//div[@class='catalog_title'][.//div[contains(@class,'catalog_tishi120')]])[1]"
    # GD_FIRST_UNFINISHED_CONTENT_XPATH = "//*[@id=\"cur754278090\"]/div"
    # 章节详情页面中第一个未完成的目录
    GD_UNFINISHED_CONTENT_XPATH = "(//div[contains(@class,'posCatalog_select')][.//span[contains(@class,'catalog_points_yi')]][.//span[@title != '讨论分享']])[1]"
    # 目录名称
    GD_CONTENT_NAME_XPATH = "//div[@class='prev_title']"
    # GD_VIDEO_CONTENT_NAME_XPATH = "//div[@class='prev_title']"
    # GD_VIDEO_CONTENT_NAME_XPATH = "//div[contains(@class,'ans-job-icon')]//span"
    # 视频
    GD_VIDEO_XPATH = "//video"
    # 播放按钮
    GD_PLAY_VIDEO_XPATH = "//button[@class='vjs-big-play-button']"
    # 播放时间
    GD_VIDEO_PLAYED_TIME_CSS = "span[class='vjs-current-time-display']"
    # 总时间
    GD_VIDEO_TOTAL_TIME_CSS = "span[class='vjs-duration-display']"
    # 拓展阅读页面中的“去阅读”按钮
    GD_READING_BTN_XPATH = "//span[text()='去阅读']"
    # 拓展阅读页面中的第一个章节
    GD_FIRST_CHAPTER_IN_READING_PAGE_XPATH = "(//ul//div[contains(@class,'chapterText')])[1]"
    # 拓展阅读页面中的“下一页”按钮
    GD_NEXT_BTN_IN_READING_PAGE_XPATH = "//a[@class='ml40 nodeItem r'] | //a[@id='loadbutton']"
    # 用户真名
    GD_USER_REAL_NAME_XPATH = "//li[@class='user']//h3"
    # 提示
    GD_TIPS_WINDOW_XPATH = "//div[@class='commitment-content-dialog']"
    # 我已阅读，开始学习单选框
    GD_I_AM_READ_CHECK_BOX_IN_TIPS_WINDOW_XPATH = "//input[@id='learnCommit-bottom-div']"
    # 开始学习
    GD_START_LEARN_IN_TIPS_WINDOW_XPATH = "//a[text()='开始学习'][2]"
    # 暂停按钮
    GD_PAUSE_BTN_XPATH = "//button[contains(@class,'vjs-paused')]"

    #############
    ## 智慧平台 ##
    #############

    SMTEDU_LOGIN_SLIDER_WIDTH = 114
    SMTEDU_LOGIN_SLIDER_MOVE_X = 576 - 12
    SMTEDU_ENTER_LOGIN_PAGE_BTN_XPATH = "//div[@class='index-module_user-un-login-in_0lCmo']"
    SMTEDU_USERNAME_INPUT_XPATH = "//input[@id='username']"
    SMTEDU_PASSWORD_INPUT_XPATH = "//input[@id='tmpPassword']"
    SMTEDU_LOGIN_BTN_XPATH = "//button[@id='loginBtn']"
    SMTEDU_WEEK_PASSWORD_ALERT_XPATH = "//div[@id='modify__tips_wrapper']"
    SMTEDU_SKIP_WEEK_PASSWORD_BTN_XPATH = "//button[@id='cancel_sdk']"
    SMTEDU_ACCEPT_AGREEMENT_BTN_XPATH = "//button[@id='gotologon_sdk']"
    SMTEDU_LOGIN_FAIL_TIPS_XPATH = "//p[@id='loginFormError']"
    SMTEDU_AGREE_CB_XPATH = "//input[@id='agreementCheckbox']"
    SMTEDU_SLIDER_XPATH = "//span[contains(@class,'m_slider')]"
    SMTEDU_SLIDER_VERIFY_SUCC_XPATH = "//span[@class='m_t_txt m_t_txt_sucess dis_none']"
    SMTEDU_UNSAFE_PASSWORD_TIPS_WINDOW_XPATH = "//div[@id='modify__tips_wrapper']"
    SMTEDU_UNSAFE_PASSWORD_SKIP_BTN_XPATH = "//button[@id='cancel_sdk']"

    SMTEDU_TARGET_COURSE_TMPL_XPATH = "//div[@class='index-module_box_2FQGy'][.//div[@class='index-module_title_8i8E6' and text()='%s']]"
    SMTEDU_CONTINUE_STUDY_BTN_XPATH = "//a[@class='CourseIndex-module_course-btn_3Yy4j']"
    SMTEDU_LEARN_GUIDE_WINDOW_XPATH = "//div[@class='fish-modal']"
    SMTEDU_NO_RECOMMEND_CB_XPATH = "//input[@type='checkbox']"
    SMTEDU_I_KNOW_BTN_XPATH = "//div[text()='我知道了']"
    # SMTEDU_LEARNED_DURATION_TMPL_XPATH = "//div[@class='index-module_box_2FQGy'][.//div[@class='index-module_title_8i8E6' and text()='%s']]//div[@class='index-module_processC_2kAFI' and contains(text(),'已学习')]//span"
    SMTEDU_LEARNED_DURATION_TMPL_XPATH = "//div[@class='index-module_processC_0VNia'][contains(text(),'已认定')]//span[@class='index-module_processCMy_kp+Ww']"
    SMTEDU_SIGN_IN_BTN_XPATH = "//div[text()='立即报名']"
    SMTEDU_FIRST_UNFINISHED_VIDEO_XPATH = "(//div[contains(@class,'resource-item-train')][.//i[contains(@class,'icon_checkbox_linear')]][.//i[@title='未开始' or @title='进行中']])[1]"
    SMTEDU_FIRST_FINISHED_VIDEO_XPATH = "(//div[contains(@class,'resource-item-train')][.//i[contains(@class,'icon_checkbox_linear')]][.//i[@title='已学完']])[1]"
    SMTEDU_CHAPTERS_XPATH = "//div[@class='fish-collapse-header']"
    SMTEDU_VIDEO_XPATH = "//video"
    SMTEDU_VIDEO_FIRST_IN_PLAY_BTN = "//button[@class='vjs-big-play-button']"
    SMTEDU_VIDEO_PLAYED_TIME_CSS = "span[class='vjs-current-time-display']"
    SMTEDU_VIDEO_TOTAL_TIME_CSS = "span[class='vjs-duration-display']"
    SMTEDU_VIDEO_PLAY_BTN_XPATH = "//button[contains(@class,'vjs-paused')]"
    SMTEDU_I_KNOWN_BTN_IN_TEST_TIPS_XPATH = "//button[@class='fish-btn fish-btn-primary']"
    SMTEDU_EXERCISE_WINDOW_XPATH = "//div[@class='index-module_box_blt8G']"
    SMTEDU_EXERCISE_ITEMS_XPATH = "//li[@class='nqti-option _qp-option']"
    SMTEDU_EXERCISE_NEXT_SUBJECT_BTN_XPATH = "//button[@class='fish-btn fish-btn-primary']"

    ###########
    ## 福师大 ##
    ###########
    # 用户名输入框
    FJSD_USERNAME_INPUT_XPATH = "//input[@id='username']"
    # 密码输入框
    FJSD_PASSWORD_INPUT_XPATH = "//input[@id='password']"
    # 登录按钮
    FJSD_LOGIN_BUTTON_XPATH = "//button[@class='btn_login']"
    # 登录失败提示信息
    FJSD_LOGIN_FAIL_TIPS_XPATH = "//div[@id='msg']"
    # 进行中按钮，进入到目标资源页面的按钮
    FJSD_ENTER_TARGET_SOURCE_BTN_XPATH = "//div[@class='tip active']"
    # 目标资源
    FJSD_TARGET_SOURCE_XPATH = "//li[last()]//h4"
    # 更多课程按钮
    FJSD_MORE_COURSES_BTN_XPATH = "//div[@class='discount'][.//div[contains(text(),'培训课程')]]//div[@class='more']"
    # 课程中未完成的目录
    FJSD_UNFINISHED_CONTENT_XPATH = "//div[@class=\"section\"]//li[.//i[@title=\"'学习中'\" or @title=\"'未学习'\"]]"
    FJSD_FIRST_UNFINISHED_CONTENT_XPATH = "//div[@class=\"section\"]//li[.//i[@title=\"'学习中'\" or @title=\"'未学习'\"]][1]"
    # 获取目录的名字
    FJSD_ALL_UNFINISHED_CONTENT_NAMES_XPATH_TMPL = "//div[@class=\"section\"]//li[.//i[@title=\"'学习中'\" or @title=\"'未学习'\"]]%s//span[@class='name']"
    # 所有展开的加号按钮，点击会展开所有的目录
    FJSD_ALL_EXTEND_BTN_XPATH = "//i[contains(@class, 'icon-plus')]"
    # 文档页面中展开文档按钮
    FJSD_SHOW_DOC_PAGES_BTN_XPATH = "//span[@class='lg-toggle-thumb lg-icon']"
    # 文档页面中一个文档展开后的所有的页面
    FJSD_ALL_DOC_PAGES_XPATH = "//div[@class='lg-thumb-outer lg-grab']//img"
    # 播放按钮
    FJSD_PLAY_VIDEO_XPATH = "//button[@class='vjs-big-play-button']"
    # 播放时间
    FJSD_VIDEO_PLAYED_TIME_CSS = "span[class='vjs-current-time-display']"
    # 总时间
    FJSD_VIDEO_TOTAL_TIME_CSS = "span[class='vjs-duration-display']"
    # 拉到最低端“无更多数据”
    FJSD_NO_MORE_DATA_TIPS_XPATH = "//div[@class='nomore']"

    #############
    ## 继续教育 ##
    #############
    # 切换到手机号码登录的按钮
    FJJXEDU_PHONE_LOGIN_SWITCH_BTN_XPATH = "//div[@id='firstSection']//a[@class='list link-phone fl txt-theme']"
    # 切换到证件号码登录的按钮
    FJJXEDU_CERT_LOGIN_SWITCH_BTN_XPATH = "//div[@id='firstSection']//a[@class='list link-jigou fl txt-theme']"
    # 用户名输入框
    FJJXEDU_USERNAME_INPUT_XPATH = "//div[@id='firstSection']//input[@type='text']"
    # 密码输入框
    FJJXEDU_PASSWORD_INPUT_XPATH = "//div[@id='firstSection']//input[@type='password']"
    # 登录按钮
    FJJXEDU_LOGIN_BTN_XPATH = "//div[@id='firstSection']//a[text()='登录']"
    # 登录失败提示信息
    FJJXEDU_LOGIN_FAIL_TIPS_XPATH = "//div[@id='firstSection']//p[@class='colorRed err-tip fs12 txt-l']//span"
    # 个人空间按钮
    FJJXEDU_INDIVIDUAL_SPACE_BTN_XPATH = "//div[@id='firstSection']//a[text()='个人空间']"
    # 进入学习按钮
    FJJXEDU_ENTER_STUDY_BTN_XPATH = "//a[text()='进入学习'] | //a[text()='Start']"
    # 第一个未完成的常规专题（非考试）
    FJJXEDU_FIRST_UNFINISHED_NORMAL_SUBJECT_BTN_XPATH = "(//li[contains(@class,'moocCourse')][.//span[@class='l_sprogress_text mal10'][text()!='100%']]//div[@class='px_form_btn l_sform_btn fr'])[1]"
    # 第一个未完成的考试专题
    FJJXEDU_FIRST_UNFINISHED_EXAM_SUBJECT_BTN_XPATH = "//li[contains(@class,'l_tcourse_list clearf')]//div[@class='px_form_btn l_sform_btn fr']//a[text()='去考试' or text()='GO']"
    # 所有的常规专题
    FJJXEDU_ALL_UNFINISHED_NORMAL_SUBJECT_BTNS_XPATH = "//li[contains(@class,'moocCourse')][.//span[@class='l_sprogress_text mal10'][text()!='100%']]//div[@class='px_form_btn l_sform_btn fr']"
    # 章节页面中的第一个未完成的目录
    FJJXEDU_FIRST_UNFINISHED_CONTENT_XPATH = "(//div[@class='catalog_title'][.//div[contains(@class,'catalog_tishi120')]])[1]"
    # 章节详情页面中第一个未完成的目录
    FJJXEDU_UNFINISHED_CONTENT_XPATH = "(//div[contains(@class,'posCatalog_select')][.//span[contains(@class,'catalog_points_yi')]])[1]"
    # 目录名称
    FJJXEDU_CONTENT_NAME_XPATH = "//div[@class='prev_title']"
    # 视频
    FJJXEDU_VIDEO_XPATH = "//video"
    # 播放按钮
    FJJXEDU_PLAY_VIDEO_XPATH = "//button[@class='vjs-big-play-button']"
    # 播放时间
    FJJXEDU_VIDEO_PLAYED_TIME_CSS = "span[class='vjs-current-time-display']"
    # 总时间
    FJJXEDU_VIDEO_TOTAL_TIME_CSS = "span[class='vjs-duration-display']"
    # 拓展阅读页面中的“去阅读”按钮
    FJJXEDU_READING_BTN_XPATH = "//span[text()='去阅读']"
    # 拓展阅读页面中的第一个章节
    FJJXEDU_FIRST_CHAPTER_IN_READING_PAGE_XPATH = "(//ul//div[contains(@class,'chapterText')])[1]"
    # 拓展阅读页面中的“下一页”按钮
    FJJXEDU_NEXT_BTN_IN_READING_PAGE_XPATH = "//a[@class='ml40 nodeItem r'] | //a[@id='loadbutton']"
    # 下一页
    FJJXEDU_PRE_BTN_IN_READING_PAGE_XPATH = "//a[@class='nodeItem l']"
    # 用户真名
    FJJXEDU_USER_REAL_NAME_XPATH = "//li[@class='user']//h3"
    # 提示
    FJJXEDU_TIPS_WINDOW_XPATH = "//div[@class='commitment-content-dialog']"
    # 我已阅读，开始学习单选框
    FJJXEDU_I_AM_READ_CHECK_BOX_IN_TIPS_WINDOW_XPATH = "//input[@id='learnCommit-bottom-div']"
    # 开始学习
    FJJXEDU_START_LEARN_IN_TIPS_WINDOW_XPATH = "//a[text()='开始学习'][2]"
    # 暂停按钮
    FJJXEDU_PAUSE_BTN_XPATH = "//button[contains(@class,'vjs-paused')]"

    #############
    ## 安溪教育 ##
    #############
    # 通知信息的对话框
    AXJY_NOTIFY_DIALOGUE_XPATH = "//div[contains(@class, 'el-dialog__wrapper m-notice-dialog')]"
    # 对话框关闭按钮
    AXJY_NOTIFY_DIALOGUE_CLOSE_BTN_XPATH = "//div[contains(@class, 'el-dialog__wrapper m-notice-dialog')]//button[./span[text()='关闭']]"
    # 记住我
    AXJY_NOTIFY_REMEMBER_ME_XPATH = "//div[contains(@class, 'el-dialog__wrapper m-notice-dialog')]//input[@type='checkbox']"
    # 用户名
    AXJY_USERNAME_INPUT_XPAHT = "//input[@class='ipt' and @type='text']"
    # 密码输入框
    AXJY_PASSWORD_INPUT_XPATH = "//input[@class='ipt' and @type='password']"
    # 登录按钮
    AXJY_LOGIN_BTN_XPATH = "//button[./*[text()='登 录']]"
    # 同意协议
    AXJY_ACCEPT_AGREEMENT_XPATH = "//div[@class='m-login-box']//label[@class='el-checkbox']"
    # 验证码输入框
    AXJY_CAPTCHA_INPUT_XPATH = "//input[@class='ipt ipt-img-code' and @type='text']"
    # 验证码图片
    AXJY_CAPTCHA_IMG_XPATH = "//span[@class='qr-code']"
    # 账密错误提示框
    AXJY_USER_ERROR_DIALOGUE_XPAHT = "//div[@class='el-message-box__wrapper']"
    # 账密错误原因
    AXJY_LOGIN_FAIL_REASON_XPATH = "//div[@class='el-message-box__wrapper']//p"
    # 验证码错误的失败提示，取text()
    AXJY_CAPTHCA_ERROR_TIPS_XPATH = "//div[@class='el-form-item__error']"

    # 去学习按钮
    AXJY_LEARN_BTN_IN_FIRST_PAGE_XPATH = "//div[@class='m-login-box']//div[text()='去学习']"
    # 第一个班级中的“立即学习”按钮
    AXJY_LEARN_NOW_IN_CLASS_PAGE_XPATH = "(//ul[@class='m-class-list']//li)[1]//button"

    # 未完成课程标签
    AXJY_UNFINISHED_COURSES_TAB_XPATH = "//div[@id='tab-unlearn']"

    # 第一个未完成的课程
    AXJY_FIRST_UNFINISHED_COURSE_BTN_XPATH = "//ul[@class='m-detail-list']//li[1]//button[.//*[contains(text(),'课程学习')]]"
    # 视频页面的播放按钮
    AXJY_PLAY_BTN_XPATH = "//button[@class='vjs-big-play-button']"

    # 课程中第一个未读的目录
    AXJY_FIRST_UNFINISHED_VIDEO_XPATH = "(//div[@class='el-collapse-item__content']//div[@class='course-name'][.//span[@class='progress-num f-mr10' and text()!='已学 100%']])[1]"
    # 课程名称
    AXJY_CUR_COURSE_NAME_XPATH = "//ul[@class='m-detail-list']//li[1]//a[@class='tit']//a"
    # 目录名称
    AXJY_CUR_CONTENT_NAME_XPATH = "//div[contains(@class,'playing')]//div[@class='course-name']/p"
    # 当前目录的学习进度
    AXJY_CUR_CONTENT_LEARN_PROGRESS_XPATH = "//div[contains(@class,'playing')]//span[@class='progress-num f-mr10']"
    # 当前课程结束的提示
    AXJY_CUR_COURSE_FINISHED_TIPS_XPATH = "//div[@class='txt' and text()='您已学完当前课程']"
    # 选课的按钮
    AXJY_CHOOSE_COURSE_BTN_XPATH = "//button[contains(.//text(), '立即选课')]"
    # 最后一个视频
    AXJY_LAST_VIDEO_XPATH = "//div[@class='el-collapse-item__content']//div[contains(@class, 'item')][last()]"
    # 获取当前正在播放的视频
    AXJY_CUR_PLAYING_VIDEO_XPATH = "//div[@class='el-collapse-item__content']//div[@class='item playing']"
    # 用户名
    AXJY_REAL_NAME_XPATH = "//div[@class='login-after']//div[@class='name']"

    #############
    #### 希沃 ###
    #############
    # 登录页面出发按钮，点击该按钮会跳转到登录页面
    SEEWO_LOGIN_PAGE_TRIGGER_BTN_XPATH = "//span[text()='登录']"
    # 用户密码登录方式，点击该标签会切换到用户名密码的登录方式
    SEEWO_USERNAME_PWD_LOGIN_TAB_XPATH = "//div[@id='scanLoginTab']"
    # 用户名
    SEEWO_USERNAME_INPUT_XPAHT = "//input[@id='username']"
    # 密码输入框
    SEEWO_PASSWORD_INPUT_XPATH = "//input[@id='password']"
    # 同意协议
    SEEWO_AGREE_PROTOCOL_XPATH = "//i[@class='custom-checkbox']"
    # 登录按钮
    SEEWO_LOGIN_BTN_XPATH = "//div[@id='login-btn']"
    # 登录失败提示
    SEEWO_LOGIN_FAIL_TIPS_XPATH = "//span[@id='login-err-text']"

    ###############
    ## 福师大2024 ##
    ###############
    # 用户名输入框
    FJSD2_USERNAME_INPUT_XPATH = "//input[@id='aw-login-user-name']"
    # 密码输入框
    FJSD2_PASSWORD_INPUT_XPATH = "//input[@id='aw-login-user-password']"
    # 登录按钮
    FJSD2_LOGIN_BUTTON_XPATH = "//a[@id='login_submit']"
    # 登录失败提示信息
    FJSD2_LOGIN_FAIL_TIPS_XPATH = "//div[@class='error-info']"
    # 去学习按钮
    FJSD2_GO_TO_LEARN_BTN = "//a[@id='goLearn']"
    # 第一个未读课程
    FJSD2_FIRST_UNFINISHED_COURSE_XPATH = "//span[@class='a-bg-tip-orange'][1]"

    # 课程中未完成的目录
    FJSD2_UNFINISHED_CONTENT_XPATH = "//div[@class=\"section\"]//li[.//i[@title=\"'学习中'\" or @title=\"'未学习'\"]]"
    FJSD2_FIRST_UNFINISHED_CONTENT_XPATH = "//div[@class=\"section\"]//li[.//i[@title=\"'学习中'\" or @title=\"'未学习'\"]][1]"
    # 获取目录的名字
    FJSD2_ALL_UNFINISHED_CONTENT_NAMES_XPATH_TMPL = "//div[@class=\"section\"]//li[.//i[@title=\"'学习中'\" or @title=\"'未学习'\"]]%s//span[@class='name']"
    # 所有展开的加号按钮，点击会展开所有的目录
    FJSD2_ALL_EXTEND_BTN_XPATH = "//i[contains(@class, 'icon-plus')]"
    # 文档页面中展开文档按钮
    FJSD2_SHOW_DOC_PAGES_BTN_XPATH = "//span[@class='lg-toggle-thumb lg-icon']"
    # 文档页面中一个文档展开后的所有的页面
    FJSD2_ALL_DOC_PAGES_XPATH = "//div[@class='lg-thumb-outer lg-grab']//img"
    # 播放按钮
    FJSD2_PLAY_VIDEO_XPATH = "//button[@class='vjs-big-play-button']"
    # 播放时间
    FJSD2_VIDEO_PLAYED_TIME_CSS = "span[class='vjs-current-time-display']"
    # 总时间
    FJSD2_VIDEO_TOTAL_TIME_CSS = "span[class='vjs-duration-display']"
    # 拉到最低端“无更多数据”
    FJSD2_NO_MORE_DATA_TIPS_XPATH = "//div[@class='nomore']"


class ActivateStatus(Enum):
    """
    激活状态
    """
    # 未激活
    NOT_ACTIVATED = 0
    # 已激活
    ACTIVATED = 1
    # 已过期
    EXPIRED = 99
    # 远程校验失败
    REMOTE_VERIFY_FAILED = 2

    @classmethod
    def get_by_value(cls, value: str):
        ret = None
        for member in cls:
            if str(member.value) == value:
                ret = member
                break
        return ret
