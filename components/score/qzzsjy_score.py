from dataclasses import dataclass
from typing import Dict, List

from playwright.async_api import Locator

from src.frame.base.base_task_node import BasePYNode


@dataclass(init=False)
class QZZSJYScore(BasePYNode):
    """
    泉州终身教育获取分数
    https://qzzsjy.mh.chaoxing.com/
    """
    workspace_url: str =  ""

    async def execute(self, context: Dict) -> bool:
        self.workspace_url = self.node_config.get("node_params", {}).get("workspace_url", "")
        if not self.workspace_url:
            self.logger.error("未指定空间地址，参数名：workspace_url")
            return False
        else:
            await self.load_url(self.workspace_url)

        iframe_elem = self.switch_to_frame("#frame_content")

        class_names: List[Locator] = await self.get_elems_with_wait_by_xpath(10, "//ul[@class='l_tcourse_item clearfix']/li//div[@class='l_tcourse_center h120']//dt[1]", iframe=iframe_elem)
        status_descs: List[Locator] = await self.get_elems_with_wait_by_xpath(10, "//ul[@class='l_tcourse_item clearfix']/li//div[@class='l_tcourse_center h120']//dd[4]", iframe=iframe_elem)

        learning_desc = []

        for class_name, status_desc in zip(class_names, status_descs):
            class_name_desc = await class_name.text_content()
            status_desc_text = await status_desc.text_content()
            # 去掉"合格状态："的前缀
            status_desc_text = status_desc_text[status_desc_text.find("合格状态：")+5:]
            self.logger.info(f"{class_name_desc}：{status_desc_text}")
            learning_desc.append(class_name_desc)
            learning_desc.append("-")
            learning_desc.append(status_desc_text)
            learning_desc.append("；")

        if learning_desc:
            learning_desc = "".join(learning_desc)
            learning_desc = learning_desc[:-1]
        else:
            learning_desc = "无课程"
        self.user_manager.update_learning_status(self.username, learning_desc)
        return True