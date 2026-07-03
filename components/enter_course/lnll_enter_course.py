import asyncio
import random
from dataclasses import dataclass, field
from typing import Tuple, Optional, List

from playwright.async_api import Locator, Page
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from src.frame.base import BaseEnterCourseTaskNode
from src.frame.common.exceptions import BusinessException


@dataclass(init=False)
class LNLLEnterCourse(BaseEnterCourseTaskNode):
    excluded_courses: list = field(default_factory=list)
    video_page_window_handler: Page = None
    course_page_window_handler: Page = None
    net_location: str = ""
    current_course_id: int = ""
    target_course_name: str = ""  # 指定的课程名称

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        self.excluded_courses = []
        self.net_location = self.node_config.get("node_params", {}).get("net_location", "")
        self.target_course_name = self.node_config.get("node_params", {}).get("target_course_name", "")
        if not self.net_location:
            self.logger.error("请配置网络地址！")
            return False, "请配置网络地址！"
        self.course_page_window_handler = self.get_latest_window()
        await self.switch_to_latest_window()
        btn_enter_study_center: Locator = await self.get_elem_with_wait_by_xpath(4,
                                                                                 "//div[@class='success_login']//div[@class='btn']")
        if btn_enter_study_center:
            # 进入学习页面
            await btn_enter_study_center.click()
        else:
            self.logger.error("进入学习中心失败")
            return False, "进入学习中心失败"
        is_need_choose_course, remaining_course_hours = await self.is_need_choose_course()
        # 检查是否选课了
        if is_need_choose_course:
            # 未选课，开始选课
            await self.choose_courses(remaining_course_hours)

        return True, ""

    async def enter_course(self) -> Tuple[bool, str]:
        # 获取未完成的课程
        try:
            unfinished_course_id = await self.get_random_choose_uncompleted_course(self.excluded_courses)
        except:
            self.logger.error("获取未完成的课程失败：网络错误！")
            return False, "获取未完成的课程失败：网络错误！"
        else:
            if unfinished_course_id:
                # 当前的课程ID
                self.current_course_id = unfinished_course_id
                # 进入课程详情页面
                status, desc = await self.enter_course_detail_page_and_start_learn(unfinished_course_id)
                if not status:
                    self.logger.error(f"进入课程失败：{desc}")
                    if "没有找到视频地址" == desc:
                        # 排除掉该课程了，重新进入新的课程
                        self.excluded_courses.append(unfinished_course_id)
                        return await self.enter_course()

                self.set_output_data("net_location", self.net_location)
                self.set_output_data("video_page_window_handler", self.video_page_window_handler)
                return True, ""
            else:
                self.logger.info("没有未完成的课程，退出学习！")
                return False, "没有未完成的课程，退出学习！"

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        if not self.get_prev_output().get("restart_course", False):  # 重启课程，则不排除课程
            self.excluded_courses.append(self.current_course_id)
        # 关闭当前页面，刷新课程页面
        await self.close_window(self.video_page_window_handler)
        await self.switch_to_window(self.course_page_window_handler)
        await self.refresh()
        return True, ""

    async def choose_courses(self, remaining_course_hours: float):
        # 获取所有的课程分类
        all_categories = await self._get_all_categories()
        target_course_names = [] if not self.target_course_name.strip() else self.target_course_name.strip().split(",")
        if target_course_names:
            for target_course_name in target_course_names:
                course = await self._search_course_by_name(target_course_name)
                if not course:
                    self.logger.error(f"【{target_course_name}】课程不存在！")
                    await asyncio.sleep(0.5)
                    continue

                if not course['learning_progress']:
                    # 课程未被选中
                    # 选课
                    await asyncio.sleep(random.uniform(0.5, 1))
                    status, msg = await self._choose_course(course['id'])
                    if status:
                        self.logger.info(f"【{target_course_name}】选课成功！")
                    else:
                        self.logger.info(f"【{target_course_name}】选课失败，原因：{msg}！")
                elif course['learning_progress'] == "100":
                    self.logger.info(f"【{target_course_name}】之前已经学完！")
                else:
                    # 已经被选中
                    self.logger.info(f"【{target_course_name}】之前已被选中！")
        else:
            for category in all_categories:
                # 获取所有的专题
                all_subjects = await self._get_all_subjects(category["id"])
                for subject in all_subjects:
                    courses = await self._get_all_courses(subject["id"])
                    # 根据剩余课时进行选课
                    # self.logger.info(f"匹配指定的课程名称：{course_name}")
                    for course in courses:
                        course_name = course['course_name']
                        if not course['learning_progress']:
                            # 未选课
                            hours = float(course['learning_hour'])
                            # 选课
                            await asyncio.sleep(0.5)
                            status, msg = await self._choose_course(course['id'])
                            if status:
                                self.logger.info(f"选课【{course_name}】成功！", )
                                # 修改课时
                                remaining_course_hours -= hours
                                if remaining_course_hours <= 0:
                                    # 选课学时已满足、
                                    self.logger.info("已完成选课！")
                                    return
                            else:
                                self.logger.info(f"选课【{course_name}】失败，原因：{msg}！")

    async def _search_course_by_name(self, course_name: str):
        course = None
        url = f"https://{self.net_location}/trainee/api/search/course"
        params = {"currentPage": 1, "pageSize": 10, "keyword": course_name}
        cookie = await self.cookie_to_str()
        user_agent = r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        request_body = {}
        response = await self.context.request.post(url, headers={"cookie": cookie, "user-agent": user_agent},
                                                   data=request_body,
                                                   params=params)
        if response.status != 200:
            raise BusinessException(f"找不到课程：{course_name}")
        else:
            response_obj = await response.json()
            # 总的已完成的学时

            courses = response_obj['data']['courses']
            if courses:
                # 取第一个课程
                course = courses[0]
        return course

    async def is_need_choose_course(self) -> Tuple[bool, float]:
        total_course_hours = await self.get_all_completed_hours() + await self.get_all_uncompleted_hours()
        # 需要选课
        return total_course_hours < 50.0, 50.0 - total_course_hours

    async def get_all_completed_hours(self) -> float:
        # 获取所有学完的学时
        page_num = 1
        page_size = 10
        url = f"https://{self.net_location}/trainee/api/course/completed"
        params = {"currentPage": page_num, "pageSize": page_size, "year": 2026}
        cookie = await self.cookie_to_str()
        user_agent = r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        request_body = {}
        response = await self.context.request.post(url, headers={"cookie": cookie, "user-agent": user_agent},
                                                   data=request_body,
                                                   params=params)
        if response.status != 200:
            raise BusinessException("获取已完成的课程失败")
        else:
            response_obj = await response.json()
            # 总的已完成的学时
            total_hours = float(response_obj['data'].get('totalHours', 0))
            return total_hours

    @retry(retry=retry_if_exception_type((Exception, BusinessException)), stop=stop_after_attempt(3), wait=wait_fixed(2))
    async def get_all_uncompleted_hours(self) -> float:
        # 获取所有未学完的学时
        page_num = 1
        page_size = 10
        url = f"https://{self.net_location}/trainee/api/course/uncompleted"
        params = {"currentPage": page_num, "pageSize": page_size, "year": 2026}
        cookie = await self.cookie_to_str()
        user_agent = r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        request_body = {}
        response = await self.context.request.post(url, headers={"cookie": cookie, "user-agent": user_agent},
                                                   data=request_body,
                                                   params=params)
        if response.status != 200:
            raise BusinessException("获取未完成的课程失败")
        else:
            response_obj = await response.json()
            # 总的已完成的学时
            total_hours = float(response_obj['data'].get('totalHours', 0))
            return total_hours

    async def _get_all_categories(self) -> list:
        url = f"https://{self.net_location}/trainee/api/subject/list"
        # 返回课程ID，返回为None说明没有未完成的课程
        cookie = await self.cookie_to_str()
        user_agent = r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        response = await self.context.request.get(url, headers={"cookie": cookie, "user-agent": user_agent})
        if response.status != 200:
            raise BusinessException("获取专题信息失败")
        else:
            response_obj = await response.json()
            if response_obj["code"] != 0:
                raise BusinessException(f"获取专题信息失败，原因：{response_obj['message']}")
            else:
                categories = response_obj["data"]["category_group"][0]["category"]
                ret = []
                for category in categories:
                    ret += category["categoryVos"]

                return ret

    async def _get_all_subjects(self, subject_id: int):
        """
        [{
            "id": 568,
            "category_name": "专题一：深入学习习近平新时代中国特色社会主义思想",
            "course_num": 16,
            "icon": "https://kczytest.lngbzx.gov.cn/subject_image/zt120250323.jpg",
            "course_learning_hour": "15.0",
            "subject_date": "2025"
        }]
        :param subject_id:
        :return:
        """
        url = f"https://{self.net_location}/trainee/api/subject/subject_and_course_list//{subject_id}"
        request_body = {"currentPage": 1, "pageSize": 5, "year": ""}
        cookie = await self.cookie_to_str()
        user_agent = r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        response = await self.context.request.post(url, headers={"cookie": cookie, "user-agent": user_agent},
                                                   data=request_body)
        if response.status != 200:
            raise BusinessException("获取专题信息失败")
        else:
            response_obj = await response.json()
            return response_obj["data"]["category"][0]["subjects"]

    async def _get_all_courses(self, subject_id: int, page_num=1, page_size=5):
        """
        [{
            "id": 5816,
            "course_name": "学习习近平总书记在2024年全国两会期间发表的重要讲话精神（上）",
            "course_no": "GYS0025601",
            "cover_image": "https://kczytest.lngbzx.gov.cn/course_image/GYS0025601logo.png",
            "online_date": "2025-03-21",
            "lecturer": "洪向华",
            "lecturer_introduction": "中共中央党校（国家行政学院）科研部副主任、教授、博士生导师",
            "duration": 41,
            "learning_hour": "1.00",
            "completed_count": 22217,
            "rating_score": "4.8",
            "learning_progress": "0.00",
            "is_completed": 0,
            "is_test": 0,
            "play_type": 4,
            "courseware_url": ""
        }]
        learning_progress 为null说明未选择
        :param subject_id:
        :return:
        """
        url = f"https://{self.net_location}/trainee/api/subject/subject_and_course_list//{subject_id}"
        request_body = {"currentPage": page_num, "pageSize": page_size, "year": ""}
        cookie = await self.cookie_to_str()
        user_agent = r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        response = await self.context.request.post(url, headers={"cookie": cookie, "user-agent": user_agent},
                                                   data=request_body)
        if response.status != 200:
            raise BusinessException("获取专题信息失败")
        else:
            response_obj = await response.json()
            courses = response_obj["data"]["courses"]
            total_count = response_obj["data"]["pager"]["rowCount"]
            fetch_count = (total_count - 1) // page_size + 1
            if fetch_count > 1 and fetch_count > page_num:
                page_num += 1
                await asyncio.sleep(0.5)
                courses += await self._get_all_courses(subject_id, page_num, page_size)
            return courses

    async def _choose_course(self, course_id: int):
        url = f"https://{self.net_location}/trainee/api/course/elective/{course_id}"
        # 返回课程ID，返回为None说明没有未完成的课程
        cookie = await self.cookie_to_str()
        response = await self.context.request.get(url, headers={"cookie": cookie})
        if response.status != 200:
            raise BusinessException("选课失败")
        else:
            response_obj = await response.json()
            if response_obj["code"] != 0:
                return False, f"选课失败失败，原因：{response_obj['message']}"
            else:
                # 选课成功
                return True, "选课成功"

    @retry(retry=retry_if_exception_type((BusinessException, Exception)), stop=stop_after_attempt(3),
           wait=wait_fixed(1))
    async def get_random_choose_uncompleted_course(self, excluded_courses: List = None) -> Optional[int]:
        # 返回课程ID，返回为None说明没有未完成的课程
        page_num = 1
        page_size = 10
        url = f"https://{self.net_location}/trainee/api/course/uncompleted"
        params = {"currentPage": page_num, "pageSize": page_size, "year": 2026}
        cookie = await self.cookie_to_str()
        user_agent = r"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        request_body = {}
        response = await self.context.request.post(url, headers={"cookie": cookie, "user-agent": user_agent},
                                                   data=request_body,
                                                   params=params)
        if response.status != 200:
            raise BusinessException("获取未完成的课程失败")
        else:
            response_obj = await response.json()
            if response_obj["code"] != 0:
                raise BusinessException(f"获取未完成的课程失败，原因：{response_obj['message']}")
            else:
                courses = response_obj["data"]["courses"]
                course_ids = [course["id"] for course in courses if
                              not excluded_courses or course["id"] not in excluded_courses]
                return None if len(course_ids) <= 0 else course_ids[random.randint(0, len(course_ids) - 1)]

    async def enter_course_detail_page_and_start_learn(self, course_id: int):
        url = f"https://{self.net_location}/pc/index.html#/course_detail?id={course_id}&typeInfo=1"
        await self.load_url(url)
        max_retry_count = 5
        while max_retry_count > 0:
            btn_start_learn = await self.get_elem_with_wait_by_xpath(10, "//div[@class='select_course']")
            if btn_start_learn:
                try:
                    await btn_start_learn.click()
                    # await self.js_click(btn_start_learn)
                except:
                    self.logger.exception("点击“开始学习”按钮失败")
                    raise BusinessException("点击“开始学习”按钮失败")
                else:
                    # await asyncio.sleep(2)
                    if await self.judge_video_page_load_complete():
                        window_handlers = await self.get_windows_by_url_key("video_detail")
                        self.video_page_window_handler = window_handlers[0]
                        await self.switch_to_window(self.video_page_window_handler)
                        alert_info_elem = await self.get_elem_with_wait_by_xpath(5, "//div[@role='alert']//p")
                        if alert_info_elem and "没有找到视频地址" in await alert_info_elem.text_content():
                            await self.close_other_windows(self.course_page_window_handler)
                            return False, "没有找到视频地址"
                        else:
                            break
                    else:
                        self.logger.info("加载视频页面失败，尝试刷新，重新加载！")
                        max_retry_count -= 1
                        await self.refresh()
                        await asyncio.sleep(random.uniform(1, 3))
        else:
            # 刷新5次后，还未进入视频页面
            self.logger.error("加载视频页面失败，重试5次后退出学习！")
            return False, "加载视频页面失败！"
        return True, "进入课程详情页面成功！"

    async def judge_video_page_load_complete(self) -> bool:
        # 判断视频页面是否加载完成
        # 获取新窗口句柄
        max_count = 15
        while max_count > 0:
            if await self.get_windows_by_url_key("video_detail"):
                return True
            await asyncio.sleep(0.2)
            max_count -= 1
        return False
