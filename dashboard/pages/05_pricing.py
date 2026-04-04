"""
方案與訂閱 — 三方案定價頁面
"""
import streamlit as st
from auth import auth_sidebar, is_logged_in, has_plan, show_login_modal, current_plan, PLAN_LABEL

st.set_page_config(page_title="方案說明", page_icon="💎", layout="wide")
auth_sidebar()

st.title("💎 方案說明")
st.caption("選擇適合您的方案，隨時可以升級或取消")
st.divider()

cur_plan = current_plan()

# ── 三欄定價卡 ────────────────────────────────────────────────────────────────

col_free, col_pro, col_ult = st.columns(3)

# ─ 基礎版 ─
with col_free:
    is_current = cur_plan == "free"
    st.markdown(
        f"""
        <div style="
            border: 2px solid {'#4f8ef7' if is_current else '#333'};
            border-radius: 12px; padding: 28px 20px; text-align: center;
            background: {'#0a1628' if is_current else '#111'};
            height: 100%;
        ">
          <div style="font-size:36px">🟢</div>
          <h2 style="color:#e0e0e0;margin:12px 0 4px">基礎版</h2>
          <div style="font-size:32px;font-weight:bold;color:#e0e0e0;margin:8px 0">
            免費
          </div>
          <div style="color:#888;font-size:13px;margin-bottom:20px">永久免費</div>
          <hr style="border-color:#333;margin:16px 0">
          <div style="text-align:left;color:#ccc;font-size:14px;line-height:2.2">
            ✅ 系統運作狀態<br>
            ✅ 最新資料日期查詢<br>
            ✅ 隱私權政策<br>
            🔒 選擇權資金地圖<br>
            🔒 市場進階分析<br>
            🔒 每日籌碼報告 Email<br>
            🔒 版主深度交流
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if is_current and is_logged_in():
        st.button("目前方案", key="_cur_free", disabled=True, use_container_width=True)
    elif not is_logged_in():
        if st.button("免費註冊", key="_reg_free", use_container_width=True):
            show_login_modal()

# ─ 進階版 ─
with col_pro:
    is_current = cur_plan == "pro"
    st.markdown(
        f"""
        <div style="
            border: 2px solid {'#4f8ef7' if is_current else '#4f8ef755'};
            border-radius: 12px; padding: 28px 20px; text-align: center;
            background: {'#0a1628' if is_current else '#0d1a2e'};
            height: 100%;
        ">
          <div style="font-size:36px">🔵</div>
          <h2 style="color:#4f8ef7;margin:12px 0 4px">進階版</h2>
          <div style="font-size:32px;font-weight:bold;color:#4f8ef7;margin:8px 0">
            NT$88<span style="font-size:16px;color:#888"> / 月</span>
          </div>
          <div style="color:#888;font-size:13px;margin-bottom:20px">隨時取消，無綁約</div>
          <hr style="border-color:#1e3a5f;margin:16px 0">
          <div style="text-align:left;color:#ccc;font-size:14px;line-height:2.2">
            ✅ 基礎版所有功能<br>
            ✅ 選擇權資金地圖（完整）<br>
            ✅ 市場進階分析（完整）<br>
            ✅ 每日籌碼觀察報告 Email<br>
            ✅ 歷史資料完整查詢<br>
            🔒 版主深度交流
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if is_current:
        st.button("目前方案", key="_cur_pro", disabled=True, use_container_width=True)
    else:
        st.button(
            "即將開放訂閱" if not is_logged_in() else "升級進階版（即將開放）",
            key="_sub_pro",
            use_container_width=True,
            type="primary",
            disabled=True,
        )
        st.caption("目前可使用優惠碼 **LAUNCH2026** 於註冊時免費體驗一個月")

# ─ 終極版 ─
with col_ult:
    is_current = cur_plan == "ultimate"
    st.markdown(
        f"""
        <div style="
            border: 2px solid {'#f5a623' if is_current else '#f5a62355'};
            border-radius: 12px; padding: 28px 20px; text-align: center;
            background: {'#1a1000' if is_current else '#14100a'};
            height: 100%;
        ">
          <div style="font-size:36px">🏆</div>
          <h2 style="color:#f5a623;margin:12px 0 4px">終極版</h2>
          <div style="font-size:32px;font-weight:bold;color:#f5a623;margin:8px 0">
            NT$1,688<span style="font-size:16px;color:#888"> / 月</span>
          </div>
          <div style="color:#888;font-size:13px;margin-bottom:20px">含一對一深度交流</div>
          <hr style="border-color:#3d2800;margin:16px 0">
          <div style="text-align:left;color:#ccc;font-size:14px;line-height:2.2">
            ✅ 進階版所有功能<br>
            ✅ 與版主一對一深度交流<br>
            ✅ 市場時事探討（不限次數）<br>
            ✅ 網站技術架構討論<br>
            ✅ 優先回覆與客製化分析<br>
            ✅ 未來新功能搶先體驗
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
    if is_current:
        st.button("目前方案", key="_cur_ult", disabled=True, use_container_width=True)
    else:
        st.button(
            "即將開放訂閱",
            key="_sub_ult",
            use_container_width=True,
            disabled=True,
        )
        st.caption("目前可使用優惠碼 **ULTIMATE88** 於註冊時免費體驗一個月")

st.divider()

# ── 優惠碼說明 ────────────────────────────────────────────────────────────────

with st.expander("🎟️ 優惠碼使用說明"):
    st.markdown(
        """
        - 優惠碼請於**註冊時填入**，可解鎖對應方案一個月免費體驗
        - 目前有效優惠碼：`LAUNCH2026`（進階版）、`ULTIMATE88`（終極版）
        - 優惠碼有使用次數限制，先搶先得
        - 優惠期間結束後若不續訂，自動退回基礎版（免費），不會自動扣款
        """
    )

with st.expander("❓ 常見問題"):
    st.markdown(
        """
        **Q：付款方式？**
        A：目前金流串接建置中，正式開放後將支援信用卡、轉帳等常見方式。

        **Q：可以取消嗎？**
        A：可以，訂閱期滿後不會自動續訂，無任何綁約。

        **Q：終極版的「深度交流」是什麼形式？**
        A：訂閱後將以 Email 提供專屬聯絡方式，可與版主進行文字交流，
        主題涵蓋市場觀察、籌碼解讀、網站技術等，但不含任何投資操作建議。

        **Q：資料來源是否可靠？**
        A：所有數據均直接源自台灣期貨交易所（TAIFEX）每日公開揭露資訊，
        本站僅做整理與視覺化呈現，不修改原始數據。
        """
    )

st.divider()
st.caption(
    "⚠️ 本網站所有資料均源自 TAIFEX 公開資訊，不構成任何投資建議。"
    "終極版交流服務不涉及期貨投資建議，亦不具備期貨顧問資格。"
)
