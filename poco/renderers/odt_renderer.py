"""
ODT 渲染器 — OpenDocument Text 模板填充实现。

使用 Python 标准库 (zipfile + xml.etree.ElementTree) 直接操作 ODT 的 XML 内容，
无需外部依赖（odfpy 可选，LibreOffice 可选）。

ODT 文件结构:
  - mimetype       : application/vnd.oasis.opendocument.text
  - content.xml    : 正文内容（段落、表格、文本）
  - styles.xml     : 样式定义（含页眉页脚）
  - META-INF/manifest.xml : 文件清单

支持:
  - 文本替换 (text:p, text:span, text:a, text:h)
  - 简单表格替换 (table:table → table:table-row → table:table-cell)
  - 跨元素占位符安全处理
  - 占位符格式统一为 {{xxx}}（与 DOCX 完全一致）
  - 页眉/页脚替换（如果 styles.xml 中有定义）

依赖:
  - 仅使用 Python 标准库 (zipfile, xml.etree.ElementTree, re, os, copy)
"""

import os
import re
import zipfile
import xml.etree.ElementTree as ET
from copy import deepcopy
from typing import Dict, List, Optional, Tuple

from ..core.base_renderer import BaseRenderer

# ---- ODF 命名空间 ------------------------------------------------------------

NS_TEXT = "urn:oasis:names:tc:opendocument:xmlns:text:1.0"
NS_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
NS_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
NS_STYLE = "urn:oasis:names:tc:opendocument:xmlns:style:1.0"
NS_FO = "urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"

# 所有需要在 ElementTree 中注册的命名空间（保证输出 XML 前缀一致）
_NS_MAP = {
    "text": NS_TEXT,
    "table": NS_TABLE,
    "office": NS_OFFICE,
    "style": NS_STYLE,
    "fo": NS_FO,
}

# 注册命名空间到 ElementTree（全局，只执行一次）
for prefix, uri in _NS_MAP.items():
    ET.register_namespace(prefix, uri)

# 占位符正则
_PLACEHOLDER_RE = re.compile(r"\{\{(.*?)\}\}")

# 文本承载元素的标签名（Clark 表示法）
_TEXT_BEARING_TAGS = {
    f"{{{NS_TEXT}}}p",       # 段落
    f"{{{NS_TEXT}}}span",    # 内联文本
    f"{{{NS_TEXT}}}a",       # 超链接
    f"{{{NS_TEXT}}}h",       # 标题
}

# 文本承载元素列表（用于 iter 匹配）
_TEXT_BEARING = [
    f"{{{NS_TEXT}}}p",
    f"{{{NS_TEXT}}}span",
    f"{{{NS_TEXT}}}a",
    f"{{{NS_TEXT}}}h",
]

# 容器元素（可递归进入）
_TABLE_CELL = f"{{{NS_TABLE}}}table-cell"
_TABLE_ROW = f"{{{NS_TABLE}}}table-row"
_TABLE = f"{{{NS_TABLE}}}table"


class OdtRenderer(BaseRenderer):
    """
    OpenDocument Text (.odt) 模板渲染器。

    支持:
      - 文本段落 (text:p) + 内联文本 (text:span)
      - 表格 (table:table → table:table-row → table:table-cell)
      - 标题 (text:h)
      - 超链接 (text:a)
      - 跨元素占位符安全替换
      - 页眉/页脚 (styles.xml 中的 master-styles)

    Usage:
        renderer = OdtRenderer()
        renderer.load("template.odt")
        renderer.fill({"姓名": "PAN YU", "护照号": "EJ6376603"})
        renderer.save("output.odt")

        # 或一站式:
        renderer.process("template.odt", data, "output.odt")
    """

    ERROR_TAG = "ODT_RENDER_ERROR"

    def __init__(self):
        self._zf_in: Optional[zipfile.ZipFile] = None
        self._file_map: Dict[str, bytes] = {}          # 原始文件内容映射
        self._modified_files: Dict[str, bytes] = {}     # 修改后的文件内容映射
        self._content_root: Optional[ET.Element] = None  # content.xml 根元素
        self._styles_root: Optional[ET.Element] = None   # styles.xml 根元素
        self._template_path: str = None

    # ---- BaseRenderer 接口实现 -----------------------------------------------

    def load(self, file_path: str) -> None:
        """
        加载 .odt 模板文件。

        将整个 ZIP 归档读入内存，解析 content.xml 和 styles.xml。

        Args:
            file_path: .odt 模板文件路径

        Raises:
            FileNotFoundError: 文件不存在
            ValueError:        文件不是有效的 .odt 格式
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(
                self._error_tag(self.ERROR_TAG,
                                f"模板文件不存在: {file_path}")
            )

        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                # 验证 mimetype
                try:
                    mime = zf.read("mimetype").decode("utf-8").strip()
                    if "opendocument.text" not in mime:
                        raise ValueError(
                            self._error_tag(
                                self.ERROR_TAG,
                                f"不是有效的 ODT 文件 (mimetype={mime})"
                            )
                        )
                except KeyError:
                    raise ValueError(
                        self._error_tag(self.ERROR_TAG,
                                        "文件缺少 mimetype 条目，不是有效的 ODT 文件")
                    )

                # 读取所有文件内容到内存
                self._file_map = {}
                for name in zf.namelist():
                    self._file_map[name] = zf.read(name)

            self._template_path = file_path

            # 解析 content.xml
            if "content.xml" not in self._file_map:
                raise ValueError(
                    self._error_tag(self.ERROR_TAG,
                                    "ODT 文件缺少 content.xml")
                )
            self._content_root = ET.fromstring(
                self._file_map["content.xml"]
            )

            # 解析 styles.xml（可能包含页眉页脚）
            if "styles.xml" in self._file_map:
                self._styles_root = ET.fromstring(
                    self._file_map["styles.xml"]
                )

        except (zipfile.BadZipFile, ET.ParseError) as e:
            raise ValueError(
                self._error_tag(self.ERROR_TAG,
                                f"无法解析 ODT 文件: {file_path} — {e}")
            ) from e

    def fill(self, data: Dict[str, str]) -> None:
        """
        将数据填充到已加载的模板中。

        覆盖范围:
          - content.xml 中所有文本段落 + 表格
          - styles.xml 中所有文本（页眉/页脚等）

        Args:
            data: {占位符名称: 替换值} 映射表
        """
        if self._content_root is None:
            raise RuntimeError(
                self._error_tag(self.ERROR_TAG,
                                "未加载模板，请先调用 load()")
            )

        # 填充 content.xml
        self._fill_element_tree(self._content_root, data)

        # 填充 styles.xml（页眉/页脚）
        if self._styles_root is not None:
            self._fill_element_tree(self._styles_root, data)

    def save(self, output_path: str) -> None:
        """
        保存填充后的文档为 .odt 文件。

        Args:
            output_path: 输出 .odt 文件路径（目录不存在时自动创建）
        """
        if self._content_root is None:
            raise RuntimeError(
                self._error_tag(self.ERROR_TAG,
                                "未加载模板，请先调用 load()")
            )

        out_dir = os.path.dirname(output_path)
        if out_dir and not os.path.exists(out_dir):
            os.makedirs(out_dir, exist_ok=True)

        try:
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for name, content in self._file_map.items():
                    if name == "content.xml":
                        # 写入修改后的 content.xml
                        xml_str = self._serialize_xml(self._content_root)
                        zf.writestr(name, xml_str.encode("utf-8"))
                    elif name == "styles.xml" and self._styles_root is not None:
                        # 写入修改后的 styles.xml
                        xml_str = self._serialize_xml(self._styles_root)
                        zf.writestr(name, xml_str.encode("utf-8"))
                    else:
                        # 原样复制其他文件
                        zf.writestr(name, content)
        except Exception as e:
            raise RuntimeError(
                self._error_tag(self.ERROR_TAG,
                                f"保存 ODT 文件失败: {output_path} — {e}")
            ) from e

    # ---- 可选重写 ------------------------------------------------------------

    def extract_placeholders(self) -> List[str]:
        """
        从已加载的模板中提取所有占位符名称。

        Returns:
            占位符名称列表（去重，按首次出现顺序）
        """
        if self._content_root is None:
            return []

        text = self._collect_all_text(self._content_root)
        if self._styles_root is not None:
            text += self._collect_all_text(self._styles_root)

        return self._parse_placeholders(text)

    def validate(self, data: Dict[str, str]) -> List[str]:
        """
        校验数据是否覆盖模板中的所有占位符。

        Returns:
            缺失的占位符名称列表
        """
        placeholders = self.extract_placeholders()
        missing = [ph for ph in placeholders if ph not in data]
        if missing:
            for ph in missing:
                print(
                    self._error_tag(self.ERROR_TAG,
                                    f"missing field: {ph}")
                )
        return missing

    # ---- 内部：XML 填充逻辑 ---------------------------------------------------

    def _fill_element_tree(
        self, root: ET.Element, data: Dict[str, str]
    ) -> None:
        """
        递归填充元素树中的所有占位符。

        策略:
          1. 简单替换 — 占位符完整包含在单个元素的 text 中
          2. 跨元素替换 — 占位符跨越多个兄弟元素（如多个 text:span）
        """
        # ---- 阶段 1：简单替换（逐元素） ----
        self._simple_replace(root, data)

        # ---- 阶段 2：跨元素替换（段落级别） ----
        self._cross_element_replace(root, data)

    def _simple_replace(
        self, root: ET.Element, data: Dict[str, str]
    ) -> None:
        """
        在单个元素的 text 属性中直接替换占位符。

        处理:
          - 所有 text:* 文本承载元素的 .text 和 .tail
          - 递归进入表格单元格
        """
        for elem in root.iter():
            tag = elem.tag

            # 处理元素的 text
            if elem.text and "{{" in elem.text:
                new_text = elem.text
                for match in _PLACEHOLDER_RE.finditer(elem.text):
                    name = match.group(1).strip()
                    if name in data:
                        new_text = new_text.replace(
                            match.group(0), data[name]
                        )
                if new_text != elem.text:
                    elem.text = new_text

            # 处理元素的 tail
            if elem.tail and "{{" in elem.tail:
                new_tail = elem.tail
                for match in _PLACEHOLDER_RE.finditer(elem.tail):
                    name = match.group(1).strip()
                    if name in data:
                        new_tail = new_tail.replace(
                            match.group(0), data[name]
                        )
                if new_tail != elem.tail:
                    elem.tail = new_tail

    def _cross_element_replace(
        self, root: ET.Element, data: Dict[str, str]
    ) -> None:
        """
        处理跨越多个兄弟元素的占位符。

        场景: 占位符 {{酒店号公式}} 被拆分到两个 text:span 中:
          <text:span>编号：{{酒店</text:span>
          <text:span>号公式}}</text:span>

        策略:
          1. 对每个文本承载元素的父元素，拼接其直属文本子元素的完整文本
          2. 查找跨元素的 {{...}} 占位符
          3. 将替换值写入第一个涉及的元素，清除其余元素中的占位符部分
        """
        # 遍历所有容器元素（段落、标题、链接、表格单元格）
        container_tags = _TEXT_BEARING + [_TABLE_CELL]

        for container in root.iter():
            if container.tag not in container_tags:
                continue

            # 收集直接文本子元素（text:span, text:a）或自身的 text
            text_children = self._get_text_children(container)

            if len(text_children) <= 1:
                continue  # 无跨元素的可能性

            # 拼接完整文本，记录每个子元素的偏移
            self._resolve_cross_element_placeholders(
                container, text_children, data
            )

    def _get_text_children(
        self, parent: ET.Element
    ) -> List[Tuple[ET.Element, str, int, int]]:
        """
        获取父元素下的文本承载子元素列表。

        返回: [(element, attr_name, global_start, global_end), ...]
        其中 attr_name 为 "text" 或 "tail"。

        同时也包括父元素自身的 text（在第一个子元素之前）。

        注意: 跳过纯空白字符的条目，以防止占位符被
        元素间的格式化空白打断（例如 text:span 间的换行/缩进）。
        跳过的空白不计入 global 位置偏移，确保偏移量与
        _resolve_cross_element_placeholders 中拼接的 full_text 一致。
        """
        result = []
        pos = 0  # global position within the concatenated meaningful text

        # 父元素的 text（在第一个子元素之前），仅非空白时包含
        if parent.text and parent.text.strip():
            result.append((parent, "text", pos, pos + len(parent.text)))
            pos += len(parent.text)

        for child in parent:
            tag = child.tag
            if tag in _TEXT_BEARING_TAGS:
                if child.text:
                    start = pos
                    end = pos + len(child.text)
                    result.append((child, "text", start, end))
                    pos = end
                # 仅当 tail 包含非空白字符时才纳入；空白 tail 直接跳过（不推进 pos）
                if child.tail and child.tail.strip():
                    start = pos
                    end = pos + len(child.tail)
                    result.append((child, "tail", start, end))
                    pos = end
            elif tag == _TABLE_CELL:
                pass  # 表格单元格递归由 _fill_element_tree 处理

        return result

    def _resolve_cross_element_placeholders(
        self,
        container: ET.Element,
        text_children: List[Tuple[ET.Element, str, int, int]],
        data: Dict[str, str],
    ) -> None:
        """
        对给定容器的文本子元素列表，解析并替换跨元素占位符。
        """
        # 拼接完整文本
        full_text = ""
        for elem, attr, start, end in text_children:
            value = getattr(elem, attr) or ""
            full_text += value

        if "{{" not in full_text or "}}" not in full_text:
            return

        # 查找所有完整占位符
        max_iterations = 30
        for _ in range(max_iterations):
            match = _PLACEHOLDER_RE.search(full_text)
            if not match:
                return

            name = match.group(1).strip()
            if name not in data:
                # 占位符未在 mapping 中 → 保留原样，但更新 full_text 避免死循环
                # 移除已处理的部分
                full_text = full_text[match.end():]
                continue

            replacement = data[name]
            m_start = match.start()
            m_end = match.end()

            # 找到涉及此占位符的所有文本子项
            involved = []
            for elem, attr, s, e in text_children:
                if e > m_start and s < m_end:
                    value = getattr(elem, attr) or ""
                    if value:
                        involved.append((elem, attr, s, e))

            if not involved:
                full_text = full_text[m_end:]
                continue

            if len(involved) == 1:
                # 单元素 → 简单替换（阶段 1 应已处理，此处防御）
                elem, attr, s, e = involved[0]
                value = getattr(elem, attr) or ""
                local_s = m_start - s
                local_e = m_end - s
                new_value = value[:local_s] + replacement + value[local_e:]
                setattr(elem, attr, new_value)
            else:
                # 多元素 → 第一个元素接收完整替换值，其余清除
                for i, (elem, attr, s, e) in enumerate(involved):
                    value = getattr(elem, attr) or ""
                    if i == 0:
                        local_s = m_start - s
                        prefix = value[:local_s]
                        setattr(elem, attr, prefix + replacement)
                    else:
                        local_e = m_end - s
                        if local_e >= len(value):
                            setattr(elem, attr, "")
                        else:
                            setattr(elem, attr, value[local_e:])

            # 更新 full_text 以处理后续占位符
            full_text = (
                full_text[:m_start]
                + replacement
                + full_text[m_end:]
            )
            # 更新 text_children 的偏移（简化策略：重建）
            # 由于已修改，重新收集 text_children
            text_children = self._get_text_children(container)

    # ---- 内部：文本收集 -------------------------------------------------------

    def _collect_all_text(self, root: ET.Element) -> str:
        """递归收集元素树中的所有文本。"""
        parts: List[str] = []
        for elem in root.iter():
            if elem.text:
                parts.append(elem.text)
            if elem.tail:
                parts.append(elem.tail)
        return "".join(parts)

    @staticmethod
    def _parse_placeholders(text: str) -> List[str]:
        """从文本中提取占位符名称（去重，保留顺序）。"""
        seen = set()
        result: List[str] = []
        for match in _PLACEHOLDER_RE.finditer(text):
            name = match.group(1).strip()
            if name and name not in seen:
                seen.add(name)
                result.append(name)
        return result

    # ---- 内部：XML 序列化 -----------------------------------------------------

    @staticmethod
    def _serialize_xml(root: ET.Element) -> str:
        """
        将 ElementTree 序列化为 ODT 兼容的 XML 字符串。

        确保:
          - XML 声明
          - 正确的命名空间前缀
          - UTF-8 编码兼容
        """
        # ET.tostring 配合 registered namespaces 会产生正确前缀
        raw = ET.tostring(root, encoding="unicode", xml_declaration=False)

        # 移除可能的多余空白声明
        # 构建完整的 XML 文档
        xml_declaration = '<?xml version="1.0" encoding="UTF-8"?>\n'
        return xml_declaration + raw
