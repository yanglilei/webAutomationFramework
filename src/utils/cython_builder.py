import os
from typing import Optional, List, Dict, Union, Tuple

from Cython.Build import cythonize
from setuptools import Extension, setup


class CythonBuilder:
    """Cython编译工具类，用于将Python项目编译为C扩展模块"""

    def __init__(
            self,
            project_root: str = '.',
            exclude_files: Optional[List[str]] = None,
            exclude_dirs: Optional[List[str]] = None,
            build_dir: str = "cython_build",
            compiler_directives: Optional[Dict[str, Union[str, bool]]] = None,
            extension_kwargs: Optional[Dict[str, Union[str, bool, List]]] = None
    ):
        """
        初始化Cython构建器

        参数:
            project_root: 项目根目录路径
            exclude_files: 要排除的文件名列表
            exclude_dirs: 要排除的目录名列表
            build_dir: 编译输出目录
            compiler_directives: Cython编译指令
            extension_kwargs: 传递给Extension构造函数的额外参数
        """
        self.project_root = os.path.abspath(project_root)
        self.exclude_files = exclude_files or []
        self.exclude_dirs = exclude_dirs or []
        self.build_dir = build_dir

        # 设置默认编译指令
        self.compiler_directives = compiler_directives or {
            'language_level': "3",  # 使用Python 3语法
            # 'embedsignature': True,  # 嵌入函数签名便于调试
        }

        # 设置默认Extension参数
        self.extension_kwargs = extension_kwargs or {
            'py_limited_api': True,  # 生成通用文件名
            'define_macros': [('CYTHON_LIMITED_API', '1')]
        }

        self.python_files = []
        self.extensions = []

    def find_python_files(self) -> List[Tuple[str, str]]:
        """
        递归查找目录下所有Python文件

        返回:
            包含(模块名, 文件路径)的元组列表
        """
        python_files = []

        for dirpath, dirnames, filenames in os.walk(self.project_root):
            # 排除指定目录
            dirnames[:] = [d for d in dirnames if d not in self.exclude_dirs]

            for filename in filenames:
                if filename.endswith('.py') and filename not in self.exclude_files:
                    # 构建模块名 (例如: src.apps.dxm_publish_helper.busi_handler)
                    relative_path = os.path.relpath(dirpath, os.getcwd())
                    module_parts = relative_path.split(os.sep)
                    if module_parts[0] == '.':
                        module_parts = []
                    module_name = ".".join(module_parts + [filename[:-3]])

                    # 构建文件路径
                    file_path = os.path.join(dirpath, filename)

                    python_files.append((module_name, file_path))

        self.python_files = python_files
        return python_files

    def create_extensions(self, files: Optional[List[Tuple[str, str]]] = None) -> List[Extension]:
        """
        为Python文件列表创建Extension对象

        参数:
            files: 包含(模块名, 文件路径)的元组列表，默认使用find_python_files的结果

        返回:
            Extension对象列表
        """
        if files is None:
            if not self.python_files:
                self.find_python_files()
            files = self.python_files

        extensions = []

        for module_name, file_path in files:
            ext = Extension(
                name=module_name,
                sources=[file_path],
                **self.extension_kwargs
            )
            extensions.append(ext)

        self.extensions = extensions
        return extensions

    def build(self, files: Optional[List[Tuple[str, str]]] = None) -> None:
        """
        执行Cython编译

        参数:
            files: 可选的要编译的文件列表，默认编译所有找到的文件
        """
        if not self.extensions and files is None:
            self.create_extensions()
        elif files:
            self.create_extensions(files)

        setup(
            name="ProtectedProject",
            ext_modules=cythonize(
                self.extensions,
                compiler_directives=self.compiler_directives,
                build_dir=self.build_dir,
            ),
        )

    def get_compiled_files(self) -> List[str]:
        """获取编译后生成的文件列表"""
        compiled_files = []

        # 根据操作系统确定扩展名
        if os.name == 'nt':  # Windows
            extension = '.pyd'
        else:  # Linux/macOS
            extension = '.so'

        # 生成预期的编译后文件名
        for module_name, _ in self.python_files:
            parts = module_name.split('.')
            file_name = parts[-1] + extension
            file_path = os.path.join(os.path.dirname(self.project_root), *parts[:-1], file_name)
            compiled_files.append(file_path)

        return compiled_files


# def compile_project():
#     builder = CythonBuilder(
#         project_root="src/apps/dxm_publish_helper",
#         exclude_files=["ui.py"],  # 排除UI文件，只编译业务逻辑
#         exclude_dirs=["__pycache__", "tests"]
#     )
#     builder.build()


# 使用示例
# def demo():
#     # 创建构建器实例
#     builder = CythonBuilder(
#         project_root="src/apps/dxm_publish_helper",
#         exclude_files=["ui.py"],  # 排除UI文件，只编译业务逻辑
#         exclude_dirs=["__pycache__", "tests"]
#     )
#
#     # 查找Python文件
#     python_files = builder.find_python_files()
#     print(f"找到 {len(python_files)} 个Python文件")
#
#     # 编译所有文件
#     builder.build()
#
#     # 获取编译后的文件列表
#     compiled_files = builder.get_compiled_files()
#     print("编译后的文件:")
#     for file in compiled_files:
#         print(f"  - {file}")
