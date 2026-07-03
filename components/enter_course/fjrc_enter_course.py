import asyncio
from dataclasses import dataclass, field
from typing import Tuple, List

from playwright.async_api import Page

from src.frame.base import BaseEnterCourseTaskNode
from src.frame.common.exceptions import BusinessException


@dataclass(init=False)
class FJRCEnterCourse(BaseEnterCourseTaskNode):
    user_center_page_url = "https://fj.rcpxpt.com/usersCenter"
    # 测验答案的key，%s为测验ID
    FJRC_EXERCISE_ANSWER_TMPL = "fjrc_answer_%s"
    # 课程包中选修课的课程名称，多个课程用英文逗号分割，%s为课程包ID
    FJRC_ELECTIVE_COURSES_TMPL = "fjrc_%s_elective_courses"
    # 课程中包含测验标志的key，%s为课程的commodityId。值=1标识，课程中包含测验
    FJRC_COURSE_CONTAINS_EXERCISE_FLAG_TMPL = "fjrc_course_%s_contains_exercise_flag"
    # 海峡证书保存目录
    FJRC_CERT_SAVE_DIR = "fjrc_cert_save_dir"
    # 海峡课程详情页面的URL模板，%s为课程ID，%s为课程包ID
    FJRC_COURSE_DETAIL_PAGE_URL_TMPL = "https://fj.rcpxpt.com/sysConfigItem/selectDetail/%s?pId=%s"
    # 海峡视频的URL模板，%s为课程ID，%s为课程包ID，%s为视频ID
    FJRC_VIDEO_PAGE_URL_TMPL = "https://fj.rcpxpt.com/classModule/video/%s/%s/%s/0/0?videoIsBuy=0&pId=%s"

    course_package_ids: List[str] = field(default_factory=list)

    window_handle: Page = None

    async def prepare_before_first_enter_course(self) -> Tuple[bool, str]:
        await self.switch_to_latest_window()
        await self.handle_area_tips()
        await self.handle_qrcode_alert()
        self.course_package_ids = await self._get_course_package_id()
        # self.course_package_ids = ["27337"]
        if len(self.course_package_ids) == 0:
            # 没有课程包退出
            self.logger.info("学习退出！")
            return False, "没有课程包退出！"
        return True, ""

    async def enter_course(self) -> Tuple[bool, str]:
        content_info = await self._get_next_content(self.course_package_ids)
        # content_info = {"type": "exercise", "url": "https://fj.rcpxpt.com/sysConfigItem/selectDetail/1327924?pId=27170"}
        if content_info:
            if content_info["type"] == "video":
                await self._learn_new_content(content_info["url"])
                # 设置course_type为video
                self.set_output_data("course_type", "video")
                return True, content_info["content_name"]
            else:
                # TODO 作测验未完成！！！TODO pause by zcy 20260616
                # 当前任务结束，添加测验任务！等待测验完成之后，再学习最后一个章节
                self.logger.info("准备做测验")
                # 设置course_type为exam
                self.set_output_data("course_type", "exam")
                # 添加做测验的任务
                # FJRCExerciseTaskMonitor.instance().add_task(
                #     FJRCExerciseTask(self.web_browser, self.username, self.user_info_operator, content_info["url"]))
                # 结束任务
                # FJRCLearningTaskMonitor.instance().remove_task(self)
                return True, "做测验"
        else:
            # 退出学习
            self.logger.info("都学习完了！")
            return False, "都学习完了！"

    async def handle_after_course_finished(self) -> Tuple[bool, str]:
        user_center_page_url = "https://fj.rcpxpt.com/usersCenter"
        await self.open_in_new_window(user_center_page_url)
        await self.close_other_windows(self.get_current_page())
        return True, ""

    async def _learn_new_content(self, content_url):
        # 不是最后一个课程，新窗口打开该页面
        await self.open_in_new_window(content_url)
        await asyncio.sleep(2)
        self.window_handle = self.get_current_page()
        # 关闭旧窗口
        await self.close_other_windows(self.window_handle)
        # TODO 触发播放视频
        # self._trigger_play_video(self.window_handle)

    async def handle_area_tips(self):
        completed_user_info_alert = await self.get_elem_with_wait_by_xpath(3, "//div[@id='userinfoPopViewCommon']")
        if completed_user_info_alert:
            # 选择省份
            province_selector = await self.get_elem_by_xpath("//select[@id='provinceSelectCommon']")
            if province_selector:
                try:
                    await province_selector.click()
                except:
                    self.logger.error("选择省份失败")
                    raise BusinessException("选择省份失败")
                else:
                    await (await self.get_elem_with_wait_by_xpath(2, "//option[@value='350000']")).click()
                    # 选择城市
                    city_selector = await self.get_elem_by_xpath("//select[@id='citySelectCommon']")
                    if city_selector:
                        await city_selector.click()
                        await (await self.get_elem_with_wait_by_xpath(2, "//option[@value='350300']")).click()
                        # 选择地区
                        area_selector = await self.get_elem_by_xpath("//select[@id='countySelectCommon']")
                        if area_selector:
                            await area_selector.click()
                            await(await self.get_elem_with_wait_by_xpath(2, "//option[@value='350305']")).click()
                            await(await self.get_elem_by_xpath("//a[@id='okUserinfoPopCommon']")).click()
            else:
                self.logger.error("加载地区信息失败")
                raise BusinessException("加载地区信息失败")

    async def handle_qrcode_alert(self):
        alert_elem = await self.get_elem_with_wait_by_xpath(3, "//div[@class='qrCodeBox']")
        if alert_elem:
            close_btn = await self.get_elem_by_xpath("//img[@class='wxClose']")
            if close_btn:
                try:
                    await close_btn.click()
                except:
                    self.logger.error("关闭关联微信窗口失败")

    async def _get_course_package_id(self):
        ret = []

        if self.user_center_page_url not in await self.get_current_url():
            # 当前在用户中心页面，
            await self.open_in_new_window(self.user_center_page_url)
            await self.close_other_windows(self.get_current_page())
        try:
            course_package_elems = await self.get_elems_with_wait_by_xpath(5,
                                                                           "//ul[@class='list']/li[.//span[@class='exp-per'][text()!='100.00%']]",
                                                                           visible=False)
        except:
            self.logger.info("没有未读的课程包")
        else:
            if course_package_elems:
                for course_package_elem in course_package_elems:
                    package_id = await course_package_elem.get_attribute("id")
                    ret.append(package_id)
                    # if package_id.startswith("27"):
                    #     ret.append(package_id)
        return ret

    async def _get_next_content(self, course_package_ids):
        next_content = None
        for course_package_id in course_package_ids:
            next_content = await self._get_first_unfinished_content(course_package_id)
            if not next_content:
                continue
            else:
                break
        return next_content

    async def _get_first_unfinished_content(self, course_package_id):
        ret = None
        required_content_list = await self._get_required_content_info(course_package_id)
        elective_content_list = await self._get_elective_content_info(course_package_id)
        content_list = required_content_list + elective_content_list
        for course_package_id_local, module_id, course_id, content_body, commodity_id in content_list:
            if ret is not None:
                break
            data_list = content_body["data"]

            # 排序，测验排到最后，读书先
            # data_list = self._sort_content_list_by_file_type(data_list)
            # 有video字段的是视频，没有video字段的是测验！
            for data in data_list:
                if data["fileType"] is None:
                    # fileType字段为None，说明是测验，不是看视频
                    pass_flag = data["passFlag"]
                    if pass_flag is not None and pass_flag == 1:
                        # 测验已经通过了，则不需要再学习
                        continue
                    else:
                        # 测验需要另外处理！
                        course_detail_page_url = self.FJRC_COURSE_DETAIL_PAGE_URL_TMPL % (
                            commodity_id, course_package_id_local)
                        ret = {"type": "exercise", "content_name": data["testName"], "url": course_detail_page_url}
                        break
                elif data["fileType"] == "video" and int(
                        data["videoLeanPercent"] if data["videoLeanPercent"] else 0) < 99:
                    # 是观看视频，而且视频没看完的情况
                    page_url = self.FJRC_VIDEO_PAGE_URL_TMPL % (
                        module_id, course_id, data["id"], course_package_id_local)
                    ret = {"type": "video", "content_name": data["lectureName"], "url": page_url}
                    break
        return ret

    async def _get_required_content_info(self, course_package_id) -> List[tuple]:
        ret = list()
        required_courses = await self._get_required_unfinished_course(course_package_id)
        # id, classtypeId, commodityId
        if required_courses is not None and len(required_courses) > 0:
            for course in required_courses:
                # 该网站的规则：视频读完了，课程进度就是100%，不管测验有没有做！因此，存在一个问题：当测验在最后一个课程的时候，测验未做的情况下，课程进度为100%！
                # 此时，需要从配置文件中读取，课程中是否有测验，有的话忽略进度为100%条件，继续获取课程下的所有子目录
                # 从而不会出现测验未做的bug
                course_contains_exercise_flag = self.node_config.get("node_params", {}).get(
                    self.FJRC_COURSE_CONTAINS_EXERCISE_FLAG_TMPL % course["commodity_id"])
                if course["study_percent"] != "100.00" or course_contains_exercise_flag == "1":
                    # if course["study_percent"] != "100.00":
                    lectures = await self._get_lectures(course["id"], course["commodity_id"])
                    await asyncio.sleep(0.1)
                    if lectures is not None and len(lectures) > 0:
                        for lecture in lectures:
                            ret.append((course_package_id, lecture["module_id"], course["id"],
                                        await self._get_sub_contents_in_lecture(lecture["id"], course["id"],
                                                                                course_package_id),
                                        course["commodity_id"]))
                            await asyncio.sleep(0.1)

        return ret

    async def _get_elective_content_info(self, course_package_id):
        # 获取选修课程信息
        ret = list()
        elective_course_names: str = self.node_config.get("node_params", {}).get(
            self.FJRC_ELECTIVE_COURSES_TMPL % course_package_id)
        if elective_course_names is not None and len(elective_course_names) > 0:
            elective_course_name_list = elective_course_names.split(",")
            for elective_course_name in elective_course_name_list:
                elective_courses = await self._get_elective_unfinished_course(course_package_id)
                third_courses = await self._get_third_study_course(course_package_id)
                elective_courses.extend(third_courses)
                # id, classtypeId, commodityId
                if elective_courses is not None and len(elective_courses) > 0:
                    for course in elective_courses:
                        # 该网站的规则：视频读完了，课程进度就是100%，不管测验有没有做！因此，存在一个问题：测验未做的情况下，课程进度为100%！
                        # 此时，需要从配置文件中读取，课程中是否有测验，有的话忽略进度为100%条件，继续获取课程下的所有子目录
                        # 从而不会出现测验未做的bug
                        course_contains_exercise_flag = self.node_config.get("node_params", {}).get(
                            self.FJRC_COURSE_CONTAINS_EXERCISE_FLAG_TMPL % course["commodity_id"])
                        if (course["study_percent"] != "100.00" or course_contains_exercise_flag == "1") \
                                and course["name"] == elective_course_name:
                            lectures = await self._get_lectures(course["id"], course["commodity_id"])
                            await asyncio.sleep(0.1)
                            if lectures is not None and len(lectures) > 0:
                                for lecture in lectures:
                                    ret.append((course_package_id, lecture["module_id"], course["id"],
                                                await self._get_sub_contents_in_lecture(lecture["id"], course["id"],
                                                                                        course_package_id),
                                                course["commodity_id"]))
                                    await asyncio.sleep(0.1)

        return ret

    async def _get_required_unfinished_course(self, course_package_id):
        # 必修课程
        ret = list()
        url = "https://fj.rcpxpt.com/classPackage/findRequiredCourse/%s" % course_package_id
        headers = {"Cookie": await self.cookie_to_str(), "Content-Type": "application/json;charset=utf-8",
                   "User-Agent": await self.user_agent()}
        try:
            resp = await self.context.request.post(url, headers=headers)
        except:
            self.logger.error("获取必修课程失败")
        else:
            try:
                resp_json_obj = await resp.json()
            except:
                self.logger.exception("解析必修课程返回报文失败：%s" % resp.text)
            else:
                if resp_json_obj is not None and len(resp_json_obj) > 0:
                    for item in resp_json_obj:
                        ret.append(
                            {"id": item["id"], "commodity_id": item["commodityId"],
                             "study_percent": item["studyPercent"]})
        return ret

    async def _get_elective_unfinished_course(self, course_package_id):
        ret = list()
        # https://fj.rcpxpt.com/classPackage/findElectiveCourse/27170
        referer = "https://fj.rcpxpt.com/classPackage/classPackageDetail/%s" % course_package_id
        url = "https://fj.rcpxpt.com/classPackage/findElectiveCourse/%s" % course_package_id
        data = r'{"name":"","itemOneId":"","itemSecondId":"","minStudyHour":"","maxStudyHour":"","onlyLearned":"","page":1,"pageSize":10}'
        headers = {"Cookie": await self.cookie_to_str(), "Content-Type": "application/json",
                   "User-Agent": await self.user_agent(), "Referer": referer}
        try:
            resp = await self.context.request.post(url, data=data, headers=headers)
        except:
            self.logger.exception("获取选修课程失败")
        else:
            try:
                resp_json_obj = await resp.json()
            except:
                self.logger.exception("解析选修课程返回报文失败：%s" % resp.text)
            else:
                data = resp_json_obj["data"]
                if data is not None and len(data) > 0:
                    for item in data:
                        ret.append(
                            {"id": item["id"], "commodity_id": item["commodityId"],
                             "study_percent": item["studyPercent"], "name": item["name"]})
        return ret

    async def _get_third_study_course(self, course_package_id):
        ret = list()
        # https://fj.rcpxpt.com/classPackage/findElectiveCourse/27170
        referer = "https://fj.rcpxpt.com/classPackage/classPackageDetail/%s" % course_package_id
        url = "https://fj.rcpxpt.com/classPackage/findThirdStudyCourse/%s" % course_package_id
        data = {"page": 1, "pageSize": 50}
        headers = {"Cookie": await self.cookie_to_str(),
                   "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
                   "User-Agent": await self.user_agent(), "Referer": referer}
        try:
            resp = await self.context.request.post(url, data=data, headers=headers)
        except:
            self.logger.exception("获取选修课程失败")
        else:
            try:
                resp_json_obj = await resp.json()
            except:
                self.logger.exception("解析选修课程返回报文失败：%s" % resp.text)
            else:
                data = resp_json_obj["data"]
                if data is not None and len(data) > 0:
                    for item in data:
                        ret.append(
                            {"id": item["id"], "commodity_id": item["commodityId"],
                             "study_percent": item["studyPercent"], "name": item["name"]})
        return ret

    async def _get_lectures(self, classtype_id, commodity_id):
        ret = list()
        url = "https://fj.rcpxpt.com/commoditynew/findPcLectrueById"
        headers = {"Cookie": await self.cookie_to_str(),
                   "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                   "User-Agent": await self.user_agent()}
        # params = "page=1&classtypeId=%s&commodityId=%s&videoIsBuy=0" %(classtypeId, commodityId)
        params = {"page": 1, "classtypeId": classtype_id, "commodityId": commodity_id, "videoIsBuy": 0}
        try:
            resp = await self.context.request.post(url, params=params, headers=headers)
        except:
            self.logger.exception("获取课程的章节失败")
        else:
            try:
                resp_json_obj = await resp.json()
            except:
                self.logger.exception("解析课程的章节返回报文失败：%s" % resp.text)
            else:
                data_list = resp_json_obj["data"]
                if data_list is not None and len(data_list) > 0:
                    for item in data_list:
                        ret.append(
                            {"id": item["id"], "module_id": item["moduleId"]})
        return ret

    async def _get_sub_contents_in_lecture(self, lecture_id, classtype_id, class_package_id) -> dict:
        ret = None
        url = "https://fj.rcpxpt.com/commoditynew/queryLecturesByChapterId"
        headers = {"Cookie": await self.cookie_to_str(),
                   "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
                   "User-Agent": await self.user_agent()}
        # params = "page=1&pageSize=12&chapterId=3619613&classtypeId=1301306&videoIsBuy=0&classPackageId=27170"
        params = {"page": 1, "pageSize": 50, "chapterId": lecture_id, "classtypeId": classtype_id, "videoIsBuy": 0,
                  "classPackageId": class_package_id}
        try:
            resp = await self.context.request.post(url, params=params, headers=headers)
        except:
            self.logger.exception("获取章节的子目录失败")
        else:
            try:
                ret = await resp.json()
            except:
                self.logger.exception("解析章节的子目录返回报文失败：%s" % resp.text)
            else:
                # data_list = resp_json_obj["data"]
                # if data_list is not None and len(data_list) > 0:
                #     for item in data_list:
                #         ret.append(
                #             {"id": item["id"]})
                pass

        return ret
