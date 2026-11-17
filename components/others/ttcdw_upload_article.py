import asyncio
import os
import shutil
from dataclasses import dataclass
from typing import Tuple, Dict

from playwright.async_api import Page

from src.frame.base.base_task_node import BasePYNode
from src.utils import UploadLocalFile


@dataclass(init=False)
class TTCDWUploadArticle(BasePYNode):
    """
    学习公社（ttcdw）上传作业

    需配置
    file_dir-文件目录
    recycle_dir-删除目录
    两个参数
    """
    # 上传本地文件的操作句柄
    upload_file_handler: UploadLocalFile = None

    course_page: Page = None

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        target_dir = self.node_config.get("node_params", {}).get("file_dir")
        if not target_dir:
            self.logger.error("未配置file_dir参数")
            return False, "未配置file_dir参数"
        if not os.path.exists(target_dir):
            self.logger.error("file_dir指定的目录不存在！")
            return False, "file_dir指定的目录不存在！"
        recycle_dir = self.node_config.get("node_params", {}).get("recycle_dir")
        if not recycle_dir:
            self.logger.error("未配置recycle_dir参数")
            return False, "未配置recycle_dir参数"
        if not os.path.exists(recycle_dir):
            self.logger.error("recycle_dir指定的目录不存在！")
            return False, "recycle_dir指定的目录不存在！"
        # 点击项目
        tab_projects = await self.get_elem_with_wait_by_xpath(10,
                                                              "//div[contains(@class, 'sec-menu') and contains(text(), '项目')]")
        if tab_projects:
            await tab_projects.click()
        else:
            return False, "未找到项目标签"

        btn_learn = await self.get_elem_with_wait_by_xpath(10,
                                                           "//div[@class='list']/div[contains(@class, 'item')]//a[@class='item_btn']")
        if not btn_learn:
            return False, "未找到学习按钮"
        await btn_learn.click()
        await asyncio.sleep(2)
        # 打开新窗口
        await self.switch_to_window_by_url_key("uc/myClassroom")

        # 点击资源分享
        btn_share = await self.get_elem_with_wait_by_xpath(10,
                                                           "//div[contains(@class, 'item-one')][.//span[@class='item-title' and contains(.//text(), '资源分享')]]")
        if not btn_share:
            self.logger.error("获取资源分享按钮失败！")
            return False, "获取资源分享按钮失败！"

        await self.js_click(btn_share)

        # 需要上传的资源数量
        el_recourse_counts = await self.get_elems_with_wait_by_xpath(10, "//div[@class='col-1']//span")
        total_count, finished_count = await el_recourse_counts[0].text_content(), await el_recourse_counts[
            1].text_content()
        upload_count = int(total_count) - int(finished_count)
        if upload_count > 0:
            # 上传资源
            btn_upload = await self.get_elem_with_wait_by_xpath(10, "//a[@class='btn add-resource']")
            if not btn_upload:
                self.logger.error("没找到上传资源按钮！")
                return False, "没有找到上传资源按钮！"
            await self.js_click(btn_upload)

            btn_upload_attr = await self.get_elem_with_wait_by_xpath(10, "//button[@class='add-files']")
            if not btn_upload_attr:
                self.logger.error("没有找到上传附件按钮！")
                return False, "没有找到上传附件按钮！"
            await self.js_click(btn_upload_attr)
            await asyncio.sleep(2)
            fail_count = 0
            succ_count = 0
            for _ in range(upload_count):
                # 选择目标文件
                file_path = await self.choose_target_file(target_dir)
                if not file_path:
                    self.logger.error("未找到文件！")
                    return False, "未找到文件！"
                # 等待弹出文件窗口
                self.upload_file_handler.select_file(file_path)
                # 等待上传成功
                el_upload_succ_tips = await self.get_elem_with_wait_by_xpath(10, "//p[@class='el-message__content']")
                if el_upload_succ_tips and "上传成功" in await el_upload_succ_tips.text_content():
                    await asyncio.sleep(1)
                    btn_confirm = await self.get_elem_with_wait_by_xpath(10,
                                                                         "//div[@role='dialog' and contains(.//text(), '上传资料')]//button[@class='btn']")
                    if not btn_confirm:
                        self.logger.error("未找到确定上传按钮！")
                        return False, "未找到确定上传按钮！"
                    await self.js_click(btn_confirm)
                    succ_count += 1
                    self.logger.info(f"成功上传{succ_count}个文件！")
                    shutil.move(file_path, os.path.join(recycle_dir, os.path.basename(file_path)))
                else:
                    self.logger.error("上传失败！")
                    # 关闭上传页面
                    btn_close = await self.get_elem_with_wait_by_xpath(10, "//div[@role='dialog' and contains(.//text(), '上传资料')]//i[contains(@class, 'icon-guanbi')]")
                    await self.js_click(btn_close)
                    fail_count += 1

            desc = f"需要上传{upload_count}个，成功{succ_count}个"
            self.logger.info(desc)
            self.user_manager.update_record_by_username(self.username, {4: desc})

        return True, ""

    def set_up(self):
        super().set_up()
        self.upload_file_handler = UploadLocalFile()

    async def execute(self, context: Dict) -> bool:
        status, desc = await self.prepare_before_first_enter_course()
        return status

    async def choose_target_file(self, target_dir):
        target_file = None
        for f in os.listdir(target_dir):
            full_path = os.path.join(target_dir, f)
            if os.path.isfile(full_path):
                target_file = full_path
                break
        return target_file
