"""
訂閱邏輯單元測試 — 直接測試 subscription_logic.py（無 FastAPI 依賴）

涵蓋：
  - get_active_subscription  — 狀態篩選、過期降級、self-heal
  - activate_subscription    — supersede 舊訂閱、建立新訂閱、更新 profile
  - check_can_purchase       — 方案升降級邏輯、取消後可重新訂閱
整合情境：
  - 取消後重新訂閱完整流程
  - 到期後自動降級
"""
import sys
import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, call

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "api"))

from subscription_logic import (
    get_active_subscription,
    activate_subscription,
    check_can_purchase,
)


# ── Mock 工廠 ─────────────────────────────────────────────────────────────────

def _fluent(data):
    """回傳支援 fluent chaining 的 mock，execute() 回傳 data"""
    m = MagicMock()
    m.execute.return_value = MagicMock(data=data)
    for method in ("select", "eq", "in_", "order", "limit", "maybe_single",
                   "update", "insert", "single"):
        getattr(m, method).return_value = m
    return m


def _make_sb(sub_rows=None, profile_data=None):
    """
    sub_rows:     list[dict] — user_subscriptions 查詢結果
    profile_data: dict|None — user_profiles 查詢結果
    """
    sb = MagicMock()

    def table_factory(name):
        tbl = MagicMock()
        if name == "user_subscriptions":
            m = _fluent(sub_rows or [])
            tbl.select.return_value = m
            tbl.update.return_value = _fluent([])
            tbl.insert.return_value = _fluent([])
        elif name == "user_profiles":
            m = _fluent(profile_data)
            tbl.select.return_value = m
            tbl.update.return_value = _fluent([])
        elif name == "subscription_events":
            tbl.insert.return_value = _fluent([])
        return tbl

    sb.table.side_effect = table_factory
    return sb


def _future(days=30):
    return (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()


def _past(days=1):
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


# ══════════════════════════════════════════════════════════════════════════════
# get_active_subscription
# ══════════════════════════════════════════════════════════════════════════════

class TestGetActiveSubscription:

    def test_returns_none_when_no_subscription(self):
        sb = _make_sb(sub_rows=[])
        assert get_active_subscription(sb, "u1") is None

    def test_returns_active_subscription_within_expiry(self):
        sub = {"plan": "pro", "status": "active", "started_at": "2026-01-01",
               "expires_at": _future(30)}
        sb = _make_sb(sub_rows=[sub], profile_data={"plan": "pro"})
        result = get_active_subscription(sb, "u1")
        assert result is not None
        assert result["plan"] == "pro"

    def test_cancelled_within_expiry_still_valid(self):
        """取消但未到期 → 仍回傳（到期前保留功能）"""
        sub = {"plan": "pro", "status": "cancelled", "started_at": "2026-01-01",
               "expires_at": _future(10)}
        sb = _make_sb(sub_rows=[sub], profile_data={"plan": "pro"})
        result = get_active_subscription(sb, "u1")
        assert result is not None
        assert result["status"] == "cancelled"

    def test_superseded_within_expiry_still_valid(self):
        sub = {"plan": "pro", "status": "superseded", "started_at": "2026-01-01",
               "expires_at": _future(5)}
        sb = _make_sb(sub_rows=[sub], profile_data={"plan": "pro"})
        assert get_active_subscription(sb, "u1") is not None

    def test_expired_returns_none(self):
        sub = {"plan": "pro", "status": "active", "started_at": "2026-01-01",
               "expires_at": _past(1)}
        sb = _make_sb(sub_rows=[sub], profile_data={"plan": "pro"})
        assert get_active_subscription(sb, "u1") is None

    def test_expired_triggers_profile_downgrade(self):
        """過期後應觸發 user_profiles.plan = 'free'"""
        sub = {"plan": "pro", "status": "active", "started_at": "2026-01-01",
               "expires_at": _past(1)}

        profile_updates = []
        sb = MagicMock()

        def table_factory(name):
            tbl = MagicMock()
            if name == "user_subscriptions":
                m = _fluent([sub])
                tbl.select.return_value = m
                tbl.update.return_value = _fluent([])
            elif name == "user_profiles":
                m = _fluent({"plan": "pro"})
                tbl.select.return_value = m
                def capture_update(data):
                    profile_updates.append(data)
                    return _fluent([])
                tbl.update.side_effect = capture_update
            elif name == "subscription_events":
                tbl.insert.return_value = _fluent([])
            return tbl

        sb.table.side_effect = table_factory
        get_active_subscription(sb, "u1")

        assert any(u.get("plan") == "free" for u in profile_updates), \
            "過期後應將 user_profiles.plan 降回 free"

    def test_no_expiry_date_returns_normally(self):
        """無到期日（lifetime）→ 正常回傳"""
        sub = {"plan": "pro", "status": "active", "started_at": "2026-01-01",
               "expires_at": None}
        sb = _make_sb(sub_rows=[sub], profile_data={"plan": "pro"})
        assert get_active_subscription(sb, "u1") is not None

    def test_self_heal_when_profile_lags(self):
        """profile.plan=free 但訂閱是 pro → 自動補正"""
        sub = {"plan": "pro", "status": "active", "started_at": "2026-01-01",
               "expires_at": _future(30)}
        profile_updates = []
        sb = MagicMock()

        def table_factory(name):
            tbl = MagicMock()
            if name == "user_subscriptions":
                m = _fluent([sub])
                tbl.select.return_value = m
                tbl.update.return_value = _fluent([])
            elif name == "user_profiles":
                m = _fluent({"plan": "free"})  # 落後
                tbl.select.return_value = m
                def capture(data):
                    profile_updates.append(data)
                    return _fluent([])
                tbl.update.side_effect = capture
            return tbl

        sb.table.side_effect = table_factory
        result = get_active_subscription(sb, "u1")
        assert result is not None
        assert any(u.get("plan") == "pro" for u in profile_updates), \
            "self-heal 應將 profile.plan 補正為 pro"


# ══════════════════════════════════════════════════════════════════════════════
# activate_subscription
# ══════════════════════════════════════════════════════════════════════════════

class TestActivateSubscription:

    def _run(self, is_periodic=False, plan="pro"):
        updates, inserts = [], []
        sb = MagicMock()
        tbl = MagicMock()

        def capture_update(data):
            updates.append(data)
            return tbl
        def capture_insert(data):
            inserts.append(data)
            return tbl

        tbl.update.side_effect = capture_update
        tbl.insert.side_effect = capture_insert
        tbl.eq.return_value = tbl
        tbl.in_.return_value = tbl
        tbl.execute.return_value = MagicMock(data=[])
        sb.table.return_value = tbl

        activate_subscription(sb, "u1", plan, "ORD1", "TRD1", 88, is_periodic)
        return updates, inserts

    def test_supersedes_old_subscriptions(self):
        updates, _ = self._run()
        assert {"status": "superseded"} in updates

    def test_creates_new_active_subscription(self):
        _, inserts = self._run()
        new_active = [i for i in inserts if isinstance(i, dict) and i.get("status") == "active"]
        assert len(new_active) == 1

    def test_updates_profile_plan(self):
        updates, _ = self._run(plan="ultimate")
        assert {"plan": "ultimate"} in updates

    def test_inserts_payment_event(self):
        _, inserts = self._run()
        events = [i for i in inserts if isinstance(i, dict) and i.get("event_type") == "payment_success"]
        assert len(events) == 1

    def test_periodic_expiry_is_35_days(self):
        _, inserts = self._run(is_periodic=True)
        sub = next(i for i in inserts if isinstance(i, dict) and i.get("status") == "active")
        expires_dt = datetime.fromisoformat(sub["expires_at"])
        days = (expires_dt - datetime.now(timezone.utc)).days
        assert 30 <= days <= 40

    def test_non_periodic_expiry_is_2099(self):
        _, inserts = self._run(is_periodic=False)
        sub = next(i for i in inserts if isinstance(i, dict) and i.get("status") == "active")
        assert "2099" in sub["expires_at"]


# ══════════════════════════════════════════════════════════════════════════════
# check_can_purchase
# ══════════════════════════════════════════════════════════════════════════════

class TestCheckCanPurchase:

    def _make(self, profile_plan, sub_status=None, profile_exists=True):
        sub_rows = [{"status": sub_status}] if sub_status else []
        profile_data = {"plan": profile_plan} if profile_exists else None
        return _make_sb(sub_rows=sub_rows, profile_data=profile_data)

    def test_invalid_plan_blocked(self):
        sb = self._make("free")
        allowed, reason = check_can_purchase(sb, "u1", "invalid_plan")
        assert not allowed
        assert "無效" in reason

    def test_missing_profile_blocked(self):
        sb = self._make("free", profile_exists=False)
        allowed, reason = check_can_purchase(sb, "u1", "pro")
        assert not allowed
        assert "找不到用戶資料" in reason

    def test_free_to_pro_allowed(self):
        sb = self._make("free")
        allowed, _ = check_can_purchase(sb, "u1", "pro")
        assert allowed

    def test_active_pro_blocks_repurchase(self):
        sb = self._make("pro", sub_status="active")
        allowed, reason = check_can_purchase(sb, "u1", "pro")
        assert not allowed
        assert "已經是此方案" in reason

    def test_cancelled_pro_allows_repurchase(self):
        """取消後 → 允許重新購買同方案"""
        sb = self._make("pro", sub_status="cancelled")
        allowed, _ = check_can_purchase(sb, "u1", "pro")
        assert allowed

    def test_ultimate_blocks_downgrade_to_pro(self):
        sb = self._make("ultimate", sub_status="active")
        allowed, _ = check_can_purchase(sb, "u1", "pro")
        assert not allowed

    def test_pro_allows_upgrade_to_ultimate(self):
        sb = self._make("pro", sub_status="active")
        allowed, _ = check_can_purchase(sb, "u1", "ultimate")
        assert allowed


# ══════════════════════════════════════════════════════════════════════════════
# 整合情境
# ══════════════════════════════════════════════════════════════════════════════

class TestLifecycle:

    def test_cancel_then_resubscribe(self):
        """取消 → 重新訂閱：舊 cancelled 應被 superseded，新 active 被建立"""
        updates, inserts = [], []
        sb = MagicMock()
        tbl = MagicMock()
        tbl.update.side_effect = lambda d: (updates.append(d), tbl)[1]
        tbl.insert.side_effect = lambda d: (inserts.append(d), tbl)[1]
        tbl.eq.return_value = tbl
        tbl.in_.return_value = tbl
        tbl.execute.return_value = MagicMock(data=[])
        sb.table.return_value = tbl

        activate_subscription(sb, "u1", "pro", "ORD2", "TRD2", 88, False)

        assert {"status": "superseded"} in updates, "cancelled 應被標為 superseded"
        new_active = [i for i in inserts if isinstance(i, dict) and i.get("status") == "active"]
        assert len(new_active) == 1, "應建立一筆新 active 訂閱"

    def test_expired_blocks_access_and_downgrades(self):
        """到期 → get_active_subscription 回傳 None，且觸發 free 降級"""
        sub = {"plan": "pro", "status": "active",
               "started_at": "2026-01-01", "expires_at": _past(3)}
        profile_updates = []

        sb = MagicMock()

        def table_factory(name):
            tbl = MagicMock()
            if name == "user_subscriptions":
                m = _fluent([sub])
                tbl.select.return_value = m
                tbl.update.return_value = _fluent([])
            elif name == "user_profiles":
                m = _fluent({"plan": "pro"})
                tbl.select.return_value = m
                def cap(d):
                    profile_updates.append(d)
                    return _fluent([])
                tbl.update.side_effect = cap
            elif name == "subscription_events":
                tbl.insert.return_value = _fluent([])
            return tbl

        sb.table.side_effect = table_factory

        result = get_active_subscription(sb, "u1")
        assert result is None
        assert any(u.get("plan") == "free" for u in profile_updates)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
