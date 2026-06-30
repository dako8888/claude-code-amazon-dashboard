"""
Obsidian 知识库体检脚本 — vault_lint.py

12 项检查 + auto_fix + 双输出（终端彩色 + --json）

用法：
    python vault_lint.py                    # 跑检查，终端彩色输出
    python vault_lint.py --json             # 跑检查，JSON 输出
    python vault_lint.py --fix              # 跑检查 + 应用自动修复
    python vault_lint.py --json --fix       # 跑检查 + 修复，JSON 输出

退出码：0 全通过 / 1 仅告警 / 2 有错误

设计参考：C:\\Users\\Administrator\\.claude\\skills\\amazon-ads-analyzer\\scripts\\pre_release_check.py
"""
import argparse
import io
import json
import re
import shutil
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Windows GBK 终端兼容：强制 stdout UTF-8
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

# 从 Dashboard config 读 vault 路径
DASHBOARD_DIR = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(DASHBOARD_DIR))
from config import (
    OBSIDIAN_VAULT_DIR,
    OBSIDIAN_AUDIT_DIR,
    OBSIDIAN_MANIFEST_PATH,
)

# ─── 配置加载 ───

def load_manifest() -> dict:
    if OBSIDIAN_MANIFEST_PATH.exists():
        try:
            return json.loads(OBSIDIAN_MANIFEST_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}


MANIFEST = load_manifest()
THRESHOLDS = MANIFEST.get("thresholds", {})
EXCLUDE_FILES = set(MANIFEST.get("exclude_files", []))
EXCLUDE_DIRS = set(MANIFEST.get("exclude_directories", ["_audit", ".obsidian", "assets"]))
RAW_TOPIC_QUOTAS = MANIFEST.get("raw_topic_quotas", {})
AUTO_FIX_CONFIG = MANIFEST.get("auto_fix_config", {"backup_before_fix": True, "backup_dir": "_audit/backups/", "backup_suffix": ".bak"})

# ─── 辅助函数 ───

def collect_md_files(root: Path, sub: str = "") -> list[Path]:
    """收集指定子目录下所有 .md 文件，排除约定目录"""
    base = root / sub if sub else root
    if not base.exists():
        return []
    files = []
    for p in base.rglob("*.md"):
        # 排除目录
        rel_parts = p.relative_to(root).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        # 排除文件
        rel_str = str(p.relative_to(root)).replace("\\", "/")
        if rel_str in EXCLUDE_FILES:
            continue
        files.append(p)
    return files


def extract_markdown_links(content: str) -> list[tuple[int, str, str]]:
    """提取标准 markdown 链接 [text](path)，返回 [(line_no, text, path), ...]"""
    links = []
    for i, line in enumerate(content.split("\n"), 1):
        # 匹配 [text](path.md) 但排除图片 ![alt](path)
        for m in re.finditer(r"(?<!\!)\[([^\]]+)\]\(([^)]+)\)", line):
            links.append((i, m.group(1), m.group(2)))
    return links


def extract_wikilinks(content: str) -> list[tuple[int, str]]:
    """提取 [[wikilink]] 格式链接"""
    links = []
    for i, line in enumerate(content.split("\n"), 1):
        for m in re.finditer(r"\[\[([^\]]+)\]\]", line):
            links.append((i, m.group(1)))
    return links


def resolve_link(src_file: Path, link_path: str, vault_root: Path) -> Path | None:
    """解析 wiki 文章里的相对链接，返回实际文件路径（不存在则 None）"""
    # 去掉 anchor
    link_path = link_path.split("#")[0]
    if not link_path:
        return None
    # 相对 src_file 解析
    target = (src_file.parent / link_path).resolve()
    if target.exists():
        return target
    # 尝试相对 vault root
    target2 = (vault_root / link_path).resolve()
    if target2.exists():
        return target2
    return None


def find_file_by_name(vault_root: Path, filename: str) -> Path | None:
    """在 vault 全局找同名文件（死链修复用）"""
    if not filename:
        return None
    for p in vault_root.rglob(filename):
        rel_parts = p.relative_to(vault_root).parts
        if any(part in EXCLUDE_DIRS for part in rel_parts):
            continue
        return p
    return None


def backup_file(filepath: Path) -> Path | None:
    """备份文件到 _audit/backups/，返回备份路径"""
    if not AUTO_FIX_CONFIG.get("backup_before_fix", True):
        return None
    backup_dir = OBSIDIAN_VAULT_DIR / AUTO_FIX_CONFIG.get("backup_dir", "_audit/backups/")
    backup_dir.mkdir(parents=True, exist_ok=True)
    # 用相对路径做备份文件名，避免冲突
    rel = filepath.relative_to(OBSIDIAN_VAULT_DIR)
    backup_name = str(rel).replace("\\", "_").replace("/", "_") + AUTO_FIX_CONFIG.get("backup_suffix", ".bak")
    backup_path = backup_dir / backup_name
    shutil.copy2(filepath, backup_path)
    return backup_path


# ─── 检查项数据结构 ───
# 每个检查函数返回 list[dict]，dict 格式：
#   {file, status: "ok"|"warn"|"error", rule, msg, line_no?, auto_fixable?}
# auto_fix 函数接收 issue dict，返回 {fixed: bool, msg: str, backup?: str}

results_by_category = {
    "deterministic": [],
    "structure_timeliness": [],
    "heuristic": [],
    "log_check": [],
}
auto_fixes_applied = []


def add_issue(category: str, file: str, status: str, rule: str, msg: str,
              line_no: int | None = None, auto_fixable: bool = False):
    issue = {
        "file": file,
        "status": status,
        "rule": rule,
        "msg": msg,
        "auto_fixable": auto_fixable,
    }
    if line_no is not None:
        issue["line_no"] = line_no
    results_by_category[category].append(issue)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Part 1: 确定性检查（5 项，可自动修复，只改 wiki/）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def check_index_file_consistency(vault_root: Path):
    """wiki/index.md ↔ 实际文件一致性"""
    index_path = vault_root / "wiki" / "index.md"
    wiki_dir = vault_root / "wiki"

    if not index_path.exists():
        add_issue("deterministic", str(index_path.relative_to(vault_root)), "error",
                  "index_file_consistency", "wiki/index.md 不存在", auto_fixable=False)
        return

    index_content = index_path.read_text(encoding="utf-8")

    # 收集所有 wiki 文章（排除 index.md/log.md）
    wiki_files = collect_md_files(vault_root, "wiki")
    article_files = [f for f in wiki_files if f.name not in ("index.md", "log.md")]

    # 提取 index.md 中的所有 markdown 链接
    index_links = extract_markdown_links(index_content)
    index_link_paths = set()
    for _, text, path in index_links:
        # 只看指向 .md 的链接
        if path.endswith(".md"):
            resolved = resolve_link(index_path, path, vault_root)
            if resolved:
                index_link_paths.add(str(resolved))

    # 检查：文件存在但索引缺
    for f in article_files:
        if str(f) not in index_link_paths and str(f.resolve()) not in index_link_paths:
            rel = str(f.relative_to(vault_root)).replace("\\", "/")
            add_issue("deterministic", rel, "error",
                      "index_file_consistency",
                      f"文件存在但 index.md 缺失条目",
                      auto_fixable=True)

    # 检查：索引指向死文件
    for _, text, path in index_links:
        if path.endswith(".md") and not resolve_link(index_path, path, vault_root):
            add_issue("deterministic", "wiki/index.md", "error",
                      "index_file_consistency",
                      f"索引指向死文件: [{text}]({path})",
                      auto_fixable=True)


def check_internal_dead_links(vault_root: Path):
    """wiki 内部 markdown 链接死链检测"""
    wiki_files = collect_md_files(vault_root, "wiki")

    for f in wiki_files:
        content = f.read_text(encoding="utf-8")
        links = extract_markdown_links(content)
        for line_no, text, path in links:
            # 跳过外链、anchor、图片
            if path.startswith(("http://", "https://", "mailto:")):
                continue
            if path.startswith("#"):
                continue
            if not path.endswith(".md"):
                continue

            resolved = resolve_link(f, path, vault_root)
            if not resolved:
                rel = str(f.relative_to(vault_root)).replace("\\", "/")
                # 尝试找同名文件
                filename = Path(path).name
                alt = find_file_by_name(vault_root, filename)
                if alt:
                    add_issue("deterministic", rel, "error",
                              "internal_dead_links",
                              f"L{line_no}: 链接 [{text}]({path}) 死链，但找到同名文件 {alt.relative_to(vault_root)}",
                              line_no=line_no, auto_fixable=True)
                else:
                    add_issue("deterministic", rel, "error",
                              "internal_dead_links",
                              f"L{line_no}: 链接 [{text}]({path}) 死链，未找到同名文件",
                              line_no=line_no, auto_fixable=False)


def check_see_also_links(vault_root: Path):
    """See Also 链接指向已删文件"""
    wiki_files = collect_md_files(vault_root, "wiki")

    for f in wiki_files:
        content = f.read_text(encoding="utf-8")
        # 找 See Also 段落
        see_also_match = re.search(r"^##\s*See Also\s*$(.*?)(?=^##\s|\Z)", content, re.MULTILINE | re.DOTALL)
        if not see_also_match:
            continue
        see_also_section = see_also_match.group(1)
        links = extract_markdown_links(see_also_section)
        for line_no, text, path in links:
            if path.startswith(("http://", "https://")):
                continue
            if not path.endswith(".md"):
                continue
            # line_no 需要加上 See Also 段落偏移
            section_start = see_also_match.start()
            lines_before = content[:section_start].count("\n") + 1
            actual_line = lines_before + line_no

            resolved = resolve_link(f, path, vault_root)
            if not resolved:
                rel = str(f.relative_to(vault_root)).replace("\\", "/")
                add_issue("deterministic", rel, "warn",
                          "see_also_links",
                          f"L{actual_line}: See Also 指向死文件 [{text}]({path})",
                          line_no=actual_line, auto_fixable=True)


def check_see_also_format(vault_root: Path):
    """See Also 用 [[wikilink]] 而非 [text](path) 标准格式"""
    wiki_files = collect_md_files(vault_root, "wiki")

    for f in wiki_files:
        content = f.read_text(encoding="utf-8")
        see_also_match = re.search(r"^##\s*See Also\s*$(.*?)(?=^##\s|\Z)", content, re.MULTILINE | re.DOTALL)
        if not see_also_match:
            continue
        see_also_section = see_also_match.group(1)
        wikilinks = extract_wikilinks(see_also_section)
        if not wikilinks:
            continue

        section_start = see_also_match.start()
        lines_before = content[:section_start].count("\n") + 1
        rel = str(f.relative_to(vault_root)).replace("\\", "/")

        for line_no, wikilink in wikilinks:
            actual_line = lines_before + line_no
            add_issue("deterministic", rel, "warn",
                      "see_also_format",
                      f"L{actual_line}: See Also 用 [[{wikilink}]] 应改为标准 markdown 格式",
                      line_no=actual_line, auto_fixable=True)


def check_frontmatter_dates(vault_root: Path):
    """Skill 文档双日期标注（frontmatter 版本日期 vs 源文件 mtime）"""
    # 这个检查针对 raw/Skill设计/ 下的 SKILL.md，但 raw 不改，只报告
    # wiki 文章里 §二 的 Skill 版本标注应该有双日期
    wiki_skill_doc = vault_root / "wiki" / "Skill设计" / "Skill 3.0架构与实现.md"
    if not wiki_skill_doc.exists():
        return

    content = wiki_skill_doc.read_text(encoding="utf-8")
    # 找 §二.x 下的版本标注，检查是否有 frontmatter 日期 vs mtime 双标注
    # 简化版：检查是否含 "frontmatter" 和 "mtime" 关键词（已有则通过）
    skill_sections = re.findall(r"^###\s*§?二\.?\d*.*?$.*?(?=^###|\Z)", content, re.MULTILINE | re.DOTALL)

    for section in skill_sections:
        # 提取 Skill 名
        name_match = re.match(r"^###\s*(?:§二\.)?(\d+)\s+(.+?)\s*(?:v\d|$)", section, re.MULTILINE)
        if not name_match:
            continue
        skill_name = name_match.group(2).strip()

        # 检查是否有双日期标注（frontmatter 日期 vs mtime）
        has_frontmatter_date = "frontmatter" in section.lower()
        has_mtime = "mtime" in section.lower() or "源文件实际修改" in section

        # 如果版本日期较新（2026-06-26 之后）但没有双标注，告警
        # 简化：只报告没有 ⚠️ 双日期标注的 Skill 段落
        if not has_frontmatter_date and "v" in section:
            add_issue("deterministic", "wiki/Skill设计/Skill 3.0架构与实现.md", "warn",
                      "frontmatter_dates",
                      f"§二 {skill_name} 缺少 frontmatter 日期 vs mtime 双标注",
                      auto_fixable=False)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Part 2: 结构 + 时效（4 项，仅报告）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def check_raw_topic_coverage(vault_root: Path):
    """raw/ 各主题文件数 + 空目录标记"""
    raw_dir = vault_root / "raw"
    if not raw_dir.exists():
        add_issue("structure_timeliness", "raw/", "error",
                  "raw_topic_coverage", "raw/ 目录不存在", auto_fixable=False)
        return

    for topic_dir in sorted(raw_dir.iterdir()):
        if not topic_dir.is_dir():
            continue
        md_count = len(list(topic_dir.rglob("*.md")))
        rel = str(topic_dir.relative_to(vault_root)).replace("\\", "/") + "/"

        quota = RAW_TOPIC_QUOTAS.get(topic_dir.name, {})
        min_files = quota.get("min", 1)

        if md_count == 0:
            add_issue("structure_timeliness", rel, "info",
                      "raw_topic_coverage",
                      f"空目录（index.md 标 [待 ingest]）",
                      auto_fixable=False)
        elif md_count < min_files:
            add_issue("structure_timeliness", rel, "warn",
                      "raw_topic_coverage",
                      f"仅 {md_count} 个文件（建议 ≥{min_files}）",
                      auto_fixable=False)


def check_wiki_index_coverage(vault_root: Path):
    """wiki 文章是否全在 index.md 注册"""
    index_path = vault_root / "wiki" / "index.md"
    wiki_files = collect_md_files(vault_root, "wiki")
    article_files = [f for f in wiki_files if f.name not in ("index.md", "log.md")]

    if not index_path.exists():
        return  # check_index_file_consistency 已报告

    index_content = index_path.read_text(encoding="utf-8")
    index_links = extract_markdown_links(index_content)
    index_link_paths = set()
    for _, _, path in index_links:
        if path.endswith(".md"):
            resolved = resolve_link(index_path, path, vault_root)
            if resolved:
                index_link_paths.add(str(resolved))

    for f in article_files:
        if str(f) not in index_link_paths and str(f.resolve()) not in index_link_paths:
            rel = str(f.relative_to(vault_root)).replace("\\", "/")
            add_issue("structure_timeliness", rel, "warn",
                      "wiki_index_coverage",
                      "wiki 文章未在 index.md 注册",
                      auto_fixable=False)


def check_file_staleness(vault_root: Path):
    """文件 Updated 日期距今 >90 天"""
    wiki_files = collect_md_files(vault_root, "wiki")
    threshold = THRESHOLDS.get("file_staleness_days", 90)
    today = date.today()

    for f in wiki_files:
        if f.name in ("index.md", "log.md"):
            continue
        content = f.read_text(encoding="utf-8")
        # 找 Updated: YYYY-MM-DD
        m = re.search(r"Updated[:\s]+(\d{4}-\d{2}-\d{2})", content)
        if not m:
            continue
        try:
            updated_date = datetime.strptime(m.group(1), "%Y-%m-%d").date()
            days = (today - updated_date).days
            if days > threshold:
                rel = str(f.relative_to(vault_root)).replace("\\", "/")
                add_issue("structure_timeliness", rel, "warn",
                          "file_staleness",
                          f"上次更新 {days} 天前（>{threshold}天），建议复核时效性",
                          auto_fixable=False)
        except ValueError:
            continue


def check_deprecated_annotations(vault_root: Path):
    """过时标注格式完整性（日期 + raw 引用 + 最新做法三要素）

    只检查真正的"过时校准"标注（含 过时/已于/已过时 关键词），
    不检查其他用途的 ⚠️（历史快照说明/维度澄清/版本警告等）。
    """
    wiki_files = collect_md_files(vault_root, "wiki")
    # 过时校准关键词
    deprecated_keywords = ["过时", "已于", "已过时", "已弃用", "已废弃", "经实战发现"]

    for f in wiki_files:
        content = f.read_text(encoding="utf-8")
        for i, line in enumerate(content.split("\n"), 1):
            if not (line.strip().startswith(">") and "⚠️" in line):
                continue
            # 必须含过时校准关键词才检查
            if not any(kw in line for kw in deprecated_keywords):
                continue

            # 检查三要素：日期、raw 引用、最新做法
            has_date = bool(re.search(r"\d{4}-\d{2}-\d{2}", line))
            has_raw_ref = "raw/" in line or "日常沉淀" in line
            if not has_date or not has_raw_ref:
                rel = str(f.relative_to(vault_root)).replace("\\", "/")
                missing = []
                if not has_date: missing.append("日期")
                if not has_raw_ref: missing.append("raw 引用")
                add_issue("structure_timeliness", rel, "warn",
                          "deprecated_annotations",
                          f"过时标注缺少 {'+'.join(missing)}（标准：日期+raw引用+最新做法）",
                          line_no=i, auto_fixable=False)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Part 3: 启发式检查（3 项，仅报告）
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def check_orphan_pages(vault_root: Path):
    """无入链的 wiki 孤岛页面"""
    wiki_files = collect_md_files(vault_root, "wiki")
    article_files = [f for f in wiki_files if f.name not in ("index.md", "log.md")]

    # 建立入链索引
    incoming = {str(f): set() for f in article_files}
    for f in wiki_files:
        content = f.read_text(encoding="utf-8")
        links = extract_markdown_links(content)
        for _, text, path in links:
            if not path.endswith(".md") or path.startswith(("http://", "https://")):
                continue
            resolved = resolve_link(f, path, vault_root)
            if resolved:
                resolved_str = str(resolved)
                if resolved_str in incoming:
                    incoming[resolved_str].add(str(f))

    for f in article_files:
        f_str = str(f)
        if not incoming.get(f_str):
            rel = str(f.relative_to(vault_root)).replace("\\", "/")
            add_issue("heuristic", rel, "warn",
                      "orphan_pages",
                      "无任何文章引用此页面（孤岛）",
                      auto_fixable=False)


def check_cross_topic_missing_links(vault_root: Path):
    """跨主题该链未链的概念（简化版：基于关键词匹配）"""
    # 这个检查较复杂，简化版：检查已知配对（A+模块设计 ↔ 选品方法论）等
    # 实际生产中应由 Claudian 启发式判断
    known_pairs = [
        ("wiki/视觉设计/A+与品牌旗舰店模块设计.md", "wiki/选品开发/选品方法论与品牌布局.md"),
    ]
    for src_rel, tgt_rel in known_pairs:
        src = vault_root / src_rel
        tgt = vault_root / tgt_rel
        if not src.exists() or not tgt.exists():
            continue
        content = src.read_text(encoding="utf-8")
        # 检查是否已有链接指向 tgt
        tgt_name = tgt.stem
        if tgt_name not in content and tgt_rel not in content:
            add_issue("heuristic", src_rel, "warn",
                      "cross_topic_missing_links",
                      f"建议添加 See Also 指向 {tgt_rel}（上下游依赖）",
                      auto_fixable=False)


def check_concept_repeat(vault_root: Path):
    """反复提及但没独立成页的概念"""
    # 简化版：检查已知候选概念（否定词策略/千问视觉评估/AMC）
    candidates = ["否定词", "Negative Keywords", "千问视觉评估", "evaluate_image", "AMC", "Amazon Marketing Cloud"]
    min_mentions = THRESHOLDS.get("concept_repeat_min_mentions", 3)

    wiki_files = collect_md_files(vault_root, "wiki")
    for concept in candidates:
        mentions = []
        for f in wiki_files:
            content = f.read_text(encoding="utf-8")
            count = content.lower().count(concept.lower())
            if count >= 1:
                mentions.append((f, count))

        total = sum(c for _, c in mentions)
        if total >= min_mentions:
            # 检查是否有独立页面
            has_standalone = any(concept.lower() in f.stem.lower() for f in wiki_files)
            if not has_standalone:
                files_list = ", ".join(str(f.relative_to(vault_root)).replace("\\", "/") for f, _ in mentions[:5])
                add_issue("heuristic", "wiki/", "info",
                          "concept_repeat",
                          f"概念 '{concept}' 在 {len(mentions)} 篇文章提及 {total} 次但未独立成页（候选拆分）— 涉及: {files_list}",
                          auto_fixable=False)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Part 4: 日志连续性
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def check_log_continuity(vault_root: Path):
    """log.md 最近 lint 记录距今天数"""
    log_path = vault_root / "wiki" / "log.md"
    if not log_path.exists():
        add_issue("log_check", "wiki/log.md", "error",
                  "log_continuity", "log.md 不存在", auto_fixable=False)
        return

    content = log_path.read_text(encoding="utf-8")
    # 找最近的 lint 记录日期
    lint_dates = re.findall(r"^##\s*\[(\d{4}-\d{2}-\d{2})\]\s*lint", content, re.MULTILINE)
    if not lint_dates:
        add_issue("log_check", "wiki/log.md", "info",
                  "log_continuity", "无 lint 记录", auto_fixable=False)
        return

    try:
        latest = datetime.strptime(lint_dates[-1], "%Y-%m-%d").date()
        days = (date.today() - latest).days
        threshold = THRESHOLDS.get("log_continuity_warn_days", 14)
        if days > threshold:
            add_issue("log_check", "wiki/log.md", "info",
                      "log_continuity",
                      f"上次 lint: {days} 天前（>{threshold}天），建议定期体检",
                      auto_fixable=False)
    except ValueError:
        pass


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# auto_fix 函数
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def auto_fix_issue(issue: dict, vault_root: Path) -> dict:
    """对单个 issue 应用自动修复，返回 {fixed, msg, backup?}"""
    rule = issue.get("rule")
    file_rel = issue.get("file", "")
    filepath = vault_root / file_rel

    if not filepath.exists():
        return {"fixed": False, "msg": f"文件不存在: {file_rel}"}

    backup = backup_file(filepath) if rule != "index_file_consistency" else None

    try:
        if rule == "index_file_consistency" and "缺失条目" in issue.get("msg", ""):
            # 补 index.md 条目
            index_path = vault_root / "wiki" / "index.md"
            backup = backup_file(index_path)
            content = index_path.read_text(encoding="utf-8")
            # 提取文章第一行 H1 作为标题
            article_content = filepath.read_text(encoding="utf-8")
            title_match = re.search(r"^#\s+(.+)$", article_content, re.MULTILINE)
            title = title_match.group(1).strip() if title_match else filepath.stem

            # 找对应主题段落
            topic = filepath.parent.name
            topic_pattern = re.compile(rf"^##\s+{re.escape(topic)}\s*$.*?(?=^##\s|\Z)", re.MULTILINE | re.DOTALL)
            new_entry = f"\n- [{title}]({file_rel.replace('wiki/', '').replace(chr(92), '/')}) — 待补摘要 Updated {date.today()}"

            if topic_pattern.search(content):
                content = topic_pattern.sub(lambda m: m.group(0).rstrip() + new_entry, content)
            else:
                content += f"\n\n## {topic}\n{new_entry.strip()}\n"

            index_path.write_text(content, encoding="utf-8")
            return {"fixed": True, "msg": f"补 index.md 条目: {title}", "backup": str(backup) if backup else None}

        elif rule == "internal_dead_links" and "找到同名文件" in issue.get("msg", ""):
            # 改链接路径
            content = filepath.read_text(encoding="utf-8")
            line_no = issue.get("line_no", 0)
            lines = content.split("\n")
            if 0 < line_no <= len(lines):
                line = lines[line_no - 1]
                # 找死链的同名文件
                old_link_match = re.search(r"\[([^\]]+)\]\(([^)]+)\)", line)
                if old_link_match:
                    old_path = old_link_match.group(2)
                    filename = Path(old_path).name
                    alt = find_file_by_name(vault_root, filename)
                    if alt:
                        # 计算相对路径
                        new_path = Path("..") / alt.relative_to(vault_root / "wiki")
                        new_path_str = str(new_path).replace("\\", "/")
                        new_line = line.replace(f"]({old_path}", f"]({new_path_str}")
                        lines[line_no - 1] = new_line
                        filepath.write_text("\n".join(lines), encoding="utf-8")
                        return {"fixed": True, "msg": f"修复死链: {old_path} → {new_path_str}", "backup": str(backup) if backup else None}

            return {"fixed": False, "msg": "无法定位死链行"}

        elif rule == "see_also_links":
            # 删失效 See Also 链接
            content = filepath.read_text(encoding="utf-8")
            line_no = issue.get("line_no", 0)
            lines = content.split("\n")
            if 0 < line_no <= len(lines):
                # 找该行的 markdown 链接，删除整行
                old_line = lines[line_no - 1]
                lines[line_no - 1] = ""  # 留空行避免行号错乱
                filepath.write_text("\n".join(lines), encoding="utf-8")
                return {"fixed": True, "msg": f"删失效 See Also: {old_line.strip()[:60]}", "backup": str(backup) if backup else None}

            return {"fixed": False, "msg": "无法定位 See Also 行"}

        elif rule == "see_also_format":
            # [[wikilink]] → [text](path)
            content = filepath.read_text(encoding="utf-8")
            line_no = issue.get("line_no", 0)
            lines = content.split("\n")
            if 0 < line_no <= len(lines):
                line = lines[line_no - 1]
                # 提取 wikilink
                m = re.search(r"\[\[([^\]]+)\]\]", line)
                if m:
                    wikilink = m.group(1)
                    # 找同名文件
                    alt = find_file_by_name(vault_root, wikilink + ".md") or find_file_by_name(vault_root, wikilink)
                    if alt:
                        new_path = Path("..") / alt.relative_to(vault_root / "wiki")
                        new_path_str = str(new_path).replace("\\", "/")
                        new_line = line.replace(f"[[{wikilink}]]", f"[{wikilink}]({new_path_str})")
                        lines[line_no - 1] = new_line
                        filepath.write_text("\n".join(lines), encoding="utf-8")
                        return {"fixed": True, "msg": f"格式统一: [[{wikilink}]] → [{wikilink}]({new_path_str})", "backup": str(backup) if backup else None}

            return {"fixed": False, "msg": "无法转换 wikilink"}

        else:
            return {"fixed": False, "msg": f"rule '{rule}' 无 auto_fix 实现"}

    except Exception as e:
        return {"fixed": False, "msg": f"修复异常: {e}", "backup": str(backup) if backup else None}


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 主流程
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_all_checks(vault_root: Path, apply_fix: bool = False) -> dict:
    """跑全部 12 项检查，返回结构化结果"""
    # 重置结果
    global results_by_category, auto_fixes_applied
    results_by_category = {k: [] for k in results_by_category}
    auto_fixes_applied = []

    # 确定性检查
    check_index_file_consistency(vault_root)
    check_internal_dead_links(vault_root)
    check_see_also_links(vault_root)
    check_see_also_format(vault_root)
    check_frontmatter_dates(vault_root)

    # 结构 + 时效
    check_raw_topic_coverage(vault_root)
    check_wiki_index_coverage(vault_root)
    check_file_staleness(vault_root)
    check_deprecated_annotations(vault_root)

    # 启发式
    check_orphan_pages(vault_root)
    check_cross_topic_missing_links(vault_root)
    check_concept_repeat(vault_root)

    # 日志
    check_log_continuity(vault_root)

    # 应用自动修复
    if apply_fix:
        for category, issues in results_by_category.items():
            for issue in issues[:]:
                if issue.get("auto_fixable"):
                    fix_result = auto_fix_issue(issue, vault_root)
                    if fix_result.get("fixed"):
                        auto_fixes_applied.append({
                            "rule": issue.get("rule"),
                            "file": issue.get("file"),
                            "msg": fix_result.get("msg"),
                            "backup": fix_result.get("backup"),
                        })
                        # 从问题列表移除已修复
                        issue["status"] = "ok"
                        issue["msg"] = f"[已修复] {issue['msg']}: {fix_result.get('msg')}"

    # 统计
    all_issues = []
    for category, issues in results_by_category.items():
        for issue in issues:
            issue["category"] = category
            all_issues.append(issue)

    errors = sum(1 for i in all_issues if i.get("status") == "error")
    warns = sum(1 for i in all_issues if i.get("status") == "warn")
    infos = sum(1 for i in all_issues if i.get("status") == "info")
    oks = sum(1 for i in all_issues if i.get("status") == "ok")

    return {
        "version": MANIFEST.get("_meta", {}).get("version", "1.0.0"),
        "audit_date": str(date.today()),
        "vault_root": str(vault_root),
        "total": len(all_issues),
        "ok": oks,
        "warnings": warns,
        "errors": errors,
        "infos": infos,
        "auto_fixed_count": len(auto_fixes_applied),
        "passed": errors == 0,
        "details": results_by_category,
        "auto_fixes": auto_fixes_applied,
    }


def print_terminal_report(result: dict):
    """终端彩色输出"""
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BLUE = "\033[94m"
    RESET = "\033[0m"
    BOLD = "\033[1m"

    print(f"\n{BOLD}=== AmazonKB 知识库体检报告 ==={RESET}")
    print(f"日期: {result['audit_date']}  版本: {result['version']}")
    print(f"Vault: {result['vault_root']}\n")

    # 汇总
    print(f"{BOLD}汇总:{RESET}")
    print(f"  {GREEN}[OK] 通过: {result['ok']}{RESET}")
    print(f"  {RED}[ERR] 错误: {result['errors']}{RESET}")
    print(f"  {YELLOW}[WARN] 告警: {result['warnings']}{RESET}")
    print(f"  {BLUE}[INFO] 信息: {result['infos']}{RESET}")
    if result.get("auto_fixed_count", 0) > 0:
        print(f"  {GREEN}[FIX] 已自动修复: {result['auto_fixed_count']}{RESET}")
    print()

    # 按类别
    category_names = {
        "deterministic": "确定性检查（可自动修复）",
        "structure_timeliness": "结构 + 时效",
        "heuristic": "启发式检查（仅报告）",
        "log_check": "日志连续性",
    }

    for category, name in category_names.items():
        issues = result["details"].get(category, [])
        non_ok = [i for i in issues if i.get("status") != "ok"]
        if not non_ok:
            print(f"{GREEN}[OK] {name}: 全部通过{RESET}")
            continue

        print(f"{BOLD}-- {name} ({len(non_ok)} 项) --{RESET}")
        for issue in non_ok:
            status = issue.get("status")
            icon = {"error": f"{RED}[ERR]{RESET}", "warn": f"{YELLOW}[WARN]{RESET}", "info": f"{BLUE}[INFO]{RESET}"}.get(status, "")
            file_short = issue.get("file", "?")
            if len(file_short) > 50:
                file_short = "..." + file_short[-47:]
            line_info = f" L{issue.get('line_no')}" if issue.get("line_no") else ""
            fix_tag = f" {GREEN}[可修复]{RESET}" if issue.get("auto_fixable") else ""
            print(f"  {icon} {file_short}{line_info}: {issue.get('msg', '')}{fix_tag}")
        print()

    # 自动修复详情
    if result.get("auto_fixes"):
        print(f"{BOLD}-- 自动修复（{len(result['auto_fixes'])} 项） --{RESET}")
        for i, fix in enumerate(result["auto_fixes"], 1):
            print(f"  {GREEN}{i}.{RESET} {fix.get('msg')}")
            if fix.get("backup"):
                print(f"      备份: {fix['backup']}")
        print()

    # 结论
    if result["passed"]:
        print(f"{GREEN}{BOLD}[PASS] 知识库健康{RESET}\n")
    else:
        print(f"{RED}{BOLD}[FAIL] 有 {result['errors']} 个错误需修复{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Obsidian 知识库体检脚本")
    parser.add_argument("--json", action="store_true", help="JSON 输出（供 Dashboard 解析）")
    parser.add_argument("--fix", action="store_true", help="应用自动修复（只改 wiki/，含备份）")
    parser.add_argument("--vault", type=str, default=str(OBSIDIAN_VAULT_DIR), help="vault 根目录（默认 E:\\Obsidian\\AmazonKB）")
    args = parser.parse_args()

    vault_root = Path(args.vault)
    if not vault_root.exists():
        if args.json:
            print(json.dumps({"error": f"vault 不存在: {vault_root}", "passed": False}, ensure_ascii=False))
        else:
            print(f"错误: vault 不存在: {vault_root}")
        sys.exit(2)

    result = run_all_checks(vault_root, apply_fix=args.fix)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_terminal_report(result)

    # 退出码：0 全通过 / 1 仅告警 / 2 有错误
    if result["errors"] > 0:
        sys.exit(2)
    elif result["warnings"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
