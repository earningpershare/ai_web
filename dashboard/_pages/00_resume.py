"""
個人履歷 — 溫彥竹 Andrew Wen
全特效展示頁面（分段渲染避免 Streamlit HTML 截斷）
"""
import streamlit as st

# ── 共用 CSS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Noto+Sans+TC:wght@300;400;700;900&display=swap');

.r * { box-sizing: border-box; }
.r {
    font-family: 'Noto Sans TC', sans-serif;
    color: #e0e0e0;
    --nb: #00d4ff; --np: #a855f7; --ng: #22d3ee; --no: #f97316;
    --gb: rgba(255,255,255,0.04); --gd: rgba(255,255,255,0.08);
}

/* 粒子 */
.particles { position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;overflow:hidden; }
.pt { position:absolute;border-radius:50%;background:radial-gradient(circle,var(--nb),transparent);opacity:0.12;animation:fU linear infinite; }
@keyframes fU { 0%{transform:translateY(100vh) scale(0);opacity:0}10%{opacity:.12}90%{opacity:.12}100%{transform:translateY(-10vh) scale(1);opacity:0} }

/* Hero */
.hero { position:relative;text-align:center;padding:60px 20px 40px;margin-bottom:40px;background:linear-gradient(135deg,#0a0a1a 0%,#1a0a2e 40%,#0a1a3e 70%,#0a0a1a 100%);border-radius:20px;border:1px solid var(--gd);overflow:hidden; }
.hero::before { content:'';position:absolute;top:-50%;left:-50%;width:200%;height:200%;background:conic-gradient(from 0deg,transparent,var(--nb),transparent,var(--np),transparent);animation:rb 8s linear infinite;opacity:.05; }
@keyframes rb { 100%{transform:rotate(360deg)} }
.ha { width:130px;height:130px;border-radius:50%;border:3px solid var(--nb);box-shadow:0 0 30px rgba(0,212,255,.3),0 0 60px rgba(0,212,255,.1);margin:0 auto 20px;background:linear-gradient(135deg,#1a2a4a,#2a1a3a);display:flex;align-items:center;justify-content:center;font-size:52px;animation:pg 3s ease-in-out infinite;position:relative;z-index:1; }
@keyframes pg { 0%,100%{box-shadow:0 0 30px rgba(0,212,255,.3)}50%{box-shadow:0 0 50px rgba(0,212,255,.5),0 0 80px rgba(168,85,247,.2)} }
.hn { font-family:'Orbitron',sans-serif;font-size:42px;font-weight:900;background:linear-gradient(90deg,var(--nb),var(--np),var(--ng),var(--nb));background-size:300% 100%;-webkit-background-clip:text;-webkit-text-fill-color:transparent;animation:gs 4s ease infinite;margin-bottom:8px;position:relative;z-index:1; }
@keyframes gs { 0%{background-position:0% 50%}50%{background-position:100% 50%}100%{background-position:0% 50%} }
.ht { font-size:18px;color:#aaa;letter-spacing:4px;text-transform:uppercase;position:relative;z-index:1;margin-bottom:16px; }
.tw { font-family:'Orbitron',sans-serif;font-size:15px;color:var(--ng);position:relative;z-index:1;margin-bottom:20px; }
.tt { display:inline-block;overflow:hidden;white-space:nowrap;border-right:2px solid var(--ng);animation:tw 3.5s steps(40) 1s forwards,bk .75s step-end infinite;width:0; }
@keyframes tw { to{width:100%} }
@keyframes bk { 50%{border-color:transparent} }
.cb { display:inline-flex;align-items:center;gap:8px;padding:8px 20px;border-radius:24px;background:linear-gradient(135deg,rgba(249,115,22,.15),rgba(168,85,247,.15));border:1px solid rgba(249,115,22,.3);font-family:'Orbitron',sans-serif;font-size:13px;font-weight:700;color:var(--no);animation:po 2s ease-in-out infinite;margin-top:16px;position:relative;z-index:1; }
@keyframes po { 0%,100%{box-shadow:0 0 15px rgba(249,115,22,.2)}50%{box-shadow:0 0 30px rgba(249,115,22,.4),0 0 60px rgba(168,85,247,.15)} }
.tags { display:flex;flex-wrap:wrap;justify-content:center;gap:10px;position:relative;z-index:1;margin-top:20px; }
.tag { padding:6px 16px;border-radius:20px;font-size:13px;font-weight:700;border:1px solid;color:#fff;animation:fsu .6s ease both;transition:transform .3s,box-shadow .3s; }
.tag:hover { transform:translateY(-3px) scale(1.05); }
.tag:nth-child(1){border-color:var(--nb);background:rgba(0,212,255,.1);box-shadow:0 0 15px rgba(0,212,255,.15);animation-delay:.2s}
.tag:nth-child(2){border-color:var(--np);background:rgba(168,85,247,.1);box-shadow:0 0 15px rgba(168,85,247,.15);animation-delay:.35s}
.tag:nth-child(3){border-color:var(--ng);background:rgba(34,211,238,.1);box-shadow:0 0 15px rgba(34,211,238,.15);animation-delay:.5s}
.tag:nth-child(4){border-color:var(--no);background:rgba(249,115,22,.1);box-shadow:0 0 15px rgba(249,115,22,.15);animation-delay:.65s}
.tag:nth-child(5){border-color:#ec4899;background:rgba(236,72,153,.1);box-shadow:0 0 15px rgba(236,72,153,.15);animation-delay:.8s}
.tag:nth-child(6){border-color:#facc15;background:rgba(250,204,21,.1);box-shadow:0 0 15px rgba(250,204,21,.15);animation-delay:.95s}
@keyframes fsu { from{opacity:0;transform:translateY(20px)}to{opacity:1;transform:translateY(0)} }

/* Section Title */
.st2 { font-family:'Orbitron',sans-serif;font-size:22px;font-weight:700;color:#fff;margin:50px 0 24px;padding-left:16px;border-left:4px solid var(--nb);position:relative; }
.st2::after { content:'';position:absolute;bottom:-8px;left:16px;width:60px;height:2px;background:linear-gradient(90deg,var(--nb),transparent); }

/* Stats */
.sr { display:flex;justify-content:center;gap:40px;flex-wrap:wrap;margin:30px 0; }
.sb { text-align:center;animation:fsu .8s ease both; }
.sb:nth-child(1){animation-delay:.1s}.sb:nth-child(2){animation-delay:.25s}.sb:nth-child(3){animation-delay:.4s}.sb:nth-child(4){animation-delay:.55s}
.sn { font-family:'Orbitron',sans-serif;font-size:36px;font-weight:900;background:linear-gradient(135deg,var(--nb),var(--np));-webkit-background-clip:text;-webkit-text-fill-color:transparent; }
.sl { font-size:12px;color:#666;margin-top:4px;letter-spacing:1px; }

/* Skills */
.sg { display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px; }
.si { background:var(--gb);border:1px solid var(--gd);border-radius:12px;padding:16px 20px;transition:transform .3s,border-color .3s; }
.si:hover { transform:translateY(-2px);border-color:var(--nb); }
.sh { display:flex;justify-content:space-between;align-items:center;margin-bottom:10px; }
.skn { font-weight:700;font-size:14px; }
.skp { font-family:'Orbitron',sans-serif;font-size:13px;color:var(--nb); }
.skb { height:6px;border-radius:3px;background:rgba(255,255,255,.06);overflow:hidden; }
.skf { height:100%;border-radius:3px;animation:fb 1.5s ease forwards;width:0; }
@keyframes fb { to{width:var(--pct)} }

/* Timeline */
.tl { position:relative;padding-left:32px; }
.tl::before { content:'';position:absolute;left:11px;top:0;bottom:0;width:2px;background:linear-gradient(180deg,var(--nb),var(--np),var(--ng)); }
.ti { position:relative;margin-bottom:32px;animation:fsu .6s ease both; }
.ti:nth-child(1){animation-delay:.1s}.ti:nth-child(2){animation-delay:.25s}.ti:nth-child(3){animation-delay:.4s}.ti:nth-child(4){animation-delay:.55s}
.td2 { position:absolute;left:-27px;top:6px;width:14px;height:14px;border-radius:50%;border:2px solid var(--nb);background:#0a0a1a;box-shadow:0 0 10px rgba(0,212,255,.4); }
.tc { background:var(--gb);border:1px solid var(--gd);border-radius:14px;padding:22px 24px;transition:transform .3s,border-color .3s,box-shadow .3s; }
.tc:hover { transform:translateX(6px);border-color:var(--nb);box-shadow:0 0 30px rgba(0,212,255,.08); }
.tdt { font-family:'Orbitron',sans-serif;font-size:12px;color:var(--nb);margin-bottom:4px;letter-spacing:1px; }
.tcp { font-size:18px;font-weight:900;color:#fff;margin-bottom:2px; }
.trl { font-size:14px;color:var(--np);margin-bottom:10px; }
.tds { font-size:13px;color:#aaa;line-height:1.8; }
.tds li { margin-bottom:4px; }
.hl { color:var(--ng);font-weight:700; }

/* Projects */
.pg { display:grid;grid-template-columns:repeat(auto-fit,minmax(320px,1fr));gap:20px; }
.pc { background:linear-gradient(135deg,rgba(0,212,255,.03),rgba(168,85,247,.03));border:1px solid var(--gd);border-radius:16px;padding:28px;position:relative;overflow:hidden;transition:transform .3s,box-shadow .3s;animation:fsu .6s ease both; }
.pc:nth-child(1){animation-delay:.15s}.pc:nth-child(2){animation-delay:.3s}.pc:nth-child(3){animation-delay:.45s}
.pc:hover { transform:translateY(-4px);box-shadow:0 8px 40px rgba(0,212,255,.1);border-color:var(--nb); }
.pc::before { content:'';position:absolute;top:0;left:0;width:100%;height:3px;background:linear-gradient(90deg,var(--nb),var(--np)); }
.pi { font-size:36px;margin-bottom:12px; }
.pn { font-size:17px;font-weight:900;color:#fff;margin-bottom:8px; }
.pd { font-size:13px;color:#aaa;line-height:1.7; }
.pt2 { display:flex;flex-wrap:wrap;gap:6px;margin-top:14px; }
.pt2 span { padding:3px 10px;border-radius:12px;font-size:11px;background:rgba(0,212,255,.08);border:1px solid rgba(0,212,255,.15);color:var(--nb); }

/* Education */
.eg { display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px; }
.ec { background:var(--gb);border:1px solid var(--gd);border-radius:14px;padding:24px;text-align:center;transition:transform .3s;animation:fsu .6s ease both; }
.ec:hover { transform:translateY(-3px); }
.ei { font-size:40px;margin-bottom:10px; }
.es { font-size:18px;font-weight:900;color:#fff; }
.edp { font-size:14px;color:var(--np);margin:4px 0; }
.ey { font-family:'Orbitron',sans-serif;font-size:12px;color:#666; }

/* Contact */
.ctb { display:flex;justify-content:center;align-items:center;gap:32px;flex-wrap:wrap;margin-top:50px;padding:30px;background:var(--gb);border:1px solid var(--gd);border-radius:16px; }
.cti { text-align:center;font-size:13px;color:#aaa;transition:color .3s; }
.cti:hover { color:var(--nb); }
.ctic { font-size:28px;display:block;margin-bottom:6px; }
</style>
""", unsafe_allow_html=True)

# ── 粒子背景 ──────────────────────────────────────────────────────────────────
particles = "".join([
    f'<div class="pt" style="left:{x}%;width:{s}px;height:{s}px;animation-duration:{d}s;animation-delay:{dl}s;"></div>'
    for x, s, d, dl in [
        (10,4,12,0),(25,6,15,3),(40,3,10,1),(55,5,18,5),(70,4,13,2),
        (85,7,16,4),(15,3,11,6),(45,5,14,7),(65,4,12,8),(80,6,17,1),
        (5,3,15,9),(35,4,11,3),(60,5,13,6),(90,3,16,2),(50,6,10,4),
    ]
])
st.markdown(f'<div class="r"><div class="particles">{particles}</div></div>', unsafe_allow_html=True)

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="r"><div class="hero">
    <div class="ha">👨‍💻</div>
    <div class="hn">溫彥竹</div>
    <div class="ht">Andrew Wen ・ Data & AI Engineer</div>
    <div class="tw"><span class="tt">&gt; 實踐家 — 將瑣事自動化，發掘數據價值，研究人性與交易</span></div>
    <div class="cb">⚡ Claude Code Power User — AI-Augmented Development</div>
    <div class="tags">
        <span class="tag">🔧 Data Pipeline</span>
        <span class="tag">🤖 AI / ML</span>
        <span class="tag">📊 金融數據</span>
        <span class="tag">☁️ Cloud Infra</span>
        <span class="tag">🐍 Python</span>
        <span class="tag">⚡ Claude Code</span>
    </div>
</div></div>
""", unsafe_allow_html=True)

# ── Stats ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="r"><div class="sr">
    <div class="sb"><div class="sn">4+</div><div class="sl">YEARS EXP</div></div>
    <div class="sb"><div class="sn">4</div><div class="sl">COMPANIES</div></div>
    <div class="sb"><div class="sn">10B+</div><div class="sl">DATA ROWS</div></div>
    <div class="sb"><div class="sn">835</div><div class="sl">TOEIC</div></div>
</div></div>
""", unsafe_allow_html=True)

# ── Skills ────────────────────────────────────────────────────────────────────
st.markdown('<div class="r"><div class="st2">⚡ Tech Stack</div></div>', unsafe_allow_html=True)

skills = [
    ("🐍 Python (Django, Pandas, Airflow)", 95, "#00d4ff,#a855f7"),
    ("🗄️ SQL (Oracle, Doris, PostgreSQL, MySQL)", 92, "#22d3ee,#00d4ff"),
    ("⚡ Claude Code / AI-Augmented Dev", 90, "#f97316,#a855f7"),
    ("📊 ETL / Data Pipeline Design", 93, "#a855f7,#ec4899"),
    ("☁️ Cloud Infra (HCS, Docker, Linux)", 82, "#22d3ee,#22c55e"),
    ("📈 金融量化 / Backtesting", 78, "#facc15,#f97316"),
    ("🌐 JavaScript / Web Dev", 75, "#facc15,#22d3ee"),
    ("📊 Power BI / Data Visualization", 80, "#ec4899,#a855f7"),
]
skill_html = '<div class="r"><div class="sg">'
for name, pct, grad in skills:
    skill_html += f'''<div class="si">
        <div class="sh"><span class="skn">{name}</span><span class="skp">{pct}%</span></div>
        <div class="skb"><div class="skf" style="--pct:{pct}%;background:linear-gradient(90deg,{grad})"></div></div>
    </div>'''
skill_html += '</div></div>'
st.markdown(skill_html, unsafe_allow_html=True)

# ── Experience ────────────────────────────────────────────────────────────────
st.markdown('<div class="r"><div class="st2">🚀 Experience</div></div>', unsafe_allow_html=True)

jobs = [
    {
        "date": "2025.02 — PRESENT",
        "company": "臻鼎科技 ZDT",
        "role": "大數據開發工程師 ・ 外派深圳",
        "items": [
            ("🏭", "百億級 SPI Terminal 專案", " — Django + JS 構建大數據分析平台，從百億底層數據中精準過濾百萬級目標"),
            ("⚙️", "Python 自動化框架", " — 針對 Oracle & Doris 開發標準化配置，實現數據表與 SP 快速產出"),
            ("☁️", "華為雲 (HCS)", " 主要維運負責人 — VM 規劃、命名規範、安全組、負載均衡"),
        ]
    },
    {
        "date": "2023.05 — 2025.02",
        "company": "烽泰科技 Unicorn Fintech",
        "role": "金融數據工程師",
        "items": [
            ("🏗️", "SOLID 原則", " 設計模組化需求系統，重複性報表開發時間縮短 50%+"),
            ("📊", "端到端 Data Pipeline", " — Python API 抓取 → 清洗 → Power BI 每日自動更新看板"),
            ("🧠", "客戶入金行為預測模型", "，轉化原始數據為商業價值"),
        ]
    },
    {
        "date": "2022.11 — 2023.02",
        "company": "大拇哥投顧 TAROBO",
        "role": "量化與金融大數據工程師",
        "items": [
            ("📈", "金融數據爬蟲與自動化報表", " — Python、.NET、VBA 開發，支援量化研究團隊"),
        ]
    },
    {
        "date": "2019.10 — 2022.10",
        "company": "中國人壽 China Life",
        "role": "ETL 工程師（研發替代役）",
        "items": [
            ("🔍", "XML Parsing 自動化工具", " — 解析 IBM DataStage Job 依賴關係 + 視覺化樹狀圖"),
            ("📱", "投資選股 APP 上架 App Store", " — 串接券商 API 實現秒級即時行情監控"),
            ("🧹", "即時數據清洗機制", " — 確保券商報價數據正確性"),
        ]
    },
]

for job in jobs:
    items_html = ""
    for icon, hl, rest in job["items"]:
        items_html += f'<li>{icon} <span class="hl">{hl}</span>{rest}</li>'

    st.markdown(f"""
    <div class="r"><div class="tl"><div class="ti">
        <div class="td2"></div>
        <div class="tc">
            <div class="tdt">{job["date"]}</div>
            <div class="tcp">{job["company"]}</div>
            <div class="trl">{job["role"]}</div>
            <div class="tds"><ul style="padding-left:18px;margin:0;">{items_html}</ul></div>
        </div>
    </div></div></div>
    """, unsafe_allow_html=True)

# ── Projects ──────────────────────────────────────────────────────────────────
st.markdown('<div class="r"><div class="st2">🏆 Side Projects</div></div>', unsafe_allow_html=True)

projects = [
    {
        "icon": "🚀", "name": "台指天空 SpaceTFX",
        "desc": "台灣期貨交易所籌碼分析平台。三大法人淨口數、選擇權 PCR、Max Pain、散戶多空比。從爬蟲到 DB 到前端全棧自建，使用 <strong style='color:#f97316'>Claude Code</strong> 作為 AI 協作核心工具。",
        "tags": ["Streamlit", "FastAPI", "PostgreSQL", "Airflow", "Docker", "Claude Code"],
    },
    {
        "icon": "📱", "name": "投資選股 APP",
        "desc": "獨立開發並上架 App Store 的投資選股應用。串接券商 API 實現秒級即時行情監控，內建即時數據清洗邏輯。",
        "tags": ["iOS", "Swift", "Broker API", "Real-time", "App Store"],
    },
    {
        "icon": "🤖", "name": "AI Virtual Team",
        "desc": "基於 Claude Code 建立 AI 虛擬團隊架構：PM、Engineer、Reviewer、DevOps、QA、Researcher 各角色自動協作，實現全流程 AI 輔助開發。",
        "tags": ["Claude Code", "Agent Skills", "finlab", "Automation"],
    },
]

proj_html = '<div class="r"><div class="pg">'
for p in projects:
    tags_html = "".join(f"<span>{t}</span>" for t in p["tags"])
    proj_html += f'''<div class="pc">
        <div class="pi">{p["icon"]}</div>
        <div class="pn">{p["name"]}</div>
        <div class="pd">{p["desc"]}</div>
        <div class="pt2">{tags_html}</div>
    </div>'''
proj_html += '</div></div>'
st.markdown(proj_html, unsafe_allow_html=True)

# ── Education ─────────────────────────────────────────────────────────────────
st.markdown('<div class="r"><div class="st2">🎓 Education</div></div>', unsafe_allow_html=True)
st.markdown("""
<div class="r"><div class="eg">
    <div class="ec" style="animation-delay:.1s">
        <div class="ei">🎓</div>
        <div class="es">國立中山大學</div>
        <div class="edp">資訊管理學系 ・ 碩士</div>
        <div class="ey">2017 — 2019</div>
    </div>
    <div class="ec" style="animation-delay:.25s">
        <div class="ei">🏫</div>
        <div class="es">國立中央大學</div>
        <div class="edp">資訊工程學系 ・ 學士</div>
        <div class="ey">2014 — 2017</div>
    </div>
    <div class="ec" style="animation-delay:.4s">
        <div class="ei">📜</div>
        <div class="es">證券商高級業務員</div>
        <div class="edp">金融投顧相關證照</div>
        <div class="ey">CERTIFIED</div>
    </div>
</div></div>
""", unsafe_allow_html=True)

# ── Contact ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="r"><div class="ctb">
    <div class="cti"><span class="ctic">📧</span>somehandisfrank@gmail.com</div>
    <div class="cti"><span class="ctic">📱</span>0921-089-367</div>
    <div class="cti"><span class="ctic">📍</span>新竹・台北・台中・高雄</div>
    <div class="cti"><span class="ctic">🌐</span>16888u.com</div>
</div></div>
""", unsafe_allow_html=True)

st.markdown("""
<div style="text-align:center;margin-top:30px;padding-bottom:30px;">
    <span style="font-size:12px;color:#333;letter-spacing:2px;">BUILT WITH ⚡ CLAUDE CODE × STREAMLIT</span>
</div>
""", unsafe_allow_html=True)
