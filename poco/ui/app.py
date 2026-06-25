"""
POCO v3.4 Streamlit App — 产品化 Word 模板自动生成工具。

Run:
    streamlit run poco/ui/app.py

Features:
    - 账号登录系统（多用户，本地 JSON 存储）
    - 操作日志与生成历史（JSON append-only 存储）
    - 模板库（选择已有 / 上传新模板保存）
    - 字段自动分类（user_input vs auto_generated）
    - UI 仅展示需用户填写的字段，隐藏公式/随机/派生字段
    - 多模板批量生成
"""

import io
import os
import sys
import tempfile
import zipfile
from typing import Dict, List, Optional

import streamlit as st

# Ensure poco is importable
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from poco.auth import login, logout, check_login, load_users
from poco.logs import log_generation, get_recent_logs, get_log_count
from poco.engine import (
    generate_mapping_for_template,
    classify_template_fields,
    CONTEXT_BASE_FIELDS,
)
from poco.filler import fill_template
from poco.validator import validate_required_fields
from poco.templates.registry import (
    list_templates as list_rule_templates,
    get_groups_for_template,
)
from poco.templates import storage as template_storage
from poco.utils.history import (
    log_generation as log_generation_csv,
    read_history,
    search_history,
)

# ---- Constants ---------------------------------------------------------------

CONTEXT_FIELD_LABELS = {
    "姓":  "姓名（姓）",
    "名":  "姓名（名）",
    "护照号": "护照号码",
    "到达日期": "到达日期",
}

# 文件名非法字符（Windows + 通用安全）
_ILLEGAL_FILENAME_CHARS = set('\\/:*?"<>|')


def _sanitize_filename_part(s: str) -> str:
    """移除文件名中的非法字符，去除首尾空白/点号。"""
    result = "".join(ch for ch in s if ch not in _ILLEGAL_FILENAME_CHARS)
    return result.strip().strip(".")


def _build_output_filename(template_name: str, last_name: str, first_name: str) -> str:
    """
    构建输出文件名：模板名-姓_名.docx

    - 非法字符自动过滤
    - 姓/名为空时使用 "Unknown"
    - 示例：Return Ticket-PAN_YU.docx
    """
    last = _sanitize_filename_part(last_name) if last_name else ""
    first = _sanitize_filename_part(first_name) if first_name else ""

    if not last and not first:
        person = "Unknown"
    elif not last:
        person = first
    elif not first:
        person = last
    else:
        person = f"{last}_{first}"

    template_part = _sanitize_filename_part(template_name)
    return f"{template_part}-{person}.docx"


# ---- Batch Generation ----------------------------------------------------------


def generate_all(
    selected_templates: List[dict],
    user_info: Dict[str, str],
    seed: Optional[int] = None,
) -> List[str]:
    """
    批量生成：多选模板 → 生成全部文档。

    Args:
        selected_templates: 模板元数据列表（来自 template_storage 的 list 条目）
        user_info:          用户填写的所有字段
        seed:               随机种子

    Returns:
        list[filepath] — 生成的所有 .docx 文件路径列表
    """
    last_name = user_info.get("姓", "")
    first_name = user_info.get("名", "")

    output_paths: List[str] = []

    for tmpl in selected_templates:
        tpath = tmpl["path"]
        tname = tmpl["display_name"]
        tid = tmpl.get("template_id")

        mapping = generate_mapping_for_template(
            template_path=tpath,
            user_info=user_info,
            seed=seed,
            template_id=tid,
        )

        filename = _build_output_filename(tname, last_name, first_name)
        output_path = os.path.join(tempfile.gettempdir(), filename)
        fill_template(tpath, output_path, mapping)
        output_paths.append(output_path)

    return output_paths


def _make_zip_bytes(file_paths: List[str], entry_names: Optional[List[str]] = None) -> bytes:
    """将多个文件打包为 ZIP 字节流。entry_names 可指定 ZIP 内每条目的文件名。"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i, fp in enumerate(file_paths):
            arcname = entry_names[i] if entry_names else os.path.basename(fp)
            zf.write(fp, arcname)
    return buf.getvalue()

# ---- Page Config -------------------------------------------------------------

st.set_page_config(
    page_title="POCO — 文档自动生成系统",
    page_icon="📄",
    layout="wide",
)

st.title("📄 POCO — Word 模板自动生成工具")
st.caption("模板库选择 → 填写信息 → 一键批量生成 Word 文档")

# ============================================================================
#  Login Gate
# ============================================================================

if not check_login():
    st.divider()

    col_left, col_center, col_right = st.columns([1, 2, 1])
    with col_center:
        st.subheader("🔐 登录 POCO")
        st.caption("请输入账号密码以使用系统。")

        with st.form("login_form"):
            input_user = st.text_input(
                "用户名",
                placeholder="请输入用户名",
                key="login_username",
            )
            input_pass = st.text_input(
                "密码",
                type="password",
                placeholder="请输入密码",
                key="login_password",
            )

            col_submit, _ = st.columns([1, 2])
            with col_submit:
                submitted = st.form_submit_button(
                    "🔓 登录", use_container_width=True, type="primary"
                )

            if submitted:
                if login(input_user, input_pass):
                    st.success(f"✅ 登录成功，欢迎 {st.session_state.user}！")
                    st.rerun()
                else:
                    st.error("❌ 用户名或密码错误，请重试。")

    # 阻止未登录用户访问任何功能
    st.stop()

# ---- Session State Init ------------------------------------------------------

# -- Auth state --
if "login" not in st.session_state:
    st.session_state.login = False
if "user" not in st.session_state:
    st.session_state.user = None

if "saved_templates" not in st.session_state:
    st.session_state.saved_templates = template_storage.list_saved_templates()
if "uploaded_template_path" not in st.session_state:
    st.session_state.uploaded_template_path = None
if "delete_target" not in st.session_state:
    st.session_state.delete_target = None  # {name, display_name} 待删除模板


def refresh_library():
    """刷新模板库列表"""
    st.session_state.saved_templates = template_storage.list_saved_templates()


# ---- Sidebar: Configuration + Upload -----------------------------------------

with st.sidebar:
    # ---- User Info & Logout ----
    st.markdown(f"👤 **当前用户：** `{st.session_state.user}`")

    col_logout1, col_logout2 = st.columns([2, 1])
    with col_logout1:
        pass
    with col_logout2:
        if st.button("🚪 退出", use_container_width=True, key="logout_btn"):
            logout()
            st.rerun()

    st.divider()

    # ---- Page Switcher ----
    page = st.radio(
        "📌 导航",
        ["📄 文档生成", "📋 生成历史"],
        key="page_switcher",
    )

    if page == "📋 生成历史":
        st.divider()

    # -- Seed --
    use_seed = st.checkbox(
        "固定随机种子", value=True,
        help="启用后可复现生成结果。",
    )
    seed_val: Optional[int] = None
    if use_seed:
        seed_val = st.number_input(
            "随机种子值", value=42, step=1,
            help="相同种子 + 相同输入 = 相同输出。",
        )

    st.divider()

    # -- Recent History Quick-View --
    with st.expander("📜 生成历史（最近记录）"):
        recent = get_recent_logs(limit=10, username=st.session_state.user)
        if not recent:
            st.caption("暂无生成记录。")
        else:
            for entry in recent:
                tmpl_name = entry.get("template", "未知模板")
                ts = entry.get("timestamp", "")[:16]  # "2026-06-23 14:30"
                out_files = entry.get("output_files", [])
                file_basename = (
                    os.path.basename(out_files[0]) if out_files else "—"
                )
                st.caption(f"📄 {tmpl_name}")
                st.caption(f"⏱ {ts}  |  📎 {file_basename}")
                st.caption("---")

    st.divider()

    # -- Template Library --
    st.subheader("📁 模板库")

    saved = st.session_state.saved_templates
    if not saved:
        st.info("暂无已保存模板，请在下方上传。")

    # Build multiselect options
    tmpl_options = {
        f"{t['display_name']} [{t.get('template_id') or '自动识别'}]": t
        for t in saved
    }
    selected_labels = st.multiselect(
        "选择要处理的模板：",
        options=list(tmpl_options.keys()),
        help="选择一个或多个模板进行批量生成。",
    )

    # Resolve selected templates
    selected_templates = [tmpl_options[label] for label in selected_labels]

    if selected_templates:
        st.caption(f"✅ 已选择 {len(selected_templates)} 个模板")

    # ── 删除模板 ──
    with st.expander("🗑 管理模板（删除）"):
        for t in saved:
            col1, col2 = st.columns([4, 1])
            with col1:
                tid_label = f" [{t.get('template_id')}]" if t.get('template_id') else ""
                st.caption(f"📄 {t['display_name']}{tid_label}")
            with col2:
                if st.button("🗑", key=f"delbtn_{t['name']}", help=f"删除「{t['display_name']}」"):
                    st.session_state.delete_target = {
                        "name": t["name"],
                        "display_name": t["display_name"],
                    }
                    st.rerun()

    # ── 删除确认 ──
    if st.session_state.delete_target is not None:
        target = st.session_state.delete_target
        st.divider()
        st.warning(f"⚠️ 确认删除模板？\n\n**模板名：** {target['display_name']}\n\n删除后不可恢复。")

        col_cancel, col_confirm = st.columns(2)
        with col_cancel:
            if st.button("取消", use_container_width=True, key="del_cancel"):
                st.session_state.delete_target = None
                st.rerun()
        with col_confirm:
            if st.button("确认删除", type="primary", use_container_width=True, key="del_confirm"):
                try:
                    ok = template_storage.delete_template(target["name"])
                    if ok:
                        # 如果被删除的模板正在选中，刷新后会因列表更新而自动清除
                        refresh_library()
                        st.session_state.delete_target = None
                        st.success(f"已删除模板：{target['display_name']}.docx")
                        st.rerun()
                    else:
                        st.error(f"删除失败：模板「{target['display_name']}」不存在。")
                        st.session_state.delete_target = None
                except Exception as e:
                    st.error(f"删除失败：{e}")
                    st.session_state.delete_target = None

    st.divider()

    # -- Upload New Template --
    st.subheader("📤 上传新模板")

    uploaded_file = st.file_uploader(
        "选择 .docx 文件",
        type=["docx"],
        key="new_template_uploader",
        help="上传包含 {{占位符}} 标记的 Word 文档。",
    )

    if uploaded_file is not None:
        upload_name = st.text_input(
            "模板名称",
            value=uploaded_file.name.replace(".docx", ""),
            help="在模板库中的显示名称。",
        )

        # Template type for the uploaded file
        rule_tmpls = list_rule_templates()
        rule_options = ["（自动 — 使用全部规则）"] + sorted(rule_tmpls.keys())
        upload_tmpl_type = st.selectbox(
            "模板关联的规则集",
            options=rule_options,
            key="upload_rule_type",
        )
        upload_tmpl_id = (
            None if "自动" in upload_tmpl_type else upload_tmpl_type
        )

        if st.button("💾 保存到模板库", use_container_width=True):
            try:
                template_storage.save_uploaded_bytes(
                    uploaded_file.read(),
                    upload_name,
                    upload_tmpl_id,
                )
                refresh_library()
                st.success(f"已保存「{upload_name}」到模板库。")
                st.rerun()
            except Exception as e:
                st.error(f"保存失败：{e}")


# ---- Main Area ---------------------------------------------------------------

if page == "📋 生成历史":
    # ========================================================================
    # History Page
    # ========================================================================
    st.subheader("📋 生成历史")
    st.caption("最近 100 条生成记录")

    # Search bar
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        search_query = st.text_input(
            "搜索",
            placeholder="输入姓名或护照号搜索...",
            key="history_search",
            label_visibility="collapsed",
        )
    with search_col2:
        search_btn = st.button("🔍 搜索", use_container_width=True)

    # Load records
    if search_query.strip():
        records = search_history(search_query, limit=100)
    else:
        records = read_history(limit=100)

    if not records:
        if search_query.strip():
            st.info(f"未找到匹配「{search_query}」的记录。")
        else:
            st.info("暂无生成记录。生成文档后自动记录。")
    else:
        st.caption(f"共 {len(records)} 条记录")

        # Build table data
        table_data = []
        for r in records:
            table_data.append([
                r.get("timestamp", ""),
                r.get("surname", ""),
                r.get("given_name", ""),
                r.get("passport_no", ""),
                r.get("template_name", ""),
                r.get("output_filename", ""),
            ])

        st.dataframe(
            table_data,
            column_config={
                0: st.column_config.TextColumn("时间", width="small"),
                1: st.column_config.TextColumn("姓", width="small"),
                2: st.column_config.TextColumn("名", width="small"),
                3: st.column_config.TextColumn("护照号", width="medium"),
                4: st.column_config.TextColumn("模板", width="medium"),
                5: st.column_config.TextColumn("输出文件名", width="large"),
            },
            hide_index=True,
            use_container_width=True,
        )

elif not selected_templates:
    st.info(
        "👈 请从左侧模板库中选择模板，或上传新的 .docx 文件开始使用。"
    )
else:
    # ---- Collect field classifications for all selected templates ----
    all_user_input: set = set()
    all_auto_generated: set = set()
    template_meta: List[dict] = []

    for tmpl in selected_templates:
        tpath = tmpl["path"]
        tid = tmpl.get("template_id")
        try:
            classified = classify_template_fields(tpath, template_id=tid)
        except Exception as e:
            st.error(f"扫描模板「{tmpl['display_name']}」失败：{e}")
            continue

        template_meta.append({
            **tmpl,
            "classification": classified,
        })
        all_user_input.update(classified["user_input_fields"])
        all_auto_generated.update(classified["auto_generated_fields"])

    if not template_meta:
        st.stop()

    # ---- Section 1: Context Base Fields ----
    st.subheader("✏️ 基础信息（所有模板共用）")

    ctx_cols = st.columns(4)
    user_info: Dict[str, str] = {}

    for i, field in enumerate(CONTEXT_BASE_FIELDS):
        with ctx_cols[i]:
            label = CONTEXT_FIELD_LABELS.get(field, field)
            if field == "到达日期":
                date_val = st.date_input(
                    label,
                    value=None,
                    format="YYYY-MM-DD",
                    key=f"ctx_{field}",
                )
                user_info[field] = date_val.strftime("%Y-%m-%d") if date_val else ""
            else:
                user_info[field] = st.text_input(
                    label,
                    key=f"ctx_{field}",
                    placeholder=f"请输入{field}",
                )

    st.info("📌 请输入标准日期格式：YYYY-MM-DD，例如 2026-06-23")

    # ---- Section 2: Additional User Input Fields ----
    if all_user_input:
        st.subheader(f"✏️ 补充信息（{len(all_user_input)} 个字段）")

        # Only show fields NOT in context base fields
        extra_fields = sorted(all_user_input - set(CONTEXT_BASE_FIELDS))

        if extra_fields:
            cols = st.columns(2)
            for i, field in enumerate(extra_fields):
                with cols[i % 2]:
                    user_info[field] = st.text_input(
                        field,
                        key=f"extra_{field}",
                        placeholder=f"请输入{field}",
                    )

    # ---- Auto-generated Fields (hidden from user, shown in expander) ----
    if all_auto_generated:
        with st.expander(
            f"🤖 自动生成字段（共 {len(all_auto_generated)} 个，已隐藏）"
        ):
            st.caption(
                "以下字段由规则插件自动计算，无需用户填写。"
            )
            shown = sorted(all_auto_generated)
            st.text(", ".join(shown))

    # ---- Section 3: Generate ----
    st.divider()

    batch_count = len(template_meta)
    btn_label = (
        f"🚀 生成 {batch_count} 份文档"
        if batch_count > 1
        else "🚀 生成已填写文档"
    )

    if st.button(btn_label, type="primary", use_container_width=True):
        # ---- 必填字段校验 ------------------------------------------------
        missing_required = validate_required_fields(user_info)
        if missing_required:
            for err in missing_required:
                st.error(f"❌ {err}")
            st.stop()

        success_count = 0
        results: List[dict] = []

        for tmpl in template_meta:
            tpath = tmpl["path"]
            tname = tmpl["display_name"]
            tid = tmpl.get("template_id")

            try:
                mapping = generate_mapping_for_template(
                    template_path=tpath,
                    user_info=user_info,
                    seed=seed_val,
                    template_id=tid,
                )

                # Write filled output
                with tempfile.NamedTemporaryFile(
                    delete=False, suffix=".docx"
                ) as out:
                    output_path = out.name

                fill_template(tpath, output_path, mapping)

                # Read back for download
                with open(output_path, "rb") as f:
                    output_bytes = f.read()

                results.append({
                    "name": tname,
                    "path": output_path,
                    "data": output_bytes,
                    "mapping": mapping,
                    "filename": _build_output_filename(
                        tname,
                        user_info.get("姓", ""),
                        user_info.get("名", ""),
                    ),
                })
                success_count += 1

                # 记录生成历史（CSV 兼容 + JSON 结构化日志）
                output_filename = _build_output_filename(
                    tname,
                    user_info.get("姓", ""),
                    user_info.get("名", ""),
                )
                log_generation_csv(
                    surname=user_info.get("姓", ""),
                    given_name=user_info.get("名", ""),
                    passport_no=user_info.get("护照号", ""),
                    template_name=tname,
                    output_filename=output_filename,
                )
                # v3.4 JSON 操作日志（含用户 + 完整字段映射）
                log_generation(
                    user=st.session_state.user or "unknown",
                    template=tname,
                    output_files=[output_path],
                    fields_used=mapping,
                )

            except ValueError as e:
                st.error(f"❌ {tname}: {e}")
            except Exception as e:
                st.error(f"❌ {tname}：未知错误 — {e}")

        # ---- Show Results ----
        if success_count > 0:
            st.success(
                f"✅ 成功生成 {success_count}/{batch_count} 份文档！"
            )

            if success_count == 1:
                r = results[0]
                st.download_button(
                    label=f"📥 下载 {r['filename']}",
                    data=r["data"],
                    file_name=r["filename"],
                    mime="application/"
                    "vnd.openxmlformats-officedocument."
                    "wordprocessingml.document",
                    use_container_width=True,
                )
                with st.expander("🔍 预览生成字段映射"):
                    st.json(r["mapping"])
            else:
                # Batch: ZIP download + individual downloads
                st.subheader("📥 下载")

                # ZIP all generated docs
                zip_bytes = _make_zip_bytes(
                    [r["path"] for r in results],
                    entry_names=[r["filename"] for r in results],
                )
                st.download_button(
                    label="📦 打包下载全部（ZIP）",
                    data=zip_bytes,
                    file_name="poco_generated_docs.zip",
                    mime="application/zip",
                    use_container_width=True,
                    key="dl_zip_all",
                )

                # Individual download buttons
                for r in results:
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.caption(r["name"])
                    with col2:
                        st.download_button(
                            label="📥 下载",
                            data=r["data"],
                            file_name=r["filename"],
                            mime="application/"
                            "vnd.openxmlformats-officedocument."
                            "wordprocessingml.document",
                            key=f"dl_{r['name']}",
                        )

                # Shared mapping preview
                with st.expander("🔍 预览全部字段映射"):
                    for r in results:
                        st.caption(r["name"])
                        st.json(r["mapping"])

# ---- Footer ------------------------------------------------------------------

st.divider()
st.caption(
    f"POCO v3.4 — 模板库：{len(st.session_state.saved_templates)} 个模板"
    f" | 规则分组：{len(list_rule_templates())} 组"
    f" | 操作日志：{get_log_count()} 条"
)
