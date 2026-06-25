"""
业务公式规则。

覆盖字段：
  - 酒店号公式   （YYMMDD + "4" + 随机四位数）
  - 公           （停留天数 = offset_a）
  - 英文全名     （姓 + " " + 名）
"""

from .base import Rule, Context, register_rule


def _fallback(_field: str) -> str:
    """规则无法计算时返回空字符串 —— validator 会标记格式问题"""
    return ""


@register_rule(group="business")
class HotelNumberRule(Rule):
    """
    {{酒店号公式}} — 11 位数字。

    前六位：YYMMDD（到达日期）
    第七位：固定为 "4"
    后四位：随机四位数（取自 random_pool）
    """
    field_name = "酒店号公式"
    group = "business"

    def compute(self, context: Context) -> str:
        if context.base_date is None:
            return _fallback("酒店号公式")
        yy = context.base_date.strftime("%y")
        mm = context.base_date.strftime("%m")
        dd = context.base_date.strftime("%d")
        random_four = context.get_random("random_four")
        return f"{yy}{mm}{dd}4{random_four:04d}"


@register_rule(group="business")
class DiffRule(Rule):
    """
    {{公}} — 停留天数。

    值等于 offset_a（6~9），即 到日2 与 到日 的差值。
    """
    field_name = "公"
    group = "business"

    def compute(self, context: Context) -> str:
        offset_a = context.get_random("offset_a")
        return str(offset_a)


@register_rule(group="business")
class FullNameRule(Rule):
    """{{英文全名}} — "姓 名" 拼接"""
    field_name = "英文全名"
    group = "business"

    def compute(self, context: Context) -> str:
        if context.last_name and context.first_name:
            return f"{context.last_name} {context.first_name}"
        return _fallback("英文全名")
