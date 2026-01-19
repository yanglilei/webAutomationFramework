import re


def mask_username(username: str) -> str:
    """
    用户名脱敏函数
    :param username: 原始用户名（字符串类型）
    :return: 脱敏后的用户名
    """
    # 输入校验：确保是字符串类型
    if not isinstance(username, str):
        raise TypeError("用户名必须是字符串类型")

    username_len = len(username)

    # 情况1：长度大于14位，隐藏第5-12位（索引4到11，共8位）
    if username_len > 14:
        # 前4位 + 8个* + 从第13位开始的剩余字符
        return username[:4] + "********" + username[12:]

    # 情况2：长度≤14位，按分区间规则脱敏
    if username_len <= 2:
        return username  # 太短不脱敏
    elif 3 <= username_len <= 4:
        # 隐藏中间1位：第1个字符 + * + 从第3个字符开始的剩余部分
        return username[0] + "*" + username[2:]
    elif 5 <= username_len <= 10:
        # 隐藏中间3位：计算前后保留长度
        front_len = (username_len - 3) // 2
        back_len = username_len - 3 - front_len
        return username[:front_len] + "***" + username[-back_len:]
    elif 11 <= username_len <= 14:
        # 隐藏中间5位：计算前后保留长度
        front_len = (username_len - 5) // 2
        back_len = username_len - 5 - front_len
        return username[:front_len] + "*****" + username[-back_len:]

    # 兜底返回（理论上不会执行到）
    return username


def is_phone_no(val: str):
    pattern = r"^1[0-9]{10}$"
    return re.match(pattern, val) is not None

def is_id_no(val: str):
    pattern = r"(^[1-9]\d{5}(18|19|([23]\d))\d{2}((0[1-9])|(10|11|12))(([0-2][1-9])|10|20|30|31)\d{3}[0-9Xx]$)|(^[1-9]\d{5}\d{2}((0[1-9])|(10|11|12))(([0-2][1-9])|10|20|30|31)\d{2}$)"
    return re.match(pattern, val) is not None