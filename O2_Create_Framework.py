import os
import json
import time
import shutil
import argparse
import subprocess
from pathlib import Path

import pandas as pd
import requests
from tqdm import tqdm


PR_LINK_COLUMN = "PR Link"
MY_GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


# ─────────────────────────────────────────────────────────────────────────────
# GitHub / PR helpers
# ─────────────────────────────────────────────────────────────────────────────

def parse_pr_link(pr_link: str) -> tuple[str, str, str]:
    """Return (owner, repo, pr_number) from a GitHub PR URL."""
    parts = pr_link.replace("https://github.com/", "").split("/")
    owner, repo, pr_number = parts[0], parts[1], parts[3]
    return owner, repo, pr_number


def github_api_get_pr(owner: str, repo: str, pr_number: str, token: str | None = None) -> dict:
    """Fetch PR metadata from the GitHub REST API."""
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(api_url, headers=headers)
    if response.status_code != 200:
        raise RuntimeError(
            f"GitHub API failed for {api_url}\n"
            f"Status: {response.status_code}\n"
            f"Response: {response.text[:500]}"
        )
    return response.json()


# ─────────────────────────────────────────────────────────────────────────────
# Core: clone + checkout PR head for fixed version, then reverse-apply the diff for buggy version
# ─────────────────────────────────────────────────────────────────────────────

def _run(cmd: list[str], cwd: Path | None = None) -> None:
    """Run a shell command, raising on non-zero exit."""
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed: {' '.join(cmd)}\n"
            f"stdout: {result.stdout[:500]}\n"
            f"stderr: {result.stderr[:500]}"
        )


def _fetch_pr_diff(owner: str, repo: str, pr_number: str, token: str | None = None) -> bytes:
    """
    Download the unified diff for a pull request.
    Returns raw bytes suitable for piping into `git apply`.
    """
    diff_url = f"https://github.com/{owner}/{repo}/pull/{pr_number}.diff"
    headers = {"Accept": "application/vnd.github.v3.diff"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    response = requests.get(diff_url, headers=headers, allow_redirects=True)
    if response.status_code != 200:
        raise RuntimeError(
            f"Diff download failed: {diff_url}\n"
            f"Status: {response.status_code}"
        )
    return response.content


def checkout_pr_version(
    owner: str,
    repo: str,
    pr_number: str,
    target_dir: Path,
    mode: str,          # "fix" | "bug"
    token: str | None = None,
) -> None:
    """
    Checkout a PR version into a target directory.
        fix  →  clone + checkout PR head  (the merged/proposed state)
        bug  →  same, then `git apply -R` the PR diff to revert to pre-fix state

    Parameters
    ----------
    mode : "fix" | "bug"
    """
    if mode not in ("fix", "bug"):
        raise ValueError(f"mode must be 'fix' or 'bug', got {mode!r}")

    target_dir = Path(target_dir)

    if target_dir.exists() and any(target_dir.iterdir()):
        print(f"  Skipping existing non-empty folder: {target_dir}")
        return

    target_dir.mkdir(parents=True, exist_ok=True)

    clone_url = f"https://github.com/{owner}/{repo}.git"
    pr_ref    = f"pull/{pr_number}/head"
    branch    = f"pr-{pr_number}"

    print(f"  Cloning {owner}/{repo} …")
    _run(["git", "clone", clone_url, "."], cwd=target_dir)

    print(f"  Fetching {pr_ref} → {branch} …")
    _run(["git", "fetch", "origin", f"{pr_ref}:{branch}"], cwd=target_dir)

    _run(["git", "checkout", branch], cwd=target_dir)
    print(f"  Checked out PR head ({branch})")

    if mode == "bug":
        print(f"  Fetching diff for PR #{pr_number} …")
        diff_bytes = _fetch_pr_diff(owner, repo, pr_number, token)

        # Write diff to a temp file so we avoid any stdin buffering issues
        diff_file = target_dir.parent / f"pr_{pr_number}.diff"
        diff_file.write_bytes(diff_bytes)

        try:
            print(f"  Reverse-applying diff (git apply -R) …")
            _run(
                ["git", "apply", "-R", "--whitespace=nowarn", str(diff_file)],
                cwd=target_dir,
            )
        finally:
            diff_file.unlink(missing_ok=True)

        print(f"  Buggy version ready: {target_dir}")
    else:
        print(f"  Fixed version ready: {target_dir}")

    # Remove .git to keep the benchmark folder clean (no history needed)
    git_dir = target_dir / ".git"
    if git_dir.exists():
        shutil.rmtree(git_dir)
        print(f"  Removed .git from {target_dir}")


# ─────────────────────────────────────────────────────────────────────────────
# Folder structure helpers
# ─────────────────────────────────────────────────────────────────────────────

def create_public_pr_structure(pr_dir: Path) -> None:
    """
    LLM-safe PR folder.
    Must NOT contain fixed commits, fixed source code, developer patches,
    or head SHA.
    """
    for folder in [
        "metadata",
        "buggy",
        "generated/claude",
        "generated/gemini",
        "generated/codex",
        "prompts",
        "reports",
        "scripts",
        "env",
    ]:
        (pr_dir / folder).mkdir(parents=True, exist_ok=True)


def create_private_pr_structure(private_pr_dir: Path) -> None:
    """
    Researcher-only PR folder.
    Contains fixed code and private metadata.
    Do NOT expose to LLM repair agents.
    """
    for folder in ["metadata", "fixed", "patches", "reports"]:
        (private_pr_dir / folder).mkdir(parents=True, exist_ok=True)


def write_json(path: Path, data: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv",   default="sampled_prs.csv")
    parser.add_argument("--out",   default="repair-benchmark")
    parser.add_argument("--sleep", type=float, default=1.0,
                        help="Seconds to sleep between PRs (be kind to GitHub)")
    args = parser.parse_args()

    github_token = os.environ.get("GITHUB_TOKEN")

    df = pd.read_csv(args.csv)
    if PR_LINK_COLUMN not in df.columns:
        raise ValueError(f"CSV must contain column: {PR_LINK_COLUMN}")

    root      = Path(args.out)
    apps_root = root / "apps"
    apps_root.mkdir(parents=True, exist_ok=True)

    app_map      = {}   # "owner/repo" → app_id
    summary_rows = []

    for i, row in tqdm(df.iterrows(), total=len(df)):
        pr_link = str(row[PR_LINK_COLUMN]).strip()
        pr_id   = row["PR Id"]

        if not pr_link or pr_link == "nan":
            print(f"Skipping row {i}: missing PR Link")
            continue

        print("\n" + "=" * 80)
        print(f"Processing row {i}: {pr_link}")

        try:
            owner, repo, pr_number = parse_pr_link(pr_link)
            pr_data = github_api_get_pr(owner, repo, pr_number, github_token)

            repo_key = f"{owner}/{repo}"
            if repo_key not in app_map:
                app_map[repo_key] = f"{owner}_{repo}".lower()
            app_id = app_map[repo_key]

            pr_folder_name         = f"PR_{int(pr_id)}"
            private_pr_folder_name = f"PR_{int(pr_id)}_private"

            app_dir    = apps_root / app_id
            issues_dir = app_dir / "issues"

            pr_dir         = issues_dir / pr_folder_name
            private_pr_dir = issues_dir / private_pr_folder_name

            create_public_pr_structure(pr_dir)
            create_private_pr_structure(private_pr_dir)

            # ------------------------------------------------------------------
            # Commit SHAs — kept in private metadata only; the public folder
            # never sees head_sha (the fixed commit).
            # ------------------------------------------------------------------
            base_sha = pr_data["base"]["sha"]
            head_sha = pr_data["head"]["sha"]

            base_repo_url = pr_data["base"]["repo"]["clone_url"]
            head_repo_url = (
                pr_data["head"]["repo"]["clone_url"]
                if pr_data["head"]["repo"]
                else base_repo_url
            )

            # ── LLM-safe metadata ──────────────────────────────────────────
            public_metadata = {
                "app_id":           app_id,
                "pr_id":            int(pr_id),
                "pr_folder":        pr_folder_name,
                "csv_row_index":    int(i),

                "repo_owner":       owner,
                "repo_name":        repo,
                "repo_key":         repo_key,
                "pr_number":        pr_number,
                "pr_link":          pr_link,

                "issue_summary":    row["Issue Summary"],
                "issue_type":       row["Issue type"],
                "user_demographic": row["User Demographic"],
                "issue_title_github": pr_data["title"],

                "buggy_source":          "git_reverse_diff",
                "fixed_source":          "git_pr_head",
                "contains_git_history":  False,

                "llm_visibility": "safe",
                "notes": (
                    "Buggy version produced by cloning the repo, checking out the "
                    "PR head, then reverse-applying the PR diff (git apply -R). "
                    "Fixed version is the PR head state. "
                    "This metadata intentionally excludes fixed-commit information."
                ),
            }
            write_json(pr_dir / "metadata" / "issue.json", public_metadata)

            # ── Private (researcher-only) metadata ─────────────────────────
            private_metadata = {
                "app_id":               app_id,
                "pr_id":                int(pr_id),
                "pr_folder":            pr_folder_name,
                "private_pr_folder":    private_pr_folder_name,
                "csv_row_index":        int(i),

                "repo_owner":           owner,
                "repo_name":            repo,
                "repo_key":             repo_key,
                "pr_number":            pr_number,
                "pr_link":              pr_link,
                "pr_api_url":           pr_data["url"],
                "pr_database_id":       pr_data["id"],

                "issue_summary":        row["Issue Summary"],
                "issue_type":           row["Issue type"],
                "user_demographic":     row["User Demographic"],
                "issue_title_github":   pr_data["title"],

                "buggy_commit_base_sha":  base_sha,
                "fixed_commit_head_sha":  head_sha,
                "pr_diff_url":           f"https://github.com/{owner}/{repo}/pull/{pr_number}.diff",

                "base_repo_url":        base_repo_url,
                "head_repo_url":        head_repo_url,

                "merged":               pr_data["merged"],
                "merge_commit_sha":     pr_data["merge_commit_sha"],
                "state":                pr_data["state"],

                "checkout_method":      "git_pr_head_plus_reverse_diff",
                "contains_git_history": False,

                "llm_visibility": "private",
                "notes": (
                    "Contains fixed-commit SHA and diff URL. "
                    "Must NOT be exposed to LLM repair agents."
                ),
            }
            write_json(private_pr_dir / "metadata" / "issue_private.json", private_metadata)

            # ── App-level metadata ─────────────────────────────────────────
            write_json(app_dir / "metadata" / "app.json", {
                "app_id":     app_id,
                "repo_owner": owner,
                "repo_name":  repo,
                "repo_key":   repo_key,
                "repo_url":   base_repo_url,
            })

            # ── Checkout: buggy (LLM-safe) ─────────────────────────────────
            # Clone PR head, reverse-apply the diff → pre-fix state.
            checkout_pr_version(
                owner=owner, repo=repo, pr_number=pr_number,
                target_dir=pr_dir / "buggy",
                mode="bug",
                token=github_token,
            )

            # ── Checkout: fixed (private) ──────────────────────────────────
            # Clone PR head → already the fixed state.
            checkout_pr_version(
                owner=owner, repo=repo, pr_number=pr_number,
                target_dir=private_pr_dir / "fixed",
                mode="fix",
                token=github_token,
            )

            summary_rows.append({
                "app_id":               app_id,
                "pr_id":                int(pr_id),
                "pr_folder":            pr_folder_name,
                "private_pr_folder":    private_pr_folder_name,
                "repo":                 repo_key,
                "pr_number":            pr_number,
                "pr_link":              pr_link,
                "buggy_commit":         base_sha,
                "fixed_commit_private": head_sha,
                "checkout_method":      "git_pr_head_plus_reverse_diff",
                "status":               "success",
            })

            time.sleep(args.sleep)

        except Exception as e:
            print(f"ERROR on row {i}: {e}")
            summary_rows.append({
                "app_id":               "",
                "pr_id":                int(pr_id),
                "pr_folder":            f"PR_{int(pr_id)}",
                "private_pr_folder":    f"PR_{int(pr_id)}_private",
                "repo":                 "",
                "pr_number":            "",
                "pr_link":              pr_link,
                "buggy_commit":         "",
                "fixed_commit_private": "",
                "checkout_method":      "git_pr_head_plus_reverse_diff",
                "status":               f"error: {e}",
            })

    summary_df   = pd.DataFrame(summary_rows)
    summary_path = root / "setup_summary_private.csv"
    summary_df.to_csv(summary_path, index=False)

    print("\nDone.")
    print(f"Summary written to: {summary_path}")


if __name__ == "__main__":
    main()