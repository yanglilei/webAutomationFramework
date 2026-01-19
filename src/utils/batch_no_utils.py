import datetime
import random
import string
import uuid


def generate_batch_number(sep: str = "") -> str:
    """
    生成不重复的批次号，包含日期+时间（精确到微秒）

    参数：
        sep: 分隔符（可选），用于分隔时间部分和随机部分，增强可读性，默认无分隔符

    返回：
        str: 不重复的批次号
    示例：
        无分隔符：20260113162530123456a8s79d
        有分隔符(sep="-")：20260113162530123456-a8s79d
    """
    try:
        # 1. 获取当前时间，精确到微秒（6位数字）
        now = datetime.datetime.now()
        # 格式化时间：年(4)月(2)日(2)时(2)分(2)秒(2)微秒(6)
        time_part = now.strftime("%Y%m%d%H%M%S%f")

        # 2. 生成6位随机字母+数字组合（进一步保证唯一性）
        # 可选：替换为 uuid.uuid4().hex[:6] 适配分布式场景
        random_part = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

        # 3. 拼接批次号
        batch_number = f"{time_part}{sep}{random_part}"
        return batch_number
    except Exception as e:
        raise RuntimeError(f"生成批次号失败：{str(e)}")


# 进阶版本（分布式场景推荐）：用UUID替代随机字符串，全局唯一
def generate_batch_number_distributed(sep: str = "-") -> str:
    """
    分布式环境下的批次号生成方法（多机器/多进程无重复）
    格式：日期时间(14位) + 分隔符 + UUID前8位
    示例：20260113162530-8a7b6c5d
    """
    now = datetime.datetime.now()
    time_part = now.strftime("%Y%m%d%H%M%S")  # 简化时间部分（到秒）
    uuid_part = uuid.uuid4().hex[:8]  # UUID4的16进制字符串前8位
    return f"{time_part}{sep}{uuid_part}"


# 测试代码
if __name__ == "__main__":
    # 生成10个普通批次号
    print("=== 普通批次号（单机）===")
    for i in range(3):
        print(f"第{i + 1}个：{generate_batch_number('-')}")

    # 生成10个分布式批次号
    print("\n=== 分布式批次号（多机）===")
    for i in range(3):
        print(f"第{i + 1}个：{generate_batch_number_distributed()}")