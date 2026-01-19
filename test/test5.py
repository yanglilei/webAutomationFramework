import sys
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout,
    QHBoxLayout, QRadioButton, QButtonGroup, QLabel,
    QPushButton, QFrame, QSizePolicy
)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class SubWindow(QMainWindow):
    """子窗口：用于展示UI变动的窗口"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("运行模式展示窗口")
        self.setGeometry(200, 200, 400, 300)

        # 初始化UI
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # 模式状态显示标签
        self.mode_label = QLabel("当前运行模式：未选择")
        self.mode_label.setFont(QFont("Arial", 14, QFont.Bold))
        self.mode_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(self.mode_label)

        # 分隔线
        self.line = QFrame()
        self.line.setFrameShape(QFrame.HLine)
        self.line.setFrameShadow(QFrame.Sunken)
        self.main_layout.addWidget(self.line)

        # 动态变化的UI区域
        self.dynamic_widget = QWidget()
        self.dynamic_layout = QVBoxLayout(self.dynamic_widget)
        self.main_layout.addWidget(self.dynamic_widget)

        # 初始化动态UI（默认无选择）
        self.update_ui_by_mode(None)

    def update_ui_by_mode(self, mode):
        """根据运行模式更新子窗口UI

        Args:
            mode: str - "全自动" 或 "半自动" 或 None
        """
        # 清空原有动态UI元素
        for i in reversed(range(self.dynamic_layout.count())):
            widget = self.dynamic_layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()

        # 更新模式显示
        if mode == "全自动":
            self.mode_label.setText("当前运行模式：全自动")
            # 全自动模式下的UI元素
            auto_label = QLabel("✅ 全自动模式特性：")
            auto_label.setFont(QFont("Arial", 12))
            self.dynamic_layout.addWidget(auto_label)

            auto_features = [
                "• 无需人工干预，自动完成所有流程",
                "• 自动检测异常并尝试恢复",
                "• 运行日志自动保存到指定路径"
            ]
            for feature in auto_features:
                feature_label = QLabel(feature)
                self.dynamic_layout.addWidget(feature_label)

        elif mode == "半自动":
            self.mode_label.setText("当前运行模式：半自动")
            # 半自动模式下的UI元素
            semi_label = QLabel("⚠️ 半自动模式特性：")
            semi_label.setFont(QFont("Arial", 12))
            self.dynamic_layout.addWidget(semi_label)

            semi_features = [
                "• 关键步骤需要人工确认后继续",
                "• 异常时暂停并弹出提示框",
                "• 支持手动调整运行参数"
            ]
            for feature in semi_features:
                feature_label = QLabel(feature)
                self.dynamic_layout.addWidget(feature_label)

        else:
            self.mode_label.setText("当前运行模式：未选择")
            tip_label = QLabel("请在主窗口选择运行模式")
            tip_label.setAlignment(Qt.AlignCenter)
            self.dynamic_layout.addWidget(tip_label)


class MainWindow(QMainWindow):
    """主窗口：包含运行模式选择"""
    # 定义自定义信号，用于传递模式选择结果
    mode_selected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("运行模式选择")
        self.setGeometry(100, 100, 400, 200)

        # 创建子窗口实例
        self.sub_window = SubWindow()

        # 初始化主窗口UI
        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.main_layout = QVBoxLayout(self.central_widget)

        # 标题
        title_label = QLabel("运行模式选择")
        title_label.setFont(QFont("Arial", 16, QFont.Bold))
        title_label.setAlignment(Qt.AlignCenter)
        self.main_layout.addWidget(title_label)

        # 单选按钮组布局
        radio_layout = QHBoxLayout()

        # 创建单选按钮组
        self.mode_group = QButtonGroup(self)

        # 全自动单选按钮
        self.auto_radio = QRadioButton("全自动模式")
        self.auto_radio.setFont(QFont("Arial", 12))
        self.mode_group.addButton(self.auto_radio, 1)
        radio_layout.addWidget(self.auto_radio)

        # 半自动单选按钮
        self.semi_radio = QRadioButton("半自动模式")
        self.semi_radio.setFont(QFont("Arial", 12))
        self.mode_group.addButton(self.semi_radio, 2)
        radio_layout.addWidget(self.semi_radio)

        self.main_layout.addLayout(radio_layout)

        # 打开子窗口按钮
        self.open_sub_btn = QPushButton("打开模式展示窗口")
        self.open_sub_btn.setFont(QFont("Arial", 12))
        self.main_layout.addWidget(self.open_sub_btn)

        # 信号与槽连接
        # 单选按钮状态变化时触发模式更新
        self.mode_group.buttonClicked[int].connect(self.on_mode_changed)
        # 打开子窗口按钮点击事件
        self.open_sub_btn.clicked.connect(self.open_sub_window)
        # 将主窗口的自定义信号连接到子窗口的UI更新函数
        self.mode_selected.connect(self.sub_window.update_ui_by_mode)

        # ========== 关键修改：设置默认选中全自动模式 ==========
        # 1. 设置单选按钮默认选中
        self.auto_radio.setChecked(True)
        # 2. 手动触发模式更新，让子窗口同步显示全自动UI
        self.on_mode_changed(1)

    def on_mode_changed(self, btn_id):
        """单选按钮选择变化时的处理函数"""
        if btn_id == 1:
            self.mode_selected.emit("全自动")
        elif btn_id == 2:
            self.mode_selected.emit("半自动")

    def open_sub_window(self):
        """打开子窗口"""
        self.sub_window.show()


if __name__ == "__main__":
    try:
        # 创建应用程序实例
        app = QApplication(sys.argv)

        # 创建并显示主窗口
        main_win = MainWindow()
        main_win.show()

        # 运行应用程序
        sys.exit(app.exec_())
    except Exception as e:
        print(e)