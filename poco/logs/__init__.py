"""
POCO Logs — 操作日志与生成历史系统。

用法:
    from poco.logs import log_generation, get_user_history, get_recent_logs

    # 记录一次生成
    log_generation(
        user="admin",
        template="Return Ticket",
        output_files=["output/Return_Ticket_PAN_YU.docx"],
        fields_used={"姓": "PAN", "名": "YU", "护照号": "EJ6376603"},
    )

    # 查询用户历史
    history = get_user_history("admin")

    # 最近 10 条
    recent = get_recent_logs(limit=10, username="admin")
"""

from .logger import log_generation, log_batch_generation
from .storage import (
    get_user_history,
    get_recent_logs,
    read_all_logs,
    get_log_count,
)
