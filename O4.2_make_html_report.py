#!/usr/bin/env python3

"""
Create an HTML report for the static diff chart outputs.

This version adds:
- clearer explanations before each group of numbers
- explicit denominators for bounded metrics, such as 0.38 / 1.00
- count-based descriptions, such as 9 / 25 patches
- explanations of abbreviations such as lines of code and pull request
- clearer descriptions of how each metric is calculated
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
        "title": "1. Median lines of code churn by patch source",
        "metric": (
            "Lines of code churn means the number of added lines plus the number of deleted lines. "
            "For example, a patch with 8 added lines and 4 deleted lines has 12 lines of code churn."
        ),
        "question": "Which repair source tends to produce the smallest or largest patches?",
        "why_numbers_matter": (
            "These numbers matter because smaller patches are usually easier to review and integrate. "
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
        "title": "2. Lines of code churn distribution by patch source",
        "metric": (
            "This chart shows the distribution of patch sizes. Patch size is measured as added lines plus deleted lines."
        ),
        "question": "Are larger patches common, or are they caused by a few extreme cases?",
        "why_numbers_matter": (
            "These numbers matter because the median alone can hide unusual agent behavior. "
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
        "title": "3. Files changed distribution by patch source",
        "metric": "This chart counts how many files were changed by each patch.",
        "question": "Do agents spread their fixes across more files than developers?",
        "why_numbers_matter": (
            "These numbers matter because a fix that touches many files can be harder to review and may indicate "
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
        "title": "4. File overlap with developer patch by agent",
        "metric": (
            "File overlap is calculated with the Jaccard score: "
            "number of shared files divided by the total number of unique files changed by either the agent or developer. "
            "The score ranges from 0.00 / 1.00 to 1.00 / 1.00."
        ),
        "question": "Did the agent modify the same files as the developer?",
        "why_numbers_matter": (
            "These numbers matter because file overlap is a static proxy for localization similarity. "
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
        "title": "5. Agent-to-developer lines of code churn ratio",
        "metric": (
            "This ratio is calculated as agent lines of code churn divided by developer lines of code churn "
            "for the same pull request."
        ),
        "question": "How much larger or smaller are agent patches compared to the developer patch for the same pull request?",
        "why_numbers_matter": (
            "These numbers matter because this is a paired comparison. Instead of comparing all patches globally, "
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
        "title": "6. Same-file and same-directory rates",
        "metric": (
            "Same-file rate is the share of agent patches that touched at least one file also touched by the developer. "
            "Same-directory rate is the share of agent patches that touched at least one directory also touched by the developer."
        ),
        "question": "How often did agents work in the same code region as the developer?",
        "why_numbers_matter": (
            "These numbers matter because they separate exact file-level localization from broader module-level localization. "
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
        "title": "7. Over-modification flag rate by agent",
        "metric": (
            "Over-modification rate is the share of agent patches that triggered at least one broad-change heuristic. "
            "Examples include many extra files, much larger churn than the developer patch, or agent-only config, lockfile, "
            "or generated-file changes."
        ),
        "question": "How often did each agent produce patches that look broader than necessary?",
        "why_numbers_matter": (
            "These numbers matter because over-modification can increase review burden even if the patch builds. "
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
        "title": "8. Accessibility-signal rate by patch source",
        "metric": (
            "Accessibility-signal rate is the share of patches that added accessibility-related code tokens or application programming interface references. "
            "Examples include aria-label, role, tabindex, alternative text, focus handlers, contentDescription, accessibilityLabel, and visually-hidden text."
        ),
        "question": "Do patches explicitly modify accessibility-related code?",
        "why_numbers_matter": (
            "These numbers matter because they help characterize the repair strategy. "
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
        "title": "9. Extra files touched by agent",
        "metric": (
            "Extra files are files touched by the agent but not touched by the developer for the same pull request."
        ),
        "question": "How many additional files did agents modify beyond the developer patch?",
        "why_numbers_matter": (
            "These numbers matter because extra files show how much the agent patch diverged from the developer patch. "
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
        "title": "10. Top flagged patches by agent-to-developer churn ratio",
        "metric": (
            "This chart ranks flagged agent patches by the ratio between agent lines of code churn and developer lines of code churn."
        ),
        "question": "Which specific pull request and agent pairs should be inspected first?",
        "why_numbers_matter": (
            "These numbers matter because they identify the most extreme cases. "
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
        return "not available"
    try:
        return f"{float(value):.{digits}f}"
    except Exception:
        return str(value)


def fmt_count(value: Any) -> str:
    if value is None or is_missing(value):
        return "not available"
    try:
        return str(int(round(float(value))))
    except Exception:
        return str(value)


def fmt_score_out_of_one(value: Any, digits: int = 2) -> str:
    if value is None or is_missing(value):
        return "not available"
    return f"{float(value):.{digits}f} / 1.00"


def fmt_ratio(value: Any, digits: int = 2) -> str:
    if value is None or is_missing(value):
        return "not available"
    return f"{float(value):.{digits}f} × developer patch"


def fmt_percentage_from_fraction(value: Any, digits: int = 1) -> str:
    if value is None or is_missing(value):
        return "not available"
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


def stat_line(label: str, value: str, explanation: str) -> str:
    return f"""
    <div class="stat-line">
      <div class="stat-value">{esc(value)}</div>
      <div>
        <div class="stat-label">{esc(label)}</div>
        <div class="stat-explanation">{esc(explanation)}</div>
      </div>
    </div>
    """


def build_summary_cards(src_stats: Dict[str, Dict[str, Any]], ag_stats: Dict[str, Dict[str, Any]]) -> str:
    cards = []

    for source in ["developer", "claude", "codex"]:
        s = src_stats.get(source)
        if not s:
            continue

        patches = s.get("patches")

        cards.append(f"""
        <div class="card">
          <h3>{esc(source.title())}</h3>
          <p class="card-intro">
            These values summarize the typical size and accessibility-related signals for {esc(source)} patches.
          </p>

          {stat_line(
              "Patches analyzed",
              f"{fmt_count(patches)} patches",
              "The number of patches found for this source."
          )}

          {stat_line(
              "Median lines of code churn",
              f"{fmt_number(s.get('median_lines_of_code_churn'), 1)} lines",
              "The median number of added plus deleted lines."
          )}

          {stat_line(
              "Median files changed",
              f"{fmt_number(s.get('median_files_changed'), 1)} files",
              "The median number of files changed per patch."
          )}

          {stat_line(
              "Accessibility-signal patches",
              f"{fmt_count(s.get('accessibility_signal_count'))} / {fmt_count(patches)} patches "
              f"({fmt_percentage_from_fraction(s.get('accessibility_signal_rate'))})",
              "Patches that added explicit accessibility-related terms or programming interface references."
          )}
        </div>
        """)

    for agent in ["claude", "codex"]:
        s = ag_stats.get(agent)
        if not s:
            continue

        pairs = s.get("pairs")

        cards.append(f"""
        <div class="card">
          <h3>{esc(agent.title())} compared with developer</h3>
          <p class="card-intro">
            These values compare {esc(agent)} patches to developer patches for the same pull requests.
          </p>

          {stat_line(
              "Pairs analyzed",
              f"{fmt_count(pairs)} pull request pairs",
              "Each pair compares one agent patch against the developer patch for the same pull request."
          )}

          {stat_line(
              "Median file overlap",
              fmt_score_out_of_one(s.get("median_file_overlap")),
              "A bounded score where 0.00 / 1.00 means no shared files and 1.00 / 1.00 means identical changed-file sets."
          )}

          {stat_line(
              "Median churn ratio",
              fmt_ratio(s.get("median_churn_ratio")),
              "A value of 1.00 means the agent changed the same number of lines as the developer."
          )}

          {stat_line(
              "Over-modification flags",
              f"{fmt_count(s.get('overmodified_count'))} / {fmt_count(pairs)} pairs "
              f"({fmt_percentage_from_fraction(s.get('overmodified_rate'))})",
              "Pairs where the agent triggered at least one broad-change heuristic."
          )}
        </div>
        """)

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
            f"Median lines of code churn is developer: {fmt_number(dev.get('median_lines_of_code_churn'), 1)} lines, "
            f"Claude: {fmt_number(claude.get('median_lines_of_code_churn'), 1)} lines, "
            f"and Codex: {fmt_number(codex.get('median_lines_of_code_churn'), 1)} lines. "
            "A lower value means the typical patch from that source changed fewer lines."
        )

    if chart_file == "02_loc_churn_distribution_by_source.png":
        return (
            "This chart shows the full spread of patch sizes, not just the median. "
            "Large upper outliers indicate individual patches that changed much more code than typical patches from the same source."
        )

    if chart_file == "03_files_changed_distribution_by_source.png":
        return (
            f"Median files changed is developer: {fmt_number(dev.get('median_files_changed'), 1)} files, "
            f"Claude: {fmt_number(claude.get('median_files_changed'), 1)} files, "
            f"and Codex: {fmt_number(codex.get('median_files_changed'), 1)} files. "
            "A lower value means the typical patch was more localized at the file level."
        )

    if chart_file == "04_file_overlap_distribution_by_agent.png":
        return (
            f"Median file-overlap score is Claude: {fmt_score_out_of_one(claude_ag.get('median_file_overlap'))} "
            f"and Codex: {fmt_score_out_of_one(codex_ag.get('median_file_overlap'))}. "
            "This score is bounded, so the maximum possible value is 1.00 / 1.00."
        )

    if chart_file == "05_churn_ratio_distribution_by_agent.png":
        return (
            f"Median agent-to-developer churn ratio is Claude: {fmt_ratio(claude_ag.get('median_churn_ratio'))} "
            f"and Codex: {fmt_ratio(codex_ag.get('median_churn_ratio'))}. "
            "A value above 1.00 means the agent changed more lines than the developer for the same pull request."
        )

    if chart_file == "06_same_file_and_directory_rates.png":
        return (
            f"Claude same-file rate is {fmt_count(claude_ag.get('same_file_count'))} / "
            f"{fmt_count(claude_ag.get('pairs'))} pairs "
            f"({fmt_percentage_from_fraction(claude_ag.get('same_file_rate'))}); "
            f"Claude same-directory rate is {fmt_count(claude_ag.get('same_directory_count'))} / "
            f"{fmt_count(claude_ag.get('pairs'))} pairs "
            f"({fmt_percentage_from_fraction(claude_ag.get('same_directory_rate'))}). "
            f"Codex same-file rate is {fmt_count(codex_ag.get('same_file_count'))} / "
            f"{fmt_count(codex_ag.get('pairs'))} pairs "
            f"({fmt_percentage_from_fraction(codex_ag.get('same_file_rate'))}); "
            f"Codex same-directory rate is {fmt_count(codex_ag.get('same_directory_count'))} / "
            f"{fmt_count(codex_ag.get('pairs'))} pairs "
            f"({fmt_percentage_from_fraction(codex_ag.get('same_directory_rate'))})."
        )

    if chart_file == "07_overmodified_rate_by_agent.png":
        return (
            f"Claude over-modification flag count is {fmt_count(claude_ag.get('overmodified_count'))} / "
            f"{fmt_count(claude_ag.get('pairs'))} pairs "
            f"({fmt_percentage_from_fraction(claude_ag.get('overmodified_rate'))}). "
            f"Codex over-modification flag count is {fmt_count(codex_ag.get('overmodified_count'))} / "
            f"{fmt_count(codex_ag.get('pairs'))} pairs "
            f"({fmt_percentage_from_fraction(codex_ag.get('overmodified_rate'))}). "
            "This is a heuristic inspection signal, not a correctness label."
        )

    if chart_file == "08_accessibility_signal_rate_by_source.png":
        return (
            f"Developer accessibility-signal count is {fmt_count(dev.get('accessibility_signal_count'))} / "
            f"{fmt_count(dev.get('patches'))} patches "
            f"({fmt_percentage_from_fraction(dev.get('accessibility_signal_rate'))}). "
            f"Claude accessibility-signal count is {fmt_count(claude.get('accessibility_signal_count'))} / "
            f"{fmt_count(claude.get('patches'))} patches "
            f"({fmt_percentage_from_fraction(claude.get('accessibility_signal_rate'))}). "
            f"Codex accessibility-signal count is {fmt_count(codex.get('accessibility_signal_count'))} / "
            f"{fmt_count(codex.get('patches'))} patches "
            f"({fmt_percentage_from_fraction(codex.get('accessibility_signal_rate'))})."
        )

    if chart_file == "09_extra_files_distribution_by_agent.png":
        return (
            f"Median extra files are Claude: {fmt_number(claude_ag.get('median_extra_files'), 1)} files "
            f"and Codex: {fmt_number(codex_ag.get('median_extra_files'), 1)} files. "
            "Extra files are files touched by the agent but not by the developer for the same pull request."
        )

    if chart_file == "10_flagged_patches_by_churn_ratio.png":
        return (
            "This chart identifies specific pull request and agent pairs that deserve qualitative inspection. "
            "The largest bars show where the agent changed many more lines than the developer for the same issue."
        )

    return ""


def chart_section(chart: Dict[str, str], charts_dir: Path, report_dir: Path, src_stats, ag_stats) -> str:
    img_path = charts_dir / chart["file"]

    if img_path.exists():
        rel_img = img_path.relative_to(report_dir).as_posix()
        img_html = f'<img src="{esc(rel_img)}" alt="{esc(chart["title"])}">'
    else:
        img_html = f'<div class="missing">Missing chart image: {esc(chart["file"])}</div>'

    auto_text = auto_interpretation_for_chart(chart["file"], src_stats, ag_stats)

    return f"""
    <section class="chart-section">
      <h2>{esc(chart["title"])}</h2>

      <p class="why-before-numbers">
        <strong>Why these numbers matter:</strong>
        {esc(chart["why_numbers_matter"])}
      </p>

      <div class="chart-wrap">
        {img_html}
      </div>

      <div class="explanation-grid">
        <div>
          <h4>What this measures</h4>
          <p>{esc(chart["metric"])}</p>
        </div>
        <div>
          <h4>Research question</h4>
          <p>{esc(chart["question"])}</p>
        </div>
        <div>
          <h4>How to read it</h4>
          <p>{esc(chart["how_to_read"])}</p>
        </div>
        <div>
          <h4>What to look for</h4>
          <p>{esc(chart["look_for"])}</p>
        </div>
      </div>

      <div class="interpretation">
        <h4>Dataset-specific numbers</h4>
        <p class="numbers-intro">
          The following values are calculated from your generated comma-separated value files.
          Bounded scores are shown with their maximum value, such as 0.38 / 1.00.
          Rate-based metrics are shown as both counts and percentages, such as 9 / 25 patches.
        </p>
        <p>{esc(auto_text)}</p>
      </div>

      <div class="paper-use">
        <h4>How this can be used in the paper</h4>
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

    total_pull_requests = "not available"
    if not patch_metrics.empty and "pr_id" in patch_metrics.columns:
        total_pull_requests = str(patch_metrics["pr_id"].nunique())

    chart_sections = "\n".join(
        chart_section(chart, charts_dir, report_dir, src_stats, ag_stats)
        for chart in CHARTS
    )

    summary_cards = build_summary_cards(src_stats, ag_stats)

    html_text = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Static Diff Visual Report</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, Helvetica, sans-serif;
      background: #f7f8fb;
      color: #222;
      line-height: 1.5;
    }}

    header {{
      background: #1f2937;
      color: white;
      padding: 36px 56px;
    }}

    header h1 {{
      margin: 0 0 8px 0;
      font-size: 32px;
    }}

    header p {{
      margin: 0;
      max-width: 1000px;
      color: #d1d5db;
      font-size: 16px;
    }}

    main {{
      max-width: 1180px;
      margin: 0 auto;
      padding: 32px 24px 64px 24px;
    }}

    .overview {{
      background: white;
      border-radius: 14px;
      padding: 24px;
      margin-bottom: 28px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }}

    .overview h2 {{
      margin-top: 0;
    }}

    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(270px, 1fr));
      gap: 16px;
      margin-top: 18px;
    }}

    .card {{
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      padding: 16px;
      background: #fbfbfd;
    }}

    .card h3 {{
      margin-top: 0;
      margin-bottom: 10px;
    }}

    .card-intro {{
      color: #4b5563;
      font-size: 14px;
      margin-bottom: 14px;
    }}

    .stat-line {{
      display: grid;
      grid-template-columns: 95px 1fr;
      gap: 12px;
      align-items: start;
      padding: 10px 0;
      border-top: 1px solid #e5e7eb;
    }}

    .stat-value {{
      font-weight: bold;
      color: #111827;
    }}

    .stat-label {{
      font-weight: bold;
      color: #374151;
    }}

    .stat-explanation {{
      color: #6b7280;
      font-size: 13px;
      margin-top: 2px;
    }}

    .chart-section {{
      background: white;
      border-radius: 14px;
      padding: 28px;
      margin-bottom: 28px;
      box-shadow: 0 1px 4px rgba(0,0,0,0.08);
    }}

    .chart-section h2 {{
      margin-top: 0;
      font-size: 24px;
      color: #111827;
    }}

    .why-before-numbers {{
      background: #eef2ff;
      border-left: 5px solid #4f46e5;
      padding: 14px 16px;
      border-radius: 8px;
      margin: 14px 0 22px 0;
    }}

    .chart-wrap {{
      text-align: center;
      margin: 20px 0 26px 0;
    }}

    .chart-wrap img {{
      max-width: 100%;
      height: auto;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      background: white;
    }}

    .explanation-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 16px;
      margin-top: 12px;
    }}

    .explanation-grid div,
    .interpretation,
    .paper-use {{
      background: #f9fafb;
      border: 1px solid #e5e7eb;
      border-radius: 10px;
      padding: 14px 16px;
    }}

    h4 {{
      margin: 0 0 8px 0;
      color: #374151;
    }}

    .interpretation {{
      margin-top: 16px;
      border-left: 5px solid #2563eb;
    }}

    .numbers-intro {{
      color: #4b5563;
      margin-bottom: 8px;
    }}

    .paper-use {{
      margin-top: 16px;
      border-left: 5px solid #059669;
    }}

    .missing {{
      padding: 24px;
      border: 1px dashed #dc2626;
      color: #dc2626;
      border-radius: 10px;
      background: #fff7f7;
    }}

    .note {{
      background: #fff7ed;
      border-left: 5px solid #f97316;
      padding: 14px 16px;
      border-radius: 8px;
      margin-top: 16px;
    }}

    code {{
      background: #eef2ff;
      padding: 2px 5px;
      border-radius: 4px;
    }}

    blockquote {{
      border-left: 5px solid #d1d5db;
      margin-left: 0;
      padding-left: 16px;
      color: #374151;
    }}

    footer {{
      text-align: center;
      color: #6b7280;
      padding: 24px;
    }}
  </style>
</head>

<body>
  <header>
    <h1>Static Diff Visual Report</h1>
    <p>
      This report summarizes diff-level static comparisons among developer patches,
      Claude-generated patches, and Codex-generated patches. The charts focus on
      patch size, localization similarity, over-modification signals, and
      accessibility-related patch signals.
    </p>
  </header>

  <main>
    <section class="overview">
      <h2>Overview</h2>
      <p>
        Total unique pull requests detected: <strong>{esc(total_pull_requests)}</strong>.
        A pull request is a proposed code change submitted to a software repository.
        The report compares each generated patch against the developer patch for the same pull request.
      </p>

      <div class="note">
        <strong>Important limitation:</strong>
        These charts are computed from diffs only. A diff is the textual record of added and deleted lines.
        These charts do not prove whether a patch is functionally correct. They should be interpreted together
        with your manual build results and accessibility test outcomes.
      </div>

      <h3>Summary numbers</h3>
      <p>
        The numbers below provide a compact overview before the chart-by-chart analysis.
        They matter because they show whether generated patches tend to be larger, less localized,
        or more likely to trigger broad-change inspection flags than developer patches.
      </p>

      <div class="cards">
        {summary_cards}
      </div>
    </section>

    <section class="overview">
      <h2>How to interpret this report</h2>
      <p>
        The strongest results usually come from reading the charts together:
        <strong>lines of code churn</strong> and <strong>files changed</strong> describe patch succinctness;
        <strong>file overlap</strong>, <strong>same-file rate</strong>, and <strong>same-directory rate</strong>
        describe localization similarity; and <strong>over-modification rate</strong> and
        <strong>extra files</strong> describe potential review burden.
      </p>
      <p>
        A patch that differs from the developer patch is not automatically wrong. However,
        low overlap, high churn ratio, and many extra files are useful signals for selecting
        cases that need closer qualitative inspection.
      </p>
    </section>

    {chart_sections}

    <section class="overview">
      <h2>Recommended paper framing</h2>
      <p>
        These visualizations support a static patch-shape analysis. In the paper, describe them as
        measurements of <strong>succinctness</strong>, <strong>localization similarity</strong>, and
        <strong>static over-modification signals</strong>. Avoid presenting them as correctness metrics.
      </p>
      <p>
        A concise sentence you can use:
      </p>
      <blockquote>
        We compare developer and agent-generated patches using diff-level static metrics, including
        patch size, file-level overlap with the developer patch, same-directory localization, extra-file
        modifications, and accessibility-related code-change signals. These metrics are intended to
        characterize patch shape and review burden, rather than to determine functional correctness.
      </blockquote>
    </section>
  </main>

  <footer>
    Generated from static diff analysis comma-separated value files and chart images.
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
        help="Folder containing comma-separated value files and charts folder.",
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