"""
POCO Core — 多格式统一处理框架。

提供:
  - detect_format():     自动识别文档格式（docx / odt / unknown）
  - BaseRenderer:        所有渲染器的抽象基类
  - DocumentEngine:      统一入口，自动检测格式并调度渲染器
  - scan_template_text(): 格式无关的模板文本提取

用法:
    from poco.core import DocumentEngine

    engine = DocumentEngine()
    engine.process("template.docx", data, "output.docx")
    engine.process("template.odt", data, "output.odt")
"""

from .format_detector import detect_format, SUPPORTED_FORMATS
from .base_renderer import BaseRenderer
from .engine import DocumentEngine, scan_template_text

__all__ = [
    "detect_format",
    "SUPPORTED_FORMATS",
    "BaseRenderer",
    "DocumentEngine",
    "scan_template_text",
]
