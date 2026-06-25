"""
日期派生规则。

覆盖字段：
  - 月 / 到日 / 到月 / 到年 / 星 / 月日          （基于到达日期）
  - 到日2 / 月2 / 星2                            （到达日期 + offset_a）
  - 返程机票计算公式                              （到达日期 + offset_b）

所有日期偏移使用 timedelta，自动处理月份/闰年进位。
"""

from datetime import timedelta
from .base import Rule, Context, register_rule


_MONTH_ABBRS = [
    "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]

_DAY_ABBRS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _fallback(_field: str) -> str:
    """规则无法计算时返回空字符串 —— validator 会标记格式问题"""
    return ""


# ---- 基础日期规则（基于 base_date）-------------------------------------------


@register_rule(group="date")
class MonthRule(Rule):
    """{{月}} — 到达月份英文三字缩写"""
    field_name = "月"
    group = "date"

    def compute(self, context: Context) -> str:
        if context.base_date is None:
            return _fallback("月")
        return _MONTH_ABBRS[context.base_date.month - 1]


@register_rule(group="date")
class DayRule(Rule):
    """{{到日}} — 到达日期号数"""
    field_name = "到日"
    group = "date"

    def compute(self, context: Context) -> str:
        if context.base_date is None:
            return _fallback("到日")
        return str(context.base_date.day)


@register_rule(group="date")
class MonthNumRule(Rule):
    """{{到月}} — 到达月份数字"""
    field_name = "到月"
    group = "date"

    def compute(self, context: Context) -> str:
        if context.base_date is None:
            return _fallback("到月")
        return str(context.base_date.month)


@register_rule(group="date")
class YearRule(Rule):
    """{{到年}} — 到达年份数字"""
    field_name = "到年"
    group = "date"

    def compute(self, context: Context) -> str:
        if context.base_date is None:
            return _fallback("到年")
        return str(context.base_date.year)


@register_rule(group="date")
class WeekdayRule(Rule):
    """{{星}} — 到达日期星期英文三字缩写"""
    field_name = "星"
    group = "date"

    def compute(self, context: Context) -> str:
        if context.base_date is None:
            return _fallback("星")
        return _DAY_ABBRS[context.base_date.weekday()]


@register_rule(group="date")
class MonthDayRule(Rule):
    """{{月日}} — 月份缩写 + 日期（如 Jun23）"""
    field_name = "月日"
    group = "date"

    def compute(self, context: Context) -> str:
        if context.base_date is None:
            return _fallback("月日")
        month = _MONTH_ABBRS[context.base_date.month - 1]
        day = str(context.base_date.day)
        return month + day


# ---- 偏移日期规则（base_date + random_pool["offset_a"]）----------------------


@register_rule(group="date")
class Day2Rule(Rule):
    """{{到日2}} — 到达日期 + offset_a 天后的日号"""
    field_name = "到日2"
    group = "date"

    def compute(self, context: Context) -> str:
        if context.base_date is None:
            return _fallback("到日2")
        offset_a = context.get_random("offset_a")
        date2 = context.base_date + timedelta(days=offset_a)
        return str(date2.day)


@register_rule(group="date")
class Month2Rule(Rule):
    """{{月2}} — 到达日期 + offset_a 天后的月份"""
    field_name = "月2"
    group = "date"

    def compute(self, context: Context) -> str:
        if context.base_date is None:
            return _fallback("月2")
        offset_a = context.get_random("offset_a")
        date2 = context.base_date + timedelta(days=offset_a)
        return _MONTH_ABBRS[date2.month - 1]


@register_rule(group="date")
class Weekday2Rule(Rule):
    """{{星2}} — 到达日期 + offset_a 天后的星期"""
    field_name = "星2"
    group = "date"

    def compute(self, context: Context) -> str:
        if context.base_date is None:
            return _fallback("星2")
        offset_a = context.get_random("offset_a")
        date2 = context.base_date + timedelta(days=offset_a)
        return _DAY_ABBRS[date2.weekday()]


# ---- 返程机票公式（base_date + random_pool["offset_b"]）----------------------


@register_rule(group="date")
class ReturnTicketRule(Rule):
    """{{返程机票计算公式}} — 到达日期 + offset_b 天，格式 DDMon（如 27Jun）"""
    field_name = "返程机票计算公式"
    group = "date"

    def compute(self, context: Context) -> str:
        if context.base_date is None:
            return _fallback("返程机票计算公式")
        offset_b = context.get_random("offset_b")
        ret_date = context.base_date + timedelta(days=offset_b)
        return f"{ret_date.day:02d}{_MONTH_ABBRS[ret_date.month - 1]}"
