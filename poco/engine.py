"""
规则调度引擎 —— 只做三件事：

  1. 读取模板字段
  2. 匹配规则
  3. 调用规则生成值

严禁在 engine 中编写业务逻辑。
"""

import random as _random
from datetime import datetime
from typing import Dict, List, Optional

from .rules import get_all_rules
from .rules.base import Context, Rule


# ---- 内部辅助 ---------------------------------------------------------------


def _parse_date(date_str: str) -> Optional[datetime]:
    """解析 YYYY-MM-DD 日期字符串，失败返回 None"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.strip(), "%Y-%m-%d")
    except (ValueError, TypeError):
        return None


def _build_context(
    user_info: Dict[str, str],
    seed: Optional[int],
) -> Context:
    """
    构建统一上下文（包含预生成的随机池）。

    所有随机值在此处一次性生成，规则内部禁止调用 random。
    """
    if seed is not None:
        _random.seed(seed)

    # 基础字段
    last_name = user_info.get("姓", "")
    first_name = user_info.get("名", "")
    passport = user_info.get("护照号", "")
    arrival_str = user_info.get("到达日期", "")
    base_date = _parse_date(arrival_str)

    # 预生成所有随机值 —— 规则只读取，不生成
    random_pool = {
        "offset_a": _random.randint(6, 9),
        "offset_b": _random.randint(11, 15),
        "random_four": _random.randint(1000, 9999),
        "random_six": _random.randint(100000, 999999),
    }

    return Context(
        seed=seed if seed is not None else 0,
        base_date=base_date,
        last_name=last_name,
        first_name=first_name,
        passport=passport,
        random_pool=random_pool,
    )


def _filter_rules_by_template(template_id: Optional[str]) -> List[Rule]:
    """
    根据 template_id 过滤规则。

    - template_id=None  → 返回全部规则（向后兼容）
    - template_id=指定  → 仅返回对应 group 的规则
    """
    all_rules = get_all_rules()
    if template_id is None:
        return all_rules

    from .templates.registry import get_groups_for_template
    allowed_groups = set(get_groups_for_template(template_id))
    return [r for r in all_rules if getattr(r, 'group', 'default') in allowed_groups]


# ---- 公共 API ---------------------------------------------------------------


def generate_mapping(
    user_info: Dict[str, str],
    seed: Optional[int] = None,
    template_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    根据用户基础信息生成完整 mapping。

    Args:
        user_info: {
            "姓": "PAN",
            "名": "YU",
            "护照号": "EJ6376603",
            "到达日期": "2026-06-23",
        }
        seed:        随机种子（用于可复现结果）
        template_id: 模板标识符（可选，用于过滤规则分组）

    Returns:
        完整字段映射表，所有值均为可直接填入 Word 的字符串。

    Guarantees:
        - 输出绝不包含 {{xxx}}
        - 所有随机值在一次调用中保持一致
        - 用户提供的额外字段全部透传
        - 规则覆盖的字段均由 rule_engine 生成
    """
    context = _build_context(user_info, seed)

    mapping: Dict[str, str] = {}

    # 1) 基础字段（直接透传）
    mapping["姓"] = context.last_name
    mapping["名"] = context.first_name
    mapping["护照号"] = context.passport

    # 2) 匹配规则 → 调用生成值
    rules = _filter_rules_by_template(template_id)
    for rule in rules:
        mapping[rule.field_name] = rule.compute(context)

    # 3) 透传用户提供的所有额外字段（UI 收集的 user_input_fields）
    for key, value in user_info.items():
        if key not in mapping and value:
            mapping[key] = value

    return mapping


def generate_mapping_for_template(
    template_path: str,
    user_info: Dict[str, str],
    seed: Optional[int] = None,
    template_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    根据模板需要的占位符 + 用户信息，生成精确匹配的 mapping。

    Args:
        template_path: .docx 模板路径
        user_info:     基础字段（姓/名/护照号/到达日期）
        seed:          随机种子
        template_id:   模板标识符（可选，用于过滤规则分组）

    Returns:
        仅包含模板所需占位符的 mapping
    """
    from .scanner import read_docx_text
    from .extractor import extract_placeholders

    # 先生成（已按 template_id 过滤的）全量 mapping
    full_mapping = generate_mapping(user_info, seed=seed, template_id=template_id)

    # 使用格式感知的扫描器，兼容 docx 和 odt
    try:
        from .core.engine import scan_template_text
        text = scan_template_text(template_path)
    except (ImportError, ValueError):
        # 回退到纯 docx 扫描（向后兼容）
        text = read_docx_text(template_path)
    placeholders = extract_placeholders(text)

    filtered: Dict[str, str] = {}
    for ph in placeholders:
        if ph in full_mapping:
            filtered[ph] = full_mapping[ph]
        # 不在此处的占位符不在 mapping 中 → 留待 validator 报告缺失

    return filtered


# ---- 字段分类（纯数据输出，无 UI 逻辑）------------------------------------------

# Context 构建所需的固定基础字段
CONTEXT_BASE_FIELDS = ["姓", "名", "护照号", "到达日期"]


def classify_template_fields(
    template_path: str,
    template_id: Optional[str] = None,
) -> Dict[str, List[str]]:
    """
    将模板中的所有占位符分类为「需用户填写」与「系统自动生成」。

    此函数为纯数据输出，不包含任何 UI 逻辑。
    UI 层可根据此分类决定展示/隐藏哪些字段。

    Args:
        template_path: .docx 模板路径
        template_id:   模板标识符（可选，用于限制规则范围）

    Returns:
        {
            "context_fields":         ["姓", "名", "护照号", "到达日期"],
            "user_input_fields":      ["电话号", "公司名", ...],
            "auto_generated_fields":  ["月", "到日", "随机四位数", ...],
        }

    - context_fields:       构建 Context 始终需要的字段（固定 4 个）
    - user_input_fields:    模板中存在但无规则处理的字段 → 用户必须填写
    - auto_generated_fields: 模板中存在且有规则处理的字段 → 系统自动生成
    """
    from .scanner import read_docx_text
    from .extractor import extract_placeholders

    # 使用格式感知的扫描器，兼容 docx 和 odt
    try:
        from .core.engine import scan_template_text
        text = scan_template_text(template_path)
    except (ImportError, ValueError):
        text = read_docx_text(template_path)
    placeholders = extract_placeholders(text)
    rules = _filter_rules_by_template(template_id)
    rule_field_names: set = {r.field_name for r in rules}

    user_input: List[str] = []
    auto_generated: List[str] = []

    for ph in placeholders:
        if ph in rule_field_names:
            auto_generated.append(ph)
        else:
            user_input.append(ph)

    return {
        "context_fields": list(CONTEXT_BASE_FIELDS),
        "user_input_fields": user_input,
        "auto_generated_fields": auto_generated,
    }


__all__ = [
    "generate_mapping",
    "generate_mapping_for_template",
    "classify_template_fields",
    "CONTEXT_BASE_FIELDS",
]
