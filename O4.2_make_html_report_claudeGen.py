#!/usr/bin/env python3

"""
Create an HTML report for the static diff chart outputs.

This version adds:
- clearer explanations before each group of numbers
- explicit denominators for bounded metrics, such as 0.38 / 1.00
- count-based descriptions, such as 9 / 25 patches
- explanations of abbreviations such as lines of code and pull request
- clearer descriptions of how each metric is calculated
- a polished dark research-tool visual design
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path
from typing import Any, Dict

import pandas as pd


CHARTS = [
    {
        "file": "01_median_loc_churn_by_source.png",
        "title": "Median lines of code churn by patch source",
        "metric": (
            "Lines of code churn means the number of added lines plus the number of deleted lines. "
            "For example, a patch with 8 added lines and 4 deleted lines has 12 lines of code churn."
        ),
        "question": "Which repair source tends to produce the smallest or largest patches?",
        "why_numbers_matter": (
            "Smaller patches are usually easier to review and integrate. "
            "For the same accessibility issue, a much larger generated patch may indicate that the agent "
            "changed more code than necessary."
        ),
        "how_to_read": (
            "Each bar shows the median amount of code changed by developer, Claude, and Codex patches. "
            "A lower bar means the patch source usually made smaller, more succinct changes."
        ),
        "look_for": (
            "If Claude or Codex has a much higher median lines of code churn than developers, that suggests "
            "the agent tends to produce more verbose or broader patches than human developers."
        ),
        "paper_use": "Use this chart to support the patch succinctness comparison.",
    },
    {
        "file": "02_loc_churn_distribution_by_source.png",
        "title": "Lines of code churn distribution by patch source",
        "metric": (
            "This chart shows the distribution of patch sizes. Patch size is measured as added lines plus deleted lines."
        ),
        "question": "Are larger patches common, or are they caused by a few extreme cases?",
        "why_numbers_matter": (
            "The median alone can hide unusual agent behavior. "
            "A few very large generated patches may create extra review burden even when most generated patches are small."
        ),
        "how_to_read": (
            "Each boxplot shows the spread of lines of code churn values for one patch source. "
            "The center line is the median; the box shows the middle range; points outside the box are outliers."
        ),
        "look_for": (
            "If an agent has many high outliers, it may occasionally produce very large patches. "
            "If the whole box is higher than the developer box, the agent generally produces larger patches."
        ),
        "paper_use": (
            "Use this chart to avoid relying only on averages. It shows whether patch-size differences are systematic."
        ),
    },
    {
        "file": "03_files_changed_distribution_by_source.png",
        "title": "Files changed distribution by patch source",
        "metric": "This chart counts how many files were changed by each patch.",
        "question": "Do agents spread their fixes across more files than developers?",
        "why_numbers_matter": (
            "A fix that touches many files can be harder to review and may indicate "
            "that the agent did not localize the issue narrowly."
        ),
        "how_to_read": (
            "Each boxplot shows how many files each patch source changed. "
            "Lower values mean the fix was more localized at the file level."
        ),
        "look_for": (
            "If Claude or Codex changes more files than developers, that may indicate broader localization "
            "or possible over-modification."
        ),
        "paper_use": "Use this chart for the patch locality and over-modification discussion.",
    },
    {
        "file": "04_file_overlap_distribution_by_agent.png",
        "title": "File overlap with developer patch by agent",
        "metric": (
            "File overlap is calculated with the Jaccard score: "
            "number of shared files divided by the total number of unique files changed by either the agent or developer. "
            "The score ranges from 0.00 / 1.00 to 1.00 / 1.00."
        ),
        "question": "Did the agent modify the same files as the developer?",
        "why_numbers_matter": (
            "File overlap is a static proxy for localization similarity. "
            "If an agent fixes the same issue but touches completely different files, that patch deserves closer inspection."
        ),
        "how_to_read": (
            "A score of 1.00 / 1.00 means the agent and developer touched exactly the same set of files. "
            "A score of 0.00 / 1.00 means they touched completely different files."
        ),
        "look_for": (
            "Higher overlap suggests better static localization similarity. Lower overlap does not automatically "
            "mean the patch is wrong, but it is a strong signal to inspect the patch manually."
        ),
        "paper_use": "Use this chart as the main localization-similarity result.",
    },
    {
        "file": "05_churn_ratio_distribution_by_agent.png",
        "title": "Agent-to-developer lines of code churn ratio",
        "metric": (
            "This ratio is calculated as agent lines of code churn divided by developer lines of code churn "
            "for the same pull request."
        ),
        "question": "How much larger or smaller are agent patches compared to the developer patch for the same pull request?",
        "why_numbers_matter": (
            "This is a paired comparison. Instead of comparing all patches globally, "
            "it asks whether the agent changed more or less code than the developer for the exact same issue."
        ),
        "how_to_read": (
            "The dashed line at 1.00 means the agent changed the same amount of code as the developer. "
            "A value of 2.00 means the agent changed twice as many lines. "
            "A value of 0.50 means the agent changed half as many lines."
        ),
        "look_for": (
            "Ratios much larger than 1.00 suggest the agent produced a broader patch than the developer. "
            "Very high outliers are good candidates for qualitative inspection."
        ),
        "paper_use": "Use this chart to compare patch succinctness in a paired way, pull request by pull request.",
    },
    {
        "file": "06_same_file_and_directory_rates.png",
        "title": "Same-file and same-directory rates",
        "metric": (
            "Same-file rate is the share of agent patches that touched at least one file also touched by the developer. "
            "Same-directory rate is the share of agent patches that touched at least one directory also touched by the developer."
        ),
        "question": "How often did agents work in the same code region as the developer?",
        "why_numbers_matter": (
            "They separate exact file-level localization from broader module-level localization. "
            "An agent may miss the exact developer-touched file but still work in a nearby directory."
        ),
        "how_to_read": (
            "Same-file rate is stricter. Same-directory rate is looser. "
            "A high same-directory rate but low same-file rate means the agent often found the right module but not the exact file."
        ),
        "look_for": (
            "If same-file rate is low, the agent may frequently localize the fix differently from developers. "
            "If same-directory rate is high, the agent may still be working in a related area."
        ),
        "paper_use": "Use this chart to discuss localization at two granularities.",
    },
    {
        "file": "07_overmodified_rate_by_agent.png",
        "title": "Over-modification flag rate by agent",
        "metric": (
            "Over-modification rate is the share of agent patches that triggered at least one broad-change heuristic. "
            "Examples include many extra files, much larger churn than the developer patch, or agent-only config, lockfile, "
            "or generated-file changes."
        ),
        "question": "How often did each agent produce patches that look broader than necessary?",
        "why_numbers_matter": (
            "Over-modification can increase review burden even if the patch builds. "
            "This metric helps identify patches that may require extra human inspection."
        ),
        "how_to_read": (
            "A higher percentage means more patches were flagged for possible over-modification. "
            "This is not a correctness judgment by itself."
        ),
        "look_for": (
            "Higher rates mean more patches deserve manual inspection for unnecessary changes. "
            "This is an inspection signal, not proof that the patch is wrong."
        ),
        "paper_use": "Use this chart to support claims about integration burden or patch review burden.",
    },
    {
        "file": "08_accessibility_signal_rate_by_source.png",
        "title": "Accessibility-signal rate by patch source",
        "metric": (
            "Accessibility-signal rate is the share of patches that added accessibility-related code tokens or application programming interface references. "
            "Examples include aria-label, role, tabindex, alternative text, focus handlers, contentDescription, accessibilityLabel, and visually-hidden text."
        ),
        "question": "Do patches explicitly modify accessibility-related code?",
        "why_numbers_matter": (
            "They help characterize the repair strategy. "
            "Some fixes explicitly add accessibility attributes, while others fix accessibility through structure, styling, or behavior."
        ),
        "how_to_read": (
            "A higher value means more patches added explicit accessibility-related terms. "
            "A lower value does not mean the patch is unrelated to accessibility."
        ),
        "look_for": (
            "A low value does not mean the patch is not accessibility-related. Some accessibility fixes are structural, "
            "styling-related, or behavioral. This chart only captures explicit textual signals."
        ),
        "paper_use": "Use this chart to characterize repair strategy, not correctness.",
    },
    {
        "file": "09_extra_files_distribution_by_agent.png",
        "title": "Extra files touched by agent",
        "metric": (
            "Extra files are files touched by the agent but not touched by the developer for the same pull request."
        ),
        "question": "How many additional files did agents modify beyond the developer patch?",
        "why_numbers_matter": (
            "Extra files show how much the agent patch diverged from the developer patch. "
            "A few extra files may be harmless, but many extra files can indicate a broader or less localized repair."
        ),
        "how_to_read": (
            "Each boxplot shows the distribution of extra files. Zero means the agent did not touch files outside "
            "the developer-touched set."
        ),
        "look_for": (
            "High values suggest patch spread. This may indicate over-modification, but can also happen when an agent "
            "uses a valid alternative implementation strategy."
        ),
        "paper_use": "Use this chart to explain patch divergence from developer fixes.",
    },
    {
        "file": "10_flagged_patches_by_churn_ratio.png",
        "title": "Top flagged patches by agent-to-developer churn ratio",
        "metric": (
            "This chart ranks flagged agent patches by the ratio between agent lines of code churn and developer lines of code churn."
        ),
        "question": "Which specific pull request and agent pairs should be inspected first?",
        "why_numbers_matter": (
            "They identify the most extreme cases. "
            "These are useful candidates for qualitative examples in the paper."
        ),
        "how_to_read": (
            "Each bar is one agent patch for one pull request. Longer bars mean the agent changed much more code than the developer."
        ),
        "look_for": (
            "Use this as a triage chart. These patches are useful examples for qualitative analysis of over-modification "
            "or poor localization."
        ),
        "paper_use": "Use this chart to select representative examples for the discussion section.",
    },
    {
        "file": "11_app_wise_patch_counts_by_source.png",
        "title": "App-wise patch counts by source",
        "metric": (
            "This chart counts how many patches are available for each app, separated by patch source: "
            "developer, Claude, and Codex."
        ),
        "question": "Are the analyzed patches evenly distributed across apps, or concentrated in a few apps?",
        "why_numbers_matter": (
            "App concentration can affect interpretation. "
            "If many patches come from one app, the overall static-analysis results may partly reflect that app's structure."
        ),
        "how_to_read": (
            "Each horizontal bar group represents one app. The bars show how many developer, Claude, and Codex patches "
            "exist for that app."
        ),
        "look_for": (
            "Look for apps with much higher counts than others. These apps may have a stronger influence on the overall results."
        ),
        "paper_use": (
            "Use this chart to describe dataset coverage across apps. Do not use it as a correctness or success-rate chart."
        ),
    },
    {
        "file": "12_user_demographic_wise_patch_counts_by_source.png",
        "title": "User-demographic-wise patch counts by source",
        "metric": (
            "This chart counts how many patches are associated with each affected user demographic, separated by patch source."
        ),
        "question": "Which user demographics are represented in the analyzed patches?",
        "why_numbers_matter": (
            "Accessibility bugs affect different user groups. "
            "This chart shows whether the repair evaluation covers multiple affected populations or is concentrated in one group."
        ),
        "how_to_read": (
            "Each horizontal bar group represents one user demographic. The bars show how many developer, Claude, and Codex "
            "patches are associated with that demographic."
        ),
        "look_for": (
            "Look for user demographics with very low counts. Low-count categories should be interpreted cautiously."
        ),
        "paper_use": (
            "Use this chart to describe demographic coverage of the repair benchmark. Do not treat it as a fix-success chart."
        ),
    },
    {
        "file": "13_issue_type_wise_patch_counts_by_source.png",
        "title": "Issue-type-wise patch counts by source",
        "metric": (
            "This chart counts how many patches are associated with each broader accessibility issue type, separated by patch source."
        ),
        "question": "Which accessibility issue types are represented in the analyzed patches?",
        "why_numbers_matter": (
            "Different accessibility issue types may require different repair strategies. "
            "A model may perform differently on labeling issues, focus issues, keyboard-navigation issues, or screen-reader issues."
        ),
        "how_to_read": (
            "Each horizontal bar group represents one broader issue type. The bars show how many developer, Claude, and Codex "
            "patches are associated with that issue type."
        ),
        "look_for": (
            "Look for issue types with high or low representation. High-count issue types may drive the overall trends, while "
            "low-count issue types should be discussed carefully."
        ),
        "paper_use": (
            "Use this chart to describe issue-type coverage. Since it uses broader issue types, it is better for paper-level analysis "
            "than very fine-grained issue labels."
        ),
    },
]


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def to_numeric(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def to_bool(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for col in cols:
        if col in df.columns:
            df[col] = (
                df[col]
                .astype(str)
                .str.strip()
                .str.lower()
                .map({"true": True, "false": False, "1": True, "0": False})
            )
    return df


def esc(text: Any) -> str:
    return html.escape(str(text))


def is_missing(value: Any) -> bool:
    try:
        return pd.isna(value)
    except Exception:
        return value is None


def fmt_number(value: Any, digits: int = 2) -> str:
    if value is None or is_missing(value):
        return "—"
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def fmt_count(value: Any) -> str:
    if value is None or is_missing(value):
        return "—"
    try:
        return str(int(round(float(value))))
    except Exception:
        return str(value)


def fmt_score_out_of_one(value: Any, digits: int = 2) -> str:
    if value is None or is_missing(value):
        return "—"
    return f"{float(value):.{digits}f} / 1.00"


def fmt_ratio(value: Any, digits: int = 2) -> str:
    if value is None or is_missing(value):
        return "—"
    return f"{float(value):.{digits}f}× developer"


def fmt_percentage_from_fraction(value: Any, digits: int = 1) -> str:
    if value is None or is_missing(value):
        return "—"
    return f"{float(value) * 100:.{digits}f}%"


def bool_count(df: pd.DataFrame, col: str) -> int:
    if df.empty or col not in df.columns:
        return 0
    return int(df[col].fillna(False).sum())


def source_stats(patch_metrics: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}

    if patch_metrics.empty or "source" not in patch_metrics.columns:
        return stats

    for source in ["developer", "claude", "codex"]:
        sub = patch_metrics[patch_metrics["source"] == source].copy()
        if len(sub) == 0:
            continue

        patches = len(sub)

        stats[source] = {
            "patches": patches,
            "median_lines_of_code_churn": sub["loc_churn"].median() if "loc_churn" in sub else None,
            "median_files_changed": sub["files_changed"].median() if "files_changed" in sub else None,
            "median_hunks": sub["num_hunks"].median() if "num_hunks" in sub else None,

            "accessibility_signal_count": bool_count(sub, "added_any_a11y_signal"),
            "accessibility_signal_rate": (
                bool_count(sub, "added_any_a11y_signal") / patches if patches else None
            ),

            "config_touch_count": bool_count(sub, "patch_touches_config"),
            "config_touch_rate": (
                bool_count(sub, "patch_touches_config") / patches if patches else None
            ),

            "lockfile_touch_count": bool_count(sub, "patch_touches_lockfile"),
            "lockfile_touch_rate": (
                bool_count(sub, "patch_touches_lockfile") / patches if patches else None
            ),

            "generated_touch_count": bool_count(sub, "patch_touches_generated"),
            "generated_touch_rate": (
                bool_count(sub, "patch_touches_generated") / patches if patches else None
            ),
        }

    return stats


def agent_stats(agent_vs_dev: pd.DataFrame) -> Dict[str, Dict[str, Any]]:
    stats: Dict[str, Dict[str, Any]] = {}

    if agent_vs_dev.empty or "agent" not in agent_vs_dev.columns:
        return stats

    for agent in ["claude", "codex"]:
        sub = agent_vs_dev[agent_vs_dev["agent"] == agent].copy()
        if len(sub) == 0:
            continue

        pairs = len(sub)

        same_file_count = bool_count(sub, "same_file_as_developer")
        same_directory_count = bool_count(sub, "same_directory_as_developer")
        overmodified_count = bool_count(sub, "overmodified_flag")
        no_file_overlap_count = bool_count(sub, "no_file_overlap_flag")

        stats[agent] = {
            "pairs": pairs,
            "median_file_overlap": sub["file_overlap_jaccard"].median() if "file_overlap_jaccard" in sub else None,
            "median_churn_ratio": sub["churn_ratio_vs_developer"].median() if "churn_ratio_vs_developer" in sub else None,
            "median_extra_files": sub["extra_files_count"].median() if "extra_files_count" in sub else None,

            "same_file_count": same_file_count,
            "same_file_rate": same_file_count / pairs if pairs else None,

            "same_directory_count": same_directory_count,
            "same_directory_rate": same_directory_count / pairs if pairs else None,

            "overmodified_count": overmodified_count,
            "overmodified_rate": overmodified_count / pairs if pairs else None,

            "no_file_overlap_count": no_file_overlap_count,
            "no_file_overlap_rate": no_file_overlap_count / pairs if pairs else None,
        }

    return stats


def kpi_chip(value: str, label: str, sublabel: str = "", accent: str = "blue") -> str:
    """A compact metric chip used inside summary cards."""
    accent_map = {
        "blue": "#4f8ef7",
        "purple": "#a78bfa",
        "green": "#34d399",
        "amber": "#fbbf24",
    }
    color = accent_map.get(accent, "#4f8ef7")
    sub_html = f'<div class="kpi-sublabel">{esc(sublabel)}</div>' if sublabel else ""
    return f"""
    <div class="kpi-chip" style="--accent:{color}">
      <div class="kpi-value">{esc(value)}</div>
      <div class="kpi-label">{esc(label)}</div>
      {sub_html}
    </div>"""


def build_summary_cards(src_stats: Dict[str, Dict[str, Any]], ag_stats: Dict[str, Dict[str, Any]]) -> str:
    cards = []

    source_meta = {
        "developer": {"label": "Developer", "accent": "green", "icon": "👩‍💻"},
        "claude": {"label": "Claude", "accent": "blue", "icon": "🤖"},
        "codex": {"label": "Codex", "accent": "purple", "icon": "⚙️"},
    }

    for source in ["developer", "claude", "codex"]:
        s = src_stats.get(source)
        if not s:
            continue
        meta = source_meta[source]
        patches = s.get("patches")
        a_count = s.get("accessibility_signal_count")
        a_rate = s.get("accessibility_signal_rate")

        cards.append(f"""
        <div class="summary-card source-card">
          <div class="card-header">
            <span class="card-icon">{meta["icon"]}</span>
            <span class="card-title">{meta["label"]}</span>
            <span class="card-badge" style="--badge-color:var(--accent-{meta['accent']})">{fmt_count(patches)} patches</span>
          </div>
          <div class="kpi-row">
            {kpi_chip(fmt_number(s.get('median_lines_of_code_churn'), 1) + " lines", "Median LoC churn", "added + deleted lines", meta["accent"])}
            {kpi_chip(fmt_number(s.get('median_files_changed'), 1), "Median files changed", "per patch", meta["accent"])}
            {kpi_chip(
                f"{fmt_count(a_count)} / {fmt_count(patches)}",
                "A11y-signal patches",
                fmt_percentage_from_fraction(a_rate),
                meta["accent"]
            )}
          </div>
        </div>""")

    for agent in ["claude", "codex"]:
        s = ag_stats.get(agent)
        if not s:
            continue
        meta = source_meta[agent]
        pairs = s.get("pairs")

        cards.append(f"""
        <div class="summary-card agent-card">
          <div class="card-header">
            <span class="card-icon">{meta["icon"]}</span>
            <span class="card-title">{meta["label"]} vs. Developer</span>
            <span class="card-badge" style="--badge-color:var(--accent-{meta['accent']})">{fmt_count(pairs)} PR pairs</span>
          </div>
          <div class="kpi-row">
            {kpi_chip(fmt_score_out_of_one(s.get('median_file_overlap')), "Median file overlap", "Jaccard score", meta["accent"])}
            {kpi_chip(fmt_ratio(s.get('median_churn_ratio')), "Median churn ratio", "vs. developer patch", meta["accent"])}
            {kpi_chip(
                f"{fmt_count(s.get('overmodified_count'))} / {fmt_count(pairs)}",
                "Over-modification flags",
                fmt_percentage_from_fraction(s.get('overmodified_rate')),
                "amber"
            )}
          </div>
        </div>""")

    return "\n".join(cards)


def auto_interpretation_for_chart(
    chart_file: str,
    src_stats: Dict[str, Dict[str, Any]],
    ag_stats: Dict[str, Dict[str, Any]],
) -> str:
    dev = src_stats.get("developer", {})
    claude = src_stats.get("claude", {})
    codex = src_stats.get("codex", {})
    claude_ag = ag_stats.get("claude", {})
    codex_ag = ag_stats.get("codex", {})

    if chart_file == "01_median_loc_churn_by_source.png":
        return (
            f"Median LoC churn — Developer: {fmt_number(dev.get('median_lines_of_code_churn'), 1)} lines · "
            f"Claude: {fmt_number(claude.get('median_lines_of_code_churn'), 1)} lines · "
            f"Codex: {fmt_number(codex.get('median_lines_of_code_churn'), 1)} lines. "
            "A lower value means the typical patch from that source changed fewer lines."
        )

    if chart_file == "02_loc_churn_distribution_by_source.png":
        return (
            "This chart shows the full spread of patch sizes, not just the median. "
            "Large upper outliers indicate individual patches that changed much more code than typical patches from the same source."
        )

    if chart_file == "03_files_changed_distribution_by_source.png":
        return (
            f"Median files changed — Developer: {fmt_number(dev.get('median_files_changed'), 1)} · "
            f"Claude: {fmt_number(claude.get('median_files_changed'), 1)} · "
            f"Codex: {fmt_number(codex.get('median_files_changed'), 1)}. "
            "A lower value means the typical patch was more localized at the file level."
        )

    if chart_file == "04_file_overlap_distribution_by_agent.png":
        return (
            f"Median file-overlap score — Claude: {fmt_score_out_of_one(claude_ag.get('median_file_overlap'))} · "
            f"Codex: {fmt_score_out_of_one(codex_ag.get('median_file_overlap'))}. "
            "This score is bounded; the maximum possible value is 1.00 / 1.00."
        )

    if chart_file == "05_churn_ratio_distribution_by_agent.png":
        return (
            f"Median churn ratio — Claude: {fmt_ratio(claude_ag.get('median_churn_ratio'))} · "
            f"Codex: {fmt_ratio(codex_ag.get('median_churn_ratio'))}. "
            "A value above 1.00× means the agent changed more lines than the developer for the same PR."
        )

    if chart_file == "06_same_file_and_directory_rates.png":
        return (
            f"Claude — same-file: {fmt_count(claude_ag.get('same_file_count'))} / {fmt_count(claude_ag.get('pairs'))} pairs "
            f"({fmt_percentage_from_fraction(claude_ag.get('same_file_rate'))}); "
            f"same-directory: {fmt_count(claude_ag.get('same_directory_count'))} / {fmt_count(claude_ag.get('pairs'))} pairs "
            f"({fmt_percentage_from_fraction(claude_ag.get('same_directory_rate'))}). "
            f"Codex — same-file: {fmt_count(codex_ag.get('same_file_count'))} / {fmt_count(codex_ag.get('pairs'))} pairs "
            f"({fmt_percentage_from_fraction(codex_ag.get('same_file_rate'))}); "
            f"same-directory: {fmt_count(codex_ag.get('same_directory_count'))} / {fmt_count(codex_ag.get('pairs'))} pairs "
            f"({fmt_percentage_from_fraction(codex_ag.get('same_directory_rate'))})."
        )

    if chart_file == "07_overmodified_rate_by_agent.png":
        return (
            f"Claude over-modification flags: {fmt_count(claude_ag.get('overmodified_count'))} / "
            f"{fmt_count(claude_ag.get('pairs'))} pairs "
            f"({fmt_percentage_from_fraction(claude_ag.get('overmodified_rate'))}). "
            f"Codex: {fmt_count(codex_ag.get('overmodified_count'))} / "
            f"{fmt_count(codex_ag.get('pairs'))} pairs "
            f"({fmt_percentage_from_fraction(codex_ag.get('overmodified_rate'))}). "
            "This is a heuristic inspection signal, not a correctness label."
        )

    if chart_file == "08_accessibility_signal_rate_by_source.png":
        return (
            f"A11y-signal patches — Developer: {fmt_count(dev.get('accessibility_signal_count'))} / "
            f"{fmt_count(dev.get('patches'))} ({fmt_percentage_from_fraction(dev.get('accessibility_signal_rate'))}). "
            f"Claude: {fmt_count(claude.get('accessibility_signal_count'))} / "
            f"{fmt_count(claude.get('patches'))} ({fmt_percentage_from_fraction(claude.get('accessibility_signal_rate'))}). "
            f"Codex: {fmt_count(codex.get('accessibility_signal_count'))} / "
            f"{fmt_count(codex.get('patches'))} ({fmt_percentage_from_fraction(codex.get('accessibility_signal_rate'))})."
        )

    if chart_file == "09_extra_files_distribution_by_agent.png":
        return (
            f"Median extra files — Claude: {fmt_number(claude_ag.get('median_extra_files'), 1)} · "
            f"Codex: {fmt_number(codex_ag.get('median_extra_files'), 1)}. "
            "Extra files are files touched by the agent but not by the developer for the same PR."
        )

    if chart_file == "10_flagged_patches_by_churn_ratio.png":
        return (
            "This chart identifies specific PR–agent pairs that deserve qualitative inspection. "
            "The largest bars show where the agent changed many more lines than the developer for the same issue."
        )

    if chart_file == "11_app_wise_patch_counts_by_source.png":
        return (
            "This chart is based on the app metadata merged from sampled_prs.csv. "
            "It shows patch counts by app, not whether those patches successfully fixed the issue."
        )

    if chart_file == "12_user_demographic_wise_patch_counts_by_source.png":
        return (
            "This chart is based on the user demographic labels in sampled_prs.csv. "
            "If a PR has multiple demographics, it may contribute to more than one category. "
            "The chart shows coverage by affected user group, not repair success."
        )

    if chart_file == "13_issue_type_wise_patch_counts_by_source.png":
        return (
            "This chart is based on the Broader issue type column in sampled_prs.csv. "
            "If a PR has multiple broader issue types, it may contribute to more than one category. "
            "The chart shows issue-type coverage, not repair success."
        )

    return ""


def chart_section(chart: Dict[str, str], chart_index: int, charts_dir: Path, report_dir: Path, src_stats, ag_stats) -> str:
    img_path = charts_dir / chart["file"]

    if img_path.exists():
        rel_img = img_path.relative_to(report_dir).as_posix()
        img_html = f'<img src="{esc(rel_img)}" alt="{esc(chart["title"])}" loading="lazy">'
    else:
        img_html = f'<div class="missing">Missing chart: {esc(chart["file"])}</div>'

    auto_text = auto_interpretation_for_chart(chart["file"], src_stats, ag_stats)
    fig_num = f"{chart_index:02d}"

    return f"""
    <section class="chart-section">
      <div class="chart-header">
        <div class="fig-badge">FIG {fig_num}</div>
        <h2 class="chart-title">{esc(chart["title"])}</h2>
      </div>

      <p class="why-callout">{esc(chart["why_numbers_matter"])}</p>

      <div class="chart-wrap">
        {img_html}
      </div>

      <div class="meta-grid">
        <div class="meta-cell">
          <div class="meta-label">What this measures</div>
          <p>{esc(chart["metric"])}</p>
        </div>
        <div class="meta-cell">
          <div class="meta-label">Research question</div>
          <p>{esc(chart["question"])}</p>
        </div>
        <div class="meta-cell">
          <div class="meta-label">How to read it</div>
          <p>{esc(chart["how_to_read"])}</p>
        </div>
        <div class="meta-cell">
          <div class="meta-label">What to look for</div>
          <p>{esc(chart["look_for"])}</p>
        </div>
      </div>

      <div class="numbers-panel">
        <div class="numbers-header">
          <span class="numbers-icon">⟨/⟩</span>
          <span>Dataset-specific numbers</span>
        </div>
        <p class="numbers-intro">Computed from your CSV files. Bounded scores show their maximum (e.g., 0.38 / 1.00). Rates show counts and percentages (e.g., 9 / 25 patches).</p>
        <p class="numbers-body">{esc(auto_text)}</p>
      </div>

      <div class="paper-panel">
        <div class="paper-label">✦ Paper use</div>
        <p>{esc(chart["paper_use"])}</p>
      </div>
    </section>
    """


def build_html(report_dir: Path, charts_dir: Path, output_path: Path) -> str:
    patch_metrics = read_csv(report_dir / "patch_metrics.csv")
    agent_vs_dev = read_csv(report_dir / "agent_vs_developer.csv")

    patch_metrics = to_numeric(
        patch_metrics,
        [
            "files_changed",
            "source_files_changed",
            "test_files_changed",
            "loc_added",
            "loc_deleted",
            "loc_churn",
            "num_hunks",
        ],
    )

    patch_metrics = to_bool(
        patch_metrics,
        [
            "patch_found",
            "patch_touches_config",
            "patch_touches_lockfile",
            "patch_touches_generated",
            "added_any_a11y_signal",
            "deleted_any_a11y_signal",
        ],
    )

    agent_vs_dev = to_numeric(
        agent_vs_dev,
        [
            "file_overlap_jaccard",
            "extra_files_count",
            "missing_developer_files_count",
            "churn_ratio_vs_developer",
            "hunks_ratio_vs_developer",
        ],
    )

    agent_vs_dev = to_bool(
        agent_vs_dev,
        [
            "developer_patch_found",
            "agent_patch_found",
            "same_file_as_developer",
            "same_directory_as_developer",
            "same_top_level_dir_as_developer",
            "no_file_overlap_flag",
            "broad_extra_file_flag",
            "large_churn_flag",
            "overmodified_flag",
        ],
    )

    src_stats = source_stats(patch_metrics)
    ag_stats = agent_stats(agent_vs_dev)

    total_pull_requests = "—"
    if not patch_metrics.empty and "pr_id" in patch_metrics.columns:
        total_pull_requests = str(patch_metrics["pr_id"].nunique())

    chart_sections = "\n".join(
        chart_section(chart, i + 1, charts_dir, report_dir, src_stats, ag_stats)
        for i, chart in enumerate(CHARTS)
    )

    summary_cards = build_summary_cards(src_stats, ag_stats)

    html_text = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Static Diff Visual Report</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
  <style>
    /* ── Design tokens ── */
    :root {{
      --bg:            #0f1117;
      --surface:       #1a1d27;
      --surface-raised:#21253a;
      --border:        #2a2d3a;
      --border-subtle: #1e2130;
      --text-primary:  #f1f5f9;
      --text-secondary:#94a3b8;
      --text-muted:    #64748b;

      --accent-blue:   #4f8ef7;
      --accent-blue-bg:#1a2845;
      --accent-green:  #34d399;
      --accent-green-bg:#0d2a20;
      --accent-purple: #a78bfa;
      --accent-purple-bg:#1e1a3a;
      --accent-amber:  #fbbf24;
      --accent-amber-bg:#2a1f08;

      --mono: 'IBM Plex Mono', monospace;
      --sans: 'Inter', system-ui, sans-serif;

      --radius-sm: 6px;
      --radius-md: 10px;
      --radius-lg: 14px;
    }}

    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

    body {{
      background: var(--bg);
      color: var(--text-primary);
      font-family: var(--sans);
      font-size: 15px;
      line-height: 1.6;
    }}

    /* ── Header ── */
    header {{
      background: var(--surface);
      border-bottom: 1px solid var(--border);
      padding: 48px 56px 40px;
    }}

    .header-eyebrow {{
      font-family: var(--mono);
      font-size: 11px;
      letter-spacing: 0.12em;
      color: var(--accent-blue);
      text-transform: uppercase;
      margin-bottom: 14px;
    }}

    header h1 {{
      font-family: var(--mono);
      font-size: 28px;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 12px;
      letter-spacing: -0.02em;
    }}

    .header-meta {{
      display: flex;
      gap: 20px;
      flex-wrap: wrap;
      margin-top: 20px;
    }}

    .header-pill {{
      font-family: var(--mono);
      font-size: 12px;
      color: var(--text-secondary);
      background: var(--surface-raised);
      border: 1px solid var(--border);
      border-radius: 20px;
      padding: 4px 14px;
    }}

    header p {{
      color: var(--text-secondary);
      max-width: 760px;
      font-size: 14px;
    }}

    /* ── Layout ── */
    main {{
      max-width: 1200px;
      margin: 0 auto;
      padding: 36px 24px 80px;
    }}

    section.overview,
    section.chart-section {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-radius: var(--radius-lg);
      padding: 32px;
      margin-bottom: 24px;
    }}

    section.overview h2 {{
      font-family: var(--mono);
      font-size: 16px;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 14px;
      letter-spacing: -0.01em;
    }}

    section.overview p {{
      color: var(--text-secondary);
      font-size: 14px;
      margin-bottom: 10px;
    }}

    section.overview p:last-child {{ margin-bottom: 0; }}

    /* ── Note / warning box ── */
    .note {{
      background: var(--accent-amber-bg);
      border: 1px solid rgba(251,191,36,0.25);
      border-left: 3px solid var(--accent-amber);
      border-radius: var(--radius-md);
      padding: 14px 18px;
      margin-top: 18px;
      color: #e5c27a;
      font-size: 13px;
    }}

    .note strong {{ color: var(--accent-amber); }}

    /* ── Summary cards ── */
    .cards-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
      gap: 16px;
      margin-top: 20px;
    }}

    .summary-card {{
      background: var(--surface-raised);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 20px;
    }}

    .card-header {{
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 18px;
    }}

    .card-icon {{ font-size: 18px; }}

    .card-title {{
      font-family: var(--mono);
      font-size: 13px;
      font-weight: 600;
      color: var(--text-primary);
      flex: 1;
    }}

    .card-badge {{
      font-family: var(--mono);
      font-size: 11px;
      color: var(--badge-color, var(--accent-blue));
      background: rgba(79,142,247,0.1);
      border: 1px solid rgba(79,142,247,0.25);
      border-radius: 20px;
      padding: 2px 10px;
    }}

    .kpi-row {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: 10px;
    }}

    .kpi-chip {{
      background: var(--surface);
      border: 1px solid var(--border);
      border-top: 2px solid var(--accent, var(--accent-blue));
      border-radius: var(--radius-sm);
      padding: 12px 10px 10px;
    }}

    .kpi-value {{
      font-family: var(--mono);
      font-size: 15px;
      font-weight: 600;
      color: var(--accent, var(--accent-blue));
      margin-bottom: 4px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }}

    .kpi-label {{
      font-size: 11px;
      color: var(--text-primary);
      font-weight: 500;
      line-height: 1.3;
    }}

    .kpi-sublabel {{
      font-family: var(--mono);
      font-size: 10px;
      color: var(--text-muted);
      margin-top: 3px;
    }}

    /* ── Chart section ── */
    .chart-header {{
      display: flex;
      align-items: flex-start;
      gap: 16px;
      margin-bottom: 20px;
    }}

    .fig-badge {{
      font-family: var(--mono);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.1em;
      color: var(--accent-blue);
      background: var(--accent-blue-bg);
      border: 1px solid rgba(79,142,247,0.3);
      border-radius: var(--radius-sm);
      padding: 5px 10px;
      white-space: nowrap;
      flex-shrink: 0;
      margin-top: 3px;
    }}

    .chart-title {{
      font-family: var(--mono);
      font-size: 17px;
      font-weight: 600;
      color: var(--text-primary);
      letter-spacing: -0.02em;
      line-height: 1.3;
    }}

    .why-callout {{
      background: rgba(79,142,247,0.07);
      border-left: 3px solid var(--accent-blue);
      border-radius: var(--radius-sm);
      padding: 12px 16px;
      font-size: 13px;
      color: var(--text-secondary);
      margin-bottom: 22px;
    }}

    .chart-wrap {{
      text-align: center;
      margin: 0 0 24px;
      background: var(--surface-raised);
      border: 1px solid var(--border);
      border-radius: var(--radius-md);
      padding: 16px;
    }}

    .chart-wrap img {{
      max-width: 100%;
      height: auto;
      border-radius: var(--radius-sm);
      display: block;
      margin: 0 auto;
    }}

    /* ── Meta grid ── */
    .meta-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 12px;
      margin-bottom: 16px;
    }}

    .meta-cell {{
      background: var(--surface-raised);
      border: 1px solid var(--border-subtle);
      border-radius: var(--radius-sm);
      padding: 14px 16px;
    }}

    .meta-label {{
      font-family: var(--mono);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--text-muted);
      margin-bottom: 8px;
    }}

    .meta-cell p {{
      font-size: 13px;
      color: var(--text-secondary);
      margin: 0;
      line-height: 1.5;
    }}

    /* ── Numbers panel ── */
    .numbers-panel {{
      background: var(--accent-blue-bg);
      border: 1px solid rgba(79,142,247,0.2);
      border-radius: var(--radius-md);
      padding: 16px 20px;
      margin-bottom: 12px;
    }}

    .numbers-header {{
      display: flex;
      align-items: center;
      gap: 8px;
      font-family: var(--mono);
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.08em;
      text-transform: uppercase;
      color: var(--accent-blue);
      margin-bottom: 8px;
    }}

    .numbers-icon {{
      font-size: 13px;
    }}

    .numbers-intro {{
      font-size: 12px;
      color: var(--text-muted);
      margin-bottom: 8px;
    }}

    .numbers-body {{
      font-family: var(--mono);
      font-size: 12px;
      color: #a5c8ff;
      line-height: 1.7;
    }}

    /* ── Paper panel ── */
    .paper-panel {{
      background: var(--accent-green-bg);
      border: 1px solid rgba(52,211,153,0.2);
      border-radius: var(--radius-md);
      padding: 14px 18px;
    }}

    .paper-label {{
      font-family: var(--mono);
      font-size: 10px;
      font-weight: 600;
      letter-spacing: 0.1em;
      text-transform: uppercase;
      color: var(--accent-green);
      margin-bottom: 6px;
    }}

    .paper-panel p {{
      font-size: 13px;
      color: #86d4b0;
      margin: 0;
    }}

    /* ── Missing image ── */
    .missing {{
      padding: 28px;
      border: 1px dashed rgba(251,191,36,0.4);
      color: var(--accent-amber);
      border-radius: var(--radius-md);
      background: var(--accent-amber-bg);
      font-family: var(--mono);
      font-size: 13px;
      text-align: center;
    }}

    /* ── Blockquote ── */
    blockquote {{
      border-left: 3px solid var(--accent-blue);
      padding-left: 18px;
      margin: 16px 0 0;
      color: var(--text-secondary);
      font-size: 13px;
      line-height: 1.7;
      font-style: italic;
    }}

    code {{
      font-family: var(--mono);
      font-size: 12px;
      background: var(--surface-raised);
      border: 1px solid var(--border);
      padding: 1px 6px;
      border-radius: 4px;
      color: var(--accent-blue);
    }}

    strong {{ color: var(--text-primary); }}

    /* ── Interpretation guide ── */
    .interp-guide {{
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 14px;
      margin-top: 16px;
    }}

    .interp-card {{
      background: var(--surface-raised);
      border: 1px solid var(--border);
      border-radius: var(--radius-sm);
      padding: 14px 16px;
    }}

    .interp-card strong {{
      display: block;
      font-family: var(--mono);
      font-size: 11px;
      color: var(--text-muted);
      text-transform: uppercase;
      letter-spacing: 0.08em;
      margin-bottom: 6px;
    }}

    .interp-card p {{
      font-size: 13px;
      color: var(--text-secondary);
      margin: 0;
    }}

    /* ── Footer ── */
    footer {{
      text-align: center;
      padding: 32px;
      font-family: var(--mono);
      font-size: 11px;
      color: var(--text-muted);
      border-top: 1px solid var(--border-subtle);
      letter-spacing: 0.05em;
    }}

    /* ── Responsive ── */
    @media (max-width: 700px) {{
      header {{ padding: 28px 20px; }}
      main {{ padding: 20px 14px 60px; }}
      section.overview, section.chart-section {{ padding: 20px; }}
      .kpi-row {{ grid-template-columns: 1fr 1fr; }}
      .interp-guide {{ grid-template-columns: 1fr; }}
      header h1 {{ font-size: 20px; }}
    }}

    @media (prefers-reduced-motion: reduce) {{
      * {{ transition: none !important; animation: none !important; }}
    }}
  </style>
</head>

<body>
  <header>
    <div class="header-eyebrow">Accessibility Repair Benchmark · Static Diff Analysis</div>
    <h1>Static Diff Visual Report</h1>
    <p>
      Diff-level static comparisons among developer patches, Claude-generated patches,
      and Codex-generated patches. Covers patch size, localization similarity,
      over-modification signals, and accessibility-related code-change signals.
    </p>
    <div class="header-meta">
      <span class="header-pill">📋 {esc(total_pull_requests)} unique pull requests</span>
      <span class="header-pill">📊 {len(CHARTS)} figures</span>
      <span class="header-pill">⚠ Static analysis only — not a correctness measure</span>
    </div>
  </header>

  <main>
    <section class="overview">
      <h2>Summary statistics</h2>
      <p>
        A compact overview before the figure-by-figure analysis.
        Each metric shows whether generated patches tend to be larger, less localized,
        or more likely to trigger broad-change inspection flags than developer patches.
      </p>
      <div class="cards-grid">
        {summary_cards}
      </div>

      <div class="note">
        <strong>Scope limitation:</strong>
        All charts are computed from diffs — the textual record of added and deleted lines.
        They do not determine whether a patch is functionally correct.
        Interpret alongside manual build results and accessibility test outcomes.
      </div>
    </section>

    <section class="overview">
      <h2>How to read this report</h2>
      <p>
        The strongest insights come from reading the figures together.
      </p>
      <div class="interp-guide">
        <div class="interp-card">
          <strong>Succinctness</strong>
          <p><strong>LoC churn</strong> and <strong>files changed</strong> describe how much code each patch modifies.</p>
        </div>
        <div class="interp-card">
          <strong>Localization similarity</strong>
          <p><strong>File overlap</strong>, <strong>same-file rate</strong>, and <strong>same-directory rate</strong> measure how closely agents matched developer file choices.</p>
        </div>
        <div class="interp-card">
          <strong>Review burden signals</strong>
          <p><strong>Over-modification rate</strong> and <strong>extra files</strong> flag patches that may require more reviewer effort.</p>
        </div>
        <div class="interp-card">
          <strong>Interpretation guidance</strong>
          <p>A patch differing from the developer patch is not automatically wrong. Low overlap and high churn ratio are signals for qualitative inspection — not verdicts.</p>
        </div>
      </div>
    </section>

    {chart_sections}

    <section class="overview">
      <h2>Recommended paper framing</h2>
      <p>
        Describe these visualizations as measurements of <strong>succinctness</strong>,
        <strong>localization similarity</strong>, and <strong>static over-modification signals</strong>.
        Avoid presenting them as correctness metrics.
      </p>
      <blockquote>
        We compare developer and agent-generated patches using diff-level static metrics, including
        patch size, file-level overlap with the developer patch, same-directory localization, extra-file
        modifications, and accessibility-related code-change signals. These metrics characterize patch
        shape and review burden, rather than functional correctness.
      </blockquote>
    </section>
  </main>

  <footer>
    Generated from static diff analysis CSV files and chart images.
  </footer>
</body>
</html>
"""

    output_path.write_text(html_text, encoding="utf-8")
    return html_text


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-dir",
        default="static_diff_report",
        help="Folder containing CSV files and charts folder.",
    )
    parser.add_argument(
        "--charts-dir",
        default=None,
        help="Folder containing chart images. Default: <report-dir>/charts",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Output HTML path. Default: <report-dir>/static_diff_visual_report.html",
    )

    args = parser.parse_args()

    report_dir = Path(args.report_dir)
    charts_dir = Path(args.charts_dir) if args.charts_dir else report_dir / "charts"
    output_path = Path(args.out) if args.out else report_dir / "static_diff_visual_report.html"

    if not report_dir.exists():
        raise SystemExit(f"Report directory does not exist: {report_dir}")

    if not charts_dir.exists():
        raise SystemExit(f"Charts directory does not exist: {charts_dir}")

    build_html(report_dir, charts_dir, output_path)

    print(f"Done. HTML report written to: {output_path.resolve()}")


if __name__ == "__main__":
    main()