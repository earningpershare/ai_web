"""
向後相容橋接層 — 保持舊 import 路徑可用。
實際邏輯已移至 agents/derived/ 套件。

Airflow DAG、backfill.py 中 `from agents import derived_metrics; derived_metrics.run(d)`
無需修改即可繼續使用。
"""

from .derived import run  # noqa: F401  re-export

__all__ = ["run"]
