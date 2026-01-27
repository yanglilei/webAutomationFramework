import os
import shutil
import subprocess
import sys
from pathlib import Path


class PyInstallerBuilder:
    def __init__(self):
        pass
        # self.name = name
        # self.enter_file = enter_file
        # self.icon = icon
        # self.datas = datas
        # self.excludes = excludes
        # self.dist_dir = os.path.join(os.getcwd(), 'dist')
        # self.hidden_imports = hidden_imports

    @classmethod
    def _pyinstaller_path(cls):
        # 判断操作系统
        if sys.platform.startswith('win'):
            # Windows 系统使用分号分隔
            separator = ';'
            # 指定 PyInstaller 可执行文件路径
            pyinstaller_path = os.path.join(sys.prefix, 'Scripts', 'pyinstaller.exe')
        else:
            # Linux 和 macOS 使用冒号分隔
            separator = ':'
            # 指定 PyInstaller 可执行文件路径
            pyinstaller_path = os.path.join(sys.prefix, 'bin', 'pyinstaller')

        return pyinstaller_path

    @classmethod
    def _is_windows(cls):
        return sys.platform.startswith('win')

    @classmethod
    def build(cls, conda_env, name, enter_file, icon, datas=[], excludes=[], hidden_imports=[]):
        """
        使用 PyInstaller 打包
        :param conda_env: conda环境名称
        :param name: 应用名称
        :param enter_file: 入口文件
        :param icon: 图标
        :param datas: List[Tuple[str, str]]打包的资源文件,
        :param excludes: 排除的模块
        :param hidden_imports: 隐式导入模块
        """

        # 设置标准输出编码为 UTF-8
        # sys.stdout.reconfigure(encoding='utf-8')
        cmd_segs = ["conda", "activate", conda_env, "&" if cls._is_windows() else '&&', "pyinstaller", '--onefile', '--clean', '-y',
                    '-w', f'-n={name}']
        if icon:
            # cmd_segs.append(f'--icon={os.path.join(current_dir, icon)}')
            cmd_segs.append(f'--icon={icon}')
        if excludes:
            for exclude in excludes:
                cmd_segs.append(f'--exclude-module={exclude}')
        if hidden_imports:
            for hidden_import in hidden_imports:
                cmd_segs.append(f'--hidden-import={hidden_import}')

        cmd_segs.append(enter_file)

        try:
            # 执行打包命令，捕获标准输出和标准错误输出
            print(f"开始打包{name}...")
            result = subprocess.run(cmd_segs, stderr=subprocess.STDOUT, stdout=subprocess.PIPE, text=True, shell=True,
                                    encoding="utf-8")
            result.check_returncode()
            # 打印命令执行的输出信息
            print(result.stdout)
            print("恭喜：应用程序打包成功！")
        except subprocess.CalledProcessError as e:
            # 打印错误信息
            print(f"打包失败: {e}")
            print(e.stdout)
            return
        # 应用目录
        app_dir = cls._create_app_dir(name)
        # exe移动到应用目录
        shutil.move(Path(app_dir).parent / f"{name}.exe", app_dir)

        print("开始复制资源文件...")
        if datas:
            for data in datas:
                src, dst = data
                dst_dir = os.path.join(app_dir, dst)
                if not os.path.exists(dst_dir):
                    os.makedirs(dst_dir)

                if os.path.isfile(src):
                    shutil.copy2(src, dst_dir)
                elif os.path.isdir(src):
                    shutil.copytree(src, dst_dir, dirs_exist_ok=True)
                print(f"已将 {src} 复制到 {dst_dir}")
        print("资源文件复制完成！整个流程完成！")

    @classmethod
    def _create_app_dir(cls, app_name):
        app_dir = os.path.join(os.getcwd(), "dist", app_name)
        if not os.path.exists(os.path.join(app_dir)):
            os.mkdir(app_dir)
        else:
            # 删除旧的目录
            shutil.rmtree(app_dir)
            # 重新建立目录
            os.mkdir(app_dir)

        return app_dir


def build_xianyu_tools():
    """
    构建闲鱼助手
    :return:
    """
    data = [(".\\xianyu.ico", ""), (".\\conf\\config.ini", "conf"), (".\\conf\\node.exe", "conf")]
    hidden_import = ["comtypes.stream"]
    excludes = ["ddddocr", "cv2"]
    PyInstallerBuilder.build('write_robot', '闲鱼助手V1.0.0', '.\\xianyu_tools\\ui2.py', '.\\xianyu.ico', data,
                             excludes, hidden_import)


def build_encrypt_machine():
    """
    构建加密机
    :return:
    """
    data = [(".\\crypto_machine.ico", "")]
    hidden_import = ["comtypes.stream"]
    excludes = ["ddddocr", "cv2", "pandas"]
    PyInstallerBuilder.build('write_robot', '加密机V1.0.2', '.\\encrypt_machine\\ui.py', '.\\crypto_machine.ico', data,
                             excludes, hidden_import)


def build_kele_picture_helper():
    """
    构建可乐图片助手
    :return:
    """
    data = [(".\\kele.ico", ""), (".\\conf\\config.ini", "conf")]
    hidden_import = ["comtypes.stream"]
    excludes = ["ddddocr", "cv2"]
    PyInstallerBuilder.build('write_robot', '可乐图片工具V1.0.0', '.\\rpa\\kele_picture_helper\\ui.py', '.\\kele.ico',
                             data,
                             excludes, hidden_import)


def build_dxm_publish_helper():
    """
    构建店小秘发布助手
    :return:
    """
    data = [(".\\dxm.ico", ""), (".\\conf\\config.ini", "conf"), (".\\conf\\chromedriver.exe", "conf"),
            (".\\Chrome", "Chrome")]
    hidden_import = ["comtypes.stream"]
    excludes = ["ddddocr", "cv2"]
    PyInstallerBuilder.build('write_robot', '秘仔上架助手V1.0.0', '.\\rpa\\dxm_publish_helper\\ui.py', '.\\dxm.ico',
                             data,
                             excludes, hidden_import)


class XGSBuilder(PyInstallerBuilder):
    # 原始常量文件路径
    CONSTANTS_FILE = r"D:\PycharmProjects\webAutomationFramework\src\frame\common\constants.py"
    # 打包时要替换的参数（可根据需要修改）
    TARGET_APP_NAME = "小怪兽"  # 替换后的应用名
    TARGET_VERSION = "2.1.0"  # 替换后的版本号
    TARGET_IS_ACTIVATION = False  # 替换后的激活状态
    ICON = '.\\xgs.ico'  # 图标文件路径，相对路径，相对于当前文件

    ADD_DATAS = [(".\\xgs.ico", ""),
                 (".\\conf\\public_key.pem", "conf"),
                 # (".\\conf\\chromedriver.exe", "conf"),
                 (".\\conf\\playwright_stealth_js", "conf\\playwright_stealth_js"),
                 (".\\Chrome", "Chrome"),
                 # (r"c:\users\lovel\.conda\envs\web_automation_framework\Lib\site-packages\onnxruntime\capi\onnxruntime_providers_shared.dll", r".\onnxruntime\capi"),
                 # (r"c:\users\lovel\.conda\envs\web_automation_framework\Lib\site-packages\ddddocr\common_old.onnx", r".\ddddocr"),
                 # (r"c:\users\lovel\.conda\envs\web_automation_framework\Lib\site-packages\ddddocr\common.onnx", r".\ddddocr")
                 ]

    CONDA_ENV = 'web_automation_framework'
    ENTER_FILE = '.\\src\\ui\\ui_main_window.py'
    HIDDEN_IMPORTS = ["comtypes.stream"]
    EXCLUDES = []

    @classmethod
    def backup_file(cls, file_path):
        """备份文件（防止替换后丢失原内容）"""
        backup_path = f"{file_path}.bak"
        if not os.path.exists(backup_path):
            shutil.copy2(file_path, backup_path)
        return backup_path

    @classmethod
    def restore_file(cls, original_path, backup_path):
        """恢复原始文件"""
        if os.path.exists(backup_path):
            shutil.copy2(backup_path, original_path)
            os.remove(backup_path)

    @classmethod
    def replace_constants(cls, file_path):
        """替换constants.py中的目标变量值"""
        # 读取原文件内容
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 替换变量值（正则替换更严谨，这里用简单字符串替换）
        content = content.replace(
            f'APP_NAME = "小怪兽"',
            f'APP_NAME = "{cls.TARGET_APP_NAME}"'
        )
        content = content.replace(
            f'VERSION = "1.0.0"',
            f'VERSION = "{cls.TARGET_VERSION}"'
        )
        content = content.replace(
            f'IS_NEED_ACTIVATION = True',
            f'IS_NEED_ACTIVATION = {cls.TARGET_IS_ACTIVATION}'
        )

        # 写入替换后的内容
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)

    @classmethod
    def do_build(cls):
        # 1. 备份原始常量文件
        backup_path = cls.backup_file(cls.CONSTANTS_FILE)
        print(f"已备份常量文件到：{backup_path}")

        try:
            # 2. 替换常量值
            cls.replace_constants(cls.CONSTANTS_FILE)
            print(
                f"已替换常量：APP_NAME={cls.TARGET_APP_NAME}, VERSION={cls.TARGET_VERSION}, IS_NEED_ACTIVATION={cls.TARGET_IS_ACTIVATION}")

            # 3. 调用PyInstaller打包
            super().build(cls.CONDA_ENV, f"{cls.TARGET_APP_NAME}V{cls.TARGET_VERSION}",
                          cls.ENTER_FILE, cls.ICON, cls.ADD_DATAS,
                          cls.EXCLUDES, cls.HIDDEN_IMPORTS)
        finally:
            # 4. 恢复原始常量文件
            cls.restore_file(cls.CONSTANTS_FILE, backup_path)
            print(f"已恢复常量文件：{cls.CONSTANTS_FILE}")


def build_xgs():
    """
    构建小怪兽
    :return:
    """
    # 打包时要替换的参数（可根据需要修改）
    XGSBuilder.TARGET_VERSION = "1.0.2"  # 替换后的版本号
    XGSBuilder.TARGET_IS_ACTIVATION = False  # 替换后的激活状态
    XGSBuilder.do_build()  # 打包


if __name__ == '__main__':
    # build_encrypt_machine()
    # build_xianyu_tools()
    # build_kele_picture_helper()
    # build_dxm_publish_helper()
    build_xgs()
    # src = r"D:\PycharmProjects\write_robot\Chrome"
    # dst_dir = r"D:\PycharmProjects\write_robot\dist\秘仔上架助手V1.0.0\Chrome"
    # shutil.copytree(src, dst_dir, dirs_exist_ok=True)