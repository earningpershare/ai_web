# TaifexAI — 專案指南

台灣期貨交易所籌碼分析平台 (https://16888u.com)

## 架構

```
dashboard/   Streamlit 1.35 前端 (port 8501)
api/         FastAPI 後端 (port 8000)
airflow/     Apache Airflow 排程 (DAGs)
crawler/     資料爬蟲
postgres/    DB 初始化
deploy.sh    一鍵部署到 VPS
```

## 技術棧

- **前端**: Streamlit 1.35（注意：用 `@st.experimental_dialog` 非 `@st.dialog`）
- **後端**: FastAPI，所有 router 同時掛 `/endpoint` 和 `/v1/endpoint`
- **金融資料 DB**: PostgreSQL 16 (Docker local)
- **會員/Auth**: Supabase（個資與金融資料物理隔離）
- **支付**: 綠界科技 ECPay
- **排程**: Airflow (taifex_daily, taifex_report, payment_reconcile)
- **部署**: Docker Compose on Oracle Cloud VPS

## 部署

```bash
bash deploy.sh              # 部署 api + dashboard
bash deploy.sh all          # 全部重建
```

VPS: `opc@161.33.17.40`，路徑 `/home/opc/ai_web`

## 重要約定

- 頁面檔名用數字前綴：`01_`, `02_` ...（控制排序）
- 註解使用繁體中文
- Supabase 查詢用 `.maybe_single()`（不要用 `.single()`，空結果會拋異常）
- ECPay CheckMacValue 編碼：`quote_plus` 後需還原 `- _ . ! * ( )` 字元
- ECPay callback URL 必須用 `API_PUBLIC_URL`（不能用 Docker 內部 URL）
- Payment callback（OrderResultURL）是 POST，Streamlit 不接受 POST，需由 FastAPI 302 redirect
- `.env` 放 secrets，不可提交到 git

## 方案等級

free (0) → pro (1) → ultimate (2)

## Admin

管理員帳號：`ohmygot65@yahoo.com.tw`（09_admin.py 頁面）

## 虛擬團隊 Slash Commands

| 指令 | 角色 | 說明 |
|------|------|------|
| `/product` | 產品經理 | 提案、建 Issue、分析改進空間 |
| `/engineer` | 工程師 | 實作功能、修 bug |
| `/review` | Code Reviewer | 審查 code、安全檢查 |
| `/pm` | 專案經理 | 進度追蹤、週報、changelog |
| `/devops` | DevOps | 部署、監控、健康檢查 |
| `/qa` | 數據品質分析師 | 比對官網 vs DB、找聚合邏輯問題 |
| `/researcher` | AI 研究員 | 提出籌碼假設、用 finlab 回測驗證、發布研究文章 |
