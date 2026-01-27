import asyncio


def get_event_loop_safely():
    """
    安全获取事件循环的通用方法：
    1. 优先获取正在运行的循环（异步上下文）
    2. 无运行中循环则获取当前线程的默认循环
    3. 无默认循环则创建新循环并设为默认
    """
    try:
        # 异步上下文：获取正在运行的循环（最安全）
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # 同步上下文：尝试获取当前线程的默认循环
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            # 无默认循环，创建新循环并设为默认
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    return loop