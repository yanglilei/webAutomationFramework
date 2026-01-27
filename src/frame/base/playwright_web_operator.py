from pathlib import Path
from typing import List, Union, Literal, Optional

from playwright.async_api import Page, BrowserContext, Dialog, Locator, FrameLocator, Frame
from playwright.async_api import TimeoutError as PlaywrightTimeoutError


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
        """辅助方法：获取当前活跃页面，确保不为None"""
        if not self._current_page or self._current_page.is_closed():
            self._current_page = self.context.pages[0] if self.context.pages else None
        # if not self._current_page:
        #     raise RuntimeError("无可用的页面/窗口")
        return self._current_page

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
        if not self._is_window_closed(page):
            self._current_page = page
            await page.close()

    async def close_latest_window(self):
        await self.close_window(self.get_latest_window())

    def get_windows(self):
        # 返回所有未关闭的Page（对应Selenium的window_handles）
        return [page for page in self.context.pages if not page.is_closed()]

    def get_latest_window(self):
        windows = self.get_windows()
        return None if not windows else windows[-1]

    def _is_window_closed(self, window_handle: Page):
        # 判断Page是否已关闭
        return window_handle not in self.context.pages or window_handle.is_closed()

    async def refresh(self):
        page = self.get_current_page()
        await page.reload()

    async def cookie_to_str(self, page=None):
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
        page = self.get_current_page()
        return await page.evaluate("navigator.userAgent")

    async def close_other_windows(self, cur_window_handle):
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

    async def switch_to_window(self, page):
        if await self._is_window_closed(page):
            return
            # raise ValueError("窗口已关闭")
        self._current_page = page
        await page.bring_to_front()

    async def switch_to_latest_window(self):
        latest_window = self.get_latest_window()
        await self.switch_to_window(latest_window)

    def switch_to_frame(self, frame_reference: str, locator: Locator | FrameLocator = None) -> FrameLocator:
        """
        获取iframe
        返回FrameLocator实例
        :param frame_reference: 符合playwright规则的定位表达式
        :param locator: Locator or FrameLocator实例，不传默认在page下查找，否则在该Locator下查找
        :return:
        """
        # FrameLocator 是惰性求值的 iframe 定位器，创建后可直接定位 iframe 内部元素，无需 “显式进入 / 退出”，逻辑最简洁，适配动态加载的 iframe。
        if not locator:
            current_page = self.get_current_page()
            frame = current_page.frame_locator(frame_reference).first
        else:
            frame = locator.frame_locator(frame_reference).first
        self._current_frame = frame
        return self._current_frame

    # async def get_frame(self, iframe_name: str=None, iframe_url: str=None) -> Frame:
    #     current_page = self.get_current_page()
    #     frame = current_page.frame(name=iframe_name, url=iframe_url)
    #     return frame

    # async def switch_to_default_content(self):
    #     # 回到主frame
    #     self._current_frame = None
    #     self._get_current_page().main_frame

    async def go_back(self):
        page = self.get_current_page()
        await page.go_back()

    async def open_in_new_window(self, url):
        # 新建Page（窗口）并打开URL
        new_page = await self.context.new_page()
        await new_page.goto(url)
        self._current_page = new_page

    async def quit(self):
        # 关闭上下文和浏览器
        await self.context.close()
        await self.context.browser.close()

    async def load_url(self, url, wait_until: Literal["commit", "domcontentloaded", "load", "networkidle"] = "load"):
        page = self.get_current_page()
        await page.goto(url, wait_until=wait_until)

    async def execute_js(self, js_str: str, arg=None, locator: Optional[Locator]=None):
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
        await locator.evaluate("elem => elem.click();")
        # await self.execute_js("elem => elem.click();", locator=locator)

    async def open_blank_tab(self):
        new_page = await self.context.new_page()
        await new_page.goto("about:blank")
        self._current_page = new_page

    async def format_video_time(self, time: str):
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
        if not element:
            page = self.get_current_page()
            return await page.screenshot(path=path, full_page=True)
        else:
            return await element.screenshot(path=path)

    async def get_current_url(self, page=None):
        ret = ""
        if not page:
            page = self.get_current_page()

        if not await self._is_window_closed(page):
            ret = page.url
        return ret

    async def play_video(self, video_css: str, locator: Locator = None):
        if not locator:
            locator = self.get_current_page()
        await locator.evaluate(""" (css_expr) => {
            let video = document.querySelector(css_expr);
            if (video != null && !video.muted) {
                video.muted = true;
            }
            if (video != null && video.paused) {
                video.play();
            }}
            """, video_css)

    async def get_elem_with_wait(self, wait_time, locator, visible=True,
                                 iframe: Locator | FrameLocator = None) -> Locator:
        """
        延迟获取元素
        :param wait_time:等待时间
        :param locator: 符合playwright的locator格式
        :param visible: True-等待可见，False-等待存在
        :param iframe: Locator or FrameLocator实例，不传默认在page下查找，否则在该Locator下查找
        :return: Playwright Locator对象（兼容原WebElement）
        """
        page = self.get_current_page()
        try:
            if not iframe:
                ret = page.locator(locator)  # 先创建Locator（惰性，不立即查DOM）
            else:
                ret = iframe.locator(locator)
            # 等待该Locator对应的元素可见，超时时间和原代码一致
            await ret.wait_for(state="visible" if visible else "attached", timeout=wait_time * 1000)
        except Exception:
            ret = None
        return ret

    async def get_elem_with_wait_by_xpath(self, wait_time, xpath, visible=True, iframe:Optional[FrameLocator]=None) -> Locator:
        return await self.get_elem_with_wait(wait_time, f"xpath={xpath}", visible, iframe)

    async def get_elem_with_wait_by_css(self, wait_time, css, visible=True, iframe:Optional[FrameLocator]=None) -> Locator:
        return await self.get_elem_with_wait(wait_time, css, visible, iframe)

    async def get_elems(self, locator, iframe=None) -> List[Locator]:
        page = self.get_current_page()
        ret: List[Locator] = []
        try:
            # by, selector = locator
            # pw_selector = self._convert_by_to_selector(by, selector)
            if not iframe:
                ret = await page.locator(locator).all()
            else:
                ret = await iframe.locator(locator).all()
        except Exception:
            pass
        return ret

    async def get_elems_by_xpath(self, xpath, iframe=None) -> List[Locator]:
        return await self.get_elems(f"xpath={xpath}", iframe)

    async def get_elems_by_css(self, css, iframe=None) -> List[Locator]:
        return await self.get_elems(css, iframe)

    async def get_elems_with_wait(self, wait_secs, locator, visible=True, iframe=None) -> List[Locator]:
        page = self.get_current_page()
        ret: List[Locator] = []
        # by, selector = locator
        # pw_selector = self._convert_by_to_selector(by, selector)
        timeout = wait_secs * 1000
        try:
            if not iframe:
                await page.wait_for_selector(locator, state="visible" if visible else "attached", timeout=timeout)
            else:
                await iframe.wait_for_selector(locator, state="visible" if visible else "attached", timeout=timeout)
            ret = await page.locator(locator).all()
        except PlaywrightTimeoutError:
            pass
        return ret

    async def get_elems_with_wait_by_xpath(self, wait_secs, xpath, visible=True, iframe=None) -> List[Locator]:
        return await self.get_elems_with_wait(wait_secs, f"xpath={xpath}", visible, iframe)

    async def get_elems_with_wait_by_css(self, wait_secs, css, visible=True, iframe=None) -> List[Locator]:
        return await self.get_elems_with_wait(wait_secs, css, visible, iframe)

    def get_elem(self, locator, iframe=None) -> Locator:
        page = self.get_current_page()
        ret: Optional[Locator] = None
        try:
            if not iframe:
                ret = page.locator(locator)
            else:
                ret = iframe.locator(locator)
        except Exception:
            pass
        return ret

    def get_elem_by_xpath(self, xpath, iframe=None) -> Locator:
        return self.get_elem(f"xpath={xpath}", iframe)

    def get_elem_by_css(self, css) -> Locator:
        return self.get_elem(css)

    def get_relative_elem(self, elem: Locator, locator) -> Locator:
        ret: Optional[Locator] = None
        try:
            ret = elem.locator(locator)
        except Exception:
            pass
        return ret

    def get_relative_elem_by_xpath(self, elem: Locator, xpath) -> Locator:
        return self.get_relative_elem(elem, f"xpath={xpath}")

    def get_relative_elem_by_css(self, elem: Locator, css) -> Locator:
        return self.get_relative_elem(elem, css)

    async def get_relative_elems(self, elem: Locator, locator) -> List[Locator]:
        ret: List[Locator] = []
        try:
            locator = elem.locator(locator)
            ret = await locator.all()
        except Exception:
            pass
        return ret

    async def get_relative_elems_by_xpath(self, elem: Locator, xpath) -> List[Locator]:
        return await self.get_relative_elems(elem, f"xpath={xpath}")

    async def get_relative_elems_by_css(self, elem: Locator, css) -> List[Locator]:
        return await self.get_relative_elems(elem, css)

    async def is_elem_visible(self, locator, iframe=None) -> Union[Locator, bool]:
        page = self.get_current_page()
        ret = False
        try:
            if not iframe:
                ret = await page.locator(locator).is_visible()
            else:
                ret = await iframe.locator(locator).is_visible()
            if ret:
                ret = page.locator(locator)
        except Exception:
            ret = False
        return ret

    async def is_elem_visible_by_xpath(self, xpath, iframe=None):
        return await self.is_elem_visible(f"xpath={xpath}", iframe)

    async def is_elem_visible_by_css(self, css):
        # 修复原代码笔误（原调用了is_elem_exists）
        return await self.is_elem_visible(css)

    async def is_elem_exists(self, locator):
        page = self.get_current_page()
        ret = False
        try:
            ret = page.locator(locator)
            if await ret.count() == 0:
                ret = False
        except Exception:
            ret = False
        return ret

    async def is_elem_exists_by_xpath(self, xpath):
        return await self.is_elem_exists(f"xpath={xpath}")

    async def is_elem_exists_by_css(self, css):
        return await self.is_elem_exists(css)

    async def wait_for_disappeared(self, wait_time, locator: str | Locator):
        page = self.get_current_page()
        timeout = wait_time * 1000
        try:
            if isinstance(locator, str):
                await page.wait_for_selector(locator, state="hidden", timeout=timeout)
            else:
                await locator.wait_for(state="hidden", timeout=timeout)
        except PlaywrightTimeoutError:
            pass

    async def wait_for_disappeared_by_xpath(self, wait_time, xpath):
        await self.wait_for_disappeared(wait_time, f"xpath={xpath}")

    async def wait_for_disappeared_by_css(self, wait_time, css):
        await self.wait_for_disappeared(wait_time, css)

    async def register_alert_handler(self, handler):
        page = self.get_current_page()
        page.on("dialog", handler)

    async def get_alert(self, wait_time):
        page = self.get_current_page()
        ret: Optional[Dialog] = None
        timeout = wait_time * 1000
        try:
            ret = await page.wait_for_event("dialog", timeout=timeout)
        except PlaywrightTimeoutError:
            pass
        return ret

    async def is_alert_present(self) -> Dialog | bool:
        try:
            page = self.get_current_page()
            return await page.wait_for_event("dialog", timeout=10)
        except PlaywrightTimeoutError:
            return False

    async def confirm_alert(self):
        dialog = await self.get_alert(10)
        if dialog:
            await dialog.accept()

    async def wait_for_visible(self, wait_time, locator: Union[Locator, str]) -> Union[Locator, bool]:
        page = self.get_current_page()
        ret = False
        timeout = wait_time * 1000
        try:
            if isinstance(locator, Locator):
                await locator.wait_for(state="visible", timeout=timeout)
                ret = locator
            else:
                ret = page.locator(locator)
                await ret.wait_for(state="visible", timeout=timeout)
        except PlaywrightTimeoutError:
            ret = False
        return ret

    async def wait_for_visible_by_xpath(self, wait_time, xpath):
        return await self.wait_for_visible(wait_time, f"xpath={xpath}")

    async def wait_for_visible_by_css(self, wait_time, css):
        return await self.wait_for_visible(wait_time, css)

    async def is_elem_exists_with_wait(self, wait_time, locator: str):
        page = self.get_current_page()
        ret = False
        timeout = wait_time * 1000
        try:
            ret = page.locator(locator)
            await ret.wait_for(state="attached", timeout=timeout)
        except PlaywrightTimeoutError:
            ret = False
        return ret

    async def is_elem_exists_with_wait_by_xpath(self, wait_time, xpath):
        return await self.is_elem_exists_with_wait(wait_time, f"xpath={xpath}")

    async def is_elem_exists_with_wait_by_css(self, wait_time, css):
        return await self.is_elem_exists_with_wait(wait_time, css)


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
