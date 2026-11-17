import asyncio
import re
from dataclasses import dataclass
from typing import Tuple

from playwright.async_api import Page

from src.frame.base import BaseEnterCourseTaskNode


@dataclass(init=False)
class TTCDWEnterCourse(BaseEnterCourseTaskNode):
    """
    学习公社进入课程
    """

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

        # 完善个人信息
        if "editPerfectInfo" in await self.get_current_url():
            xpath = "//div[@class='content-title']//span"
            el_title = await self.get_elem_with_wait_by_xpath(10, xpath)
            if not el_title:
                await self.refresh()
                el_title = await self.get_elem_with_wait_by_xpath(10, xpath)
                if not el_title:
                    return False, "未找到完善信息标题"

            if "请准确提交您的信息资料" in await el_title.text_content():  # 需要完善个人信息
                self.logger.info("需要完善信息，开始完善信息...")
                status, desc = await self.complete_information()
                if not status:
                    self.logger.error(f"完善信息失败：{desc}")
                    return False, desc
                else:
                    self.logger.info("完善信息成功！")

        t1 = await self.wait_text("(//div[@class='assess-tips']//div[@class='col-1']/span)[1]")
        t2 = await self.wait_text("(//div[@class='assess-tips']//div[@class='col-1']/span)[2]")
        if int(t1) > int(t2):
            # 点击添加选课按钮
            btn_add_course = await self.get_elem_with_wait_by_xpath(5, "//a[@class='btn add-course']")
            if btn_add_course:
                self.logger.info("开始选课...")
                await self.js_click(btn_add_course)
                status, desc = await self.choose_course()
                if not status:
                    self.logger.error(f"选课失败：{desc}")
                    return False, desc
                else:
                    self.logger.info("选课成功！")
        self.course_page = self.get_current_page()
        return True, ""

    async def enter_course(self) -> Tuple[bool, str]:
        first_unfinished_course = await self.get_first_unfinished_course()
        if not first_unfinished_course:
            return False, "已完成！"

        el_class_name = await self.get_relative_elem_by_xpath(first_unfinished_course, ".//span[@class='course-name']")
        course_name = await el_class_name.text_content()
        btn_enter_course = await self.get_relative_elem_by_xpath(first_unfinished_course, ".//a[text()='学习']")
        await self.js_click(btn_enter_course)
        await asyncio.sleep(2)
        await self.switch_to_window_by_url_key("course/videorevision")
        self.set_output_data("video_page", self.get_current_page())
        self.set_output_data("course_page", self.course_page)
        return True, course_name

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        # await self.switch_to_window(self.course_page)
        await self.close_other_windows(self.course_page)
        await self.refresh()
        return True, ""

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

    async def choose_course(self) -> Tuple[bool, str]:
        # 切换视图，改成列表视图
        # tab_list = await self.get_elem_with_wait_by_xpath(5, "//a[contains(text(), '列表')]")
        # if not tab_list:
        #     return False, "未找到列表视图"
        # await self.js_click(tab_list)
        # await asyncio.sleep(2)
        btn_choose_courses = await self.get_elems_with_wait_by_xpath(5, "//a[text()='选择']")
        if not btn_choose_courses:
            return False, "未找到选择按钮"

        is_satisfied = False
        while not is_satisfied:
            while btn_choose_courses := await self.get_elem_by_xpath("(//a[text()='选择'])[1]"):
                await self.js_click(btn_choose_courses)
                await asyncio.sleep(1)
                # await self.js_click(btn_choose_course)
                # await asyncio.sleep(1)
                # 获取已选的课程时长
                el_course_time = await self.get_elem_by_xpath("//div[@class='addElective-hasChoose-tips']")
                pattern = r"考核要求时长(\d+)分钟，\s*选课时长(\d+)分钟"
                match = re.search(pattern, await el_course_time.text_content())
                if match:
                    num1 = match.group(1)
                    num2 = match.group(2)
                    if int(num1) <= int(num2):
                        is_satisfied = True
                        break

            if not is_satisfied:
                # 点击下一页
                await self.js_click(await self.get_elem_with_wait_by_xpath(5, "//button[@class='btn-next']"))
                await asyncio.sleep(1)

        # 点击确定按钮
        btn_confirm = await self.get_elem_with_wait_by_xpath(5, "//a[text()='确定']")
        if not btn_confirm:
            return False, "未找到确定按钮"

        await self.js_click(btn_confirm)
        # 点击提示框中的确定按钮
        btn_confirm = await self.get_elem_with_wait_by_xpath(5, "(//button[@class='btn'])[last()]", visible=True)
        if btn_confirm:
            await self.js_click(btn_confirm)

        return True, ""

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

        # try:
        #     js_str = """
        #         () => {
        #             function getSingleElement(xpath) {
        #                 const result = document.evaluate(
        #                     xpath,
        #                     document,
        #                     null,
        #                     XPathResult.FIRST_ORDERED_NODE_TYPE,
        #                     null
        #                 );
        #                 return result.singleNodeValue; // 返回DOM节点或null
        #             }
        #             const el = getSingleElement("%s");
        #             return el.textContent.trim().length > 0;
        #         }
        #     """ % locator_xpath
        #     await self.get_current_page().wait_for_function(js_str, timeout=timeout*1000)
        #     return (await error_loc.text_content()).strip()
        # except:
        #     return ""

    async def get_first_unfinished_course(self):
        target_course = None
        while not target_course:
            xpath = "//tr[@class='el-table__row'][.//div[@role='progressbar' and @aria-valuenow !=100]]"
            target_course = await self.get_elem_with_wait_by_xpath(5, xpath)
            if target_course:
                break
            else:
                # 翻页
                # 获取下一页的按钮
                btn_next_page = await self.get_elem_with_wait_by_xpath(5,
                                                                       "//button[@class='btn-next' and not(@disabled)]")
                if not btn_next_page:
                    break
                else:
                    await self.js_click(btn_next_page)
                    await asyncio.sleep(1)

        return target_course
