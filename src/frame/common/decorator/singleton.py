import threading
import functools

def singleton(cls):
    _instance_cache = {}
    _lock = threading.Lock()  # 锁仅用于首次实例化时的竞争控制

    @functools.wraps(cls)
    def wrapper(*args, **kwargs):
        # 第一次检查：快速判断实例是否已存在（无锁，高性能）
        if cls not in _instance_cache:
            # 只有实例不存在时，才加锁竞争
            with _lock:
                # 第二次检查：确保加锁后，其他线程未提前创建实例
                if cls not in _instance_cache:
                    _instance_cache[cls] = cls(*args, **kwargs)
        return _instance_cache[cls]
    return wrapper