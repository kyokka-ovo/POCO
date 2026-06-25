"""
POCO — Word 模板占位符扫描 & 自动填充引擎。

用法
----
    import poco

    # 扫描模板中的所有占位符
    placeholders = poco.scan_template("template.docx")
    # => ["姓名", "护照号", "随机四位数", ...]

    # 生成占位符映射表（动态字段自动赋值）
    mapping = poco.generate_mapping("template.docx")
    # => {"姓名": "", "护照号": "", "随机四位数": "5821", ...}

    # 填充模板
    poco.fill_template(
        "template.docx",
        "output.docx",
        {"姓名": "PAN YU", "护照号": "EJ6376603"},
    )
"""

from typing import Dict, List
from .validator import validate_required_fields
from .scanner import read_docx_text
from .extractor import extract_placeholders
from .dynamic import is_dynamic, generate, generate_value_if_dynamic
from .filler import fill_template
from .validator import validate_mapping, validate_required_fields, check_residual, register_validator
from . import engine  # v2 架构：规则插件化调度引擎


def scan_template(filepath: str) -> List[str]:
    """
    扫描 Word 模板，返回所有占位符名称列表。

    Args:
        filepath: .docx 模板文件路径

    Returns:
        占位符名称列表（去重，按首次出现顺序）

    Example:
        >>> scan_template("template.docx")
        ["姓名", "护照号", "出生日期", "随机四位数"]
    """
    text = read_docx_text(filepath)
    return extract_placeholders(text)


def generate_mapping(filepath: str) -> Dict[str, str]:
    """
    扫描模板并生成占位符 → 值映射表。

    - 动态占位符（随机四位数、当前日期等）自动生成值
    - 普通占位符值为空字符串，等待用户填写

    Args:
        filepath: .docx 模板文件路径

    Returns:
        {占位符名称: 值}

    Example:
        >>> generate_mapping("template.docx")
        {"姓名": "", "护照号": "", "随机四位数": "3742", "当前日期": "2026-06-23"}
    """
    placeholders = scan_template(filepath)
    mapping: Dict[str, str] = {}
    for name in placeholders:
        mapping[name] = generate(name)
    return mapping
