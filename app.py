"""
Amazon 工作流 Dashboard — 统一维护面板
启动: streamlit run app.py
"""

import json
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

import pandas as pd
import streamlit as st

# 配置
sys.path.insert(0, str(Path(__file__).parent))
from config import (
    STORES,
    SEASONAL_EVENTS,
    DASHBOARD_STATE_FILE,
    LISTING_DATA_DIR,
    SKILL_LIB_DIR,
    BRANDSTORE_SKILL_DIR,
    BRANDSTORE_DATA_DIR,
    BRANDSTORE_SCREENSHOT_DIR,
    BRANDSTORE_QUALITY_TIERS,
    BRANDSTORE_BENCHMARKS,
    ADS_SCRIPTS_DIR,
    ADS_LIB_DIR,
    ADS_SHARED_DIR,
    STORE_CONFIG_PATH,
)

sys.path.insert(0, str(SKILL_LIB_DIR))
from state_manager import StateManager

# Skill 3.0 广告分析器
sys.path.insert(0, str(ADS_SCRIPTS_DIR))
sys.path.insert(0, str(ADS_LIB_DIR))

st.set_page_config(
    page_title="Amazon Workflow Dashboard",
    page_icon="",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---- 全局样式 ----
st.markdown("""
<style>
  /* === 基础 === */
  h1 { font-size: 1.6rem !important; font-weight: 700 !important; letter-spacing: -0.3px; }
  h2 { font-size: 1.15rem !important; font-weight: 600 !important; margin-top: 1.2rem; }
  h3 { font-size: 1rem !important; font-weight: 600 !important; }

  /* === 页面标题栏 === */
  .page-header {
    padding: 1rem 1.2rem;
    margin: -1rem -1rem 1.5rem -1rem;
    background: linear-gradient(135deg, rgba(255,153,0,0.08), transparent);
    border-left: 3px solid #FF9900;
    border-radius: 0 8px 8px 0;
  }

  /* === KPI 指标卡 === */
  [data-testid="stMetric"] {
    background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 0.8rem 1rem;
    box-shadow: 0 2px 8px rgba(0,0,0,0.2);
  }
  [data-testid="stMetric"]:hover {
    border-color: rgba(255,153,0,0.25);
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
  }
  [data-testid="stMetric"] label { color: #888 !important; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.5px;}
  [data-testid="stMetric"] [data-testid="stMetricValue"] { font-size: 1.5rem !important; font-weight: 700; }

  /* === 内容卡片 === */
  .card {
    background: linear-gradient(180deg, rgba(255,255,255,0.025), rgba(255,255,255,0.01));
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 1.2rem;
    margin-bottom: 0.8rem;
    box-shadow: 0 1px 4px rgba(0,0,0,0.15);
  }

  /* === 侧边栏 === */
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1117 0%, #161b22 100%) !important;
    border-right: 1px solid rgba(255,153,0,0.12) !important;
  }
  [data-testid="stSidebar"] .stRadio > div { gap: 0.2rem; }
  [data-testid="stSidebar"] .stRadio label {
    padding: 0.45rem 0.75rem; border-radius: 8px; transition: all 0.15s;
  }
  [data-testid="stSidebar"] .stRadio label:hover {
    background: rgba(255,153,0,0.06);
  }

  /* === 按钮 === */
  .stButton > button {
    border-radius: 8px !important; font-weight: 600 !important;
    transition: all 0.2s; border: 1px solid rgba(255,255,255,0.1) !important;
  }
  .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
  div[data-testid="stFormSubmitButton"] > button {
    background: linear-gradient(135deg, #FF9900, #FFB84D) !important;
    color: #000 !important; border: none !important; font-weight: 700 !important;
  }

  /* === 进度条 === */
  .stProgress > div > div { background: linear-gradient(90deg, #FF9900, #FFB84D) !important; border-radius: 4px; }

  /* === 表单 === */
  [data-testid="stForm"] {
    background: rgba(255,255,255,0.015);
    border: 1px solid rgba(255,255,255,0.06);
    border-radius: 12px;
    padding: 1.5rem;
  }

  /* === 数据框 / 表格 === */
  [data-testid="stDataFrame"] { border-radius: 8px; overflow: hidden; }
  [data-testid="stTable"] { border-radius: 8px; overflow: hidden; }

  /* === 空状态 === */
  .empty-state {
    text-align: center; padding: 3rem 2rem; color: #666;
    background: rgba(255,255,255,0.01); border-radius: 16px;
    border: 1px dashed rgba(255,255,255,0.08);
  }
  .empty-state .icon { font-size: 3rem; margin-bottom: 0.8rem; }
  .empty-state .title { font-size: 1rem; font-weight: 600; color: #999; margin-bottom: 0.4rem; }
  .empty-state .hint { font-size: 0.85rem; color: #666; }

  /* === Expander === */
  [data-testid="stExpander"] {
    border: 1px solid rgba(255,255,255,0.06) !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.1);
  }

  /* === 警告/成功/信息框 === */
  [data-testid="stAlert"] { border-radius: 10px !important; }
</style>
""", unsafe_allow_html=True)

sm = StateManager(str(LISTING_DATA_DIR))

# ---- 辅助函数 ----
def page_header(title: str, desc: str = "", accent: str = "#FF9900"):
    """统一的页面标题栏"""
    st.markdown(f"""
    <div class="page-header" style="border-left-color:{accent}">
      <div style="font-size:1.4rem;font-weight:700;color:#e8eaed;">{title}</div>
      <div style="font-size:0.82rem;color:#888;margin-top:0.2rem;">{desc}</div>
    </div>
    """, unsafe_allow_html=True)

def empty_state(icon: str, title: str, hint: str):
    """空状态占位"""
    st.markdown(f"""
    <div class="empty-state">
      <div class="icon">{icon}</div>
      <div class="title">{title}</div>
      <div class="hint">{hint}</div>
    </div>
    """, unsafe_allow_html=True)

# ---- Sidebar ----
st.sidebar.markdown("""
<div style="text-align:center; padding:0.5rem 0 1rem 0;">
  <div style="font-size:2rem; margin-bottom:0.3rem;"></div>
  <div style="font-size:1.1rem; font-weight:700; color:#FF9900;">Amazon Dashboard</div>
  <div style="font-size:0.75rem; color:#666;">Skill 1.0 · 统一维护面板</div>
</div>
""", unsafe_allow_html=True)

store_key = st.sidebar.selectbox(
    "店铺",
    list(STORES.keys()),
    format_func=lambda k: f"{'🍳' if k=='kitchen' else '🏠'} {STORES[k]['name']}",
)
store = STORES[store_key]

st.sidebar.divider()

page = st.sidebar.radio(
    "导航",
    [
        "📅 维护日历",
        "🔍 ASIN 诊断",
        "👥 竞品监控",
        "🔑 关键词管理",
        "🧪 A/B 测试",
        "📊 广告分析",
        "📈 品牌分析",
        "📆 季节性运营日历",
        "🖼️ 图片库存",
        "🏪 品牌旗舰店",
    ],
    label_visibility="collapsed",
)

st.sidebar.divider()
st.sidebar.markdown(f"""
<div style="font-size:0.78rem; color:#666; line-height:1.6;">
  <div style="color:#999; margin-bottom:0.3rem;">📁 {store['name']}</div>
  <div>🏷️ {store['category']}</div>
</div>
""", unsafe_allow_html=True)


# ---- Page: 维护日历 ----
if "维护日历" in page:
    page_header("维护日历总览", f"{store['name']} · {store['category']} · 所有 ASIN 健康状态")

    asins = sm.list_asins(store_key)
    if not asins:
        empty_state("📭", "暂无 ASIN 数据", "通过 /amazon-listing 创建第一个 Listing 后，这里会出现维护卡片")
    else:
        states = sm.get_all_states(store_key)
        today = date.today()

        cols = st.columns(3)
        for i, s in enumerate(states):
            with cols[i % 3]:
                # 计算维护状态
                st_rotate = s.get("search_terms_next", "")
                days_left = None
                alert = False
                if st_rotate:
                    try:
                        rotate_date = datetime.strptime(st_rotate, "%Y-%m-%d").date()
                        days_left = (rotate_date - today).days
                        alert = days_left <= 3
                    except ValueError:
                        pass

                # 卡片颜色
                if alert:
                    border_color = "#e74c3c"
                elif days_left is not None and days_left <= 7:
                    border_color = "#f39c12"
                else:
                    border_color = "#2ecc71"

                with st.container(border=True):
                    st.markdown(
                        f"<div style='border-left:4px solid {border_color};padding-left:8px'>"
                        f"<b>{s['asin']}</b></div>",
                        unsafe_allow_html=True,
                    )
                    st.caption(f"状态: {s.get('status', 'active')}")
                    if s.get("bsr"):
                        st.metric("BSR", f"#{s['bsr']:,}")
                    if s.get("rating"):
                        st.metric("评分", f"{s['rating']} ⭐")
                    if st_rotate:
                        st.caption(
                            f"Search Terms 下次轮换: {st_rotate} ({days_left}天后)"
                        )
                    st.caption(f"最后更新: {s.get('last_updated', 'N/A')}")

        # 今日到期的 ASIN
        st.divider()
        st.subheader("需要关注的 ASIN")
        today_str = today.strftime("%Y-%m-%d")
        urgent = [
            s
            for s in states
            if s.get("search_terms_next", "") <= today_str
        ]
        if urgent:
            for s in urgent:
                st.warning(
                    f"**{s['asin']}** — Search Terms 轮换到期 ({s.get('search_terms_next')})"
                )
        else:
            st.success("无到期事项")

    # -- 广告维护 SOP (Skill 3.0) --
    st.divider()
    st.subheader("广告维护 SOP")

    from maintenance_check import load_state as m_load, check_due as m_check, init_state as m_init

    # 获取广告店铺的 store_id（从 store_config 读取）
    try:
        from normalize import _load_unified_config
        sc = _load_unified_config()
        ads_data = sc.get("stores", {})
        ads_store_id = None
        if isinstance(ads_data, dict):
            for sk, si in ads_data.items():
                if sk == store_key and si.get("ads", {}).get("store_id"):
                    ads_store_id = si["ads"]["store_id"]
                    break
    except Exception:
        ads_store_id = None

    if ads_store_id:
        m_state = m_load(ads_store_id)
        if m_state is None:
            if st.button("初始化广告维护", key="btn_ads_init"):
                m_state = m_init(ads_store_id)
                st.success(f"已初始化 — {ads_store_id}")
                st.rerun()
        else:
            due_list = m_check(m_state)
            if due_list:
                for task in due_list:
                    if task.get("is_overdue"):
                        st.error(
                            f"逾期 {abs(task.get('days_left', 0))} 天: **{task.get('label', '')}** "
                            f"— {task.get('description', '')}"
                        )
                    elif task.get("is_due_soon"):
                        st.warning(
                            f"{task.get('days_left', 0)} 天后: **{task.get('label', '')}**"
                        )
                    else:
                        st.info(
                            f"{task.get('days_left', 0)} 天后: {task.get('label', '')}"
                        )
            else:
                st.success("广告维护任务全部正常")

            with st.expander("标记完成"):
                task_keys = [
                    ("search_term", "SP 搜索词分析 (7天)"),
                    ("sb_sd_check", "SB/SD 检查 (14天)"),
                    ("budget_review", "预算审查 (30天)"),
                    ("campaign_audit", "Campaign 审计 (90天)"),
                ]
                for tk, tl in task_keys:
                    if st.button(f"完成: {tl}", key=f"done_{tk}"):
                        from maintenance_check import mark_done as m_done
                        m_done(ads_store_id, tk)
                        st.success(f"已标记: {tl}")
                        st.rerun()
    else:
        st.caption("配置广告店铺后显示维护提醒")


# ---- Page: ASIN 诊断 ----
elif "ASIN 诊断" in page:
    page_header("ASIN 诊断", "对比创建基线 · 追踪趋势变化 · 生成行动清单", "#4CAF50")

    asins = sm.list_asins(store_key)
    if not asins:
        empty_state("🔍", "暂无 ASIN 数据", "通过 /amazon-listing 创建 Listing 后在这里进行诊断")
    else:
        selected_asin = st.selectbox("选择 ASIN", asins)
        if selected_asin:
            state = sm.load(store_key, selected_asin)
            if state:
                col1, col2 = st.columns(2)
                with col1:
                    st.subheader("状态基线")
                    st.json(
                        {
                            "asin": state["asin"],
                            "created": state["created_date"],
                            "last_updated": state["last_updated"],
                            "keywords": {
                                "core": len(state["keywords"]["core"]),
                                "long_tail": len(state["keywords"]["long_tail"]),
                                "scene": len(state["keywords"]["scene"]),
                                "search_terms": len(
                                    state["keywords"]["search_terms"]
                                ),
                            },
                        }
                    )

                with col2:
                    st.subheader("维护信息")
                    maint = state["maintenance"]
                    st.write(f"Search Terms 上次轮换: {maint.get('search_terms_last_rotated') or '从未'}")
                    st.write(f"Search Terms 下次轮换: {maint.get('search_terms_next_rotation') or '未设置'}")
                    st.write(f"竞品下次检查: {maint.get('next_competitor_check') or '未设置'}")
                    st.write(f"关键词下次刷新: {maint.get('next_keyword_refresh') or '未设置'}")

                st.divider()
                st.subheader("手动更新基线指标")
                with st.form("update_metrics"):
                    c1, c2, c3, c4 = st.columns(4)
                    ctr = c1.number_input("CTR (%)", 0.0, 100.0, 0.0, 0.01) / 100
                    cvr = c2.number_input("CVR (%)", 0.0, 100.0, 0.0, 0.01) / 100
                    bsr = c3.number_input("BSR", 0, 9999999, 0)
                    rating = c4.number_input("评分", 0.0, 5.0, 0.0, 0.1)
                    orders = st.number_input("近7天订单", 0, 99999, 0)

                    if st.form_submit_button("更新指标"):
                        sm.update_metrics(
                            store_key,
                            selected_asin,
                            {
                                "ctr": ctr if ctr > 0 else None,
                                "cvr": cvr if cvr > 0 else None,
                                "bsr": bsr if bsr > 0 else None,
                                "rating": rating if rating > 0 else None,
                                "orders": orders if orders > 0 else None,
                            },
                        )
                        sm.set_maintenance_alerts(store_key, selected_asin)
                        st.success("指标已更新，维护提醒已设置")

                st.divider()
                st.subheader("内容快照")
                content = state.get("content_snapshot", {})
                if content.get("title"):
                    st.text_area("标题", content["title"], disabled=True)
                if content.get("bullets"):
                    for i, b in enumerate(content["bullets"], 1):
                        st.text_area(f"5点 #{i}", b, disabled=True)

                # 竞品列表
                st.divider()
                st.subheader("追踪竞品")
                competitors = state.get("competitors", {}).get("tracked_asins", [])
                c_cols = st.columns(len(competitors) if competitors else 1)
                for i, c_asin in enumerate(competitors):
                    with c_cols[i]:
                        st.code(c_asin)


# ---- Page: 竞品监控 ----
elif "竞品监控" in page:
    page_header("竞品监控", "追踪竞品动态 · BSR / 价格 / 关键词变化", "#E91E63")

    asins = sm.list_asins(store_key)
    if not asins:
        empty_state("📭", "暂无 ASIN 数据", "通过 /amazon-listing 创建 Listing 后这里会有数据")
    else:
        selected_asin = st.selectbox("选择要查竞品的 ASIN", asins)
        if selected_asin:
            state = sm.load(store_key, selected_asin)
            competitors = state.get("competitors", {}).get("tracked_asins", []) if state else []

            st.subheader("手动录入竞品快照")
            with st.form("competitor_snapshot"):
                c_asin = st.text_input("竞品 ASIN")
                c1, c2, c3 = st.columns(3)
                c_bsr = c1.number_input("BSR", 0, 99999999, 0)
                c_price = c2.number_input("价格 ($)", 0.0, 9999.0, 0.0, 0.01)
                c_rating = c3.number_input("评分", 0.0, 5.0, 0.0, 0.1)
                c_reviews = st.number_input("评论数", 0, 999999, 0)
                c_title = st.text_input("标题")
                c_keywords = st.text_area("关键词 (逗号分隔)")

                if st.form_submit_button("保存快照"):
                    from competitor_research import CompetitorResearch

                    cr = CompetitorResearch(str(LISTING_DATA_DIR))
                    cr.take_snapshot(
                        store_key,
                        c_asin,
                        {
                            "bsr": c_bsr,
                            "price": c_price,
                            "rating": c_rating,
                            "review_count": c_reviews,
                            "title": c_title,
                            "keywords": [k.strip() for k in c_keywords.split(",") if k.strip()],
                        },
                    )
                    st.success(f"竞品 {c_asin} 快照已保存")

            # 显示已有竞品快照
            if competitors:
                st.subheader("追踪的竞品")
                try:
                    from competitor_research import CompetitorResearch
                    cr = CompetitorResearch(str(LISTING_DATA_DIR))
                    for c_asin in competitors:
                        latest = cr.get_latest_snapshot(store_key, c_asin)
                        if latest:
                            with st.expander(f"{c_asin} — {latest['snapshot_date']}"):
                                data = latest["data"]
                                c1, c2, c3, c4 = st.columns(4)
                                c1.metric("BSR", f"#{data.get('bsr', 'N/A')}")
                                c2.metric("价格", f"${data.get('price', 'N/A')}")
                                c3.metric("评分", data.get("rating", "N/A"))
                                c4.metric("评论数", data.get("review_count", "N/A"))
                                if data.get("title"):
                                    st.caption(f"标题: {data['title'][:120]}")
                        else:
                            st.caption(f"{c_asin}: 无快照数据")
                except ImportError:
                    st.warning("competitor_research 模块加载失败")


# ---- Page: 关键词管理 ----
elif "关键词管理" in page:
    page_header("关键词管理", "Search Terms 轮换 · 关键词分层 · 到期提醒", "#2196F3")

    asins = sm.list_asins(store_key)
    if not asins:
        empty_state("📭", "暂无 ASIN 数据", "通过 /amazon-listing 创建 Listing 后这里会有数据")
    else:
        selected_asin = st.selectbox("选择 ASIN", asins)
        if selected_asin:
            state = sm.load(store_key, selected_asin)
            if state:
                kw = state.get("keywords", {})

                st.subheader("关键词分层")
                cols = st.columns(4)
                for i, (layer, title) in enumerate(
                    [
                        ("core", "核心大词"),
                        ("long_tail", "高转化长尾"),
                        ("scene", "场景/属性"),
                        ("search_terms", "Search Terms"),
                    ]
                ):
                    with cols[i]:
                        st.metric(title, len(kw.get(layer, [])))
                        if kw.get(layer):
                            with st.expander("查看"):
                                for word in kw[layer]:
                                    st.code(word, language=None)

                st.divider()
                st.subheader("Search Terms 轮换")
                maint = state.get("maintenance", {})
                st.write(f"上次轮换: {maint.get('search_terms_last_rotated') or '从未'}")
                st.write(f"下次轮换: {maint.get('search_terms_next_rotation') or '未设置'}")

                current_st = state.get("content_snapshot", {}).get("search_terms", "")
                st.text_area("当前 Search Terms", current_st, disabled=True)

                with st.form("rotate_search_terms"):
                    new_st = st.text_area("新的 Search Terms（空格分隔，250字节内）")
                    if st.form_submit_button("执行轮换"):
                        st_bytes = len(new_st.encode("utf-8"))
                        if st_bytes <= 250:
                            sm.rotate_search_terms(store_key, selected_asin, new_st)
                            st.success(f"Search Terms 已轮换 ({st_bytes}/250 bytes)")
                        else:
                            st.error(f"超出限制: {st_bytes}/250 bytes, 请删减 {st_bytes - 250} 字节")


# ---- Page: A/B 测试 ----
elif "A/B 测试" in page:
    page_header("A/B 测试", "版本对比 · CTR/CVR/订单 · 胜出判定", "#9C27B0")

    asins = sm.list_asins(store_key)
    if not asins:
        empty_state("📭", "暂无 ASIN 数据", "通过 /amazon-listing 创建 Listing 后这里会有数据")
    else:
        selected_asin = st.selectbox("选择 ASIN", asins)
        if selected_asin:
            state = sm.load(store_key, selected_asin)
            maint = state.get("maintenance", {}) if state else {}
            st.write(f"A/B 测试开始: {maint.get('aplus_ab_test_start') or '未开始'}")
            st.write(f"A/B 测试结束: {maint.get('aplus_ab_test_end') or '未设置'}")

            st.divider()
            st.subheader("版本数据对比")
            with st.form("ab_test"):
                test_name = st.text_input("测试名称", "主图 A/B 测试")
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown("**版本 A**")
                    a_ctr = st.number_input("CTR (%)", 0.0, 100.0, 0.0, 0.01, key="a_ctr")
                    a_cvr = st.number_input("CVR (%)", 0.0, 100.0, 0.0, 0.01, key="a_cvr")
                    a_orders = st.number_input("订单", 0, 99999, 0, key="a_orders")
                with c2:
                    st.markdown("**版本 B**")
                    b_ctr = st.number_input("CTR (%)", 0.0, 100.0, 0.0, 0.01, key="b_ctr")
                    b_cvr = st.number_input("CVR (%)", 0.0, 100.0, 0.0, 0.01, key="b_cvr")
                    b_orders = st.number_input("订单", 0, 99999, 0, key="b_orders")

                if st.form_submit_button("对比分析"):
                    st.divider()
                    st.subheader("分析结果")
                    cols = st.columns(3)

                    if a_ctr > 0 and b_ctr > 0:
                        ctr_diff = round((b_ctr - a_ctr) / a_ctr * 100, 1)
                        winner = "B" if ctr_diff > 0 else "A"
                        cols[0].metric("CTR 差异", f"{ctr_diff:+.1f}%", f"版本{winner}胜")

                    if a_cvr > 0 and b_cvr > 0:
                        cvr_diff = round((b_cvr - a_cvr) / a_cvr * 100, 1)
                        winner = "B" if cvr_diff > 0 else "A"
                        cols[1].metric("CVR 差异", f"{cvr_diff:+.1f}%", f"版本{winner}胜")

                    if a_orders > 0 and b_orders > 0:
                        order_diff = round((b_orders - a_orders) / a_orders * 100, 1)
                        cols[2].metric("订单差异", f"{order_diff:+.1f}%")

                    st.info("结论：请结合统计显著性判断是否采纳变更。小样本数据波动不具有统计意义。")


# ---- Page: 广告分析 (Skill 3.0) ----
elif "广告分析" in page:
    from normalize import load as normalize_csv, _load_unified_config, get_ads_data_dir, fmt_money, fmt_pct

    page_header("广告分析", "SP/SB/SD 全类型 · CSV 上传 → 自动识别 → 一键分析 · 桌面Excel", "#FF5722")

    # -- 店铺选择 --
    store_cfg = _load_unified_config()
    ads_stores = {}
    stores_data = store_cfg.get("stores", {}) if store_cfg else {}
    if isinstance(stores_data, dict):
        for key, info in stores_data.items():
            ads = info.get("ads") if isinstance(info, dict) else {}
            if ads and ads.get("store_id"):
                ads_stores[ads["store_id"]] = {
                    "store_key": key, "name": ads.get("name", key),
                    "target_acos_sp": ads.get("target_acos_sp", 0.25),
                    "target_acos_sb": ads.get("target_acos_sb", 0.20),
                    "target_acos_sd": ads.get("target_acos_sd", 0.30),
                }

    if not ads_stores:
        st.warning("未配置广告店铺。先运行 `python scripts/store_manager.py init`")
        st.stop()

    selected_ads_store = st.sidebar.selectbox(
        "广告店铺",
        list(ads_stores.keys()),
        format_func=lambda s: ads_stores[s]["name"],
        key="ads_store_selector",
    )
    ads_store = ads_stores[selected_ads_store]

    # -- Tab: 上传分析 / 历史报告 --
    t_upload, t_history = st.tabs(["📤 上传 CSV 分析", "📁 历史报告"])

    with t_history:
        ads_data_dir = get_ads_data_dir()
        reports_dir = Path(ads_data_dir) / selected_ads_store / "reports" if ads_data_dir else None
        if reports_dir and reports_dir.exists():
            report_files = sorted(reports_dir.glob("*.md"), reverse=True)
            if report_files:
                st.caption(f"{len(report_files)} 份历史报告")
                for rf in report_files[:20]:
                    ts_str = rf.stem[:16]
                    st.markdown(f"- [{rf.name}]({rf}) — {ts_str}")
            else:
                st.info("暂无历史报告，上传 CSV 开始分析")
        else:
            st.info(f"报告目录: {ads_data_dir}/{selected_ads_store}/reports/（尚未创建）")

    with t_upload:
        col_l, col_r = st.columns([2, 1])
        with col_l:
            uploaded_files = st.file_uploader(
                "上传 Amazon Ads CSV 报告（支持同时上传多个）",
                type=["csv"],
                accept_multiple_files=True,
                help="从 Amazon Ads 后台下载 CSV → 直接拖入这里。支持 SP/SB/SD 全类型。",
            )
        with col_r:
            st.caption("**支持的报告类型**")
            st.caption("SP: 搜索词 / 关键词 / Campaign / 广告位 / 推广商品 / 已购商品 / 预算")
            st.caption("SB: 品牌广告搜索词/关键词/投放目标")
            st.caption("SD: 展示广告定向报告")

        if uploaded_files:
            import tempfile, shutil as _shutil

            tmp_dir = Path(tempfile.mkdtemp(prefix="ads_"))
            csv_paths = []
            for uf in uploaded_files:
                tpath = tmp_dir / uf.name
                with open(tpath, "wb") as f:
                    f.write(uf.getbuffer())
                csv_paths.append(tpath)

            st.divider()
            st.subheader(f"已上传 {len(uploaded_files)} 个文件")

            # 逐个文件 normalize + 识别类型
            file_metas = []
            for p in csv_paths:
                try:
                    meta = normalize_csv(str(p))
                    file_metas.append(meta)
                except Exception as e:
                    st.error(f"解析失败: {p.name} — {e}")

            if file_metas:
                st.caption(" | ".join(
                    f"{m.file_name}: **{m.ad_product}**/{m.report_type}/{m.attribution_window}"
                    for m in file_metas
                ))

                # 分析按钮
                if st.button("开始分析", type="primary", use_container_width=True):
                    store_dict = {
                        "target_acos_sp": ads_store["target_acos_sp"],
                        "target_acos_sb": ads_store["target_acos_sb"],
                        "target_acos_sd": ads_store["target_acos_sd"],
                    }

                    for meta in file_metas:
                        st.divider()
                        rtype = meta.report_type
                        st.markdown(f"### {meta.file_name} ({meta.ad_product} {rtype})")

                        try:
                            if rtype == "search_term":
                                from analyze_search_term import analyze as ast
                                results = ast(meta, store=store_dict)
                                # Key metrics
                                c1, c2, c3 = st.columns(3)
                                c1.metric("总花费", fmt_money(results["total_spend"]))
                                c2.metric("总销售额", fmt_money(results["total_sales"]))
                                c3.metric("整体 ACoS", fmt_pct(results["total_acos"]))
                                # Harvest & negative
                                harvest = results.get("categories", {}).get("harvest", [])
                                negative = results.get("categories", {}).get("negative", [])
                                cc1, cc2, cc3, cc4 = st.columns(4)
                                cc1.metric("收割", len(harvest))
                                cc2.metric("否定", len(negative))
                                cc3.metric("检查", len(results.get("categories", {}).get("review", [])))
                                cc4.metric("预计节省/月", fmt_money(results.get("waste", 0)))
                                if harvest:
                                    with st.expander(f"收割清单 ({len(harvest)} 词)"):
                                        st.dataframe(pd.DataFrame([
                                            {"搜索词": h["search_term"], "花费": fmt_money(h["spend"]),
                                             "ACoS": fmt_pct(h.get("acos", 0)), "操作": "添加 Exact"}
                                            for h in harvest[:20]
                                        ]), hide_index=True, use_container_width=True)
                                if negative:
                                    with st.expander(f"否定清单 ({len(negative)} 词)"):
                                        st.dataframe(pd.DataFrame([
                                            {"搜索词": n["search_term"], "花费": fmt_money(n["spend"]),
                                             "点击": n.get("clicks", 0)}
                                            for n in negative[:20]
                                        ]), hide_index=True, use_container_width=True)

                            elif rtype == "keyword":
                                from analyze_keyword import analyze as akw
                                results = akw(meta, store=store_dict)
                                c1, c2, c3 = st.columns(3)
                                c1.metric("关键词数", results["total_keywords"])
                                c2.metric("总花费", fmt_money(results["total_spend"]))
                                c3.metric("整体 ACoS", fmt_pct(results["total_acos"]))
                                cc1, cc2, cc3, cc4 = st.columns(4)
                                cc1.metric("优秀", len(results["excellent"]))
                                cc2.metric("健康", len(results["healthy"]))
                                cc3.metric("警告", len(results["warning"]))
                                cc4.metric("浪费", len(results["wasteful"]))
                                mig = results.get("migration_suggestions", [])
                                if mig:
                                    with st.expander(f"匹配类型迁移建议 ({len(mig)} 个)"):
                                        st.dataframe(pd.DataFrame(mig), hide_index=True, use_container_width=True)

                            elif rtype == "campaign":
                                from analyze_campaign import analyze as ac
                                results = ac(meta, store=store_dict)
                                c1, c2, c3 = st.columns(3)
                                c1.metric("Campaign 数", results["total_campaigns"])
                                c2.metric("总花费", fmt_money(results["total_spend"]))
                                c3.metric("整体 ACoS", fmt_pct(results["total_acos"]))
                                capped = [c for c in results.get("excellent", []) if c.get("budget_utilization", 0) > 0.9]
                                if capped:
                                    st.warning(f"{len(capped)} 个 Campaign 预算利用率 >90% — 可考虑加预算")

                            elif rtype in ("placement", "advertised_product", "purchased_product", "budget"):
                                # 通用 KPI 展示
                                rows = meta.rows
                                total_spend = sum(r.get("spend", 0) for r in rows)
                                total_sales = sum(r.get(meta.attribution_window == "14d" and "sales_14d" or "sales_7d", 0) for r in rows)
                                c1, c2, c3 = st.columns(3)
                                c1.metric("总花费", fmt_money(total_spend))
                                c2.metric("总销售额", fmt_money(total_sales))
                                c3.metric("ACoS", fmt_pct(total_spend / total_sales if total_sales > 0 else float("inf")))
                                st.dataframe(pd.DataFrame(rows[:20]), hide_index=True, use_container_width=True)
                                # Build results for Excel export
                                results = {"total_spend": total_spend, "total_sales": total_sales,
                                          "total_acos": total_spend / total_sales if total_sales > 0 else float("inf")}

                            else:
                                # SB/SD/其他 → 用 analyze_sb_sd
                                from analyze_sb_sd import analyze as asbsd
                                results = asbsd(meta, store=store_dict)
                                c1, c2, c3 = st.columns(3)
                                c1.metric("总花费", fmt_money(results.get("total_spend", 0)))
                                c2.metric("总销售额", fmt_money(results.get("total_sales", 0)))
                                c3.metric("ACoS", fmt_pct(results.get("total_acos", float("inf"))))
                                if "total_ntb_orders" in results:
                                    st.metric("NTB 新客订单", results["total_ntb_orders"])

                            # Excel 导出
                            st.divider()
                            if st.button(f"下载 Excel → 桌面", key=f"xlsx_{meta.file_name}"):
                                from report_xlsx import EXPORTERS
                                exporter_key = rtype if rtype in EXPORTERS else "sb_sd"
                                out = EXPORTERS[exporter_key](results, meta.file_name)
                                st.success(f"已保存: {out}")

                        except ImportError as e:
                            st.warning(f"分析器加载失败: {e}")
                        except Exception as e:
                            import traceback as _tb
                            st.error(f"分析出错: {e}")
                            st.code(_tb.format_exc())

            _shutil.rmtree(tmp_dir, ignore_errors=True)


# ---- Page: 图片库存 ----
elif "图片库存" in page:
    page_header("图片库存", "槽位完成度 · 图片分类统计 · 查漏补缺", "#00BCD4")

    asins = sm.list_asins(store_key)
    if not asins:
        empty_state("📭", "暂无 ASIN 数据", "通过 /amazon-listing 创建 Listing 后这里会有数据")
    else:
        selected_asin = st.selectbox("选择 ASIN", asins)
        if selected_asin:
            try:
                sys.path.insert(0, str(SKILL_LIB_DIR))
                from image_manager import ImageManager
                im = ImageManager()
                inv = im.get_image_inventory(store_key, selected_asin)

                st.subheader(f"{selected_asin} — 图片库存总览")

                cols = st.columns(5)
                cols[0].metric("总数", inv["total"])
                cols[1].metric("主图", len(inv["main"]))
                cols[2].metric("辅图", len(inv["alt"]))
                cols[3].metric("A+图", len(inv["aplus"]))
                cols[4].metric("AI生成", len(inv["generated"]))

                # 目标 vs 实际
                st.divider()
                st.subheader("槽位完成度")

                targets = {"main": 1, "alt": 8, "aplus": 5}
                for cat, target in targets.items():
                    current = len(inv.get(cat, []))
                    pct = min(current / target, 1.0) if target > 0 else 0
                    label = {"main": "主图", "alt": "辅图", "aplus": "A+模块"}[cat]
                    st.progress(pct, text=f"{label}: {current}/{target}")

                # 详细列表
                st.divider()
                for cat in ["main", "alt", "aplus", "generated"]:
                    files = inv.get(cat, [])
                    if files:
                        with st.expander(f"{cat}/ ({len(files)} files)"):
                            for f in sorted(files):
                                st.text(f"  {f}")
                    else:
                        if cat in ["main", "alt", "aplus"]:
                            st.caption(f"{cat}/ — 空（待生成）")

            except ImportError as e:
                st.warning(f"模块加载失败: {e}")

# ---- Page: 品牌分析 (Skill 3.0 Phase 4) ----
elif "品牌分析" in page:
    page_header("品牌分析", "我 vs 市场 · 展示份额 / 品类基准 / 品牌指标 / 受众效率", "#9C27B0")

    tab_is, tab_cb, tab_bm, tab_au = st.tabs([
        "展示量份额", "品类基准", "品牌指标", "受众分析"
    ])

    with tab_is:
        st.subheader("搜索词展示量份额分析")
        st.caption("数据来源: Amazon Ads 搜索词展示量份额报告 或 LinkFox SIF keyword overview")
        is_input = st.text_area("粘贴展示份额 JSON", height=150, key="is_json",
            placeholder='[{"search_term":"crochet rose lamp","my_share_pct":15.0,"top_competitor_share_pct":35.0,"trend":"declining","my_ctr":2.5,"my_cvr":8.0,"market_avg_ctr":1.8}]')
        if is_input and st.button("分析展示份额", key="btn_is"):
            try:
                from analyze_impression_share import analyze as is_analyze
                data = json.loads(is_input)
                if isinstance(data, dict):
                    data = data.get("keywords", data.get("results", data.get("data", [])))
                results = is_analyze(data)
                c1, c2 = st.columns(2)
                c1.metric("总词数", results.get("total_terms", 0))
                c2.metric("平均份额", f"{results.get('avg_share', 0):.1f}%")
                for label, key, color in [("份额下降（竞品在抢）", "losing_share", "#D0312D"),
                                            ("份额上升（我们在赢）", "winning_share", "#107C41"),
                                            ("低份额机会", "opportunity", "#1A56DB")]:
                    items = results.get(key, [])
                    if items:
                        with st.expander(f"{label} ({len(items)}词)"):
                            st.dataframe(pd.DataFrame([
                                {"搜索词": i.get("search_term", ""),
                                 "我的份额": f"{i.get('my_share_pct', 0):.1f}%",
                                 "竞品Top": f"{i.get('top_competitor_share_pct', 0):.1f}%",
                                 "建议": i.get("action", "")}
                                for i in items[:15]
                            ]), hide_index=True, use_container_width=True)
            except Exception as e:
                st.error(f"分析失败: {e}")

    with tab_cb:
        st.subheader("品类基准对比")
        st.caption("数据来源: Amazon Ads 品类基准报告 或 卖家精灵选市场")
        cb_input = st.text_area("粘贴品类基准 JSON", height=150, key="cb_json",
            placeholder='{"category":"Lamps & Shades","my_metrics":{"acos":0.35,"cpc":0.75,"ctr":0.025,"cvr":0.08},"benchmarks":{"category_avg":{"acos":0.28,"cpc":0.70,"ctr":0.022,"cvr":0.07},"top_quartile":{"acos":0.18,"cpc":0.55,"ctr":0.035,"cvr":0.12}}}')
        if cb_input and st.button("分析品类基准", key="btn_cb"):
            try:
                from analyze_category_benchmark import analyze as cb_analyze
                data = json.loads(cb_input)
                results = cb_analyze(data)
                st.markdown(f"**品类**: {results.get('category', '?')} | 市场趋势: {results.get('market_trend', '?')}")
                gaps = results.get("gaps", [])
                if gaps:
                    st.dataframe(pd.DataFrame([
                        {"指标": g["label"], "我的值": g["my_fmt"], "品类均值": g["avg_fmt"],
                         "vs均值": g["vs_avg_label"], "头部值": g["top_fmt"],
                         "vs头部": g["vs_top_label"], "诊断": g.get("severity", "")}
                        for g in gaps
                    ]), hide_index=True, use_container_width=True)
                for rec in results.get("recommendations", []):
                    st.warning(rec)
            except Exception as e:
                st.error(f"分析失败: {e}")

    with tab_bm:
        st.subheader("品牌指标追踪")
        st.caption("数据来源: Amazon Ads 品牌指标 (Beta) 或品牌展示量份额 (Beta)")
        bm_input = st.text_area("粘贴品牌指标 JSON（至少2个周期）", height=150, key="bm_json",
            placeholder='{"brand":"ANZRLE","periods":[{"label":"2026-04","ntb_order_pct":0.65,"repeat_rate":0.12,"brand_search_volume":3200,"brand_impression_share":0.08},{"label":"2026-05","ntb_order_pct":0.58,"repeat_rate":0.15,"brand_search_volume":3800,"brand_impression_share":0.10}]}')
        if bm_input and st.button("分析品牌指标", key="btn_bm"):
            try:
                from analyze_brand_metrics import analyze as bm_analyze
                data = json.loads(bm_input)
                results = bm_analyze(data)
                st.markdown(f"**品牌**: {results.get('brand', '?')} | 周期: {results.get('period_range', '?')}")
                for key, trend in results.get("trends", {}).items():
                    icon = {"up": "↑", "down": "↓", "stable": "→"}.get(trend["direction"], "")
                    st.metric(f"{trend['label']}", f"{icon} {trend['change_pct']:+.1f}%")
                for ins in results.get("insights", []):
                    st.info(ins)
            except Exception as e:
                st.error(f"分析失败: {e}")

    with tab_au:
        st.subheader("SD 受众定向效率分析")
        st.caption("数据来源: Amazon Ads SD 受众报告")
        au_input = st.text_area("粘贴受众数据 JSON", height=150, key="au_json",
            placeholder='{"audiences":[{"audience_name":"浏览再营销-30天","audience_type":"remarketing","impressions":15000,"clicks":320,"spend":240.0,"sales":960.0,"orders":15,"ntb_orders":8,"ctr":0.021,"cvr":0.047}]}')
        if au_input and st.button("分析受众", key="btn_au"):
            try:
                from analyze_audience import analyze as au_analyze
                data = json.loads(au_input)
                results = au_analyze(data)
                c1, c2 = st.columns(2)
                c1.metric("受众数", results.get("audience_count", 0))
                c2.metric("整体 ACoS", f"{results.get('total_acos', 0)*100:.1f}%")
                audiences = results.get("audiences", [])
                if audiences:
                    st.dataframe(pd.DataFrame([
                        {"受众": a.get("audience_name", ""), "类型": a.get("audience_type", ""),
                         "花费": f"${a.get('spend', 0):.2f}", "ACoS": f"{a.get('acos', 0)*100:.1f}%",
                         "ROAS": f"{a.get('roas', 0):.1f}x", "NTB%": f"{a.get('ntb_pct', 0)*100:.0f}%",
                         "效率": a.get("efficiency", "")}
                        for a in audiences
                    ]), hide_index=True, use_container_width=True)
                for s in results.get("strategy", []):
                    st.info(s)
            except Exception as e:
                st.error(f"分析失败: {e}")


# ---- Page: 季节性运营日历 ----
elif "季节性运营日历" in page:
    page_header("季节性运营日历", f"{store['category']} · 未来 90 天节点 · 提前提醒", "#FF9800")

    today = date.today()
    cutoff = today + timedelta(days=90)

    st.subheader("未来90天节点")

    events_data = []
    for event in SEASONAL_EVENTS:
        # 解析日期
        try:
            if event["date"] == "动态":
                continue
            event_date = datetime.strptime(
                f"{today.year}-{event['date']}", "%Y-%m-%d"
            ).date()
            # 如果今年的已过，看明年
            if event_date < today:
                event_date = datetime.strptime(
                    f"{today.year + 1}-{event['date']}", "%Y-%m-%d"
                ).date()
        except ValueError:
            continue

        if event_date <= cutoff:
            days_until = (event_date - today).days
            lead_start = event_date - timedelta(days=event["lead_days"])

            status = ""
            if today >= lead_start:
                status = "现在开始准备"
            elif days_until <= event["lead_days"]:
                status = f"即将开始 ({days_until - event['lead_days']}天后)"

            events_data.append(
                {
                    "节日": event["name"],
                    "日期": event_date.strftime("%Y-%m-%d"),
                    "距今天数": days_until,
                    "准备提前量": event["lead_days"],
                    "准备开始日期": lead_start.strftime("%Y-%m-%d"),
                    "状态": status or "等待中",
                }
            )

    if events_data:
        df_events = pd.DataFrame(events_data).sort_values("距今天数")
        st.dataframe(df_events, width="stretch", hide_index=True)

        # 高亮已进入准备期的节日
        urgent = [e for e in events_data if e["状态"] == "现在开始准备"]
        if urgent:
            st.divider()
            st.subheader("需要立即准备的节点")
            for e in urgent:
                st.warning(
                    f"**{e['节日']}** — {e['日期']} ({e['距今天数']}天后) — 建议 {e['准备提前量']} 天前开始准备"
                )
    else:
        st.info("未来90天内无节日节点")

    # 品类季节性提醒
    st.divider()
    st.subheader("品类季节性指引")
    if store_key == "kitchen":
        st.markdown("""
        | 季度 | 节点 | 内容策略 |
        |------|------|----------|
        | Q1 (1-3月) | 情人节/烘焙季 | 心形模具、爱心主题印花 |
        | Q2 (4-6月) | 母亲节/毕业/户外 | 礼品场景、亲子烘焙套装 |
        | Q3 (7-9月) | Prime Day/烧烤季 | 常青款推广、新品预热 |
        | Q4 (10-12月) | 万圣/黑五/圣诞 | 全年最大旺季，主题印花集中爆发 |
        """)
    else:
        st.markdown("""
        | 季度 | 节点 | 内容策略 |
        |------|------|----------|
        | Q1 (1-2月) | 情人节/新年焕新 | 情人节装饰、新年家居 |
        | Q2-Q3 | 淡季维护 | 基础款维稳、小幅优化 |
        | Q4 (10-12月) | 万圣/黑五/圣诞 | 节日装饰全品类（全年最高峰） |
        """)


# ---- Page: 品牌旗舰店 ----
elif "品牌旗舰店" in page:
    from lib.brandstore_manager import (
        load_state as bs_load_state,
        save_state as bs_save_state,
        load_snapshots,
        add_snapshot,
        get_latest_snapshot,
        get_maintenance_alerts,
        init_maintenance_schedule,
        set_maintenance_next,
        compute_trends,
        add_competitor_store,
    )

    # 品牌选择 — 从 store_config 获取该店铺的品牌列表
    try:
        import json as _json
        _sc_path = BRANDSTORE_SKILL_DIR / "_shared" / "store_config.json"
        if _sc_path.exists():
            _sc = _json.loads(_sc_path.read_text(encoding="utf-8"))
            _brands = _sc.get("stores", {}).get(store_key, {}).get("brands", [])
        else:
            _brands = []
    except Exception:
        _brands = []

    if not _brands:
        empty_state("🏪", "该店铺暂无品牌旗舰店数据", "在 Seller Central 创建品牌旗舰店后，在此处追踪数据")
    else:
        brand = st.sidebar.selectbox("品牌", _brands, key="bs_brand")
        bs_state = bs_load_state(store_key, brand)

        # Tab 结构
        tabs = st.tabs(["📊 总览看板", "📝 数据快照", "📄 页面分析", "🔎 竞品旗舰店", "🎨 设计参考"])

        # ================================================================
        # Tab 1: 总览看板
        # ================================================================
        with tabs[0]:
            page_header(f"品牌旗舰店总览 — {brand}", f"质量评级 · 关键指标 · 维护提醒 · 数据来自 {brand} 品牌旗舰店 Insights", "#FF9900")

            today = date.today()
            latest_snap = get_latest_snapshot(store_key, brand)
            alerts = get_maintenance_alerts(store_key, brand)
            trends = compute_trends(load_snapshots(store_key, brand)) if load_snapshots(store_key, brand) else None

            # KPI 行
            kc1, kc2, kc3, kc4 = st.columns(4)

            with kc1:
                rating = bs_state.get("quality_rating") or (latest_snap.get("overview", {}).get("quality_rating", {}).get("tier") if latest_snap else None) or "未评级"
                score = bs_state.get("quality_score") or (latest_snap.get("overview", {}).get("quality_rating", {}).get("score") if latest_snap else None) or 0
                tier_info = BRANDSTORE_QUALITY_TIERS.get(rating, {})
                tier_color = tier_info.get("color", "#888")
                st.markdown(f"""
                <div style="text-align:center;padding:0.6rem 0;">
                  <div style="font-size:0.75rem;color:#888;text-transform:uppercase;letter-spacing:0.5px;">Store 质量评级</div>
                  <div style="font-size:2.2rem;font-weight:700;color:{tier_color};">{rating}</div>
                  <div style="font-size:0.75rem;color:#666;">{tier_info.get('desc', '')}</div>
                </div>
                """, unsafe_allow_html=True)

            with kc2:
                visits = latest_snap.get("overview", {}).get("visits", 0) if latest_snap else 0
                visits_prev = trends.get("visits", {}).get("previous", 0) if trends else 0
                visits_delta = f"{trends['visits']['change_pct']:+.1f}%" if trends and trends.get("visits", {}).get("change_pct") is not None else None
                st.metric("访问量 (Visits)", f"{visits:,}", delta=visits_delta)

            with kc3:
                sales = latest_snap.get("overview", {}).get("sales_attributed", 0) if latest_snap else 0
                sales_prev = trends.get("sales_attributed", {}).get("previous", 0) if trends else 0
                sales_delta = f"{trends['sales_attributed']['change_pct']:+.1f}%" if trends and trends.get("sales_attributed", {}).get("change_pct") is not None else None
                st.metric("归因销售额", f"${sales:,.0f}", delta=sales_delta)

            with kc4:
                cvr = latest_snap.get("overview", {}).get("conversion_rate", 0) if latest_snap else 0
                cvr_prev = trends.get("conversion_rate", {}).get("previous", 0) if trends else 0
                cvr_delta = f"{trends['conversion_rate']['change_pct']:+.1f}%" if trends and trends.get("conversion_rate", {}).get("change_pct") is not None else None
                cvr_label = "差" if cvr < 5 else ("一般" if cvr < 10 else ("好" if cvr < 15 else "优秀"))
                st.metric("Store 转化率", f"{cvr:.1f}%", delta=f"{cvr_label}" if not cvr_delta else cvr_delta)

            # 第二行指标
            st.divider()
            kc5, kc6, kc7, kc8 = st.columns(4)

            with kc5:
                units = latest_snap.get("overview", {}).get("units_sold", 0) if latest_snap else 0
                st.metric("售出件数", f"{units:,}")

            with kc6:
                depth = latest_snap.get("overview", {}).get("page_depth", 0) if latest_snap else 0
                st.metric("浏览深度（页/次）", f"{depth:.1f}")

            with kc7:
                dwell = latest_snap.get("overview", {}).get("dwell_time_seconds", 0) if latest_snap else 0
                mins = int(dwell // 60)
                secs = int(dwell % 60)
                st.metric("平均停留时间", f"{mins}:{secs:02d}")

            with kc8:
                new_pct = latest_snap.get("overview", {}).get("new_to_store_pct", 0) if latest_snap else 0
                st.metric("新访客占比", f"{new_pct:.1f}%")

            # 流量来源饼图
            if latest_snap and latest_snap.get("traffic_sources"):
                st.divider()
                st.subheader("流量来源分布")
                ts = latest_snap["traffic_sources"]
                ts_cols = st.columns(5)
                sources = [
                    ("自然搜索", ts.get("organic_search", {})),
                    ("SB 广告", ts.get("sponsored_brands", {})),
                    ("DSP", ts.get("amazon_dsp", {})),
                    ("站外", ts.get("external", {})),
                    ("其他", ts.get("other", {})),
                ]
                for i, (name, data) in enumerate(sources):
                    with ts_cols[i]:
                        pct = data.get("pct", 0) if data else 0
                        st.metric(name, f"{pct:.1f}%")
                        if data:
                            st.caption(f"${data.get('sales', 0):,.0f} 销售额")

            # 维护提醒
            st.divider()
            st.subheader("🔔 维护提醒")
            if alerts:
                for a in alerts:
                    icon = "🔴" if a["urgency"] == "due" else "🟡"
                    st.warning(f"{icon} **{a['name']}** — {a['desc']}" + (f" (已逾期 {a['days']} 天)" if a["urgency"] == "due" else f" ({a['days']} 天后到期)"))
            else:
                st.success("✅ 暂无到期维护动作")

            # 快捷操作
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("🔄 初始化/重置维护计划", key="bs_init_maint"):
                    init_maintenance_schedule(store_key, brand)
                    st.success("维护计划已初始化")
                    st.rerun()
            with col_b:
                if st.button("📊 录入本期数据快照", key="bs_goto_snapshot"):
                    st.info("→ 切换到「数据快照」标签页录入")

            # 历史趋势
            snapshots = load_snapshots(store_key, brand)
            if len(snapshots) >= 2:
                st.divider()
                st.subheader("📈 历史趋势")
                try:
                    import plotly.express as px
                    import pandas as pd

                    trend_data = []
                    for s in snapshots:
                        ov = s.get("overview", {})
                        trend_data.append({
                            "日期": s.get("snapshot_date", ""),
                            "访问量": ov.get("visits", 0),
                            "销售额": ov.get("sales_attributed", 0),
                            "转化率": ov.get("conversion_rate", 0),
                        })
                    df_trend = pd.DataFrame(trend_data)

                    tc1, tc2 = st.columns(2)
                    with tc1:
                        fig = px.line(df_trend, x="日期", y=["访问量", "销售额"],
                                      title="访问量 & 销售额趋势", markers=True)
                        fig.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=20))
                        st.plotly_chart(fig, use_container_width=True)
                    with tc2:
                        fig2 = px.line(df_trend, x="日期", y="转化率",
                                       title="Store 转化率趋势", markers=True)
                        fig2.update_layout(height=320, margin=dict(l=20, r=20, t=40, b=20))
                        fig2.add_hline(y=5, line_dash="dash", line_color="red", annotation_text="差 <5%")
                        fig2.add_hline(y=10, line_dash="dash", line_color="orange", annotation_text="一般 5-10%")
                        fig2.add_hline(y=15, line_dash="dash", line_color="green", annotation_text="好 >15%")
                        st.plotly_chart(fig2, use_container_width=True)
                except ImportError:
                    st.dataframe(df_trend, use_container_width=True)

        # ================================================================
        # Tab 2: 数据快照
        # ================================================================
        with tabs[1]:
            page_header(f"数据快照 — {brand}", "从 Seller Central Brand Store Insights 手动录入 · 对标 Amazon Insights 面板", "#2196F3")

            st.markdown("""
            > **数据来源**: Seller Central → Stores → Manage Stores → 选择 `{brand}` → **See Insights**
            > **新增**: 2026.01 起，Amazon 新增 **分区级数据 (Sectional Performance Beta)**，在 Insights 页面可查看每个模块的 Renders / Viewable Impressions / Clicks / CTR
            > **评级变化**: 2025.12 起，质量评级从"停留时间导向"改为"**销售导向**"
            """.replace("{brand}", brand))

            st.divider()

            with st.form("bs_snapshot_form"):
                st.subheader("📊 本期总览数据")
                c1, c2 = st.columns(2)
                with c1:
                    snap_date = st.date_input("数据日期", value=today)
                    snap_period_start = st.date_input("统计周期开始", value=today - timedelta(days=14))
                    snap_period_end = st.date_input("统计周期结束", value=today)
                with c2:
                    quality_tier = st.selectbox("质量评级", ["未评级", "高", "中", "低"])
                    quality_score = st.slider("质量分数 (0-100)", 0, 100, 50)

                st.divider()
                st.subheader("📈 核心指标")
                c3, c4, c5, c6 = st.columns(4)
                with c3:
                    visits = st.number_input("访问量 (Visits)", 0, 9999999, 0)
                    visitors = st.number_input("访客数 (Visitors)", 0, 9999999, 0)
                with c4:
                    sales = st.number_input("归因销售额 ($)", 0.0, 99999999.0, 0.0, 0.01)
                    units = st.number_input("售出件数", 0, 999999, 0)
                with c5:
                    cvr = st.number_input("转化率 (%)", 0.0, 100.0, 0.0, 0.01)
                    page_depth = st.number_input("浏览深度 (页/次)", 0.0, 20.0, 0.0, 0.1)
                with c6:
                    dwell = st.number_input("平均停留 (秒)", 0, 9999, 0)
                    new_pct = st.number_input("新访客占比 (%)", 0.0, 100.0, 0.0, 0.1)

                st.divider()
                st.subheader("🚦 流量来源")
                tc1, tc2, tc3, tc4, tc5 = st.columns(5)
                ts_data = {}
                for idx, (col, key, label) in enumerate([
                    (tc1, "organic_search", "自然搜索"),
                    (tc2, "sponsored_brands", "SB 广告"),
                    (tc3, "amazon_dsp", "DSP"),
                    (tc4, "external", "站外"),
                    (tc5, "other", "其他"),
                ]):
                    with col:
                        st.caption(label)
                        ts_visits = st.number_input(f"访问量", 0, 9999999, 0, key=f"ts_v_{key}")
                        ts_sales = st.number_input(f"销售额 ($)", 0.0, 9999999.0, 0.0, key=f"ts_s_{key}")
                        ts_data[key] = {"visits": ts_visits, "sales": ts_sales}

                # 计算各来源占比
                total_ts_visits = sum(v["visits"] for v in ts_data.values())
                for key in ts_data:
                    ts_data[key]["pct"] = round(ts_data[key]["visits"] / total_ts_visits * 100, 1) if total_ts_visits > 0 else 0.0

                st.divider()
                st.subheader("💡 本期洞察")
                wins = st.text_area("亮点 (Wins)", placeholder="例: 首页转化率提升 12% / 新增送礼子页面带来 $500 销售额")
                problems = st.text_area("问题 (Problems)", placeholder="例: 手机端跳出率 65% / 花灯子页面零销售")
                actions = st.text_area("下期行动 (Actions)", placeholder="例: 更换 Hero 为节日版 / 优化移动端导航 / 为新品建子页面")

                if st.form_submit_button("💾 保存快照"):
                    snapshot = {
                        "snapshot_date": str(snap_date),
                        "period": {"start": str(snap_period_start), "end": str(snap_period_end)},
                        "overview": {
                            "quality_rating": {"tier": quality_tier, "score": quality_score},
                            "visits": visits, "visitors": visitors,
                            "sales_attributed": sales, "units_sold": units,
                            "conversion_rate": cvr, "page_depth": page_depth,
                            "dwell_time_seconds": dwell, "new_to_store_pct": new_pct,
                        },
                        "traffic_sources": ts_data,
                        "insights": {
                            "wins": [w.strip() for w in wins.split("\n") if w.strip()],
                            "problems": [p.strip() for p in problems.split("\n") if p.strip()],
                            "actions": [a.strip() for a in actions.split("\n") if a.strip()],
                        },
                    }
                    add_snapshot(store_key, brand, snapshot)
                    # 同步更新质量评级到 state
                    if quality_tier != "未评级":
                        bs_state["quality_rating"] = quality_tier
                        bs_state["quality_score"] = quality_score
                        bs_state["last_quality_check"] = str(snap_date)
                        bs_save_state(store_key, brand, bs_state)
                    st.success(f"✅ 快照已保存 ({snap_date})")
                    st.rerun()

            # 历史快照列表
            st.divider()
            st.subheader("📋 历史快照")
            snapshots = load_snapshots(store_key, brand)
            if snapshots:
                for s in reversed(snapshots[-10:]):  # 最近10条
                    ov = s.get("overview", {})
                    qr = ov.get("quality_rating", {})
                    with st.expander(f"{s.get('snapshot_date', '?')} — 访问 {ov.get('visits', 0):,} | 销售 ${ov.get('sales_attributed', 0):,.0f} | 转化率 {ov.get('conversion_rate', 0):.1f}% | 评级: {qr.get('tier', 'N/A')}"):
                        # 流量来源
                        ts = s.get("traffic_sources", {})
                        ts_str = " | ".join([f"{k}: {v.get('pct', 0):.1f}%" for k, v in ts.items() if v.get("pct", 0) > 0])
                        st.caption(f"流量: {ts_str}")
                        # 洞察
                        ins = s.get("insights", {})
                        if ins.get("wins"):
                            st.markdown("**亮点**: " + "; ".join(ins["wins"]))
                        if ins.get("problems"):
                            st.markdown("**问题**: " + "; ".join(ins["problems"]))
                        if ins.get("actions"):
                            st.markdown("**行动**: " + "; ".join(ins["actions"]))
            else:
                st.info("暂无快照数据 — 用上方表单录入第一条")

        # ================================================================
        # Tab 3: 页面分析
        # ================================================================
        with tabs[2]:
            page_header(f"页面分析 — {brand}", "页面级指标 · 分区级数据 (2026 Sectional Performance Beta)", "#4CAF50")

            st.info("""
            **新功能 (2026.01 Beta)**: Amazon 品牌旗舰店 Insights 新增 **Sectional Performance** 标签页。
            可以查看每个模块（Hero / 图文 / 商品网格等）的 Renders、Viewable Impressions、Clicks、CTR，
            并按流量来源（SB/DSP/自然搜索/站外）拆分。
            """)

            # 页面列表管理
            bs_pages = bs_state.get("pages", [])

            st.subheader("页面列表")
            if bs_pages:
                for i, p in enumerate(bs_pages):
                    with st.expander(f"{p.get('name', f'页面 {i+1}')} — {p.get('modules', 0)} 个模块 | 更新: {p.get('last_updated', 'N/A')}"):
                        c1, c2 = st.columns(2)
                        with c1:
                            st.write(f"类型: {p.get('type', 'homepage')}")
                            st.write(f"模块数: {p.get('modules', 0)}")
                            st.write(f"最后更新: {p.get('last_updated', 'N/A')}")
                        with c2:
                            # 分区级数据（如有）
                            sections = p.get("sections", [])
                            if sections:
                                st.write(f"分区数据: {len(sections)} 个分区")
                                for sec in sections:
                                    st.caption(f"{sec.get('name', '?')}: Renders {sec.get('renders', 0)} | CTR {sec.get('ctr', 0):.1f}%")

            # 页面录入
            with st.form("bs_page_form"):
                st.subheader("添加/更新页面")
                pc1, pc2 = st.columns(2)
                with pc1:
                    page_name = st.text_input("页面名称", placeholder="首页 / 花灯全系列 / 送礼指南")
                    page_type = st.selectbox("页面类型", ["homepage", "subpage_l1_product", "subpage_l1_landing", "subpage_l1_content", "subpage_l2"])
                with pc2:
                    page_modules = st.number_input("模块数", 1, 20, 5)
                    page_visits = st.number_input("访问量", 0, 9999999, 0)
                    page_sales = st.number_input("归因销售额 ($)", 0.0, 999999.0, 0.0, 0.01)
                    page_cvr = st.number_input("转化率 (%)", 0.0, 100.0, 0.0, 0.01)

                st.caption("分区级数据（可选 — 对应 Amazon Sectional Performance Beta）")
                section_data = st.text_area("分区数据 (JSON)", placeholder='[{"name": "Hero", "renders": 1000, "viewable_impressions": 600, "clicks": 120, "ctr": 20.0}]')

                if st.form_submit_button("💾 保存页面"):
                    sections = []
                    if section_data.strip():
                        try:
                            sections = json.loads(section_data)
                        except json.JSONDecodeError:
                            st.error("分区数据 JSON 格式错误")

                    new_page = {
                        "name": page_name,
                        "type": page_type,
                        "modules": page_modules,
                        "visits": page_visits,
                        "sales": page_sales,
                        "conversion": page_cvr,
                        "last_updated": str(today),
                        "sections": sections,
                    }

                    # 更新或追加
                    existing_names = [p["name"] for p in bs_pages]
                    if page_name in existing_names:
                        idx = existing_names.index(page_name)
                        bs_pages[idx] = new_page
                    else:
                        bs_pages.append(new_page)

                    bs_state["pages"] = bs_pages
                    bs_save_state(store_key, brand, bs_state)
                    st.success(f"✅ 页面 '{page_name}' 已保存")
                    st.rerun()

            # 页面转化对比
            if len(bs_pages) >= 1:
                st.divider()
                st.subheader("页面转化率对比")
                try:
                    import pandas as pd
                    df_pages = pd.DataFrame([{
                        "页面": p["name"], "类型": p.get("type", ""),
                        "模块数": p.get("modules", 0), "访问量": p.get("visits", 0),
                        "销售额": p.get("sales", 0), "转化率": p.get("conversion", 0),
                    } for p in bs_pages])
                    st.dataframe(df_pages, use_container_width=True, hide_index=True)
                except Exception:
                    pass

        # ================================================================
        # Tab 4: 竞品旗舰店
        # ================================================================
        with tabs[3]:
            page_header(f"竞品旗舰店 — {brand}", "竞品品牌旗舰店追踪 · 定期审计 · 差距分析", "#E91E63")

            comp_stores = bs_state.get("competitor_stores", [])

            if comp_stores:
                st.subheader("追踪的竞品旗舰店")
                for c in comp_stores:
                    with st.expander(f"🏪 {c.get('brand', '?')} — 上次审计: {c.get('last_audit', 'N/A')}"):
                        cc1, cc2 = st.columns(2)
                        with cc1:
                            st.write(f"URL: {c.get('url', '未记录')}")
                            st.write(f"开始追踪: {c.get('first_tracked', 'N/A')}")
                        with cc2:
                            st.write(f"审计次数: 审计记录数")
                        if c.get("notes"):
                            st.text_area("最新笔记", c["notes"], disabled=True, key=f"note_{c['brand']}")

                        # 快速更新笔记
                        with st.form(key=f"comp_note_{c['brand']}"):
                            new_note = st.text_area("更新审计笔记", value=c.get("notes", ""))
                            if st.form_submit_button("保存笔记"):
                                from lib.brandstore_manager import add_competitor_audit_note
                                add_competitor_audit_note(store_key, brand, c["brand"], new_note)
                                st.success("笔记已保存")
                                st.rerun()
            else:
                st.info("尚未添加竞品旗舰店 — Phase 0 门禁要求 ≥2 个同品类竞品旗舰店分析")

            st.divider()
            st.subheader("添加竞品旗舰店")
            with st.form("bs_add_competitor"):
                cc1, cc2 = st.columns(2)
                with cc1:
                    comp_brand = st.text_input("竞品品牌名")
                    comp_url = st.text_input("竞品旗舰店 URL", placeholder="https://www.amazon.com/stores/...")
                with cc2:
                    comp_category = st.text_input("品类", placeholder="同品类 / 跨品类标杆")
                    comp_notes = st.text_area("初次观察笔记", placeholder="模块数/颜色/风格/和我们的差距")
                if st.form_submit_button("➕ 添加竞品"):
                    if comp_brand:
                        add_competitor_store(store_key, brand, comp_brand, comp_url)
                        if comp_notes:
                            from lib.brandstore_manager import add_competitor_audit_note
                            add_competitor_audit_note(store_key, brand, comp_brand, comp_notes)
                        st.success(f"✅ 竞品 '{comp_brand}' 已添加")
                        st.rerun()
                    else:
                        st.error("请输入竞品品牌名")

            # 竞品审计提醒
            st.divider()
            st.subheader("竞品审计 SOP")
            st.markdown("""
            1. `opencli browser main open "<竞品旗舰店URL>"` — 打开竞品店
            2. 截图首页 Hero → 品牌故事 → 产品展示 → 每个子页面
            3. 记录：页面数 / 模块类型及顺序 / 色调 / 字体 / CTA 策略
            4. 千问 VL 逐页评估（对标 Phase 0 竞品分析流程）
            5. 填写审计笔记 → 更新本页
            """)

        # ================================================================
        # Tab 5: 设计参考
        # ================================================================
        with tabs[4]:
            page_header(f"设计参考库 — {brand}", "模块示例 · 设计截图 · Skill 2.0 文档快速入口", "#9C27B0")

            # 截图库
            st.subheader("模块设计截图库")
            screenshot_dir = BRANDSTORE_SCREENSHOT_DIR
            if screenshot_dir.exists():
                pngs = sorted(screenshot_dir.glob("*.png"))
                if pngs:
                    st.caption(f"共 {len(pngs)} 张参考截图 — {screenshot_dir}")
                    # 分页显示
                    page_size = 12
                    page_num = st.number_input("页码", 1, max(1, (len(pngs) - 1) // page_size + 1), 1, key="bs_img_page")
                    start = (page_num - 1) * page_size
                    end = min(start + page_size, len(pngs))

                    cols = st.columns(4)
                    for i, png_path in enumerate(pngs[start:end]):
                        with cols[i % 4]:
                            try:
                                st.image(str(png_path), caption=png_path.name[:40], use_container_width=True)
                            except Exception:
                                st.caption(f"📷 {png_path.name}")
                else:
                    st.info("截图库为空")
            else:
                st.warning(f"截图目录不存在: {screenshot_dir}")

            st.divider()

            # Skill 2.0 文档入口
            st.subheader("Skill 2.0 文档速查")
            skill_base = BRANDSTORE_SKILL_DIR

            doc_links = [
                ("SKILL.md", "技能主文件"),
                ("phases/phase0_brand_audit.md", "Phase 0 品牌摸底"),
                ("phases/phase1_index.md", "Phase 1 统一入口"),
                ("phases/phase1_modules.md", "18 种模块规格"),
                ("phases/phase1_homepage.md", "首页设计"),
                ("phases/phase1_subpage.md", "子页面+SB广告"),
                ("phases/phase1_visual.md", "视觉设计+提示词"),
                ("phases/phase2_qa.md", "质检流程"),
                ("phases/phase3_maintain.md", "维护 SOP"),
            ]
            dc1, dc2 = st.columns(2)
            for i, (rel_path, desc) in enumerate(doc_links):
                full_path = skill_base / rel_path
                exists = "✅" if full_path.exists() else "❌"
                with (dc1 if i % 2 == 0 else dc2):
                    st.markdown(f"{exists} **{desc}** — `{rel_path}`")

            st.divider()

            # 工具脚本入口
            st.subheader("Skill 2.0 命令行工具")
            st.code(f"""# 门禁检查
        cd E:\\WorkBuddy\\amazon-brandstore-skill
        python lib/check_brandstore_gate.py {store_key} {brand}

        # 设计方案审核
        python audit_brandstore.py --example

        # 出图后质检
        python qa_brandstore.py {store_key} {brand}

        # 维护提醒
        python maintenance_check.py {store_key} {brand}""", language="bash")


# ---- Footer ----
st.divider()
st.caption(
    f"Amazon Workflow Dashboard v1.0 | 数据目录: {store['data_dir']} | 更新: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
)
