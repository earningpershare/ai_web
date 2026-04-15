"""
個人履歷 — 溫彥竹 Andrew Wen
全特效展示頁面
"""
import streamlit as st

st.markdown("""
<style>
/* ── 全域 ───────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Noto+Sans+TC:wght@300;400;700;900&display=swap');

.resume-root * { box-sizing: border-box; }
.resume-root {
    font-family: 'Noto Sans TC', sans-serif;
    color: #e0e0e0;
    --neon-blue: #00d4ff;
    --neon-purple: #a855f7;
    --neon-green: #22d3ee;
    --neon-orange: #f97316;
    --glass-bg: rgba(255,255,255,0.04);
    --glass-border: rgba(255,255,255,0.08);
}

/* ── 粒子背景 ─────────────────────────────────────── */
.particles {
    position: fixed; top:0; left:0; width:100%; height:100%;
    pointer-events: none; z-index: 0; overflow: hidden;
}
.particle {
    position: absolute; border-radius: 50%;
    background: radial-gradient(circle, var(--neon-blue), transparent);
    opacity: 0.15;
    animation: floatUp linear infinite;
}
@keyframes floatUp {
    0%   { transform: translateY(100vh) scale(0); opacity: 0; }
    10%  { opacity: 0.15; }
    90%  { opacity: 0.15; }
    100% { transform: translateY(-10vh) scale(1); opacity: 0; }
}

/* ── Hero 區 ──────────────────────────────────────── */
.hero {
    position: relative;
    text-align: center;
    padding: 60px 20px 40px;
    margin-bottom: 40px;
    background: linear-gradient(135deg, #0a0a1a 0%, #1a0a2e 40%, #0a1a3e 70%, #0a0a1a 100%);
    border-radius: 20px;
    border: 1px solid var(--glass-border);
    overflow: hidden;
}
.hero::before {
    content: '';
    position: absolute; top: -50%; left: -50%;
    width: 200%; height: 200%;
    background: conic-gradient(from 0deg, transparent, var(--neon-blue), transparent, var(--neon-purple), transparent);
    animation: rotateBg 8s linear infinite;
    opacity: 0.05;
}
@keyframes rotateBg {
    100% { transform: rotate(360deg); }
}

.hero-avatar {
    width: 130px; height: 130px;
    border-radius: 50%;
    border: 3px solid var(--neon-blue);
    box-shadow: 0 0 30px rgba(0,212,255,0.3), 0 0 60px rgba(0,212,255,0.1);
    margin: 0 auto 20px;
    background: linear-gradient(135deg, #1a2a4a, #2a1a3a);
    display: flex; align-items: center; justify-content: center;
    font-size: 52px;
    animation: pulseGlow 3s ease-in-out infinite;
    position: relative; z-index: 1;
}
@keyframes pulseGlow {
    0%, 100% { box-shadow: 0 0 30px rgba(0,212,255,0.3); }
    50%      { box-shadow: 0 0 50px rgba(0,212,255,0.5), 0 0 80px rgba(168,85,247,0.2); }
}

.hero-name {
    font-family: 'Orbitron', sans-serif;
    font-size: 42px; font-weight: 900;
    background: linear-gradient(90deg, var(--neon-blue), var(--neon-purple), var(--neon-green), var(--neon-blue));
    background-size: 300% 100%;
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    animation: gradientShift 4s ease infinite;
    margin-bottom: 8px;
    position: relative; z-index: 1;
}
@keyframes gradientShift {
    0%   { background-position: 0% 50%; }
    50%  { background-position: 100% 50%; }
    100% { background-position: 0% 50%; }
}

.hero-title {
    font-size: 18px; color: #aaa;
    letter-spacing: 4px; text-transform: uppercase;
    position: relative; z-index: 1;
    margin-bottom: 16px;
}

.typing-wrap {
    font-family: 'Orbitron', sans-serif;
    font-size: 15px; color: var(--neon-green);
    position: relative; z-index: 1;
    margin-bottom: 20px;
}
.typing-text {
    display: inline-block;
    overflow: hidden;
    white-space: nowrap;
    border-right: 2px solid var(--neon-green);
    animation: typewriter 3.5s steps(40) 1s forwards, blink 0.75s step-end infinite;
    width: 0;
}
@keyframes typewriter { to { width: 100%; } }
@keyframes blink {
    50% { border-color: transparent; }
}

/* 標籤 */
.hero-tags {
    display: flex; flex-wrap: wrap; justify-content: center; gap: 10px;
    position: relative; z-index: 1;
    margin-top: 20px;
}
.hero-tag {
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 13px; font-weight: 700;
    border: 1px solid; color: #fff;
    animation: fadeSlideUp 0.6s ease both;
    transition: transform 0.3s, box-shadow 0.3s;
}
.hero-tag:hover { transform: translateY(-3px) scale(1.05); }
.hero-tag:nth-child(1) { border-color: var(--neon-blue); background: rgba(0,212,255,0.1); box-shadow: 0 0 15px rgba(0,212,255,0.15); animation-delay: 0.2s; }
.hero-tag:nth-child(2) { border-color: var(--neon-purple); background: rgba(168,85,247,0.1); box-shadow: 0 0 15px rgba(168,85,247,0.15); animation-delay: 0.35s; }
.hero-tag:nth-child(3) { border-color: var(--neon-green); background: rgba(34,211,238,0.1); box-shadow: 0 0 15px rgba(34,211,238,0.15); animation-delay: 0.5s; }
.hero-tag:nth-child(4) { border-color: var(--neon-orange); background: rgba(249,115,22,0.1); box-shadow: 0 0 15px rgba(249,115,22,0.15); animation-delay: 0.65s; }
.hero-tag:nth-child(5) { border-color: #ec4899; background: rgba(236,72,153,0.1); box-shadow: 0 0 15px rgba(236,72,153,0.15); animation-delay: 0.8s; }
.hero-tag:nth-child(6) { border-color: #facc15; background: rgba(250,204,21,0.1); box-shadow: 0 0 15px rgba(250,204,21,0.15); animation-delay: 0.95s; }

@keyframes fadeSlideUp {
    from { opacity:0; transform: translateY(20px); }
    to   { opacity:1; transform: translateY(0); }
}

/* ── Section 標題 ─────────────────────────────────── */
.section-title {
    font-family: 'Orbitron', sans-serif;
    font-size: 22px; font-weight: 700;
    color: #fff;
    margin: 50px 0 24px;
    padding-left: 16px;
    border-left: 4px solid var(--neon-blue);
    position: relative;
}
.section-title::after {
    content: '';
    position: absolute; bottom: -8px; left: 16px;
    width: 60px; height: 2px;
    background: linear-gradient(90deg, var(--neon-blue), transparent);
}

/* ── 技能條 ───────────────────────────────────────── */
.skills-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
}
.skill-item {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 12px;
    padding: 16px 20px;
    transition: transform 0.3s, border-color 0.3s;
}
.skill-item:hover {
    transform: translateY(-2px);
    border-color: var(--neon-blue);
}
.skill-header {
    display: flex; justify-content: space-between; align-items: center;
    margin-bottom: 10px;
}
.skill-name { font-weight: 700; font-size: 14px; }
.skill-pct  { font-family: 'Orbitron', sans-serif; font-size: 13px; color: var(--neon-blue); }
.skill-bar  {
    height: 6px; border-radius: 3px;
    background: rgba(255,255,255,0.06);
    overflow: hidden;
}
.skill-fill {
    height: 100%; border-radius: 3px;
    animation: fillBar 1.5s ease forwards;
    width: 0;
}
@keyframes fillBar { to { width: var(--pct); } }

/* ── 時間軸 ───────────────────────────────────────── */
.timeline { position: relative; padding-left: 32px; }
.timeline::before {
    content: '';
    position: absolute; left: 11px; top: 0; bottom: 0;
    width: 2px;
    background: linear-gradient(180deg, var(--neon-blue), var(--neon-purple), var(--neon-green));
}
.tl-item {
    position: relative;
    margin-bottom: 32px;
    animation: fadeSlideUp 0.6s ease both;
}
.tl-item:nth-child(1) { animation-delay: 0.1s; }
.tl-item:nth-child(2) { animation-delay: 0.25s; }
.tl-item:nth-child(3) { animation-delay: 0.4s; }
.tl-item:nth-child(4) { animation-delay: 0.55s; }
.tl-item:nth-child(5) { animation-delay: 0.7s; }

.tl-dot {
    position: absolute; left: -27px; top: 6px;
    width: 14px; height: 14px;
    border-radius: 50%;
    border: 2px solid var(--neon-blue);
    background: #0a0a1a;
    box-shadow: 0 0 10px rgba(0,212,255,0.4);
}
.tl-card {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 14px;
    padding: 22px 24px;
    transition: transform 0.3s, border-color 0.3s, box-shadow 0.3s;
}
.tl-card:hover {
    transform: translateX(6px);
    border-color: var(--neon-blue);
    box-shadow: 0 0 30px rgba(0,212,255,0.08);
}
.tl-date {
    font-family: 'Orbitron', sans-serif;
    font-size: 12px; color: var(--neon-blue);
    margin-bottom: 4px; letter-spacing: 1px;
}
.tl-company {
    font-size: 18px; font-weight: 900; color: #fff;
    margin-bottom: 2px;
}
.tl-role { font-size: 14px; color: var(--neon-purple); margin-bottom: 10px; }
.tl-desc { font-size: 13px; color: #aaa; line-height: 1.8; }
.tl-desc li { margin-bottom: 4px; }
.tl-highlight {
    color: var(--neon-green); font-weight: 700;
}

/* ── 專案卡片 ─────────────────────────────────────── */
.project-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
    gap: 20px;
}
.project-card {
    background: linear-gradient(135deg, rgba(0,212,255,0.03), rgba(168,85,247,0.03));
    border: 1px solid var(--glass-border);
    border-radius: 16px;
    padding: 28px;
    position: relative;
    overflow: hidden;
    transition: transform 0.3s, box-shadow 0.3s;
    animation: fadeSlideUp 0.6s ease both;
}
.project-card:nth-child(1) { animation-delay: 0.15s; }
.project-card:nth-child(2) { animation-delay: 0.3s; }
.project-card:nth-child(3) { animation-delay: 0.45s; }
.project-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 40px rgba(0,212,255,0.1);
    border-color: var(--neon-blue);
}
.project-card::before {
    content: '';
    position: absolute; top: 0; left: 0;
    width: 100%; height: 3px;
    background: linear-gradient(90deg, var(--neon-blue), var(--neon-purple));
}
.project-icon { font-size: 36px; margin-bottom: 12px; }
.project-name { font-size: 17px; font-weight: 900; color: #fff; margin-bottom: 8px; }
.project-desc { font-size: 13px; color: #aaa; line-height: 1.7; }
.project-tags { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 14px; }
.project-tags span {
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 11px;
    background: rgba(0,212,255,0.08);
    border: 1px solid rgba(0,212,255,0.15);
    color: var(--neon-blue);
}

/* ── 教育 ─────────────────────────────────────────── */
.edu-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
    gap: 16px;
}
.edu-card {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 14px;
    padding: 24px;
    text-align: center;
    transition: transform 0.3s;
    animation: fadeSlideUp 0.6s ease both;
}
.edu-card:hover { transform: translateY(-3px); }
.edu-icon { font-size: 40px; margin-bottom: 10px; }
.edu-school { font-size: 18px; font-weight: 900; color: #fff; }
.edu-dept { font-size: 14px; color: var(--neon-purple); margin: 4px 0; }
.edu-year { font-family: 'Orbitron', sans-serif; font-size: 12px; color: #666; }

/* ── 聯絡底部 ─────────────────────────────────────── */
.contact-bar {
    display: flex; justify-content: center; align-items: center;
    gap: 32px; flex-wrap: wrap;
    margin-top: 50px; padding: 30px;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 16px;
}
.contact-item {
    text-align: center;
    font-size: 13px; color: #aaa;
    transition: color 0.3s;
}
.contact-item:hover { color: var(--neon-blue); }
.contact-icon { font-size: 28px; display: block; margin-bottom: 6px; }

/* ── 浮動 stat ────────────────────────────────────── */
.stats-row {
    display: flex; justify-content: center; gap: 40px; flex-wrap: wrap;
    margin: 30px 0;
}
.stat-box {
    text-align: center;
    animation: fadeSlideUp 0.8s ease both;
}
.stat-box:nth-child(1) { animation-delay: 0.1s; }
.stat-box:nth-child(2) { animation-delay: 0.25s; }
.stat-box:nth-child(3) { animation-delay: 0.4s; }
.stat-box:nth-child(4) { animation-delay: 0.55s; }
.stat-num {
    font-family: 'Orbitron', sans-serif;
    font-size: 36px; font-weight: 900;
    background: linear-gradient(135deg, var(--neon-blue), var(--neon-purple));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
}
.stat-label { font-size: 12px; color: #666; margin-top: 4px; letter-spacing: 1px; }

/* Claude Code 特別標籤 */
.claude-badge {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 8px 20px;
    border-radius: 24px;
    background: linear-gradient(135deg, rgba(249,115,22,0.15), rgba(168,85,247,0.15));
    border: 1px solid rgba(249,115,22,0.3);
    font-family: 'Orbitron', sans-serif;
    font-size: 13px; font-weight: 700;
    color: var(--neon-orange);
    animation: pulseOrange 2s ease-in-out infinite;
    margin-top: 16px;
    position: relative; z-index: 1;
}
@keyframes pulseOrange {
    0%, 100% { box-shadow: 0 0 15px rgba(249,115,22,0.2); }
    50%      { box-shadow: 0 0 30px rgba(249,115,22,0.4), 0 0 60px rgba(168,85,247,0.15); }
}
</style>

<div class="resume-root">

<!-- 粒子背景 -->
<div class="particles">
""" + "".join([
    f'<div class="particle" style="left:{x}%;width:{s}px;height:{s}px;animation-duration:{d}s;animation-delay:{dl}s;"></div>'
    for x, s, d, dl in [
        (10,4,12,0),(25,6,15,3),(40,3,10,1),(55,5,18,5),(70,4,13,2),
        (85,7,16,4),(15,3,11,6),(45,5,14,7),(65,4,12,8),(80,6,17,1),
        (5,3,15,9),(35,4,11,3),(60,5,13,6),(90,3,16,2),(50,6,10,4),
    ]
]) + """
</div>

<!-- ▸ HERO ──────────────────────────────────────────── -->
<div class="hero">
    <div class="hero-avatar">👨‍💻</div>
    <div class="hero-name">溫彥竹</div>
    <div class="hero-title">Andrew Wen ・ Data & AI Engineer</div>
    <div class="typing-wrap">
        <span class="typing-text">&gt; 實踐家 — 將瑣事自動化，發掘數據價值，研究人性與交易</span>
    </div>
    <div class="claude-badge">⚡ Claude Code Power User — AI-Augmented Development</div>
    <div class="hero-tags">
        <span class="hero-tag">🔧 Data Pipeline</span>
        <span class="hero-tag">🤖 AI / ML</span>
        <span class="hero-tag">📊 金融數據</span>
        <span class="hero-tag">☁️ Cloud Infra</span>
        <span class="hero-tag">🐍 Python</span>
        <span class="hero-tag">⚡ Claude Code</span>
    </div>
</div>

<!-- ▸ STATS ─────────────────────────────────────────── -->
<div class="stats-row">
    <div class="stat-box"><div class="stat-num">4+</div><div class="stat-label">YEARS EXP</div></div>
    <div class="stat-box"><div class="stat-num">4</div><div class="stat-label">COMPANIES</div></div>
    <div class="stat-box"><div class="stat-num">10B+</div><div class="stat-label">DATA ROWS</div></div>
    <div class="stat-box"><div class="stat-num">835</div><div class="stat-label">TOEIC</div></div>
</div>

<!-- ▸ SKILLS ────────────────────────────────────────── -->
<div class="section-title">⚡ Tech Stack</div>
<div class="skills-grid">
    <div class="skill-item">
        <div class="skill-header"><span class="skill-name">🐍 Python (Django, Pandas, Airflow)</span><span class="skill-pct">95%</span></div>
        <div class="skill-bar"><div class="skill-fill" style="--pct:95%;background:linear-gradient(90deg,#00d4ff,#a855f7)"></div></div>
    </div>
    <div class="skill-item">
        <div class="skill-header"><span class="skill-name">🗄️ SQL (Oracle, Doris, PostgreSQL, MySQL)</span><span class="skill-pct">92%</span></div>
        <div class="skill-bar"><div class="skill-fill" style="--pct:92%;background:linear-gradient(90deg,#22d3ee,#00d4ff)"></div></div>
    </div>
    <div class="skill-item">
        <div class="skill-header"><span class="skill-name">⚡ Claude Code / AI-Augmented Dev</span><span class="skill-pct">90%</span></div>
        <div class="skill-bar"><div class="skill-fill" style="--pct:90%;background:linear-gradient(90deg,#f97316,#a855f7)"></div></div>
    </div>
    <div class="skill-item">
        <div class="skill-header"><span class="skill-name">📊 ETL / Data Pipeline Design</span><span class="skill-pct">93%</span></div>
        <div class="skill-bar"><div class="skill-fill" style="--pct:93%;background:linear-gradient(90deg,#a855f7,#ec4899)"></div></div>
    </div>
    <div class="skill-item">
        <div class="skill-header"><span class="skill-name">☁️ Cloud Infra (HCS, Docker, Linux)</span><span class="skill-pct">82%</span></div>
        <div class="skill-bar"><div class="skill-fill" style="--pct:82%;background:linear-gradient(90deg,#22d3ee,#22c55e)"></div></div>
    </div>
    <div class="skill-item">
        <div class="skill-header"><span class="skill-name">📈 金融量化 / Backtesting</span><span class="skill-pct">78%</span></div>
        <div class="skill-bar"><div class="skill-fill" style="--pct:78%;background:linear-gradient(90deg,#facc15,#f97316)"></div></div>
    </div>
    <div class="skill-item">
        <div class="skill-header"><span class="skill-name">🌐 JavaScript / Web Dev</span><span class="skill-pct">75%</span></div>
        <div class="skill-bar"><div class="skill-fill" style="--pct:75%;background:linear-gradient(90deg,#facc15,#22d3ee)"></div></div>
    </div>
    <div class="skill-item">
        <div class="skill-header"><span class="skill-name">📊 Power BI / Data Visualization</span><span class="skill-pct">80%</span></div>
        <div class="skill-bar"><div class="skill-fill" style="--pct:80%;background:linear-gradient(90deg,#ec4899,#a855f7)"></div></div>
    </div>
</div>

<!-- ▸ EXPERIENCE ────────────────────────────────────── -->
<div class="section-title">🚀 Experience</div>
<div class="timeline">

    <div class="tl-item">
        <div class="tl-dot"></div>
        <div class="tl-card">
            <div class="tl-date">2025.02 — PRESENT</div>
            <div class="tl-company">臻鼎科技 ZDT</div>
            <div class="tl-role">大數據開發工程師 ・ 外派深圳</div>
            <div class="tl-desc">
                <ul style="padding-left:18px;margin:0;">
                    <li>🏭 <span class="tl-highlight">百億級 SPI Terminal 專案</span> — Django + JS 構建大數據分析平台，從百億底層數據中精準過濾百萬級目標</li>
                    <li>⚙️ 針對 Oracle & Doris 開發 <span class="tl-highlight">Python 自動化框架</span>，標準化配置實現數據表與 SP 快速產出</li>
                    <li>☁️ <span class="tl-highlight">華為雲 (HCS)</span> 主要維運負責人 — VM 規劃、命名規範、安全組、負載均衡</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="tl-item">
        <div class="tl-dot"></div>
        <div class="tl-card">
            <div class="tl-date">2023.05 — 2025.02</div>
            <div class="tl-company">烽泰科技 Unicorn Fintech</div>
            <div class="tl-role">金融數據工程師</div>
            <div class="tl-desc">
                <ul style="padding-left:18px;margin:0;">
                    <li>🏗️ 導入 <span class="tl-highlight">SOLID 原則</span> 設計模組化需求系統，重複性報表開發時間縮短 50%+</li>
                    <li>📊 端到端 Data Pipeline — Python API 抓取 → 清洗 → Power BI 每日自動更新看板</li>
                    <li>🧠 建立<span class="tl-highlight">客戶入金行為預測模型</span>，轉化原始數據為商業價值</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="tl-item">
        <div class="tl-dot"></div>
        <div class="tl-card">
            <div class="tl-date">2022.11 — 2023.02</div>
            <div class="tl-company">大拇哥投顧 TAROBO</div>
            <div class="tl-role">量化與金融大數據工程師</div>
            <div class="tl-desc">
                <ul style="padding-left:18px;margin:0;">
                    <li>📈 運用 Python、.NET、VBA 開發<span class="tl-highlight">金融數據爬蟲與自動化報表</span>系統</li>
                    <li>🔬 支援量化研究團隊進行大數據分析</li>
                </ul>
            </div>
        </div>
    </div>

    <div class="tl-item">
        <div class="tl-dot"></div>
        <div class="tl-card">
            <div class="tl-date">2019.10 — 2022.10</div>
            <div class="tl-company">中國人壽 China Life</div>
            <div class="tl-role">ETL 工程師（研發替代役）</div>
            <div class="tl-desc">
                <ul style="padding-left:18px;margin:0;">
                    <li>🔍 開發 <span class="tl-highlight">XML Parsing 自動化工具</span>，解析 IBM DataStage Job 依賴關係 + 視覺化樹狀圖</li>
                    <li>📱 獨立開發投資選股 APP 並<span class="tl-highlight">上架 App Store</span>，串接券商 API 實現秒級即時行情</li>
                    <li>🧹 設計即時數據清洗機制，確保券商報價數據正確性</li>
                </ul>
            </div>
        </div>
    </div>
</div>

<!-- ▸ PROJECTS ──────────────────────────────────────── -->
<div class="section-title">🏆 Side Projects</div>
<div class="project-grid">
    <div class="project-card">
        <div class="project-icon">🚀</div>
        <div class="project-name">台指天空 SpaceTFX</div>
        <div class="project-desc">
            台灣期貨交易所籌碼分析平台。三大法人淨口數、選擇權 PCR、Max Pain、散戶多空比。
            從爬蟲到 DB 到前端全棧自建，使用 <strong style="color:#f97316">Claude Code</strong> 作為 AI 協作開發的核心工具。
        </div>
        <div class="project-tags">
            <span>Streamlit</span><span>FastAPI</span><span>PostgreSQL</span><span>Airflow</span><span>Docker</span><span>Claude Code</span>
        </div>
    </div>
    <div class="project-card">
        <div class="project-icon">📱</div>
        <div class="project-name">投資選股 APP</div>
        <div class="project-desc">
            獨立開發並上架 App Store 的投資選股應用。串接券商 API 實現秒級即時行情監控，
            內建即時數據清洗邏輯，確保繪圖指標正確性。
        </div>
        <div class="project-tags">
            <span>iOS</span><span>Swift</span><span>Broker API</span><span>Real-time</span><span>App Store</span>
        </div>
    </div>
    <div class="project-card">
        <div class="project-icon">🤖</div>
        <div class="project-name">AI Virtual Team</div>
        <div class="project-desc">
            基於 Claude Code 建立 AI 虛擬團隊架構：PM、Engineer、Reviewer、DevOps、QA、Researcher
            各角色自動協作，實現全流程 AI 輔助開發。
        </div>
        <div class="project-tags">
            <span>Claude Code</span><span>Agent Skills</span><span>finlab</span><span>Automation</span>
        </div>
    </div>
</div>

<!-- ▸ EDUCATION ─────────────────────────────────────── -->
<div class="section-title">🎓 Education</div>
<div class="edu-grid">
    <div class="edu-card" style="animation-delay:0.1s">
        <div class="edu-icon">🎓</div>
        <div class="edu-school">國立中山大學</div>
        <div class="edu-dept">資訊管理學系 ・ 碩士</div>
        <div class="edu-year">2017 — 2019</div>
    </div>
    <div class="edu-card" style="animation-delay:0.25s">
        <div class="edu-icon">🏫</div>
        <div class="edu-school">國立中央大學</div>
        <div class="edu-dept">資訊工程學系 ・ 學士</div>
        <div class="edu-year">2014 — 2017</div>
    </div>
    <div class="edu-card" style="animation-delay:0.4s">
        <div class="edu-icon">📜</div>
        <div class="edu-school">證券商高級業務員</div>
        <div class="edu-dept">金融投顧相關證照</div>
        <div class="edu-year">CERTIFIED</div>
    </div>
</div>

<!-- ▸ CONTACT ──────────────────────────────────────── -->
<div class="contact-bar">
    <div class="contact-item">
        <span class="contact-icon">📧</span>
        somehandisfrank@gmail.com
    </div>
    <div class="contact-item">
        <span class="contact-icon">📱</span>
        0921-089-367
    </div>
    <div class="contact-item">
        <span class="contact-icon">📍</span>
        新竹・台北・台中・高雄
    </div>
    <div class="contact-item">
        <span class="contact-icon">🌐</span>
        16888u.com
    </div>
</div>

<div style="text-align:center;margin-top:30px;padding-bottom:30px;">
    <span style="font-size:12px;color:#333;letter-spacing:2px;">BUILT WITH ⚡ CLAUDE CODE × STREAMLIT</span>
</div>

</div>
""", unsafe_allow_html=True)
