"""
规则注册中心 —— 装饰器驱动的自动注册系统。

新增规则：
  1. 在 rules/ 下新建 <name>_rules.py
  2. 用 @register_rule(group="...") 装饰 Rule 子类（从 .base 导入）
  3. 设置 field_name / group 类属性

无需编辑此文件。
engine.py 无需任何修改。
"""

from typing import List, Optional

from .base import (
    Rule, Context, register_rule,  # noqa: F401
    _RULE_REGISTRY,
)


# ---- 导入规则模块（触发 @register_rule 装饰器）--------------------------------

from . import date_rules     # noqa: F401 E402
from . import random_rules   # noqa: F401 E402
from . import business_rules # noqa: F401 E402


# ---- 公共 API -----------------------------------------------------------------


def get_all_rules() -> List[Rule]:
    """返回所有已注册规则"""
    return list(_RULE_REGISTRY)


def find_rule(field_name: str) -> Optional[Rule]:
    """查找能处理指定字段名的规则"""
    for rule in _RULE_REGISTRY:
        if rule.match(field_name):
            return rule
    return None


def get_all_field_names() -> List[str]:
    """返回所有可通过规则生成的字段名（自动推导）"""
    return [r.field_name for r in _RULE_REGISTRY if r.field_name]
