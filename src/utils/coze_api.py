
import random
from typing import Optional, List

from cozepy import COZE_CN_BASE_URL, MessageType, Message, Coze, TokenAuth


class CozeAPI:
    def __init__(self, coze_api_token, bot_id, user_id=None):
        self.coze = Coze(auth=TokenAuth(token=coze_api_token), base_url=COZE_CN_BASE_URL)
        self.bot_id = bot_id
        self.user_id = user_id

    def no_stream_request(self, additional_messages: Optional[List[Message]]=None):
        user_id = self.user_id if self.user_id else str(random.randint(100000000, 999999999))
        chat_poll = self.coze.chat.create_and_poll(
            bot_id=self.bot_id,
            user_id=user_id,
            additional_messages=additional_messages
        )

        reply_content = ""
        for message in chat_poll.messages:
            if message.type == MessageType.ANSWER:
                reply_content = message.content
                break

        return reply_content


class CommonEDUAgent:

    def __init__(self, bot_id="", token=""):
        """
        通用教育智能体
        :param coze_api_token:
        """
        # 智能体id
        self.bot_id = bot_id or "7568879141236850726"
        # 不过期令牌
        self.token = token or "sat_cBUzkoAJDvu3qrVTojpJntczmU2pGtxt5HMMS3OqFUMOkcbrmqO9PUjPddaNkynm"
        self.coze_api = CozeAPI(self.token, self.bot_id)

    def get_reply(self, question: Optional[List[Message]]=None):
        return self.coze_api.no_stream_request(question)


class CommonHNKFAgent:
    def __init__(self):
        """
        湖南考法智能体
        :param coze_api_token:
        """
        # 智能体id
        self.bot_id = "7574308916490944558"
        # 不过期令牌
        self.token = "sat_cBUzkoAJDvu3qrVTojpJntczmU2pGtxt5HMMS3OqFUMOkcbrmqO9PUjPddaNkynm"
        self.coze_api = CozeAPI(self.token, self.bot_id)

    def get_reply(self, question: Optional[List[Message]]=None):
        return self.coze_api.no_stream_request(question)


if __name__ == '__main__':
    # 1.截图
    # import os
    # self.web_browser.save_screenshot(os.path.join(os.getcwd(), self.username + "-error" + str(
    #     random.randint(0, 100000)) + ".png"))
    local_file = r"C:\Users\lovel\Desktop\问题1.png"
    # 2.上传到七牛

    # 3.发送给智能体

    reply_content = CommonEDUAgent().get_reply([Message.build_user_question_text("我是一位中小学教师，以下是一道题目，请以我的视角解答。要求：直接输出文字，不添加任何格式（包括markdown格式）\n=====\n请问该如何帮助学生爱上学习？")])
    print(reply_content)

