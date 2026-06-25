"""
POCO Auth — 轻量账号密码登录系统。

用法:
    from poco.auth import login, logout, check_login, load_users

    # 登录页面
    if not check_login():
        # 显示登录表单 ...
        st.stop()

    # 退出登录
    logout()
"""

from .auth import login, logout, check_login, load_users
