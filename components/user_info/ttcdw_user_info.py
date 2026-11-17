import asyncio
import re
from dataclasses import dataclass
from typing import Dict, Tuple

from playwright.async_api import Page
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.frame.base.base_task_node import BasePYNode


@dataclass(init=False)
class TTCDWUserInfo(BasePYNode):
    course_page: Page = None

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
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

        self.course_page = self.get_current_page()
        return True, ""

    async def execute(self, context: Dict) -> bool:
        status, msg = await self.prepare_before_first_enter_course()
        if not status:
            self.logger.error(f"获取用户信息失败：{msg}")
            return False
        cur_url = await self.get_current_url()
        if "editPerfectInfo" in cur_url:
            # https://www.ttcdw.cn/p/uc/myClassroom/1135700489687203840/editPerfectInfo/1135730896421232640?orgId=171864496496529408
            real_name, work_unit, subject_name = await self.get_user_info_in_edit_page()
            self.user_manager.update_record_by_username(self.username, {2: real_name, 3: work_unit, 4: subject_name})

            self.logger.error("地址和身份未填写，开始自动填写")
            xpath = "//div[@class='content-title']//span"
            el_title = await self.get_elem_with_wait_by_xpath(10, xpath)
            if not el_title:
                await self.refresh()
                el_title = await self.get_elem_with_wait_by_xpath(10, xpath)
                if not el_title:
                    self.logger.error("未找到完善信息标题")
                    return False

            if "请准确提交您的信息资料" in await el_title.text_content():  # 需要完善个人信息
                self.logger.info("需要完善信息，开始完善信息...")
                status, desc = await self.complete_information()
                if not status:
                    self.logger.error(f"完善信息失败：{desc}")
                    return False
                else:
                    self.logger.info("完善信息成功！")
            return True
        elif "center" in cur_url:
            room_id, class_id, org_id = self.get_three_num_str(await self.get_current_url())
            subject_name = await self.get_subject_name(room_id, class_id)
            real_name, work_unit = await self.get_user_info(room_id)
            self.user_manager.update_record_by_username(self.username, {2: real_name, 3: work_unit, 4: subject_name})
            return True
        else:
            self.logger.error(f"未知页面：{cur_url}")
            self.user_manager.update_record_by_username(self.username, {2: "可能未填写手机号码！"})
            return False

    async def wait_text(self, locator_xpath: str, timeout=5):
        error_loc = await self.get_elem_with_wait_by_xpath(10, locator_xpath)
        if not error_loc:
            await self.refresh()
            error_loc = await self.get_elem_with_wait_by_xpath(10, locator_xpath)

        # 每个0.5秒检测一次元素的textContent，当时间超过timeout，则返回""
        while True:
            if (await error_loc.text_content()).strip():
                return (await error_loc.text_content()).strip()
            await asyncio.sleep(0.5)
            timeout -= 0.5
            if timeout <= 0:
                return ""

    def get_three_num_str(self, url: str) -> tuple[str, str, str]:
        """
        从指定链接提取三段数字字符串
        :param url: 目标链接
        :return: (第一段数字, 第二段数字, 第三段数字)
        """
        # 正则匹配三段数字
        pattern = r"/myClassroom/(\d+)/center/(\d+)\?orgId=(\d+)"
        match_res = re.search(pattern, url)
        if not match_res:
            raise ValueError("链接格式不匹配，无法提取数字")
        num1, num2, num3 = match_res.groups()
        return num1, num2, num3

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def get_subject_name(self, room_id, class_id):
        url = f"https://www.ttcdw.cn/p/uc/services/member/project/classes/detail/v2/{room_id}?classId={class_id}"
        headers = {
            "user-agent": await self.user_agent(),
            "cookie": await self.cookie_to_str()}

        try:
            resp = await self.context.request.get(url, headers=headers)
        except:
            self.logger.error(f"获取班级信息异常")
            raise
        else:
            json_obj = await resp.json()
            return json_obj["data"].get("projectClass").get("name")

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def get_user_info(self, room_id):
        url = f"https://www.ttcdw.cn/p/uc/services/member/project/study_f/mem_info/{room_id}"
        headers = {
            "user-agent": await self.user_agent(),
            "cookie": await self.cookie_to_str()}

        try:
            resp = await self.context.request.get(url, headers=headers)
        except:
            self.logger.error(f"获取班级信息异常")
            raise
        else:
            json_obj = await resp.json()
            user_info = json_obj["data"].get("orgStudent")
            return user_info.get("name"), user_info.get("workUnit")

    async def get_user_info_in_edit_page(self):
        # 获取姓名和工作单位
        username = ""
        work_unit = ""
        class_name = ""
        # //input[@placeholder='请输入姓名'] | //input[@placeholder='请输入工作单位']
        el_username = await self.get_elem_with_wait_by_xpath(10, "//input[@placeholder='请输入姓名']")
        if el_username:
            username = await el_username.input_value()
        el_work_unit = await self.get_elem_with_wait_by_xpath(10, "//input[@placeholder='请输入工作单位']")
        if el_work_unit:
            work_unit = await el_work_unit.input_value()

        el_class_name = await self.get_elem_with_wait_by_xpath(10, "//div[@class='class-name']")
        if el_class_name:
            class_name = await el_class_name.text_content()

        return username, work_unit, class_name

    async def complete_information(self) -> Tuple[bool, str]:
        xpath = "//div[@class='el-cascader']"
        el_location = await self.get_elem_with_wait_by_xpath(3, xpath)
        await el_location.click()

        xpath = "//li[@role='menuitem'][./span[text()='福建省']]"
        el_province = await self.get_elem_with_wait_by_xpath(3, xpath)
        if not el_province:
            return False, "未弹出省份选择框"
        await self.js_click(el_province)

        xpath = "//li[@role='menuitem'][./span[text()='莆田市']]"
        el_city = await self.get_elem_with_wait_by_xpath(3, xpath)
        if not el_city:
            return False, "未弹出市选择框"
        await self.js_click(el_city)

        xpath = "//li[@role='menuitem'][./span[text()='城厢区']]"
        el_area = await self.get_elem_with_wait_by_xpath(3, xpath)
        if not el_area:
            return False, "未弹出区县选择框"
        await self.js_click(el_area)

        # 填写详细地址
        input_address = await self.get_elem_with_wait_by_xpath(5,
                                                               "(//div[@class='el-input']//input[@class='el-input__inner'])[2]")
        if not input_address:
            return False, "未找到地址输入框"
        await input_address.fill("文献西路")

        # 填写学员身份
        el_identity = await self.get_elem_with_wait_by_xpath(5, "(//input[@class='el-input__inner'])[5]")
        if not el_identity:
            return False, "未找到学员身份输入框"
        await el_identity.click()

        xpath = "//li[@class='el-select-dropdown__item' and ./span[text()='中小学教师']]"
        opt_identity = await self.get_elem_with_wait_by_xpath(3, xpath)
        if not opt_identity:
            return False, "未弹出学员身份选择框"
        await self.js_click(opt_identity)

        # 点击保存按钮
        btn_save = await self.get_elem_with_wait_by_xpath(5, "//button[@class='btn']")
        if not btn_save:
            return False, "未找到保存按钮"
        await self.js_click(btn_save)

        return True, ""
