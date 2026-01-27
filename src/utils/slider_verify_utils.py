import asyncio
import random
import time

import cv2
import numpy as np
from playwright.async_api import Locator, Mouse


class SliderVerifyUtils:
    """
    滑块验证码操作工具
    """

    @classmethod
    def cal_gap_x_pos(cls, background_img_path: str = "", ) -> int:
        """
        计算背景图片上的缺口距离（相对于最左侧）
        若是实际上图片验证码的尺寸和网址上显示的尺寸有差别，说明网站上对图片进行了缩放，实际移动的距离需要除以缩放比例。
        例如：验证码的背景图的宽度为600，但是在网站上显示的为300，则实际需要移动的距离需要除以2，同时要考虑滑块是否在最左侧，

        若不是在最左侧，则移动的距离还需减去滑块的起始距离。若何获取？用截图工具对着验证码图片测量出有多少px
        还有部分滑块需要鼠标拉动一定的距离后才能动，所以实际上需要移动的距离还要加上该距离。称为“动距”

        实际滑块需要移动的距离=该方法计算出的距离/缩放比例 - 滑块的起始距离 + “动距”

        :param background_img_path: 背景图片路径
        :return: int 距离
        """
        target_img_gray = cv2.imdecode(np.fromfile(background_img_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        blurred = cv2.GaussianBlur(target_img_gray, (5, 5), 0)
        # gray = cv2.cvtColor(captcha_image, cv2.COLOR_BGR2GRAY)
        # blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edged = cv2.Canny(blurred, 50, 150)
        contours, _ = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        contours = sorted(contours, key=cv2.contourArea, reverse=True)
        slider_contour = contours[0]
        x, y, w, h = cv2.boundingRect(slider_contour)
        slider_position = (x, y, w, h)
        return slider_position[0]

    @classmethod
    def move_slider_slowly(cls, move_x: int, btn_slider, ac):
        """
        模拟滑块缓慢移动（确保所有移动距离为整数，适配move_by_offset要求）
        :param move_x: 总移动距离（x方向，整数）
        :param btn_slider: 滑块元素（WebElement）
        :param ac: ActionChains实例
        """
        ac.click_and_hold(btn_slider).perform()
        time.sleep(random.uniform(0.1, 0.3))  # 按住后停顿

        # 总步数（确保每步移动1-5像素，避免过大跳动）
        steps = max(12, int(abs(move_x) / 10))  # 至少20步，距离越大步数越多
        current_x = 0  # 当前累计移动x距离（整数）

        for i in range(steps):
            # 1. 计算当前步的比例（0→1）
            ratio = i / steps

            # 2. 基于正弦曲线计算理论移动比例（先加速后减速）
            if ratio < 0.5:
                # 前半段加速：sin(π*ratio) 从0→1
                speed_ratio = 2 * ratio
            else:
                # 后半段减速：sin(π*(1-ratio)) 从1→0
                speed_ratio = 2 * (1 - ratio)

            # 3. 计算当前步的理论移动距离（加入随机波动，确保为整数）
            # 总理论移动 = move_x * 速度占比，再随机±10%波动
            raw_dx = move_x * speed_ratio * random.uniform(0.9, 1.1)
            dx = round(raw_dx)  # 转换为整数（核心修正点）

            # 4. 控制不超过剩余距离（避免超调）
            remaining_x = move_x - current_x
            if move_x > 0:
                dx = min(dx, remaining_x)  # 正向移动，不超过剩余
                dx = max(dx, 1)  # 至少移动1像素（避免停滞）
            else:
                dx = max(dx, remaining_x)  # 反向移动，不超过剩余
                dx = min(dx, -1)  # 至少移动-1像素

            # 5. y方向随机抖动（±2像素，整数）
            # dy = random.randint(-2, 2)
            dy = 0

            # 6. 执行移动（确保dx和dy都是整数）
            ac.move_by_offset(dx, dy).perform()
            current_x += dx  # 更新累计距离

            # 7. 每步延迟（模拟人手速度）
            time.sleep(random.uniform(0.001, 0.01))

        # 8. 最终微调（确保总距离精确到move_x）
        final_adjust = move_x - current_x
        if abs(final_adjust) > 0:
            ac.move_by_offset(final_adjust, 0).perform()
            time.sleep(0.05)

        # 释放滑块
        ac.release().perform()
        time.sleep(random.uniform(0.1, 0.2))

    def cal_gap_x_distance_with_gap_img(self, background_img_path: str, gap_img_path: str):
        """
        计算背景图片上的缺口距离（相对于最左侧）
        用缺口图片和背景图片做对比的方式

        若是实际上图片验证码的尺寸和网址上显示的尺寸有差别，说明网站上对图片进行了缩放，实际移动的距离需要除以缩放比例。
        例如：验证码的背景图的宽度为600，但是在网站上显示的为300，则实际需要移动的距离需要除以2，同时要考虑滑块是否在最左侧，

        若不是在最左侧，则移动的距离还需减去滑块的起始距离。若何获取？用截图工具对着验证码图片测量出有多少px
        还有部分滑块需要鼠标拉动一定的距离后才能动，所以实际上需要移动的距离还要加上该距离。称为“动距”

        实际滑块需要移动的距离=该方法计算出的距离/缩放比例 - 滑块的起始距离 + “动距”

        :param background_img_path: 背景图片路径
        :param gap_img_path：缺口图片路径
        :return: int 距离
        """
        target_img_gray = cv2.imdecode(np.fromfile(gap_img_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        base_img_gray = cv2.imdecode(np.fromfile(background_img_path, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
        res = cv2.matchTemplate(target_img_gray, base_img_gray, cv2.TM_CCOEFF_NORMED)
        value = cv2.minMaxLoc(res)
        a, b, c, d = value
        if abs(a) >= abs(b):
            distance = c[0]
        else:
            distance = d[0]
        return distance

    @classmethod
    async def move_slider_slowly_pw_version(cls, move_x: int, btn_slider: Locator, mouse: Mouse):
        """
        模拟滑块缓慢移动（确保所有移动距离为整数，适配move_by_offset要求）
        :param move_x: 总移动距离（x方向，整数）
        :param btn_slider: 滑块元素（WebElement）
        :param ac: ActionChains实例
        """
        rect = await btn_slider.bounding_box()
        await mouse.move(rect['x'], rect['y'])
        await mouse.down()
        # time.sleep(random.uniform(0.1, 0.3))  # 按住后停顿
        # 总步数（确保每步移动1-5像素，避免过大跳动）
        steps = max(12, int(abs(move_x) / 10))  # 至少20步，距离越大步数越多
        current_x = 0  # 当前累计移动x距离（整数）

        for i in range(steps):
            # 1. 计算当前步的比例（0→1）
            ratio = i / steps

            # 2. 基于正弦曲线计算理论移动比例（先加速后减速）
            if ratio < 0.5:
                # 前半段加速：sin(π*ratio) 从0→1
                speed_ratio = 2 * ratio
            else:
                # 后半段减速：sin(π*(1-ratio)) 从1→0
                speed_ratio = 2 * (1 - ratio)

            # 3. 计算当前步的理论移动距离（加入随机波动，确保为整数）
            # 总理论移动 = move_x * 速度占比，再随机±10%波动
            raw_dx = move_x * speed_ratio * random.uniform(0.9, 1.1)
            dx = round(raw_dx)  # 转换为整数（核心修正点）

            # 4. 控制不超过剩余距离（避免超调）
            remaining_x = move_x - current_x
            if move_x > 0:
                dx = min(dx, remaining_x)  # 正向移动，不超过剩余
                dx = max(dx, 1)  # 至少移动1像素（避免停滞）
            else:
                dx = max(dx, remaining_x)  # 反向移动，不超过剩余
                dx = min(dx, -1)  # 至少移动-1像素

            # 5. y方向随机抖动（±2像素，整数）
            # dy = random.randint(-2, 2)
            dy = 0

            # 6. 执行移动（确保dx和dy都是整数）
            # ac.move_by_offset(dx, dy).perform()
            current_x += dx  # 更新累计距离

            await mouse.move(rect['x'] + current_x, rect['y'])

            # 7. 每步延迟（模拟人手速度）
            await asyncio.sleep(random.uniform(0.001, 0.01))
            # time.sleep(random.uniform(0.001, 0.01))

        # 8. 最终微调（确保总距离精确到move_x）
        final_adjust = move_x - current_x
        if abs(final_adjust) > 0:
            # ac.move_by_offset(final_adjust, 0).perform()
            await mouse.move(rect['x'] + move_x, rect['y'])
            # time.sleep(0.05)
            await asyncio.sleep(0.05)

        # 释放滑块
        # ac.release().perform()
        # time.sleep(random.uniform(0.1, 0.2))
        await mouse.up()
        await asyncio.sleep(2)  # 等待2秒，让验证通过
