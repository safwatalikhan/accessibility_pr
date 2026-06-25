import os
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
import time

IGNORE_COPY_PATTERNS = [
    ".git",
    "node_modules",
    "dist",
    "build",
    ".gradle",
    "target",
    "__pycache__",
    ".venv",
    "venv",
]


FORBIDDEN_METADATA_KEYS = [
    "fixed_commit",
    "fixed_commit_head_sha",
    "head_sha",
    "developer_patch",
    "code_change_summary",
    "detailed_code_change",
    "fixed_path",
    "fixed_folder",
    "human_fix",
]


def run(cmd, cwd=None, capture=False, timeout=None):
    print(f"\n$ {' '.join(cmd)}")

    if capture:
        result = subprocess.run(
            cmd,
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=timeout,
        )
        return result.returncode, result.stdout

    subprocess.run(cmd, cwd=cwd, check=True, timeout=timeout)


def read_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def write_text(path, text):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def ensure_public_pr_dir(pr_dir):
    pr_dir = Path(pr_dir).resolve()

    for part in pr_dir.parts:
        if part.endswith("_private"):
            raise RuntimeError(f"Refusing to use private path: {pr_dir}")

    if pr_dir.name.endswith("_private"):
        raise RuntimeError(f"Refusing to run on private PR folder: {pr_dir}")

    private_sibling = pr_dir.parent / f"{pr_dir.name}_private"
    if private_sibling.exists():
        print(f"Private sibling exists but will not be read: {private_sibling}")

    return pr_dir


def validate_safe_metadata(metadata):
    for key in FORBIDDEN_METADATA_KEYS:
        if key in metadata:
            raise RuntimeError(
                f"LLM-safe metadata contains forbidden key: {key}. "
                f"Move this information to the _private folder."
            )
def make_timestamp_attempt_name():
    return "attempt_" + datetime.now().strftime("%Y%m%d_%H%M%S")

def copy_buggy_to_attempt(buggy_dir, attempt_dir, overwrite=False):
    buggy_dir = Path(buggy_dir)
    attempt_dir = Path(attempt_dir)

    if not buggy_dir.exists():
        raise RuntimeError(f"Missing buggy folder: {buggy_dir}")

    if attempt_dir.exists():
        if overwrite:
            shutil.rmtree(attempt_dir)
        else:
            raise RuntimeError(
                f"Attempt folder already exists: {attempt_dir}\n"
                f"Use --overwrite if you want to replace it."
            )

    shutil.copytree(
        buggy_dir,
        attempt_dir,
        ignore=shutil.ignore_patterns(*IGNORE_COPY_PATTERNS),
    )


def init_git_repo(project_dir):
    """
    Source snapshots do not contain .git.
    We create a local git repo in the attempt folder so we can capture the agent's patch.
    """
    project_dir = Path(project_dir)

    run(["git", "init"], cwd=project_dir)
    run(["git", "config", "user.email", "repair-benchmark@example.com"], cwd=project_dir)
    run(["git", "config", "user.name", "Repair Benchmark"], cwd=project_dir)
    run(["git", "add", "."], cwd=project_dir)

    code, output = run(["git", "commit", "-m", "initial buggy snapshot"], cwd=project_dir, capture=True)

    if code != 0:
        # If there are no files or commit fails, save the output for debugging.
        raise RuntimeError(f"Initial git commit failed:\n{output}")


def create_patch_from_attempt(project_dir):
    code, output = run(["git", "diff", "--binary"], cwd=project_dir, capture=True)
    return output


def get_changed_files(project_dir):
    code, output = run(["git", "diff", "--name-only"], cwd=project_dir, capture=True)
    if code != 0:
        return []
    return [line.strip() for line in output.splitlines() if line.strip()]


def make_agent_instruction(metadata, agent_name):
    issue_title = metadata.get("issue_title_github", "")
    issue_summary = metadata.get("issue_summary", "")
    issue_type = metadata.get("issue_type", "")
    user_demo = metadata.get("user_demographic", "")
    pr_link = metadata.get("pr_link", "")

    return f"""
# Accessibility Repair Task

You are working inside a buggy software project.

Your task is to find and fix the accessibility issue described below with the smallest reasonable code change.

## Issue Information

GitHub PR link:
{pr_link}

Issue title:
{issue_title}

Issue summary:
{issue_summary}

Issue type:
{issue_type}

Affected user demographic:
{user_demo}

## Rules

- Work only inside the current project folder.
- Inspect the codebase yourself to find the relevant files.
- Make the smallest reasonable code change that fixes the accessibility issue.
- Preserve existing behavior unless the accessibility fix requires a change.
- Do not rewrite unrelated code.
- Do not create a new project.
- Do not delete unrelated files.
- Do not modify dependency lockfiles unless absolutely necessary.
- Do not use external information about the human developer's fix.
- When done, leave the modified files in this working directory.

## Expected Result

The final output should be a modified project folder containing your proposed repair.
A separate script will collect the patch using git diff after you finish.
""".strip()


def prepare_attempt(pr_dir, model_name, attempt_name, overwrite=False):
    pr_dir = ensure_public_pr_dir(pr_dir)

    metadata_path = pr_dir / "metadata" / "issue.json"
    buggy_dir = pr_dir / "buggy"
    generated_dir = pr_dir / "generated" / model_name
    attempt_dir = generated_dir / attempt_name
    prompts_dir = pr_dir / "prompts"
    reports_dir = pr_dir / "reports"

    metadata = read_json(metadata_path)
    validate_safe_metadata(metadata)

    generated_dir.mkdir(parents=True, exist_ok=True)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)

    copy_buggy_to_attempt(buggy_dir, attempt_dir, overwrite=overwrite)
    init_git_repo(attempt_dir)

    instruction = make_agent_instruction(metadata, model_name)

    if model_name == "claude":
        instruction_file = attempt_dir / "CLAUDE.md"
    elif model_name == "codex":
        instruction_file = attempt_dir / "AGENTS.md"
    else:
        instruction_file = attempt_dir / "AGENT_TASK.md"

    write_text(instruction_file, instruction)
    write_text(prompts_dir / f"{model_name}_{attempt_name}_instruction.md", instruction)

    return {
        "pr_dir": pr_dir,
        "metadata": metadata,
        "attempt_dir": attempt_dir,
        "generated_dir": generated_dir,
        "prompts_dir": prompts_dir,
        "reports_dir": reports_dir,
        "instruction_file": instruction_file,
        "instruction": instruction,
    }


def run_claude_agent(context, claude_model=None, max_turns=None, timeout=None):
    attempt_dir = context["attempt_dir"]

    cmd = [
        "claude",
        "-p",
        "Read CLAUDE.md and complete the accessibility repair task. Edit the project files directly.",
        "--output-format",
        "json",
        "--permission-mode",
        "acceptEdits",
    ]

    if claude_model:
        cmd.extend(["--model", claude_model])

    if max_turns:
        cmd.extend(["--max-turns", str(max_turns)])

    code, output = run(cmd, cwd=attempt_dir, capture=True, timeout=timeout)
    return code, output


def run_codex_agent(context, codex_model=None, timeout=None):
    attempt_dir = context["attempt_dir"]

    cmd = [
        "codex",
        "exec",
        "--sandbox",
        "danger-full-access"
    ]

    if codex_model:
        cmd.extend(["--model", codex_model])

    cmd.append(
    "Read AGENTS.md and complete the accessibility repair task."
    "Edit the project files directly."\
    )

    code, output = run(cmd, cwd=attempt_dir, capture=True, timeout=timeout)
    return code, output


def save_agent_results(context, model_name, attempt_name, exit_code, agent_output):
    pr_dir = context["pr_dir"]
    attempt_dir = context["attempt_dir"]
    generated_dir = context["generated_dir"]
    reports_dir = context["reports_dir"]

    log_path = reports_dir / f"{model_name}_{attempt_name}_agent_log.txt"
    write_text(log_path, agent_output)

    patch_text = create_patch_from_attempt(attempt_dir)
    patch_path = generated_dir / f"{attempt_name}_final.patch"
    write_text(patch_path, patch_text)

    changed_files = get_changed_files(attempt_dir)

    status = {
        "model": model_name,
        "attempt": attempt_name,
        "timestamp": datetime.now().isoformat(),
        "exit_code": exit_code,
        "status": "success" if exit_code == 0 else "agent_failed",
        "pr_dir": str(pr_dir),
        "attempt_dir": str(attempt_dir),
        "agent_log": str(log_path),
        "final_patch": str(patch_path),
        "changed_files": changed_files,
        "num_changed_files": len(changed_files),
        "patch_is_empty": len(patch_text.strip()) == 0,
    }

    status_path = reports_dir / f"{model_name}_{attempt_name}_status.json"
    write_json(status_path, status)

    print(f"\nSaved log: {log_path}")
    print(f"Saved patch: {patch_path}")
    print(f"Saved status: {status_path}")

    if len(patch_text.strip()) == 0:
        print("WARNING: final patch is empty. The agent may not have changed files.")


def run_one_agent(
    pr_dir,
    model_name,
    attempt_name,
    overwrite=False,
    claude_model=None,
    codex_model=None,
    claude_max_turns=None,
    timeout=None,
):
    context = prepare_attempt(
        pr_dir=pr_dir,
        model_name=model_name,
        attempt_name=attempt_name,
        overwrite=overwrite,
    )

    if model_name == "claude":
        exit_code, output = run_claude_agent(
            context=context,
            claude_model=claude_model,
            max_turns=claude_max_turns,
            timeout=timeout,
        )

    elif model_name == "codex":
        exit_code, output = run_codex_agent(
            context=context,
            codex_model=codex_model,
            timeout=timeout,
        )

    else:
        raise ValueError(f"Unsupported model: {model_name}")

    save_agent_results(
        context=context,
        model_name=model_name,
        attempt_name=attempt_name,
        exit_code=exit_code,
        agent_output=output,
    )


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--pr",
        required=True,
        help="Path to public PR folder, e.g., repair-benchmark/apps/x/issues/PR_123",
    )

    parser.add_argument(
        "--models",
        nargs="+",
        default=["claude", "codex"],
        choices=["claude", "codex"],
        help="Agentic repair tools to run.",
    )

    parser.add_argument(
        "--attempt",
        default=None,
        help="Attempt folder name. If not provided, a timestamped attempt name is used.",
    )

    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing generated/<model>/<attempt> folder.",
    )

    parser.add_argument(
        "--claude-model",
        default=None,
        help="Optional Claude Code model, e.g., sonnet or a full model name.",
    )

    parser.add_argument(
        "--codex-model",
        default=None,
        help="Optional Codex model name.",
    )

    parser.add_argument(
        "--claude-max-turns",
        type=int,
        default=None,
        help="Optional max number of Claude Code agentic turns.",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=None,
        help="Optional timeout in seconds for each agent.",
    )

    args = parser.parse_args()
    if args.attempt is None:
        args.attempt = make_timestamp_attempt_name()

    start_time=time.perf_counter()
    print(f"Using attempt name: {args.attempt}")
    pr_dir = ensure_public_pr_dir(args.pr)

    for model_name in args.models:
        run_one_agent(
            pr_dir=pr_dir,
            model_name=model_name,
            attempt_name=args.attempt,
            overwrite=args.overwrite,
            claude_model=args.claude_model,
            codex_model=args.codex_model,
            claude_max_turns=args.claude_max_turns,
            timeout=args.timeout,
        )
    end_time=time.perf_counter()
    elapsed_time=end_time-start_time
    print(f"\nTotal elapsed time: {elapsed_time:.2f} seconds")

if __name__ == "__main__":
    main()