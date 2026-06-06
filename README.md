# Amazon Workflow Dashboard

Skill 1.0 / 2.0 / 3.0 的统一 Web 运维面板（Streamlit）。

## 前置条件

- Python 3.7+
- `pip install streamlit pandas openpyxl`

## 安装

```bash
git clone https://github.com/dako8888/claude-code-amazon-dashboard.git
```

把这个 repo 放进你的工作目录，和以下目录平级：

```
你的工作目录/
├── amazon-dashboard/          ← 这个 repo
├── amazon-ads-analyzer/       ← Skill 3.0（广告分析联动）
├── amazon-listing-skill/      ← Skill 1.0（维护数据联动）
├── amazon-brandstore-skill/   ← Skill 2.0（品牌旗舰店联动）
├── amazon-listings/           ← Skill 1.0 的数据目录
└── ads_data/                  ← Skill 3.0 的广告数据目录
```

## 启动

```bash
cd amazon-dashboard
streamlit run app.py
```

浏览器打开 http://localhost:8501

## 功能页面

| 页面 | 用途 |
|------|------|
| 维护日历 | ASIN 健康卡片 + 广告维护 7/14/30/90 天提醒 |
| ASIN 诊断 | 指标 vs 基线追踪 |
| 竞品监控 | 手动快照 + 历史对比 |
| 关键词管理 | 四层分布 + Search Terms 轮换 |
| A/B 测试 | 版本对比 |
| 广告分析 | CSV 上传 → 10 种报告 → Excel 导出 |
| 品牌分析 | 展示份额 / 品类基准 / 品牌指标 / 受众 |
| 图片库存 | 槽位完成度 |
| 季节性日历 | 90 天节日提醒 + 品类策略 |
| 品牌旗舰店 | 质量评级 / 流量趋势 / 竞品审计 |

## Skill 体系

| Skill | 定位 |
|------|------|
| [Skill 1.0](https://github.com/dako8888/claude-code-amazon-listing-skill) | Listing 文案/图片/视频 |
| [Skill 2.0](https://github.com/dako8888/claude-code-amazon-brandstore-skill) | 品牌旗舰店 |
| [Skill 3.0](https://github.com/dako8888/claude-code-amazon-ads-analyzer) | 广告分析 |
| [Dashboard](https://github.com/dako8888/claude-code-amazon-dashboard) | 统一运维面板 |
