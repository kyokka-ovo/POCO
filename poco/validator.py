"""
校验与防漏系统 —— 保证 Word 输出 100% 无 {{xxx}}。

提供：
  - validate_mapping():    模板 vs mapping 校验（缺失 / 格式）
  - check_residual():      输出文档残留占位符检测
  - register_validator():  注册字段格式校验器
"""

import re
from typing import Callable, Dict, List, Optional

from .scanner import read_docx_text
from .extractor import extract_placeholders
from .utils.logging import ValidationLogger

# ---- 字段格式校验器注册表 ------------------------------------------------

_VALIDATORS: Dict[str, Callable[[str], Optional[str]]] = {}
"""
{字段关键词: 校验函数}

校验函数签名：
    def validator(value: str) -> Optional[str]:
        return None          # 校验通过
        return "失败原因"     # 校验失败
"""


def register_validator(
    field_keyword: str,
    validator_fn: Callable[[str], Optional[str]],
) -> None:
    """
    注册一个字段格式校验器。

    Args:
        field_keyword: 字段名关键词（子串匹配，例如 "护照号" 会匹配 "护照号"、"旧护照号"）
        validator_fn:  校验函数，接收字段值，返回 None=通过 或 错误信息字符串

    Example:
        >>> def validate_email(value):
        ...     if "@" not in value:
        ...         return "邮箱格式不正确"
        ...     return None
        >>> register_validator("邮箱", validate_email)
    """
    _VALIDATORS[field_keyword] = validator_fn


def unregister_validator(field_keyword: str) -> None:
    """移除已注册的校验器"""
    _VALIDATORS.pop(field_keyword, None)


def list_validators() -> Dict[str, str]:
    """列出所有已注册的校验器关键词"""
    return {k: v.__name__ for k, v in _VALIDATORS.items()}


# ---- 内置校验器 ---------------------------------------------------------


def _validate_passport(value: str) -> Optional[str]:
    """
    护照号校验规则：
      - 长度 >= 6
      - 仅允许字母 A-Z a-z 和数字 0-9
      - 不允许空格
    """
    if not value:
        return "护照号为空"
    if len(value) < 6:
        return f"护照号长度不足（至少 6 位，当前 {len(value)} 位）"
    if " " in value:
        return "护照号不允许包含空格"
    if not re.match(r"^[A-Za-z0-9]+$", value):
        return "护照号只能包含字母和数字"
    return None


def _validate_phone(value: str) -> Optional[str]:
    """
    电话号校验规则：
      - 允许数字、+、-、(、)、空格
      - 纯数字部分至少 7 位
    """
    if not value:
        return "电话号为空"
    if not re.match(r"^[\d\s\-\+\(\)]+$", value):
        return "电话号包含非法字符"
    digits = re.sub(r"[^\d]", "", value)
    if len(digits) < 7:
        return f"电话号位数不足（至少 7 位，当前 {len(digits)} 位）"
    return None


# 注册内置校验器
register_validator("护照号", _validate_passport)
register_validator("电话号", _validate_phone)
# 身份证号 —— 预留，未来扩展
# register_validator("身份证号", _validate_id_card)


# ---- 必填字段校验 -------------------------------------------------------

# 与 engine.CONTEXT_BASE_FIELDS 保持一致
_REQUIRED_FIELDS = ["姓", "名", "护照号", "到达日期"]


def validate_required_fields(
    user_info: Dict[str, str],
) -> List[str]:
    """
    校验必填字段是否已填写。

    以下情况视为未填写：
      - None / 空字符串
      - 仅包含空白字符（空格、制表符等）
      - trim 后为空

    Args:
        user_info: {"姓": "PAN", "名": "", ...}

    Returns:
        错误信息列表（空列表 = 全部通过），每条格式为 "{字段名} 未填写"

    Example:
        >>> validate_required_fields({"姓": "PAN", "名": "", "护照号": "  ", "到达日期": "2026-06-23"})
        ['名 未填写', '护照号 未填写']
    """
    errors: List[str] = []
    for field in _REQUIRED_FIELDS:
        value = user_info.get(field)
        if value is None or not str(value).strip():
            errors.append(f"{field} 未填写")
    return errors


# ---- 公共 API -----------------------------------------------------------


def validate_mapping(
    template_path: str,
    mapping: Dict[str, str],
) -> ValidationLogger:
    """
    校验 mapping 与模板的匹配情况。

    检查项：
      1) 模板中有但 mapping 中没有的占位符 → missing_fields
      2) mapping 值与注册的格式校验器不匹配 → invalid_fields

    Args:
        template_path: .docx 模板路径
        mapping:       {占位符: 值} 映射表

    Returns:
        ValidationLogger 包含完整校验报告

    Example:
        >>> result = validate_mapping("template.docx", {"姓名": "PAN"})
        >>> print(result.report())
        [WARNING] 未定义占位符（2个）：
          - 护照号
          - 出生日期
    """
    logger = ValidationLogger()

    # 1) 提取模板中所有占位符
    text = read_docx_text(template_path)
    placeholders = extract_placeholders(text)

    # 2) 检查缺失字段
    for ph in placeholders:
        if ph not in mapping:
            logger.log_missing(ph)

    # 3) 检查格式校验
    for ph, value in mapping.items():
        for keyword, validator_fn in _VALIDATORS.items():
            if keyword in ph:  # 子串匹配
                err = validator_fn(value)
                if err:
                    logger.log_invalid(ph, value, err)
                break  # 每个字段只匹配第一个命中关键词的校验器

    return logger


def check_residual(output_path: str) -> List[str]:
    """
    检查输出文档中是否仍残留 {{占位符}}。

    Args:
        output_path: 已生成的 .docx 文件路径

    Returns:
        残留占位符列表（空列表 = 无残留）

    Raises:
        ValueError: 当存在残留占位符时抛出
    """
    text = read_docx_text(output_path)
    residual = extract_placeholders(text)
    return residual
