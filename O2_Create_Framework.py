import os
import json
import time
import argparse
import tarfile
from pathlib import Path
from tqdm import tqdm

import pandas as pd
import requests


PR_LINK_COLUMN = "PR Link"
MY_GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")


def parse_pr_link(pr_link):
    url_focus = pr_link.replace("https://github.com/", "")
    url_focus_split = url_focus.split("/")
    owner, repo, pr_number = url_focus_split[0], url_focus_split[1], url_focus_split[3]
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


def download_github_archive(owner, repo, commit_sha, target_dir, token=None):
    """
    Downloads a GitHub source archive for a specific commit and extracts it
    into target_dir.

    This avoids creating a .git folder.
    """
    target_dir = Path(target_dir)

    if target_dir.exists() and any(target_dir.iterdir()):
        print(f"Skipping existing non-empty folder: {target_dir}")
        return

    if target_dir.exists():
        target_dir.rmdir()

    target_dir.mkdir(parents=True, exist_ok=True)

    archive_url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{commit_sha}"

    headers = {
        "Accept": "application/vnd.github+json"
    }

    if token:
        headers["Authorization"] = f"Bearer {token}"

    archive_path = target_dir.parent / f"{target_dir.name}_{commit_sha[:8]}.tar.gz"

    print(f"Downloading archive: {owner}/{repo}@{commit_sha[:8]}")

    response = requests.get(archive_url, headers=headers, stream=True)

    if response.status_code != 200:
        raise RuntimeError(
            f"Archive download failed for {archive_url}\n"
            f"Status: {response.status_code}\n"
            f"Response: {response.text[:500]}"
        )

    with open(archive_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)

    with tarfile.open(archive_path, "r:gz") as tar:
        members = tar.getmembers()

        if not members:
            raise RuntimeError(f"Archive is empty: {archive_path}")

        top_folder = members[0].name.split("/")[0]

        for member in members:
            original_name = member.name

            if original_name == top_folder:
                continue

            member.name = original_name.replace(top_folder + "/", "", 1)
            tar.extract(member, target_dir)

    archive_path.unlink()

    print(f"Extracted to: {target_dir}")
# def download_github_archive(owner, repo, commit_sha, target_dir, token=None):
#     """
#     Downloads a GitHub source archive for a specific commit and extracts it
#     into target_dir.

#     This avoids creating a .git folder.
#     """
#     target_dir = Path(target_dir)

#     if target_dir.exists() and any(target_dir.iterdir()):
#         print(f"Skipping existing non-empty folder: {target_dir}")
#         return

#     if target_dir.exists():
#         target_dir.rmdir()

#     target_dir.mkdir(parents=True, exist_ok=True)

#     archive_url = f"https://api.github.com/repos/{owner}/{repo}/tarball/{commit_sha}"

#     headers = {
#         "Accept": "application/vnd.github+json"
#     }

#     if token:
#         headers["Authorization"] = f"Bearer {token}"

#     archive_path = target_dir.parent / f"{target_dir.name}_{commit_sha[:8]}.tar.gz"

#     print(f"Downloading archive: {owner}/{repo}@{commit_sha[:8]}")

#     response = requests.get(archive_url, headers=headers, stream=True)

#     if response.status_code != 200:
#         raise RuntimeError(
#             f"Archive download failed for {archive_url}\n"
#             f"Status: {response.status_code}\n"
#             f"Response: {response.text[:500]}"
#         )

#     with open(archive_path, "wb") as f:
#         for chunk in response.iter_content(chunk_size=1024 * 1024):
#             if chunk:
#                 f.write(chunk)

#     with tarfile.open(archive_path, "r:gz") as tar:
#         members = tar.getmembers()

#         if not members:
#             raise RuntimeError(f"Archive is empty: {archive_path}")

#         top_folder = members[0].name.split("/")[0]

#         for member in members:
#             original_name = member.name

#             if original_name == top_folder:
#                 continue

#             relative_name = original_name.replace(top_folder + "/", "", 1)

#             if owner == "code-dot-org" and repo == "code-dot-org":
#                 if any(part == "sites.v3" for part in Path(relative_name).parts):
#                     continue

#             member.name = relative_name
#             tar.extract(member, target_dir)

#     archive_path.unlink()

#     print(f"Extracted to: {target_dir}")

def create_public_pr_structure(pr_dir):
    """
    LLM-safe PR folder.
    This folder should not contain fixed commits, fixed source code,
    developer patches, or head.sha.
    """
    pr_dir = Path(pr_dir)

    folders = [
        "metadata",
        "buggy",
        "generated/claude",
        "generated/gemini",
        "generated/copilot",
        "prompts",
        "reports",
        "scripts",
        "env",
    ]

    for folder in folders:
        (pr_dir / folder).mkdir(parents=True, exist_ok=True)


def create_private_pr_structure(private_pr_dir):
    """
    Researcher-only PR folder.
    This folder contains fixed code and private metadata.
    Do not expose this folder to LLMs.
    """
    private_pr_dir = Path(private_pr_dir)

    folders = [
        "metadata",
        "fixed",
        "patches",
        "reports",
    ]

    for folder in folders:
        (private_pr_dir / folder).mkdir(parents=True, exist_ok=True)


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="sampled_prs.csv")
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

    for i, row in tqdm(df.iterrows(), total=len(df)):
        pr_link = str(row[PR_LINK_COLUMN]).strip()
        pr_id = row["PR Id"]

        if not pr_link or pr_link == "nan":
            print(f"Skipping row {i}: missing PR Link")
            continue

        print("\n" + "=" * 80)
        print(f"Processing row {i}: {pr_link}")
        print(pr_link, pr_id)

        try:
            owner, repo, pr_number = parse_pr_link(pr_link)
            pr_data = github_api_get_pr(owner, repo, pr_number, github_token)

            repo_key = f"{owner}/{repo}"

            if repo_key not in app_map:
                app_id = f"{owner}_{repo}".lower()
                app_map[repo_key] = app_id
            else:
                app_id = app_map[repo_key]

            pr_folder_name = f"PR_{int(pr_id)}"
            private_pr_folder_name = f"PR_{int(pr_id)}_private"

            app_dir = apps_root / app_id
            issues_dir = app_dir / "issues"

            pr_dir = issues_dir / pr_folder_name
            private_pr_dir = issues_dir / private_pr_folder_name

            create_public_pr_structure(pr_dir)
            create_private_pr_structure(private_pr_dir)

            base_sha = pr_data["base"]["sha"]
            head_sha = pr_data["head"]["sha"]

            base_repo_url = pr_data["base"]["repo"]["clone_url"]
            head_repo_url = (
                pr_data["head"]["repo"]["clone_url"]
                if pr_data["head"]["repo"]
                else base_repo_url
            )

            # ------------------------------------------------------------
            # LLM-SAFE METADATA
            # This file is safe to expose to GPT/Claude/Gemini/Copilot.
            # It does NOT contain head.sha, fixed commit, fixed path,
            # developer patch, or merge commit.
            # ------------------------------------------------------------
            public_metadata = {
                "app_id": app_id,
                "pr_id": int(pr_id),
                "pr_folder": pr_folder_name,
                "csv_row_index": int(i),

                "repo_owner": owner,
                "repo_name": repo,
                "repo_key": repo_key,
                "pr_number": pr_number,
                "pr_link": pr_link,

                "issue_summary": row["Issue Summary"],
                "issue_type": row["Issue type"],
                "user_demographic": row["User Demographic"],
                "issue_title_github": pr_data["title"],

                "buggy_source": "github_tarball_archive",
                "contains_git_history": False,

                "llm_visibility": "safe",
                "notes": "This metadata file is safe for LLM repair agents. It intentionally excludes fixed commit information."
            }

            write_json(pr_dir / "metadata" / "issue.json", public_metadata)

            # ------------------------------------------------------------
            # PRIVATE METADATA
            # This file is for researcher/evaluation only.
            # Do NOT expose this to LLM repair agents.
            # ------------------------------------------------------------
            private_metadata = {
                "app_id": app_id,
                "pr_id": int(pr_id),
                "pr_folder": pr_folder_name,
                "private_pr_folder": private_pr_folder_name,
                "csv_row_index": int(i),

                "repo_owner": owner,
                "repo_name": repo,
                "repo_key": repo_key,
                "pr_number": pr_number,
                "pr_link": pr_link,
                "pr_api_url": pr_data["url"],
                "pr_database_id": pr_data["id"],

                "issue_summary": row["Issue Summary"],
                "issue_type": row["Issue type"],
                "user_demographic": row["User Demographic"],
                "issue_title_github": pr_data["title"],

                "buggy_commit_base_sha": base_sha,
                "fixed_commit_head_sha": head_sha,

                "base_repo_url": base_repo_url,
                "head_repo_url": head_repo_url,

                "merged": pr_data["merged"],
                "merge_commit_sha": pr_data["merge_commit_sha"],
                "state": pr_data["state"],

                "checkout_method": "github_tarball_archive",
                "contains_git_history": False,

                "llm_visibility": "private",
                "notes": "This metadata file contains fixed commit information and must not be exposed to LLM repair agents."
            }

            write_json(private_pr_dir / "metadata" / "issue_private.json", private_metadata)

            app_metadata = {
                "app_id": app_id,
                "repo_owner": owner,
                "repo_name": repo,
                "repo_key": repo_key,
                "repo_url": base_repo_url,
            }

            write_json(app_dir / "metadata" / "app.json", app_metadata)

            # Download buggy version into the LLM-safe PR folder.
            download_github_archive(
                owner=owner,
                repo=repo,
                commit_sha=base_sha,
                target_dir=pr_dir / "buggy",
                token=github_token,
            )

            # Download fixed version only into the private PR folder.
            download_github_archive(
                owner=owner,
                repo=repo,
                commit_sha=head_sha,
                target_dir=private_pr_dir / "fixed",
                token=github_token,
            )

            summary_rows.append({
                "app_id": app_id,
                "pr_id": int(pr_id),
                "pr_folder": pr_folder_name,
                "private_pr_folder": private_pr_folder_name,
                "repo": repo_key,
                "pr_number": pr_number,
                "pr_link": pr_link,
                "buggy_commit": base_sha,
                "fixed_commit_private": head_sha,
                "checkout_method": "github_tarball_archive",
                "status": "success",
            })

            time.sleep(args.sleep)

        except Exception as e:
            print(f"ERROR on row {i}: {e}")

            summary_rows.append({
                "app_id": "",
                "pr_id": int(pr_id),
                "pr_folder": f"PR_{int(pr_id)}",
                "private_pr_folder": f"PR_{int(pr_id)}_private",
                "repo": "",
                "pr_number": "",
                "pr_link": pr_link,
                "buggy_commit": "",
                "fixed_commit_private": "",
                "checkout_method": "github_tarball_archive",
                "status": f"error: {e}",
            })

    summary_df = pd.DataFrame(summary_rows)
    summary_path = root / "setup_summary_private.csv"
    summary_df.to_csv(summary_path, index=False)

    print("\nDone.")
    print(f"Summary written to: {summary_path}")


if __name__ == "__main__":
    main()