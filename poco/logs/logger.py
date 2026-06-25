"""
操作日志写入核心 — 在 fill_template / 批量生成后记录结构化日志。

约束：
  - 日志写入失败仅输出 console warning，绝不抛出异常
  - 不影响 fill_template 主流程
  - 不依赖数据库或外部服务
"""

from datetime import datetime
from typing import Dict, List, Optional

from .storage import append_log


def log_generation(
    user: str,
    template: str,
    output_files: List[str],
    fields_used: Dict[str, str],
    *,
    timestamp: Optional[str] = None,
) -> bool:
    """
    记录一次文档生成操作。

    Args:
        user:         当前登录用户名
        template:     使用的模板名称
        output_files: 输出文件路径列表（单个文件也传列表）
        fields_used:  使用的字段映射 {占位符: 值}
        timestamp:    可选，自定义时间戳（默认当前时间）

    Returns:
        bool: 写入成功返回 True，失败返回 False（不会抛出异常）

    Example:
        >>> log_generation(
        ...     user="admin",
        ...     template="Return Ticket",
        ...     output_files=["output/Return_Ticket_PAN_YU.docx"],
        ...     fields_used={"姓": "PAN", "名": "YU", "护照号": "EJ6376603"},
        ... )
    """
    if timestamp is None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    entry = {
        "user": user,
        "template": template,
        "output_files": output_files,
        "timestamp": timestamp,
        "fields_used": fields_used,
    }

    try:
        return append_log(entry)
    except Exception as e:
        # 最后一道防线：绝不让日志异常影响主流程
        print(f"[POCO Logger] ⚠️ 日志记录异常（已忽略）: {e}", flush=True)
        return False


def log_batch_generation(
    user: str,
    templates: List[str],
    output_files: List[str],
    fields_used: Dict[str, str],
) -> bool:
    """
    记录一次批量生成操作（合并多条记录的便捷方法）。

    为每个模板创建独立日志条目，确保每条记录精确对应一个模板。

    Args:
        user:         当前登录用户名
        templates:    模板名称列表（与 output_files 一一对应）
        output_files: 输出文件路径列表
        fields_used:  使用的字段映射（所有模板共用）

    Returns:
        bool: 全部写入成功返回 True，任一失败返回 False
    """
    if len(templates) != len(output_files):
        print(
            f"[POCO Logger] ⚠️ 批量日志记录失败："
            f"templates({len(templates)}) 与 output_files({len(output_files)}) 数量不匹配",
            flush=True,
        )
        return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    all_ok = True

    for tmpl, out_file in zip(templates, output_files):
        ok = log_generation(
            user=user,
            template=tmpl,
            output_files=[out_file],
            fields_used=fields_used,
            timestamp=timestamp,
        )
        if not ok:
            all_ok = False

    return all_ok
