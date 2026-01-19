import hashlib
import logging
import os
import platform
import re
import subprocess
from typing import Dict, Tuple


class HardwareFingerprint:
    def __init__(self, salt: str = None, debug: bool = False,
                 vm_activation_allowed: bool = True,
                 clone_detection_threshold: float = 0.8):
        """初始化硬件指纹生成器

        Args:
            salt: 用于哈希的盐值，默认随机生成
            debug: 是否启用调试模式
            vm_activation_allowed: 是否允许在虚拟机中激活
            clone_detection_threshold: 硬件变更检测阈值
        """
        self.salt = salt or os.urandom(16).hex()
        # self.salt = ""
        self.debug = debug
        self.vm_activation_allowed = vm_activation_allowed
        self.clone_detection_threshold = clone_detection_threshold
        self.logger = self._setup_logger()

        # 虚拟机检测特征库
        self.known_vm_signatures = [
            "VMware", "VirtualBox", "Hyper-V", "QEMU", "Parallels",
            "Bochs", "Virtual Machine", "Xen", "VMW"
        ]

        # 硬件参数权重配置（基于唯一性和稳定性）
        self.hardware_weights = {
            'cpu_id': 0.4,
            'motherboard_id': 0.3,
            'disk_id': 0.3,
            # 'mac_address': 0.05,
            # 'vm_instance_id': 0.05  # 虚拟机实例ID作为额外特征
        }

        # 已生成的指纹缓存（用于检测克隆）
        # self.generated_fingerprints = set()

    def _setup_logger(self) -> logging.Logger:
        """配置日志记录"""
        logger = logging.getLogger("hardware_fingerprint")
        logger.setLevel(logging.DEBUG if self.debug else logging.INFO)
        ch = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        logger.addHandler(ch)
        return logger

    def _get_os(self) -> str:
        """获取当前操作系统类型"""
        return platform.system()

    def _is_vm_advanced(self) -> bool:
        """增强版虚拟机检测，结合系统特征和硬件参数"""
        try:
            os_type = self._get_os()

            # 系统层面检测
            if os_type == "Windows":
                # 检查注册表
                # output = subprocess.check_output(
                #     'reg query "HKEY_LOCAL_MACHINE\\HARDWARE\\DESCRIPTION\\System\\BIOS"',
                #     shell=True,
                #     stderr=subprocess.STDOUT
                # ).decode('utf-8', errors='ignore')
                output = subprocess.check_output(
                    'reg query "HKEY_LOCAL_MACHINE\\HARDWARE\\DESCRIPTION\\System\\BIOS"',
                    shell=True,
                    stderr=subprocess.STDOUT
                )
                if isinstance(output, bytes):
                    output = output.decode('utf-8', errors='ignore')

                for signature in self.known_vm_signatures:
                    if signature.lower() in output.lower():
                        self.logger.warning(f"检测到虚拟机环境: {signature}")
                        return True

                # 检查设备驱动
                output = subprocess.check_output(
                    'wmic path win32_VideoController get Name',
                    shell=True,
                    stderr=subprocess.STDOUT
                )
                if isinstance(output, bytes):
                    output = output.decode('utf-8', errors='ignore')

                for signature in self.known_vm_signatures:
                    if signature.lower() in output.lower():
                        self.logger.warning(f"检测到虚拟机显卡: {signature}")
                        return True

            elif os_type == "Darwin":  # macOS
                # 检查IOKit注册表
                output = subprocess.check_output(
                    "ioreg -l | grep -i 'vendor'",
                    shell=True,
                    stderr=subprocess.STDOUT
                )
                if isinstance(output, bytes):
                    output = output.decode('utf-8', errors='ignore')

                for signature in self.known_vm_signatures:
                    if signature.lower() in output.lower():
                        self.logger.warning(f"检测到虚拟机环境: {signature}")
                        return True

            elif os_type == "Linux":
                # 检查/proc/cpuinfo和dmesg
                with open('/proc/cpuinfo', 'r') as f:
                    cpu_info = f.read().lower()
                    for signature in self.known_vm_signatures:
                        if signature.lower() in cpu_info:
                            self.logger.warning(f"检测到虚拟机CPU: {signature}")
                            return True

                output = subprocess.check_output(
                    "dmesg | grep -i 'virtual'",
                    shell=True,
                    stderr=subprocess.STDOUT
                )
                if isinstance(output, bytes):
                    output = output.decode('utf-8', errors='ignore')

                for signature in self.known_vm_signatures:
                    if signature.lower() in output.lower():
                        self.logger.warning(f"检测到虚拟机环境: {signature}")
                        return True

            # 硬件层面检测（避免递归调用，改用直接命令）
            if os_type == "Windows":
                # 检查处理器信息
                output = subprocess.check_output(
                    'wmic cpu get Name',
                    shell=True,
                    stderr=subprocess.STDOUT
                )

                if isinstance(output, bytes):
                    output = output.decode('utf-8', errors='ignore')

                for signature in self.known_vm_signatures:
                    if signature.lower() in output.lower():
                        self.logger.warning(f"检测到虚拟机CPU: {signature}")
                        return True

            elif os_type == "Linux":
                # 检查DMI信息
                try:
                    output = subprocess.check_output(
                        "dmidecode -s system-product-name",
                        shell=True,
                        stderr=subprocess.STDOUT
                    )

                    if isinstance(output, bytes):
                        output = output.decode('utf-8', errors='ignore')

                    for signature in self.known_vm_signatures:
                        if signature.lower() in output.lower():
                            self.logger.warning(f"检测到虚拟机系统: {signature}")
                            return True
                except:
                    pass

            return False
        except Exception as e:
            self.logger.error(f"虚拟机检测失败: {str(e)}")
            return False

    def _get_hardware_info(self) -> Dict[str, str]:
        """根据操作系统获取硬件信息"""
        os_type = self._get_os()

        if os_type == "Windows":
            return self._get_windows_hardware_info()
        elif os_type == "Darwin":  # macOS
            return self._get_macos_hardware_info()
        elif os_type == "Linux":
            return self._get_linux_hardware_info()
        else:
            self.logger.error(f"不支持的操作系统: {os_type}")
            return {}

    def _get_windows_hardware_info(self) -> Dict[str, str]:
        """获取Windows系统的硬件信息"""
        hardware_info = {}

        try:
            # 获取CPU信息
            output = subprocess.check_output(
                'wmic cpu get ProcessorId',
                shell=True,
                stderr=subprocess.STDOUT
            )
            if isinstance(output, bytes):
                output = output.decode('utf-8', errors='ignore')

            match = re.search(r'ProcessorId\s+([^\s]+)', output)
            if match:
                hardware_info['cpu_id'] = match.group(1).strip()

            # 获取主板信息
            output = subprocess.check_output(
                'wmic baseboard get SerialNumber',
                shell=True,
                stderr=subprocess.STDOUT
            )
            if isinstance(output, bytes):
                output = output.decode('utf-8', errors='ignore')
            match = re.search(r'SerialNumber\s+([^\s]+)', output)
            if match:
                hardware_info['motherboard_id'] = match.group(1).strip()

            # 获取硬盘信息
            output = subprocess.check_output(
                'wmic diskdrive get SerialNumber',
                shell=True,
                stderr=subprocess.STDOUT
            )
            if isinstance(output, bytes):
                output = output.decode('utf-8', errors='ignore')

            match = re.search(r'SerialNumber\s+([^\s]+)', output)
            if match:
                hardware_info['disk_id'] = match.group(1).strip()

            # 获取网卡MAC地址
            output = subprocess.check_output(
                'wmic nic where "NetEnabled=True" get MACAddress',
                shell=True,
                stderr=subprocess.STDOUT
            )
            if isinstance(output, bytes):
                output = output.decode('utf-8', errors='ignore')
            match = re.search(r'MACAddress\s+([^\s]+)', output)
            if match:
                hardware_info['mac_address'] = match.group(1).strip()

            # 获取虚拟机实例ID（如果是虚拟机）
            if self._is_vm_advanced():
                hardware_info['vm_instance_id'] = self._get_windows_vm_instance_id()

        except Exception as e:
            self.logger.error(f"获取Windows硬件信息失败: {str(e)}")

        return hardware_info

    def _get_windows_vm_instance_id(self) -> str:
        """获取Windows虚拟机的唯一实例ID"""
        try:
            # 尝试获取VMware实例ID
            output = subprocess.check_output(
                'powershell -Command "Get-ItemProperty -Path HKLM:\\SOFTWARE\\VMware, Inc.\\VMware Tools -ErrorAction SilentlyContinue | Select-Object -ExpandProperty InstallPath"',
                shell=True,
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore').strip()

            if output and "VMware" in output:
                vmx_path = os.path.join(output, "..\\vmware-vmx.exe")
                vmx_path = os.path.normpath(vmx_path)
                if os.path.exists(vmx_path):
                    # 执行vmx命令获取uuid
                    vmx_output = subprocess.check_output(
                        f'"{vmx_path}" -Q get uuid.bios',
                        shell=True,
                        stderr=subprocess.STDOUT
                    ).decode('utf-8', errors='ignore')
                    match = re.search(r'uuid.bios = "([^"]+)"', vmx_output)
                    if match:
                        return match.group(1)

            # 尝试获取VirtualBox实例ID
            try:
                output = subprocess.check_output(
                    'VBoxManage list runningvms',
                    shell=True,
                    stderr=subprocess.STDOUT
                ).decode('utf-8', errors='ignore')
                match = re.search(r'"([^"]+)" \{([^}]+)\}', output)
                if match:
                    return match.group(2)
            except:
                pass

        except Exception as e:
            self.logger.error(f"获取Windows虚拟机实例ID失败: {str(e)}")

        return ""

    def _get_macos_hardware_info(self) -> Dict[str, str]:
        """获取macOS系统的硬件信息"""
        hardware_info = {}

        try:
            # 获取CPU信息
            output = subprocess.check_output(
                "sysctl -n machdep.cpu.brand_string",
                shell=True,
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')
            hardware_info['cpu_info'] = output.strip()

            # 获取主板信息
            output = subprocess.check_output(
                "ioreg -l | grep IOPlatformSerialNumber",
                shell=True,
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')
            match = re.search(r'"IOPlatformSerialNumber" = "([^"]+)"', output)
            if match:
                hardware_info['motherboard_id'] = match.group(1).strip()

            # 获取硬盘信息
            output = subprocess.check_output(
                "diskutil info / | grep 'Volume UUID'",
                shell=True,
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')
            match = re.search(r'Volume UUID:\s+([^\s]+)', output)
            if match:
                hardware_info['disk_id'] = match.group(1).strip()

            # 获取网卡MAC地址
            output = subprocess.check_output(
                "ifconfig en0 | grep ether",
                shell=True,
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')
            match = re.search(r'ether\s+([^\s]+)', output)
            if match:
                hardware_info['mac_address'] = match.group(1).strip()

            # 获取虚拟机实例ID（如果是虚拟机）
            if self._is_vm_advanced():
                hardware_info['vm_instance_id'] = self._get_macos_vm_instance_id()

        except Exception as e:
            self.logger.error(f"获取macOS硬件信息失败: {str(e)}")

        return hardware_info

    def _get_macos_vm_instance_id(self) -> str:
        """获取macOS虚拟机的唯一实例ID"""
        try:
            # 检查是否为Parallels虚拟机
            output = subprocess.check_output(
                "ioreg -l | grep Parallels",
                shell=True,
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')

            if "Parallels" in output:
                # 获取Parallels虚拟机ID
                output = subprocess.check_output(
                    "prlctl list -a --json",
                    shell=True,
                    stderr=subprocess.STDOUT
                ).decode('utf-8', errors='ignore')
                match = re.search(r'"uuid":\s*"([^"]+)"', output)
                if match:
                    return match.group(1)

            # 检查是否为VMware Fusion
            output = subprocess.check_output(
                "ioreg -l | grep VMware",
                shell=True,
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')

            if "VMware" in output:
                # 获取VMware虚拟机ID
                output = subprocess.check_output(
                    "ps aux | grep vmware-vmx",
                    shell=True,
                    stderr=subprocess.STDOUT
                ).decode('utf-8', errors='ignore')
                match = re.search(r'/Users/[^/]+/Documents/Virtual\ Machines.localized/([^/]+)/', output)
                if match:
                    return match.group(1)

        except Exception as e:
            self.logger.error(f"获取macOS虚拟机实例ID失败: {str(e)}")

        return ""

    def _get_linux_hardware_info(self) -> Dict[str, str]:
        """获取Linux系统的硬件信息"""
        hardware_info = {}

        try:
            # 获取CPU信息
            with open('/proc/cpuinfo', 'r') as f:
                for line in f:
                    if line.startswith('model name'):
                        hardware_info['cpu_info'] = line.split(':')[1].strip()
                        break

            # 获取主板信息
            output = subprocess.check_output(
                "dmidecode -t 0 | grep 'System Serial Number'",
                shell=True,
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')
            match = re.search(r'System Serial Number:\s+([^\s]+)', output)
            if match:
                hardware_info['motherboard_id'] = match.group(1).strip()

            # 获取硬盘信息
            output = subprocess.check_output(
                "blkid | grep -i 'UUID'",
                shell=True,
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')
            match = re.search(r'UUID="([^"]+)"', output)
            if match:
                hardware_info['disk_id'] = match.group(1).strip()

            # 获取网卡MAC地址
            output = subprocess.check_output(
                "ifconfig eth0 | grep ether",
                shell=True,
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')
            match = re.search(r'ether\s+([^\s]+)', output)
            if match:
                hardware_info['mac_address'] = match.group(1).strip()

            # 获取虚拟机实例ID（如果是虚拟机）
            if self._is_vm_advanced():
                hardware_info['vm_instance_id'] = self._get_linux_vm_instance_id()

        except Exception as e:
            self.logger.error(f"获取Linux硬件信息失败: {str(e)}")

        return hardware_info

    def _get_linux_vm_instance_id(self) -> str:
        """获取Linux虚拟机的唯一实例ID"""
        try:
            # 检查是否为KVM/QEMU虚拟机
            output = subprocess.check_output(
                "dmesg | grep -i kvm",
                shell=True,
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')

            if "kvm" in output.lower():
                # 获取libvirt域ID
                try:
                    output = subprocess.check_output(
                        "virsh list --all --name",
                        shell=True,
                        stderr=subprocess.STDOUT
                    ).decode('utf-8', errors='ignore')
                    domains = output.strip().split('\n')
                    if domains and domains[0]:
                        return domains[0]
                except:
                    pass

            # 检查是否为VMware虚拟机
            output = subprocess.check_output(
                "dmesg | grep -i vmware",
                shell=True,
                stderr=subprocess.STDOUT
            ).decode('utf-8', errors='ignore')

            if "vmware" in output.lower():
                # 获取VMware虚拟机UUID
                try:
                    with open('/sys/class/dmi/id/product_uuid', 'r') as f:
                        return f.read().strip()
                except:
                    pass

        except Exception as e:
            self.logger.error(f"获取Linux虚拟机实例ID失败: {str(e)}")

        return ""

    def _sanitize_value(self, value: str) -> str:
        """清理和标准化硬件值"""
        if not value:
            return ""
        # 转换为小写并去除空格和特殊字符
        return re.sub(r'[^a-z0-9]', '', value.lower())

    def _weighted_hash(self, hardware_info: Dict[str, str]) -> str:
        """生成加权哈希值"""
        combined = ""

        # 按权重组合硬件参数
        for key, weight in self.hardware_weights.items():
            if key in hardware_info and hardware_info[key]:
                # 应用权重：将权重乘以100作为前缀，增加哈希的唯一性
                sanitized_value = self._sanitize_value(hardware_info[key])
                if sanitized_value:
                    combined += f"{int(weight * 100)}{sanitized_value}"

        # 添加盐值增强安全性
        combined += self.salt

        # 计算SHA-256哈希
        # return hashlib.sha256(combined.encode('utf-8')).hexdigest()
        # 创建 MD5 对象
        m = hashlib.md5()
        # 更新 MD5 对象的内容
        m.update(combined.encode('utf-8'))
        # 获取加密后的十六进制字符串
        return m.hexdigest()

    def generate_fingerprint(self) -> Tuple[str, Dict[str, str]]:
        """生成硬件指纹

        Returns:
            元组：(指纹哈希值, 采集的硬件信息)
        """
        # 检测虚拟机环境
        is_vm = self._is_vm_advanced()

        if is_vm and not self.vm_activation_allowed:
            self.logger.warning("在虚拟机中尝试生成指纹，但已配置为禁止虚拟机激活")
            return None, {}

        # 获取硬件信息
        hardware_info = self._get_hardware_info()

        # 添加操作系统信息作为额外特征
        hardware_info['os_info'] = platform.platform()

        # 生成指纹
        fingerprint = self._weighted_hash(hardware_info)
        # self.logger.info(f"生成的硬件指纹: {fingerprint[:10]}...（已截断）")

        # 检测克隆风险
        # if fingerprint in self.generated_fingerprints:
        #     self.logger.warning(f"检测到可能的虚拟机克隆: 指纹 {fingerprint[:10]}... 已被生成过")
        # self.generated_fingerprints.add(fingerprint)

        return fingerprint, hardware_info

    def verify_fingerprint(self, stored_fingerprint: str, hardware_info: Dict[str, str] = None) -> bool:
        """验证硬件指纹

        Args:
            stored_fingerprint: 存储的指纹哈希值
            hardware_info: 可选的硬件信息，若不提供则重新采集

        Returns:
            指纹是否匹配
        """
        # 如果没有提供硬件信息，则重新获取
        if not hardware_info:
            _, current_hardware_info = self.generate_fingerprint()
        else:
            current_hardware_info = hardware_info

        # 重新生成当前指纹
        current_fingerprint = self._weighted_hash(current_hardware_info)

        # 比较指纹
        is_valid = current_fingerprint == stored_fingerprint
        self.logger.info(f"指纹验证结果: {'有效' if is_valid else '无效'}")

        return is_valid

    def detect_hardware_change(self, old_hardware_info: Dict[str, str],
                               new_hardware_info: Dict[str, str],
                               threshold: float = None) -> bool:
        """检测硬件变更（相似度低于阈值则认为有变更）

        Args:
            old_hardware_info: 旧的硬件信息
            new_hardware_info: 新的硬件信息
            threshold: 相似度阈值，默认使用初始化时的值

        Returns:
            是否检测到硬件变更
        """
        threshold = threshold or self.clone_detection_threshold

        # 计算相似度
        matched_count = 0
        total_count = 0

        for key in ['cpu_id', 'motherboard_id', 'disk_id', 'mac_address', 'vm_instance_id']:
            if key in old_hardware_info and key in new_hardware_info:
                total_count += 1
                if self._sanitize_value(old_hardware_info[key]) == self._sanitize_value(new_hardware_info[key]):
                    matched_count += 1

        if total_count == 0:
            return False

        similarity = matched_count / total_count
        self.logger.info(f"硬件相似度: {similarity:.2f} (阈值: {threshold})")

        return similarity < threshold


# 使用示例
if __name__ == "__main__":
    # 创建指纹生成器实例（可指定自定义盐值）
    fp_generator = HardwareFingerprint(vm_activation_allowed=True)
    # hardware_weights = {
    #     'cpu_id': 0.4,
    #     'motherboard_id': 0.3,
    #     'disk_id': 0.2,
    #     'mac_address': 0.05,
    #     'vm_instance_id': 0.05  # 虚拟机实例ID作为额外特征
    # }

    # 生成指纹
    fingerprint, hardware_info = fp_generator.generate_fingerprint()

    print("\n=== 硬件指纹信息 ===")
    print(f"指纹: {fingerprint}")

    print("\n=== 采集的硬件信息 ===")
    for key, value in hardware_info.items():
        print(f"{key}: {value}")

    # 验证指纹
    is_valid = fp_generator.verify_fingerprint(fingerprint)
    print(f"\n指纹验证结果: {'有效' if is_valid else '无效'}")

    # 模拟硬件变更检测（这里使用相同信息，实际应比较不同时间的硬件信息）
    is_changed = fp_generator.detect_hardware_change(hardware_info, hardware_info)
    print(f"硬件变更检测结果: {'有变更' if is_changed else '无变更'}")
