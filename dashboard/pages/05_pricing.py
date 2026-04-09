"""
方案與訂閱 — 三方案定價頁面 + 綠界付款
"""
import os

import streamlit as st
import requests as _requests

from auth import auth_sidebar, is_logged_in, has_plan, show_login_modal, current_plan, PLAN_LABEL

st.set_page_config(page_title="方案說明", page_icon="💎", layout="wide")
auth_sidebar()

API_URL = os.getenv("API_URL", "http://localhost:8000")
API_PUBLIC_URL = os.getenv("API_PUBLIC_URL", "https://api.16888u.com")

# ── 付款結果處理 ─────────────────────────────────────────────────────────────

if st.query_params.get("payment_failed"):
    msg = st.query_params.get("msg", "付款失敗，請稍後再試")
    st.query_params.clear()
    st.error(f"付款未完成：{msg}")

if st.query_params.get("payment_result"):
    st.query_params.clear()
    token = st.session_state.get("token", "")
    if token:
        try:
            r = _requests.get(
                f"{API_URL}/auth/me",
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if r.ok:
                data = r.json()
                st.session_state["plan"] = data["plan"]
                if data["plan"] != "free":
                    st.success(f"🎉 付款成功！您已升級為 **{PLAN_LABEL.get(data['plan'], data['plan'])}**")
                else:
                    st.warning("付款處理中，請稍後重新整理頁面確認")
        except Exception:
            pass

st.title("💎 方案說明")
st.caption("選擇適合您的方案，隨時可以升級")
st.divider()

cur_plan = current_plan()


def _checkout_url(plan_key: str) -> str:
    """回傳一鍵付款 URL，點擊即建立訂單並跳轉至綠界"""
    token = st.session_state.get("token", "")
    return f"{API_PUBLIC_URL}/payment/checkout?plan={plan_key}&token={token}"


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
            ✅ 市場快照（三大法人概覽）<br>
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
          <div style="color:#888;font-size:13px;margin-bottom:20px">信用卡自動扣款，隨時可取消</div>
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
    elif not is_logged_in():
        if st.button("登入後訂閱", key="_login_pro", use_container_width=True, type="primary"):
            show_login_modal()
    elif cur_plan == "ultimate":
        st.button("已擁有更高方案", key="_higher_pro", disabled=True, use_container_width=True)
    else:
        st.link_button("升級進階版 — NT$88/月", _checkout_url("pro"),
                       use_container_width=True, type="primary")

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
            NT$1,688
          </div>
          <div style="color:#888;font-size:13px;margin-bottom:20px">一次性買斷・永久有效</div>
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
    elif not is_logged_in():
        if st.button("登入後購買", key="_login_ult", use_container_width=True):
            show_login_modal()
    else:
        st.link_button("購買終極版 — NT$1,688", _checkout_url("ultimate"),
                       use_container_width=True, type="primary")

st.divider()

# ── 取消訂閱 ─────────────────────────────────────────────────────────────────

if is_logged_in() and cur_plan == "pro":
    with st.expander("⚙️ 管理訂閱"):
        st.markdown("**取消定期扣款**")
        st.caption("取消後仍可使用至當期到期日，到期後自動降回基礎版，不會再扣款。")
        if st.button("取消自動續扣", key="_btn_cancel_sub", type="secondary"):
            token = st.session_state.get("token", "")
            try:
                r = _requests.post(
                    f"{API_URL}/payment/cancel-subscription",
                    headers={"Authorization": f"Bearer {token}"},
                    timeout=15,
                )
                if r.ok:
                    st.success(r.json().get("message", "訂閱已取消"))
                else:
                    detail = r.json().get("detail", "取消失敗") if r.headers.get("content-type", "").startswith("application/json") else r.text
                    st.error(detail)
            except Exception as e:
                st.error(f"請求失敗：{e}")

st.divider()

# ── 優惠碼兌換 ───────────────────────────────────────────────────────────────

if is_logged_in() and cur_plan == "free":
    with st.expander("🎟️ 有優惠碼？在此兌換"):
        promo_input = st.text_input("輸入優惠碼", key="_promo_input", placeholder="例如：FRIEND2026")
        if st.button("兌換", key="_btn_redeem", use_container_width=True):
            if not promo_input:
                st.error("請輸入優惠碼")
            else:
                # 直接用現有的 register 後端 promo_code 邏輯不適合
                # 需要獨立的兌換端點，先顯示提示
                st.info("優惠碼兌換功能開發中，請聯繫管理員手動升級")

st.divider()

with st.expander("❓ 常見問題"):
    st.markdown(
        """
        **Q：付款方式？**
        A：使用信用卡付款（VISA / MasterCard / JCB），透過綠界科技安全處理。

        **Q：進階版可以取消嗎？**
        A：可以，訂閱期滿後不會自動續訂，無任何綁約。如需取消請聯繫管理員。

        **Q：終極版買斷是什麼意思？**
        A：一次性支付 NT$1,688，即可永久享有終極版所有功能，無需每月繳費。

        **Q：終極版的「深度交流」是什麼形式？**
        A：購買後將以 Email 提供專屬聯絡方式，可與版主進行文字交流，
        主題涵蓋市場觀察、籌碼解讀、網站技術等，但不含任何投資操作建議。

        **Q：資料來源是否可靠？**
        A：所有數據均直接源自台灣期貨交易所（TAIFEX）每日公開揭露資訊，
        本站僅做整理與視覺化呈現，不修改原始數據。

        **Q：付款安全嗎？**
        A：付款透過綠界科技（ECPay）處理，本站不會儲存任何信用卡資訊。
        """
    )

st.divider()
st.caption(
    "⚠️ 本網站所有資料均源自 TAIFEX 公開資訊，不構成任何投資建議。"
    "終極版交流服務不涉及期貨投資建議，亦不具備期貨顧問資格。"
)
