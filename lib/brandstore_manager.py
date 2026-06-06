"""品牌旗舰店数据管理 — 数据快照录入/查询/趋势分析"""
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

# 延迟导入避免 Streamlit 环境冲突
DATA_DIR = Path(r"E:\WorkBuddy\amazon-dashboard\data\brandstore")


def _ensure_dir() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)


def get_state_path(store: str, brand: str) -> Path:
    _ensure_dir()
    return DATA_DIR / f"{store}_{brand}_state.json"


def get_snapshots_path(store: str, brand: str) -> Path:
    _ensure_dir()
    return DATA_DIR / f"{store}_{brand}_snapshots.json"


def load_state(store: str, brand: str) -> dict:
    """加载品牌旗舰店状态"""
    p = get_state_path(store, brand)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _default_state(store, brand)


def save_state(store: str, brand: str, state: dict) -> None:
    _ensure_dir()
    state["last_updated"] = str(date.today())
    p = get_state_path(store, brand)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _default_state(store: str, brand: str) -> dict:
    today = str(date.today())
    return {
        "store": store,
        "brand": brand,
        "created_date": today,
        "last_updated": today,
        "status": "active",
        "quality_rating": None,       # 高/中/低
        "quality_score": None,        # 0-100
        "last_quality_check": None,
        "pages": [],                  # [{"name": "首页", "modules": 7, "last_updated": ...}]
        "competitor_stores": [],      # [{"brand": "...", "url": "...", "last_audit": ...}]
        "maintenance": {
            "next_quality_check": None,
            "next_section_review": None,
            "next_competitor_audit": None,
            "next_seasonal_update": None,
            "next_content_refresh": None,
        },
        "design_refs": {              # 关联的设计参考文件
            "screenshot_lib": str(Path(r"C:\Users\Administrator\亚马逊资料\claude code自进化\品牌旗舰店模块示例")),
            "store_design_json": None,
            "prompts_homepage": None,
        },
    }


# ─── 数据快照（从 Seller Central Brand Store Insights 手动录入）───

def load_snapshots(store: str, brand: str) -> list[dict]:
    p = get_snapshots_path(store, brand)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_snapshots(store: str, brand: str, snapshots: list[dict]) -> None:
    _ensure_dir()
    p = get_snapshots_path(store, brand)
    p.write_text(json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8")


def add_snapshot(store: str, brand: str, snapshot: dict) -> list[dict]:
    """添加一条品牌旗舰店数据快照。snapshot 需包含 snapshot_date。"""
    snapshots = load_snapshots(store, brand)
    if "snapshot_date" not in snapshot:
        snapshot["snapshot_date"] = str(date.today())
    snapshots.append(snapshot)
    snapshots.sort(key=lambda s: s.get("snapshot_date", ""))
    save_snapshots(store, brand, snapshots)
    return snapshots


def get_latest_snapshot(store: str, brand: str) -> dict | None:
    snapshots = load_snapshots(store, brand)
    return snapshots[-1] if snapshots else None


def get_page_snapshots(store: str, brand: str) -> list[dict]:
    """获取页面级别的快照（含分区级数据）"""
    snapshots = load_snapshots(store, brand)
    return [s for s in snapshots if "pages" in s]


# ─── 信息洞察模板（对应 Amazon Brand Store Insights 面板）───

INSIGHTS_TEMPLATE = {
    "_meta": {
        "version": "2026.06.05",
        "description": "品牌旗舰店信息洞察模板 — 对应 Amazon Seller Central Brand Store Insights 数据面板",
        "data_sources": [
            "Seller Central → Stores → Manage Stores → See Insights",
            "Brand Store Insights → Sectional Performance (Beta, 2026.01)",
            "Brand Analytics → Search Query Performance",
        ],
    },
    "overview": {
        "period": {"start": "", "end": "", "note": "建议每 14 天录入一次"},
        "quality_rating": {"tier": "", "score": 0, "note": "高/中/低 — Amazon 销售导向评分"},
        "visits": 0,
        "visitors": 0,
        "sales_attributed": 0.0,
        "units_sold": 0,
        "conversion_rate": 0.0,
        "page_depth": 0.0,
        "dwell_time_seconds": 0,
        "new_to_store_pct": 0.0,
    },
    "traffic_sources": {
        "organic_search": {"visits": 0, "sales": 0.0, "pct": 0.0},
        "sponsored_brands": {"visits": 0, "sales": 0.0, "pct": 0.0},
        "amazon_dsp": {"visits": 0, "sales": 0.0, "pct": 0.0},
        "external": {"visits": 0, "sales": 0.0, "pct": 0.0},
        "other": {"visits": 0, "sales": 0.0, "pct": 0.0},
    },
    "pages": [
        # {"name": "首页", "visits": 0, "sales": 0.0, "units": 0, "conversion": 0.0,
        #  "sections": [{"name": "Hero", "renders": 0, "viewable_impressions": 0, "clicks": 0, "ctr": 0.0}]}
    ],
    "top_products": [
        # {"asin": "", "name": "", "sales": 0.0, "units": 0}
    ],
    "insights": {
        "wins": [],          # 本期亮点
        "problems": [],      # 本期问题
        "actions": [],       # 下期行动
        "competitor_notes": [],  # 竞品旗舰店动态
    },
}


def create_insight_snapshot() -> dict:
    """创建一条空白的信息洞察快照，预填模板结构"""
    import copy
    return copy.deepcopy(INSIGHTS_TEMPLATE)


# ─── 趋势计算 ───

def compute_trends(snapshots: list[dict]) -> dict | None:
    """从历史快照计算关键指标趋势"""
    if len(snapshots) < 2:
        return None

    latest = snapshots[-1].get("overview", {})
    previous = snapshots[-2].get("overview", {})

    def _pct_change(new, old) -> float | None:
        if old and old > 0:
            return round((new - old) / old * 100, 1)
        return None

    trends = {}
    for key in ["visits", "visitors", "sales_attributed", "units_sold", "conversion_rate", "page_depth"]:
        new_val = latest.get(key, 0) or 0
        old_val = previous.get(key, 0) or 0
        trends[key] = {
            "current": new_val,
            "previous": old_val,
            "change_pct": _pct_change(new_val, old_val),
        }

    return trends


# ─── 竞品旗舰店追踪 ───

def add_competitor_store(store: str, brand: str, comp_brand: str, comp_url: str = "") -> dict:
    """添加竞品旗舰店"""
    state = load_state(store, brand)
    existing = [c for c in state["competitor_stores"] if c["brand"] == comp_brand]
    if existing:
        existing[0]["last_audit"] = str(date.today())
        if comp_url:
            existing[0]["url"] = comp_url
    else:
        state["competitor_stores"].append({
            "brand": comp_brand,
            "url": comp_url,
            "first_tracked": str(date.today()),
            "last_audit": str(date.today()),
            "notes": "",
        })
    save_state(store, brand, state)
    return state


def add_competitor_audit_note(store: str, brand: str, comp_brand: str, note: str) -> dict:
    """为竞品旗舰店添加审计笔记"""
    state = load_state(store, brand)
    for c in state["competitor_stores"]:
        if c["brand"] == comp_brand:
            c["notes"] = note
            c["last_audit"] = str(date.today())
            break
    save_state(store, brand, state)
    return state


# ─── 维护提醒计算 ───

def get_maintenance_alerts(store: str, brand: str) -> list[dict]:
    """计算到期的品牌旗舰店维护动作"""
    from config import BRANDSTORE_MAINTENANCE

    state = load_state(store, brand)
    maint = state.get("maintenance", {})
    today = date.today()
    alerts = []

    checks = [
        ("quality_rating_check", "质量评级检查", "查看 Brand Store Insights → Quality Rating"),
        ("section_insights_review", "分区级数据分析", "查看 Sectional Performance (Beta)"),
        ("competitor_store_audit", "竞品旗舰店审计", "opencli 截图 ≥2 个竞品旗舰店"),
        ("seasonal_content_update", "季节性内容更新", "检查下个节日是否需要更换 Hero/子页面"),
        ("content_refresh", "全局内容刷新", "更新 ≥20% 页面内容（新场景图/产品/文案）"),
    ]

    for key, name, desc in checks:
        interval = BRANDSTORE_MAINTENANCE.get(key, 30)
        next_date_str = maint.get(f"next_{key}")
        if next_date_str:
            try:
                next_date = datetime.strptime(next_date_str, "%Y-%m-%d").date()
                days_left = (next_date - today).days
                if days_left <= 0:
                    alerts.append({"type": "overdue", "name": name, "desc": desc,
                                   "days": abs(days_left), "urgency": "due"})
                elif days_left <= 7:
                    alerts.append({"type": "upcoming", "name": name, "desc": desc,
                                   "days": days_left, "urgency": "upcoming"})
            except ValueError:
                pass

    return sorted(alerts, key=lambda a: (a["urgency"] == "due", -a.get("days", 999)), reverse=True)


def set_maintenance_next(store: str, brand: str, task_key: str, days_from_now: int) -> dict:
    """设置某项维护任务的下次检查日期"""
    from config import BRANDSTORE_MAINTENANCE
    state = load_state(store, brand)
    next_date = date.today() + timedelta(days=max(days_from_now, 1))
    state["maintenance"][f"next_{task_key}"] = str(next_date)
    save_state(store, brand, state)
    return state


def init_maintenance_schedule(store: str, brand: str) -> dict:
    """初始化所有维护任务的日期（新建品牌旗舰店时调用）"""
    from config import BRANDSTORE_MAINTENANCE
    state = load_state(store, brand)
    today = date.today()
    for key, days in BRANDSTORE_MAINTENANCE.items():
        state["maintenance"][f"next_{key}"] = str(today + timedelta(days=days))
    save_state(store, brand, state)
    return state
