import os
import re
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime

from openai import OpenAI
import anthropic


IGNORE_DIRS = {
    ".git", "node_modules", "dist", "build", ".next", ".nuxt",
    "coverage", ".gradle", "target", "__pycache__", ".venv",
    "venv", ".idea", ".vscode"
}

IGNORE_EXTS = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".jar", ".class", ".lock",
    ".mp4", ".mov", ".avi", ".woff", ".woff2", ".ttf", ".eot"
}

MAX_FILE_CHARS = 30000
MAX_SELECTED_FILES = 12


def run(cmd, cwd=None, capture=False):
    if capture:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
        )
        return result.returncode, result.stdout

    subprocess.run(cmd, cwd=cwd, check=True)


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def copy_buggy_to_attempt(buggy_dir, attempt_dir, overwrite=False):
    buggy_dir = Path(buggy_dir)
    attempt_dir = Path(attempt_dir)

    if attempt_dir.exists():
        if overwrite:
            shutil.rmtree(attempt_dir)
        else:
            raise RuntimeError(f"Attempt folder already exists: {attempt_dir}")

    shutil.copytree(
        buggy_dir,
        attempt_dir,
        ignore=shutil.ignore_patterns(
            ".git", "node_modules", "dist", "build", ".gradle", "target", "__pycache__"
        )
    )


def should_include_file(path):
    path = Path(path)

    if any(part in IGNORE_DIRS for part in path.parts):
        return False

    if path.suffix.lower() in IGNORE_EXTS:
        return False

    return True


def build_project_file_map(project_dir):
    project_dir = Path(project_dir)
    paths = []

    for path in project_dir.rglob("*"):
        if path.is_file() and should_include_file(path.relative_to(project_dir)):
            rel = path.relative_to(project_dir)
            paths.append(str(rel))

    return sorted(paths)


def read_selected_files(project_dir, selected_files):
    project_dir = Path(project_dir)
    contents = {}

    for rel_path in selected_files:
        path = project_dir / rel_path

        if not path.exists() or not path.is_file():
            continue

        if not should_include_file(path.relative_to(project_dir)):
            continue

        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            contents[rel_path] = f"[Could not read file: {e}]"
            continue

        if len(text) > MAX_FILE_CHARS:
            text = text[:MAX_FILE_CHARS] + "\n\n[TRUNCATED]\n"

        contents[rel_path] = text

    return contents


def extract_json_array(text):
    """
    Extracts a JSON array from model output.
    Expected output example:
    ["src/Button.jsx", "src/Dialog.tsx"]
    """
    text = text.strip()

    fenced = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    match = re.search(r"\[.*\]", text, re.DOTALL)
    if not match:
        raise RuntimeError(f"Could not find JSON array in response:\n{text}")

    return json.loads(match.group(0))


def extract_unified_diff(text):
    """
    Extracts unified diff from model output.
    """
    text = text.strip()

    fenced = re.search(r"```(?:diff|patch)?\s*(.*?)```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    diff_start = text.find("diff --git")
    if diff_start != -1:
        return text[diff_start:].strip() + "\n"

    diff_start = text.find("--- ")
    if diff_start != -1:
        return text[diff_start:].strip() + "\n"

    raise RuntimeError("Could not find a unified diff in the model response.")


def init_git_repo(project_dir):
    """
    The source snapshots do not contain .git.
    We create a temporary local git repo inside the attempt folder so that
    git apply and git diff can be used.
    """
    project_dir = Path(project_dir)

    run(["git", "init"], cwd=project_dir)
    run(["git", "config", "user.email", "repair-benchmark@example.com"], cwd=project_dir)
    run(["git", "config", "user.name", "Repair Benchmark"], cwd=project_dir)
    run(["git", "add", "."], cwd=project_dir)
    run(["git", "commit", "-m", "initial buggy snapshot"], cwd=project_dir)


def apply_patch(project_dir, patch_text, patch_path):
    write_text(patch_path, patch_text)

    code, output = run(
        ["git", "apply", "--whitespace=fix", str(patch_path)],
        cwd=project_dir,
        capture=True,
    )

    return code, output


def create_patch_from_attempt(project_dir):
    code, output = run(["git", "diff"], cwd=project_dir, capture=True)
    return output


def make_file_selection_prompt(metadata, file_map):
    issue_title = metadata.get("issue_title_github", "")
    issue_summary = metadata.get("issue_summary", "")
    issue_type = metadata.get("issue_type", "")
    user_demo = metadata.get("user_demographic", "")

    files_text = "\n".join(file_map)

    return f"""
You are helping repair an accessibility bug in a software project.

You may only use the issue information and file paths provided here.

Issue title:
{issue_title}

Issue summary:
{issue_summary}

Issue type:
{issue_type}

Affected user demographic:
{user_demo}

Project file paths:
{files_text}

Task:
Choose the files that are most likely relevant to fixing this accessibility issue.

Return only a JSON array of file paths.
Do not include explanation.
Select at most {MAX_SELECTED_FILES} files.
""".strip()


def make_patch_prompt(metadata, selected_file_contents):
    issue_title = metadata.get("issue_title_github", "")
    issue_summary = metadata.get("issue_summary", "")
    issue_type = metadata.get("issue_type", "")
    user_demo = metadata.get("user_demographic", "")

    file_blocks = []

    for rel_path, content in selected_file_contents.items():
        file_blocks.append(
            f"""
FILE: {rel_path}
{content}
""".strip()
        )

    files_text = "\n\n".join(file_blocks)

    return f"""
You are repairing an accessibility issue in a buggy software project.

Use only the issue information and source files provided below.

Issue title:
{issue_title}

Issue summary:
{issue_summary}

Issue type:
{issue_type}

Affected user demographic:
{user_demo}

Relevant source files:
{files_text}

Task:
Create the smallest reasonable code change that fixes the accessibility issue.

Output requirements:
- Return only a unified diff patch.
- Do not include markdown explanation.
- Do not include prose before or after the patch.
- The patch must apply to the current project root.
""".strip()


def call_openai(prompt, model):
    client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

    response = client.responses.create(
        model=model,
        input=prompt,
    )

    return response.output_text


def call_claude(prompt, model):
    client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

    response = client.messages.create(
        model=model,
        max_tokens=12000,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )

    return "\n".join(
        block.text for block in response.content
        if getattr(block, "type", None) == "text"
    )


def call_model(model_name, prompt, openai_model, claude_model):
    if model_name == "gpt":
        return call_openai(prompt, openai_model)

    if model_name == "claude":
        return call_claude(prompt, claude_model)

    raise ValueError(f"Unsupported model name: {model_name}")


def run_one_model(pr_dir, model_name, attempt_name, openai_model, claude_model, overwrite=False):
    pr_dir = Path(pr_dir)

    if pr_dir.name.endswith("_private"):
        raise RuntimeError("Refusing to run on a private PR folder.")

    private_sibling = pr_dir.parent / f"{pr_dir.name}_private"

    metadata_path = pr_dir / "metadata" / "issue.json"
    buggy_dir = pr_dir / "buggy"
    attempt_dir = pr_dir / "generated" / model_name / attempt_name
    prompts_dir = pr_dir / "prompts"
    reports_dir = pr_dir / "reports"

    if private_sibling.exists():
        print(f"Private folder exists but will not be read: {private_sibling}")

    metadata = read_json(metadata_path)

    forbidden_keys = [
        "fixed_commit",
        "fixed_commit_head_sha",
        "head_sha",
        "developer_patch",
        "code_change_summary",
        "detailed_code_change",
    ]

    for key in forbidden_keys:
        if key in metadata:
            raise RuntimeError(
                f"LLM-safe metadata contains forbidden key: {key}. "
                f"Move it to the private folder before running."
            )

    copy_buggy_to_attempt(buggy_dir, attempt_dir, overwrite=overwrite)
    init_git_repo(attempt_dir)

    file_map = build_project_file_map(attempt_dir)
    write_text(reports_dir / f"{model_name}_{attempt_name}_file_map.txt", "\n".join(file_map))

    selection_prompt = make_file_selection_prompt(metadata, file_map)
    write_text(prompts_dir / f"{model_name}_{attempt_name}_select_files_prompt.txt", selection_prompt)

    selection_response = call_model(model_name, selection_prompt, openai_model, claude_model)
    write_text(reports_dir / f"{model_name}_{attempt_name}_select_files_response.txt", selection_response)

    selected_files = extract_json_array(selection_response)
    selected_files = selected_files[:MAX_SELECTED_FILES]

    selected_file_contents = read_selected_files(attempt_dir, selected_files)
    write_text(
        reports_dir / f"{model_name}_{attempt_name}_selected_files.json",
        json.dumps(list(selected_file_contents.keys()), indent=2),
    )

    patch_prompt = make_patch_prompt(metadata, selected_file_contents)
    write_text(prompts_dir / f"{model_name}_{attempt_name}_patch_prompt.txt", patch_prompt)

    patch_response = call_model(model_name, patch_prompt, openai_model, claude_model)
    write_text(reports_dir / f"{model_name}_{attempt_name}_raw_patch_response.txt", patch_response)

    try:
        patch_text = extract_unified_diff(patch_response)
    except Exception as e:
        write_text(
            reports_dir / f"{model_name}_{attempt_name}_error.txt",
            f"Patch extraction failed:\n{e}\n\nRaw response:\n{patch_response}",
        )
        raise

    proposed_patch_path = pr_dir / "generated" / model_name / f"{attempt_name}_proposed.patch"
    apply_code, apply_output = apply_patch(attempt_dir, patch_text, proposed_patch_path)

    write_text(reports_dir / f"{model_name}_{attempt_name}_apply_patch_output.txt", apply_output)

    if apply_code != 0:
        write_text(
            reports_dir / f"{model_name}_{attempt_name}_status.json",
            json.dumps({
                "model": model_name,
                "attempt": attempt_name,
                "status": "patch_apply_failed",
                "timestamp": datetime.now().isoformat(),
                "attempt_dir": str(attempt_dir),
                "proposed_patch": str(proposed_patch_path),
            }, indent=2),
        )
        return

    final_patch = create_patch_from_attempt(attempt_dir)
    final_patch_path = pr_dir / "generated" / model_name / f"{attempt_name}_final.patch"
    write_text(final_patch_path, final_patch)

    code, changed_files = run(
        ["git", "diff", "--name-only"],
        cwd=attempt_dir,
        capture=True,
    )

    write_text(
        reports_dir / f"{model_name}_{attempt_name}_status.json",
        json.dumps({
            "model": model_name,
            "attempt": attempt_name,
            "status": "success",
            "timestamp": datetime.now().isoformat(),
            "attempt_dir": str(attempt_dir),
            "selected_files": list(selected_file_contents.keys()),
            "changed_files": changed_files.strip().splitlines(),
            "proposed_patch": str(proposed_patch_path),
            "final_patch": str(final_patch_path),
        }, indent=2),
    )

    print(f"{model_name} {attempt_name} completed successfully.")
    print(f"Final patch: {final_patch_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--pr",
        required=True,
        help="Path to the public PR folder, e.g., repair-benchmark/apps/x/issues/PR_123",
    )
    parser.add_argument(
        "--models",
        nargs="+",
        default=["gpt", "claude"],
        choices=["gpt", "claude"],
    )
    parser.add_argument("--attempt", default="attempt_001")
    parser.add_argument("--openai-model", default="gpt-5.1")
    parser.add_argument("--claude-model", default="claude-sonnet-4-5-20250929")
    parser.add_argument("--overwrite", action="store_true")

    args = parser.parse_args()

    if "gpt" in args.models and not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")

    if "claude" in args.models and not os.environ.get("ANTHROPIC_API_KEY"):
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")

    pr_dir = Path(args.pr)

    for model_name in args.models:
        run_one_model(
            pr_dir=pr_dir,
            model_name=model_name,
            attempt_name=args.attempt,
            openai_model=args.openai_model,
            claude_model=args.claude_model,
            overwrite=args.overwrite,
        )


if __name__ == "__main__":
    main()