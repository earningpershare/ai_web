"""
工具箱 — VPN 連線設定與 Claude Code 離線安裝（每人專屬 UUID）
"""
import os

import streamlit as st
import requests as _requests

from auth import auth_sidebar, require_plan

auth_sidebar()
require_plan("pro")

# ── 取得個人 VLESS UUID ─────────────────────────────────────────────────────

API_URL = os.getenv("API_URL", "http://localhost:8000")


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

# ── VLESS 連線資訊 ───────────────────────────────────────────────────────────

VLESS_ADDR = "16888u.com"
VLESS_PORT = 443
VLESS_PATH = "/proxy-ws"

vless_uri = (
    f"vless://{user_uuid}@{VLESS_ADDR}:{VLESS_PORT}"
    f"?encryption=none&security=tls&type=ws&host={VLESS_ADDR}&path=%2Fproxy-ws"
    f"#TaifexAI-Proxy"
)

st.title("🧰 工具箱")
st.caption("代理連線設定與開發工具離線安裝")
st.divider()

st.subheader("🔗 代理連線")
st.markdown("透過 VLESS + WebSocket + TLS 加密通道，安全存取外部服務。")

# 連線參數表
col1, col2 = st.columns(2)
with col1:
    st.markdown(
        f"""
        | 參數 | 值 |
        |------|-----|
        | **協定** | VLESS |
        | **地址** | `{VLESS_ADDR}` |
        | **Port** | `{VLESS_PORT}` |
        | **UUID** | `{user_uuid}` |
        | **傳輸方式** | WebSocket |
        | **Path** | `{VLESS_PATH}` |
        | **TLS** | 開啟 |
        """
    )

with col2:
    st.markdown("**一鍵匯入連結**")
    st.code(vless_uri, language=None)
    st.markdown(
        """
        <small style="color:#888">
        複製上方連結，在客戶端 App 中選擇「從剪貼簿匯入」即可。
        </small>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# ── 客戶端下載 ───────────────────────────────────────────────────────────────

DOWNLOAD_BASE = "https://16888u.com/downloads"

st.subheader("📱 客戶端 App 下載")

c_ios, c_android, c_win, c_mac = st.columns(4)

with c_ios:
    st.markdown(
        """
        <div style="text-align:center;padding:16px;border:1px solid #333;border-radius:10px;">
            <div style="font-size:36px">🍎</div>
            <h4 style="margin:8px 0">iOS</h4>
            <p style="color:#888;font-size:13px">Shadowrocket</p>
            <p style="color:#666;font-size:12px">App Store 搜尋<br>"Shadowrocket"<br>(付費 US$2.99)</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c_android:
    st.markdown(
        """
        <div style="text-align:center;padding:16px;border:1px solid #333;border-radius:10px;">
            <div style="font-size:36px">🤖</div>
            <h4 style="margin:8px 0">Android</h4>
            <p style="color:#888;font-size:13px">v2rayNG</p>
            <p style="color:#666;font-size:12px">Google Play 搜尋<br>"v2rayNG"</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

with c_win:
    st.markdown(
        """
        <div style="text-align:center;padding:16px;border:1px solid #333;border-radius:10px;">
            <div style="font-size:36px">🪟</div>
            <h4 style="margin:8px 0">Windows</h4>
            <p style="color:#888;font-size:13px">v2rayN 一鍵安裝</p>
            <p style="color:#666;font-size:12px">下載 5 個檔案後<br>執行腳本自動設定</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button("Part 1 (45 MB)", f"{DOWNLOAD_BASE}/v2rayN-part-aa", use_container_width=True)
    st.link_button("Part 2 (45 MB)", f"{DOWNLOAD_BASE}/v2rayN-part-ab", use_container_width=True)
    st.link_button("Part 3 (45 MB)", f"{DOWNLOAD_BASE}/v2rayN-part-ac", use_container_width=True)
    st.link_button("Part 4 (8.3 MB)", f"{DOWNLOAD_BASE}/v2rayN-part-ad", use_container_width=True)
    st.link_button("setup-v2rayN.ps1", f"{DOWNLOAD_BASE}/setup-v2rayN.ps1", use_container_width=True, type="primary")
    st.markdown(
        """
        <small style="color:#888">
        將 5 個檔案放同一資料夾，右鍵 setup-v2rayN.ps1 →
        「用 PowerShell 執行」即可自動合併、解壓、設定。
        </small>
        """,
        unsafe_allow_html=True,
    )

with c_mac:
    st.markdown(
        """
        <div style="text-align:center;padding:16px;border:1px solid #333;border-radius:10px;">
            <div style="font-size:36px">🍏</div>
            <h4 style="margin:8px 0">macOS</h4>
            <p style="color:#888;font-size:13px">V2rayU / ClashX</p>
            <p style="color:#666;font-size:12px">GitHub 下載</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.divider()

# ── Claude Code 離線安裝 ──────────────────────────────────────────────────────

st.subheader("🤖 Claude Code 離線安裝")

st.markdown("在無法直接存取外網的電腦上安裝 Claude Code，下載以下兩個檔案即可。")

dl1, dl2 = st.columns(2)
with dl1:
    st.markdown(
        """
        <div style="text-align:center;padding:20px;border:1px solid #333;border-radius:10px;">
            <div style="font-size:36px">📦</div>
            <h4 style="margin:8px 0">Node.js v22 安裝檔</h4>
            <p style="color:#888;font-size:13px">Windows x64 MSI (30 MB)</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button(
        "下載 Node.js",
        f"{DOWNLOAD_BASE}/node-v22.14.0-x64.msi",
        use_container_width=True,
    )

with dl2:
    st.markdown(
        """
        <div style="text-align:center;padding:20px;border:1px solid #333;border-radius:10px;">
            <div style="font-size:36px">🤖</div>
            <h4 style="margin:8px 0">Claude Code v2.1.96</h4>
            <p style="color:#888;font-size:13px">npm 離線包 (18.5 MB)</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button(
        "下載 Claude Code",
        f"{DOWNLOAD_BASE}/anthropic-ai-claude-code-2.1.96.tgz",
        use_container_width=True,
    )

st.markdown("")

with st.expander("**安裝步驟**", expanded=True):
    st.markdown(
        """
**Step 1** — 雙擊 `node-v22.14.0-x64.msi`，一路 Next 安裝 Node.js

**Step 2** — 開啟 PowerShell，cd 到下載目錄，執行：
```powershell
npm install -g anthropic-ai-claude-code-2.1.96.tgz
```
> 這是離線安裝，不需要網路。裝完後 `claude --version` 驗證。

**Step 3** — 先確認 v2rayN 代理已啟動（系統匣右鍵 → 自動設定系統代理），然後：
```powershell
$env:HTTPS_PROXY = "http://127.0.0.1:10809"
$env:ANTHROPIC_API_KEY = "你的 API Key"
claude
```
> 每次開新的 PowerShell 都要重設環境變數。如果想永久設定：
> `[Environment]::SetEnvironmentVariable("HTTPS_PROXY", "http://127.0.0.1:10809", "User")`
> `[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "你的 API Key", "User")`
        """
    )

st.divider()

# ── 注意事項 ──────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:16px;margin-top:8px;">
        <h4 style="color:#e0e0e0;margin-top:0">⚠️ 注意事項</h4>
        <ul style="color:#aaa;font-size:14px;line-height:2;">
            <li>此代理僅供授權用戶個人使用</li>
            <li>請勿用於大量影片串流，以避免超出流量額度</li>
            <li>UUID 為個人專屬，請勿分享給他人</li>
            <li>如連線異常請聯繫管理員</li>
        </ul>
    </div>
    """,
    unsafe_allow_html=True,
)
