"""Orca bridge for the chat: list projects, create a new project, start an agent on a task.
Uses the Orca CLI (D:\\Applications\\Orca). Creating/starting always goes through a confirm button in the UI."""
import json
import re
import subprocess
from pathlib import Path

ORCA = r"D:\Applications\Orca\resources\bin\orca.exe"
PROJECTS = Path("D:/projects")  # new projects always on D (user preference)
AGENTS = ("claude", "codex")


def _run(*args, timeout=90):
    r = subprocess.run([ORCA, *args, "--json"], capture_output=True, text=True, encoding="utf-8", timeout=timeout)
    out = (r.stdout or "").strip()
    try:
        data = json.loads(out[out.find("{"):]) if "{" in out else {}
    except json.JSONDecodeError:
        data = {}
    if r.returncode != 0 or data.get("ok") is False:
        msg = (data.get("error") or {}).get("message") if isinstance(data.get("error"), dict) else data.get("error")
        raise RuntimeError(msg or (r.stderr or out or "orca command failed").strip()[:300])
    return data.get("result", data)


def _ensure_open():
    try:
        _run("repo", "list", timeout=20)
    except Exception:
        subprocess.run([ORCA, "open", "--json"], capture_output=True, timeout=60)


def list_projects():
    _ensure_open()
    res = _run("repo", "list")
    repos = res.get("repos", res) if isinstance(res, dict) else res
    return [{"id": r["id"], "name": r.get("displayName") or Path(r["path"]).name, "path": r["path"]} for r in repos]


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:40] or "new-project"


def _find(project):
    p = project.strip().lower()
    for r in list_projects():
        if p in (r["name"].lower(), r["id"].lower(), r["path"].lower()):
            return r
    for r in list_projects():
        if p in r["name"].lower():
            return r
    raise ValueError(f"No Orca project matches '{project}'")


def new_project(name, description="", prompt="", agent="claude"):
    """D:\\projects\\<slug> + git init + README → added to Orca → agent started with the prompt."""
    agent = agent if agent in AGENTS else "claude"
    slug = slugify(name)
    path = PROJECTS / slug
    if path.exists() and any(path.iterdir()):
        raise ValueError(f"{path} already exists — use 'start task' on it instead")
    path.mkdir(parents=True, exist_ok=True)
    (path / "README.md").write_text(f"# {name}\n\n{description or prompt}\n", encoding="utf-8")
    (path / ".gitignore").write_text("node_modules/\nvenv/\n.venv/\n__pycache__/\n.env\n*.log\n", encoding="utf-8")
    git = ["git", "-C", str(path)]
    subprocess.run([*git, "init", "-q"], check=True)
    subprocess.run([*git, "config", "user.name", "Taylor"], check=True)
    subprocess.run([*git, "config", "user.email", "taylormadegrit@gmail.com"], check=True)
    subprocess.run([*git, "add", "-A"], check=True)
    subprocess.run([*git, "commit", "-q", "-m", f"Start {name}"], check=True)
    _ensure_open()
    repo = _run("repo", "add", "--path", str(path))["repo"]
    started = start_task(repo["id"], prompt, agent, by_id=True) if prompt.strip() else None
    return {"project": repo.get("displayName", slug), "path": str(path), "agent": started}


def start_task(project, prompt, agent="claude", by_id=False):
    """New Orca worktree in an existing project with an agent working on `prompt`."""
    agent = agent if agent in AGENTS else "claude"
    repo_id = project if by_id else _find(project)["id"]
    name = slugify(" ".join(prompt.split()[:5])) or "task"
    res = _run("worktree", "create", "--repo", f"id:{repo_id}", "--name", name, "--agent", agent,
               "--prompt", prompt, "--no-parent", "--activate", timeout=180)
    wt = res.get("worktree", res)
    return {"worktree": wt.get("id") or wt.get("path"), "agent": agent, "task": name}
