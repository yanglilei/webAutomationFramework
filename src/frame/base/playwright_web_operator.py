import logging
from pathlib import Path
from typing import List, Literal, Optional, Callable, Union, Pattern, Awaitable

from playwright.async_api import Page, BrowserContext, Dialog, Locator, FrameLocator


class PlaywrightWebOperator:

    def __init__(self, web_browser: BrowserContext):
        """
        初始化方法（替换为Playwright的BrowserContext）
        :param web_browser: Playwright的BrowserContext对象（管理多个页面/窗口）
        """
        self.context: BrowserContext = web_browser
        # 记录当前活跃页面（对应Selenium的current_window_handle）
        self._current_page: Page = self.context.pages[0] if self.context.pages else None
        # 记录当前frame（用于frame切换）
        self._current_frame = None

    def get_current_page(self) -> Page:
        """
        获取当前活跃页面，确保不为None
        """
        if not self._current_page or self._current_page.is_closed():
            self._current_page = self.context.pages[0] if self.context.pages else None
        # if not self._current_page:
        #     raise RuntimeError("无可用的页面/窗口")
        return self._current_page

    async def wait_for_url_changed(self, url: Union[str, Pattern[str], Callable[[str], bool]], timeout: float=10.0):
        await self.get_current_page().wait_for_url(url=url, timeout=timeout*1000)

    # async def _convert_by_to_selector(self, by: str, selector: str) -> str:
    #     """将Selenium的By类型转换为Playwright的selector格式"""
    #     if by == By.XPATH:
    #         return f"xpath={selector}"
    #     elif by == By.CSS_SELECTOR:
    #         return selector
    #     elif by == By.ID:
    #         return f"#{selector}"
    #     elif by == By.NAME:
    #         return f"[name='{selector}']"
    #     elif by == By.CLASS_NAME:
    #         return f".{selector}"
    #     else:
    #         raise ValueError(f"不支持的By类型：{by}")

    async def close_window(self, page: Page):
        """
        关闭页面
        :param page: 页面对象
        :return:
        """
        if not self._is_window_closed(page):
            await page.close()
            # 当前页面为none，避免当前页面被关了，而对象中还保留了旧的页面对象
            self._current_page = None

    async def close_latest_window(self):
        """
        关闭最新打开的页面
        :return:
        """
        await self.close_window(self.get_latest_window())

    def get_windows(self):
        """
        获取所有打开的页面
        :return:
        """
        # 返回所有未关闭的Page（对应Selenium的window_handles）
        return [page for page in self.context.pages if not page.is_closed()]

    def get_latest_window(self):
        """
        获取最新打开的页面
        :return:
        """
        windows = self.get_windows()
        return None if not windows else windows[-1]

    def _is_window_closed(self, window_handle: Page):
        """
        判断页面是否已关闭
        :param window_handle: 页面句柄
        :return:
        """
        return window_handle not in self.context.pages or window_handle.is_closed()

    async def refresh(self):
        """
        刷新当前页面
        :return:
        """
        page = self.get_current_page()
        await page.reload()

    async def cookie_to_str(self, page=None):
        """
        将Cookie转为字符串
        格式：a=b;c=d;...
        :param page:
        :return:
        """
        cookies: List[dict] = await self.get_cookies(page)  # Playwright从Context获取Cookies
        return "".join(["%s=%s;" % (cookie["name"], cookie["value"]) for cookie in cookies])[0:-1] if cookies else ""

    async def get_cookies(self, page=None) -> list[dict]:
        """
        获取指定page的Cookie，若未传page则获取上下文所有Cookie

        参数：
            context: playwright.async_api._context.BrowserContext - 浏览器上下文（必传）
            page: playwright.async_api._page.Page - 目标页面（可选，默认None）

        返回：
            list[dict] - Cookie列表，每个Cookie字典包含domain/name/value等字段

        异常：
            若page存在但未导航（url为空），返回空列表并打印提示
        """
        try:
            # 1. 传了page：获取该page当前域名的Cookie
            if page:
                # 检查page是否已导航（避免url为空导致获取不到Cookie）
                if not page.url or page.url == "about:blank":
                    print(f"警告：页面未导航，无法获取对应域名的Cookie！")
                    return []
                # 获取该页面域名的Cookie（核心：用page的url过滤）
                return await self.context.cookies(page.url)

            # 2. 未传page：获取上下文所有Cookie
            else:
                return await self.context.cookies()
        except Exception as e:
            print(f"获取Cookie失败：{str(e)}")
            return []

    async def user_agent(self):
        """
        获取当前页面的User-Agent
        :return:
        """
        page = self.get_current_page()
        return await page.evaluate("navigator.userAgent")

    async def close_other_windows(self, cur_window_handle=None):
        """
        关闭其他窗口
        :param cur_window_handle: 当前窗口句柄
        :return:
        """
        if not cur_window_handle:
            cur_window_handle = self.get_current_page()

        if self._is_window_closed(cur_window_handle):
            # raise ValueError("当前窗口已关闭")
            return

        for window_handle in self.get_windows():
            if window_handle != cur_window_handle:
                await self.close_window(window_handle)
        # 切换到当前窗口
        self._current_page = cur_window_handle
        await cur_window_handle.bring_to_front()

    async def switch_to_window_by_url_key(self, value):
        """
        根据url_key获取窗口
        :param value: url_key
        :return:
        """

        async def _switch_to_window_by_url_key(value):
            for window_handle in self.get_windows():
                self._current_page = window_handle
                if value in window_handle.url:
                    return window_handle
            else:
                raise ValueError("未找到包含【%s】的窗口" % value)

        window_handler = await _switch_to_window_by_url_key(value)
        if self._current_page != window_handler:
            self._current_page = window_handler
            await window_handler.bring_to_front()

    async def get_windows_by_url_key(self, url_key: str, is_support_fuzzy=True) -> list[Page]:
        """
        根据url_key获取窗口
        :param url_key: url关键字
        :param is_support_fuzzy: 是否支持模糊匹配
        :return:
        """
        windows = []
        for window_handle in self.get_windows():
            if is_support_fuzzy:
                if url_key in window_handle.url:
                    windows.append(window_handle)
            else:
                if url_key == window_handle.url:
                    windows.append(window_handle)

        return windows

    async def switch_to_window(self, page: Page, bring_to_front=True):
        """
        切换窗口
        :param page: 页面
        :param bring_to_front: 是否切换到最前面
        :return:
        """
        if not page:
            return
        if self._is_window_closed(page):
            return
            # raise ValueError("窗口已关闭")
        self._current_page = page
        if bring_to_front:
            await page.bring_to_front()

    async def switch_to_latest_window(self):
        """
        切换到最新窗口
        :return:
        """
        latest_window = self.get_latest_window()
        await self.switch_to_window(latest_window)

    def switch_to_frame(self, frame_reference: str, selector: Locator | FrameLocator = None) -> FrameLocator:
        """
        获取iframe
        返回FrameLocator实例
        :param frame_reference: 符合playwright规则的定位表达式
        :param locator: Locator or FrameLocator实例，不传默认在page下查找，否则在该Locator下查找
        :return:
        """
        # FrameLocator 是惰性求值的 iframe 定位器，创建后可直接定位 iframe 内部元素，无需 “显式进入 / 退出”，逻辑最简洁，适配动态加载的 iframe。
        locator = self.get_current_page() if not selector else selector
        frame = locator.frame_locator(frame_reference)
        self._current_frame = frame
        return self._current_frame

    async def go_back(self):
        """
        返回上一页
        :return:
        """
        page = self.get_current_page()
        await page.go_back()

    async def open_in_new_window(self, url, *,
        timeout: Optional[float] = None,
        wait_until: Optional[
            Literal["commit", "domcontentloaded", "load", "networkidle"]
        ] = None,
        referer: Optional[str] = None):
        """
        新建Page（窗口）并打开URL
        :param url: url地址
        :param timeout: 等待时间，单位：秒
        :param wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"]
        :param referer: 请求头里的「来源地址」
        :
        :return:
        """
        new_page = await self.context.new_page()
        timeout = int(timeout*1000) if timeout else None
        await new_page.goto(url, timeout=timeout, wait_until=wait_until, referer=referer)
        self._current_page = new_page

    async def quit(self):
        # 关闭上下文和浏览器
        await self.context.close()
        await self.context.browser.close()

    async def load_url(self, url,
                    timeout: Optional[float] = None,
                    wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] = "load"):
        """
        加载指定url
        :param url: url
        :param timeout: 等待时间，单位：秒
        :param wait_until: 等待条件，可选值：commit, domcontentloaded, load, networkidle
        :return:
        """
        page = self.get_current_page()
        timeout = int(timeout * 1000) if timeout else None
        await page.goto(url, timeout=timeout, wait_until=wait_until)

    async def wait_for_load_state(self, timeout: float, state: Literal["domcontentloaded", "load", "networkidle"] = "load"):
        """
        等待页面加载完成
        :param timeout: 等待时间，单位：秒
        :param state: 默认load，可选值："domcontentloaded", "load", "networkidle"
        :return:
        """
        page = self.get_current_page()
        await page.wait_for_load_state(state=state, timeout=int(timeout*1000))

    async def execute_js(self, js_str: str, arg=None, locator: Optional[Locator] = None):
        """
        执行js代码
        :param js_str: js代码
        :param arg: 参数，请参照Page.evaluate方法中关于arg参数的介绍
        :param locator: locator，不传默认为当前page（即main_frame）
        :return:
        """
        if not locator:
            locator = self.get_current_page()
        return await locator.evaluate(js_str, arg)

    async def js_click(self, locator: Locator):
        """
        js点击元素
        :param locator: Locator元素
        :return:
        """
        await locator.evaluate("elem => elem.click();")
        # await self.execute_js("elem => elem.click();", locator=locator)

    async def open_blank_tab(self):
        """
        打开空白tab
        :return:
        """
        new_page = await self.context.new_page()
        await new_page.goto("about:blank")
        self._current_page = new_page

    def format_video_time(self, time: str):
        # 纯字符串处理，逻辑不变
        ret = time
        if len(time) < 5:
            ret = "00:" + time.rjust(5, "0")
        elif len(time) < 6:
            ret = "00:" + time
        elif len(time) < 8:
            ret = time.rjust(8, "0")
        return ret

    async def screenshot(self, path: Optional[str | Path] = None, element: Optional[Locator] = None) -> bytes:
        """
        截图
        支持元素和当前页面截图
        :param path: 保存路径
        :param element: 元素，不为空则截图该元素
        :return:
        """
        if not element:
            page = self.get_current_page()
            return await page.screenshot(path=path, full_page=True)
        else:
            return await element.screenshot(path=path)

    async def get_current_url(self, page=None):
        """
        获取当前页面的url
        :param page:
        :return:
        """
        ret = ""
        if not page:
            page = self.get_current_page()

        if not self._is_window_closed(page):
            ret = page.url
        return ret

    async def play_video(self, video_css: str, locator: Locator = None):
        if not locator:
            locator = self.get_current_page()
        await locator.evaluate(""" (css_expr) => {
            let video = document.querySelector(css_expr);
            if (video != null) {
                if (!video.muted || video.volume != 0) {
                    video.muted = true;
                    video.volume = 0;
                }
                if (video.paused) {
                    video.play();
                }
            }}
            """, video_css)

    async def is_video_ended(self, video_css: str, locator: Locator = None):
        if not locator:
            locator = self.get_current_page()

        return await locator.evaluate(""" (css_expr) => {
            let v = document.querySelector(css_expr);
            return v ? v.ended : null;
            }
            """, video_css)

    async def get_elem_with_wait(self, wait_time: float, selector, visible=True,
                                 iframe: Locator | FrameLocator = None) -> Optional[Locator]:
        """
        延迟获取元素
        :param wait_time:等待时间
        :param selector: 符合playwright的locator格式
        :param visible: True-等待可见，False-等待存在
        :param iframe: Locator or FrameLocator实例，不传默认在page下查找，否则在该Locator下查找
        :return: Playwright Locator对象（兼容原WebElement）
        """
        context = self.get_current_page() if not iframe else iframe
        try:
            locator = context.locator(selector)
            await locator.first.wait_for(state="visible" if visible else "attached", timeout=wait_time * 1000)
            return None if await locator.count() == 0 else locator.first
        except Exception:
            return None

    async def get_elem_with_wait_by_xpath(self, wait_time: float, xpath: str, visible=True,
                                          iframe: Optional[FrameLocator] = None) -> Locator:
        """
        等待获取元素
        :param wait_time:等待时间
        :param xpath: xpath表达式
        :param visible: True-可见，False-存在
        :param iframe: Locator or FrameLocator实例，不传默认在page下查找，否则在该Locator下查找
        :return: Playwright Locator对象（兼容原WebElement）
        """
        return await self.get_elem_with_wait(wait_time, f"xpath={xpath}", visible, iframe)

    async def get_elem_with_wait_by_css(self, wait_time: float, css: str, visible=True,
                                        iframe: Optional[FrameLocator] = None) -> Locator:
        """
        等待获取元素
        :param wait_time:等待时间
        :param css: css表达式
        :param visible: True-可见，False-存在
        :param iframe: Locator or FrameLocator实例，不传默认在page下查找，否则在该Locator下查找
        :return: Playwright Locator对象（兼容原WebElement）
        """
        return await self.get_elem_with_wait(wait_time, css, visible, iframe)

    async def get_elems(self, selector, iframe=None) -> List[Locator]:
        context = self.get_current_page() if not iframe else iframe
        try:
            locator = context.locator(selector)
            return await locator.all()
        except:
            return []

    async def get_elems_by_xpath(self, xpath: str, iframe=None) -> List[Locator]:
        """
        获取多个元素
        :param xpath: xpath表达式
        :param iframe: iframe表达式
        :return: Locator列表
        """
        return await self.get_elems(f"xpath={xpath}", iframe)

    async def get_elems_by_css(self, css: str, iframe=None) -> List[Locator]:
        """
        获取多个元素
        :param css: css表达式
        :param iframe: iframe表达式
        :return: Locator列表
        """
        return await self.get_elems(css, iframe)

    async def get_elems_with_wait(self, timeout: float, selector: str, visible=True, iframe=None) -> List[Locator]:
        context = self.get_current_page() if not iframe else iframe
        try:
            locator = context.locator(selector)
            await locator.first.wait_for(timeout=timeout * 1000, state="visible" if visible else "attached")
            return await locator.all()
        except Exception as e:
            logging.exception("获取元素失败：")
            return []

    async def get_elems_with_wait_by_xpath(self, timeout: float, xpath: str, visible=True, iframe=None) -> List[
        Locator]:
        """
        等待获取多个元素
        当第一个元素“可见”或“存在”的时候就返回，不等待所有的元素“可见”或“存在”
        :param timeout: 等待时间，秒
        :param xpath: xpath表达式
        :param visible: True-可见；False-存在
        :param iframe: iframe表达式
        :return: Locator列表
        """
        return await self.get_elems_with_wait(timeout, f"xpath={xpath}", visible, iframe)

    async def get_elems_with_wait_by_css(self, timeout: float, css: str, visible=True, iframe=None) -> List[Locator]:
        """
        等待获取多个元素
        当第一个元素“可见”或“存在”的时候就返回，不等待所有的元素“可见”或“存在”
        :param timeout: 等待时间，秒
        :param css: css表达式
        :param visible: True-可见；False-存在
        :param iframe: iframe表达式
        :return: Locator列表
        """
        return await self.get_elems_with_wait(timeout, css, visible, iframe)

    async def get_elem(self, selector, iframe=None) -> Optional[Locator]:
        context = self.get_current_page() if not iframe else iframe
        try:
            locator = context.locator(selector)
            return locator.first if await locator.count() > 0 else None
        except Exception:
            return None

    async def get_elem_by_xpath(self, xpath: str, iframe=None) -> Optional[Locator]:
        """
        获取一个元素
        - 没有元素返回False
        - 存在元素返回元素本身
        :param xpath: xpath表达式
        :param iframe: iframe
        :return:
        """
        return await self.get_elem(f"xpath={xpath}", iframe)

    async def get_elem_by_css(self, css: str, iframe=None) -> Optional[Locator]:
        """
        获取一个元素
        - 没有元素返回False
        - 存在元素返回元素本身
        :param css: css表达式
        :param iframe: iframe
        :return:
        """
        return await self.get_elem(css, iframe)

    async def get_relative_elem(self, elem: Locator, locator: str) -> Optional[Locator]:
        try:
            ret = elem.locator(locator)
            return None if await ret.count() == 0 else ret.first
        except Exception:
            return None

    async def get_relative_elem_with_wait(self, timeout, elem: Locator, locator: str, visible=True) -> Optional[Locator]:
        try:
            ret = elem.locator(locator)
            await ret.first.wait_for(timeout=timeout * 1000, state="visible" if visible else "attached")
            return None if await ret.count() == 0 else ret.first
        except Exception:
            return None

    async def get_relative_elem_by_xpath(self, elem: Locator, xpath: str) -> Optional[Locator]:
        """
        获取一个相对 elem 的元素
        - 没有元素返回False
        - 存在元素返回元素本身
        :param elem: 元素
        :param xpath: xpath表达式
        :return:
        """
        return await self.get_relative_elem(elem, f"xpath={xpath}")

    async def get_relative_elem_with_wait_by_xpath(self, timeout: float, elem: Locator, xpath: str, visible=True) -> Optional[Locator]:
        """
        获取一个相对 elem 的元素
        - 没有元素返回False
        - 存在元素返回元素本身
        :param timeout: 超时时间，单位秒
        :param elem: 元素
        :param xpath: xpath表达式
        :param visible: True-等待可见，False-等待存在
        :return:
        """
        return await self.get_relative_elem_with_wait(timeout, elem, f"xpath={xpath}", visible)

    async def get_relative_elem_by_css(self, elem: Locator, css: str) -> Optional[Locator]:
        """
        获取一个相对 elem 的元素
        - 没有元素返回False
        - 存在元素返回元素本身
        :param elem: 元素
        :param css: css表达式
        :return:
        """
        return await self.get_relative_elem(elem, css)

    async def get_relative_elems(self, elem: Locator, locator: str) -> List[Locator]:
        try:
            return await elem.locator(locator).all()
        except Exception:
            return []

    async def get_relative_elems_by_xpath(self, elem: Locator, xpath: str) -> List[Locator]:
        """
        获取多个相对 elem 的元素
        :param elem: 元素
        :param xpath: xpath表达式
        :return: Locator列表
        """
        return await self.get_relative_elems(elem, f"xpath={xpath}")

    async def get_relative_elems_by_css(self, elem: Locator, css: str) -> List[Locator]:
        """
        获取多个相对 elem 的元素
        :param elem: 元素
        :param css: css表达式
        :return: Locator列表
        """
        return await self.get_relative_elems(elem, css)

    async def is_elem_visible(self, locator: str, iframe=None) -> Locator | bool:
        context = self.get_current_page() if not iframe else iframe
        try:
            locator = context.locator(locator)
            return False if not await locator.is_visible() else locator.first
        except:
            return False

    async def is_elem_visible_by_xpath(self, xpath: str, iframe=None) -> Locator | bool:
        """
        瞬时判断元素是否可见：
        - 元素可见 → 返回第一个匹配的元素 Locator
        - 元素不可见/不存在/异常 → 返回 False
        :param xpath: xpath表达式
        :param iframe: iframe
        :return:
        """
        return await self.is_elem_visible(f"xpath={xpath}", iframe)

    async def is_elem_visible_by_css(self, css: str, iframe=None) -> Locator | bool:
        """
        瞬时判断元素是否可见：
        - 元素可见 → 返回第一个匹配的元素 Locator
        - 元素不可见/不存在/异常 → 返回 False
        :param css: css表达式
        :param iframe: iframe
        :return:
        """
        # 修复原代码笔误（原调用了is_elem_exists）
        return await self.is_elem_visible(css, iframe)

    async def is_elem_exists(self, selector: str, iframe=None) -> bool:
        context = self.get_current_page() if not iframe else iframe
        try:
            ret = context.locator(selector)
            return False if await ret.count() == 0 else True
        except:
            return False

    async def is_elem_exists_by_xpath(self, xpath, iframe=None) -> bool:
        """
        瞬时判断元素是否存在：
        - 元素存在 → 返回第一个匹配的元素 Locator
        - 元素不存在/异常 → 返回 False
        :param xpath: xpath表达式
        :param iframe: iframe
        :return:
        """
        return await self.is_elem_exists(f"xpath={xpath}", iframe)

    async def is_elem_exists_by_css(self, css, iframe=None) -> bool:
        """
        瞬时判断元素是否存在：
        - 元素存在 → 返回第一个匹配的元素 Locator
        - 元素不存在/异常 → 返回 False
        :param css: css表达式
        :param iframe: iframe
        :return:
        """
        return await self.is_elem_exists(css, iframe)

    async def wait_for_disappeared(self, wait_time: float, locator: str | Locator, context=None):
        if not context:
            context = self.get_current_page()

        timeout = wait_time * 1000
        try:
            if isinstance(locator, str):
                locator_obj = context.locator(locator)
                await locator_obj.first.wait_for(timeout=timeout, state="hidden")
            else:
                await locator.first.wait_for(timeout=timeout, state="hidden")
        except:
            pass

    async def wait_for_disappeared_by_xpath(self, wait_time: float, xpath: str, iframe=None):
        """
        等待元素消失
        :param wait_time: 等待时间，单位秒
        :param xpath: xpath表达式
        :param iframe: iframe
        :return:
        """
        await self.wait_for_disappeared(wait_time, f"xpath={xpath}", iframe)

    async def wait_for_disappeared_by_css(self, wait_time: float, css: str, iframe=None):
        """
        等待元素消失
        :param wait_time: 等待时间，单位秒
        :param css: css表达式
        :param iframe: iframe
        :return:
        """
        await self.wait_for_disappeared(wait_time, css, iframe)

    async def register_alert_handler(self, handler: Callable[..., Union[Awaitable[None], None]]):
        """
        注册弹窗监听方法
        最好提前用该方法获取监听
        :param handler: 回调方法，接收一个Dialog类型的参数，dialog.message，dialog.accept(prompt_text=), dialog.dismiss()
        :return:
        """
        self.get_current_page().on("dialog", handler)

    async def is_alert_present(self) -> Dialog | bool:
        """
        判断网页弹窗是否存在
        - 不存在返回False
        - 存在返回Dialog
        :return:
        """
        try:
            return await self.get_current_page().wait_for_event("dialog", timeout=1.0)
        except:
            return False

    async def accept_dialog(self, dialog: Dialog, prompt_text=""):
        """
        处理弹窗
        :param dialog: 弹窗
        :param prompt_text: 输入内容
        :return:
        """
        await dialog.accept(prompt_text="我是输入的内容")

    async def wait_for_visible(self, wait_time: float, locator: Locator | str, iframe=None) -> Locator | bool:
        context = self.get_current_page() if not iframe else iframe
        timeout = wait_time * 1000
        try:
            if isinstance(locator, Locator):
                await locator.first.wait_for(timeout=timeout, state="visible")
                return locator
            else:
                locator_obj = context.locator(locator)
                await locator_obj.first.wait_for(timeout=timeout, state="visible")
                return locator_obj.first
        except:
            return False

    async def wait_for_visible_by_xpath(self, wait_time: float, xpath: str, iframe=None) -> Locator | bool:
        """
        等待元素可见
        - 返回第一个可见的元素 Locator
        - 元素不可见/异常 → 返回 False
        :param wait_time: 等待时间
        :param xpath: xpath表达式
        :param iframe: iframe
        :return:
        """
        return await self.wait_for_visible(wait_time, f"xpath={xpath}", iframe)

    async def wait_for_visible_by_css(self, wait_time: float, css: str, iframe=None) -> Locator | bool:
        """
        等待元素可见
        - 返回第一个可见的元素 Locator
        - 元素不可见/异常 → 返回 False
        :param wait_time: 等待时间
        :param css: css表达式
        :param iframe: iframe
        :return:
        """
        return await self.wait_for_visible(wait_time, css, iframe)

    async def is_elem_exists_with_wait(self, wait_time: float, locator: str, iframe=None) -> Locator | bool:
        context = self.get_current_page() if not iframe else iframe
        try:
            ret = context.locator(locator)
            await ret.first.wait_for(timeout=wait_time * 1000, state="attached")
            return ret.first
        except:
            return False

    async def is_elem_exists_with_wait_by_xpath(self, wait_time: float, xpath: str, iframe=None) -> Locator | bool:
        """
        等待元素存在
        - 返回第一个存在的元素 Locator
        - 元素不存在/异常 → 返回 False
        :param wait_time: 等待时间，单位：秒
        :param xpath: xpath表达式
        :param iframe: iframe
        :return:
        """
        return await self.is_elem_exists_with_wait(wait_time, f"xpath={xpath}", iframe)

    async def is_elem_exists_with_wait_by_css(self, wait_time: float, css, iframe=None) -> Locator | bool:
        """
        等待元素存在
        - 返回第一个存在的元素 Locator
        - 元素不存在/异常 → 返回 False
        :param wait_time: 等待时间，单位：秒
        :param css: css表达式
        :param iframe: iframe
        :return:
        """
        return await self.is_elem_exists_with_wait(wait_time, css, iframe)


from playwright.sync_api import sync_playwright

if __name__ == "__main__":
    with sync_playwright() as p:
        # 启动浏览器并创建Context（对应原WebDriver）
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # 初始化封装类（传入Context）
        operator = PlaywrightWebOperator(context)

        # 调用原有接口（完全无感知切换）
        operator.load_url("https://www.baidu.com")
        operator.refresh()
        elem = operator.get_elem_with_wait_by_xpath(10, '//input[@id="kw"]')
        elem.fill("Playwright")
        operator.quit()
