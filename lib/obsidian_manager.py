"""Obsidian 知识库体检数据管理 — 复用 brandstore_manager.py 模式

职责：
- 状态管理：健康度评分 / 上次体检时间 / 问题数统计
- 体检快照：每次跑 vault_lint 的结果归档，支持趋势对比
- 维护提醒：lint / Claudian 评估 / 过时复核 到期提醒
- Claudian 评估：生成提示词 + 保存用户回贴的 JSON 结果
- 经验卡沉淀：生成 6 段结构经验卡写入 raw/日常沉淀/

数据目录：E:\\WorkBuddy\\amazon-dashboard\\data\\obsidian\\
"""
import json
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


def _utf8_env() -> dict:
    """构造强制 UTF-8 的子进程环境变量（Windows GBK 兼容）"""
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONLEGACYWINDOWSSTDIO"] = "0"
    return env

# 从 Dashboard config 读取（app.py 已 sys.path.insert Dashboard 根）
from config import (
    OBSIDIAN_VAULT_DIR,
    OBSIDIAN_DATA_DIR,
    OBSIDIAN_AUDIT_DIR,
    OBSIDIAN_MANIFEST_PATH,
    OBSIDIAN_CLAUDIAN_REPORTS_DIR,
    OBSIDIAN_MAINTENANCE,
)

# 脚本位置：Dashboard/scripts/vault_lint.py
VAULT_LINT_SCRIPT = Path(__file__).parent.parent / "scripts" / "vault_lint.py"

# 经验卡目录
EXPERIENCE_CARD_DIR = OBSIDIAN_VAULT_DIR / "raw" / "日常沉淀"

# ─── manifest 加载 ───

def load_manifest() -> dict:
    """加载 vault _audit/manifest.json 单一事实源"""
    if OBSIDIAN_MANIFEST_PATH.exists():
        try:
            return json.loads(OBSIDIAN_MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


def save_manifest(manifest: dict) -> None:
    """保存 manifest.json"""
    OBSIDIAN_AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    OBSIDIAN_MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )


# ─── 状态管理（对应 brandstore_manager.load_state/save_state）───

def get_state_path() -> Path:
    OBSIDIAN_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return OBSIDIAN_DATA_DIR / "obsidian_state.json"


def load_state() -> dict:
    """加载知识库全局状态"""
    p = get_state_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _default_state()


def save_state(state: dict) -> None:
    OBSIDIAN_DATA_DIR.mkdir(parents=True, exist_ok=True)
    state["last_updated"] = str(date.today())
    p = get_state_path()
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _default_state() -> dict:
    today = str(date.today())
    return {
        "created_date": today,
        "last_updated": today,
        "status": "active",
        "health_score": None,           # 综合健康度 0-100
        "objective_score": None,       # 脚本客观分 0-100
        "claudian_score": None,         # Claudian 语义分 0-100
        "last_lint_date": None,
        "last_claudian_eval_date": None,
        "total_issues": 0,
        "error_count": 0,
        "warn_count": 0,
        "info_count": 0,
        "auto_fixed_count": 0,
        "maintenance": {
            "next_vault_lint": None,
            "next_claudian_evaluation": None,
            "next_stale_review": None,
        },
    }


# ─── 体检快照（对应 load_snapshots/add_snapshot/get_latest_snapshot）───

def get_snapshots_path() -> Path:
    OBSIDIAN_DATA_DIR.mkdir(parents=True, exist_ok=True)
    return OBSIDIAN_DATA_DIR / "obsidian_snapshots.json"


def load_snapshots() -> list[dict]:
    """加载历史体检快照"""
    p = get_snapshots_path()
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []


def save_snapshots(snapshots: list[dict]) -> None:
    p = get_snapshots_path()
    p.write_text(json.dumps(snapshots, ensure_ascii=False, indent=2), encoding="utf-8")


def add_snapshot(snapshot: dict) -> list[dict]:
    """添加一条体检快照。snapshot 需含 snapshot_date + issues + summary"""
    snapshots = load_snapshots()
    if "snapshot_date" not in snapshot:
        snapshot["snapshot_date"] = str(date.today())
    snapshots.append(snapshot)
    snapshots.sort(key=lambda s: s.get("snapshot_date", ""))
    # 保留最近 50 条
    if len(snapshots) > 50:
        snapshots = snapshots[-50:]
    save_snapshots(snapshots)
    return snapshots


def get_latest_snapshot() -> dict | None:
    snapshots = load_snapshots()
    return snapshots[-1] if snapshots else None


# ─── 趋势计算（对应 compute_trends）───

def compute_trends(snapshots: list[dict] | None = None) -> dict | None:
    """从历史快照计算健康度趋势：问题数变化 / 自动修复率 / 健康度变化"""
    if snapshots is None:
        snapshots = load_snapshots()
    if len(snapshots) < 2:
        return None

    latest = snapshots[-1]
    previous = snapshots[-2]

    def _pct_change(new, old) -> float | None:
        if old and old > 0:
            return round((new - old) / old * 100, 1)
        return None

    trends = {}
    for key in ["total_issues", "error_count", "warn_count", "health_score", "auto_fixed_count"]:
        new_val = latest.get(key, 0) or 0
        old_val = previous.get(key, 0) or 0
        trends[key] = {
            "current": new_val,
            "previous": old_val,
            "change_pct": _pct_change(new_val, old_val),
        }

    return trends


# ─── 维护提醒（对应 get_maintenance_alerts/init_maintenance_schedule）───

def get_maintenance_alerts() -> list[dict]:
    """计算到期的知识库维护动作"""
    state = load_state()
    maint = state.get("maintenance", {})
    today = date.today()
    alerts = []

    checks = [
        ("vault_lint", "知识库体检", "跑 vault_lint.py 扫 12 项客观检查"),
        ("claudian_evaluation", "Claudian 5 维度评估", "用 5 篇 benchmark 做语义评估"),
        ("stale_review", "过时标注复核", "检查 ⚠️ 过时标注是否需更新"),
    ]

    for key, name, desc in checks:
        interval = OBSIDIAN_MAINTENANCE.get(key, 30)
        next_date_str = maint.get(f"next_{key}")
        if next_date_str:
            try:
                next_date = datetime.strptime(next_date_str, "%Y-%m-%d").date()
                days_left = (next_date - today).days
                if days_left <= 0:
                    alerts.append({"type": "overdue", "name": name, "desc": desc,
                                   "days": abs(days_left), "urgency": "due"})
                elif days_left <= 3:
                    alerts.append({"type": "upcoming", "name": name, "desc": desc,
                                   "days": days_left, "urgency": "upcoming"})
            except ValueError:
                pass

    return sorted(alerts, key=lambda a: (a["urgency"] == "due", -a.get("days", 999)), reverse=True)


def set_maintenance_next(task_key: str, days_from_now: int) -> dict:
    """设置某项维护任务的下次执行日期"""
    state = load_state()
    next_date = date.today() + timedelta(days=max(days_from_now, 1))
    state["maintenance"][f"next_{task_key}"] = str(next_date)
    save_state(state)
    return state


def init_maintenance_schedule() -> dict:
    """初始化所有维护任务的日期（首次启用体检时调用）"""
    state = load_state()
    today = date.today()
    for key, days in OBSIDIAN_MAINTENANCE.items():
        state["maintenance"][f"next_{key}"] = str(today + timedelta(days=days))
    save_state(state)
    return state


# ─── 体检脚本调用封装 ───

def run_vault_lint(apply_fix: bool = False) -> dict:
    """调用 scripts/vault_lint.py --json，返回结构化结果

    Args:
        apply_fix: 是否同时应用自动修复（默认只检查不修复）
    Returns:
        {version, total, ok, warnings, errors, passed, details, auto_fixes?}
    """
    if not VAULT_LINT_SCRIPT.exists():
        return {"error": f"vault_lint.py 不存在: {VAULT_LINT_SCRIPT}", "passed": False}

    cmd = [sys.executable, str(VAULT_LINT_SCRIPT), "--json"]
    if apply_fix:
        cmd.append("--fix")

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8",
            errors="replace",
            cwd=str(VAULT_LINT_SCRIPT.parent), timeout=120,
            env=_utf8_env(),
        )
        if result.returncode not in (0, 1, 2):
            return {"error": f"脚本退出码异常: {result.returncode}", "stderr": result.stderr, "passed": False}
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError:
            return {"error": "脚本输出非 JSON", "stdout": result.stdout, "stderr": result.stderr, "passed": False}
    except subprocess.TimeoutExpired:
        return {"error": "脚本执行超时（>120s）", "passed": False}
    except Exception as e:
        return {"error": f"脚本调用失败: {e}", "passed": False}


def apply_auto_fixes(fixes: list[dict] | None = None) -> dict:
    """应用自动修复（脚本内部已含备份机制）

    Args:
        fixes: 可选，指定只修哪些（None = 全部可自动修复的）
    Returns:
        {applied: int, failed: int, backups: [paths], details: [...]}
    """
    result = run_vault_lint(apply_fix=True)
    return result


def snapshot_from_lint(lint_result: dict, claudian_result: dict | None = None) -> dict:
    """把 vault_lint 结果转成体检快照"""
    today = str(date.today())
    details = lint_result.get("details", {})
    all_issues = []
    for category, items in details.items():
        for item in items:
            all_issues.append({**item, "category": category})

    errors = sum(1 for i in all_issues if i.get("status") == "error")
    warns = sum(1 for i in all_issues if i.get("status") == "warn")
    infos = sum(1 for i in all_issues if i.get("status") == "info")
    auto_fixable = sum(1 for i in all_issues if i.get("auto_fixable"))

    # 客观健康度评分：error 每个扣 5，warn 扣 2，info 扣 0.5
    objective_score = max(0, 100 - errors * 5 - warns * 2 - infos * 0.5)

    snapshot = {
        "snapshot_date": today,
        "lint_result": lint_result,
        "total_issues": len(all_issues),
        "error_count": errors,
        "warn_count": warns,
        "info_count": infos,
        "auto_fixable_count": auto_fixable,
        "auto_fixed_count": lint_result.get("auto_fixed_count", 0),
        "objective_score": round(objective_score, 1),
        "issues_by_category": {cat: len(items) for cat, items in details.items()},
    }

    if claudian_result:
        scores = claudian_result.get("scores", {})
        score_values = [s.get("score", 0) for s in scores.values()] if isinstance(scores, dict) else []
        claudian_score = round(sum(score_values) / len(score_values) * 20, 1) if score_values else None  # 5分制转100
        snapshot["claudian_result"] = claudian_result
        snapshot["claudian_score"] = claudian_score
        # 综合健康度 = 客观 70% + 语义 30%
        if claudian_score is not None:
            snapshot["health_score"] = round(objective_score * 0.7 + claudian_score * 0.3, 1)
        else:
            snapshot["health_score"] = round(objective_score, 1)
    else:
        snapshot["claudian_score"] = None
        snapshot["health_score"] = round(objective_score, 1)

    return snapshot


def save_lint_snapshot(lint_result: dict, claudian_result: dict | None = None) -> dict:
    """跑完体检后保存快照 + 更新 state

    如果今天已有快照且本次未传 claudian_result，保留旧的 claudian_result（重跑体检不丢失语义评分）。
    """
    # 如果本次没传 claudian_result，检查今天是否已有含 claudian 的快照
    if claudian_result is None:
        existing_snapshots = load_snapshots()
        today = str(date.today())
        today_snap = next((s for s in existing_snapshots if s.get("snapshot_date") == today), None)
        if today_snap and today_snap.get("claudian_result"):
            claudian_result = today_snap["claudian_result"]

    snapshot = snapshot_from_lint(lint_result, claudian_result)
    add_snapshot(snapshot)

    # 更新 state
    state = load_state()
    state["last_lint_date"] = snapshot["snapshot_date"]
    state["total_issues"] = snapshot["total_issues"]
    state["error_count"] = snapshot["error_count"]
    state["warn_count"] = snapshot["warn_count"]
    state["info_count"] = snapshot["info_count"]
    state["auto_fixed_count"] = snapshot["auto_fixed_count"]
    state["objective_score"] = snapshot["objective_score"]
    state["health_score"] = snapshot["health_score"]
    if claudian_result:
        state["claudian_score"] = snapshot["claudian_score"]
        state["last_claudian_eval_date"] = snapshot["snapshot_date"]
    # 重置下次体检日期
    state["maintenance"]["next_vault_lint"] = str(date.today() + timedelta(days=OBSIDIAN_MAINTENANCE["vault_lint"]))
    save_state(state)

    # 更新 manifest 的 last_audit_date
    manifest = load_manifest()
    manifest["_meta"]["last_audit_date"] = snapshot["snapshot_date"]
    save_manifest(manifest)

    return snapshot


# ─── Claudian 评估 ───

def generate_claudian_prompt() -> str:
    """从 manifest.json 的 claudian_prompt_template + benchmark_files 生成提示词

    用字符串替换而非 str.format，避免 JSON 花括号被误解析。
    """
    manifest = load_manifest()
    template = manifest.get("claudian_prompt_template", "")
    benchmark_files = manifest.get("benchmark_files", [])

    today = str(date.today())
    benchmark_list = "\n".join(f"{i+1}. {f}" for i, f in enumerate(benchmark_files))

    # 安全替换：只替换 {date} 和 {benchmark_list} 两个占位符
    # 不用 str.format（会误解析 JSON 的 {}）
    result = template.replace("{date}", today).replace("{benchmark_list}", benchmark_list)
    return result


def save_claudian_result(json_str: str) -> str:
    """保存用户从 Claudian 回贴的 JSON 结果，返回文件路径

    Args:
        json_str: Claudian 输出的 JSON 字符串
    Returns:
        保存的文件路径
    """
    OBSIDIAN_CLAUDIAN_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    today = str(date.today())

    # 解析 + 校验
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON 解析失败: {e}")

    # 保存原始 JSON
    report_path = OBSIDIAN_CLAUDIAN_REPORTS_DIR / f"{today}_report.json"
    report_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    # 同步到 state + 最新快照
    state = load_state()
    state["last_claudian_eval_date"] = today

    # 把 Claudian 结果合并到最新一条体检快照
    snapshots = load_snapshots()
    if snapshots and snapshots[-1].get("snapshot_date") == today:
        # 合并到今天的快照
        snapshots[-1] = snapshot_from_lint(
            snapshots[-1].get("lint_result", {}), claudian_result=data
        )
        save_snapshots(snapshots)
        state["claudian_score"] = snapshots[-1].get("claudian_score")
        state["health_score"] = snapshots[-1].get("health_score")
    else:
        # 没有今天的快照，单独存 claudian_score
        scores = data.get("scores", {})
        score_values = [s.get("score", 0) for s in scores.values()] if isinstance(scores, dict) else []
        if score_values:
            claudian_score = round(sum(score_values) / len(score_values) * 20, 1)
            state["claudian_score"] = claudian_score

    state["maintenance"]["next_claudian_evaluation"] = str(
        date.today() + timedelta(days=OBSIDIAN_MAINTENANCE["claudian_evaluation"])
    )
    save_state(state)

    return str(report_path)


def load_latest_claudian_report() -> dict | None:
    """加载最新的 Claudian 评估报告"""
    if not OBSIDIAN_CLAUDIAN_REPORTS_DIR.exists():
        return None
    reports = sorted(OBSIDIAN_CLAUDIAN_REPORTS_DIR.glob("*_report.json"), reverse=True)
    if not reports:
        return None
    try:
        return json.loads(reports[0].read_text(encoding="utf-8"))
    except Exception:
        return None


def list_claudian_reports() -> list[dict]:
    """列出所有 Claudian 报告"""
    if not OBSIDIAN_CLAUDIAN_REPORTS_DIR.exists():
        return []
    reports = []
    for p in sorted(OBSIDIAN_CLAUDIAN_REPORTS_DIR.glob("*_report.json"), reverse=True):
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            reports.append({
                "file": p.name,
                "date": data.get("eval_date", p.stem[:10]),
                "overall_score": data.get("overall_score"),
                "overall_rating": data.get("overall_rating"),
                "summary": data.get("summary", ""),
            })
        except Exception:
            continue
    return reports


# ─── 经验卡沉淀 ───

EXPERIENCE_CARD_TEMPLATE = """---
type: 跑通打法
date: {date}
tags: [知识库评估, vault体检, 版本校准]
---

# {title}

## 场景

{scene}

## 做法

{steps}

## 结果

{result}

## 坑

{pitfalls}

## 沉淀

{lessons}

## 相关

{related}
"""


def list_experience_cards() -> list[dict]:
    """列出 raw/日常沉淀/ 下所有经验卡"""
    if not EXPERIENCE_CARD_DIR.exists():
        return []
    cards = []
    for p in sorted(EXPERIENCE_CARD_DIR.glob("*.md"), reverse=True):
        if p.name.startswith("_"):
            continue
        # 读前 5 行提取 title
        try:
            first_lines = p.read_text(encoding="utf-8").split("\n", 10)
            title = p.stem
            for line in first_lines:
                if line.startswith("# "):
                    title = line[2:].strip()
                    break
            cards.append({
                "file": p.name,
                "path": str(p),
                "title": title,
                "modified": datetime.fromtimestamp(p.stat().st_mtime).strftime("%Y-%m-%d %H:%M"),
            })
        except Exception:
            continue
    return cards


def create_experience_card(
    title: str,
    scene: str,
    steps: str,
    result: str,
    pitfalls: str,
    lessons: str,
    related: str,
) -> str:
    """生成经验卡写入 raw/日常沉淀/，返回文件路径

    严格对齐已有 5 份经验卡的 6 段结构（场景/做法/结果/坑/沉淀/相关）
    """
    EXPERIENCE_CARD_DIR.mkdir(parents=True, exist_ok=True)
    today = str(date.today())

    # 文件名：YYYY-MM-DD_<slug>.md
    slug = title.replace(" ", "-").replace("/", "-")[:40]
    filename = f"{today}_{slug}.md"
    filepath = EXPERIENCE_CARD_DIR / filename

    content = EXPERIENCE_CARD_TEMPLATE.format(
        date=today,
        title=title,
        scene=scene,
        steps=steps,
        result=result,
        pitfalls=pitfalls,
        lessons=lessons,
        related=related,
    )

    filepath.write_text(content, encoding="utf-8")
    return str(filepath)


# ─── vault log.md 追加（对齐已有 4 次 lint 记录格式）───

LOG_APPEND_TEMPLATE = """
## [{date}] lint | {issues} issues found, {fixed} auto-fixed

### 确定性检查
{deterministic_summary}

### 自动修复（{fixed} 项）
{auto_fix_details}

### 启发式检查（只报告，{heuristic_count} 项）
{heuristic_summary}

### 孤岛页面 / 跨文章事实矛盾
{orphan_contradiction}

### 知识库现状
- {wiki_count} 篇 wiki，{topic_count} 主题有内容，{orphan_count} 孤岛，{dead_link_count} 失效链接，{contradiction_count} 事实矛盾。
"""


def append_log_entry(lint_result: dict) -> str:
    """体检完成后追加 log.md 记录，对齐已有格式

    Returns: 追加的内容
    """
    log_path = OBSIDIAN_VAULT_DIR / "wiki" / "log.md"
    today = str(date.today())

    details = lint_result.get("details", {})
    all_issues = []
    for category, items in details.items():
        for item in items:
            all_issues.append({**item, "category": category})

    errors = [i for i in all_issues if i.get("status") == "error"]
    warns = [i for i in all_issues if i.get("status") == "warn"]
    infos = [i for i in all_issues if i.get("status") == "info"]
    auto_fixed = lint_result.get("auto_fixed_count", 0)

    # 确定性检查摘要
    deterministic = [i for i in all_issues if i.get("category") == "deterministic"]
    det_summary = "\n".join(
        f"- {i.get('rule', '?')}: {i.get('msg', '')}" for i in deterministic[:10]
    ) or "- 全部通过 ✓"

    # 自动修复详情
    fixes = lint_result.get("auto_fixes", [])
    fix_details = "\n".join(f"{i+1}. {f.get('msg', '')}" for i, f in enumerate(fixes[:10])) or "- 本轮无自动修复"

    # 启发式检查
    heuristic = [i for i in all_issues if i.get("category") == "heuristic"]
    heu_summary = "\n".join(
        f"{i+1}. {h.get('rule', '?')}: {h.get('msg', '')}" for i, h in enumerate(heuristic[:10])
    ) or "- 无启发式问题"

    # 孤岛 + 矛盾
    orphans = [i for i in all_issues if i.get("rule") == "orphan_pages"]
    contradictions = [i for i in all_issues if i.get("rule") == "fact_contradictions"]
    orphan_section = "\n".join(f"- **{o.get('file', '?')}**: {o.get('msg', '')}" for o in orphans) or "- 无孤岛"
    contradiction_section = "\n".join(f"- {c.get('msg', '')}" for c in contradictions) or "- 无实质矛盾"

    # 知识库现状统计
    wiki_dir = OBSIDIAN_VAULT_DIR / "wiki"
    wiki_count = len(list(wiki_dir.rglob("*.md"))) - 2 if wiki_dir.exists() else 0  # 减去 index.md + log.md
    topic_count = len([d for d in (wiki_dir).iterdir() if d.is_dir()]) if wiki_dir.exists() else 0

    entry = LOG_APPEND_TEMPLATE.format(
        date=today,
        issues=len(all_issues),
        fixed=auto_fixed,
        deterministic_summary=det_summary,
        auto_fix_details=fix_details,
        heuristic_count=len(heuristic),
        heuristic_summary=heu_summary,
        orphan_contradiction=f"### 孤岛页面\n{orphan_section}\n\n### 事实矛盾\n{contradiction_section}",
        wiki_count=wiki_count,
        topic_count=topic_count,
        orphan_count=len(orphans),
        dead_link_count=len([i for i in all_issues if i.get("rule") == "internal_dead_links"]),
        contradiction_count=len(contradictions),
    )

    # 追加到 log.md
    if log_path.exists():
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)
    else:
        log_path.write_text(entry, encoding="utf-8")

    return entry


# ─── 综合健康度评分 ───

def compute_health_score(objective_score: float, claudian_score: float | None = None) -> float:
    """综合健康度 = 客观分 70% + 语义分 30%"""
    if claudian_score is None:
        return round(objective_score, 1)
    return round(objective_score * 0.7 + claudian_score * 0.3, 1)
