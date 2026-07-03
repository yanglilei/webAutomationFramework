"""
读取doc，docx文档
"""
from typing import Tuple, List

from docx import Document

class DocReader:

    @classmethod
    def read_docx(cls, doc_path: str) -> Tuple[str, List[str]]:
        """
        读取Word文档，第一段落为标题，剩余所有段落组成正文数组
        :param doc_path: str 文档本地文件路径
        :return: tuple (title: str, content_paragraphs: list[str])
            title：文档首段标题
            content_paragraphs：正文每一段文字组成的列表
        """
        # 打开文档
        document = Document(doc_path)
        # 提取所有非空段落文本（自动过滤空白空行）
        all_text = []
        for para in document.paragraphs:
            text = para.text.strip()
            if text:
                all_text.append(text)

        # 文档无内容处理
        if len(all_text) == 0:
            return "", []

        # 第一段=标题，剩下全部为正文
        title = all_text[0]
        content = all_text[1:]
        return title, content
