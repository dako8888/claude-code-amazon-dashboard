"""
Search Terms 轮换算法 — 基于时间窗口和关键词表现的动态轮换

用法:
    from lib.keyword_rotator import KeywordRotator
    kr = KeywordRotator()
    next_terms = kr.get_rotation_plan(current_terms, keyword_pool, days_active=14)
"""

from datetime import datetime, timedelta
from typing import Any


class KeywordRotator:
    """Search Terms 轮换管理器"""

    ROTATION_INTERVALS = {
        "fast": 14,   # 14天轮换（新品/激烈竞争）
        "normal": 21,  # 21天轮换（常规商品）
        "slow": 30,   # 30天轮换（稳定商品）
    }

    def __init__(self):
        self.rotation_history: list[dict] = []

    def get_rotation_plan(
        self,
        current_terms: str,
        keyword_pool: list[str],
        days_active: int = 14,
        interval: str = "normal",
    ) -> dict[str, Any]:
        """
        生成轮换方案

        Args:
            current_terms: 当前 Search Terms 字符串
            keyword_pool: 可用关键词池
            days_active: 当前 Search Terms 已用天数
            interval: 轮换间隔策略

        Returns:
            轮换计划 dict，含新 Search Terms 和理由
        """
        interval_days = self.ROTATION_INTERVALS.get(interval, 21)
        current_words = set(current_terms.lower().split())

        # 时间到必须轮换
        due = days_active >= interval_days
        # 提前轮换：接近到期
        approaching = days_active >= interval_days * 0.8

        # 从词库中选词：优先选择未出现过的词
        unused = [w for w in keyword_pool if w.lower() not in current_words]
        used = [w for w in keyword_pool if w.lower() in current_words]

        # 构建新方案
        new_terms_list = []
        # 保留部分表现好的词（如有表现数据）+ 加入新词

        # 简化为：全部替换为新词 + 保留Top表现词
        candidates = unused if unused else keyword_pool

        # 按搜索量排序（keyword_pool 假定已排序）
        selected = candidates[: min(len(candidates), 30)]

        new_terms = " ".join(selected)
        new_bytes = len(new_terms.encode("utf-8"))

        # 如果超出250字节，逐步删减
        while new_bytes > 250 and len(selected) > 1:
            selected.pop()
            new_terms = " ".join(selected)
            new_bytes = len(new_terms.encode("utf-8"))

        # 记录
        record = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "old_terms": current_terms,
            "new_terms": new_terms,
            "days_active": days_active,
            "trigger": "scheduled" if due else "early_refresh",
            "replaced_count": len(current_words - set(new_terms.lower().split())),
            "new_count": len(set(new_terms.lower().split()) - current_words),
            "byte_count": new_bytes,
        }
        self.rotation_history.append(record)

        return {
            "new_terms": new_terms,
            "byte_count": new_bytes,
            "within_limit": new_bytes <= 250,
            "interval_days": interval_days,
            "days_until_next": interval_days,
            "next_rotation": (
                datetime.now() + timedelta(days=interval_days)
            ).strftime("%Y-%m-%d"),
            "record": record,
        }

    def get_rotation_schedule(
        self, total_keywords: int, interval: str = "normal"
    ) -> list[dict]:
        """生成长期轮换时间表"""
        interval_days = self.ROTATION_INTERVALS.get(interval, 21)
        # 假设每次轮换用 ~20 个词
        words_per_rotation = 20
        total_rotations = max(1, total_keywords // words_per_rotation)

        schedule = []
        for i in range(total_rotations):
            rotation_date = datetime.now() + timedelta(
                days=interval_days * (i + 1)
            )
            schedule.append(
                {
                    "rotation_number": i + 1,
                    "date": rotation_date.strftime("%Y-%m-%d"),
                    "words_used_so_far": words_per_rotation * (i + 1),
                }
            )
        return schedule

    def get_history(self) -> list[dict]:
        return self.rotation_history
