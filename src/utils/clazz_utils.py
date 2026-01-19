
class ClazzUtils:
    """
    类工具
    定义了一些操作类、对象相关的工具
    """
    @staticmethod
    def copy_object_attributes(source_obj, target_obj, skip_private=True, skip_methods=True):
        """
        复制源对象的属性到目标对象（不确定属性名时的通用方案）

        Args:
            source_obj: 源对象（提供属性的对象）
            target_obj: 目标对象（接收属性的对象）
            skip_private: 是否跳过私有属性（以_开头），默认True
            skip_methods: 是否跳过方法/函数属性，默认True

        Returns:
            None
        """
        # 步骤1：获取源对象的所有可复制属性名
        attr_names = []

        # 处理有__slots__的情况
        if hasattr(source_obj, '__slots__'):
            attr_names = [slot for slot in source_obj.__slots__ if isinstance(slot, str)]
        # 处理普通对象（有__dict__的情况）
        elif hasattr(source_obj, '__dict__'):
            attr_names = list(source_obj.__dict__.keys())
        # 兜底：遍历所有属性（过滤后使用）
        else:
            attr_names = dir(source_obj)

        # 步骤2：遍历并复制属性
        for attr_name in attr_names:
            # 跳过私有属性（可选）
            if skip_private and attr_name.startswith('_'):
                continue

            # 跳过方法/函数（可选）
            if skip_methods:
                try:
                    attr_value = getattr(source_obj, attr_name)
                    if callable(attr_value):  # 判断是否是方法/函数
                        continue
                except AttributeError:
                    continue

            # 安全复制属性（处理属性不存在/不可写的情况）
            try:
                # 获取源对象的属性值
                attr_value = getattr(source_obj, attr_name)
                # 设置到目标对象
                setattr(target_obj, attr_name, attr_value)
            except (AttributeError, TypeError) as e:
                # 跳过不可访问/不可设置的属性（比如只读属性）
                print(f"跳过属性 {attr_name}：{e}")
                continue