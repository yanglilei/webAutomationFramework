import sys
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QLabel, QPushButton
)

if __name__ == "__main__":
    app = QApplication(sys.argv)

    # ========== 场景1：纯空QWidget（无布局、无内容） ==========
    empty_widget = QWidget()
    empty_widget.setWindowTitle("纯空QWidget")
    empty_widget.show()
    # 获取初始尺寸（宽度×高度）
    empty_size = empty_widget.size()
    print(f"场景1 - 纯空QWidget默认尺寸：宽={empty_size.width()}px，高={empty_size.height()}px")

    # ========== 场景2：有子控件但无布局 ==========
    widget_with_child = QWidget()
    widget_with_child.setWindowTitle("有子控件但无布局")
    # 添加一个高50px的按钮（手动摆放在(10,10)位置）
    btn = QPushButton("测试按钮", widget_with_child)
    btn.setGeometry(10, 10, 100, 50)
    widget_with_child.show()
    child_size = widget_with_child.size()
    print(f"场景2 - 有子控件无布局的QWidget尺寸：宽={child_size.width()}px，高={child_size.height()}px")

    # ========== 场景3：有布局和子控件（实际开发常用） ==========
    widget_with_layout = QWidget()
    widget_with_layout.setWindowTitle("有布局和子控件")
    layout = QVBoxLayout(widget_with_layout)
    # 添加两个子控件：标签（默认高≈20px）+ 按钮（高50px）
    layout.addWidget(QLabel("测试标签"))
    layout.addWidget(QPushButton("测试按钮（高50px）"))
    # 布局默认边距11px（上下各11），间距11px
    widget_with_layout.show()
    layout_size = widget_with_layout.size()
    print(f"场景3 - 有布局和子控件的QWidget尺寸：宽={layout_size.width()}px，高={layout_size.height()}px")

    sys.exit(app.exec_())