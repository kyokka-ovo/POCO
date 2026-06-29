"""
文档引擎 — 多格式统一入口。

自动检测模板格式，选择对应的渲染器，完成 load → fill → save 流水线。

使用示例:
    from poco.core.engine import DocumentEngine

    engine = DocumentEngine()
    engine.process("template.docx", data, "output.docx")
    engine.process("template.odt",  data, "output.odt")
"""

import os
import re
import zipfile
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Type

from .format_detector import detect_format, SUPPORTED_FORMATS
from .base_renderer import BaseRenderer


# ---- 渲染器注册表 ------------------------------------------------------------

_RENDERER_REGISTRY: Dict[str, Type[BaseRenderer]] = {}
"""格式 → 渲染器类的映射表。通过 register_renderer() 注册。"""


def register_renderer(fmt: str, renderer_cls: Type[BaseRenderer]) -> None:
    """
    注册一个渲染器类。

    Args:
        fmt:           格式标识（如 "docx", "odt"）
        renderer_cls:  BaseRenderer 子类
    """
    _RENDERER_REGISTRY[fmt] = renderer_cls


def get_renderer(fmt: str) -> Optional[Type[BaseRenderer]]:
    """获取已注册的渲染器类。"""
    return _RENDERER_REGISTRY.get(fmt)


def list_registered_formats() -> List[str]:
    """列出所有已注册渲染器的格式。"""
    return list(_RENDERER_REGISTRY.keys())


# ---- 统一文本扫描（格式无关）-------------------------------------------------


# ODF 文本命名空间
NS_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
NS_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"

# WordprocessingML 命名空间
NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"

# 占位符正则
_PLACEHOLDER_RE = re.compile(r"\{\{(.*?)\}\}")


def _extract_text_from_docx_xml(xml_bytes: bytes) -> str:
    """从 DOCX XML 中提取所有 <w:t> 文本。"""
    root = ET.fromstring(xml_bytes)
    parts: List[str] = []
    for t_elem in root.iter(f"{{{NS_W}}}t"):
        text = t_elem.text
        if text:
            parts.append(text)
    return "".join(parts)


def _extract_text_from_odt_xml(xml_bytes: bytes) -> str:
    """从 ODT content.xml 中提取所有文本。"""
    root = ET.fromstring(xml_bytes)
    parts: List[str] = []

    # ODT 中的文本节点:
    # - <text:p> 段落中的直接文本和 <text:span> 子元素
    # - <text:span> 中的文本
    # - <text:a> 链接中的文本
    # - 表格单元格中的文本（递归在 <text:p> 内）
    for elem in root.iter():
        tag = elem.tag
        # 检查是否为文本承载元素的直接文本
        if tag in (
            f"{{{NS_TEXT}}}p",
            f"{{{NS_TEXT}}}span",
            f"{{{NS_TEXT}}}a",
            f"{{{NS_TEXT}}}h",
        ):
            text = elem.text
            if text:
                parts.append(text)
            # 同时收集子元素的 tail 文本
            for child in elem:
                if child.tail:
                    parts.append(child.tail)
        # 收集所有 text() 节点中的文本（包括嵌套情况）
        if elem.text and tag not in (
            f"{{{NS_TEXT}}}p",
            f"{{{NS_TEXT}}}span",
            f"{{{NS_TEXT}}}a",
            f"{{{NS_TEXT}}}h",
        ):
            pass  # 非文本承载元素不收集

    # 更健壮的策略：收集所有元素的 text 和 tail
    for elem in root.iter():
        if elem.text:
            parts.append(elem.text)
        if elem.tail:
            parts.append(elem.tail)

    return "".join(parts)


def scan_template_text(file_path: str) -> str:
    """
    格式无关的模板文本提取。

    自动检测文件格式，使用对应的提取策略读取全部文本内容。

    Args:
        file_path: 模板文件路径（.docx 或 .odt）

    Returns:
        文档中所有文本拼接后的字符串（包含占位符标记）

    Raises:
        ValueError: 不支持的格式
        FileNotFoundError: 文件不存在

    Example:
        >>> text = scan_template_text("template.docx")
        >>> text = scan_template_text("template.odt")
    """
    fmt = detect_format(file_path)
    if fmt == "unknown":
        raise ValueError(f"无法识别文件格式: {file_path}")

    collected: List[str] = []

    with zipfile.ZipFile(file_path, "r") as zf:
        all_names = zf.namelist()

        if fmt == "docx":
            # 正文
            if "word/document.xml" in all_names:
                collected.append(
                    _extract_text_from_docx_xml(zf.read("word/document.xml"))
                )
            # 页眉 / 页脚 / 脚注 / 尾注
            for name in all_names:
                if name.startswith(("word/header", "word/footer",
                                   "word/footnotes", "word/endnotes")):
                    if name.endswith(".xml"):
                        collected.append(
                            _extract_text_from_docx_xml(zf.read(name))
                        )

        elif fmt == "odt":
            # ODT 主内容
            if "content.xml" in all_names:
                collected.append(
                    _extract_text_from_odt_xml(zf.read("content.xml"))
                )
            # ODT 样式中的文本（如页眉页脚）
            if "styles.xml" in all_names:
                collected.append(
                    _extract_text_from_odt_xml(zf.read("styles.xml"))
                )

    return "".join(collected)


# ---- DocumentEngine ----------------------------------------------------------


class DocumentEngine:
    """
    多格式文档处理引擎。

    自动检测模板格式，选择对应的渲染器，执行 load → fill → save 流水线。

    所有渲染器在首次使用时通过 register_renderer() 注册。
    用户也可以注册自定义渲染器以扩展新格式支持。

    Usage:
        engine = DocumentEngine()
        engine.process("template.docx", {"姓名": "PAN"}, "output.docx")
        engine.process("template.odt",  {"姓名": "PAN"}, "output.odt")

        # 批量处理
        engine.process_batch([
            ("t1.docx", data1, "out1.docx"),
            ("t2.odt",  data2, "out2.odt"),
        ])
    """

    def __init__(self):
        """初始化引擎，自动注册内置渲染器。"""
        self._ensure_renderers_registered()

    @staticmethod
    def _ensure_renderers_registered() -> None:
        """确保内置渲染器已注册（幂等）。"""
        if "docx" not in _RENDERER_REGISTRY:
            from ..renderers.docx_renderer import DocxRenderer
            register_renderer("docx", DocxRenderer)
        if "odt" not in _RENDERER_REGISTRY:
            from ..renderers.odt_renderer import OdtRenderer
            register_renderer("odt", OdtRenderer)

    # ---- 公共 API -----------------------------------------------------------

    def process(
        self,
        template_path: str,
        data: Dict[str, str],
        output_path: str,
        *,
        renderer_class: Optional[Type[BaseRenderer]] = None,
    ) -> str:
        """
        处理单个模板：检测格式 → load → fill → save。

        Args:
            template_path:  模板文件路径
            data:           {占位符: 值} 映射表
            output_path:    输出文件路径
            renderer_class: 可选，显式指定渲染器类（跳过格式检测）

        Returns:
            实际使用的格式标识（"docx" 或 "odt"）

        Raises:
            ValueError:   不支持的格式 / 模板数据不匹配
            FileNotFoundError: 模板文件不存在
            RuntimeError: 填充或保存过程中出错

        Example:
            >>> engine = DocumentEngine()
            >>> engine.process("template.docx", {"姓名": "PAN"}, "output.docx")
            "docx"
        """
        # 1) 检测格式
        if renderer_class is not None:
            # 显式指定渲染器
            renderer = renderer_class()
            fmt = self._infer_format_from_class(renderer_class)
        else:
            fmt = detect_format(template_path)
            if fmt == "unknown":
                raise ValueError(
                    f"[ENGINE_ERROR] 无法识别文件格式: {template_path}"
                    f"\n  支持的格式: {', '.join(SUPPORTED_FORMATS)}"
                )
            cls = get_renderer(fmt)
            if cls is None:
                raise ValueError(
                    f"[ENGINE_ERROR] 格式 '{fmt}' 已识别但无对应渲染器"
                    f"\n  已注册的渲染器: {list_registered_formats()}"
                )
            renderer = cls()

        # 2) 执行流水线
        try:
            renderer.load(template_path)
            renderer.fill(data)
            renderer.save(output_path)
        except Exception as e:
            raise RuntimeError(
                f"[ENGINE_ERROR] 处理失败: {template_path}\n"
                f"  格式: {fmt}\n"
                f"  原因: {e}"
            ) from e

        return fmt

    def process_batch(
        self,
        jobs: List[tuple],
    ) -> List[Dict[str, Optional[str]]]:
        """
        批量处理多个模板。

        Args:
            jobs: [(template_path, data, output_path), ...] 列表

        Returns:
            [
                {
                    "template": str,
                    "output": str,
                    "format": str | None,
                    "error": str | None,
                },
                ...
            ]

        Note:
            单个任务失败不会中断批量处理，错误信息会记录在返回值的 "error" 字段中。
        """
        results: List[Dict[str, Optional[str]]] = []

        for template_path, data, output_path in jobs:
            entry = {
                "template": template_path,
                "output": output_path,
                "format": None,
                "error": None,
            }
            try:
                fmt = self.process(template_path, data, output_path)
                entry["format"] = fmt
            except Exception as e:
                entry["error"] = str(e)
            results.append(entry)

        return results

    # ---- 辅助方法 -----------------------------------------------------------

    def preview_placeholders(self, template_path: str) -> List[str]:
        """
        预览模板中的所有占位符（不执行填充）。

        Args:
            template_path: 模板文件路径

        Returns:
            占位符名称列表
        """
        fmt = detect_format(template_path)
        if fmt == "unknown":
            raise ValueError(f"无法识别文件格式: {template_path}")

        cls = get_renderer(fmt)
        if cls is None:
            raise ValueError(f"格式 '{fmt}' 无对应渲染器")

        renderer = cls()
        renderer.load(template_path)
        return renderer.extract_placeholders()

    @staticmethod
    def _infer_format_from_class(cls: Type[BaseRenderer]) -> str:
        """从渲染器类名推断格式标识。"""
        name = cls.__name__.lower()
        for fmt in SUPPORTED_FORMATS:
            if fmt in name:
                return fmt
        return "unknown"

    @property
    def supported_formats(self) -> List[str]:
        """返回当前支持的格式列表。"""
        return sorted(list_registered_formats())


# ---- 便捷函数 ----------------------------------------------------------------


def process_document(
    template_path: str,
    data: Dict[str, str],
    output_path: str,
) -> str:
    """
    便捷函数：单次处理一个文档（无需手动创建 DocumentEngine）。

    等价于:
        engine = DocumentEngine()
        engine.process(template_path, data, output_path)

    Args:
        template_path: 模板文件路径
        data:          {占位符: 值}
        output_path:   输出文件路径

    Returns:
        格式标识字符串
    """
    engine = DocumentEngine()
    return engine.process(template_path, data, output_path)
