"""
工具箱 — VPN 連線設定與 Claude Code 離線安裝
"""
import streamlit as st
from auth import auth_sidebar, require_plan

st.set_page_config(page_title="工具箱", page_icon="🧰", layout="wide")
auth_sidebar()
require_plan("pro")

st.title("🧰 工具箱")
st.caption("代理連線設定與開發工具離線安裝")
st.divider()

# ── VLESS 連線資訊 ───────────────────────────────────────────────────────────

VLESS_UUID = "1f21e008-779a-45ee-aae1-a1e6e46a879b"
VLESS_ADDR = "16888u.com"
VLESS_PORT = 443
VLESS_PATH = "/proxy-ws"

vless_uri = (
    f"vless://{VLESS_UUID}@{VLESS_ADDR}:{VLESS_PORT}"
    f"?encryption=none&security=tls&type=ws&host={VLESS_ADDR}&path=%2Fproxy-ws"
    f"#TaifexAI-Proxy"
)

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
        | **UUID** | `{VLESS_UUID}` |
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
            <p style="color:#888;font-size:13px">v2rayN</p>
            <p style="color:#666;font-size:12px">免安裝版 (144 MB)</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.link_button(
        "下載 v2rayN",
        f"{DOWNLOAD_BASE}/v2rayN-windows-64.zip",
        use_container_width=True,
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
        f"""
**Step 1** — 安裝 Node.js（雙擊下載的 MSI 安裝檔，一路 Next）

**Step 2** — 安裝 Claude Code（開啟 CMD 或 PowerShell）：
```
npm install -g anthropic-ai-claude-code-2.1.96.tgz
```

**Step 3** — 開啟 v2rayN 連上代理後，設定環境變數並啟動：

```powershell
# PowerShell
$env:HTTPS_PROXY = "http://127.0.0.1:10809"
$env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
claude
```

```bash
# Git Bash / WSL
export HTTPS_PROXY=http://127.0.0.1:10809
export ANTHROPIC_API_KEY=sk-ant-your-key-here
claude
```
        """
    )

st.divider()

# ── 注意事項 ──────────────────────────────────────────────────────────────────

st.markdown(
    """
    <div style="background:#1a1a2e;border:1px solid #333;border-radius:8px;padding:16px;margin-top:8px;">
        <h4 style="color:#e0e0e0;margin-top:0">⚠️ 注意事項</h4>
        <ul style="color:#aaa;font-size:14px;line-height:2;">
            <li>此代理僅供授權用戶個人開發使用</li>
            <li>請勿用於大量影片串流，以避免超出流量額度</li>
            <li>UUID 為個人專屬，請勿分享給他人</li>
            <li>如連線異常請聯繫管理員</li>
        </ul>
    </div>
    """,
    unsafe_allow_html=True,
)
