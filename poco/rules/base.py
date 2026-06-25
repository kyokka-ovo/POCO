"""
规则基类与上下文定义。

Context:
  - seed:        随机种子（可复现）
  - random_pool: 统一随机池（所有随机值预先生成，规则内部禁止 rand）
  - base_date:   到达日期（datetime 或 None）
  - last_name:   姓
  - first_name:  名
  - passport:    护照号

Rule:
  - field_name:  本规则处理的字段名（类属性，子类覆盖）
  - group:       本规则所属分组（类属性，用于模板→规则集过滤）
  - match(field_name) → 是否处理该字段（默认：精确匹配 field_name）
  - compute(context)   → 根据上下文计算字段值
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


# ---- 全局注册表 --------------------------------------------------------------

_RULE_REGISTRY: List["Rule"] = []


def register_rule(cls=None, *, group: str = "default"):
    """
    装饰器：自动注册 Rule 子类到全局注册表。

    Usage:
        @register_rule(group="date")
        class MonthRule(Rule):
            field_name = "月"
            group = "date"
            def compute(self, context): ...

    规则实例在模块导入时自动加入 _RULE_REGISTRY。
    """
    def _decorator(rule_cls):
        instance = rule_cls()
        # 若类未显式声明 group，使用装饰器参数
        if not getattr(instance, 'group', None) or instance.group == "default":
            instance.group = group
        _RULE_REGISTRY.append(instance)
        return rule_cls

    if cls is not None:
        # 无参数调用：@register_rule
        return _decorator(cls)
    # 带参数调用：@register_rule(group="date")
    return _decorator


@dataclass
class Context:
    """
    统一上下文 —— 规则间共享的数据容器。

    所有随机值由 engine 在构建 context 时预先生成并存入 random_pool，
    规则内部严禁调用 random 模块。
    """
    seed: int
    base_date: Optional[datetime]
    last_name: str       # 姓
    first_name: str      # 名
    passport: str        # 护照号
    random_pool: Dict[str, int] = field(default_factory=dict)

    def get_random(self, key: str, default: int = 0) -> int:
        """从随机池中获取预计算值"""
        return self.random_pool.get(key, default)


class Rule(ABC):
    """
    规则插件基类。

    子类必须：
      - 覆盖 field_name 类属性（声明处理的字段名）
      - 覆盖 group 类属性（声明所属分组，如 "date" / "random" / "business"）
      - 实现 compute(context) 方法

    match() 提供默认实现（精确匹配 field_name），子类可按需覆盖。

    Example:
        >>> @register_rule(group="date")
        ... class MonthRule(Rule):
        ...     field_name = "月"
        ...     group = "date"
        ...     def compute(self, context: Context) -> str:
        ...         if context.base_date is None:
        ...             return ""  # 无法计算时返回空字符串，由 validator 捕获
        ...         return _MONTH_ABBRS[context.base_date.month - 1]
    """

    # 子类必须覆盖：
    field_name: str = ""       # e.g. "月", "随机四位数"
    group: str = "default"     # e.g. "date", "random", "business"

    def match(self, field_name: str) -> bool:
        """
        判断本规则是否处理给定字段名。

        默认实现：精确匹配 self.field_name。
        子类可覆盖以实现更复杂的匹配逻辑（如前缀匹配）。
        """
        return field_name == self.field_name

    @abstractmethod
    def compute(self, context: Context) -> str:
        """根据上下文计算字段值。"""
        ...
