"""
渲染器包 — 各格式的具体实现。

内置渲染器:
  - DocxRenderer: Microsoft Word (.docx) 渲染器
  - OdtRenderer:  OpenDocument Text (.odt) 渲染器

扩展:
  可通过 poco.core.engine.register_renderer() 注册自定义渲染器。
"""

from .docx_renderer import DocxRenderer
from .odt_renderer import OdtRenderer

__all__ = [
    "DocxRenderer",
    "OdtRenderer",
]
