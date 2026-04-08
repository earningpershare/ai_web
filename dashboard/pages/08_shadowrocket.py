"""
Shadowrocket VPN — 一鍵匯入代理連線（每人專屬 UUID）
"""
import io
import base64
import os

import streamlit as st
import qrcode
import requests as _requests

from auth import auth_sidebar, require_plan

st.set_page_config(page_title="Shadowrocket VPN", page_icon="🚀", layout="wide")
auth_sidebar()
require_plan("pro")

# ── 取得個人 VLESS UUID ─────────────────────────────────────────────────────

API_URL = os.getenv("API_URL", "http://localhost:8000")
VLESS_ADDR = "16888u.com"
VLESS_PORT = 443
VLESS_PATH = "/proxy-ws"


def _get_my_vless_uuid() -> str | None:
    token = st.session_state.get("token", "")
    if not token:
        return None
    try:
        r = _requests.get(
            f"{API_URL}/auth/me",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if r.ok:
            return r.json().get("vless_uuid")
    except Exception:
        pass
    return None


user_uuid = _get_my_vless_uuid()
if not user_uuid:
    st.error("無法取得個人連線金鑰，請重新登入")
    st.stop()

VLESS_URI = (
    f"vless://{user_uuid}@{VLESS_ADDR}:{VLESS_PORT}"
    f"?encryption=none&security=tls&type=ws&host={VLESS_ADDR}&path=%2Fproxy-ws"
    f"#TaifexAI-Proxy"
)


def _make_qr_base64(data: str) -> str:
    """產生 QR Code 並回傳 base64 PNG"""
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="white", back_color="#0e1117")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()


# ── 頁面內容 ─────────────────────────────────────────────────────────────────

st.title("🚀 Shadowrocket VPN")
st.caption("掃碼或一鍵匯入，30 秒完成設定")
st.divider()

# ── QR Code + 一鍵匯入 ──────────────────────────────────────────────────────

col_qr, col_info = st.columns([1, 1], gap="large")

with col_qr:
    qr_b64 = _make_qr_base64(VLESS_URI)
    st.markdown(
        f"""
        <div style="text-align:center;padding:20px;">
            <img src="data:image/png;base64,{qr_b64}"
                 style="width:280px;height:280px;border-radius:12px;border:2px solid #333;" />
            <p style="color:#888;font-size:13px;margin-top:12px">
                Shadowrocket → 左上角 ＋ → 掃描 QR Code
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with col_info:
    st.markdown(
        """
        <div style="padding:12px 0;">
            <h3 style="color:#e0e0e0;margin-bottom:16px">📋 快速設定</h3>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("**方法一：掃描 QR Code**")
    st.markdown(
        """
        1. 開啟 Shadowrocket
        2. 點左上角 **＋**
        3. 選擇 **掃描 QR Code**
        4. 掃描左方 QR Code → 自動完成設定
        """,
    )

    st.markdown("**方法二：從剪貼簿匯入**")
    st.markdown("複製下方連結，回到 Shadowrocket 會自動偵測並詢問是否匯入。")
    st.code(VLESS_URI, language=None)

st.divider()

# ── 連線參數明細 ─────────────────────────────────────────────────────────────

with st.expander("🔧 手動設定參數（進階）", expanded=False):
    st.markdown(
        f"""
        | 參數 | 值 |
        |------|-----|
        | **類型** | VLESS |
        | **地址** | `{VLESS_ADDR}` |
        | **Port** | `{VLESS_PORT}` |
        | **UUID** | `{user_uuid}` |
        | **傳輸方式** | WebSocket |
        | **Path** | `{VLESS_PATH}` |
        | **TLS** | 開啟 |
        | **允許不安全** | 關閉 |
        """
    )

st.divider()

# ── 使用教學 ─────────────────────────────────────────────────────────────────

st.subheader("📖 使用教學")

step1, step2, step3 = st.columns(3)

with step1:
    st.markdown(
        """
        <div style="text-align:center;padding:20px;border:1px solid #333;border-radius:10px;height:100%;">
            <div style="font-size:40px">1️⃣</div>
            <h4 style="color:#e0e0e0;margin:12px 0 8px">安裝 App</h4>
            <p style="color:#aaa;font-size:14px;line-height:1.8">
                App Store 搜尋<br>
                <strong style="color:#4f8ef7">Shadowrocket</strong><br>
                (付費 US$2.99)<br>
                <span style="font-size:12px;color:#666">需使用非中國區 Apple ID</span>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with step2:
    st.markdown(
        """
        <div style="text-align:center;padding:20px;border:1px solid #333;border-radius:10px;height:100%;">
            <div style="font-size:40px">2️⃣</div>
            <h4 style="color:#e0e0e0;margin:12px 0 8px">匯入設定</h4>
            <p style="color:#aaa;font-size:14px;line-height:1.8">
                掃描上方 QR Code<br>
                或複製連結自動匯入<br>
                <strong style="color:#4f8ef7">零手動設定</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with step3:
    st.markdown(
        """
        <div style="text-align:center;padding:20px;border:1px solid #333;border-radius:10px;height:100%;">
            <div style="font-size:40px">3️⃣</div>
            <h4 style="color:#e0e0e0;margin:12px 0 8px">開啟連線</h4>
            <p style="color:#aaa;font-size:14px;line-height:1.8">
                點擊開關啟用 VPN<br>
                首次會要求 VPN 權限<br>
                <strong style="color:#4f8ef7">允許即可上網</strong>
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# ── 注意事項 ─────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:16px;margin-top:8px;">
        <h4 style="color:#e0e0e0;margin-top:0">⚠️ 注意事項</h4>
        <ul style="color:#aaa;font-size:14px;line-height:2;">
            <li>此代理僅供授權用戶個人使用</li>
            <li>請勿用於大量影片串流，以避免超出流量額度</li>
            <li>UUID 為個人專屬，請勿分享給他人</li>
            <li>如連線異常請聯繫管理員</li>
            <li>Shadowrocket 需使用非中國區 Apple ID 購買</li>
        </ul>
    </div>
    """,
    unsafe_allow_html=True,
)
