"""
规则引擎（v2 架构兼容层）。

本模块已重构为"规则插件系统"，所有逻辑已迁移至：
  - rules/         → 独立规则类
  - engine.py      → 纯调度层

保留此文件仅用于向后兼容，新代码请直接从 engine 导入。
"""

from .engine import generate_mapping, generate_mapping_for_template  # noqa: F401
