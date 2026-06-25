"""
Template → RuleSet 注册表。

每个 template_id 对应一组 rule group，engine 据此过滤应用的规则。

扩展方式：
    from poco.templates.registry import register_template
    register_template("my_template", ["date", "business"])
"""

from typing import Dict, List

# ---- 内置模板定义 ------------------------------------------------------------

TEMPLATE_RULE_GROUPS: Dict[str, List[str]] = {
    "service_voucher": ["date", "random", "business"],
    "return_ticket": ["date", "random", "business"],
}

# 默认分组（未匹配到 template_id 时使用全部）
DEFAULT_GROUPS: List[str] = ["date", "random", "business"]

# ---- 公共 API ---------------------------------------------------------------


def get_groups_for_template(template_id: str) -> List[str]:
    """
    返回指定 template_id 对应的规则分组列表。

    未注册的 template_id 返回 DEFAULT_GROUPS（全部规则）。
    """
    return TEMPLATE_RULE_GROUPS.get(template_id, DEFAULT_GROUPS)


def register_template(template_id: str, groups: List[str]) -> None:
    """
    注册或覆盖一个模板的规则分组。

    Args:
        template_id: 模板标识符（如 "ticket"）
        groups:      规则分组列表（如 ["date", "random"]）
    """
    TEMPLATE_RULE_GROUPS[template_id] = list(groups)


def list_templates() -> Dict[str, List[str]]:
    """返回所有已注册模板及其分组"""
    return dict(TEMPLATE_RULE_GROUPS)
