"""
随机数规则。

覆盖字段：
  - 随机四位数  （1000~9999）
  - 随机六位数  （100000~999999）

所有随机值取自 context.random_pool，规则内部不调用 random。
"""

from .base import Rule, Context, register_rule


@register_rule(group="random")
class RandomFourRule(Rule):
    """{{随机四位数}} — 1000~9999 随机整数"""
    field_name = "随机四位数"
    group = "random"

    def compute(self, context: Context) -> str:
        val = context.get_random("random_four")
        return str(val)


@register_rule(group="random")
class RandomSixRule(Rule):
    """{{随机六位数}} — 100000~999999 随机整数"""
    field_name = "随机六位数"
    group = "random"

    def compute(self, context: Context) -> str:
        val = context.get_random("random_six")
        return str(val)
