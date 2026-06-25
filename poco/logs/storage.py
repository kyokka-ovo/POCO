"""
日志持久化层 — append-only JSON 文件读写。

安全保证：
  - 写入使用原子操作（临时文件 + 重命名），防止写入中途崩溃损坏数据
  - 读取时自动校验 JSON 合法性，损坏时备份并重建
  - 仅支持 append，绝不覆盖或删除已有记录
"""

import json
import os
import shutil
import tempfile
from datetime import datetime
from typing import Dict, List, Optional

# ---- 路径常量 ------------------------------------------------------------

_LOG_DIR = os.path.dirname(os.path.abspath(__file__))
_LOG_FILE = os.path.join(_LOG_DIR, "history.json")

# ---- 内部 helpers --------------------------------------------------------


def _atomic_write(data: list) -> None:
    """
    原子写入：先写入临时文件，再重命名为目标文件。

    防止写入过程中崩溃导致 JSON 损坏。
    """
    tmp_fd, tmp_path = tempfile.mkstemp(
        suffix=".json", prefix="poco_log_", dir=_LOG_DIR
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # Windows 下需要先删除目标文件才能 rename
        if os.path.exists(_LOG_FILE):
            os.replace(tmp_path, _LOG_FILE)
        else:
            os.rename(tmp_path, _LOG_FILE)
    except Exception:
        # 清理临时文件
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def _safe_read() -> list:
    """
    安全读取 history.json，返回日志列表。

    - 文件不存在 → 创建空文件，返回 []
    - JSON 损坏 → 备份损坏文件，返回 []
    """
    if not os.path.exists(_LOG_FILE):
        # 创建空日志文件
        _atomic_write([])
        return []

    try:
        with open(_LOG_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError("history.json 根元素不是数组")
        return data
    except (json.JSONDecodeError, ValueError) as e:
        # JSON 损坏 → 备份
        backup_name = (
            f"history_corrupted_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        backup_path = os.path.join(_LOG_DIR, backup_name)
        try:
            shutil.copy2(_LOG_FILE, backup_path)
            print(
                f"[POCO Logger] ⚠️ history.json 损坏，已备份至 {backup_name}，"
                f"错误: {e}",
                flush=True,
            )
        except OSError:
            print(
                f"[POCO Logger] ⚠️ history.json 损坏且无法备份，错误: {e}",
                flush=True,
            )
        # 重建空文件
        _atomic_write([])
        return []


# ---- 公开 API ------------------------------------------------------------


def append_log(entry: dict) -> bool:
    """
    追加一条日志记录到 history.json。

    写入失败时不会抛出异常，返回 False 并在控制台输出 warning。

    Args:
        entry: 单条日志记录（dict）

    Returns:
        bool: 写入成功返回 True，失败返回 False
    """
    try:
        logs = _safe_read()
        logs.append(entry)
        _atomic_write(logs)
        return True
    except Exception as e:
        print(f"[POCO Logger] ⚠️ 日志写入失败: {e}", flush=True)
        return False


def read_all_logs() -> List[dict]:
    """
    读取全部日志记录（按写入顺序）。

    Returns:
        list[dict]: 所有日志条目
    """
    return _safe_read()


def get_user_history(username: str) -> List[dict]:
    """
    获取指定用户的所有历史记录（按时间倒序，最新在前）。

    Args:
        username: 用户名

    Returns:
        list[dict]: 该用户的日志条目，按时间倒序排列
    """
    all_logs = _safe_read()
    user_logs = [
        entry for entry in all_logs if entry.get("user") == username
    ]
    # 按时间戳倒序（最新在前）
    user_logs.sort(key=lambda e: e.get("timestamp", ""), reverse=True)
    return user_logs


def get_recent_logs(limit: int = 10, username: Optional[str] = None) -> List[dict]:
    """
    获取最近 N 条日志记录（最新在前）。

    Args:
        limit:    返回记录数上限
        username: 可选，按用户名过滤

    Returns:
        list[dict]: 最近的日志条目
    """
    if username:
        logs = get_user_history(username)
    else:
        logs = _safe_read()
        logs.sort(key=lambda e: e.get("timestamp", ""), reverse=True)

    return logs[:limit]


def get_log_count() -> int:
    """返回当前日志总条数。"""
    return len(_safe_read())
