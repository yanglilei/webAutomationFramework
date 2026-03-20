import asyncio
import random
from dataclasses import dataclass, field
from typing import Dict

from playwright.async_api import Request

from src.frame.base.base_task_node import BasePYNode
from src.utils.smtedu_sign_utils import SMTEduSignUtils, RequestMethod
from src.utils.utils import calculate_request_times, random_int_exclude_values


@dataclass(init=False)
class SMTEDUGetPoints(BasePYNode):
    # 获取收藏的课程的url模板
    favor_course_url_tmpl = "https://e-favorite-api.ykt.eduyun.cn/v1/user_favors?$count=true&$offset=%d&$limit=%d&_userId=%s&client_id=all"
    # 获取所有教材
    all_textbook_url = "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/prepare_lesson/teachingmaterials/part_100.json"
    # 获取课程树的url模板，能否获悉该教材下有哪些优秀的资源
    course_tree_url_tmpl = "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/prepare_lesson/trees/%s.json"
    # 获取课程详情的url模板，能够获悉每个资源中的详细内容，比如该一个资源中有视频、音频、图片、pdf
    textbook_detail_url_tmpl = "https://s-file-1.ykt.cbern.com.cn/zxx/ndrs/prepare_lesson/teachingmaterials/%s/resources/part_100.json"

    # EXTRACTED_AUTHORIZATION = ""
    pre_authorization: str = ""
    cur_authorization: str = ""
    sdp_app_id: str = ""
    user_agent: str = ""
    # ["X-ND-AUTH"]请求头
    x_nd_auth_tmpl: str = 'MAC id="%s",nonce="0",mac="0"'
    # 请求头
    headers: Dict[str, str] = field(default_factory=dict)
    # 用户id
    user_id: str = ""
    # mac_key
    mac_key: str = ""
    # token
    access_token: str = ""
    # app_id
    app_id: str = ""
    # 最大尝试次数
    max_try_times: int = 20
    # 已经尝试的次数
    try_times: int = 0
    # 做之前的积分
    previous_total_points: float = 0.0
    # 做完的积分
    current_total_points: float = 0.0
    # 会话ID
    session_id: str = ""
    # 总共浏览课程数量，起始为1，因为进入课程页面就已经自动打开了一个课程。
    total_view_course_count: int = 1

    async def intercept_request_authorization(self, request: Request):
        """
        监听所有请求，提取目标接口的 Authorization 请求头
        :param request: 浏览器上下文的请求对象
        """
        # 1. 过滤目标接口（比如包含 /api/ 的接口，可根据实际调整）
        # 可叠加过滤条件：请求方法、资源类型等
        if request.method in ["GET", "POST", "PUT"]:
            # 2. 从请求头中提取 Authorization
            self.pre_authorization = request.headers.get("authorization")
            if self.pre_authorization and self.pre_authorization != self.cur_authorization:  # 只提取一次，避免覆盖
                self.cur_authorization = self.pre_authorization
                self.logger.info(f"✅ 成功从请求中提取 authorization: {self.cur_authorization}")
                self.sdp_app_id = request.headers.get("sdp-app-id")
                self.user_agent = request.headers.get("user-agent")

    async def execute(self, context: Dict) -> bool:
        # 进入到我的收藏页面
        await self.load_url("https://basic.smartedu.cn/user/myFavorite")
        # 获取用户签名信息
        self.user_id, self.mac_key, self.access_token, self.app_id = await SMTEduSignUtils.get_user_sign_params(
            self.execute_js)
        self.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
            "sdp-app-id": self.app_id}
        # 获取当前积分
        self.previous_total_points = await self.get_user_points()
        # 和育小苗互动5次
        await self._comm_with_yxm()
        # 获取会话ID
        # self.session_id = await self._get_session_id()
        # 获取已经收藏的课程，已经收藏了，不需要再收藏
        exclude_course_ids = await self.get_favor_courses()
        # 开始学习
        await self.learn_course(exclude_course_ids)
        self.current_total_points = await self.get_user_points()
        if self.current_total_points > self.previous_total_points:
            self.logger.info(f"🎉 恭喜，积分增加了！总积分：{self.previous_total_points} -> {self.current_total_points}")
        else:
            self.logger.warning(f"❌ 积分没有增加！总积分：{self.previous_total_points} -> {self.current_total_points}")

        if self.user_manager:
            self.user_manager.update_record_by_username(self.username, {2: self.current_total_points})
            self.logger.info(f"✅ 更新用户积分成功！积分：{self.current_total_points}")
        return True

    def set_up(self):
        # 关键步骤：给上下文绑定 response 监听事件
        # self.context.on("request", self.intercept_request_authorization)
        # self.headers["X-ND-AUTH"] = self.x_nd_auth_tmpl % access_token
        super().set_up()

    async def get_user_points(self):
        # 获取今年积分
        url = r"https://x-incentive-service.ykt.eduyun.cn/v1/incentives/my_package"
        # 获取去年积分
        # url = r"https://x-incentive-service.ykt.eduyun.cn/v1/incentives/my_package?last_year=true"
        self._set_authorization(url, RequestMethod.GET)
        try:
            resp = await self.context.request.get(url, headers=self.headers)
            json = await resp.json()
            return json["total"]
        except Exception as e:
            self.logger.exception("获取用户积分失败：")
            return None

    async def get_favor_courses(self) -> list:
        """
        获取收藏的课程列表
        :return:
        """
        self.logger.info("👉获取收藏的课程列表...")
        ret = []
        url = self.favor_course_url_tmpl % (0, 1, self.user_id)
        self._set_authorization(url, RequestMethod.GET)
        try:
            resp = await self.context.request.get(url, headers=self.headers)
        except Exception as e:
            self.logger.error(e)
            return ret
        else:
            json = await resp.json()
            total = json["total"]
            page_size = 12
            request_times = calculate_request_times(total, page_size)
            for i in range(request_times):
                url = self.favor_course_url_tmpl % (i * page_size, page_size, self.user_id)
                self._set_authorization(url, RequestMethod.GET)
                resp = await self.context.request.get(url, headers=self.headers)
                json = await resp.json()
                for item in json["items"]:
                    ret.append(item["content_id"])
                await asyncio.sleep(random.uniform(0.3, 2))
        self.logger.info("✅获取收藏的课程列表成功！")
        return ret

    def _set_authorization(self, url, request_method):
        self.headers["authorization"] = SMTEduSignUtils.gen_authorization(url, self.access_token, self.mac_key,
                                                                          request_method)

    def gen_authorization(self, url, request_method):
        return SMTEduSignUtils.gen_authorization(url, self.access_token, self.mac_key, request_method)

    async def get_teaching_materials(self):
        url = "https://s-file-2.ykt.cbern.com.cn/zxx/ndrs/prepare_lesson/teachingmaterials/part_100.json"
        self._set_authorization(url, RequestMethod.GET)
        resp = await self.context.request.get(url, headers=self.headers)
        json = await resp.json()
        return json

    async def get_one_teaching_material_detail(self, material_id: str) -> list[dict]:
        url_tmpl = "https://s-file-2.ykt.cbern.com.cn/zxx/ndrs/prepare_lesson/teachingmaterials/%s/resources/part_100.json"
        url = url_tmpl % material_id
        self._set_authorization(url, RequestMethod.GET)
        resp = await self.context.request.get(url, headers=self.headers)
        json = await resp.json()
        return json

    async def get_target_courses(self, target_material, exclude_course_ids: list):
        material_info = await self.get_one_teaching_material_detail(target_material)
        target_courses = []
        for item in material_info:
            if item["id"] in exclude_course_ids:
                continue

            relations = item.get("relations", {})
            courses = relations.get("national_course_resource", [])
            courses.extend(relations.get("course_resource", []))
            if not courses:
                continue

            if any([course.get("resource_type_code") in {"assets_document", "coursewares", "lesson_plandesign",
                                                         "learning_task", "after_class_exercise"} for course in
                    courses]):
                # 有包含了文档的课程
                target_courses.append(item)

        return target_courses

    async def choose_target_courses(self, exclude_course_ids: list, exclude_material_ids=[]):
        """
        选择目标课程，进行评分、点赞、收藏的操作
        :param exclude_course_ids: 排除的课程ID列表，为已经收藏过的课程列表
        :return:
        """
        # 获取所有的物料
        teaching_materials = await self.get_teaching_materials()
        length = len(teaching_materials) - 1

        exclude_indexes = set()
        while True:
            randint = random.randint(0, length)
            exclude_indexes.add(randint)
            target_material = teaching_materials[randint]
            if target_material.get("id") not in exclude_material_ids:
                # 后续不能再次获取该教材了，避免重复提高效率
                exclude_material_ids.append(target_material.get("id"))
                break

        while True:
            target_courses = await self.get_target_courses(target_material.get("id"), exclude_course_ids)
            if target_courses:
                break

            while True:
                # 思路：随机获取一个目标素材，然后获取该素材下的课程，如果课程包含文档，则返回该素材下的课程；否则，重新获取一个目标素材
                idx = random_int_exclude_values(0, length, exclude_indexes)
                exclude_indexes.add(idx)
                target_material = teaching_materials[idx]
                if target_material.get("id") not in exclude_material_ids:
                    # 后续不能再次获取该教材了，避免重复提高效率
                    exclude_material_ids.append(target_material.get("id"))
                    break

        return target_courses, exclude_material_ids

    async def _do_like(self):
        btn_like = await self.get_elem_with_wait_by_xpath(10,
                                                          "//div[@class='course-detail-control']//div[contains(@class, 'index-module_like-count')]")
        await btn_like.click()
        self.logger.info("✅点赞成功！")

    async def _do_favor(self):
        btn_favor = await self.get_elem_with_wait_by_xpath(10,
                                                           "//div[@class='course-detail-control']//i[contains(@class, 'index-module_uncollected')]")
        await btn_favor.click()
        await asyncio.sleep(1.5)
        btn_confirm = await self.get_elem_with_wait_by_xpath(1.5, "//button[@class='fish-btn fish-btn-primary']")
        if btn_confirm:
            await btn_confirm.click()
        self.logger.info("✅收藏成功！")

    async def _do_send_points(self):
        btn_send_points = await self.get_elem_with_wait_by_xpath(10,
                                                                 "//div[@class='course-detail-control']//button[@class='fish-btn fish-btn-round']")
        await btn_send_points.click()
        await asyncio.sleep(1)
        btn_config_xpath = "//div[@class='course-detail-control']//button[.//span[text()='确认提交']]"
        btn_confirm = await self.get_elem_with_wait_by_xpath(5, btn_config_xpath)
        if btn_confirm:
            if not await btn_confirm.is_visible():
                await btn_confirm.scroll_into_view_if_needed()
            await btn_confirm.click()
        else:
            # 兜底用js点击
            js = """let btn_confirm = document.evaluate("//div[@class='course-detail-control']//button[.//span[text()='确认提交']]", document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null).singleNodeValue;
btn_confirm.click();"""
            await self.execute_js(js)

        # btn_confirm = await self.wait_for_visible_by_xpath(5, "//div[@class='course-detail-control']//button[.//span[text()='确认提交']]")
        self.logger.info("✅提交评分成功！")

    async def _learn_course(self):
        # 点赞
        await self._do_like()
        await asyncio.sleep(random.uniform(0.1, 2))
        # 收藏
        await self._do_favor()
        await asyncio.sleep(random.uniform(0.1, 2))
        # 评分
        await self._do_send_points()
        await asyncio.sleep(random.uniform(0.1, 2))
        # 切换课程
        first_unfinished_content = await self.get_elem_with_wait_by_xpath(10,
                                                                          "(//div[contains(@class,'study-list-item study-list-item-active')]/following-sibling::div)[1]")
        while first_unfinished_content:
            if not await first_unfinished_content.is_visible():
                await first_unfinished_content.scroll_into_view_if_needed()
            await asyncio.sleep(random.uniform(0.1, 1))
            await first_unfinished_content.click()
            await asyncio.sleep(random.uniform(0.1, 2))
            first_unfinished_content = await self.get_elem_by_xpath(
                "(//div[contains(@class,'study-list-item study-list-item-active')]/following-sibling::div)[1]")
            self.total_view_course_count += 1
        # 点击存到我的资源库5次
        btn_save = await self.get_elem("//span[@class='study-more-menu']")
        for _ in range(5):
            await btn_save.click()
            self.logger.info(f"✅存在到我的资源库+1")
            await asyncio.sleep(random.uniform(0.3, 2))

    async def learn_course(self, favor_course_ids: list, exclude_material_ids=[]):
        courses, exclude_material_ids = await self.choose_target_courses(favor_course_ids, exclude_material_ids)
        course_page_url_tmpl = "https://basic.smartedu.cn/syncClassroom/classActivity?activityId=%s"
        is_enter_course = False
        for course in courses:
            title = course.get("title")
            course_page_url = course_page_url_tmpl % course.get("id")
            await self.open_in_new_window(course_page_url)
            await self.switch_to_latest_window()
            if await self.get_elem_with_wait(5, "//div[contains(@class,'index-module_error')]"):
                # 出现课程找不到的问题，说明资源被删除了
                await asyncio.sleep(random.uniform(1, 3.5))
                self.logger.error(f"❌课程找不到，尝试切换下一个课程！")
                # 一个课程找不到了，基本上代表该教材中的其他课程都没有了，可以换一本教材了，避免重试太多次导致账号被封禁
                await self.close_latest_window()
                await self.switch_to_latest_window()
                break
                # continue
            else:
                self.logger.info(f"✅进入课程成功！课程名称：{title}")
                is_enter_course = True
                break

        if is_enter_course:
            await self._learn_course()
            if self.total_view_course_count < 5:
                self.try_times = 0
                await self.learn_course(favor_course_ids, exclude_material_ids)
            else:
                self.logger.info("✅已查看5个课程，退出！")
        else:
            self.try_times += 1
            if self.try_times >= self.max_try_times:
                self.logger.error("❌尝试次数过多，不再寻找课程，该用户提升积分失败！")
                if self.user_manager:
                    self.user_manager.update_record_by_username(self.username,
                                                                {4: "提升积分失败：找不到合适的课程！重试达到10次！"})
                return
            else:
                self.logger.error(f"❌课程找不到，尝试切换一本教材！重试次数：{self.try_times}")
                # 课程找不到，重新尝试
                await self.learn_course(favor_course_ids, exclude_material_ids)

    async def _get_session_id(self):
        url = r"https://uc-gateway.ykt.eduyun.cn/v1.1/sessions"

        try:
            resp = await self.context.request.get(url, headers=self.headers)
        except:
            self.logger.exception("获取session_id失败：")
        else:
            json = await resp.json()
            return json.get("session_id")

    async def _comm_with_yxm(self):
        # 和育小苗进行互动，5次
        btn_open_xm = await self.get_elem_with_wait_by_xpath(10, "//div[@class='ai-assistant2-entrance']")
        if btn_open_xm:
            await btn_open_xm.click()
            # 等待出现育小苗对话框！
            await self.wait_for_visible_by_xpath(10, "//div[contains(@class, 'fish-modal-wrap ai-assistant2-modal')]")
            # 获取您可以这样问我的列表
            btn_known = await self.get_elem_with_wait_by_xpath(10,
                                                               "//div[@class='ai-assistant2-leftpanel-agents-tip-btn']")
            if btn_known:
                await self.js_click(btn_known)
                total_count = 5
                while total_count > 0:
                    qs_list = await self.get_elems_with_wait_by_xpath(10,
                                                                      "//div[@class='ai-assistant2-homebox-listitem-question-wrapper']")
                    if qs_list:
                        await self.js_click(qs_list[0])

                    # 等待回答
                    await self.wait_for_visible_by_xpath(20, "//div[contains(@class,'ai-assistant2-answer-content')]")
                    # 再等待内容出来
                    await asyncio.sleep(random.uniform(3, 6))
                    # await asyncio.sleep(random.uniform(3, 6))
                    self.logger.info("✅和育小苗互动次数 +1")
                    total_count -= 1
                    if total_count == 0:
                        break

                    new_dialog = await self.get_elem_with_wait_by_xpath(10,
                                                                        "//div[@class='ai-assistant2-leftpanel-content']/span[contains(@class, 'ai-assistant2-leftpanel-operator')]//i[@class='ai-assistant2-operator-newtalk-icon']")
                    if new_dialog:
                        await self.js_click(new_dialog)
                    else:
                        self.logger.error(f"❌获取新的对话框按钮失败！停止和育小苗互动！还差 {total_count} 次，请人工操作！")
                        break

                    await asyncio.sleep(random.uniform(1, 3))
                    # 点击换一换
                    change_btn = await self.get_elem_with_wait_by_xpath(10,
                                                                        "//div[@class='ai-assistant2-homebox-change']")

                    if change_btn:
                        await self.js_click(change_btn)
                        await asyncio.sleep(random.uniform(1, 3))
                    else:
                        self.logger.error(f"❌获取换一换按钮失败！停止和育小苗互动！还差 {total_count} 次，请人工操作！")
                        break
