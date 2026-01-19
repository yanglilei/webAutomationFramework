import os
import subprocess
import sys
from typing import List, Optional
import logging
# 替换 pkg_resources，使用标准库 importlib.metadata
from importlib.metadata import PackageNotFoundError, distribution

class ComponentDependencyManager:
    """组件第三方依赖管理器"""
    @staticmethod
    def _get_component_requirements_path(component_path: str) -> Optional[str]:
        """获取组件对应的requirements.txt路径"""
        component_dir = os.path.dirname(component_path)
        requirements_path = os.path.join(component_dir, "requirements.txt")
        return requirements_path if os.path.exists(requirements_path) else None

    @staticmethod
    def _parse_requirements(requirements_path: str) -> List[str]:
        """解析requirements.txt，返回依赖列表"""
        dependencies = []
        with open(requirements_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#"):
                    dependencies.append(line)
        return dependencies

    @staticmethod
    def check_dependency(dep_name: str) -> bool:
        """检查单个依赖是否已安装（替换 pkg_resources 实现）"""
        try:
            # 提取纯包名（去掉版本号信息）
            package_name, target_version = dep_name.split("==")
            # 1. 获取分发包对象（不存在则抛出PackageNotFoundError）
            dist = distribution(package_name.strip())
            # 2. 获取已安装的版本号
            installed_version = dist.version
            # 3. 比对版本（精确比对，如需模糊比对可使用packaging库）
            target_version = target_version.strip()
            if installed_version == target_version:
                logging.info(f"✅ 已安装 {package_name} {target_version}（当前版本：{installed_version}）")
                return True
            else:
                logging.error(
                    f"❌ 已安装 {package_name}，但版本不匹配（当前版本：{installed_version}，目标版本：{target_version}）")
                return False
        except PackageNotFoundError:
            # 替代 pkg_resources.DistributionNotFound 异常
            return False

    @staticmethod
    def install_dependency(dep_name: str, install_dir: Optional[str] = None):
        """安装单个依赖（支持自定义安装目录）"""
        # 构造安装命令
        cmd = [sys.executable, "-m", "pip", "install", dep_name]
        # 自定义安装目录（避免污染全局环境）
        if install_dir:
            os.makedirs(install_dir, exist_ok=True)
            cmd.extend(["--target", install_dir])
            # 将安装目录加入系统路径
            if install_dir not in sys.path:
                sys.path.append(install_dir)

        # 执行安装
        try:
            subprocess.check_call(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            return True
        except subprocess.CalledProcessError as e:
            raise Exception(f"依赖{dep_name}安装失败：{e.stderr.decode('utf-8')}")

    def handle_component_dependencies(self, component_path: str, custom_install_dir: str) -> bool:
        """
        处理组件依赖：检测并自动安装缺失依赖
        :param component_path: 组件文件路径
        :param custom_install_dir: 组件依赖统一安装目录
        :return: 依赖处理是否成功
        """
        # 1. 获取requirements.txt
        requirements_path = self._get_component_requirements_path(component_path)
        if not requirements_path:
            return True  # 无依赖文件，直接返回成功
        # 避免重复安装，check_dependency的时候会进入该目录监测
        if custom_install_dir not in sys.path:
            sys.path.append(custom_install_dir)
        # 2. 解析依赖列表
        dependencies = self._parse_requirements(requirements_path)
        if not dependencies:
            return True

        # 3. 检查并安装缺失依赖
        for dep in dependencies:
            if not self.check_dependency(dep):
                logging.info(f"组件依赖{dep}未安装，正在自动安装...")
                try:
                    self.install_dependency(dep, custom_install_dir)
                    logging.info(f"依赖{dep}安装成功")
                except Exception as e:
                    logging.error(f"依赖{dep}安装失败：{e}")
                    return False

        # 4. 将自定义依赖目录加入系统路径
        if custom_install_dir not in sys.path:
            sys.path.append(custom_install_dir)

        return True