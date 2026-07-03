"""
各种类型的验证码处理器
"""
import asyncio
from pathlib import Path

from PIL import Image

from src.frame.base.playwright_web_operator import PlaywrightWebOperator
from src.utils import SysPathUtils, SliderVerifyUtils


class CXImageValidatorHandler:
    """
    超星图片验证码处理器
    """

    def __init__(self, username, web_operator: PlaywrightWebOperator, logger):
        self.username = username
        self.logger = logger
        self.web_operator = web_operator
        # 滑块验证码的滑块图片保存位置
        self.target_img_path = str(Path(SysPathUtils.get_tmp_file_dir(), self.username + "_2.png"))
        # 滑块验证码的背景图片保存位置
        self.background_img_path = str(Path(SysPathUtils.get_tmp_file_dir(), self.username + "_1.png"))

    async def handle_cx_image_validate(self, iframe, max_retry_count=20):
        count = 0
        ret = False
        while True:
            if count == max_retry_count:
                self.logger.error("滑块验证码，验证失败达20次，请人工介入检查")
                ret = False
                break
            else:
                count = count + 1
                # 获取滑动的图片
                target_img_elem = await self.web_operator.get_elem_with_wait_by_xpath(3,
                                                                                      "//div[@class='cx_imgBtn']/img",
                                                                                      iframe=iframe)
                file_url = await target_img_elem.get_attribute("src")
                headers = {"Cookie": await self.web_operator.cookie_to_str(),
                           "Content-Type": "application/json;charset=utf-8",
                           "User-Agent": await self.web_operator.user_agent()}
                img = await self.web_operator.context.request.get(file_url, headers=headers)
                with open(self.target_img_path, "wb") as f:
                    f.write(await img.body())
                # 获取背景图片
                slider_background_elem = await self.web_operator.get_elem_by_xpath("//canvas[@id='cx_obstacle_canvas']",
                                                                                   iframe)
                await self.web_operator.screenshot(self.background_img_path, slider_background_elem)

                # 截图验证码模块
                ret = self._shot_img(self.background_img_path, self.background_img_path,
                                     56 + 1, 0,
                                     320,
                                     160)
                if not ret:
                    # 截图保存失败
                    self.logger.error("请检查滑块图片的路径是否存在！")
                    ret = False
                    break
                else:
                    # 计算滑块到缺口的距离
                    try:
                        x = SliderVerifyUtils.calculate_slider_distance(self.background_img_path,
                                                                              self.target_img_path)
                    except:
                        self.logger.error("计算滑块和缺口的距离失败，原因：", exc_info=True)
                        ret = False
                        break
                    # 滑块需要移动的距离
                    diff_x = 25  # 补偿距离，滑块移动25个像素后图片才会跟着移动
                    move_x = 56 + x + diff_x

                slider_btn_elem = await self.web_operator.get_elem_with_wait_by_xpath(3,
                                                                                      "//div[contains(@class, 'cx_rightBtn')]",
                                                                                      visible=True, iframe=iframe)
                await SliderVerifyUtils.move_slider_slowly_pw_version(move_x, slider_btn_elem, self.web_operator.get_current_page())

                await self.web_operator.wait_for_disappeared(3, "//div[@id='eject']", context=iframe)
                if await self.web_operator.get_elem_by_xpath("//div[@id='eject']", iframe=iframe):
                    ret = False
                    self.logger.info(f"签到，滑块验证失败，重试次数：{count}")
                    error_tips_elem = await self.web_operator.get_elem_with_wait_by_xpath(2, "//div[@class='cx_comImageValidate']//span[@class='cx_tip_text cx_fallback_tip']", iframe=iframe)
                    if error_tips_elem:
                        await error_tips_elem.click()
                        await asyncio.sleep(2)
                else:
                    ret = True
                    break

        return ret

    def _shot_img(self, src_img_path, save_path, left, upper, right, lower):
        """
        截图
        :param src_img_path: 原始图片路径
        :param save_path:截图后保存的路径
        :param left:左边坐标
        :param upper:上方坐标
        :param right:右边坐标
        :param lower:下方坐标
        :return:bool True-截图保存成功；False-截图保存失败
        """
        ret = True
        img = None
        region = None
        try:
            img = Image.open(src_img_path)
            region = img.crop((left, upper, right, lower))
            region.save(save_path)
        except:
            self.logger.exception("截图失败，原因：")
            ret = False
        finally:
            if img is not None:
                img.close()
            if region is not None:
                region.close()
        return ret
