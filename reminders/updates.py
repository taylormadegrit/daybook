"""Automatic update checker & 1-click updater for Daybook.
Queries the GitHub repository (https://github.com/taylormadegrit/daybook) for new commits and releases.
Supports one-click pull & restart for git source checkouts, and automated download & installer launch for packaged installs.
"""
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

try:
    import certifi
except ImportError:
    certifi = None

from flask import Blueprint, jsonify, request

from . import paths

bp = Blueprint("updates", __name__)

CURRENT_VERSION = "1.7.9"
GITHUB_REPO = "taylormadegrit/daybook"
GITHUB_COMMITS_URL = f"https://api.github.com/repos/{GITHUB_REPO}/commits/master"
GITHUB_COMPARE_URL = f"https://api.github.com/repos/{GITHUB_REPO}/compare/{{base}}...{{head}}"
GITHUB_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def _get_ssl_context():
    """Returns an SSL context with certifi CA bundle if available, falling back to default or unverified."""
    if certifi:
        try:
            return ssl.create_default_context(cafile=certifi.where())
        except Exception:
            pass
    try:
        return ssl.create_default_context()
    except Exception:
        pass
    return ssl._create_unverified_context()


def _safe_urlopen(req, timeout=10):
    """Executes urlopen with SSL verification.
    If Windows certificate verification fails (unable to get local issuer certificate on clean installs or corporate proxy),
    automatically falls back to an unverified context so update checks and release downloads never fail."""
    ctx = _get_ssl_context()
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=ctx)
    except (urllib.error.URLError, ssl.SSLError) as e:
        err_str = str(e)
        if "CERTIFICATE_VERIFY_FAILED" in err_str or "certificate verify failed" in err_str or "unable to get local issuer certificate" in err_str:
            fallback_ctx = ssl._create_unverified_context()
            return urllib.request.urlopen(req, timeout=timeout, context=fallback_ctx)
        raise

_CACHE = {
    "checked_at": 0.0,
    "data": None
}
CACHE_TTL = 300  # 5 minutes

UPDATE_JOB = {
    "state": "idle",       # idle | downloading | launching | done | error
    "pct": 0,
    "msg": "",
    "error": None,
    "installer_path": None,
    "download_url": None,
    "tag": None,
    "file_size": 0,
    "downloaded_bytes": 0,
}
_JOB_LOCK = threading.Lock()


def is_git_repo() -> bool:
    return (paths.APP / ".git").exists()


def parse_version(v: str) -> tuple:
    if not v:
        return (0, 0, 0)
    cleaned = re.sub(r"^[^\d]*", "", str(v).strip())
    parts = []
    for piece in cleaned.split("."):
        m = re.match(r"^(\d+)", piece)
        if m:
            parts.append(int(m.group(1)))
        else:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def is_newer_version(remote_ver: str, local_ver: str) -> bool:
    return parse_version(remote_ver) > parse_version(local_ver)


def get_local_commit() -> dict:
    if not is_git_repo():
        return {
            "sha": "unknown",
            "short": "v" + CURRENT_VERSION,
            "message": f"Daybook {CURRENT_VERSION} Packaged Release",
            "date": "",
            "author": "Packaged Release",
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
        with _safe_urlopen(req, timeout=7) as resp:
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


def get_latest_release() -> dict:
    req = urllib.request.Request(
        GITHUB_RELEASES_URL,
        headers={
            "User-Agent": "Daybook-Updater/1.7",
            "Accept": "application/vnd.github.v3+json",
        }
    )
    with _safe_urlopen(req, timeout=7) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        tag = (data.get("tag_name") or "").strip()
        clean_ver = tag.lstrip("v").strip()
        assets = data.get("assets", []) or []
        exe_asset = next((a for a in assets if str(a.get("name", "")).lower().endswith(".exe")), None)
        return {
            "tag_name": tag,
            "version": clean_ver,
            "name": data.get("name") or f"Daybook {tag}",
            "body": data.get("body") or "",
            "html_url": data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest"),
            "published_at": data.get("published_at") or "",
            "download_url": exe_asset.get("browser_download_url") if exe_asset else None,
            "asset_name": exe_asset.get("name") if exe_asset else None,
            "asset_size": exe_asset.get("size") if exe_asset else 0,
        }


def _download_and_launch_worker(download_url: str, dest_path: Path, tag: str):
    """Background worker that streams the installer download, updates progress, and launches it."""
    with _JOB_LOCK:
        UPDATE_JOB.update(
            state="downloading",
            pct=0,
            msg=f"Connecting to download Daybook installer ({tag})...",
            error=None,
            installer_path=str(dest_path),
            download_url=download_url,
            tag=tag,
            downloaded_bytes=0,
            file_size=0,
        )

    try:
        req = urllib.request.Request(
            download_url,
            headers={"User-Agent": "Daybook-Updater/1.7"}
        )
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path = dest_path.with_suffix(".tmp")

        download_success = False
        try:
            with _safe_urlopen(req, timeout=60) as resp, open(tmp_path, "wb") as f:
                total = int(resp.headers.get("Content-Length") or 0)
                done = 0
                with _JOB_LOCK:
                    UPDATE_JOB["file_size"] = total

                while True:
                    chunk = resp.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    pct = round(done * 100 / total) if total > 0 else 0
                    mb_done = done / (1024 * 1024)
                    mb_total = total / (1024 * 1024) if total > 0 else 0
                    msg = f"Downloading Daybook {tag}: {mb_done:.1f} MB / {mb_total:.1f} MB ({pct}%)"
                    with _JOB_LOCK:
                        UPDATE_JOB["pct"] = pct
                        UPDATE_JOB["downloaded_bytes"] = done
                        UPDATE_JOB["msg"] = msg
            download_success = True
        except Exception as dl_err:
            curl_exe = shutil.which("curl") or "curl.exe"
            try:
                with _JOB_LOCK:
                    UPDATE_JOB["msg"] = f"Retrying download via curl fallback ({tag})..."
                c_res = subprocess.run(
                    [curl_exe, "-L", "-k", "-s", "-S", download_url, "-o", str(tmp_path)],
                    capture_output=True, timeout=300, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
                if c_res.returncode == 0 and tmp_path.exists() and tmp_path.stat().st_size > 1000000:
                    download_success = True
            except Exception:
                raise dl_err

        if not download_success:
            raise RuntimeError("Downloaded installer file was empty or incomplete.")

        if dest_path.exists():
            try:
                dest_path.unlink()
            except Exception:
                pass
        tmp_path.rename(dest_path)

        with _JOB_LOCK:
            UPDATE_JOB.update(
                state="launching",
                pct=100,
                msg="Download complete! Launching installer...",
            )

        time.sleep(0.5)
        try:
            os.startfile(str(dest_path))
        except Exception:
            subprocess.Popen([str(dest_path)], close_fds=True)

        with _JOB_LOCK:
            UPDATE_JOB.update(
                state="done",
                pct=100,
                msg="Installer launched! Follow the prompts to finish updating Daybook.",
            )

    except Exception as e:
        with _JOB_LOCK:
            UPDATE_JOB.update(
                state="error",
                error=str(e),
                msg=f"Download failed: {e}",
            )


@bp.get("/api/updates/progress")
def update_progress():
    """Returns the current background download job status."""
    with _JOB_LOCK:
        job_copy = dict(UPDATE_JOB)
    return jsonify(ok=True, job=job_copy)


@bp.get("/api/updates/check")
def check_updates():
    """Checks whether an update is available on GitHub."""
    force = request.args.get("force", "").lower() in ("1", "true", "yes")
    now = time.time()

    if not force and _CACHE["data"] and (now - _CACHE["checked_at"] < CACHE_TTL):
        return jsonify(_CACHE["data"])

    local = get_local_commit()
    local_sha = local.get("sha", "")
    current_ver = CURRENT_VERSION
    in_git = is_git_repo()

    remote_rel = None
    remote_commit = None
    error_msg = None

    # Step 1: Query GitHub latest release
    try:
        remote_rel = get_latest_release()
    except Exception as e:
        error_msg = f"Release check notice: {e}"

    # Step 2: Query GitHub commits if in git repo
    if in_git:
        try:
            remote_commit = get_remote_commit(local_sha)
        except Exception as e:
            if not remote_rel:
                error_msg = str(e)

    update_available = False
    update_type = "none"  # "git" or "release"
    commits_behind = 0
    commit_list = []
    remote_info = {}

    # Check git commits first for source repository checkouts
    if in_git and remote_commit and remote_commit.get("sha") and local_sha != "unknown":
        if local_sha[:12] != remote_commit["sha"][:12]:
            update_available = True
            update_type = "git"
            try:
                comp_url = GITHUB_COMPARE_URL.format(base=local_sha, head=remote_commit["sha"])
                req = urllib.request.Request(comp_url, headers={"User-Agent": "Daybook-Updater/1.7", "Accept": "application/vnd.github.v3+json"})
                with _safe_urlopen(req, timeout=5) as resp:
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
                    "sha": remote_commit.get("short", ""),
                    "message": remote_commit.get("message", ""),
                    "author": remote_commit.get("author", ""),
                    "date": remote_commit.get("date", ""),
                }]
            remote_info = remote_commit

    # Check release version: works for BOTH packaged installs and git checkouts
    if remote_rel and remote_rel.get("version"):
        rel_ver = remote_rel["version"]
        if is_newer_version(rel_ver, current_ver):
            update_available = True
            if not in_git or update_type == "none":
                update_type = "release"
                remote_info = {
                    "tag_name": remote_rel["tag_name"],
                    "version": remote_rel["version"],
                    "message": remote_rel.get("name") or f"Daybook {remote_rel['tag_name']}",
                    "short": remote_rel["tag_name"],
                    "date": remote_rel.get("published_at", ""),
                    "author": "GitHub Release",
                    "html_url": remote_rel.get("html_url", ""),
                    "notes": remote_rel.get("body", ""),
                    "download_url": remote_rel.get("download_url"),
                    "asset_name": remote_rel.get("asset_name"),
                    "asset_size": remote_rel.get("asset_size"),
                }

    if not remote_info:
        if remote_commit:
            remote_info = remote_commit
        elif remote_rel:
            remote_info = {
                "tag_name": remote_rel.get("tag_name"),
                "version": remote_rel.get("version"),
                "message": remote_rel.get("name"),
                "short": remote_rel.get("tag_name"),
                "date": remote_rel.get("published_at", ""),
                "author": "GitHub Release",
                "html_url": remote_rel.get("html_url", ""),
                "download_url": remote_rel.get("download_url"),
            }

    result = {
        "ok": (error_msg is None) or update_available or (remote_rel is not None) or (remote_commit is not None),
        "error": error_msg if not (update_available or remote_rel) else None,
        "update_available": update_available,
        "update_type": update_type,
        "commits_behind": commits_behind,
        "commit_list": commit_list,
        "current_version": current_ver,
        "is_repo": in_git,
        "local": local,
        "remote": remote_info,
        "release": remote_rel,
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
        with _JOB_LOCK:
            if UPDATE_JOB.get("state") == "downloading":
                return jsonify(
                    ok=True,
                    mode="installer_downloading",
                    job=dict(UPDATE_JOB),
                    message="Download is already in progress.",
                )

        rel = None
        try:
            rel = get_latest_release()
        except Exception as e:
            return jsonify(ok=False, error=f"Could not connect to GitHub Releases: {e}"), 500

        if not rel or not rel.get("download_url"):
            return jsonify(ok=False, error="No Windows installer asset (.exe) found in latest release."), 404

        tag = rel.get("tag_name") or "latest"
        temp_dir = Path(tempfile.gettempdir())
        dest_file = temp_dir / f"Daybook-Setup-{tag}.exe"

        threading.Thread(
            target=_download_and_launch_worker,
            args=(rel["download_url"], dest_file, tag),
            daemon=True
        ).start()

        return jsonify(
            ok=True,
            mode="installer_downloading",
            download_url=rel["download_url"],
            name=rel.get("asset_name"),
            tag=tag,
            job=dict(UPDATE_JOB),
            message=f"Downloading Daybook {tag} installer in background...",
        )

    # Git repository mode: 1-Click pull & restart
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
