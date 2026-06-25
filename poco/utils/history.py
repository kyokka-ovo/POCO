"""
生成记录日志模块 — 每次成功生成文档后自动记录到 CSV。

格式：
    logs/history.csv  (UTF-8, 永久保留)

字段：
    timestamp, surname, given_name, passport_no, template_name, output_filename
"""

import csv
import os
from datetime import datetime
from typing import Dict, List, Optional

# 日志目录与文件路径（相对于项目根目录）
_PROJECT_ROOT = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
_LOG_DIR = os.path.join(_PROJECT_ROOT, "logs")
_LOG_FILE = os.path.join(_LOG_DIR, "history.csv")

_HEADERS = [
    "timestamp",
    "surname",
    "given_name",
    "passport_no",
    "template_name",
    "output_filename",
]


def _ensure_log_file() -> None:
    """确保日志目录和 CSV 文件存在（不存在则自动创建并写入表头）。"""
    if not os.path.exists(_LOG_DIR):
        os.makedirs(_LOG_DIR, exist_ok=True)
    if not os.path.exists(_LOG_FILE):
        with open(_LOG_FILE, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(_HEADERS)


def log_generation(
    surname: str,
    given_name: str,
    passport_no: str,
    template_name: str,
    output_filename: str,
) -> None:
    """
    记录一次成功的文档生成。

    Args:
        surname:         姓
        given_name:      名
        passport_no:     护照号
        template_name:   模板名称
        output_filename: 输出文件名
    """
    _ensure_log_file()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(_LOG_FILE, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([
            timestamp,
            surname,
            given_name,
            passport_no,
            template_name,
            output_filename,
        ])


def read_history(limit: Optional[int] = 100) -> List[Dict[str, str]]:
    """
    读取最近 N 条生成记录（最新的在前）。

    Args:
        limit: 返回记录数上限，None 表示无上限

    Returns:
        [{timestamp, surname, given_name, passport_no, template_name, output_filename}, ...]
    """
    if not os.path.exists(_LOG_FILE):
        return []

    rows: List[Dict[str, str]] = []
    with open(_LOG_FILE, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)

    # 最新在前
    rows.reverse()
    if limit is None:
        return rows
    return rows[:limit]


def search_history(
    query: str,
    limit: int = 100,
) -> List[Dict[str, str]]:
    """
    按姓名或护照号搜索历史记录。

    匹配规则：
      - query 出现在 surname、given_name 或 passport_no 中（不区分大小写）
      - query 为空时返回全部

    Args:
        query: 搜索关键词
        limit: 返回记录数上限

    Returns:
        匹配的记录列表（最新的在前）
    """
    all_rows = read_history(limit=None)  # 读取全部（无上限）
    if not query:
        return all_rows[:limit]

    q = query.strip().lower()
    matched: List[Dict[str, str]] = []
    for row in all_rows:
        if (
            q in row.get("surname", "").lower()
            or q in row.get("given_name", "").lower()
            or q in row.get("passport_no", "").lower()
        ):
            matched.append(row)
            if len(matched) >= limit:
                break

    return matched


def get_log_file_path() -> str:
    """返回日志文件的绝对路径（用于调试）。"""
    return _LOG_FILE
