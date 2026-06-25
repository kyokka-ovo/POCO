"""
校验日志收集器 —— 收集 fill_template 过程中的校验事件并格式化输出。
"""

from typing import Dict, List, Optional


class ValidationLogger:
    """
    校验事件收集器。

    收集三类事件：
      - missing_fields:     模板有但 mapping 未定义的占位符
      - invalid_fields:     格式校验失败（护照号等）
      - replaced_fallback:  已被规则兜底替换的字段（保留用于历史兼容）

    Usage:
        >>> logger = ValidationLogger()
        >>> logger.log_missing("护照号")
        >>> logger.log_invalid("护照号", "E J", "不允许包含空格")
        >>> logger.log_fallback("到年")
        >>> print(logger.report())
    """

    def __init__(self) -> None:
        self.missing_fields: List[str] = []
        self.invalid_fields: List[Dict[str, str]] = []
        self.replaced_fallback_fields: List[str] = []

    # ---- 记录方法 ---------------------------------------------------------

    def log_missing(self, field_name: str) -> None:
        """记录一个未定义占位符"""
        self.missing_fields.append(field_name)

    def log_invalid(self, field_name: str, value: str, reason: str) -> None:
        """
        记录一个格式校验失败的字段。

        Args:
            field_name: 占位符名称
            value:      实际值
            reason:     失败原因（中文描述）
        """
        self.invalid_fields.append({
            "field": field_name,
            "value": value,
            "reason": reason,
            "ui_warning": True,  # 预留给 UI 标红使用
        })

    def log_fallback(self, field_name: str) -> None:
        """记录一个已兜底替换的字段"""
        self.replaced_fallback_fields.append(field_name)

    # ---- 输出 -------------------------------------------------------------

    @property
    def has_warnings(self) -> bool:
        """是否存在任何警告"""
        return bool(self.missing_fields or self.invalid_fields)

    def summary(self) -> Dict[str, list]:
        """返回结构化摘要（供程序化消费）"""
        return {
            "missing_fields": list(self.missing_fields),
            "invalid_fields": list(self.invalid_fields),
            "replaced_fallback_fields": list(self.replaced_fallback_fields),
        }

    def report(self) -> str:
        """
        生成人类可读的校验报告。

        Returns:
            多行文本报告（可直接 print）
        """
        lines: List[str] = []

        if self.missing_fields:
            lines.append(
                f"[WARNING] 未定义占位符（{len(self.missing_fields)}个）："
            )
            for f in self.missing_fields:
                lines.append(f"  - {f}")

        if self.invalid_fields:
            lines.append(
                f"[WARNING] 格式校验失败（{len(self.invalid_fields)}个）："
            )
            for item in self.invalid_fields:
                lines.append(
                    f"  - {item['field']}: {item['reason']} "
                    f"（当前值: {item['value']}）"
                )

        if self.replaced_fallback_fields:
            lines.append(
                f"[INFO] 已兜底替换（{len(self.replaced_fallback_fields)}个）："
            )
            for f in self.replaced_fallback_fields:
                lines.append(f"  - {f} → [自动兜底]")

        if not lines:
            lines.append("[OK] 所有字段校验通过。")

        return "\n".join(lines)
