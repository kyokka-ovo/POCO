"""
格式检测器 — 自动识别文档文件类型。

检测策略（按优先级）:
  1. 文件扩展名（不区分大小写）
  2. ZIP 魔数 + 内部结构（docx / odt 都是 ZIP 归档）
  3. 无法识别 → "unknown"

支持的格式:
  - docx: Office Open XML (Word)
  - odt:  Open Document Format (LibreOffice / OpenOffice)
"""

import os
import zipfile
from typing import Optional

# 已知格式及其扩展名（小写）
_EXTENSION_MAP = {
    ".docx": "docx",
    ".odt": "odt",
}

# 通过 ZIP 内部文件签名区分的格式映射
# docx 必定包含 word/document.xml
# odt  必定包含 content.xml 且 mimetype 为 application/vnd.oasis.opendocument.text
_ZIP_SIGNATURE_FILES = {
    "word/document.xml": "docx",
    "content.xml": None,  # 需进一步检查 mimetype
}


def detect_format(file_path: str) -> str:
    """
    自动识别文档文件格式。

    检测策略（按优先级依次尝试）:
      1. 文件扩展名匹配（快速路径）
      2. ZIP 内部文件签名验证（可靠路径）
      3. 无法识别 → "unknown"

    Args:
        file_path: 文档文件路径

    Returns:
        格式标识字符串:
          - "docx"     — Microsoft Word 文档
          - "odt"      — OpenDocument 文本文档
          - "unknown"  — 无法识别的格式

    Example:
        >>> detect_format("template.docx")
        "docx"
        >>> detect_format("template.odt")
        "odt"
        >>> detect_format("template.pdf")
        "unknown"
    """
    if not os.path.isfile(file_path):
        return "unknown"

    # ---- 策略 1: 文件扩展名 ----
    ext = os.path.splitext(file_path)[1].lower()
    if ext in _EXTENSION_MAP:
        candidate = _EXTENSION_MAP[ext]
        # 如果能打开为 ZIP，进一步验证内部签名
        verified = _verify_zip_signature(file_path, candidate)
        if verified:
            return verified

    # ---- 策略 2: ZIP 内部文件签名 ----
    # 当扩展名不正确或未识别时，尝试通过 ZIP 内部结构检测
    result = _detect_by_zip_content(file_path)
    if result != "unknown":
        return result

    # ---- 策略 3: 无法识别 ----
    return "unknown"


def _verify_zip_signature(file_path: str, expected_format: str) -> Optional[str]:
    """
    验证 ZIP 归档内部是否包含目标格式的特征文件。

    Args:
        file_path: 文件路径
        expected_format: 期望的格式标识

    Returns:
        验证通过返回格式字符串，失败返回 None
    """
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            names = set(zf.namelist())

            if expected_format == "docx":
                if "word/document.xml" in names:
                    return "docx"
            elif expected_format == "odt":
                if "content.xml" in names:
                    # 进一步验证 mimetype
                    try:
                        mime = zf.read("mimetype").decode("utf-8").strip()
                        if "opendocument.text" in mime:
                            return "odt"
                    except (KeyError, UnicodeDecodeError):
                        pass
            return None
    except (zipfile.BadZipFile, FileNotFoundError, OSError):
        return None


def _detect_by_zip_content(file_path: str) -> str:
    """
    通过 ZIP 内部文件结构检测文档格式。

    当文件扩展名不可靠时使用此方法。
    """
    try:
        with zipfile.ZipFile(file_path, "r") as zf:
            names = set(zf.namelist())

            # ODT 检测
            if "content.xml" in names:
                try:
                    mime = zf.read("mimetype").decode("utf-8").strip()
                    if "opendocument.text" in mime:
                        return "odt"
                except (KeyError, UnicodeDecodeError):
                    pass

            # DOCX 检测
            if "word/document.xml" in names:
                # 确认不是其他 OOXML 格式（如 xlsx）
                try:
                    mime = zf.read("[Content_Types].xml").decode("utf-8", errors="ignore")
                    if "wordprocessingml" in mime.lower():
                        return "docx"
                except (KeyError, UnicodeDecodeError):
                    pass

            return "unknown"
    except (zipfile.BadZipFile, FileNotFoundError, OSError):
        return "unknown"


# 当前支持的格式列表
SUPPORTED_FORMATS = ["docx", "odt"]


def is_supported_format(file_path: str) -> bool:
    """检查文件格式是否受 POCO 支持。"""
    return detect_format(file_path) in SUPPORTED_FORMATS
