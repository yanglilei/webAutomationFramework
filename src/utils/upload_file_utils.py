from typing import List

from tenacity import retry, retry_if_result, wait_fixed, stop_after_attempt, RetryError
import sys
import logging

sys.coinit_flags = 2

class UploadLocalFile:
    """
    对于Qt应用，在UI页面必须添加以下代码，不至于运行时UI冲突，卡死
    import sys
    sys.coinit_flags = 2
    """
    def __init__(self):
        # 桌面对象，目的：获取文件选择器对话框
        from pywinauto import Desktop
        self.desktop = Desktop()

    def select_file(self, image_path: str):
        file_selector_dialog = self.get_open_file_dialog()
        file_selector_dialog.child_window(class_name='Edit').set_text(image_path)
        file_selector_dialog.child_window(title="打开(&O)").click()

    def select_files(self, image_paths: List[str]):
        file_selector_dialog = self.get_open_file_dialog()
        file_selector_dialog.child_window(class_name='Edit').set_text(";".join(image_paths))
        file_selector_dialog.child_window(title="打开(&O)").click()

    # def _wait_for_file_upload_succ(self, wait_time: int):
    #     alert = self.get_alert(5)
    #     alert.accept()

    def get_open_file_dialog(self):
        dialog = None
        try:
            _, dialog = self._get_open_file_dialog()
        except RetryError:
            logging.error("获取打开文件对话框失败，等待人工介入处理...")
            try:
                _, dialog = self._wait_for_manual_click_upload_file_btn()
            except RetryError:
                logging.error("等待许久未收到人工处理的信号")
        return dialog

    @retry(stop=stop_after_attempt(10), wait=wait_fixed(1), retry=retry_if_result(lambda value: value[0] is False))
    def _get_open_file_dialog(self, title="打开"):
        dialog = self.desktop.window(title=title)
        return dialog.exists(), dialog

    @retry(stop=stop_after_attempt(3600), wait=wait_fixed(1))
    def _wait_for_manual_click_upload_file_btn(self):
        dialog = self.desktop.window(title="打开")
        if not dialog.exists():
            logging.warning("等待手动打开上传文件对话框...")
            raise Exception()
        else:
            return dialog.exists(), dialog

