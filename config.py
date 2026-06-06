"""
Dashboard 全局配置
"""

import sys
from pathlib import Path

# 项目根路径
BASE_DIR = Path(r"E:\WorkBuddy")
LISTING_DATA_DIR = BASE_DIR / "amazon-listings"
SKILL_LIB_DIR = BASE_DIR / "amazon-listing-skill" / "lib"
BRANDSTORE_SKILL_DIR = BASE_DIR / "amazon-brandstore-skill"
BRANDSTORE_DATA_DIR = BASE_DIR / "amazon-dashboard" / "data" / "brandstore"
BRANDSTORE_SCREENSHOT_DIR = Path(r"C:\Users\Administrator\亚马逊资料\claude code自进化\品牌旗舰店模块示例")

# Skill 3.0 广告分析器
ADS_SKILL_DIR = BASE_DIR / "amazon-ads-analyzer"
ADS_SCRIPTS_DIR = ADS_SKILL_DIR / "scripts"
ADS_LIB_DIR = ADS_SKILL_DIR / "lib"
ADS_SHARED_DIR = ADS_SKILL_DIR / "_shared"
STORE_CONFIG_PATH = ADS_SHARED_DIR / "store_config.json"

# 将 Listing Skill 的共享 lib 加入 Python path
if str(SKILL_LIB_DIR) not in sys.path:
    sys.path.insert(0, str(SKILL_LIB_DIR))

# 店铺配置
STORES = {
    "kitchen": {
        "name": "自有厨房",
        "category": "Kitchen & Dining",
        "data_dir": str(LISTING_DATA_DIR / "store_self_us_kitchen"),
        "primary_category": "kitchen",
    },
    "homedecor": {
        "name": "代运营家居",
        "category": "Home Decor",
        "data_dir": str(LISTING_DATA_DIR / "store_friend_us_homedecor"),
        "primary_category": "homedecor",
    },
}

# 季节性日历数据
SEASONAL_EVENTS = [
    {"name": "情人节", "date": "02-14", "lead_days": 30, "category": "all"},
    {"name": "复活节", "date": "动态", "lead_days": 21, "category": "kitchen"},
    {"name": "母亲节", "date": "05-15", "lead_days": 30, "category": "all"},
    {"name": "父亲节", "date": "06-20", "lead_days": 21, "category": "all"},
    {"name": "毕业季", "date": "06-01", "lead_days": 21, "category": "all"},
    {"name": "Prime Day", "date": "07-15", "lead_days": 45, "category": "all"},
    {"name": "开学季", "date": "08-15", "lead_days": 30, "category": "all"},
    {"name": "万圣节", "date": "10-31", "lead_days": 45, "category": "all"},
    {"name": "感恩节", "date": "11-25", "lead_days": 30, "category": "kitchen"},
    {"name": "黑色星期五", "date": "11-26", "lead_days": 45, "category": "all"},
    {"name": "圣诞季", "date": "12-25", "lead_days": 60, "category": "all"},
]

# Dashboard 自身状态文件
DASHBOARD_STATE_FILE = BASE_DIR / "amazon-dashboard" / "data" / "dashboard_state.json"

# 页面配置
PAGE_TITLES = {
    "01_home": "维护日历",
    "02_asin_diagnosis": "ASIN 诊断",
    "03_competitor_monitor": "竞品监控",
    "04_keyword_manager": "关键词管理",
    "05_ab_testing": "A/B 测试",
    "06_ad_panel": "广告数据面板",
    "07_seasonal_calendar": "季节性运营日历",
    "08_brandstore": "品牌旗舰店",
}

# 品牌旗舰店质量评级阈值（Amazon 官方 2025.12 更新 — 销售导向评分）
BRANDSTORE_QUALITY_TIERS = {
    "高": {"threshold": 80, "color": "#2ecc71", "desc": "销售额比低质量店高 97%，比中质量店高 39%"},
    "中": {"threshold": 50, "color": "#f39c12", "desc": "中等水平，有优化空间"},
    "低": {"threshold": 0, "color": "#e74c3c", "desc": "急需优化——销售额严重落后"},
}

# 品牌旗舰店关键指标基准
BRANDSTORE_BENCHMARKS = {
    "conversion_rate": {"poor": 5, "avg": 10, "good": 15, "unit": "%", "label": "Store 转化率"},
    "page_depth": {"poor": 1.5, "avg": 2.5, "good": 3.0, "unit": "页/次", "label": "浏览深度"},
    "traffic_organic_pct": {"poor": 20, "avg": 40, "good": 50, "unit": "%", "label": "自然流量占比"},
    "bounce_rate": {"poor": 70, "avg": 50, "good": 35, "unit": "%", "label": "跳出率"},
}

# 品牌旗舰店维护周期
BRANDSTORE_MAINTENANCE = {
    "quality_rating_check": 7,       # 每 7 天检查质量评级
    "section_insights_review": 14,   # 每 14 天查看分区级数据
    "competitor_store_audit": 30,    # 每 30 天竞品旗舰店审计
    "seasonal_content_update": 30,   # 旺季前 30 天更新内容
    "content_refresh": 90,           # 每 90 天全局内容刷新
}
