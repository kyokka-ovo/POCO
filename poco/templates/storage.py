"""
模板文件存储管理。

提供模板文件的持久化存取：保存、列表、获取路径、删除。
元数据以 JSON 文件存储在 storage/ 目录中。
"""

import json
import os
import shutil
from datetime import datetime
from typing import Dict, List, Optional


# ---- 路径常量 ----------------------------------------------------------------

_STORAGE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "storage")
_METADATA_FILE = os.path.join(_STORAGE_DIR, "_metadata.json")


# ---- 内部辅助 ----------------------------------------------------------------


def _ensure_storage() -> None:
    """确保存储目录和元数据文件存在"""
    os.makedirs(_STORAGE_DIR, exist_ok=True)
    if not os.path.exists(_METADATA_FILE):
        with open(_METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f)


def _load_metadata() -> dict:
    """加载元数据"""
    _ensure_storage()
    try:
        with open(_METADATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def _save_metadata(data: dict) -> None:
    """保存元数据"""
    _ensure_storage()
    with open(_METADATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _sanitize_filename(name: str) -> str:
    """清理文件名，移除不安全字符"""
    # 移除 .docx 后缀（如果存在），后续统一添加
    if name.lower().endswith(".docx"):
        name = name[:-5]
    # 替换不安全字符
    for ch in r'<>:"/\|?*':
        name = name.replace(ch, "_")
    return name.strip()


# ---- 公共 API ----------------------------------------------------------------


def save_template(
    source_path: str,
    name: str,
    template_id: Optional[str] = None,
) -> str:
    """
    将 .docx 文件保存到模板存储库。

    Args:
        source_path: 源 .docx 文件路径
        name:        模板显示名称（用于列表和选择）
        template_id: 关联的规则集 ID（可选，如 "return_ticket"）

    Returns:
        存储后的完整文件路径
    """
    _ensure_storage()

    safe_name = _sanitize_filename(name)
    dest_filename = f"{safe_name}.docx"
    dest_path = os.path.join(_STORAGE_DIR, dest_filename)

    # 复制文件
    shutil.copy2(source_path, dest_path)

    # 更新元数据
    meta = _load_metadata()
    meta[safe_name] = {
        "filename": dest_filename,
        "display_name": name,
        "template_id": template_id,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    _save_metadata(meta)

    return dest_path


def save_uploaded_bytes(data: bytes, name: str, template_id: Optional[str] = None) -> str:
    """
    保存上传的字节内容到模板存储库。

    Args:
        data:        上传文件的字节内容
        name:        模板显示名称
        template_id: 关联的规则集 ID

    Returns:
        存储后的完整文件路径
    """
    import tempfile

    # 先写入临时文件，再通过 save_template 统一处理
    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        return save_template(tmp_path, name, template_id)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


def list_saved_templates() -> List[dict]:
    """
    列出所有已保存的模板。

    Returns:
        [
            {
                "name": "return_ticket",
                "display_name": "Return Ticket",
                "template_id": "return_ticket",
                "filename": "return_ticket.docx",
                "saved_at": "2026-06-23 14:30:00",
                "path": "/full/path/to/storage/return_ticket.docx",
            },
            ...
        ]
    """
    _ensure_storage()
    meta = _load_metadata()

    result = []
    for name, info in meta.items():
        filepath = os.path.join(_STORAGE_DIR, info["filename"])
        if os.path.exists(filepath):
            result.append({
                "name": name,
                "display_name": info.get("display_name", name),
                "template_id": info.get("template_id"),
                "filename": info["filename"],
                "saved_at": info.get("saved_at", "unknown"),
                "path": filepath,
            })
        else:
            # 文件丢失，跳过
            pass

    # 同时扫描 storage 目录中未被元数据记录的文件
    known_files = {info["filename"] for info in meta.values()}
    for fname in os.listdir(_STORAGE_DIR):
        if fname.startswith("_") or not fname.endswith(".docx"):
            continue
        if fname not in known_files:
            filepath = os.path.join(_STORAGE_DIR, fname)
            display_name = fname.replace(".docx", "")
            result.append({
                "name": display_name,
                "display_name": display_name,
                "template_id": None,
                "filename": fname,
                "saved_at": "unknown",
                "path": filepath,
            })

    # 按保存时间倒序
    result.sort(key=lambda x: x.get("saved_at", ""), reverse=True)
    return result


def get_template_path(name: str) -> Optional[str]:
    """
    根据模板名称获取完整文件路径。

    Args:
        name: 模板名称（不含 .docx 后缀）

    Returns:
        文件路径，不存在时返回 None
    """
    for tmpl in list_saved_templates():
        if tmpl["name"] == name:
            return tmpl["path"]
    return None


def delete_template(name: str) -> bool:
    """
    删除已保存的模板（文件 + 元数据）。

    Returns:
        True 如果成功删除，False 如果模板不存在
    """
    meta = _load_metadata()
    if name not in meta:
        # 尝试直接删除文件
        filepath = os.path.join(_STORAGE_DIR, f"{name}.docx")
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    info = meta[name]
    filepath = os.path.join(_STORAGE_DIR, info["filename"])
    if os.path.exists(filepath):
        os.remove(filepath)

    del meta[name]
    _save_metadata(meta)
    return True
