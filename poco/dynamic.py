"""
动态占位符识别器 & 值生成器。

支持的动态占位符：

    ┌──────────────┬──────────────────┬──────────────────────┐
    │ 占位符名称   │ 生成规则         │ 示例                 │
    ├──────────────┼──────────────────┼──────────────────────┤
    │ 随机四位数   │ randint 1000~9999│ 5837                 │
    │ 随机六位数   │ randint 100000~  │ 742910               │
    │              │ 999999           │                      │
    │ 当前日期     │ 当前系统日期     │ 2026-06-23           │
    │ 当前时间     │ 当前系统时间     │ 14:30                │
    └──────────────┴──────────────────┴──────────────────────┘

可通过 ``register()`` / ``unregister()`` 扩展自定义动态字段。
"""

import random
from datetime import datetime
from typing import Any, Callable, Dict, Optional

# ---- 内置动态占位符生成器 ------------------------------------------------


def _random_four_digits() -> str:
    """生成 1000~9999 随机四位数"""
    return str(random.randint(1000, 9999))


def _random_six_digits() -> str:
    """生成 100000~999999 随机六位数"""
    return str(random.randint(100000, 999999))


def _current_date() -> str:
    """返回当前日期，格式 YYYY-MM-DD"""
    return datetime.now().strftime("%Y-%m-%d")


def _current_time() -> str:
    """返回当前时间，格式 HH:MM"""
    return datetime.now().strftime("%H:%M")


# 内置注册表
_BUILTIN_GENERATORS: Dict[str, Callable[[], str]] = {
    "随机四位数": _random_four_digits,
    "随机六位数": _random_six_digits,
    "当前日期": _current_date,
    "当前时间": _current_time,
}

# 用户自定义注册表
_CUSTOM_GENERATORS: Dict[str, Callable[[], str]] = {}


# ---- 公共 API -----------------------------------------------------------


def is_dynamic(name: str) -> bool:
    """判断占位符是否为动态占位符"""
    return name in _BUILTIN_GENERATORS or name in _CUSTOM_GENERATORS


def generate(name: str) -> str:
    """
    根据占位符名称生成对应的值。

    - 动态占位符 → 调用生成器返回结果
    - 普通占位符 → 返回空字符串
    """
    if name in _CUSTOM_GENERATORS:
        return _CUSTOM_GENERATORS[name]()
    if name in _BUILTIN_GENERATORS:
        return _BUILTIN_GENERATORS[name]()
    return ""


def register(name: str, generator: Callable[[], str]) -> None:
    """
    注册自定义动态占位符生成器。

    Args:
        name: 占位符名称（需与模板中 {{xxx}} 一致）
        generator: 无参函数，返回字符串
    """
    _CUSTOM_GENERATORS[name] = generator


def unregister(name: str) -> None:
    """移除自定义动态占位符"""
    _CUSTOM_GENERATORS.pop(name, None)


def list_dynamic_names() -> Dict[str, str]:
    """返回所有已知动态占位符名称及说明（内置 + 自定义）"""
    result: Dict[str, str] = {}
    for name in _BUILTIN_GENERATORS:
        result[name] = "内置"
    for name in _CUSTOM_GENERATORS:
        result[name] = "自定义"
    return result


def generate_value_if_dynamic(name: str) -> Optional[str]:
    """
    如果是动态占位符则生成值，否则返回 None。
    调用方可据此决定占位符值类型：
      - 返回 str → 自动填充
      - 返回 None → 需用户手动录入
    """
    if is_dynamic(name):
        return generate(name)
    return None
