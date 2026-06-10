"""
竞品数据对比器 — 批量竞品快照对比，检测变化趋势

用法:
    from lib.competitor_checker import CompetitorChecker
    cc = CompetitorChecker()
    report = cc.batch_check(store, our_asin, competitor_asins)
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import Any


class CompetitorChecker:
    """竞品批量对比检查"""

    def __init__(
        self,
        snapshot_dir: str = "",
    ):
        if not snapshot_dir:
            snapshot_dir = str(Path(__file__).parent.parent.parent / "amazon-listings" / "_shared" / "competitor_snapshots")
        self.snapshot_dir = Path(snapshot_dir)

    def _load_snapshots(
        self, store: str, asin: str
    ) -> list[dict]:
        """加载某竞品的所有快照"""
        prefix = f"{store}__{asin}__"
        files = sorted(
            [
                f
                for f in self.snapshot_dir.iterdir()
                if f.name.startswith(prefix)
            ],
            reverse=True,
        )
        return [
            json.loads(f.read_text(encoding="utf-8"))
            for f in files
        ]

    def compare_two_snapshots(
        self, old: dict, new: dict
    ) -> dict[str, Any]:
        """对比两个快照的变化"""
        old_data = old.get("data", {})
        new_data = new.get("data", {})
        changes = {}

        for field in ["bsr", "price", "rating", "review_count"]:
            ov = old_data.get(field)
            nv = new_data.get(field)
            if ov is not None and nv is not None and ov != 0:
                pct = round((nv - ov) / ov * 100, 1)
                changes[field] = {
                    "old": ov,
                    "new": nv,
                    "change_pct": pct,
                }

        # 标题变化
        if old_data.get("title") != new_data.get("title"):
            changes["title_changed"] = True

        # 关键词变化
        old_kw = set(old_data.get("keywords", []))
        new_kw = set(new_data.get("keywords", []))
        if old_kw != new_kw:
            changes["keywords"] = {
                "added": list(new_kw - old_kw),
                "removed": list(old_kw - new_kw),
            }

        return changes

    def batch_check(
        self,
        store: str,
        our_asin: str,
        competitor_asins: list[str],
    ) -> dict[str, Any]:
        """
        批量检查竞品变化

        Returns:
            {competitor_asin: {latest_snapshot, changes_from_previous, ...}}
        """
        report: dict[str, Any] = {
            "our_asin": our_asin,
            "store": store,
            "check_date": date.today().strftime("%Y-%m-%d"),
            "competitors": {},
        }

        for c_asin in competitor_asins:
            snapshots = self._load_snapshots(store, c_asin)
            if not snapshots:
                report["competitors"][c_asin] = {
                    "status": "no_data",
                    "message": "无快照数据",
                }
                continue

            latest = snapshots[0]
            data = latest.get("data", {})
            entry: dict[str, Any] = {
                "status": "ok",
                "latest_snapshot_date": latest["snapshot_date"],
                "current_bsr": data.get("bsr"),
                "current_price": data.get("price"),
                "current_rating": data.get("rating"),
                "current_review_count": data.get("review_count"),
            }

            if len(snapshots) >= 2:
                changes = self.compare_two_snapshots(snapshots[1], snapshots[0])
                entry["changes_from_previous"] = changes

                # 计算趋势（如果有3+快照）
                if len(snapshots) >= 3:
                    bsr_trend = []
                    for i in range(min(len(snapshots), 5) - 1, 0, -1):
                        s_new = snapshots[i - 1].get("data", {}).get("bsr")
                        s_old = snapshots[i].get("data", {}).get("bsr")
                        if s_new and s_old and s_old != 0:
                            bsr_trend.append(
                                round((s_new - s_old) / s_old * 100, 1)
                            )
                    if bsr_trend:
                        entry["bsr_trend_5_periods"] = bsr_trend

            report["competitors"][c_asin] = entry

        return report

    def get_competitive_landscape(
        self,
        store: str,
        competitor_asins: list[str],
    ) -> list[dict]:
        """获取竞品格局概览（最新快照摘要）"""
        landscape = []
        for c_asin in competitor_asins:
            snapshots = self._load_snapshots(store, c_asin)
            if snapshots:
                data = snapshots[0].get("data", {})
                landscape.append(
                    {
                        "asin": c_asin,
                        "date": snapshots[0]["snapshot_date"],
                        "bsr": data.get("bsr"),
                        "price": data.get("price"),
                        "rating": data.get("rating"),
                        "review_count": data.get("review_count"),
                    }
                )
        return sorted(
            landscape, key=lambda x: x.get("bsr") or 99999999
        )
