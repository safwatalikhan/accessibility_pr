#!/usr/bin/env python3
"""
generate_run_dashboard.py

Walks a `repair-benchmark/apps` tree and builds a single self-contained HTML
dashboard showing, for every App -> PR -> Agent -> Attempt:

  - whether the generated patch (generated/<agent>/**/attempt_<ts>_final.patch)
    is empty (0 bytes) -- flagged red
  - if it's empty, WHY -- classified from the matching
    reports/<agent>_attempt_<ts>_agent_log.txt via keyword rules
    (see CLASSIFIERS below -- tune freely)
  - the matching *_status.json contents, if present

Nothing here mutates your data -- it only reads files and writes one HTML file.

Usage:
    python generate_run_dashboard.py --root /path/to/repair-benchmark/apps \
        --out run_dashboard.html

If --root is omitted, it defaults to "repair-benchmark/apps" relative to the
current working directory.
"""

import argparse
import json
import re
import sys
from datetime import datetime
from html import escape
from pathlib import Path

AGENTS = ["claude", "codex", "qwen"]

FINAL_PATCH_RE = re.compile(r"attempt_(\d{8}_\d{6})_final\.patch$")
LOG_RE = re.compile(r"^(claude|codex|qwen)_attempt_(\d{8}_\d{6})_agent_log\.txt$")
STATUS_RE = re.compile(r"^(claude|codex|qwen)_attempt_(\d{8}_\d{6})_status\.json$")

# ---------------------------------------------------------------------------
# Classification rules for WHY a generated patch came back empty.
# First matching pattern wins (order matters). Case-insensitive, searched
# against the full agent_log.txt text. Edit/reorder/add to these freely --
# they're a starting guess, not ground truth about your logs.
# ---------------------------------------------------------------------------
CLASSIFIERS = [
    ("Model not supported (Codex/ChatGPT account)", r"model[' ]?s? is not supported when using codex with a chatgpt account"),
    ("Model not found / no access",       r"does not exist or you do not have access to it"),
    ("Free-tier model unavailable (needs paid slug)", r"unavailable for free|use this slug instead"),
    ("Rate limited",                      r"rate.?limit|429\b|too many requests|hit your usage limit|purchase more credits"),
    ("Context length exceeded",           r"context length|context window|maximum context|too many tokens"),
    ("Timeout",                           r"\btimeout\b|timed out|deadline exceeded"),
    ("Auth / API key error",              r"api key|unauthorized|\b401\b|invalid_api_key|authentication (?:error|failed)"),
    ("Max iterations / turns exceeded",   r"max(?:imum)? (?:turns|iterations|steps)|iteration limit|turn limit"),
    ("Agent reported no changes needed",  r"no changes? (?:needed|required)|nothing to (?:fix|patch|change)|already (?:fixed|correct)"),
    ("Crashed / exception",               r"traceback \(most recent call last\)|unhandled exception|fatal error"),
    ("Refused / declined",                r"i (?:can(?:not|'t)|won't) (?:help|assist|complete)|as an ai"),
    ("Empty response from model",         r"empty response|no content returned|received no output"),
]
COMPILED_CLASSIFIERS = [(label, re.compile(pat, re.I)) for label, pat in CLASSIFIERS]


# ---------------------------------------------------------------------------
# Model-extraction rules: which model actually ran, per agent, read out of
# the same agent_log.txt. Applied to every attempt (not just empty ones).
# ---------------------------------------------------------------------------

MODEL_USAGE_KEY_RE = re.compile(r'"modelUsage"')
CODEX_MODEL_LINE_RE = re.compile(r"^model:\s*(.+)$", re.I | re.M)
QWEN_FREE_TIER_RE = re.compile(r"unavailable for free", re.I)

_TOKEN_FIELDS = ("inputTokens", "outputTokens", "cacheReadInputTokens", "cacheCreationInputTokens")


def extract_claude_model(log_text: str) -> str:
    """Find the `"modelUsage":{...}` JSON object and return whichever model
    key has the larger total token count (input+output+cache read+cache
    creation). Returns "N/A" if the object isn't found or doesn't parse."""
    m = MODEL_USAGE_KEY_RE.search(log_text)
    if not m:
        return "N/A"
    brace_start = log_text.find("{", m.end())
    if brace_start == -1:
        return "N/A"
    depth = 0
    i = brace_start
    n = len(log_text)
    while i < n:
        c = log_text[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                break
        i += 1
    else:
        return "N/A"
    obj_str = log_text[brace_start:i + 1]
    try:
        usage = json.loads(obj_str)
    except (json.JSONDecodeError, ValueError):
        return "N/A"
    if not isinstance(usage, dict) or not usage:
        return "N/A"
    best_model, best_total = None, -1
    for model_name, stats in usage.items():
        if not isinstance(stats, dict):
            continue
        total = sum(stats.get(f, 0) or 0 for f in _TOKEN_FIELDS)
        if total > best_total:
            best_total, best_model = total, model_name
    return best_model or "N/A"


def extract_codex_model(log_text: str) -> str:
    m = CODEX_MODEL_LINE_RE.search(log_text)
    if not m:
        return "N/A"
    return m.group(1).strip() or "N/A"


def extract_qwen_model(log_text: str) -> str:
    if QWEN_FREE_TIER_RE.search(log_text):
        return "qwen-free-tier"
    return "qwen3-coder"


def extract_model(agent: str, log_text: str) -> str:
    if log_text is None:
        return "N/A"
    if agent == "claude":
        return extract_claude_model(log_text)
    if agent == "codex":
        return extract_codex_model(log_text)
    if agent == "qwen":
        return extract_qwen_model(log_text)
    return "N/A"


def classify(log_text: str) -> str:
    for label, pat in COMPILED_CLASSIFIERS:
        if pat.search(log_text):
            return label
    return "Unclassified (see log excerpt)"


def parse_ts(ts: str):
    try:
        return datetime.strptime(ts, "%Y%m%d_%H%M%S")
    except ValueError:
        return None


def find_apps(root: Path):
    return sorted((p for p in root.iterdir() if p.is_dir()), key=lambda p: p.name)


def find_pr_dirs(app_dir: Path):
    issues = app_dir / "issues"
    if not issues.is_dir():
        return []
    out = []
    for p in sorted(issues.iterdir(), key=lambda p: p.name):
        if not p.is_dir():
            continue
        name = p.name
        if not name.startswith("PR_"):
            continue
        if name.endswith("_private"):
            continue
        out.append(p)
    return out


def pr_id_from_dirname(name: str) -> str:
    return name[len("PR_"):]


def scan_generated(pr_dir: Path):
    """agent -> list of {timestamp, size, empty, path}"""
    result = {a: [] for a in AGENTS}
    gen_dir = pr_dir / "generated"
    if not gen_dir.is_dir():
        return result
    for agent in AGENTS:
        agent_dir = gen_dir / agent
        if not agent_dir.is_dir():
            continue
        for patch in sorted(agent_dir.rglob("attempt_*_final.patch")):
            m = FINAL_PATCH_RE.search(patch.name)
            if not m:
                continue
            ts = m.group(1)
            try:
                size = patch.stat().st_size
            except OSError:
                size = -1
            result[agent].append(
                {"timestamp": ts, "size": size, "empty": size == 0, "path": str(patch)}
            )
    return result


def scan_reports(pr_dir: Path):
    """(agent, timestamp) -> {"log": Path, "status": Path}"""
    reports_dir = pr_dir / "reports"
    out = {}
    if not reports_dir.is_dir():
        return out
    for f in reports_dir.iterdir():
        if not f.is_file():
            continue
        m = LOG_RE.match(f.name)
        if m:
            out.setdefault((m.group(1), m.group(2)), {})["log"] = f
            continue
        m = STATUS_RE.match(f.name)
        if m:
            out.setdefault((m.group(1), m.group(2)), {})["status"] = f
    return out


def build_data(root: Path):
    apps_data = []
    warnings = []
    for app_dir in find_apps(root):
        pr_dirs = find_pr_dirs(app_dir)
        if not pr_dirs:
            continue
        pr_records = []
        for pr_dir in pr_dirs:
            pr_id = pr_id_from_dirname(pr_dir.name)
            gen = scan_generated(pr_dir)
            reports = scan_reports(pr_dir)
            attempts = []
            for agent in AGENTS:
                for entry in gen[agent]:
                    ts = entry["timestamp"]
                    rep = reports.get((agent, ts), {})

                    # Read the log once (if present) -- used for both model
                    # extraction (every attempt) and failure classification
                    # (empty attempts only).
                    log_path = rep.get("log")
                    log_text = None
                    if log_path is not None:
                        try:
                            log_text = log_path.read_text(errors="replace")
                        except OSError as e:
                            warnings.append(f"Could not read {log_path}: {e}")
                            log_text = None

                    model = extract_model(agent, log_text)

                    classification = None
                    log_excerpt = None
                    if entry["empty"]:
                        if log_text is not None:
                            classification = classify(log_text)
                            log_excerpt = log_text[-2000:]
                        else:
                            classification = "No matching log file found"
                    status_json = None
                    status_path = rep.get("status")
                    if status_path is not None:
                        try:
                            status_json = json.loads(status_path.read_text())
                        except Exception as e:
                            warnings.append(f"Could not parse {status_path}: {e}")
                    attempts.append(
                        {
                            "agent": agent,
                            "timestamp": ts,
                            "dt": parse_ts(ts),
                            "size": entry["size"],
                            "empty": entry["empty"],
                            "model": model,
                            "classification": classification,
                            "log_excerpt": log_excerpt,
                            "status": status_json,
                            "has_log": "log" in rep,
                            "has_status": "status" in rep,
                        }
                    )
            attempts.sort(key=lambda a: (a["agent"], a["dt"] or datetime.min))
            agents_present = sorted({a["agent"] for a in attempts})
            pr_records.append(
                {
                    "pr_id": pr_id,
                    "dirname": pr_dir.name,
                    "attempts": attempts,
                    "agents_present": agents_present,
                    "is_partial_agents": len(agents_present) < len(AGENTS),
                    "empty_count": sum(1 for a in attempts if a["empty"]),
                    "total_count": len(attempts),
                }
            )
        apps_data.append({"app": app_dir.name, "prs": pr_records})
    return apps_data, warnings


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------

def dt_str(a):
    if a["dt"]:
        return a["dt"].strftime("%Y-%m-%d %H:%M:%S")
    return a["timestamp"]


def render_html(apps_data, warnings, root_str):
    total_prs = sum(len(app["prs"]) for app in apps_data)
    total_attempts = sum(pr["total_count"] for app in apps_data for pr in app["prs"])
    total_empty = sum(pr["empty_count"] for app in apps_data for pr in app["prs"])
    partial_pr_count = sum(1 for app in apps_data for pr in app["prs"] if pr["is_partial_agents"])

    class_counts = {}
    for app in apps_data:
        for pr in app["prs"]:
            for a in pr["attempts"]:
                if a["empty"]:
                    class_counts[a["classification"]] = class_counts.get(a["classification"], 0) + 1

    # Build the flat row dataset consumed by JS for filtering/sorting.
    rows = []
    for app in apps_data:
        for pr in app["prs"]:
            for a in pr["attempts"]:
                rows.append(
                    {
                        "app": app["app"],
                        "pr_id": pr["pr_id"],
                        "dirname": pr["dirname"],
                        "agent": a["agent"],
                        "timestamp": a["timestamp"],
                        "dt": dt_str(a),
                        "size": a["size"],
                        "empty": a["empty"],
                        "model": a["model"],
                        "classification": a["classification"] or "",
                        "log_excerpt": a["log_excerpt"] or "",
                        "status": a["status"],
                        "has_log": a["has_log"],
                        "has_status": a["has_status"],
                        "partial_pr": pr["is_partial_agents"],
                        "agents_present": pr["agents_present"],
                    }
                )

    rows_json = json.dumps(rows)
    class_labels = sorted(class_counts.keys())

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Agent Run Dashboard</title>
<style>
  :root {{
    --bg: #0f1115;
    --panel: #171a21;
    --panel-2: #1e222b;
    --border: #2a2f3a;
    --text: #e6e8ec;
    --muted: #9aa2af;
    --green: #2ecc71;
    --green-dim: #163d29;
    --red: #ff5c5c;
    --red-dim: #3d1616;
    --amber: #f0b429;
    --amber-dim: #3d2f0e;
    --accent: #5b8cff;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    background: var(--bg);
    color: var(--text);
  }}
  header {{
    padding: 20px 28px 12px;
    border-bottom: 1px solid var(--border);
    position: sticky;
    top: 0;
    background: var(--bg);
    z-index: 20;
  }}
  h1 {{ margin: 0 0 4px; font-size: 20px; font-weight: 600; }}
  .subtitle {{ color: var(--muted); font-size: 13px; }}
  .stats {{
    display: flex;
    gap: 12px;
    margin: 14px 0 10px;
    flex-wrap: wrap;
  }}
  .stat {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 10px 14px;
    min-width: 110px;
  }}
  .stat .num {{ font-size: 20px; font-weight: 700; }}
  .stat .lbl {{ font-size: 11px; color: var(--muted); text-transform: uppercase; letter-spacing: .04em; }}
  .stat.red .num {{ color: var(--red); }}
  .stat.amber .num {{ color: var(--amber); }}
  .stat.green .num {{ color: var(--green); }}

  .tabs {{
    display: flex;
    gap: 4px;
    padding: 12px 28px 0;
  }}
  .tab-btn {{
    background: var(--panel);
    border: 1px solid var(--border);
    border-bottom: none;
    color: var(--muted);
    padding: 8px 16px;
    border-radius: 8px 8px 0 0;
    font-size: 13px;
    cursor: pointer;
  }}
  .tab-btn.active {{
    color: var(--text);
    background: var(--panel-2);
    border-color: var(--accent);
  }}
  .field.disabled {{ opacity: .35; pointer-events: none; }}

  .nested-table {{ width: 100%; border-collapse: collapse; }}
  .nested-table td {{ padding: 4px 10px; border: none; }}
  .nested-table tr:hover {{ background: transparent; }}
  .count-badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    background: var(--panel-2);
    border: 1px solid var(--border);
    border-radius: 999px;
    padding: 2px 9px;
    font-size: 11px;
    color: var(--accent);
    cursor: pointer;
  }}
  .count-badge:hover {{ border-color: var(--accent); }}

  .controls {{
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    padding: 10px 28px;
    border-bottom: 1px solid var(--border);
    background: var(--panel);
    position: sticky;
    top: 84px;
    z-index: 19;
  }}
  .controls input, .controls select {{
    background: var(--panel-2);
    border: 1px solid var(--border);
    color: var(--text);
    border-radius: 6px;
    padding: 7px 10px;
    font-size: 13px;
  }}
  .controls label {{ font-size: 11px; color: var(--muted); display: block; margin-bottom: 3px; }}
  .controls .field {{ display: flex; flex-direction: column; }}
  .controls input[type="text"] {{ min-width: 220px; }}
  .controls .chk {{ flex-direction: row; align-items: center; gap: 6px; margin-top: 18px; }}

  main {{ padding: 16px 28px 60px; }}

  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  thead th {{
    text-align: left;
    padding: 8px 10px;
    color: var(--muted);
    font-weight: 600;
    font-size: 11px;
    text-transform: uppercase;
    letter-spacing: .03em;
    border-bottom: 1px solid var(--border);
    cursor: pointer;
    user-select: none;
    white-space: nowrap;
  }}
  thead th:hover {{ color: var(--text); }}
  thead th .arrow {{ opacity: .5; font-size: 10px; margin-left: 4px; }}
  tbody tr {{ border-bottom: 1px solid var(--border); }}
  tbody tr:hover {{ background: var(--panel); }}
  td {{ padding: 8px 10px; vertical-align: top; }}
  .badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 999px;
    font-size: 11px;
    font-weight: 600;
  }}
  .badge.ok {{ background: var(--green-dim); color: var(--green); }}
  .badge.empty {{ background: var(--red-dim); color: var(--red); }}
  .badge.partial {{ background: var(--amber-dim); color: var(--amber); }}
  .agent-tag {{
    display: inline-block;
    padding: 1px 7px;
    border-radius: 5px;
    font-size: 11px;
    font-weight: 600;
    background: var(--panel-2);
    border: 1px solid var(--border);
  }}
  .agent-claude {{ color: #d8a6ff; }}
  .agent-codex {{ color: #7fd0ff; }}
  .agent-qwen {{ color: #ffd27f; }}
  .mono {{ font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; font-size: 12px; color: var(--muted); }}
  .reason {{ color: var(--red); font-weight: 500; }}
  .expand-btn {{
    background: none; border: 1px solid var(--border); color: var(--muted);
    border-radius: 5px; font-size: 11px; padding: 2px 8px; cursor: pointer;
  }}
  .expand-btn:hover {{ color: var(--text); border-color: var(--accent); }}
  .log-row td {{ background: var(--panel-2); padding: 12px 16px; }}
  .log-row pre {{
    white-space: pre-wrap;
    word-break: break-word;
    margin: 0;
    max-height: 320px;
    overflow-y: auto;
    color: #cfd3da;
    font-size: 12px;
    line-height: 1.5;
  }}
  .hidden {{ display: none !important; }}
  .empty-state {{ color: var(--muted); padding: 40px; text-align: center; }}
  .app-pr {{ display: flex; flex-direction: column; gap: 1px; }}
  .app-pr .app {{ color: var(--muted); font-size: 11px; }}
  .app-pr .pr {{ font-weight: 600; }}
  .warnings {{
    margin: 0 28px 0;
    padding: 10px 14px;
    background: var(--amber-dim);
    color: var(--amber);
    border-radius: 8px;
    font-size: 12px;
  }}
</style>
</head>
<body>

<header>
  <h1>Agent Run Dashboard</h1>
  <div class="subtitle">Scanned root: <span class="mono">{escape(root_str)}</span> &middot; generated at {escape(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}</div>
  <div class="stats">
    <div class="stat"><div class="num">{len(apps_data)}</div><div class="lbl">Apps</div></div>
    <div class="stat"><div class="num">{total_prs}</div><div class="lbl">PRs</div></div>
    <div class="stat"><div class="num">{total_attempts}</div><div class="lbl">Attempts</div></div>
    <div class="stat green"><div class="num">{total_attempts - total_empty}</div><div class="lbl">Non-empty patches</div></div>
    <div class="stat red"><div class="num">{total_empty}</div><div class="lbl">Empty patches</div></div>
    <div class="stat amber"><div class="num">{partial_pr_count}</div><div class="lbl">PRs w/ partial agents</div></div>
  </div>
</header>

{f'<div class="warnings">{escape(str(len(warnings)))} file(s) could not be read/parsed — see console warnings.</div>' if warnings else ''}

<div class="tabs">
  <button class="tab-btn active" id="tab-attempts" data-view="attempts">Attempts</button>
  <button class="tab-btn" id="tab-summary" data-view="summary">PR Summary (models per agent)</button>
</div>

<div class="controls">
  <div class="field">
    <label>Search (app / PR id / agent / model)</label>
    <input type="text" id="f-search" placeholder="e.g. 12345 or codex">
  </div>
  <div class="field">
    <label>App</label>
    <select id="f-app"><option value="">All apps</option></select>
  </div>
  <div class="field" id="f-agent-wrap">
    <label>Agent</label>
    <select id="f-agent">
      <option value="">All agents</option>
      <option value="claude">claude</option>
      <option value="codex">codex</option>
      <option value="qwen">qwen</option>
    </select>
  </div>
  <div class="field" id="f-status-wrap">
    <label>Status</label>
    <select id="f-status">
      <option value="">All statuses</option>
      <option value="ok">OK (non-empty)</option>
      <option value="empty">Empty (flagged)</option>
    </select>
  </div>
  <div class="field" id="f-reason-wrap">
    <label>Failure reason</label>
    <select id="f-reason">
      <option value="">All reasons</option>
      {"".join(f'<option value="{escape(c)}">{escape(c)}</option>' for c in class_labels)}
    </select>
  </div>
  <div class="field chk">
    <input type="checkbox" id="f-partial-only">
    <label for="f-partial-only" style="margin:0;">Partial-agent PRs only</label>
  </div>
</div>

<main>
  <table id="tbl">
    <thead>
      <tr>
        <th data-key="app">App</th>
        <th data-key="pr_id">PR ID</th>
        <th data-key="agent">Agent</th>
        <th data-key="dt">Attempt time</th>
        <th data-key="size">Patch size</th>
        <th data-key="model">Model</th>
        <th data-key="status">Status</th>
        <th data-key="classification">Reason (if empty)</th>
        <th></th>
      </tr>
    </thead>
    <tbody id="tbody"></tbody>
  </table>

  <table id="tbl2" class="hidden">
    <thead>
      <tr>
        <th data-key2="app">App</th>
        <th data-key2="pr_id">PR ID</th>
        <th>Codex</th>
        <th>Claude</th>
        <th>Qwen</th>
        <th></th>
      </tr>
    </thead>
    <tbody id="tbody2"></tbody>
  </table>

  <div id="empty-msg" class="empty-state hidden">No rows match the current filters.</div>
</main>

<script>
const ROWS = {rows_json};
const AGENT_COUNT = {len(AGENTS)};

let sortKey = 'app';
let sortDir = 1;
let sortKey2 = 'app';
let sortDir2 = 1;
let currentView = 'attempts';

function agentClass(agent) {{ return 'agent-' + agent; }}

function fmtSize(n) {{
  if (n < 0) return 'n/a';
  if (n === 0) return '0 B';
  if (n < 1024) return n + ' B';
  return (n/1024).toFixed(1) + ' KB';
}}

function populateAppFilter() {{
  const apps = [...new Set(ROWS.map(r => r.app))].sort();
  const sel = document.getElementById('f-app');
  for (const a of apps) {{
    const o = document.createElement('option');
    o.value = a; o.textContent = a;
    sel.appendChild(o);
  }}
}}

function currentFilters() {{
  return {{
    search: document.getElementById('f-search').value.trim().toLowerCase(),
    app: document.getElementById('f-app').value,
    agent: document.getElementById('f-agent').value,
    status: document.getElementById('f-status').value,
    reason: document.getElementById('f-reason').value,
    partialOnly: document.getElementById('f-partial-only').checked,
  }};
}}

function rowMatches(r, f) {{
  if (f.app && r.app !== f.app) return false;
  if (f.agent && r.agent !== f.agent) return false;
  if (f.status === 'ok' && r.empty) return false;
  if (f.status === 'empty' && !r.empty) return false;
  if (f.reason && r.classification !== f.reason) return false;
  if (f.partialOnly && !r.partial_pr) return false;
  if (f.search) {{
    const hay = (r.app + ' ' + r.pr_id + ' ' + r.agent + ' ' + r.model + ' ' + r.classification).toLowerCase();
    if (!hay.includes(f.search)) return false;
  }}
  return true;
}}

function sortRows(rows) {{
  return rows.slice().sort((a, b) => {{
    let va = a[sortKey], vb = b[sortKey];
    if (sortKey === 'size') {{ va = a.size; vb = b.size; }}
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    if (va < vb) return -1 * sortDir;
    if (va > vb) return 1 * sortDir;
    return 0;
  }});
}}

// --- PR Summary view: one row per unique (app, PR), columns = the distinct
// models that produced a NON-empty patch for that agent on that PR. ---

function buildPrSummary() {{
  const map = new Map();
  for (const r of ROWS) {{
    const key = r.app + '\\u0001' + r.pr_id;
    if (!map.has(key)) {{
      map.set(key, {{
        app: r.app,
        pr_id: r.pr_id,
        dirname: r.dirname,
        partial_pr: r.partial_pr,
        agents_present: r.agents_present,
        models: {{ claude: new Set(), codex: new Set(), qwen: new Set() }},
        successCount: {{ claude: 0, codex: 0, qwen: 0 }},
      }});
    }}
    const entry = map.get(key);
    if (!r.empty) {{
      entry.successCount[r.agent] += 1;
      if (r.model && r.model !== 'N/A') {{
        entry.models[r.agent].add(r.model);
      }}
    }}
  }}
  return [...map.values()].map(e => ({{
    app: e.app,
    pr_id: e.pr_id,
    dirname: e.dirname,
    partial_pr: e.partial_pr,
    agents_present: e.agents_present,
    claude: [...e.models.claude].sort(),
    codex: [...e.models.codex].sort(),
    qwen: [...e.models.qwen].sort(),
    successCount: e.successCount,
  }}));
}}

function summaryRowMatches(r, f) {{
  if (f.app && r.app !== f.app) return false;
  if (f.partialOnly && !r.partial_pr) return false;
  if (f.search) {{
    const allModels = [...r.claude, ...r.codex, ...r.qwen].join(' ');
    const hay = (r.app + ' ' + r.pr_id + ' ' + allModels).toLowerCase();
    if (!hay.includes(f.search)) return false;
  }}
  return true;
}}

function sortSummary(rows) {{
  return rows.slice().sort((a, b) => {{
    let va = a[sortKey2], vb = b[sortKey2];
    if (typeof va === 'string') va = va.toLowerCase();
    if (typeof vb === 'string') vb = vb.toLowerCase();
    if (va < vb) return -1 * sortDir2;
    if (va > vb) return 1 * sortDir2;
    return 0;
  }});
}}

function modelCell(models, agent, agentsPresent, successCount) {{
  if (!agentsPresent.includes(agent)) {{
    return '<span class="mono" style="color:var(--muted)">not run</span>';
  }}
  if (models.length === 1) {{
    return '<span class="agent-tag ' + agentClass(agent) + '">' + models[0] + '</span>';
  }}
  if (models.length > 1) {{
    return '<span class="count-badge" data-toggle-agent="' + agent + '">' + models.length + ' models &#9662;</span>';
  }}
  if (successCount > 0) {{
    return '<span class="mono" style="color:var(--muted)" title="Patch succeeded but model could not be parsed from the log">model unknown</span>';
  }}
  return '<span class="badge empty">no success</span>';
}}

function nestedDetailHtml(r) {{
  const lines = [];
  for (const agent of ['codex', 'claude', 'qwen']) {{
    if (r[agent].length > 1) {{
      for (const m of r[agent]) {{
        lines.push('<tr><td><span class="agent-tag ' + agentClass(agent) + '">' + agent + '</span></td><td class="mono">' + m + '</td></tr>');
      }}
    }}
  }}
  return '<table class="nested-table"><tbody>' + lines.join('') + '</tbody></table>';
}}

function renderSummary() {{
  const f = currentFilters();
  const all = buildPrSummary();
  const filtered = sortSummary(all.filter(r => summaryRowMatches(r, f)));
  const tbody = document.getElementById('tbody2');
  tbody.innerHTML = '';
  document.getElementById('empty-msg').classList.toggle('hidden', filtered.length > 0);

  filtered.forEach((r, idx) => {{
    const tr = document.createElement('tr');
    const partialBadge = r.partial_pr
      ? ' <span class="badge partial" title="Only ' + r.agents_present.join(', ') + ' ran for this PR">PARTIAL</span>'
      : '';
    const needsExpand = r.codex.length > 1 || r.claude.length > 1 || r.qwen.length > 1;
    tr.innerHTML = `
      <td>${{r.app}}</td>
      <td>${{r.pr_id}}${{partialBadge}}</td>
      <td>${{modelCell(r.codex, 'codex', r.agents_present, r.successCount.codex)}}</td>
      <td>${{modelCell(r.claude, 'claude', r.agents_present, r.successCount.claude)}}</td>
      <td>${{modelCell(r.qwen, 'qwen', r.agents_present, r.successCount.qwen)}}</td>
      <td>${{needsExpand ? '<button class="expand-btn" data-idx2="'+idx+'">details</button>' : ''}}</td>
    `;
    tbody.appendChild(tr);

    if (needsExpand) {{
      const detailTr = document.createElement('tr');
      detailTr.className = 'log-row hidden';
      detailTr.id = 'detail-' + idx;
      const td = document.createElement('td');
      td.colSpan = 6;
      td.innerHTML = nestedDetailHtml(r);
      detailTr.appendChild(td);
      tbody.appendChild(detailTr);
    }}
  }});

  tbody.querySelectorAll('[data-idx2]').forEach(btn => {{
    btn.addEventListener('click', () => {{
      const row = document.getElementById('detail-' + btn.dataset.idx2);
      row.classList.toggle('hidden');
    }});
  }});
  tbody.querySelectorAll('[data-toggle-agent]').forEach(el => {{
    el.addEventListener('click', () => {{
      const tr = el.closest('tr');
      const nextRow = tr.nextElementSibling;
      if (nextRow && nextRow.classList.contains('log-row')) {{
        nextRow.classList.toggle('hidden');
      }}
    }});
  }});
}}

function render() {{
  if (currentView === 'summary') {{
    renderSummary();
    return;
  }}
  const f = currentFilters();
  const filtered = sortRows(ROWS.filter(r => rowMatches(r, f)));
  const tbody = document.getElementById('tbody');
  tbody.innerHTML = '';
  document.getElementById('empty-msg').classList.toggle('hidden', filtered.length > 0);

  filtered.forEach((r, idx) => {{
    const tr = document.createElement('tr');
    const statusBadge = r.empty
      ? '<span class="badge empty">EMPTY</span>'
      : '<span class="badge ok">OK</span>';
    const partialBadge = r.partial_pr
      ? ' <span class="badge partial" title="Only ' + r.agents_present.join(', ') + ' ran for this PR">PARTIAL</span>'
      : '';
    const reasonCell = r.empty
      ? '<span class="reason">' + (r.classification || '') + '</span>'
      : '<span class="mono">—</span>';
    const canExpand = !!r.log_excerpt;
    tr.innerHTML = `
      <td><div class="app-pr"><span class="app">${{r.app}}</span></div></td>
      <td>${{r.pr_id}}${{partialBadge}}</td>
      <td><span class="agent-tag ${{agentClass(r.agent)}}">${{r.agent}}</span></td>
      <td class="mono">${{r.dt}}</td>
      <td class="mono">${{fmtSize(r.size)}}</td>
      <td class="mono">${{r.model}}</td>
      <td>${{statusBadge}}</td>
      <td>${{reasonCell}}</td>
      <td>${{canExpand ? '<button class="expand-btn" data-idx="'+idx+'">log</button>' : ''}}</td>
    `;
    tbody.appendChild(tr);

    if (canExpand) {{
      const logTr = document.createElement('tr');
      logTr.className = 'log-row hidden';
      logTr.id = 'log-' + idx;
      const td = document.createElement('td');
      td.colSpan = 9;
      td.innerHTML = '<pre></pre>';
      td.querySelector('pre').textContent = r.log_excerpt;
      logTr.appendChild(td);
      tbody.appendChild(logTr);
    }}
  }});

  tbody.querySelectorAll('.expand-btn').forEach(btn => {{
    btn.addEventListener('click', () => {{
      const row = document.getElementById('log-' + btn.dataset.idx);
      row.classList.toggle('hidden');
    }});
  }});
}}

document.querySelectorAll('thead th[data-key]').forEach(th => {{
  th.addEventListener('click', () => {{
    const key = th.dataset.key;
    if (sortKey === key) {{ sortDir *= -1; }} else {{ sortKey = key; sortDir = 1; }}
    render();
  }});
}});

document.querySelectorAll('thead th[data-key2]').forEach(th => {{
  th.addEventListener('click', () => {{
    const key = th.dataset.key2;
    if (sortKey2 === key) {{ sortDir2 *= -1; }} else {{ sortKey2 = key; sortDir2 = 1; }}
    render();
  }});
}});

function setView(view) {{
  currentView = view;
  document.getElementById('tab-attempts').classList.toggle('active', view === 'attempts');
  document.getElementById('tab-summary').classList.toggle('active', view === 'summary');
  document.getElementById('tbl').classList.toggle('hidden', view !== 'attempts');
  document.getElementById('tbl2').classList.toggle('hidden', view !== 'summary');
  ['f-agent-wrap', 'f-status-wrap', 'f-reason-wrap'].forEach(id => {{
    document.getElementById(id).classList.toggle('disabled', view === 'summary');
  }});
  render();
}}

document.getElementById('tab-attempts').addEventListener('click', () => setView('attempts'));
document.getElementById('tab-summary').addEventListener('click', () => setView('summary'));

['f-search','f-app','f-agent','f-status','f-reason'].forEach(id => {{
  document.getElementById(id).addEventListener('input', render);
  document.getElementById(id).addEventListener('change', render);
}});
document.getElementById('f-partial-only').addEventListener('change', render);

populateAppFilter();
render();
</script>

</body>
</html>
"""
    return html


def main():
    ap = argparse.ArgumentParser(description="Build an HTML dashboard of all agent-run attempts.")
    ap.add_argument("--root", default="repair-benchmark/apps", help="Path to the 'apps' directory")
    ap.add_argument("--out", default="agent_runs_failure_report.html", help="Output HTML file path")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"Error: root directory not found: {root}", file=sys.stderr)
        sys.exit(1)

    apps_data, warnings = build_data(root)
    if not apps_data:
        print(f"Warning: no apps with PR_* issue folders found under {root}", file=sys.stderr)

    for w in warnings:
        print(f"Warning: {w}", file=sys.stderr)

    html = render_html(apps_data, warnings, str(root))
    out_path = Path(args.out).expanduser().resolve()
    out_path.write_text(html, encoding="utf-8")
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()