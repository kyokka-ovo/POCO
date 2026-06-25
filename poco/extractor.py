"""
占位符提取器 — 从文本中提取所有 {{xxx}} 占位符。
"""

import re
from typing import List

# 占位符正则：匹配 {{ 和 }} 之间的任意内容（非贪婪）
_PLACEHOLDER_RE = re.compile(r"\{\{(.*?)\}\}")


def extract_placeholders(text: str) -> List[str]:
    """
    从文本中提取所有占位符名称，按出现顺序去重返回。

    Args:
        text: 待扫描的文本

    Returns:
        占位符名称列表（去重，保留首次出现顺序）
    """
    seen = set()
    result: List[str] = []
    for match in _PLACEHOLDER_RE.finditer(text):
        name = match.group(1).strip()
        if name and name not in seen:
            seen.add(name)
            result.append(name)
    return result
