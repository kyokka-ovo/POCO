"""
模板系统 —— 规则集映射 + 文件存储管理。

使用方式:
    from poco.templates import get_groups_for_template
    groups = get_groups_for_template("return_ticket")
    # => ["date", "random", "business"]

    from poco.templates import storage
    storage.list_saved_templates()
"""

from .registry import (  # noqa: F401
    TEMPLATE_RULE_GROUPS,
    DEFAULT_GROUPS,
    get_groups_for_template,
    register_template,
    list_templates,
)

from . import storage  # noqa: F401
