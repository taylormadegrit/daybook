"""Automatic update checker & 1-click updater for Daybook.
Queries the GitHub repository (https://github.com/taylormadegrit/daybook) for new commits/releases.
Supports one-click pull & restart for git source checkouts, and release installer upgrades for packaged installs.
"""
import json
import os
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

from flask import Blueprint, jsonify, request

from . import paths

bp = Blueprint("updates", __name__)

GITHUB_REPO = "taylormadegrit/daybook"
GITHUB_COMMITS_URL = f"https://api.github.com/repos/{GITHUB_REPO}/commits/master"
GITHUB_COMPARE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/compare/{{base}}...{{head}}"
GITHUB_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

_CACHE = {
    "checked_at": 0.0,
    "data": None
}
CACHE_TTL = 300  # 5 minutes


def is_git_repo() -> bool:
    return (paths.APP / ".git").exists()


def get_local_commit() -> dict:
    if not is_git_repo():
        return {
            "sha": "unknown",
            "short": "pkg",
            "message": "Packaged release",
            "date": "",
            "author": "",
            "is_repo": False,
        }
    try:
        cmd = ["git", "log", "-1", "--pretty=format:%H%x00%h%x00%s%x00%ci%x00%an"]
        out = subprocess.check_output(cmd, cwd=str(paths.APP), stderr=subprocess.DEVNULL, timeout=5).decode("utf-8", "replace")
        parts = out.split("\x00")
        if len(parts) >= 5:
            return {
                "sha": parts[0].strip(),
                "short": parts[1].strip(),
                "message": parts[2].strip(),
                "date": parts[3].strip(),
                "author": parts[4].strip(),
                "is_repo": True,
            }
    except Exception:
        pass

    try:
        head_path = paths.APP / ".git" / "HEAD"
        if head_path.exists():
            head = head_path.read_text("utf-8").strip()
            if head.startswith("ref:"):
                ref = head.split(":", 1)[1].strip()
                ref_path = paths.APP / ".git" / ref
                if ref_path.exists():
                    sha = ref_path.read_text("utf-8").strip()
                    return {"sha": sha, "short": sha[:7], "message": "", "date": "", "author": "", "is_repo": True}
            else:
                return {"sha": head, "short": head[:7], "message": "", "date": "", "author": "", "is_repo": True}
    except Exception:
        pass

    return {
        "sha": "unknown",
        "short": "unknown",
        "message": "",
        "date": "",
        "author": "",
        "is_repo": is_git_repo(),
    }


def get_remote_commit(local_sha: str = "") -> dict:
    req = urllib.request.Request(
        GITHUB_COMMITS_URL,
        headers={
            "User-Agent": "Daybook-Updater/1.7",
            "Accept": "application/vnd.github.v3+json",
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=7) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            sha = data.get("sha", "")
            commit = data.get("commit", {})
            committer = commit.get("committer", {}) or {}
            author = commit.get("author", {}) or {}
            msg = commit.get("message", "")
            return {
                "sha": sha,
                "short": sha[:7] if sha else "",
                "message": msg.strip().split("\n")[0] if msg else "",
                "full_message": msg.strip(),
                "date": committer.get("date") or author.get("date") or "",
                "author": author.get("name") or committer.get("name") or "GitHub",
                "html_url": data.get("html_url", f"https://github.com/{GITHUB_REPO}/commit/{sha}"),
            }
    except Exception as e:
        if is_git_repo():
            try:
                cmd = ["git", "ls-remote", "origin", "refs/heads/master"]
                out = subprocess.check_output(cmd, cwd=str(paths.APP), stderr=subprocess.DEVNULL, timeout=8).decode("utf-8", "replace")
                sha = out.split()[0].strip() if out else ""
                if sha:
                    return {
                        "sha": sha,
                        "short": sha[:7],
                        "message": "Latest commit from origin/master",
                        "full_message": "",
                        "date": "",
                        "author": "GitHub",
                        "html_url": f"https://github.com/{GITHUB_REPO}/commit/{sha}",
                    }
            except Exception:
                pass
        raise e


@bp.get("/api/updates/check")
def check_updates():
    """Checks whether an update is available on GitHub."""
    force = request.args.get("force", "").lower() in ("1", "true", "yes")
    now = time.time()

    if not force and _CACHE["data"] and (now - _CACHE["checked_at"] < CACHE_TTL):
        return jsonify(_CACHE["data"])

    local = get_local_commit()
    local_sha = local.get("sha", "")
    error_msg = None
    remote = None

    try:
        remote = get_remote_commit(local_sha)
    except Exception as e:
        error_msg = str(e)

    update_available = False
    commits_behind = 0
    commit_list = []

    if remote and remote.get("sha") and local_sha and local_sha != "unknown":
        if local_sha[:12] != remote["sha"][:12]:
            update_available = True
            # Try to get comparison details if in git repo or valid sha
            try:
                comp_url = GITHUB_COMPARE_URL.format(base=local_sha, head=remote["sha"])
                req = urllib.request.Request(comp_url, headers={"User-Agent": "Daybook-Updater/1.7", "Accept": "application/vnd.github.v3+json"})
                with urllib.request.urlopen(req, timeout=5) as resp:
                    cdata = json.loads(resp.read().decode("utf-8"))
                    commits_behind = cdata.get("total_commits", 1)
                    for c in (cdata.get("commits", []) or [])[-10:]:
                        commit_list.append({
                            "sha": c.get("sha", "")[:7],
                            "message": (c.get("commit", {}).get("message", "")).strip().split("\n")[0],
                            "author": c.get("commit", {}).get("author", {}).get("name", ""),
                            "date": c.get("commit", {}).get("author", {}).get("date", ""),
                        })
            except Exception:
                commits_behind = 1
                commit_list = [{
                    "sha": remote.get("short", ""),
                    "message": remote.get("message", ""),
                    "author": remote.get("author", ""),
                    "date": remote.get("date", ""),
                }]

    result = {
        "ok": error_msg is None,
        "error": error_msg,
        "update_available": update_available,
        "commits_behind": commits_behind,
        "commit_list": commit_list,
        "current_version": "1.7.0",
        "is_repo": is_git_repo(),
        "local": local,
        "remote": remote,
        "checked_at": datetime.now().isoformat(),
        "repo_url": f"https://github.com/{GITHUB_REPO}",
    }

    _CACHE["checked_at"] = now
    _CACHE["data"] = result
    return jsonify(result)


@bp.post("/api/updates/apply")
def apply_update():
    """Applies the update from GitHub with one click."""
    if not is_git_repo():
        try:
            req = urllib.request.Request(GITHUB_RELEASES_URL, headers={"User-Agent": "Daybook-Updater/1.7"})
            with urllib.request.urlopen(req, timeout=8) as resp:
                rel = json.loads(resp.read().decode("utf-8"))
                assets = rel.get("assets", [])
                exe_asset = next((a for a in assets if a.get("name", "").endswith(".exe")), None)
                if exe_asset:
                    return jsonify(
                        ok=True,
                        mode="installer",
                        download_url=exe_asset.get("browser_download_url"),
                        name=exe_asset.get("name"),
                        tag=rel.get("tag_name"),
                        message=f"New installer {rel.get('tag_name')} is available for download."
                    )
        except Exception as e:
            return jsonify(ok=False, error=f"Failed to check releases: {e}"), 500
        return jsonify(ok=False, error="Running in packaged mode without git repository."), 400

    logs = []

    def run_cmd(args, cwd=str(paths.APP), timeout=60):
        cmd_str = " ".join(args)
        logs.append(f"$ {cmd_str}")
        res = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, timeout=timeout)
        out = (res.stdout or "").strip()
        if out:
            logs.append(out)
        if res.returncode != 0:
            raise RuntimeError(f"Command '{cmd_str}' failed with exit code {res.returncode}:\n{out}")
        return out

    try:
        # Step 1: Check git status and stash any local modifications to tracked files
        status = subprocess.check_output(["git", "status", "--porcelain"], cwd=str(paths.APP), text=True).strip()
        stashed = False
        if status:
            logs.append("Stashing local modifications before updating...")
            run_cmd(["git", "stash", "save", f"auto-update-{int(time.time())}"])
            stashed = True

        # Step 2: Fetch and pull latest changes from master
        run_cmd(["git", "fetch", "origin", "master"])
        pull_out = run_cmd(["git", "pull", "--no-edit", "origin", "master"])

        # Step 3: Check desktop dependencies
        desktop_pkg = paths.APP / "desktop" / "package.json"
        desktop_nm = paths.APP / "desktop" / "node_modules"
        if desktop_pkg.exists() and desktop_nm.exists():
            try:
                npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
                logs.append("Checking desktop packages...")
                run_cmd([npm_cmd, "install", "--prefer-offline", "--no-audit"], cwd=str(paths.APP / "desktop"), timeout=90)
            except Exception as ne:
                logs.append(f"npm note: {ne}")

        # Step 4: Restore local stash if one was created
        if stashed:
            try:
                run_cmd(["git", "stash", "pop"])
            except Exception as se:
                logs.append(f"Notice: local stash conflict avoided, changes preserved in git stash list ({se})")

        new_local = get_local_commit()
        _CACHE["checked_at"] = 0.0
        _CACHE["data"] = None

        return jsonify(
            ok=True,
            mode="git",
            output="\n".join(logs),
            commit=new_local,
            message=f"Successfully updated to {new_local.get('short', '')}: {new_local.get('message', '')}"
        )
    except Exception as e:
        return jsonify(ok=False, error=str(e), output="\n".join(logs)), 500


@bp.post("/api/updates/restart")
def restart_service():
    """Restarts the Daybook background daemon after an update."""
    def _do_restart():
        time.sleep(1.0)
        try:
            subprocess.run(["schtasks", "/End", "/TN", "LocalRemindersDaemon"], capture_output=True, timeout=5)
            time.sleep(1.0)
            subprocess.run(["schtasks", "/Run", "/TN", "LocalRemindersDaemon"], capture_output=True, timeout=5)
            return
        except Exception:
            pass

        try:
            py = paths.APP / "venv" / "Scripts" / "pythonw.exe"
            if not py.exists():
                py = Path(sys.executable)
            script = paths.APP / "daemon.pyw"
            subprocess.Popen([str(py), str(script), "--open"], cwd=str(paths.APP), close_fds=True)
            time.sleep(0.5)
            os._exit(0)
        except Exception:
            pass

    threading.Thread(target=_do_restart, daemon=True).start()
    return jsonify(ok=True, message="Daybook background service is restarting...")
