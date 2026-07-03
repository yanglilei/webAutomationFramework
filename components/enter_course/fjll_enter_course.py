import asyncio
from dataclasses import dataclass, field
from typing import Tuple

from playwright.async_api import Page
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.frame.base import BaseEnterCourseTaskNode
from decimal import Decimal


@dataclass(init=False)
class FJLLEnterCourse(BaseEnterCourseTaskNode):
    user_id: str = ""
    class_name: str = ""
    class_id: str = ""
    course_page: Page = None
    headers: dict = field(default_factory=dict)

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        self.class_name = self.node_config.get("node_params", {}).get("class_name")
        self.user_id = self.get_prev_output().get("user_id")
        self.headers = self.get_prev_output().get("headers", {})
        self.headers["content-type"] = "application/json"
        self.headers["cookie"] = await self.cookie_to_str()
        self.headers[
            "user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        return True, ""
        # btn_enter_required_course = await self.get_elem_with_wait_by_xpath(10,
        #                                                                    "//li[@role='menuitem'][.//text()='年度必修']")
        # if not btn_enter_required_course:
        #     return False, "没有找到年度必修"
        # await btn_enter_required_course.click()

    async def enter_course(self) -> Tuple[bool, str]:
        if self.class_name:
            self.class_id = await self._choose_target_class(self.class_name)
            if self.class_id:
                return await self._enter_class()

        # 没有找到指定班级或者没有配置班级名称，则去学习年度必修
        status, desc = await self._enter_required_course()
        if not status:
            # 进入必修课失败，进入选修课
            status, desc = await self._enter_elective_course()
        return status, desc

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        await self.close_window(self.course_page)
        return True, ""

    async def enter_course_from_training_classes(self, class_name: str):
        if not class_name:
            return False, "请配置培训班次名称"
        class_tab = await self.get_elem_with_wait_by_xpath(10, "//li[@role='menuitem'][./span[text()='培训班次']]")
        await class_tab.click()

        # 搜索班级
        class_name_search_input = await self.get_elem_with_wait_by_xpath(10,
                                                                         "//div[contains(.//text(), '班次名称')]//input[@class='el-input__inner']")
        await class_name_search_input.fill(class_name)
        btn_search = await self.get_elem_with_wait_by_xpath(10, "//div[contains(.//text(), '班次名称')]//button")
        await btn_search.click()
        class_items = await self.get_elems_with_wait_by_xpath(10, "//div[@class='right']//div[@class='right-item']")
        if not class_items:
            return False, "没有找到培训班次，请检查班次名称是否正确"
        # 进入第一个课程，打开新的窗口
        await class_items[0].click()
        await asyncio.sleep(2)
        await self.switch_to_latest_window()

        # 点击进入必修课程
        tab_required_course = await self.get_elem_with_wait_by_xpath(10, "//li[contains(.//text(), '必修课程')]")
        if not tab_required_course:
            return False, "没有找到必修课程"
        await tab_required_course.click()

        return True, ""

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _get_all_my_classes(self):
        url = "https://www.fsa.gov.cn/api/study/shift/shiftInfo/myShift"
        # 请求内容：{"id":"119320","shiftGroup":"","current":1,"size":10,"year":""}
        body = {
            "id": self.user_id,
            "shiftGroup": "",
            "current": 1,
            "size": 20,
            "year": ""
        }

        response = await self.context.request.post(url, data=body, headers=self.headers)
        resp_obj = await response.json()
        if resp_obj.get("code") == 0:
            return resp_obj.get("data", {}).get("records", [])
        else:
            self.logger.error(f"获取必修课程失败：{resp_obj.get('msg')}")
            return []

    async def _choose_target_class(self, class_name: str):
        course_id = ""
        all_my_classes = await self._get_all_my_classes()
        if all_my_classes:
            for item in all_my_classes:
                if item.get("name") == class_name:
                    course_id = item.get("id")
                    break
        return course_id

    async def _make_class_url(self, class_name: str):
        url = "https://www.fsa.gov.cn/page1?shiftId=%s&completionStatus=1"
        self.class_id = await self._choose_target_class(class_name)
        if self.class_id:
            return url % self.class_id
        return ""

    async def _enter_class(self):
        # course_url = await self._make_class_url(class_name)
        # if not course_url:
        #     return False, "没有找到该班级"
        unfinished_courses = await self._get_all_unfinished_course()
        if not unfinished_courses:
            self.logger.info("没有未完成的课程")
            return False, "已完成"
            # self.terminate("已完成")
        courses_ = unfinished_courses[0]
        course_url = "https://www.fsa.gov.cn/video?id=%s&shiftId=%s" % (
            courses_["courseware_id"], courses_["shift_id"])
        await self.open_in_new_window(course_url)
        await asyncio.sleep(2)
        windows = await self.get_windows_by_url_key("/video")
        self.course_page = windows[0]
        await self.switch_to_window(self.course_page)
        self.set_output_data("course_page", self.course_page)
        return True, courses_["name"]

    async def _enter_required_course(self):
        required_unfinished_course = await self._get_all_required_unfinished_courses()
        if not required_unfinished_course:
            self.logger.info("没有需要学习的必修课程")
            return False, "已完成"

        url = "https://www.fsa.gov.cn/video?id=%s&platformcoursewaretypeId=%s&compulsoryElective=1"
        courseware = required_unfinished_course[0]["courseware"]
        await self.open_in_new_window(url % (courseware["id"], courseware["platformcoursewaretypeId"]))
        await asyncio.sleep(2)
        windows = await self.get_windows_by_url_key("/video")
        self.course_page = windows[0]
        await self.switch_to_window(self.course_page)
        self.set_output_data("course_page", self.course_page)
        return True, required_unfinished_course[0]["name"]

    async def _enter_elective_course(self):
        elective_unfinished_course = await self._get_all_elective_unfinished_courses()
        if not elective_unfinished_course:
            self.logger.info("没有需要学习的选修课程")
            return False, "已完成"

        url = "https://www.fsa.gov.cn/video?id=%s&compulsoryElective=1&platformcoursewaretypeId=%s"
        courseware = elective_unfinished_course[0]["courseware"]
        await self.open_in_new_window(url % (courseware["id"], courseware["platformcoursewaretype"]["id"]))
        await asyncio.sleep(2)
        windows = await self.get_windows_by_url_key("/video")
        self.course_page = windows[0]
        await self.switch_to_window(self.course_page)
        self.set_output_data("course_page", self.course_page)
        return True, elective_unfinished_course[0]["name"]

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _get_courses(self, course_type=0, page_num=1, page_size=10):
        url = "https://www.fsa.gov.cn/api/study/compulsory/compulsoryCourses/findByShiftCourses"
        # 请求内容：{"shiftId":"2036709582808174594","studentId":"2038794129318236161","type":0,"size":10,"current":1}
        body = {
            "shiftId": self.class_id,
            "studentId": self.user_id,
            "type": course_type,  # 0-必修课；1-选修课
            "current": page_num,
            "size": page_size,
        }
        response = await self.context.request.post(url, data=body, headers=self.headers)
        resp_obj = await response.json()


        return resp_obj.get("records", []), resp_obj.get("pages", 0)

    async def _get_all_unfinished_course(self):
        all_courses = []
        # 获取必修课的课程
        courses, pages = await self._get_courses(0)
        all_courses.extend(courses)
        if pages > 1:
            for i in range(2, pages + 1):
                all_courses.extend((await self._get_courses(0, page_num=i))[0])

        # 获取选修课的课程
        courses, pages = await self._get_courses(1)
        all_courses.extend(courses)
        if pages > 1:
            for i in range(2, pages + 1):
                all_courses.extend((await self._get_courses(1, page_num=i))[0])

        unfinished_courses = []
        for course in all_courses:
            if course.get("learnedProgress") != "100.00":
                unfinished_courses.append(course)
        return unfinished_courses

    async def _assemble_headers(self):
        headers = self.get_prev_output().get("headers")
        headers["content-type"] = "application/json"
        headers["cookie"] = await self.cookie_to_str()
        headers[
            "user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
        return headers

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _get_required_courses(self, page_num=1, page_size=12):
        url = "https://www.fsa.gov.cn/api/study/years/yearsCourseware/annualPortalCourseList"
        # 请求参数：{"studentId":"2038794129318236161","size":12,"current":1}
        request_data = {
            "current": page_num,
            "size": page_size,
            "studentId": self.user_id
        }

        response = await self.context.request.post(url, data=request_data, headers=self.headers)
        resp_obj = await response.json()
        if resp_obj.get("code") == 0:
            data = resp_obj.get("data", {})
            return data.get("records", []), data.get("pages")
        else:
            self.logger.error(f"获取必修课程失败：{resp_obj.get('msg')}")
            return [], 0

    @retry(retry=retry_if_exception_type(Exception), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def _get_elective_courses(self, page_num=1, page_size=10):
        url = "https://www.fsa.gov.cn/api/study/my/elective/myElectives"
        # 请求参数：{"studentId":"2038794129318236161","size":12,"current":1}
        request_data = {
            "current": page_num,
            "size": page_size,
            "studentId": self.user_id
        }

        response = await self.context.request.post(url, data=request_data, headers=self.headers)
        resp_obj = await response.json()
        if resp_obj.get("code") == 0:
            data = resp_obj.get("data", {})
            return data.get("records", []), data.get("pages")
        else:
            self.logger.error(f"获取选修课程失败：{resp_obj.get('msg')}")
            return [], 0

    async def _get_all_required_unfinished_courses(self):
        courses, pages = await self._get_required_courses()
        if pages > 1:
            for i in range(2, pages + 1):
                courses.extend((await self._get_required_courses(i))[0])

        unfinished_courses = []
        for course in courses:
            if course.get("speedOfProgress", "") != "100.0":
                unfinished_courses.append(course)
        return unfinished_courses

    async def _get_all_elective_unfinished_courses(self):
        courses, pages = await self._get_elective_courses()
        if pages > 1:
            for i in range(2, pages + 1):
                courses.extend((await self._get_elective_courses(i))[0])

        unfinished_courses = []
        for course in courses:
            if Decimal(course.get("schedule", "0")) != Decimal(100):
                unfinished_courses.append(course)
        return unfinished_courses

    async def _get_all_required_courses(self):
        pass
