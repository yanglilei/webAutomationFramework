import time
from pathlib import Path
from typing import List, Optional, Any

from DrissionPage import Chromium
from DrissionPage._elements.chromium_element import ChromiumElement
from DrissionPage._pages.chromium_frame import ChromiumFrame
from DrissionPage._pages.mix_tab import MixTab

from src.frame.common.qt_log_redirector import LOG


class DrissionPageWebOperator:
    """基于DrissionPage重构的Web操作类（完全兼容原PlaywrightWebOperator接口）"""

    def __init__(self, web_browser: Chromium):
        """
        初始化方法（替换为DrissionPage的Chromium对象）
        :param web_browser: DrissionPage的Chromium对象（管理多个标签页/窗口）
        """
        self.browser: Chromium = web_browser
        # 记录当前活跃标签页（对应Playwright的current_page）
        self._current_tab: MixTab = self.browser.get_tabs()[0] if self.browser.tabs_count > 0 else None
        # 记录当前frame（用于frame切换）
        self._current_frame: Optional[ChromiumFrame] = None

    def get_current_page(self) -> MixTab:
        """辅助方法：获取当前活跃标签页，确保不为None"""
        if not self._current_tab or self._current_tab not in self.browser.get_tabs():
            self._current_tab = self.browser.get_tabs()[0] if self.browser.tabs_count > 0 else None
        return self._current_tab

    def wait_doc_loaded(self, timeout: float = 10.0):
        self.get_current_page().wait.doc_loaded(float(timeout))

    def close_window(self, tab: MixTab):
        """关闭指定标签页（窗口）"""
        if not self._is_window_closed(tab):
            self._current_tab = tab
            tab.close()

    def close_latest_window(self):
        """关闭最新打开的标签页"""
        self.close_window(self.get_latest_window())

    def get_windows(self) -> List[MixTab]:
        """返回所有未关闭的标签页（对应Playwright的pages）"""
        # return [tab for tab in self.page.get_tabs() if not tab.closed]
        return self.browser.get_tabs()

    def get_latest_window(self) -> Optional[MixTab]:
        """获取最新打开的标签页"""
        return self.browser.latest_tab

    def _is_window_closed(self, window_handle: MixTab) -> bool:
        """判断标签页是否已关闭"""
        return window_handle not in self.browser.get_tabs()

    def refresh(self):
        """刷新当前标签页"""
        page = self.get_current_page()
        page.refresh()

    def cookie_to_str(self, page: MixTab = None) -> str:
        """将Cookie转换为字符串格式"""
        return self.browser.cookies(True).as_str()

    def get_cookies(self, tab: MixTab = None) -> list[dict]:
        """
        获取指定标签页的Cookie，若未传page则获取浏览器所有Cookie
        :param tab: DrissionPage的MixTab实例
        :return: Cookie列表
        """
        try:
            if tab:
                # 检查页面是否已导航
                if not tab.url or tab.url == "about:blank":
                    print(f"警告：页面未导航，无法获取对应域名的Cookie！")
                    return []
                # 获取指定页面的Cookie
                return tab.cookies(all_domains=False)
            else:
                # 获取浏览器所有Cookie
                return self.browser.cookies(all_info=True)
        except Exception as e:
            print(f"获取Cookie失败：{str(e)}")
            return []

    def user_agent(self) -> str:
        """获取当前页面的User-Agent"""
        return self.get_current_page().user_agent

    def close_other_windows(self, cur_window_handle: MixTab):
        """关闭除当前标签页外的所有标签页"""
        if self._is_window_closed(cur_window_handle):
            return
        for window_handle in self.get_windows():
            if window_handle != cur_window_handle:
                self.close_window(window_handle)
        # 切换到当前窗口并置顶
        self._current_tab = cur_window_handle
        # cur_window_handle.bring_to_front()

    def switch_to_window_by_url_key(self, value: str):
        """根据URL关键字切换标签页"""
        tabs = self.browser.get_tabs(url=value)
        if tabs:
            self.switch_to_window(tabs[0])

    def get_windows_by_url_key(self, value: str) -> List[MixTab]:
        """根据URL关键字获取标签页"""
        return self.browser.get_tabs(url=value)

    def switch_to_window(self, tab: MixTab):
        """切换到指定标签页"""
        if self._is_window_closed(tab):
            return
        self._current_tab = tab

    def switch_to_latest_window(self):
        """切换到最新打开的标签页"""
        latest_window = self.get_latest_window()
        self.switch_to_window(latest_window)

    def switch_to_frame(self, frame_reference: str|int|tuple|ChromiumFrame|ChromiumElement, locator: Optional[MixTab | ChromiumFrame] = None) -> Optional[
        ChromiumFrame]:
        """
        切换到指定iframe（兼容原Playwright的frame_locator逻辑）
        :param frame_reference: 定位表达式（xpath/css/id/name）xpath表达式必须符合drissionpage格式的，以xpath=或者xpath:开头
        :param locator: 父元素/frame，不传默认在当前页面查找
        :return: DrissionPage的Frame对象
        """
        current_page = self.get_current_page()
        # 解析定位表达式（兼容Playwright的xpath/css格式）
        frame = locator.get_frame(frame_reference) if locator else current_page.get_frame(frame_reference)
        if not frame:
            return None
        self._current_frame = frame
        return self._current_frame

    def go_back(self):
        """返回上一页"""
        page = self.get_current_page()
        page.back()

    def open_in_new_window(self, url: str, timeout=10):
        """
        新建标签页并打开URL
        :param url: url
        :param timeout: 加载超时时间
        :return:
        """
        new_page = self.browser.new_tab()
        # 获取元素默认不等待
        # new_page.set.timeouts(0)
        new_page.get(url)
        self._current_tab = new_page

    def quit(self):
        """关闭浏览器"""
        self.browser.quit(force=True)

    def load_url(self, url: str, timeout=10):
        """
        加载指定URL
        :param url: 目标URL
        :param timeout: 超时时间
        :param params: url中的参数
        """
        page = self.get_current_page()
        page.get(url, timeout=float(timeout))

    def execute_js(self, js_str: str, *arg, locator: Optional[MixTab | ChromiumFrame] = None) -> Any:
        """
        执行JS代码
        :param js_str: JS代码字符串
        :param arg: 传入JS的参数
        :param locator: 元素定位器，不传默认为当前页面
        :return: JS执行结果
        """
        if not locator:
            locator = self.get_current_page()
        # DrissionPage的run_js支持参数传入
        return locator.run_js(js_str, *arg)

    def js_click(self, locator: Optional[ChromiumElement]):
        """通过JS点击元素"""
        # self.execute_js("arguments[0].click();", locator)
        locator.click(by_js=True)

    def open_blank_tab(self):
        """打开空白标签页"""
        new_page = self.browser.new_tab()
        new_page.get("about:blank")
        self._current_tab = new_page

    def format_video_time(self, time: str) -> str:
        """格式化视频时间（纯字符串处理，逻辑不变）"""
        ret = time
        if len(time) < 5:
            ret = "00:" + time.rjust(5, "0")
        elif len(time) < 6:
            ret = "00:" + time
        elif len(time) < 8:
            ret = time.rjust(8, "0")
        return ret

    def screenshot(self, path: Optional[str | Path] = None, element: Optional[ChromiumElement] = None,
                   as_bytes=False) -> str | bytes:
        """
        截图
        :param path: 图片保存路径
        :param element: 元素定位器，不传则截取整页
        :param as_bytes: 保存成字节码。设置为True则返回png格式图片的字节码，path参数无效
        :return: 图片完整路径或字节码
        """
        if not element:
            page = self.get_current_page()
            return page.get_screenshot(path=path, as_bytes='png', full_page=True)
        else:
            return element.get_screenshot(path=path, as_bytes='png')

    def get_current_url(self, page: MixTab = None) -> str:
        """获取当前页面URL"""
        ret = ""
        if not page:
            page = self.get_current_page()

        if not self._is_window_closed(page):
            ret = page.url
        return ret

    def play_video(self, video_css: str, locator: ChromiumElement = None):
        """播放视频（静音播放）"""
        if not locator:
            locator = self.get_current_page()
        # 执行JS播放视频（逻辑与Playwright版本一致）
        locator.run_js("""
            let video = document.querySelector(css_expr);
            if (video != null && !video.muted) {
                video.muted = true;
            }
            if (video != null && video.paused) {
                video.play();
            }
        """, video_css)

    def get_elem_with_wait(self, wait_time: float, locator: str, visible: bool = True,
                           iframe: Optional[ChromiumFrame] = None) -> Optional[ChromiumElement|ChromiumFrame]:
        """
        延迟获取元素
        :param wait_time: 等待时间（秒）
        :param locator: 定位表达式（兼容Playwright格式）
        :param visible: 是否等待可见
        :param iframe: frame对象，不传默认在当前页面查找
        :return: DrissionPage的ChromiumElement对象
        """
        page = self.get_current_page() if not iframe else iframe
        ret = None
        try:
            if visible:
                # 等待元素可见
                if page.wait.ele_displayed(locator, timeout=float(wait_time)):
                    ret = page.ele(locator)
            else:
                ret = page.ele(locator, timeout=float(wait_time))
        except Exception:
            pass
        return ret

    def get_elem_with_wait_by_xpath(self, wait_time: float, xpath: str, visible: bool = True,
                                    iframe: Optional[ChromiumFrame] = None) -> Optional[ChromiumElement|ChromiumFrame]:
        """通过XPath延迟获取元素"""
        return self.get_elem_with_wait(wait_time, f"xpath={xpath}", visible, iframe)

    def get_elem_with_wait_by_css(self, wait_time: float, css: str, visible: bool = True,
                                  iframe: Optional[ChromiumFrame] = None) -> Optional[ChromiumElement|ChromiumFrame]:
        """通过CSS延迟获取元素"""
        return self.get_elem_with_wait(wait_time, f"css={css}", visible, iframe)

    def get_elems(self, locator: str, iframe: Optional[ChromiumFrame] = None) -> list:
        """获取多个元素"""
        page = self.get_current_page() if not iframe else iframe
        return page.eles(locator, timeout=0)

    def get_elems_by_xpath(self, xpath: str, iframe: Optional[ChromiumFrame] = None) -> list:
        """通过XPath获取多个元素"""
        return self.get_elems(f"xpath={xpath}", iframe)

    def get_elems_by_css(self, css: str, iframe: Optional[ChromiumFrame] = None) -> list:
        """通过CSS获取多个元素"""
        return self.get_elems(f"css={css}", iframe)

    def get_elems_with_wait(self, wait_time: float, locator: str, visible: bool = True,
                            iframe: Optional[ChromiumFrame] = None) -> list:
        """延迟获取多个元素"""
        page = self.get_current_page() if not iframe else iframe
        ret = []
        try:
            if visible:
                def _predicate():
                    elems = page.eles(locator, timeout=0)
                    for elem in elems:
                        if not elem.states.is_displayed:
                            return False
                    return elems

                # 等待所有元素可见
                end_time = time.monotonic() + wait_time
                while True:
                    elements = _predicate()
                    if elements:
                        break
                    time.sleep(0.3)
                    if time.monotonic() > end_time:
                        break

                ret = [] if not elements else elements
            else:
                ret = page.eles(locator, timeout=float(wait_time))
        except Exception:
            pass
        return ret

    def get_elems_with_wait_by_xpath(self, wait_secs: int, xpath: str, visible: bool = True,
                                     iframe: Optional[ChromiumFrame] = None) -> list:
        """通过XPath延迟获取多个元素"""
        return self.get_elems_with_wait(wait_secs, f"xpath={xpath}", visible, iframe)

    def get_elems_with_wait_by_css(self, wait_secs: int, css: str, visible: bool = True,
                                   iframe: Optional[ChromiumFrame] = None) -> list:
        """通过CSS延迟获取多个元素"""
        return self.get_elems_with_wait(wait_secs, f"css={css}", visible, iframe)

    def get_elem(self, locator: str, iframe: Optional[ChromiumFrame] = None) -> Optional[ChromiumElement]:
        """获取单个元素"""
        page = self.get_current_page() if not iframe else iframe
        ret: Optional[ChromiumElement] = None
        try:
            ret = page.ele(locator, timeout=0)
        except Exception as e:
            LOG.exception("获取元素未找到：")
            pass
        return ret if ret else None

    def get_elem_by_xpath(self, xpath: str, iframe: Optional[ChromiumFrame] = None) -> Optional[ChromiumElement]:
        """通过XPath获取单个元素"""
        return self.get_elem(f"xpath={xpath}", iframe)

    def get_elem_by_css(self, css: str) -> Optional[ChromiumElement]:
        """通过CSS获取单个元素"""
        return self.get_elem(f"css={css}")

    def get_relative_elem(self, elem: ChromiumFrame | ChromiumElement, locator: str) -> Optional[ChromiumElement]:
        """获取相对元素（基于已有元素查找）"""
        ret: Optional[ChromiumElement] = None
        try:
            ret = elem.ele(locator, timeout=0)
        except Exception:
            pass
        return ret

    def get_relative_elem_by_xpath(self, elem: ChromiumElement, xpath: str) -> Optional[ChromiumElement]:
        """通过XPath获取相对元素"""
        return self.get_relative_elem(elem, f"xpath={xpath}")

    def get_relative_elem_by_css(self, elem: ChromiumElement, css: str) -> Optional[ChromiumElement]:
        """通过CSS获取相对元素"""
        return self.get_relative_elem(elem, f"css={css}")

    def get_relative_elems(self, elem: ChromiumElement, locator: str) -> list:
        """获取多个相对元素"""
        ret = []
        try:
            ret = elem.eles(locator, timeout=0)
        except Exception:
            pass
        return ret

    def get_relative_elems_by_xpath(self, elem: ChromiumElement, xpath: str) -> list:
        """通过XPath获取多个相对元素"""
        return self.get_relative_elems(elem, f"xpath={xpath}")

    def get_relative_elems_by_css(self, elem: ChromiumElement, css: str) -> list:
        """通过CSS获取多个相对元素"""
        return self.get_relative_elems(elem, f"css={css}")

    def is_elem_visible(self, locator: ChromiumFrame | ChromiumElement | str,
                        iframe: ChromiumFrame = None) -> ChromiumElement | ChromiumFrame | bool:
        """
        判断元素是否可见
        支持进入iframe获取判断元素
        返回：False（不可见） 或 元素（可见）
        :param locator: 定位元素
        :param iframe: iframe
        :return:
        """
        page = self.get_current_page() if not iframe else iframe
        try:
            elem = page.ele(locator, timeout=0)
            ret = elem if elem.states.is_displayed else False
        except Exception:
            ret = False
        return ret

    def is_elem_visible_by_xpath(self, xpath: str,
                                 iframe: Optional[ChromiumFrame] = None) -> ChromiumFrame | ChromiumElement | bool:
        """通过XPath判断元素是否可见"""
        return self.is_elem_visible(f"xpath={xpath}", iframe)

    def is_elem_visible_by_css(self, css: str) -> ChromiumFrame | ChromiumElement | bool:
        """通过CSS判断元素是否可见"""
        return self.is_elem_visible(f"css={css}")

    def is_elem_exists(self, locator: str):
        """
        判断元素是否存在
        :param locator: 定位表达式
        :return: False（不存在）或者 元素（存在）
        """
        try:
            elem = self.get_current_page().ele(locator, timeout=0)
            ret = elem if elem.states.is_displayed else False
        except Exception:
            ret = False
        return ret

    def is_elem_exists_by_xpath(self, xpath: str) -> ChromiumFrame | ChromiumElement | bool:
        """通过XPath判断元素是否存在"""
        return self.is_elem_exists(f"xpath={xpath}")

    def is_elem_exists_by_css(self, css: str) -> ChromiumFrame | ChromiumElement | bool:
        """通过CSS判断元素是否存在"""
        return self.is_elem_exists(f"css={css}")

    def wait_for_disappeared(self, wait_time: float, locator: str | ChromiumElement | ChromiumFrame):
        """等待元素消失"""
        try:
            self.get_current_page().wait.ele_hidden(locator, timeout=float(wait_time))
        except Exception as e:
            pass

    def wait_for_disappeared_by_xpath(self, wait_time: float, xpath: str):
        """通过XPath等待元素消失"""
        self.wait_for_disappeared(wait_time, f"xpath={xpath}")

    def wait_for_disappeared_by_css(self, wait_time: float, css: str):
        """通过CSS等待元素消失"""
        self.wait_for_disappeared(wait_time, f"css={css}")

    def is_alert_present(self) -> bool:
        """判断是否有提示框"""
        return self.get_current_page().states.has_alert

    def confirm_alert(self):
        """确认提示框"""
        self.get_current_page().handle_alert(True)

    def get_alert_content(self):
        """获取提示框的提示内容"""
        self.get_current_page().handle_alert(None, None)

    def send_alert_msg(self, msg: str):
        """
        处理prompt提示框，发送提示框消息，并确认
        :param msg: 消息
        :return:
        """
        self.get_current_page().handle_alert(True, msg)

    def wait_for_visible(self, wait_time: float,
                         locator: ChromiumElement | ChromiumFrame | str) -> ChromiumElement | ChromiumFrame | bool:
        """等待元素可见"""
        try:
            ret = self.get_current_page().wait.ele_displayed(locator, timeout=float(wait_time))
        except Exception:
            ret = False
        return ret

    def wait_for_visible_by_xpath(self, wait_time: float, xpath: str) -> ChromiumElement | bool:
        """通过XPath等待元素可见"""
        return self.wait_for_visible(wait_time, f"xpath={xpath}")

    def wait_for_visible_by_css(self, wait_time: float, css: str) -> ChromiumElement | bool:
        """通过CSS等待元素可见"""
        return self.wait_for_visible(wait_time, f"css={css}")

    def is_elem_exists_with_wait(self, wait_time: float, locator: str) -> ChromiumElement | bool:
        """等待元素存在"""
        page = self.get_current_page()
        ret = False
        try:
            ret = page.ele(locator, timeout=float(wait_time))
        except Exception:
            ret = False
        return ret

    def is_elem_exists_with_wait_by_xpath(self, wait_time: float, xpath: str) -> ChromiumElement | bool:
        """通过XPath等待元素存在"""
        return self.is_elem_exists_with_wait(wait_time, f"xpath={xpath}")

    def is_elem_exists_with_wait_by_css(self, wait_time: float, css: str) -> ChromiumElement | bool:
        """通过CSS等待元素存在"""
        return self.is_elem_exists_with_wait(wait_time, f"css={css}")


if __name__ == "__main__":
    # 启动DrissionPage浏览器（替代原Playwright）
    from DrissionPage import Chromium

    # 初始化浏览器
    browser = Chromium()
    # 初始化封装类（传入Chromium对象）
    operator = DrissionPageWebOperator(browser)

    # 调用原有接口（完全无感知切换）
    operator.load_url("https://www.baidu.com")
    operator.refresh()
    elem = operator.get_elem_with_wait_by_xpath(10, '//input[@id="kw"]')
    elem.input("DrissionPage")  # 替代Playwright的fill方法

    operator.quit()
