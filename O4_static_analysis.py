#!/usr/bin/env python3
"""
Static diff-level comparison for developer, Codex, and Claude patches.

Expected folder layout:

developer_fixes/
  PR_{pr_id}.patch

generated_29Jun2026/
  claude/
    PR_{pr_id}/
      something.patch
      some_folder/
  codex/
    PR_{pr_id}/
      something.patch
      some_folder/

This script compares patches from diffs only. It computes:
- patch size/succinctness metrics
- changed file categories
- accessibility-related token changes
- agent-vs-developer overlap/localization metrics
- over-modification heuristic flags

It does NOT run Semgrep/lizard or apply patches to code.
"""
from __future__ import annotations

import argparse
import csv
import re
import os
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any

AGENTS = ["claude", "codex"]
SOURCES = ["developer"] + AGENTS


SOURCE_EXTENSIONS = {
    ".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".kt", ".kts", ".swift",
    ".m", ".mm", ".c", ".cc", ".cpp", ".h", ".hpp", ".cs", ".rb", ".go",
    ".rs", ".php", ".scala", ".vue", ".svelte", ".css", ".scss", ".sass",
    ".less", ".html", ".htm", ".xml", ".xaml", ".dart"
}

DOC_EXTENSIONS = {
    ".md", ".rst", ".txt", ".adoc"
}

LOCKFILE_NAMES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "npm-shrinkwrap.json",
    "poetry.lock", "pipfile.lock", "cargo.lock", "gradle.lockfile",
    "composer.lock", "gemfile.lock"
}

CONFIG_NAMES = {
    "package.json", "tsconfig.json", "jsconfig.json", "babel.config.js",
    "babel.config.json", "webpack.config.js", "vite.config.js", "rollup.config.js",
    "pom.xml", "build.gradle", "settings.gradle", "gradle.properties",
    "requirements.txt", "pyproject.toml", "setup.py", "setup.cfg",
    "tox.ini", "dockerfile", "docker-compose.yml", "docker-compose.yaml",
    ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".prettierrc",
    ".stylelintrc", "gemfile", "makefile"
}

TEST_PATTERNS = [
    r"(^|/)test(s)?(/|$)",
    r"(^|/)__tests__(/|$)",
    r"(^|/)spec(s)?(/|$)",
    r"(^|/)e2e(/|$)",
    r"(^|/)cypress(/|$)",
    r"(^|/)jest(/|$)",
    r"(^|/)testing(/|$)",
    r"(\.|_|-)(test|spec)\.[a-z0-9]+$",
]

GENERATED_PATTERNS = [
    r"(^|/)dist(/|$)",
    r"(^|/)build(/|$)",
    r"(^|/)generated(/|$)",
    r"(^|/)vendor(/|$)",
    r"(^|/)coverage(/|$)",
    r"\.min\.",
    r"\.bundle\.",
    r"\.snap$",
    r"snapshot",
]

A11Y_PATTERNS = {
    "aria": r"\baria-[a-zA-Z0-9_-]+\b",
    "role": r"\brole\s*=",
    "tabindex": r"\btabindex\b|\btabIndex\b",
    "alt_text": r"\balt\s*=|\baltText\b",
    "labeling": r"\baria-label\b|\baria-labelledby\b|\blabel\b|\btitle\s*=",
    "focus_keyboard": r"\bfocus\b|\btabIndex\b|\bkeydown\b|\bkeyup\b|\bkeypress\b|\bonKeyDown\b|\bonKeyUp\b",
    "screen_reader_text": r"\bscreenreader\b|\bscreen-reader\b|\bsr-only\b|\bvisually-hidden\b|\bassistive-text\b|\ba11y\b|\baccessibility\b",
    "semantic_html": r"<\s*(button|a|input|label|select|textarea|h[1-6]|main|nav|header|footer|section|article|details|summary)\b",
    "android_a11y": r"\bcontentDescription\b|\bimportantForAccessibility\b|\btalkback\b|\bAccessibilityNodeInfo\b",
    "ios_a11y": r"\baccessibilityLabel\b|\baccessibilityIdentifier\b|\baccessibilityTraits\b|\bVoiceOver\b",
}

@dataclass
class FileDiff:
    path: Optional[str] = None
    old_path: Optional[str] = None
    new_path: Optional[str] = None
    added: int = 0
    deleted: int = 0
    hunks: int = 0
    binary: bool = False
    is_new_file: bool = False
    is_deleted_file: bool = False
    is_rename: bool = False


@dataclass
class ParsedPatch:
    patch_path: str
    patch_found: bool
    parse_error: str = ""
    files: List[FileDiff] = field(default_factory=list)
    added_lines: List[str] = field(default_factory=list)
    deleted_lines: List[str] = field(default_factory=list)


def normalize_patch_path(raw: str) -> Optional[str]:
    """
    Normalize paths from diff headers:
    a/src/file.js -> src/file.js
    b/src/file.js -> src/file.js
    /dev/null -> None
    """
    if raw is None:
        return None

    raw = raw.strip()

    if raw.startswith('"') and raw.endswith('"'):
        raw = raw[1:-1]

    # Remove timestamps after tab, common in unified diffs.
    raw = raw.split("\t")[0].strip()

    if raw == "/dev/null":
        return None

    if raw.startswith("a/") or raw.startswith("b/"):
        raw = raw[2:]

    return raw.strip() or None


def extract_header_path(line_after_marker: str) -> Optional[str]:
    """
    Extract path from lines like:
    --- a/file.js
    +++ b/file.js
    """
    value = line_after_marker.strip()
    if not value:
        return None

    # Good enough for normal git patches.
    # Handles timestamps if separated by tab.
    value = value.split("\t")[0].strip()

    return normalize_patch_path(value)


def parse_diff_git_line(line: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Parse:
    diff --git a/foo b/foo
    """
    parts = line.strip().split()
    if len(parts) >= 4:
        return normalize_patch_path(parts[2]), normalize_patch_path(parts[3])
    return None, None


def finalize_file(current: Optional[FileDiff], files: List[FileDiff]) -> None:
    if current is None:
        return

    if current.new_path:
        current.path = current.new_path
    elif current.old_path:
        current.path = current.old_path

    if current.path:
        files.append(current)


def parse_patch_file(path: Optional[Path]) -> ParsedPatch:
    if path is None or not path.exists():
        return ParsedPatch(
            patch_path="" if path is None else str(path),
            patch_found=False,
        )

    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return ParsedPatch(
            patch_path=str(path),
            patch_found=True,
            parse_error=f"Could not read patch: {e}",
        )

    files: List[FileDiff] = []
    added_lines: List[str] = []
    deleted_lines: List[str] = []
    current: Optional[FileDiff] = None

    for line in text.splitlines():
        if line.startswith("```"):
            continue

        if line.startswith("diff --git "):
            finalize_file(current, files)
            old_path, new_path = parse_diff_git_line(line)
            current = FileDiff(
                path=new_path or old_path,
                old_path=old_path,
                new_path=new_path,
            )
            continue

        if line.startswith("--- "):
            if current is None:
                current = FileDiff()
            current.old_path = extract_header_path(line[4:])
            continue

        if line.startswith("+++ "):
            if current is None:
                current = FileDiff()
            current.new_path = extract_header_path(line[4:])
            current.path = current.new_path or current.old_path
            continue

        if current is None:
            continue

        if line.startswith("new file mode"):
            current.is_new_file = True
            continue

        if line.startswith("deleted file mode"):
            current.is_deleted_file = True
            continue

        if line.startswith("rename from "):
            current.is_rename = True
            current.old_path = normalize_patch_path(line.replace("rename from ", "", 1))
            continue

        if line.startswith("rename to "):
            current.is_rename = True
            current.new_path = normalize_patch_path(line.replace("rename to ", "", 1))
            current.path = current.new_path
            continue

        if line.startswith("Binary files ") or line.startswith("GIT binary patch"):
            current.binary = True
            continue

        if line.startswith("@@"):
            current.hunks += 1
            continue

        if line.startswith("+") and not line.startswith("+++"):
            current.added += 1
            added_lines.append(line[1:])
            continue

        if line.startswith("-") and not line.startswith("---"):
            current.deleted += 1
            deleted_lines.append(line[1:])
            continue

    finalize_file(current, files)

    return ParsedPatch(
        patch_path=str(path),
        patch_found=True,
        files=files,
        added_lines=added_lines,
        deleted_lines=deleted_lines,
    )


def is_test_file(path: str) -> bool:
    p = path.lower()
    return any(re.search(pattern, p) for pattern in TEST_PATTERNS)


def is_generated_file(path: str) -> bool:
    p = path.lower()
    return any(re.search(pattern, p) for pattern in GENERATED_PATTERNS)


def is_lockfile(path: str) -> bool:
    name = Path(path).name.lower()
    return name in LOCKFILE_NAMES


def is_config_file(path: str) -> bool:
    name = Path(path).name.lower()
    if name in CONFIG_NAMES:
        return True
    if name in LOCKFILE_NAMES:
        return True
    if path.lower().endswith((".yml", ".yaml")) and (
        ".github/" in path.lower() or "ci" in path.lower()
    ):
        return True
    return False


def is_doc_file(path: str) -> bool:
    return Path(path).suffix.lower() in DOC_EXTENSIONS or "/docs/" in path.lower()


def is_source_file(path: str) -> bool:
    return Path(path).suffix.lower() in SOURCE_EXTENSIONS


def parent_dir(path: str) -> str:
    parent = str(Path(path).parent).replace("\\", "/")
    return "" if parent == "." else parent


def top_level_dir(path: str) -> str:
    return path.split("/", 1)[0] if "/" in path else ""


def classify_file(path: str) -> Dict[str, bool]:
    return {
        "is_source": is_source_file(path),
        "is_test": is_test_file(path),
        "is_config": is_config_file(path),
        "is_lockfile": is_lockfile(path),
        "is_generated": is_generated_file(path),
        "is_doc": is_doc_file(path),
    }


def count_pattern(lines: List[str], pattern: str) -> int:
    rx = re.compile(pattern, re.IGNORECASE)
    return sum(len(rx.findall(line)) for line in lines)


def count_a11y_mentions(lines: List[str], prefix: str) -> Dict[str, int]:
    out = {}
    for name, pattern in A11Y_PATTERNS.items():
        out[f"{prefix}_{name}"] = count_pattern(lines, pattern)
    return out


def patch_to_metrics(pr_id: str, source: str, parsed: ParsedPatch) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "pr_id": pr_id,
        "source": source,
        "patch_found": parsed.patch_found,
        "patch_path": parsed.patch_path,
        "parse_error": parsed.parse_error,
    }

    if not parsed.patch_found or parsed.parse_error:
        return row

    files = [f for f in parsed.files if f.path]
    paths = [f.path for f in files if f.path]
    path_set = set(paths)

    added = sum(f.added for f in files)
    deleted = sum(f.deleted for f in files)
    hunks = sum(f.hunks for f in files)

    classifications = {p: classify_file(p) for p in path_set}

    source_files = [
        p for p, c in classifications.items()
        if c["is_source"] and not c["is_test"]
    ]

    test_files = [p for p, c in classifications.items() if c["is_test"]]
    config_files = [p for p, c in classifications.items() if c["is_config"]]
    lockfiles = [p for p, c in classifications.items() if c["is_lockfile"]]
    generated_files = [p for p, c in classifications.items() if c["is_generated"]]
    doc_files = [p for p, c in classifications.items() if c["is_doc"]]

    dirs = {parent_dir(p) for p in path_set}
    top_dirs = {top_level_dir(p) for p in path_set if top_level_dir(p)}

    row.update({
        "files_changed": len(path_set),
        "source_files_changed": len(source_files),
        "test_files_changed": len(test_files),
        "config_files_changed": len(config_files),
        "lockfiles_changed": len(lockfiles),
        "generated_files_changed": len(generated_files),
        "doc_files_changed": len(doc_files),
        "dirs_touched": len(dirs),
        "top_level_dirs_touched": len(top_dirs),
        "loc_added": added,
        "loc_deleted": deleted,
        "loc_churn": added + deleted,
        "num_hunks": hunks,
        "binary_files_changed": sum(1 for f in files if f.binary),
        "new_files": sum(1 for f in files if f.is_new_file),
        "deleted_files": sum(1 for f in files if f.is_deleted_file),
        "renamed_files": sum(1 for f in files if f.is_rename),
        "changed_files_list": ";".join(sorted(path_set)),
        "changed_dirs_list": ";".join(sorted(dirs)),
        "patch_touches_only_tests": bool(path_set) and len(test_files) == len(path_set),
        "patch_touches_config": len(config_files) > 0,
        "patch_touches_lockfile": len(lockfiles) > 0,
        "patch_touches_generated": len(generated_files) > 0,
    })

    row.update(count_a11y_mentions(parsed.added_lines, "added"))
    row.update(count_a11y_mentions(parsed.deleted_lines, "deleted"))

    row["added_any_a11y_signal"] = any(
        row.get(f"added_{name}", 0) > 0 for name in A11Y_PATTERNS
    )
    row["deleted_any_a11y_signal"] = any(
        row.get(f"deleted_{name}", 0) > 0 for name in A11Y_PATTERNS
    )

    return row


def file_rows_for_patch(pr_id: str, source: str, parsed: ParsedPatch) -> List[Dict[str, Any]]:
    rows = []
    if not parsed.patch_found or parsed.parse_error:
        return rows

    for f in parsed.files:
        if not f.path:
            continue

        c = classify_file(f.path)
        rows.append({
            "pr_id": pr_id,
            "source": source,
            "path": f.path,
            "old_path": f.old_path or "",
            "new_path": f.new_path or "",
            "added": f.added,
            "deleted": f.deleted,
            "churn": f.added + f.deleted,
            "hunks": f.hunks,
            "binary": f.binary,
            "is_new_file": f.is_new_file,
            "is_deleted_file": f.is_deleted_file,
            "is_rename": f.is_rename,
            **c,
            "directory": parent_dir(f.path),
            "top_level_dir": top_level_dir(f.path),
        })

    return rows


def parse_pr_id_from_patch_name(path: Path) -> Optional[str]:
    m = re.match(r"PR_(.+?)\.patch$", path.name)
    return m.group(1) if m else None


def discover_developer_patches(developer_dir: Path) -> Dict[str, Path]:
    out = {}
    for patch in developer_dir.glob("PR_*.patch"):
        pr_id = parse_pr_id_from_patch_name(patch)
        if pr_id:
            out[pr_id] = patch
    return out


def choose_patch_file(pr_dir: Path) -> Optional[Path]:
    """
    Prefer direct .patch file inside PR_{id}/.
    If none exists, recursively search.
    If multiple exist, choose the largest file, assuming it is the full patch.
    """
    if not pr_dir.exists() or not pr_dir.is_dir():
        return None

    direct = list(pr_dir.glob("*.patch"))
    candidates = direct if direct else list(pr_dir.rglob("*.patch"))

    if not candidates:
        return None

    candidates = sorted(candidates, key=lambda p: p.stat().st_size if p.exists() else 0, reverse=True)
    return candidates[0]


def discover_agent_patches(generated_dir: Path, agent: str) -> Dict[str, Path]:
    agent_dir = generated_dir / agent
    out = {}

    if not agent_dir.exists():
        return out

    for pr_dir in agent_dir.glob("PR_*"):
        if not pr_dir.is_dir():
            continue

        pr_id = pr_dir.name.replace("PR_", "", 1)
        patch = choose_patch_file(pr_dir)
        if patch:
            out[pr_id] = patch

    return out


def get_file_set(metrics_row: Dict[str, Any]) -> Set[str]:
    value = metrics_row.get("changed_files_list", "")
    if not value:
        return set()
    return {x for x in value.split(";") if x}


def safe_div(numer: float, denom: float) -> Optional[float]:
    if denom == 0:
        return None
    return numer / denom


def round_or_blank(value: Optional[float], digits: int = 3) -> Any:
    if value is None:
        return ""
    return round(value, digits)


def compare_agent_to_developer(
    pr_id: str,
    agent: str,
    dev_row: Dict[str, Any],
    agent_row: Dict[str, Any],
) -> Dict[str, Any]:
    dev_found = bool(dev_row.get("patch_found"))
    agent_found = bool(agent_row.get("patch_found"))

    row: Dict[str, Any] = {
        "pr_id": pr_id,
        "agent": agent,
        "developer_patch_found": dev_found,
        "agent_patch_found": agent_found,
    }

    if not dev_found or not agent_found:
        return row

    dev_files = get_file_set(dev_row)
    agent_files = get_file_set(agent_row)

    shared_files = dev_files & agent_files
    union_files = dev_files | agent_files

    extra_files = agent_files - dev_files
    missing_dev_files = dev_files - agent_files

    dev_dirs = {parent_dir(p) for p in dev_files}
    agent_dirs = {parent_dir(p) for p in agent_files}

    dev_top_dirs = {top_level_dir(p) for p in dev_files if top_level_dir(p)}
    agent_top_dirs = {top_level_dir(p) for p in agent_files if top_level_dir(p)}

    file_overlap = safe_div(len(shared_files), len(union_files))
    extra_file_ratio = safe_div(len(extra_files), len(agent_files))
    missing_dev_file_ratio = safe_div(len(missing_dev_files), len(dev_files))

    dev_churn = int(dev_row.get("loc_churn") or 0)
    agent_churn = int(agent_row.get("loc_churn") or 0)
    churn_ratio = safe_div(agent_churn, dev_churn)

    dev_hunks = int(dev_row.get("num_hunks") or 0)
    agent_hunks = int(agent_row.get("num_hunks") or 0)
    hunks_ratio = safe_div(agent_hunks, dev_hunks)

    agent_changed_config_not_dev = (
        bool(agent_row.get("patch_touches_config")) and
        not bool(dev_row.get("patch_touches_config"))
    )

    agent_changed_lockfile_not_dev = (
        bool(agent_row.get("patch_touches_lockfile")) and
        not bool(dev_row.get("patch_touches_lockfile"))
    )

    agent_changed_generated_not_dev = (
        bool(agent_row.get("patch_touches_generated")) and
        not bool(dev_row.get("patch_touches_generated"))
    )

    no_file_overlap_flag = len(shared_files) == 0 and len(dev_files) > 0 and len(agent_files) > 0

    broad_extra_file_flag = (
        len(extra_files) >= 2 and
        (extra_file_ratio is not None and extra_file_ratio >= 0.50)
    )

    large_churn_flag = (
        churn_ratio is not None and
        churn_ratio >= 3.0 and
        agent_churn - dev_churn >= 20
    )

    overmodified_flag = (
        broad_extra_file_flag or
        large_churn_flag or
        agent_changed_config_not_dev or
        agent_changed_lockfile_not_dev or
        agent_changed_generated_not_dev
    )

    row.update({
        "developer_files_changed": len(dev_files),
        "agent_files_changed": len(agent_files),
        "shared_files_count": len(shared_files),
        "extra_files_count": len(extra_files),
        "missing_developer_files_count": len(missing_dev_files),
        "file_overlap_jaccard": round_or_blank(file_overlap),
        "same_file_as_developer": len(shared_files) > 0,
        "same_directory_as_developer": len(dev_dirs & agent_dirs) > 0,
        "same_top_level_dir_as_developer": len(dev_top_dirs & agent_top_dirs) > 0,
        "extra_file_ratio": round_or_blank(extra_file_ratio),
        "missing_developer_file_ratio": round_or_blank(missing_dev_file_ratio),
        "developer_churn": dev_churn,
        "agent_churn": agent_churn,
        "churn_ratio_vs_developer": round_or_blank(churn_ratio),
        "developer_hunks": dev_hunks,
        "agent_hunks": agent_hunks,
        "hunks_ratio_vs_developer": round_or_blank(hunks_ratio),
        "agent_added_any_a11y_signal": bool(agent_row.get("added_any_a11y_signal")),
        "developer_added_any_a11y_signal": bool(dev_row.get("added_any_a11y_signal")),
        "agent_changed_config_not_developer": agent_changed_config_not_dev,
        "agent_changed_lockfile_not_developer": agent_changed_lockfile_not_dev,
        "agent_changed_generated_not_developer": agent_changed_generated_not_dev,
        "no_file_overlap_flag": no_file_overlap_flag,
        "broad_extra_file_flag": broad_extra_file_flag,
        "large_churn_flag": large_churn_flag,
        "overmodified_flag": overmodified_flag,
        "shared_files": ";".join(sorted(shared_files)),
        "extra_files": ";".join(sorted(extra_files)),
        "missing_developer_files": ";".join(sorted(missing_dev_files)),
    })

    return row


def write_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    if not rows:
        path.write_text("", encoding="utf-8")
        return

    fieldnames: List[str] = []
    seen = set()

    for row in rows:
        for key in row.keys():
            if key not in seen:
                seen.add(key)
                fieldnames.append(key)

    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def numeric_values(rows: List[Dict[str, Any]], key: str) -> List[float]:
    vals = []
    for row in rows:
        value = row.get(key)
        if value in ("", None):
            continue
        try:
            vals.append(float(value))
        except ValueError:
            pass
    return vals


def median_value(rows: List[Dict[str, Any]], key: str) -> Any:
    vals = numeric_values(rows, key)
    if not vals:
        return ""
    return round(statistics.median(vals), 3)


def mean_value(rows: List[Dict[str, Any]], key: str) -> Any:
    vals = numeric_values(rows, key)
    if not vals:
        return ""
    return round(statistics.mean(vals), 3)


def bool_rate(rows: List[Dict[str, Any]], key: str) -> Any:
    valid = [row for row in rows if key in row and row.get(key) not in ("", None)]
    if not valid:
        return ""
    return round(sum(1 for row in valid if str(row.get(key)).lower() == "true") / len(valid), 3)


def summarize_by_source(patch_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []

    for source in SOURCES:
        rows = [
            r for r in patch_rows
            if r.get("source") == source and str(r.get("patch_found")).lower() == "true"
        ]

        out.append({
            "source": source,
            "patches_found": len(rows),
            "median_files_changed": median_value(rows, "files_changed"),
            "median_source_files_changed": median_value(rows, "source_files_changed"),
            "median_test_files_changed": median_value(rows, "test_files_changed"),
            "median_loc_added": median_value(rows, "loc_added"),
            "median_loc_deleted": median_value(rows, "loc_deleted"),
            "median_loc_churn": median_value(rows, "loc_churn"),
            "median_num_hunks": median_value(rows, "num_hunks"),
            "config_touch_rate": bool_rate(rows, "patch_touches_config"),
            "lockfile_touch_rate": bool_rate(rows, "patch_touches_lockfile"),
            "generated_touch_rate": bool_rate(rows, "patch_touches_generated"),
            "added_a11y_signal_rate": bool_rate(rows, "added_any_a11y_signal"),
        })

    return out


def summarize_agent_comparisons(pairwise_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []

    for agent in AGENTS:
        rows = [
            r for r in pairwise_rows
            if r.get("agent") == agent
            and str(r.get("developer_patch_found")).lower() == "true"
            and str(r.get("agent_patch_found")).lower() == "true"
        ]

        out.append({
            "source": f"{agent}_vs_developer",
            "pairs_available": len(rows),
            "median_file_overlap_jaccard": median_value(rows, "file_overlap_jaccard"),
            "median_extra_files_count": median_value(rows, "extra_files_count"),
            "median_missing_developer_files_count": median_value(rows, "missing_developer_files_count"),
            "median_churn_ratio_vs_developer": median_value(rows, "churn_ratio_vs_developer"),
            "same_file_rate": bool_rate(rows, "same_file_as_developer"),
            "same_directory_rate": bool_rate(rows, "same_directory_as_developer"),
            "no_file_overlap_rate": bool_rate(rows, "no_file_overlap_flag"),
            "overmodified_rate": bool_rate(rows, "overmodified_flag"),
        })

    return out


def markdown_table(rows: List[Dict[str, Any]], columns: List[str]) -> str:
    if not rows:
        return ""

    header = "| " + " | ".join(columns) + " |"
    sep = "| " + " | ".join(["---"] * len(columns)) + " |"
    body = []

    for row in rows:
        body.append("| " + " | ".join(str(row.get(c, "")) for c in columns) + " |")

    return "\n".join([header, sep] + body)


def write_markdown_report(
    out_path: Path,
    pr_ids: List[str],
    patch_rows: List[Dict[str, Any]],
    source_summary: List[Dict[str, Any]],
    pairwise_summary: List[Dict[str, Any]],
    pairwise_rows: List[Dict[str, Any]],
) -> None:
    missing_lines = []

    for source in SOURCES:
        total = len(pr_ids)
        found = sum(
            1 for r in patch_rows
            if r.get("source") == source and str(r.get("patch_found")).lower() == "true"
        )
        missing_lines.append(f"- {source}: {found}/{total} patches found")

    suspicious_rows = [
        r for r in pairwise_rows
        if str(r.get("overmodified_flag")).lower() == "true"
        or str(r.get("no_file_overlap_flag")).lower() == "true"
    ]

    suspicious_preview = suspicious_rows[:25]

    md = []
    md.append("# Static Diff Analysis Report\n")
    md.append(f"Total PRs discovered: **{len(pr_ids)}**\n")
    md.append("## Patch Availability\n")
    md.append("\n".join(missing_lines))
    md.append("\n\n## Summary by Patch Source\n")
    md.append(markdown_table(source_summary, [
        "source",
        "patches_found",
        "median_files_changed",
        "median_source_files_changed",
        "median_loc_churn",
        "median_num_hunks",
        "config_touch_rate",
        "lockfile_touch_rate",
        "generated_touch_rate",
        "added_a11y_signal_rate",
    ]))

    md.append("\n\n## Agent-vs-Developer Summary\n")
    md.append(markdown_table(pairwise_summary, [
        "source",
        "pairs_available",
        "median_file_overlap_jaccard",
        "median_extra_files_count",
        "median_missing_developer_files_count",
        "median_churn_ratio_vs_developer",
        "same_file_rate",
        "same_directory_rate",
        "no_file_overlap_rate",
        "overmodified_rate",
    ]))

    md.append("\n\n## Flagged Agent Patches\n")
    md.append(
        "These are patches flagged by a simple heuristic: no overlap with the developer patch, "
        "large extra-file spread, large churn ratio, or agent-only config/lock/generated-file changes.\n"
    )

    if suspicious_preview:
        md.append(markdown_table(suspicious_preview, [
            "pr_id",
            "agent",
            "file_overlap_jaccard",
            "extra_files_count",
            "churn_ratio_vs_developer",
            "no_file_overlap_flag",
            "overmodified_flag",
        ]))
    else:
        md.append("No suspicious agent patches were flagged by the heuristic.")

    md.append("\n\n## Notes\n")
    md.append(
        "- These metrics are computed from patches only.\n"
        "- `loc_churn` means added lines plus deleted lines.\n"
        "- `file_overlap_jaccard` is `|agent_files ∩ developer_files| / |agent_files ∪ developer_files|`.\n"
        "- `overmodified_flag` is a heuristic, not a correctness judgment.\n"
        "- Static warning and complexity deltas require applying patches to code and running analyzers separately.\n"
    )

    out_path.write_text("\n".join(md), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--developer-dir", default="developer_fixes", help="Folder containing PR_{pr_id}.patch developer patches")
    parser.add_argument("--generated-dir", default="generated_29Jun2026", help="Folder containing claude/ and codex/ patch outputs")
    parser.add_argument("--out-dir", default="static_diff_report", help="Output report folder")
    args = parser.parse_args()

    developer_dir = Path(args.developer_dir)
    #generated_dir = Path(args.generated_dir)
    generated_dir = Path([file for file in os.listdir() if "generated_" in file][0])
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    developer_patches = discover_developer_patches(developer_dir)
    agent_patches = {
        agent: discover_agent_patches(generated_dir, agent)
        for agent in AGENTS
    }

    pr_ids: Set[str] = set(developer_patches.keys())
    for agent in AGENTS:
        pr_ids.update(agent_patches[agent].keys())

    pr_ids_sorted = sorted(pr_ids, key=lambda x: int(x) if x.isdigit() else x)

    patch_rows: List[Dict[str, Any]] = []
    file_rows: List[Dict[str, Any]] = []
    parsed_by_pr_source: Dict[Tuple[str, str], ParsedPatch] = {}
    metrics_by_pr_source: Dict[Tuple[str, str], Dict[str, Any]] = {}

    for pr_id in pr_ids_sorted:
        source_to_path: Dict[str, Optional[Path]] = {
            "developer": developer_patches.get(pr_id),
            "claude": agent_patches["claude"].get(pr_id),
            "codex": agent_patches["codex"].get(pr_id),
        }

        for source, patch_path in source_to_path.items():
            parsed = parse_patch_file(patch_path)
            parsed_by_pr_source[(pr_id, source)] = parsed

            metrics = patch_to_metrics(pr_id, source, parsed)
            metrics_by_pr_source[(pr_id, source)] = metrics
            patch_rows.append(metrics)

            file_rows.extend(file_rows_for_patch(pr_id, source, parsed))

    pairwise_rows: List[Dict[str, Any]] = []

    for pr_id in pr_ids_sorted:
        dev_row = metrics_by_pr_source.get((pr_id, "developer"), {})
        for agent in AGENTS:
            agent_row = metrics_by_pr_source.get((pr_id, agent), {})
            pairwise_rows.append(compare_agent_to_developer(
                pr_id=pr_id,
                agent=agent,
                dev_row=dev_row,
                agent_row=agent_row,
            ))

    source_summary = summarize_by_source(patch_rows)
    pairwise_summary = summarize_agent_comparisons(pairwise_rows)

    write_csv(out_dir / "patch_metrics.csv", patch_rows)
    write_csv(out_dir / "changed_files.csv", file_rows)
    write_csv(out_dir / "agent_vs_developer.csv", pairwise_rows)
    write_csv(out_dir / "summary_by_source.csv", source_summary + pairwise_summary)

    write_markdown_report(
        out_path=out_dir / "static_diff_report.md",
        pr_ids=pr_ids_sorted,
        patch_rows=patch_rows,
        source_summary=source_summary,
        pairwise_summary=pairwise_summary,
        pairwise_rows=pairwise_rows,
    )

    print(f"Done. Wrote reports to: {out_dir.resolve()}")
    print("Main files:")
    print(f"  - {out_dir / 'patch_metrics.csv'}")
    print(f"  - {out_dir / 'changed_files.csv'}")
    print(f"  - {out_dir / 'agent_vs_developer.csv'}")
    print(f"  - {out_dir / 'summary_by_source.csv'}")
    print(f"  - {out_dir / 'static_diff_report.md'}")


if __name__ == "__main__":
    main()