"""
批次回補指定日期範圍的所有資料
用法：python backfill.py 2026-03-24 2026-03-28
"""

import sys
from datetime import date, timedelta

sys.path.insert(0, "/opt/crawler")

from agents import (
    taifex_futures,
    taifex_options,
    taifex_pcr,
    taifex_institutional,
    taifex_large_trader,
    data_validator,
    derived_metrics,
)


def date_range(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def run_date(d: date):
    print(f"\n{'='*50}")
    print(f"  回補日期: {d}  (weekday={d.weekday()})")
    print(f"{'='*50}")
    for agent in [
        taifex_futures,
        taifex_options,
        taifex_pcr,
        taifex_institutional,
        taifex_large_trader,
        derived_metrics,
        data_validator,
    ]:
        name = agent.__name__.split(".")[-1]
        try:
            agent.run(d)
            print(f"  [OK] {name}")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("用法: python backfill.py <start_date> <end_date>")
        print("例如: python backfill.py 2026-03-24 2026-03-28")
        sys.exit(1)

    start = date.fromisoformat(sys.argv[1])
    end = date.fromisoformat(sys.argv[2])

    from agents.market_calendar import is_trading_day

    all_weekdays = [d for d in date_range(start, end) if d.weekday() < 5]
    days = []
    for d in all_weekdays:
        if is_trading_day(d):
            days.append(d)
        else:
            print(f"  [SKIP] {d} 休市（假日/颱風假等），略過")

    if not days:
        print("區間內無交易日，結束。")
        sys.exit(0)

    print(f"準備回補 {len(days)} 個交易日: {days[0]} ~ {days[-1]}")

    for d in days:
        run_date(d)

    print("\n全部完成！")
