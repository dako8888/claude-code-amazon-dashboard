"""
数据分析器 — CTR/CVR 趋势分析、异常检测、竞品数据对比

用法:
    from lib.data_analyzer import DataAnalyzer
    da = DataAnalyzer()
    trend = da.analyze_trend(weekly_data)
"""

from datetime import date, timedelta
from typing import Any


class DataAnalyzer:
    """CTR/CVR 等指标的趋势分析器"""

    def analyze_trend(
        self, data_points: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """
        分析指标趋势

        Args:
            data_points: [{date, ctr, cvr, orders, impressions, clicks}, ...]

        Returns:
            趋势分析结果
        """
        if len(data_points) < 2:
            return {"error": "至少需要2个数据点"}

        analysis = {
            "total_points": len(data_points),
            "period": {
                "start": data_points[0].get("date"),
                "end": data_points[-1].get("date"),
            },
        }

        # CTR 趋势
        ctrs = [d.get("ctr", 0) for d in data_points if d.get("ctr") is not None]
        if len(ctrs) >= 2:
            ctr_change = ctrs[-1] - ctrs[0]
            analysis["ctr"] = {
                "start": ctrs[0],
                "end": ctrs[-1],
                "change": round(ctr_change, 4),
                "change_pct": (
                    round(ctr_change / ctrs[0] * 100, 1) if ctrs[0] > 0 else 0
                ),
                "trend": "up" if ctr_change > 0 else "down" if ctr_change < 0 else "flat",
                "avg": round(sum(ctrs) / len(ctrs), 4),
            }

        # CVR 趋势
        cvrs = [d.get("cvr", 0) for d in data_points if d.get("cvr") is not None]
        if len(cvrs) >= 2:
            cvr_change = cvrs[-1] - cvrs[0]
            analysis["cvr"] = {
                "start": cvrs[0],
                "end": cvrs[-1],
                "change": round(cvr_change, 4),
                "change_pct": (
                    round(cvr_change / cvrs[0] * 100, 1) if cvrs[0] > 0 else 0
                ),
                "trend": "up" if cvr_change > 0 else "down" if cvr_change < 0 else "flat",
                "avg": round(sum(cvrs) / len(cvrs), 4),
            }

        # 订单趋势
        orders_list = [
            d.get("orders", 0) for d in data_points if d.get("orders") is not None
        ]
        if len(orders_list) >= 2:
            orders_change = orders_list[-1] - orders_list[0]
            analysis["orders"] = {
                "start": orders_list[0],
                "end": orders_list[-1],
                "change": orders_change,
                "change_pct": (
                    round(orders_change / orders_list[0] * 100, 1)
                    if orders_list[0] > 0
                    else 0
                ),
                "trend": (
                    "up"
                    if orders_change > 0
                    else "down"
                    if orders_change < 0
                    else "flat"
                ),
                "total": sum(orders_list),
                "avg": round(sum(orders_list) / len(orders_list), 1),
            }

        return analysis

    def detect_anomaly(
        self,
        current_value: float,
        historical_values: list[float],
        threshold_std: float = 2.0,
    ) -> dict[str, Any]:
        """
        异常检测：当前值是否偏离历史均值

        Args:
            current_value: 当前值
            historical_values: 历史值列表
            threshold_std: 标准差倍数阈值

        Returns:
            异常检测结果
        """
        if not historical_values:
            return {"is_anomaly": False, "reason": "无历史数据"}

        mean = sum(historical_values) / len(historical_values)
        variance = sum((x - mean) ** 2 for x in historical_values) / len(
            historical_values
        )
        std = variance ** 0.5

        if std == 0:
            return {"is_anomaly": False, "reason": "历史数据无波动"}

        z_score = (current_value - mean) / std
        is_anomaly = abs(z_score) > threshold_std

        return {
            "is_anomaly": is_anomaly,
            "current_value": current_value,
            "mean": round(mean, 4),
            "std": round(std, 4),
            "z_score": round(z_score, 2),
            "threshold": threshold_std,
            "direction": (
                "above" if z_score > 0 else "below" if z_score < 0 else "normal"
            ),
        }

    def calculate_health_score(
        self,
        ctr_trend: str = "flat",
        cvr_trend: str = "flat",
        orders_trend: str = "flat",
        bsr_change_pct: float = 0.0,
    ) -> dict[str, Any]:
        """
        计算 ASIN 健康分 (0-100)

        权重:
        - 订单趋势: 30%
        - CVR趋势: 25%
        - CTR趋势: 20%
        - BSR变化: 25%
        """
        score = 50.0  # 基准分

        # 订单权重30%
        if orders_trend == "up":
            score += 30
        elif orders_trend == "down":
            score -= 30

        # CVR 25%
        if cvr_trend == "up":
            score += 25
        elif cvr_trend == "down":
            score -= 25

        # CTR 20%
        if ctr_trend == "up":
            score += 20
        elif ctr_trend == "down":
            score -= 20

        # BSR 25% (BSR下降=排名上升=好事, BSR上升=排名下降=坏事)
        if bsr_change_pct < -10:
            score += 25
        elif bsr_change_pct < -5:
            score += 12
        elif bsr_change_pct > 10:
            score -= 25
        elif bsr_change_pct > 5:
            score -= 12

        score = max(0, min(100, score))

        if score >= 80:
            status = "健康"
        elif score >= 60:
            status = "良好"
        elif score >= 40:
            status = "需关注"
        elif score >= 20:
            status = "警告"
        else:
            status = "紧急"

        return {
            "score": round(score, 1),
            "status": status,
            "breakdown": {
                "orders_contribution": (
                    30 if orders_trend == "up" else -30 if orders_trend == "down" else 0
                ),
                "cvr_contribution": (
                    25
                    if cvr_trend == "up"
                    else -25
                    if cvr_trend == "down"
                    else 0
                ),
                "ctr_contribution": (
                    20 if ctr_trend == "up" else -20 if ctr_trend == "down" else 0
                ),
                "bsr_contribution": (
                    25
                    if bsr_change_pct < -10
                    else 12
                    if bsr_change_pct < -5
                    else -25
                    if bsr_change_pct > 10
                    else -12
                    if bsr_change_pct > 5
                    else 0
                ),
            },
        }
