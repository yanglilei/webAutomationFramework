# cython_builder.py
from src.utils.cython_builder import CythonBuilder


def compile_files():
    builder = CythonBuilder()
    files = [
        ("src.frame.task", "src/frame/task.py"),
        ("src.utils.jwt_utils", "src/utils/jwt_utils.py"),
        ("src.utils.hardware_finger_utils", "src/utils/hardware_finger_utils.py"),
        ("src.utils.rsa_key_utils", "src/utils/rsa_key_utils.py"),
        ("src.frame.common.key_client", "src/frame/common/key_client.py"),
    ]
    builder.build(files)


if __name__ == "__main__":
    compile_files()