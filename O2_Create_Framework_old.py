import os
import re
import json
import time
import argparse
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import pandas as pd
import requests


PR_LINK_COLUMN = "PR Link"


def run(cmd, cwd=None):
    print(f"\n$ {' '.join(cmd)}")
    subprocess.run(cmd, cwd=cwd, check=True)


def safe_name(text):
    text = str(text).strip()
    text = re.sub(r"[^a-zA-Z0-9._-]+", "_", text)
    return text.strip("_").lower()


def parse_pr_link(pr_link):
    """
    Example:
    https://github.com/nextcloud/spreed/pull/8973

    Returns:
    owner = nextcloud
    repo = spreed
    pr_number = 8973
    """
    parsed = urlparse(pr_link)
    parts = parsed.path.strip("/").split("/")

    if len(parts) < 4 or parts[2] != "pull":
        raise ValueError(f"Invalid GitHub PR link: {pr_link}")

    owner = parts[0]
    repo = parts[1]
    pr_number = parts[3]

    return owner, repo, pr_number


def github_api_get_pr(owner, repo, pr_number, token=None):
    api_url = f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}"

    headers = {
        "Accept": "application/vnd.github+json"
    }

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


def clone_and_checkout(repo_url, target_dir, commit_sha):
    target_dir = Path(target_dir)

    if (target_dir / ".git").exists():
        print(f"Existing git repo found: {target_dir}")
    else:
        if target_dir.exists() and any(target_dir.iterdir()):
            raise RuntimeError(f"Target directory exists and is not empty: {target_dir}")

        if target_dir.exists():
            target_dir.rmdir()

        run(["git", "clone", repo_url, str(target_dir)])

    run(["git", "checkout", commit_sha], cwd=target_dir)


def create_issue_structure(issue_dir):
    issue_dir = Path(issue_dir)

    folders = [
        "metadata",
        "buggy",
        "fixed",
        "generated/claude",
        "generated/gemini",
        "generated/copilot",
        "prompts",
        "reports",
        "scripts",
        "env",
    ]

    for folder in folders:
        (issue_dir / folder).mkdir(parents=True, exist_ok=True)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="sampled_master.csv")
    parser.add_argument("--out", default="repair-benchmark")
    parser.add_argument("--sleep", type=float, default=0.5)
    args = parser.parse_args()

    github_token = os.environ.get("GITHUB_TOKEN")

    df = pd.read_csv(args.csv)

    if PR_LINK_COLUMN not in df.columns:
        raise ValueError(f"CSV must contain column: {PR_LINK_COLUMN}")

    root = Path(args.out)
    apps_root = root / "apps"
    apps_root.mkdir(parents=True, exist_ok=True)

    app_map = {}
    summary_rows = []

    for i, row in df.iterrows():
        pr_link = str(row[PR_LINK_COLUMN]).strip()

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
                app_id = safe_name(f"{owner}_{repo}")
                app_map[repo_key] = app_id
            else:
                app_id = app_map[repo_key]

            issue_id = f"issue_{i + 1:03d}"

            app_dir = apps_root / app_id
            issue_dir = app_dir / "issues" / issue_id

            create_issue_structure(issue_dir)

            base_sha = pr_data["base"]["sha"]
            head_sha = pr_data["head"]["sha"]

            base_repo_url = pr_data["base"]["repo"]["clone_url"]
            head_repo_url = pr_data["head"]["repo"]["clone_url"] if pr_data["head"]["repo"] else base_repo_url

            metadata = {
                "app_id": app_id,
                "issue_id": issue_id,
                "csv_row_index": int(i),
                "repo_owner": owner,
                "repo_name": repo,
                "repo_key": repo_key,
                "pr_number": pr_number,
                "pr_link": pr_link,
                "pr_api_url": pr_data["url"],
                "pr_database_id": pr_data["id"],
                "issue_title": pr_data["title"],
                "buggy_commit_base_sha": base_sha,
                "fixed_commit_head_sha": head_sha,
                "base_repo_url": base_repo_url,
                "head_repo_url": head_repo_url,
                "merged": pr_data["merged"],
                "merge_commit_sha": pr_data["merge_commit_sha"],
                "state": pr_data["state"],
            }

            write_json(issue_dir / "metadata" / "issue.json", metadata)

            app_metadata = {
                "app_id": app_id,
                "repo_owner": owner,
                "repo_name": repo,
                "repo_key": repo_key,
                "repo_url": base_repo_url,
            }

            write_json(app_dir / "metadata" / "app.json", app_metadata)

            clone_and_checkout(
                repo_url=base_repo_url,
                target_dir=issue_dir / "buggy",
                commit_sha=base_sha,
            )

            clone_and_checkout(
                repo_url=head_repo_url,
                target_dir=issue_dir / "fixed",
                commit_sha=head_sha,
            )

            summary_rows.append({
                "app_id": app_id,
                "issue_id": issue_id,
                "repo": repo_key,
                "pr_number": pr_number,
                "pr_link": pr_link,
                "buggy_commit": base_sha,
                "fixed_commit": head_sha,
                "status": "success",
            })

            time.sleep(args.sleep)

        except Exception as e:
            print(f"ERROR on row {i}: {e}")

            summary_rows.append({
                "app_id": "",
                "issue_id": f"issue_{i + 1:03d}",
                "repo": "",
                "pr_number": "",
                "pr_link": pr_link,
                "buggy_commit": "",
                "fixed_commit": "",
                "status": f"error: {e}",
            })

    summary_df = pd.DataFrame(summary_rows)
    summary_path = root / "setup_summary.csv"
    summary_df.to_csv(summary_path, index=False)

    print("\nDone.")
    print(f"Summary written to: {summary_path}")


if __name__ == "__main__":
    main()