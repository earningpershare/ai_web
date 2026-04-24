"""
每日操作日誌頁面 — 公開可讀，管理員可新增 / 編輯 / 刪除
"""
import os
from datetime import date as _date
import streamlit as st
import requests as _requests
from auth import auth_sidebar, is_logged_in

auth_sidebar()

ADMIN_EMAIL = "ohmygot65@yahoo.com.tw"
API_URL = os.getenv("API_URL", "http://localhost:8000")

is_admin = is_logged_in() and st.session_state.get("email", "").lower() == ADMIN_EMAIL
token = st.session_state.get("token", "")
headers = {"Authorization": f"Bearer {token}"}

# 方向對應圖示與色彩
DIRECTION_BADGE = {
    "做多": ("🟢", "#27ae60"),
    "做空": ("🔴", "#e74c3c"),
    "觀望": ("⚪", "#7f8c8d"),
    "出場": ("🏳️", "#f39c12"),
}


# ── API 輔助 ──────────────────────────────────────────────────────────────────

def _api(method: str, endpoint: str, **kwargs):
    try:
        r = getattr(_requests, method)(
            f"{API_URL}{endpoint}", headers=headers, timeout=20, **kwargs
        )
        if r.ok:
            return r.json(), None
        return None, r.json().get("detail", r.text)
    except Exception as e:
        return None, str(e)


# ── 管理員：新增 / 編輯 Dialog ─────────────────────────────────────────────────

@st.dialog("新增 / 編輯每日操作", width="large")
def _op_dialog(existing: dict | None = None):
    """existing 為 None 時表示新增，否則為編輯"""
    d = existing or {}

    trade_date = st.date_input(
        "交易日期",
        value=_date.fromisoformat(d["trade_date"]) if d.get("trade_date") else _date.today(),
        key="_op_date",
    )
    title = st.text_input("標題", value=d.get("title", ""), key="_op_title")
    trigger = st.text_area(
        "觸發指標",
        value=d.get("trigger_indicators", "") or "",
        height=100,
        placeholder="例：外資期貨淨口數單日減少 2,000 口，PCR > 1.4",
        key="_op_trigger",
    )
    direction = st.selectbox(
        "方向",
        ["做多", "做空", "出場", "觀望"],
        index=["做多", "做空", "出場", "觀望"].index(d["direction"])
        if d.get("direction") in ["做多", "做空", "出場", "觀望"]
        else 3,
        key="_op_direction",
    )

    col_ep, col_ec = st.columns(2)
    with col_ep:
        entry_price_raw = st.number_input(
            "進場價格（留空表示未進場）",
            value=float(d["entry_price"]) if d.get("entry_price") is not None else 0.0,
            min_value=0.0,
            step=1.0,
            key="_op_entry_price",
        )
    with col_ec:
        entry_contracts_raw = st.number_input(
            "口數（留空表示未設定）",
            value=int(d["entry_contracts"]) if d.get("entry_contracts") is not None else 0,
            min_value=0,
            step=1,
            key="_op_contracts",
        )

    col_xp, col_pnl = st.columns(2)
    with col_xp:
        exit_price_raw = st.number_input(
            "出場價格（留空表示未出場）",
            value=float(d["exit_price"]) if d.get("exit_price") is not None else 0.0,
            min_value=0.0,
            step=1.0,
            key="_op_exit_price",
        )
    with col_pnl:
        pnl_raw = st.number_input(
            "損益（留空表示未出場）",
            value=float(d["pnl"]) if d.get("pnl") is not None else 0.0,
            step=100.0,
            key="_op_pnl",
        )

    pnl_note = st.text_input(
        "損益備註",
        value=d.get("pnl_note", "") or "",
        placeholder="例：+12,000（+0.6%）",
        key="_op_pnl_note",
    )
    content = st.text_area(
        "內文詳述",
        value=d.get("content", "") or "",
        height=200,
        key="_op_content",
    )

    col_pub, col_cancel = st.columns([1, 1])
    with col_pub:
        if st.button("發布", type="primary", use_container_width=True, key="_op_submit"):
            if not title:
                st.error("標題為必填")
                return
            payload = {
                "trade_date": str(trade_date),
                "title": title,
                "trigger_indicators": trigger or None,
                "direction": direction,
                "entry_price": entry_price_raw if entry_price_raw > 0 else None,
                "entry_contracts": entry_contracts_raw if entry_contracts_raw > 0 else None,
                "exit_price": exit_price_raw if exit_price_raw > 0 else None,
                "pnl": pnl_raw if pnl_raw != 0 else None,
                "pnl_note": pnl_note or None,
                "content": content or None,
                "is_published": True,
            }
            if existing:
                data, err = _api("put", f"/daily-ops/{existing['id']}", json=payload)
            else:
                data, err = _api("post", "/daily-ops", json=payload)

            if err:
                st.error(f"儲存失敗：{err}")
            else:
                st.success("已儲存！")
                st.session_state.pop("_ops_cache", None)
                st.rerun()
    with col_cancel:
        if st.button("取消", use_container_width=True, key="_op_cancel"):
            st.rerun()


# ── 頁面主體 ──────────────────────────────────────────────────────────────────

col_title, col_btn = st.columns([4, 1])
with col_title:
    st.title("📋 每日操作")
with col_btn:
    if is_admin:
        st.write("")
        if st.button("＋ 新增今日操作", type="primary", use_container_width=True, key="_new_op"):
            _op_dialog()

st.caption("依據籌碼訊號每日操作記錄，僅供參考，不構成投資建議")
st.divider()

# 載入日誌列表
if "_ops_cache" not in st.session_state:
    with st.spinner("載入中..."):
        data, err = _api("get", "/daily-ops?limit=60&offset=0")
    if err:
        st.error(f"載入失敗：{err}")
        st.stop()
    st.session_state["_ops_cache"] = data or []

ops = st.session_state.get("_ops_cache", [])

if not ops:
    st.info("目前尚無發布的操作日誌，敬請期待。")
    st.stop()

for op in ops:
    op_id = op["id"]
    trade_date_str = str(op.get("trade_date", ""))[:10]
    direction = op.get("direction") or "觀望"
    icon, color = DIRECTION_BADGE.get(direction, ("⚪", "#7f8c8d"))
    pnl_note = op.get("pnl_note") or ""
    trigger = op.get("trigger_indicators") or ""

    # 標題摘要列
    if is_admin:
        col_main, col_ops_btns = st.columns([5, 1])
    else:
        col_main = st.container()
        col_ops_btns = None

    with col_main:
        label = (
            f"{icon} **{op['title']}**"
            f"　<span style='color:{color};font-size:13px'>{direction}</span>"
            f"　`{trade_date_str}`"
        )
        if pnl_note:
            label += f"　`{pnl_note}`"

        with st.expander(op["title"], expanded=False):
            # 頂部資訊列
            meta_cols = st.columns(4)
            meta_cols[0].markdown(f"**日期**　{trade_date_str}")
            meta_cols[1].markdown(
                f"**方向**　<span style='color:{color}'>{icon} {direction}</span>",
                unsafe_allow_html=True,
            )
            entry_str = f"{op['entry_price']}" if op.get("entry_price") is not None else "—"
            contracts_str = f"{op['entry_contracts']} 口" if op.get("entry_contracts") is not None else "—"
            meta_cols[2].markdown(f"**進場**　{entry_str}　{contracts_str}")
            exit_str = f"{op['exit_price']}" if op.get("exit_price") is not None else "—"
            meta_cols[3].markdown(f"**出場**　{exit_str}")

            if pnl_note or op.get("pnl") is not None:
                pnl_val = f"NT$ {op['pnl']:,.0f}" if op.get("pnl") is not None else ""
                st.markdown(f"**損益**　{pnl_val}　{pnl_note}")

            if trigger:
                st.markdown("**觸發指標**")
                st.markdown(f"> {trigger}")

            if op.get("content"):
                st.markdown("---")
                st.markdown(op["content"])

    if is_admin and col_ops_btns:
        with col_ops_btns:
            st.write("")
            if st.button("編輯", key=f"_edit_op_{op_id}", use_container_width=True):
                _op_dialog(existing=op)
            if st.button("刪除", key=f"_del_op_{op_id}", use_container_width=True):
                _, err2 = _api("delete", f"/daily-ops/{op_id}")
                if err2:
                    st.error(f"刪除失敗：{err2}")
                else:
                    st.success("已刪除")
                    st.session_state.pop("_ops_cache", None)
                    st.rerun()
