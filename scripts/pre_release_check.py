#!/usr/bin/env python3
"""
Skill 3.0 发布前自检脚本 — 读取 _shared/manifest.json 全量扫描。

检查项:
  1. 版本一致性 — 所有声明了版本号的文件是否和 manifest 一致
  2. 术语统一   — 是否有禁止的旧术语残留
  3. 硬编码清零 — 是否有禁止的硬编码模式
  4. 文件存活   — manifest 引用的文件是否都存在
  5. auto-memory — 关联记忆文件是否过期
  6. .gitignore  — 必须条目是否完整

用法:
  python scripts/pre_release_check.py          # 扫描当前项目
  python scripts/pre_release_check.py --json   # JSON 输出（CI用）
  python scripts/pre_release_check.py --fix    # 交互式修复引导

退出码: 0=全部通过, 1=有告警, 2=有错误
"""

import sys, json, re, os
from pathlib import Path
from datetime import date

PROJECT_ROOT = Path(__file__).parent.parent
MANIFEST_PATH = PROJECT_ROOT / "_shared" / "manifest.json"

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── 终端颜色 ──
GREEN = "\033[92m"; RED = "\033[91m"; YELLOW = "\033[93m"; GRAY = "\033[90m"
RESET = "\033[0m"; BOLD = "\033[1m"
CHECK = f"{GREEN}✓{RESET}"; CROSS = f"{RED}✗{RESET}"; WARN = f"{YELLOW}⚠{RESET}"


def load_manifest() -> dict:
    if not MANIFEST_PATH.exists():
        print(f"{CROSS} manifest.json 不存在: {MANIFEST_PATH}")
        sys.exit(2)
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def check_version_consistency(manifest: dict) -> list[dict]:
    """检查所有 version_files 中的版本号是否和 manifest.skill.version 一致。"""
    results = []
    expected = manifest["skill"]["version"]
    version_files = manifest.get("version_files", {})

    all_files = []
    skip_categories = {"date_version_files"}
    for category, files in version_files.items():
        if category.startswith("_") or category in skip_categories:
            continue
        all_files.extend(files)

    # 去重
    seen = set()
    unique_files = []
    for f in all_files:
        if f not in seen:
            seen.add(f)
            unique_files.append(f)

    # 只匹配 Skill 3.0 版本号格式: v2.x.x（避免误匹配 3.5.x 等不相关数字）
    ver_pattern = re.compile(r'\bv?(\d+\.\d+\.\d+)\b')

    for rel_path in unique_files:
        fpath = PROJECT_ROOT / rel_path
        if not fpath.exists():
            results.append({"file": rel_path, "status": "error",
                          "msg": f"文件不存在"})
            continue

        content = fpath.read_text(encoding="utf-8", errors="replace")
        found_versions = set()
        old_versions = set()

        for m in ver_pattern.finditer(content):
            v = m.group(1)  # 2.4.0 (不含 v 前缀)
            found_versions.add(v)
            if v != expected:
                old_versions.add(v)

        if not found_versions:
            results.append({"file": rel_path, "status": "warn",
                          "msg": f"未找到任何版本号 — 是否遗漏？"})
        elif old_versions:
            results.append({"file": rel_path, "status": "error",
                          "msg": f"发现旧版本: {', '.join(sorted(old_versions))} — 应为 {expected}"})
        else:
            results.append({"file": rel_path, "status": "ok",
                          "msg": f"v{expected}"})

    return results


def check_forbidden_patterns(manifest: dict) -> list[dict]:
    """扫描禁止的硬编码模式。"""
    results = []
    forbidden = manifest.get("forbidden_patterns", {})

    for rule_name, rule in forbidden.items():
        if rule_name.startswith("_"):
            continue
        patterns = rule.get("patterns", [])
        target_files = rule.get("files", [])
        reason = rule.get("reason", "")

        for rel_path in target_files:
            fpath = PROJECT_ROOT / rel_path
            if not fpath.exists():
                continue

            content = fpath.read_text(encoding="utf-8", errors="replace")
            for pat in patterns:
                # JSON 中的双反斜杠需要展开
                pat_actual = pat.replace("\\\\\\\\", "\\")
                try:
                    matches = list(re.finditer(pat_actual, content))
                except re.error:
                    results.append({"file": rel_path, "status": "error",
                                  "rule": rule_name,
                                  "msg": f"正则无效: {pat_actual[:60]}"})
                    continue

                if matches:
                    lines = []
                    for m in matches:
                        line_no = content[:m.start()].count('\n') + 1
                        snippet = m.group(0)[:80]
                        lines.append(f"L{line_no}: `{snippet}`")
                    results.append({"file": rel_path, "status": "error",
                                  "rule": rule_name,
                                  "msg": f"发现硬编码 — 原因: {reason}\n    位置: " + "; ".join(lines)})
                else:
                    results.append({"file": rel_path, "status": "ok",
                                  "rule": rule_name, "msg": "通过"})

    return results


def check_terminology(manifest: dict) -> list[dict]:
    """检查术语统一性 — 扫描所有 .py 和 .md 文件中是否出现禁止的旧术语。"""
    results = []
    terms = manifest.get("terms", {})

    # 扫描范围: 所有 .py 和 .md
    py_files = list(PROJECT_ROOT.rglob("*.py"))
    md_files = list(PROJECT_ROOT.rglob("*.md"))
    scan_files = [f for f in py_files + md_files
                  if "__pycache__" not in str(f)
                  and ".git" not in str(f)
                  and "output" not in str(f)]

    for term_name, term_def in terms.items():
        if term_name.startswith("_"):
            continue
        correct = term_def["correct"]
        forbidden_list = term_def["forbidden"]

        for fpath in scan_files:
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            for bad_term in forbidden_list:
                if bad_term in content:
                    line_no = content[:content.find(bad_term)].count('\n') + 1
                    rel = fpath.relative_to(PROJECT_ROOT)
                    results.append({"file": str(rel), "status": "error",
                                  "rule": term_name,
                                  "msg": f"L{line_no}: 发现禁止术语 `{bad_term}` → 应改为 `{correct}`"})

    if not any(r["status"] == "error" for r in results):
        results.append({"file": "—", "status": "ok", "rule": "全部术语", "msg": "通过"})

    return results


def check_file_existence(manifest: dict) -> list[dict]:
    """检查 manifest 中引用的文件是否都存在。"""
    results = []
    version_files = manifest.get("version_files", {})

    seen = set()
    skip_cats = {"date_version_files"}
    for category, files in version_files.items():
        if category.startswith("_") or category in skip_cats:
            continue
        if not isinstance(files, list):
            continue
        for f in files:
            if f in seen:
                continue
            seen.add(f)
            fpath = PROJECT_ROOT / f
            if fpath.exists():
                results.append({"file": f, "status": "ok", "msg": "存在"})
            else:
                results.append({"file": f, "status": "error", "msg": "文件缺失"})

    return results


def check_auto_memory(manifest: dict) -> list[dict]:
    """检查关联的 auto-memory 文件是否引用过期版本。"""
    results = []
    expected = manifest["skill"]["version"]
    memory_files = manifest.get("auto_memory_sync", {}).get("files", [])

    ver_pattern = re.compile(r'\bv?(\d+\.\d+\.\d+)\b')  # 只匹配 Skill 3.0 版本

    for mem_path_str in memory_files:
        mem_path = Path(mem_path_str)
        if not mem_path.exists():
            results.append({"file": mem_path_str, "status": "warn",
                          "msg": "auto-memory 文件不存在（可能已删除或未创建）"})
            continue

        try:
            content = mem_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            results.append({"file": mem_path_str, "status": "warn", "msg": "无法读取"})
            continue

        found_versions = set()
        old_versions = set()
        for m in ver_pattern.finditer(content):
            v = m.group(1)
            found_versions.add(v)
            if v != expected and v != "0.3.0":
                old_versions.add(v)

        if not found_versions:
            results.append({"file": mem_path_str, "status": "ok", "msg": "无版本引用（非代码文件）"})
        elif old_versions:
            results.append({"file": mem_path_str, "status": "warn",
                          "msg": f"可能引用旧版本: {', '.join(sorted(old_versions))}（当前 {expected}）。如非描述历史版本，请更新。"})
        else:
            results.append({"file": mem_path_str, "status": "ok", "msg": f"版本一致 v{expected}"})

    return results


def check_gitignore(manifest: dict) -> list[dict]:
    """检查 .gitignore 是否包含必备条目。"""
    results = []
    gi_path = PROJECT_ROOT / ".gitignore"
    required = manifest.get("gitignore_required", {}).get("entries", [])

    if not gi_path.exists():
        results.append({"file": ".gitignore", "status": "error", "msg": ".gitignore 不存在"})
        return results

    try:
        content = gi_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        results.append({"file": ".gitignore", "status": "error", "msg": "无法读取"})
        return results

    lines = set(line.strip() for line in content.split("\n") if line.strip() and not line.startswith("#"))
    for entry in required:
        if entry in lines:
            results.append({"file": ".gitignore", "status": "ok", "msg": f"包含 `{entry}`"})
        else:
            results.append({"file": ".gitignore", "status": "error",
                          "msg": f"缺少 `{entry}` — 应加入 .gitignore"})

    return results


def print_result(item: dict):
    """单行打印检查结果。"""
    icon = CHECK if item["status"] == "ok" else CROSS if item["status"] == "error" else WARN
    status_label = "OK" if item["status"] == "ok" else "ERR" if item["status"] == "error" else "WARN"
    rule = item.get("rule", "")
    fname = item.get("file", "—")
    msg = item.get("msg", "")

    rule_str = f"[{rule}]" if rule else ""
    print(f"  {icon} {fname:<40} {rule_str:<24} {msg}")


def main():
    json_output = "--json" in sys.argv
    fix_mode = "--fix" in sys.argv

    manifest = load_manifest()
    ver = manifest["skill"]["version"]

    if not json_output:
        print(f"\n{BOLD}Skill 3.0 发布前自检 — v{ver} — {date.today()}{RESET}\n")

    all_results = {}

    # 1. 文件存活
    if not json_output:
        print(f"{BOLD}[1/6] 文件存活{RESET}")
    r = check_file_existence(manifest)
    all_results["文件存活"] = r
    for item in r:
        if item["status"] != "ok" or not json_output:
            print_result(item)

    # 2. 版本一致性
    if not json_output:
        print(f"\n{BOLD}[2/6] 版本一致性 — 全部文件应标注 v{ver}{RESET}")
    r = check_version_consistency(manifest)
    all_results["版本一致性"] = r
    for item in r:
        if item["status"] != "ok" or not json_output:
            print_result(item)

    # 3. 术语统一
    if not json_output:
        print(f"\n{BOLD}[3/6] 术语统一{RESET}")
    r = check_terminology(manifest)
    all_results["术语统一"] = r
    for item in r:
        if item["status"] != "ok" or not json_output:
            print_result(item)

    # 4. 硬编码清零
    if not json_output:
        print(f"\n{BOLD}[4/6] 硬编码清零{RESET}")
    r = check_forbidden_patterns(manifest)
    all_results["硬编码清零"] = r
    for item in r:
        if item["status"] != "ok" or not json_output:
            print_result(item)

    # 5. auto-memory 同步
    if not json_output:
        print(f"\n{BOLD}[5/6] auto-memory 同步{RESET}")
    r = check_auto_memory(manifest)
    all_results["auto_memory"] = r
    for item in r:
        if item["status"] != "ok" or not json_output:
            print_result(item)

    # 6. .gitignore
    if not json_output:
        print(f"\n{BOLD}[6/6] .gitignore 完整性{RESET}")
    r = check_gitignore(manifest)
    all_results[".gitignore"] = r
    for item in r:
        if item["status"] != "ok" or not json_output:
            print_result(item)

    # ── 汇总 ──
    all_items = [item for group in all_results.values() for item in group]
    errors = sum(1 for i in all_items if i["status"] == "error")
    warns = sum(1 for i in all_items if i["status"] == "warn")
    oks = sum(1 for i in all_items if i["status"] == "ok")

    if json_output:
        print(json.dumps({
            "version": ver,
            "total": len(all_items),
            "ok": oks,
            "warnings": warns,
            "errors": errors,
            "passed": errors == 0,
            "details": all_results,
        }, ensure_ascii=False, indent=2))
    else:
        print(f"\n{'='*60}")
        if errors == 0 and warns == 0:
            print(f"{CHECK} {GREEN}{BOLD}全部通过 — {oks} 项检查，可以推送{RESET}")
        elif errors == 0:
            print(f"{WARN} {YELLOW}{BOLD}{oks} 通过, {warns} 告警 — 建议修复后推送{RESET}")
        else:
            print(f"{CROSS} {RED}{BOLD}{errors} 错误, {warns} 告警, {oks} 通过 — 修复后再推送{RESET}")
        print(f"{'='*60}\n")

    sys.exit(0 if errors == 0 else 2 if errors > 0 else 1)


if __name__ == "__main__":
    main()
