from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import (
    QApplication, QVBoxLayout, QHBoxLayout,
    QPushButton, QDialog, QTextEdit, QLabel
)


# 自定义弹窗：展示单元格完整内容
class CellContentDialog(QDialog):
    """双击单元格弹出的完整内容查看窗口"""

    def __init__(self, cell_text, row, col, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"单元格内容（行{row + 1}，列{col + 1}）")  # 行/列从1开始显示，更友好
        self.setMinimumSize(500, 300)  # 最小窗口尺寸
        self.setModal(True)  # 模态窗口，阻塞其他操作

        # 初始化UI
        self.init_ui(cell_text)

    def init_ui(self, cell_text):
        layout = QVBoxLayout()

        # 标题提示（可选）
        tip_label = QLabel("完整内容：")
        tip_label.setFont(QFont("微软雅黑", 12, QFont.Bold))

        # 内容显示区：QTextEdit支持滚动、换行，只读模式
        self.content_textedit = QTextEdit()
        self.content_textedit.setPlainText(cell_text if cell_text else "该单元格无内容")
        self.content_textedit.setReadOnly(True)  # 禁止编辑，仅查看
        self.content_textedit.setFont(QFont("微软雅黑", 11))
        # 自动换行+滚动条
        self.content_textedit.setLineWrapMode(QTextEdit.WidgetWidth)
        self.content_textedit.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)

        # 按钮区：复制内容 + 关闭
        btn_layout = QHBoxLayout()
        copy_btn = QPushButton("复制内容")
        copy_btn.clicked.connect(self.copy_content)
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.close)

        btn_layout.addStretch()
        btn_layout.addWidget(copy_btn)
        btn_layout.addWidget(close_btn)

        # 组装布局
        layout.addWidget(tip_label)
        layout.addWidget(self.content_textedit, stretch=1)  # 内容区占主要空间
        layout.addLayout(btn_layout)
        self.setLayout(layout)

    def copy_content(self):
        """复制内容到剪贴板"""
        clipboard = QApplication.clipboard()
        clipboard.setText(self.content_textedit.toPlainText())
        # 简单提示（可替换为QMessageBox，更友好）
        self.setWindowTitle("内容已复制到剪贴板！")
