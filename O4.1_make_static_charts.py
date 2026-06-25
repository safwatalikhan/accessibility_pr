#!/usr/bin/env python3

"""
Generate visual charts from static diff analysis CSV files.

Expected input folder:

static_diff_report/
  agent_vs_developer.csv
  patch_metrics.csv
  summary_by_source.csv
  changed_files.csv
  static_diff_report.md

This script creates chart PNGs in:

static_diff_report/charts/

The charts help you understand:
- whether AI patches are larger than developer patches
- whether AI patches touch more files
- whether AI patches overlap with developer-touched files
- whether AI patches show over-modification signals
- whether patches contain accessibility-related diff signals
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import List, Optional

import pandas as pd
import matplotlib.pyplot as plt


# =============================================================================
# Basic helpers
# =============================================================================

def read_csv_if_exists(path: Path) -> pd.DataFrame:
    if not path.exists():
        print(f"Missing file: {path}")
        return pd.DataFrame()
    return pd.read_csv(path)


def ensure_numeric(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for col in cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def ensure_bool(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
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


def save_current_fig(out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out_path, dpi=300, bbox_inches="tight")
    plt.close()
    print(f"Wrote: {out_path}")


def clean_source_order(df: pd.DataFrame) -> pd.DataFrame:
    if "source" not in df.columns:
        return df

    order = ["developer", "claude", "codex"]
    df = df.copy()
    df["source"] = pd.Categorical(df["source"], categories=order, ordered=True)
    return df.sort_values("source")


def clean_agent_order(df: pd.DataFrame) -> pd.DataFrame:
    if "agent" not in df.columns:
        return df

    order = ["claude", "codex"]
    df = df.copy()
    df["agent"] = pd.Categorical(df["agent"], categories=order, ordered=True)
    return df.sort_values("agent")


# =============================================================================
# Chart 1: Median LOC churn by source
# =============================================================================

def chart_median_loc_churn_by_source(patch_metrics: pd.DataFrame, out_dir: Path) -> Optional[Path]:
    """
    Shows the median patch size for developer, Claude, and Codex.

    Main interpretation:
    - Higher median LOC churn means larger patches.
    - If agents have much higher churn than developers, their patches are less succinct.
    """

    required = {"source", "loc_churn"}
    if not required.issubset(patch_metrics.columns):
        return None

    df = patch_metrics.dropna(subset=["loc_churn"]).copy()
    df = clean_source_order(df)

    summary = df.groupby("source", observed=False)["loc_churn"].median().dropna()

    plt.figure(figsize=(7, 4.5))
    summary.plot(kind="bar")
    plt.title("Median LOC churn by patch source")
    plt.xlabel("Patch source")
    plt.ylabel("Median LOC churn")
    plt.xticks(rotation=0)

    out_path = out_dir / "01_median_loc_churn_by_source.png"
    save_current_fig(out_path)
    return out_path


# =============================================================================
# Chart 2: LOC churn distribution by source
# =============================================================================

def chart_loc_churn_distribution_by_source(patch_metrics: pd.DataFrame, out_dir: Path) -> Optional[Path]:
    """
    Shows the distribution of patch sizes.

    Main interpretation:
    - Boxplots show whether one source often creates much larger patches.
    - Outliers may reveal unusually large AI-generated fixes.
    """

    required = {"source", "loc_churn"}
    if not required.issubset(patch_metrics.columns):
        return None

    df = patch_metrics.dropna(subset=["loc_churn"]).copy()
    df = clean_source_order(df)

    groups = []
    labels = []

    for source in ["developer", "claude", "codex"]:
        values = df[df["source"] == source]["loc_churn"].dropna()
        if len(values) > 0:
            groups.append(values)
            labels.append(source)

    if not groups:
        return None

    plt.figure(figsize=(7, 4.5))
    plt.boxplot(groups, labels=labels, showfliers=True)
    plt.title("LOC churn distribution by patch source")
    plt.xlabel("Patch source")
    plt.ylabel("LOC churn")

    out_path = out_dir / "02_loc_churn_distribution_by_source.png"
    save_current_fig(out_path)
    return out_path


# =============================================================================
# Chart 3: Files changed distribution by source
# =============================================================================

def chart_files_changed_distribution_by_source(patch_metrics: pd.DataFrame, out_dir: Path) -> Optional[Path]:
    """
    Shows whether agents touch more files than developers.

    Main interpretation:
    - If agent boxplots are higher, they are spreading fixes across more files.
    - This supports over-modification/localization analysis.
    """

    required = {"source", "files_changed"}
    if not required.issubset(patch_metrics.columns):
        return None

    df = patch_metrics.dropna(subset=["files_changed"]).copy()
    df = clean_source_order(df)

    groups = []
    labels = []

    for source in ["developer", "claude", "codex"]:
        values = df[df["source"] == source]["files_changed"].dropna()
        if len(values) > 0:
            groups.append(values)
            labels.append(source)

    if not groups:
        return None

    plt.figure(figsize=(7, 4.5))
    plt.boxplot(groups, labels=labels, showfliers=True)
    plt.title("Files changed distribution by patch source")
    plt.xlabel("Patch source")
    plt.ylabel("Files changed")

    out_path = out_dir / "03_files_changed_distribution_by_source.png"
    save_current_fig(out_path)
    return out_path


# =============================================================================
# Chart 4: File overlap distribution by agent
# =============================================================================

def chart_file_overlap_distribution_by_agent(agent_vs_dev: pd.DataFrame, out_dir: Path) -> Optional[Path]:
    """
    Shows how much each agent overlaps with the developer patch at file level.

    Main interpretation:
    - 1.0 means agent touched exactly the same changed-file set as developer.
    - 0.0 means agent touched completely different files.
    - Higher is generally better for localization similarity.
    """

    required = {"agent", "file_overlap_jaccard"}
    if not required.issubset(agent_vs_dev.columns):
        return None

    df = agent_vs_dev.dropna(subset=["file_overlap_jaccard"]).copy()
    df = clean_agent_order(df)

    groups = []
    labels = []

    for agent in ["claude", "codex"]:
        values = df[df["agent"] == agent]["file_overlap_jaccard"].dropna()
        if len(values) > 0:
            groups.append(values)
            labels.append(agent)

    if not groups:
        return None

    plt.figure(figsize=(7, 4.5))
    plt.boxplot(groups, labels=labels, showfliers=True)
    plt.title("File overlap with developer patch by agent")
    plt.xlabel("Agent")
    plt.ylabel("File overlap Jaccard score")
    plt.ylim(-0.05, 1.05)

    out_path = out_dir / "04_file_overlap_distribution_by_agent.png"
    save_current_fig(out_path)
    return out_path


# =============================================================================
# Chart 5: Churn ratio distribution by agent
# =============================================================================

def chart_churn_ratio_distribution_by_agent(agent_vs_dev: pd.DataFrame, out_dir: Path) -> Optional[Path]:
    """
    Shows how large agent patches are compared to developer patches.

    Main interpretation:
    - 1.0 means same LOC churn as developer.
    - 2.0 means agent changed twice as many lines.
    - 0.5 means agent changed half as many lines.
    """

    required = {"agent", "churn_ratio_vs_developer"}
    if not required.issubset(agent_vs_dev.columns):
        return None

    df = agent_vs_dev.dropna(subset=["churn_ratio_vs_developer"]).copy()
    df = clean_agent_order(df)

    groups = []
    labels = []

    for agent in ["claude", "codex"]:
        values = df[df["agent"] == agent]["churn_ratio_vs_developer"].dropna()
        if len(values) > 0:
            groups.append(values)
            labels.append(agent)

    if not groups:
        return None

    plt.figure(figsize=(7, 4.5))
    plt.boxplot(groups, labels=labels, showfliers=True)
    plt.axhline(1.0, linestyle="--", linewidth=1)
    plt.title("Agent LOC churn ratio compared to developer")
    plt.xlabel("Agent")
    plt.ylabel("Agent churn / developer churn")

    out_path = out_dir / "05_churn_ratio_distribution_by_agent.png"
    save_current_fig(out_path)
    return out_path


# =============================================================================
# Chart 6: Same-file and same-directory rates
# =============================================================================

def chart_same_file_directory_rates(agent_vs_dev: pd.DataFrame, out_dir: Path) -> Optional[Path]:
    """
    Shows how often agents touched the same file or directory as developers.

    Main interpretation:
    - Same-file rate is a stricter localization signal.
    - Same-directory rate is a looser localization signal.
    """

    required = {"agent", "same_file_as_developer", "same_directory_as_developer"}
    if not required.issubset(agent_vs_dev.columns):
        return None

    df = agent_vs_dev.copy()
    df = clean_agent_order(df)

    rows = []

    for agent in ["claude", "codex"]:
        sub = df[df["agent"] == agent]
        if len(sub) == 0:
            continue

        rows.append({
            "agent": agent,
            "same_file_rate": sub["same_file_as_developer"].mean() * 100,
            "same_directory_rate": sub["same_directory_as_developer"].mean() * 100,
        })

    if not rows:
        return None

    plot_df = pd.DataFrame(rows).set_index("agent")

    plt.figure(figsize=(7, 4.5))
    plot_df.plot(kind="bar")
    plt.title("Same-file and same-directory rates")
    plt.xlabel("Agent")
    plt.ylabel("Rate (%)")
    plt.xticks(rotation=0)
    plt.ylim(0, 100)
    plt.legend(["Same file", "Same directory"])

    out_path = out_dir / "06_same_file_and_directory_rates.png"
    save_current_fig(out_path)
    return out_path


# =============================================================================
# Chart 7: Overmodified rate by agent
# =============================================================================

def chart_overmodified_rate_by_agent(agent_vs_dev: pd.DataFrame, out_dir: Path) -> Optional[Path]:
    """
    Shows how often each agent triggered the over-modification heuristic.

    Main interpretation:
    - Higher rate means more patches had broad extra files, high churn, or
      agent-only config/lock/generated-file changes.
    - This is not correctness. It is an inspection signal.
    """

    required = {"agent", "overmodified_flag"}
    if not required.issubset(agent_vs_dev.columns):
        return None

    df = agent_vs_dev.copy()
    df = clean_agent_order(df)

    summary = df.groupby("agent", observed=False)["overmodified_flag"].mean().dropna() * 100

    plt.figure(figsize=(7, 4.5))
    summary.plot(kind="bar")
    plt.title("Over-modification flag rate by agent")
    plt.xlabel("Agent")
    plt.ylabel("Flagged patches (%)")
    plt.xticks(rotation=0)
    plt.ylim(0, 100)

    out_path = out_dir / "07_overmodified_rate_by_agent.png"
    save_current_fig(out_path)
    return out_path


# =============================================================================
# Chart 8: Accessibility signal rate by source
# =============================================================================

def chart_accessibility_signal_rate_by_source(patch_metrics: pd.DataFrame, out_dir: Path) -> Optional[Path]:
    """
    Shows how often patches added accessibility-related signals.

    Main interpretation:
    - Higher rate means the patch added terms such as aria-label, role,
      tabindex, alt text, focus handlers, contentDescription, etc.
    - This does not prove correctness, but helps characterize repair strategy.
    """

    required = {"source", "added_any_a11y_signal"}
    if not required.issubset(patch_metrics.columns):
        return None

    df = patch_metrics.copy()
    df = clean_source_order(df)

    summary = df.groupby("source", observed=False)["added_any_a11y_signal"].mean().dropna() * 100

    plt.figure(figsize=(7, 4.5))
    summary.plot(kind="bar")
    plt.title("Accessibility-signal rate by patch source")
    plt.xlabel("Patch source")
    plt.ylabel("Patches with added a11y signal (%)")
    plt.xticks(rotation=0)
    plt.ylim(0, 100)

    out_path = out_dir / "08_accessibility_signal_rate_by_source.png"
    save_current_fig(out_path)
    return out_path


# =============================================================================
# Chart 9: Extra files distribution by agent
# =============================================================================

def chart_extra_files_distribution_by_agent(agent_vs_dev: pd.DataFrame, out_dir: Path) -> Optional[Path]:
    """
    Shows how many files agents touched beyond the developer patch.

    Main interpretation:
    - Higher values mean the agent modified more files that the developer did not.
    - This is useful for spotting over-modification.
    """

    required = {"agent", "extra_files_count"}
    if not required.issubset(agent_vs_dev.columns):
        return None

    df = agent_vs_dev.dropna(subset=["extra_files_count"]).copy()
    df = clean_agent_order(df)

    groups = []
    labels = []

    for agent in ["claude", "codex"]:
        values = df[df["agent"] == agent]["extra_files_count"].dropna()
        if len(values) > 0:
            groups.append(values)
            labels.append(agent)

    if not groups:
        return None

    plt.figure(figsize=(7, 4.5))
    plt.boxplot(groups, labels=labels, showfliers=True)
    plt.title("Extra files touched by agent")
    plt.xlabel("Agent")
    plt.ylabel("Files touched by agent but not developer")

    out_path = out_dir / "09_extra_files_distribution_by_agent.png"
    save_current_fig(out_path)
    return out_path


# =============================================================================
# Chart 10: Top flagged patches by churn ratio
# =============================================================================

def chart_flagged_patches_by_churn_ratio(agent_vs_dev: pd.DataFrame, out_dir: Path, top_n: int = 15) -> Optional[Path]:
    """
    Shows the most extreme agent patches by churn ratio.

    Main interpretation:
    - These are the patches where the agent changed much more code than the developer.
    - Use this chart to pick cases for manual inspection.
    """

    required = {"pr_id", "agent", "churn_ratio_vs_developer"}
    if not required.issubset(agent_vs_dev.columns):
        return None

    df = agent_vs_dev.dropna(subset=["churn_ratio_vs_developer"]).copy()

    if "overmodified_flag" in df.columns:
        flagged = df[df["overmodified_flag"] == True].copy()
        if len(flagged) > 0:
            df = flagged

    df = df.sort_values("churn_ratio_vs_developer", ascending=False).head(top_n)

    if len(df) == 0:
        return None

    df["label"] = df["agent"].astype(str) + " PR_" + df["pr_id"].astype(str)

    plot_df = df.set_index("label")["churn_ratio_vs_developer"].sort_values()

    plt.figure(figsize=(8, max(4.5, 0.35 * len(plot_df))))
    plot_df.plot(kind="barh")
    plt.axvline(1.0, linestyle="--", linewidth=1)
    plt.title("Top agent patches by churn ratio")
    plt.xlabel("Agent churn / developer churn")
    plt.ylabel("Patch")

    out_path = out_dir / "10_flagged_patches_by_churn_ratio.png"
    save_current_fig(out_path)
    return out_path


# =============================================================================
# Markdown index for charts
# =============================================================================

def write_charts_index(out_dir: Path, chart_paths: List[Path]) -> None:
    """
    Creates a Markdown file that embeds all generated charts.

    This makes it easy to scroll through the visual report in one place.
    """

    descriptions = {
        "01_median_loc_churn_by_source.png": "Compares the median patch size across developer, Claude, and Codex.",
        "02_loc_churn_distribution_by_source.png": "Shows how patch size varies within each source.",
        "03_files_changed_distribution_by_source.png": "Shows whether agents tend to touch more files than developers.",
        "04_file_overlap_distribution_by_agent.png": "Shows how closely agent-touched files overlap with developer-touched files.",
        "05_churn_ratio_distribution_by_agent.png": "Shows how large agent patches are relative to developer patches.",
        "06_same_file_and_directory_rates.png": "Shows localization similarity at file and directory level.",
        "07_overmodified_rate_by_agent.png": "Shows how often agents triggered over-modification heuristics.",
        "08_accessibility_signal_rate_by_source.png": "Shows how often patches add accessibility-related terms or API references.",
        "09_extra_files_distribution_by_agent.png": "Shows how many extra files agents touched beyond developer patches.",
        "10_flagged_patches_by_churn_ratio.png": "Ranks the most extreme patches by agent/developer churn ratio.",
    }

    lines = ["# Static Diff Charts\n"]

    for path in chart_paths:
        name = path.name
        desc = descriptions.get(name, "")
        lines.append(f"## {name}")
        if desc:
            lines.append(desc)
        lines.append("")
        lines.append(f"![{name}]({name})")
        lines.append("")

    index_path = out_dir / "charts_index.md"
    index_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote: {index_path}")


# =============================================================================
# Main
# =============================================================================

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report-dir",
        default="static_diff_report",
        help="Folder containing patch_metrics.csv and agent_vs_developer.csv",
    )
    parser.add_argument(
        "--out-dir",
        default=None,
        help="Output folder for charts. Default: <report-dir>/charts",
    )

    args = parser.parse_args()

    report_dir = Path(args.report_dir)
    out_dir = Path(args.out_dir) if args.out_dir else report_dir / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)

    patch_metrics = read_csv_if_exists(report_dir / "patch_metrics.csv")
    agent_vs_dev = read_csv_if_exists(report_dir / "agent_vs_developer.csv")

    if patch_metrics.empty and agent_vs_dev.empty:
        raise SystemExit("No usable CSV files found.")

    patch_metrics = ensure_numeric(
        patch_metrics,
        [
            "files_changed",
            "source_files_changed",
            "test_files_changed",
            "config_files_changed",
            "loc_added",
            "loc_deleted",
            "loc_churn",
            "num_hunks",
        ],
    )

    patch_metrics = ensure_bool(
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

    agent_vs_dev = ensure_numeric(
        agent_vs_dev,
        [
            "file_overlap_jaccard",
            "extra_files_count",
            "missing_developer_files_count",
            "churn_ratio_vs_developer",
            "hunks_ratio_vs_developer",
        ],
    )

    agent_vs_dev = ensure_bool(
        agent_vs_dev,
        [
            "developer_patch_found",
            "agent_patch_found",
            "same_file_as_developer",
            "same_directory_as_developer",
            "same_top_level_dir_as_developer",
            "agent_added_any_a11y_signal",
            "developer_added_any_a11y_signal",
            "agent_changed_config_not_developer",
            "agent_changed_lockfile_not_developer",
            "agent_changed_generated_not_developer",
            "no_file_overlap_flag",
            "broad_extra_file_flag",
            "large_churn_flag",
            "overmodified_flag",
        ],
    )

    chart_paths: List[Path] = []

    chart_functions = [
        lambda: chart_median_loc_churn_by_source(patch_metrics, out_dir),
        lambda: chart_loc_churn_distribution_by_source(patch_metrics, out_dir),
        lambda: chart_files_changed_distribution_by_source(patch_metrics, out_dir),
        lambda: chart_file_overlap_distribution_by_agent(agent_vs_dev, out_dir),
        lambda: chart_churn_ratio_distribution_by_agent(agent_vs_dev, out_dir),
        lambda: chart_same_file_directory_rates(agent_vs_dev, out_dir),
        lambda: chart_overmodified_rate_by_agent(agent_vs_dev, out_dir),
        lambda: chart_accessibility_signal_rate_by_source(patch_metrics, out_dir),
        lambda: chart_extra_files_distribution_by_agent(agent_vs_dev, out_dir),
        lambda: chart_flagged_patches_by_churn_ratio(agent_vs_dev, out_dir),
    ]

    for fn in chart_functions:
        path = fn()
        if path is not None:
            chart_paths.append(path)

    write_charts_index(out_dir, chart_paths)

    print()
    print("Done.")
    print(f"Charts written to: {out_dir.resolve()}")
    print(f"Open this file to view them together: {out_dir / 'charts_index.md'}")


if __name__ == "__main__":
    main()