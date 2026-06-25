"""
POCO 轻量认证模块 — 基于本地 JSON 文件 & Streamlit session_state。

结构清晰，方便未来升级 bcrypt：
    将 _verify_password() 替换为 bcrypt.checkpw() 即可。
"""

import json
import os
from typing import Dict

import streamlit as st

# ---- 路径常量 ------------------------------------------------------------

_AUTH_DIR = os.path.dirname(os.path.abspath(__file__))
_USERS_FILE = os.path.join(_AUTH_DIR, "users.json")

# ---- 内部 helpers --------------------------------------------------------


def _read_users_file() -> Dict[str, dict]:
    """读取 users.json 文件，返回用户字典。文件不存在时返回空字典。"""
    if not os.path.exists(_USERS_FILE):
        return {}
    try:
        with open(_USERS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (json.JSONDecodeError, OSError):
        return {}


def _verify_password(plain: str, stored: str) -> bool:
    """
    密码验证（当前为明文对比）。

    v1 版本使用明文对比；未来升级时仅需替换此函数为：
        import bcrypt
        return bcrypt.checkpw(plain.encode(), stored.encode())
    同时 _hash_password() 配合升级。
    """
    return plain == stored


# ---- 公开 API ------------------------------------------------------------


def load_users() -> Dict[str, dict]:
    """
    加载所有用户数据。

    Returns:
        dict: {username: {"password": str, ...}, ...}
    """
    return _read_users_file()


def login(username: str, password: str) -> bool:
    """
    验证用户名密码，成功后将状态写入 session_state。

    Args:
        username: 用户名
        password: 明文密码

    Returns:
        bool: 登录成功返回 True，失败返回 False
    """
    username = (username or "").strip()
    if not username:
        return False

    users = load_users()
    user_data = users.get(username)

    if user_data is None:
        return False

    if not _verify_password(password, user_data.get("password", "")):
        return False

    # 登录成功 → 写入 session
    st.session_state["login"] = True
    st.session_state["user"] = username
    return True


def logout():
    """退出登录，清除 session 中的登录状态。"""
    st.session_state["login"] = False
    st.session_state["user"] = None
    # 保留其他 session 数据（如模板列表）不受影响


def check_login() -> bool:
    """
    检查当前会话是否已登录。

    Returns:
        bool: 已登录返回 True，否则返回 False
    """
    return st.session_state.get("login", False)
