from datetime import datetime
from enum import Enum
from typing import List, Optional


def has_reached_time(pre_time, cur_time, target_time):
    return True if pre_time <= target_time <= cur_time else False


def clear_doubling_down_info_at_special_time(pre_time, cur_time):
    from datetime import datetime, time, timedelta
    special_time_1 = datetime.combine(datetime.now() + timedelta(days=1), datetime.min.time())
    today_6_oclock = datetime.combine(pre_time.date(), time(6, 0, 0))
    tomorrow_6_oclock = datetime.combine(pre_time.date() + timedelta(days=1), time(6, 0, 0))
    special_time_2 = today_6_oclock if pre_time < today_6_oclock else tomorrow_6_oclock
    if has_reached_time(pre_time, cur_time, special_time_1) or has_reached_time(pre_time, cur_time, special_time_2):
        # 达到0点和6点，清掉倍投信息
        pre_time = datetime.now()
    cur_time = datetime.now()
    return cur_time, pre_time


class BetRuleType(Enum):
    # 2同号不买
    DOUBLE_SAME_KIND_NO_BET = (1, "2同号不买")
    # 空心不买
    GAP_SEQUENCE_NO_BET = (2, "空心不买")
    # 正顺子不买
    STRAIGHT_NO_BET = (3, "正顺子不买")
    # 空心买
    GAP_SEQUENCE_BET = (4, "空心买")
    # 2同号不买新规
    DOUBLE_SAME_KIND_NO_BET_V2 = (5, "2同号不买V2")

    @classmethod
    def get_by_val(cls, val: int):
        ret = None
        for instance in cls:
            if instance.value[0] == val:
                ret = instance
                break
        return ret


class BetInfo:
    def __init__(self, period_no: str, rule_type: BetRuleType, sequence: int, bet_numbers: List[int],
                 bet_amount: int = 0, doubling_count=0, win_number: Optional[int] = None):
        """
        投注信息实体类
        :param period_no: str 期号
        :param rule_type: 规则类型，看BetRuleType
        :param bet_numbers: List[int] 投注号码
        :param win_number: int 开奖号码
        :param sequence: int 第几位，顺序，第一位从1开始
        :param bet_amount: int 下注金额
        :param doubling_count: int 倍投次数。0-未倍投；1-一次倍投；2-二次倍投
        """
        # 期号
        self.period_no = period_no
        # 规则类型
        self.rule_type = rule_type
        # 下注号码
        self.bet_numbers = bet_numbers
        # 开奖号码
        self.win_number = win_number
        # 位数
        self.sequence = sequence
        # 投注金额：每个号码的投注金额
        self.bet_amount = bet_amount
        # 已经倍投的次数。初始化为0-未倍投；1-已经倍投一次；2-已经倍投二次
        self.doubling_count = doubling_count

    def is_win(self):
        """
        是否中间
        :return: bool; True-中间；False-不中奖
        """
        return True if self.win_number in self.bet_numbers else False

    def __repr__(self):
        return f"第{self.sequence}位【{self.rule_type.value[1]}】{self.bet_numbers}{'一次倍投' if self.doubling_count == 1 else '二次倍投'}"


def find_missing_piece_x(image_path):
    import cv2
    captcha_image = cv2.imread(image_path)
    gray = cv2.cvtColor(captcha_image, cv2.COLOR_BGR2GRAY)
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    edged = cv2.Canny(blurred, 50, 150)
    contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    contours = sorted(contours, key=cv2.contourArea, reverse=True)
    slider_contour = contours[0]
    x, y, w, h = cv2.boundingRect(slider_contour)
    slider_position = (x, y, w, h)
    return slider_position[0]


class DateUtils:
    @staticmethod
    def is_expired(expire_date: str, date_format="%Y%m%d") -> bool:
        """
        判断是否过期
        :param expire_date: true-当前时间>expire_date
        :return:
        """
        return datetime.strptime(expire_date, date_format) < datetime.today()
