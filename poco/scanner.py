"""
Word 模板扫描器 — 从 .docx 文件中提取全部文本内容。

使用 Python 标准库（zipfile + xml.etree.ElementTree），
不依赖 python-docx，保证最大可移植性。

提取范围：
  - 正文段落
  - 表格
  - 页眉 / 页脚
  - 脚注 / 尾注
  - 文本框（如果存在）
"""

import zipfile
import xml.etree.ElementTree as ET
from typing import List

# WordprocessingML 命名空间
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# .docx 内部需要扫描的 XML 条目
_DOCUMENT_PARTS = [
    "word/document.xml",
]

# 页眉 / 页脚 / 脚注 / 尾注 —— 从 [Content_Types].xml 或 document.xml 的 rels 中动态发现更准确，
# 但这里采用命名约定覆盖绝大多数情况。
_EXTRA_PARTS_PATTERNS = [
    "word/header",   # header1.xml, header2.xml ...
    "word/footer",   # footer1.xml, footer2.xml ...
    "word/footnotes.xml",
    "word/endnotes.xml",
]


def _extract_text_from_xml(xml_bytes: bytes) -> str:
    """
    从 WordprocessingML XML 中提取所有 <w:t> 文本节点，
    按文档顺序拼接后返回。
    """
    root = ET.fromstring(xml_bytes)
    parts: List[str] = []
    for t_elem in root.iter(f"{{{NS_W}}}t"):
        text = t_elem.text
        if text:
            parts.append(text)
    return "".join(parts)


def read_docx_text(filepath: str) -> str:
    """
    读取 .docx 文件的全部文本内容。

    Args:
        filepath: .docx 文件路径

    Returns:
        文档中所有文本拼接后的字符串（包含占位符标记）
    """
    collected: List[str] = []

    with zipfile.ZipFile(filepath, "r") as zf:
        # 列出压缩包内所有文件
        all_names = zf.namelist()

        # 1) 扫描已知路径
        for part in _DOCUMENT_PARTS:
            if part in all_names:
                collected.append(_extract_text_from_xml(zf.read(part)))

        # 2) 扫描页眉 / 页脚 / 脚注 / 尾注（按前缀匹配）
        for name in all_names:
            for pattern in _EXTRA_PARTS_PATTERNS:
                if name.startswith(pattern) and name.endswith(".xml"):
                    collected.append(_extract_text_from_xml(zf.read(name)))
                    break

    return "".join(collected)
