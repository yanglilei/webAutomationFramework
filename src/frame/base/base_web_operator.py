import threading
from typing import List, Union, Tuple

from joblib import Memory
from selenium.common import NoAlertPresentException
from selenium.webdriver import ActionChains
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

from src.utils.sys_path_utils import SysPathUtils

# ✅ 1. 创建线程本地存储对象（核心：线程数据隔离）
thread_local = threading.local()

# ✅ 2. 封装：为每个线程创建独立的Memory缓存实例
def get_thread_local_memory():
    # 每个线程首次调用时，初始化专属的Memory实例
    if not hasattr(thread_local, "memory"):
        thread_local.memory = Memory(location=SysPathUtils.get_tmp_file_dir(), verbose=0)
    # 返回当前线程的专属缓存实例
    return thread_local.memory

class SeleniumWebOperator:
    local = threading.local()
    thread_local = threading.local()

    def __init__(self, web_browser):
        self.web_browser: WebDriver = web_browser

    def close_window(self, window_handle):
        if not self._is_window_closed(window_handle):
            self.web_browser.switch_to.window(window_handle)
            self.web_browser.close()

    def close_latest_window(self):
        self.close_window(self.web_browser.window_handles[-1])

    def get_windows(self):
        return self.web_browser.window_handles

    def get_latest_window(self):
        return self.web_browser.window_handles[-1]

    def _is_window_closed(self, window_handle):
        return window_handle not in self.web_browser.window_handles if self.web_browser.bidi_connection is not None else False

    def refresh(self):
        self.web_browser.refresh()

    def get_action_chains(self):
        return ActionChains(self.web_browser)

    def cookie_to_str(self):
        cookies: List[dict] = self.web_browser.get_cookies()
        items = []
        if cookies is not None and len(cookies) > 0:
            for cookie in cookies:
                items.append("%s=%s;" % (cookie["name"], cookie["value"]))
        return "".join(items)[0:-1] if len(items) > 0 else ""

    def user_agent(self):
        return self.web_browser.execute_script("return navigator.userAgent")

    def close_other_windows(self, cur_window_handle):
        for window_handle in self.web_browser.window_handles:
            if window_handle != cur_window_handle:
                self.close_window(window_handle)
        self.web_browser.switch_to.window(cur_window_handle)

    def switch_to_window_by_url_key_2(self, value):
        # ✅ 3. 获取当前线程的专属Memory实例，实现缓存隔离
        memory = get_thread_local_memory()
        # 用线程专属的memory装饰/调用方法
        @memory.cache
        def _switch_to_window_by_url_key(value):
            for window_handle in self.web_browser.window_handles:
                self.web_browser.switch_to.window(window_handle)
                if value in self.web_browser.current_url:
                    return window_handle
            else:
                raise ValueError("未找到包含【%s】的窗口" % value)

        window_handler = _switch_to_window_by_url_key(value)
        if self.web_browser.current_window_handle != window_handler:
            self.web_browser.switch_to.window(window_handler)

    def switch_to_window_by_url_key(self, value):
        # TODO pause by zcy 20260101 00:58 待完全测试！
        def _switch_to_window_by_url_key(value):
            for window_handle in self.web_browser.window_handles:
                self.web_browser.switch_to.window(window_handle)
                if value in self.web_browser.current_url:
                    return window_handle
            else:
                raise ValueError("未找到包含【%s】的窗口" % value)

        if hasattr(self.thread_local, value):
            window_handler = self.thread_local.value
        else:
            window_handler = _switch_to_window_by_url_key(value)
            self.thread_local.value = window_handler

        if self.web_browser.current_window_handle != window_handler:
            self.web_browser.switch_to.window(window_handler)

    def switch_to_window(self, window_handle):
        self.web_browser.switch_to.window(window_handle)

    def switch_to_latest_window(self):
        self.web_browser.switch_to.window(self.web_browser.window_handles[-1])

    def switch_to_frame(self, frame_reference: str | int | WebElement):
        self.web_browser.switch_to.frame(frame_reference)

    def switch_to_default_content(self):
        self.web_browser.switch_to.default_content()

    def go_back(self):
        self.web_browser.back()

    def open_in_new_window(self, url):
        cmd = '''window.open("%s","_blank");''' % url
        self.web_browser.execute_script(cmd)

    def quit(self):
        self.web_browser.quit()

    def execute_js(self, js_str: str, *args):
        return self.web_browser.execute_script(js_str, *args)

    def load_url(self, url):
        self.web_browser.get(url)

    def open_blank_tab(self):
        self.web_browser.execute_script("window.open('about:blank');")

    def format_video_time(self, time: str):
        # 格式化时间为：HH:MM:SS
        ret = time
        if len(time) < 5:
            ret = "00:" + time.rjust(5, "0")
        elif len(time) < 6:
            ret = "00:" + time
        elif len(time) < 8:
            ret = time.rjust(8, "0")
        return ret

    def get_current_url(self, window_handle):
        ret = ""
        if self.web_browser is not None and window_handle in self.web_browser.window_handles:
            self.web_browser.switch_to.window(window_handle)
            ret = self.web_browser.current_url
        return ret

    def play_video(self, video_css: str):
        self.execute_js("""
            let video = document.querySelector(arguments[0]);
            if (video != null && !video.muted) {
                video.muted = true;
            }
            if (video != null && video.paused) {
                video.play();
            }
            """, video_css)

    def get_elem_with_wait(self, wait_time, locator, visible=True) -> WebElement:
        """
        延迟获取元素
        :param wait_time:等待时间
        :param xpath:元素的xpath表达式
        :return:页面元素
        """
        ret = None
        if visible:
            try:
                ret = WebDriverWait(self.web_browser, wait_time).until(EC.visibility_of_element_located(locator))
            except:
                pass
        else:
            try:
                ret = WebDriverWait(self.web_browser, wait_time).until(EC.presence_of_element_located(locator))
            except:
                pass
        return ret

    def get_elem_with_wait_by_xpath(self, wait_time, xpath, visible=True) -> WebElement:
        """
        延迟获取元素
        :param wait_time:等待时间
        :param xpath:元素的xpath表达式
        :return:页面元素
        """
        return self.get_elem_with_wait(wait_time, (By.XPATH, xpath), visible)

    def get_elem_with_wait_by_css(self, wait_time, css, visible=True) -> WebElement:
        """
        延迟获取元素
        :param wait_time:等待时间
        :param css:元素的css表达式
        :return:页面元素
        """
        return self.get_elem_with_wait(wait_time, (By.CSS_SELECTOR, css), visible)

    def get_elems(self, locator) -> List[WebElement]:
        """
        获取元素
        :param xpath:元素的xpath表达式
        :return:页面元素
        """
        ret = []
        try:
            ret = self.web_browser.find_elements(*locator)
        except:
            pass
        return ret

    def get_elems_by_xpath(self, xpath) -> List[WebElement]:
        """
        获取元素
        :param xpath:元素的xpath表达式
        :return:页面元素
        """
        return self.get_elems((By.XPATH, xpath))

    def get_elems_by_css(self, css) -> List[WebElement]:
        """
        获取元素
        :param css:元素的css表达式
        :return:页面元素
        """
        return self.get_elems((By.CSS_SELECTOR, css))

    def get_elems_with_wait(self, wait_secs, locator, visible=True) -> List[WebElement]:
        ret = []
        if visible:
            try:
                ret = WebDriverWait(self.web_browser, wait_secs).until(EC.visibility_of_all_elements_located(locator))
            except:
                pass
        else:
            try:
                ret = WebDriverWait(self.web_browser, wait_secs).until(EC.presence_of_all_elements_located(locator))
            except:
                pass
        return ret

    def get_elems_with_wait_by_xpath(self, wait_secs, xpath, visible=True) -> List[WebElement]:
        """
        延迟获取元素
        :param wait_time:等待时间
        :param xpath:元素的xpath表达式
        :return:页面元素
        """
        return self.get_elems_with_wait(wait_secs, (By.XPATH, xpath), visible)

    def get_elems_with_wait_by_css(self, wait_secs, css, visible=True) -> List[WebElement]:
        """
        延迟获取元素
        :param wait_time:等待时间
        :param css:元素的css表达式
        :return:页面元素
        """
        return self.get_elems_with_wait(wait_secs, (By.CSS_SELECTOR, css), visible)

    def get_elem(self, locator) -> WebElement:
        """
        获取元素
        :param xpath:元素的xpath表达式
        :return:页面元素
        """
        ret = None
        try:
            ret = self.web_browser.find_element(*locator)
        except:
            pass
        return ret

    def get_elem_by_xpath(self, xpath) -> WebElement:
        """
        获取元素
        :param xpath:元素的xpath表达式
        :return:页面元素
        """
        return self.get_elem((By.XPATH, xpath))

    def get_elem_by_css(self, css) -> WebElement:
        """
        获取元素
        :param css:元素的css表达式
        :return:页面元素
        """
        return self.get_elem((By.CSS_SELECTOR, css))

    def get_relative_elem(self, elem: WebElement, locator) -> WebElement:
        ret = None
        try:
            ret = elem.find_element(*locator)
        except:
            pass
        return ret

    def get_relative_elem_by_xpath(self, elem: WebElement, xpath) -> WebElement:
        return self.get_relative_elem(elem, (By.XPATH, xpath))

    def get_relative_elem_by_css(self, elem: WebElement, css) -> WebElement:
        return self.get_relative_elem(elem, (By.CSS_SELECTOR, css))

    def get_relative_elems(self, elem: WebElement, locator) -> List[WebElement]:
        ret = None
        try:
            ret = elem.find_elements(*locator)
        except:
            pass
        return ret

    def get_relative_elems_by_xpath(self, elem: WebElement, xpath) -> List[WebElement]:
        return self.get_relative_elems(elem, (By.XPATH, xpath))

    def get_relative_elems_by_css(self, elem: WebElement, css) -> List[WebElement]:
        return self.get_relative_elems(elem, (By.CSS_SELECTOR, css))

    def is_elem_visible(self, locator) -> Union[WebElement, bool]:
        ret = False
        try:
            ret = EC.visibility_of_element_located(locator)(self.web_browser)
        except:
            ret = False
        return ret

    def is_elem_visible_by_xpath(self, xpath):
        return self.is_elem_visible((By.XPATH, xpath))

    def is_elem_visible_by_css(self, css):
        return self.is_elem_exists((By.CSS_SELECTOR, css))

    def is_elem_exists(self, locator):
        ret = False
        try:
            ret = EC.presence_of_element_located(locator)(self.web_browser)
        except:
            ret = False
        return ret

    def is_elem_exists_by_xpath(self, xpath):
        return self.is_elem_exists((By.XPATH, xpath))

    def is_elem_exists_by_css(self, css):
        return self.is_elem_exists((By.CSS_SELECTOR, css))

    def wait_for_disappeared(self, wait_time, locator: WebElement | Tuple[str, str]):
        try:
            WebDriverWait(self.web_browser, wait_time).until(EC.invisibility_of_element(locator))
        except:
            pass

    def wait_for_disappeared_by_xpath(self, wait_time, xpath):
        self.wait_for_disappeared(wait_time, (By.XPATH, xpath))

    def wait_for_disappeared_by_css(self, wait_time, css):
        self.wait_for_disappeared(wait_time, (By.CSS_SELECTOR, css))

    def get_alert(self, wait_time):
        ret = None
        try:
            ret = WebDriverWait(self.web_browser, wait_time).until(EC.alert_is_present())
        except:
            pass

        return ret

    def is_alert_present(self):
        try:
            return self.web_browser.switch_to.alert
        except NoAlertPresentException:
            return False

    def confirm_alert(self):
        return self.web_browser.switch_to.alert.accept()

    def wait_for_visible(self, wait_time, locator: WebElement | Tuple) -> Union[WebElement, bool]:
        ret = None
        if isinstance(locator, WebElement):
            try:
                ret = WebDriverWait(self.web_browser, wait_time).until(EC.visibility_of(locator))
            except:
                pass
        else:
            try:
                ret = WebDriverWait(self.web_browser, wait_time).until(EC.visibility_of_element_located(locator))
            except:
                pass
        return ret

    def wait_for_visible_by_xpath(self, wait_time, xpath):
        return self.wait_for_visible(wait_time, (By.XPATH, xpath))

    def wait_for_visible_by_css(self, wait_time, css):
        return self.wait_for_visible(wait_time, (By.CSS_SELECTOR, css))

    def is_elem_exists_with_wait(self, wait_time, locator):
        ret = False
        try:
            ret = WebDriverWait(self.web_browser, wait_time).until(EC.presence_of_element_located(locator))
        except:
            ret = False
        return ret

    def is_elem_exists_with_wait_by_xpath(self, wait_time, xpath):
        return self.is_elem_exists_with_wait(wait_time, (By.XPATH, xpath))

    def is_elem_exists_with_wait_by_css(self, wait_time, css):
        return self.is_elem_exists_with_wait(wait_time, (By.CSS_SELECTOR, css))
