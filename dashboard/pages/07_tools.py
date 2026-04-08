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
            <p style="color:#666;font-size:12px">Google Play 或<br>GitHub 下載 APK</p>
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
            <p style="color:#666;font-size:12px">GitHub 下載<br>免安裝版</p>
        </div>
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

st.subheader("🤖 Claude Code 離線安裝教學")

st.markdown("在無法直接存取外網的電腦上安裝 Claude Code。")

with st.expander("**Step 1 — 在有網路的電腦打包安裝檔**", expanded=False):
    st.markdown(
        """
        在家裡或其他有網路的電腦上執行：

        ```bash
        # 1. 建立打包資料夾
        mkdir claude-code-offline && cd claude-code-offline

        # 2. 下載 Node.js Windows 安裝檔 (如目標是 Windows)
        curl -o node-v22-x64.msi https://nodejs.org/dist/v22.14.0/node-v22.14.0-x64.msi

        # 3. 打包 Claude Code（含依賴的完整方式）
        #    先全域安裝，再整個資料夾打包
        npm install -g @anthropic-ai/claude-code
        #    Windows: 複製 %APPDATA%\\npm\\node_modules\\@anthropic-ai 整個資料夾
        #    macOS/Linux: 複製 $(npm root -g)/@anthropic-ai 整個資料夾

        # 4. 把 node-v22-x64.msi + @anthropic-ai 資料夾放進 USB 或上傳
        ```
        """
    )

with st.expander("**Step 2 — 在目標電腦離線安裝**", expanded=False):
    st.markdown(
        """
        ```bash
        # 1. 安裝 Node.js（雙擊 MSI 安裝檔）

        # 2. 複製 @anthropic-ai 資料夾到全域 node_modules
        #    Windows: 複製到 %APPDATA%\\npm\\node_modules\\
        #    macOS/Linux: 複製到 $(npm root -g)/

        # 3. 建立全域指令連結
        npm link -g @anthropic-ai/claude-code
        ```

        安裝完成後執行 `claude --version` 確認。
        """
    )

with st.expander("**Step 3 — 設定代理與 API Key**", expanded=False):
    st.markdown(
        f"""
        開啟代理客戶端（v2rayN 等）連上本服務後：

        ```bash
        # 設定代理（v2rayN 預設 HTTP port）
        export HTTPS_PROXY=http://127.0.0.1:10809

        # 設定 Anthropic API Key
        export ANTHROPIC_API_KEY=sk-ant-your-key-here

        # 啟動 Claude Code
        claude
        ```

        **Windows PowerShell 版本：**
        ```powershell
        $env:HTTPS_PROXY = "http://127.0.0.1:10809"
        $env:ANTHROPIC_API_KEY = "sk-ant-your-key-here"
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
