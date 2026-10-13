"""Network: see your connection (Wi-Fi or Ethernet), pick a Wi-Fi network, run a quick speed test.
Uses Windows' own tools (netsh / PowerShell) — nothing extra installed. Wi-Fi passwords you type go straight
into a Windows Wi-Fi profile (the same thing the Windows Wi-Fi menu does) and are not stored by Daybook."""
import os
import re
import socket
import subprocess
import tempfile
import time
import urllib.request
from xml.sax.saxutils import escape

from flask import Blueprint, jsonify, request

bp = Blueprint("network", __name__)
NOWIN = 0x08000000
CACHE = {}


def _run(args, timeout=20):
    r = subprocess.run(["cmd", "/c", "chcp 65001 >nul & " + args], capture_output=True, timeout=timeout, creationflags=NOWIN)
    return (r.stdout or b"").decode("utf-8", "replace") + (r.stderr or b"").decode("utf-8", "replace")


def _blocks(text):
    """netsh prints 'Key : value' lines; split into dicts (one per interface / network)."""
    out, cur = [], {}
    for line in text.splitlines():
        m = re.match(r"^\s*([^:]+?)\s*:\s(.*)$", line)
        if m:
            k, v = m.group(1).strip(), m.group(2).strip()
            if k in ("Name", "SSID 1", "SSID 2") or re.match(r"^SSID \d+$", k):
                if cur:
                    out.append(cur)
                cur = {}
            cur.setdefault(k, v)
    if cur:
        out.append(cur)
    return out


def wifi_status():
    t = _run("netsh wlan show interfaces")
    if "There is no wireless interface" in t or "is not running" in t:
        return None
    for b in _blocks(t):
        if "State" in b:
            return {"adapter": b.get("Description") or b.get("Name"), "state": b.get("State", ""), "ssid": b.get("SSID", ""),
                    "signal": int(re.sub(r"\D", "", b.get("Signal", "0")) or 0), "radio": b.get("Radio type", ""), "band": b.get("Band", ""),
                    "channel": b.get("Channel", ""), "rx": b.get("Receive rate (Mbps)", ""), "tx": b.get("Transmit rate (Mbps)", ""),
                    "auth": b.get("Authentication", ""), "profile": b.get("Profile", "")}
    return None


def connection():
    """Which network gets you online, plus addresses."""
    if CACHE.get("conn") and time.time() - CACHE["conn"][0] < 6:
        return CACHE["conn"][1]
    ps = ("$c = Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway -and $_.NetAdapter.Status -eq 'Up' } | Select-Object -First 1; "
          "if ($c) { $p = Get-NetConnectionProfile -InterfaceIndex $c.InterfaceIndex -ErrorAction SilentlyContinue; "
          "[pscustomobject]@{alias=$c.InterfaceAlias; desc=$c.InterfaceDescription; ip=$c.IPv4Address.IPAddress; gateway=$c.IPv4DefaultGateway.NextHop; "
          "dns=($c.DNSServer | Where-Object AddressFamily -eq 2 | ForEach-Object { $_.ServerAddresses }) -join ', '; "
          "speed=$c.NetAdapter.LinkSpeed; media=$c.NetAdapter.PhysicalMediaType; mac=$c.NetAdapter.MacAddress; internet=[string]$p.IPv4Connectivity; name=$p.Name} | ConvertTo-Json -Compress }")
    r = subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, text=True, timeout=25, creationflags=NOWIN)
    import json
    try:
        c = json.loads(r.stdout or "null")
    except Exception:
        c = None
    if c:
        c["kind"] = "wifi" if re.search(r"wi-?fi|wireless|802\.11|wlan", (c.get("media") or "") + (c.get("alias") or "") + (c.get("desc") or ""), re.I) else "ethernet"
    CACHE["conn"] = (time.time(), c)
    return c


def latency():
    best = None
    for host in ("1.1.1.1", "8.8.8.8"):
        try:
            t = time.perf_counter()
            socket.create_connection((host, 443), timeout=2).close()
            ms = (time.perf_counter() - t) * 1000
            best = ms if best is None else min(best, ms)
        except OSError:
            pass
    return round(best) if best is not None else None


def scan():
    """Ask Windows to look for networks now (WlanScan) — the list otherwise only updates every minute or so."""
    import ctypes
    from ctypes import wintypes

    class GUID(ctypes.Structure):
        _fields_ = [("d1", wintypes.DWORD), ("d2", wintypes.WORD), ("d3", wintypes.WORD), ("d4", ctypes.c_ubyte * 8)]

    class INFO(ctypes.Structure):
        _fields_ = [("guid", GUID), ("desc", ctypes.c_wchar * 256), ("state", wintypes.DWORD)]

    class LIST(ctypes.Structure):
        _fields_ = [("n", wintypes.DWORD), ("i", wintypes.DWORD), ("items", INFO * 8)]
    try:
        w = ctypes.windll.wlanapi
    except OSError:
        return False
    h, ver, lst = wintypes.HANDLE(), wintypes.DWORD(), ctypes.POINTER(LIST)()
    if w.WlanOpenHandle(2, None, ctypes.byref(ver), ctypes.byref(h)):
        return False
    try:
        if w.WlanEnumInterfaces(h, None, ctypes.byref(lst)):
            return False
        for k in range(lst.contents.n):
            w.WlanScan(h, ctypes.byref(lst.contents.items[k].guid), None, None, None)
        w.WlanFreeMemory(lst)
        return True
    finally:
        w.WlanCloseHandle(h, None)


def networks(fresh=False):
    if fresh and scan():
        time.sleep(3.5)  # scans take a few seconds
    t = _run("netsh wlan show networks mode=bssid")
    if re.search(r"location permission|location services", t, re.I):
        return {"error": "location", "items": []}
    saved = set(re.findall(r"All User Profile\s*:\s*(.+)", _run("netsh wlan show profiles")))
    saved = {s.strip() for s in saved}
    items = {}
    for b in _blocks(t):
        ssid_key = next((k for k in b if re.match(r"^SSID \d+$", k)), None)
        if not ssid_key:
            continue
        ssid = b[ssid_key]
        if not ssid:
            continue
        sig = int(re.sub(r"\D", "", b.get("Signal", "0")) or 0)
        auth = b.get("Authentication", "")
        if ssid not in items or sig > items[ssid]["signal"]:
            items[ssid] = {"ssid": ssid, "signal": sig, "auth": auth, "secure": auth.lower() != "open", "saved": ssid in saved,
                           "band": b.get("Band", ""), "channel": b.get("Channel", "")}
    return {"items": sorted(items.values(), key=lambda x: -x["signal"])}


def connect(ssid, password=""):
    nets = {n["ssid"]: n for n in networks()["items"]}
    n = nets.get(ssid, {"auth": "WPA2-Personal", "secure": bool(password), "saved": False})
    if not n.get("saved") or password:
        if n.get("secure") and not password:
            raise ValueError("This network needs a password")
        wpa3 = "WPA3" in n.get("auth", "")
        auth = "open" if not n.get("secure") else ("WPA3SAE" if wpa3 else "WPA2PSK")
        sec = ("<sharedKey><keyType>passPhrase</keyType><protected>false</protected><keyMaterial>"
               f"{escape(password)}</keyMaterial></sharedKey>") if n.get("secure") else ""
        xml = (f'<?xml version="1.0"?><WLANProfile xmlns="http://www.microsoft.com/networking/WLAN/profile/v1"><name>{escape(ssid)}</name>'
               f'<SSIDConfig><SSID><name>{escape(ssid)}</name></SSID></SSIDConfig><connectionType>ESS</connectionType><connectionMode>auto</connectionMode>'
               f'<MSM><security><authEncryption><authentication>{auth}</authentication><encryption>{"none" if auth == "open" else "AES"}</encryption>'
               f'<useOneX>false</useOneX></authEncryption>{sec}</security></MSM></WLANProfile>')
        fd, path = tempfile.mkstemp(suffix=".xml")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(xml)
            out = _run(f'netsh wlan add profile filename="{path}" user=current')
        finally:
            os.remove(path)  # the password only lives in Windows' own Wi-Fi profile
        if "is added" not in out and "added on interface" not in out:
            raise RuntimeError(out.strip()[-200:] or "Windows didn't accept the network")
    out = _run(f'netsh wlan connect name="{ssid}" ssid="{ssid}"')
    if "successfully" not in out.lower():
        raise RuntimeError(out.strip()[-200:])
    for _ in range(20):  # wait until it's actually connected
        time.sleep(0.6)
        s = wifi_status()
        if s and s["state"].lower() == "connected" and s["ssid"] == ssid:
            CACHE.pop("conn", None)
            return s
    raise RuntimeError("Couldn't join — check the password and try again")


def speed_test():
    t0, got = time.perf_counter(), 0
    req = urllib.request.Request("https://speed.cloudflare.com/__down?bytes=25000000", headers={"User-Agent": "Daybook speed test"})
    with urllib.request.urlopen(req, timeout=30) as r:
        while chunk := r.read(1 << 16):
            got += len(chunk)
            if time.perf_counter() - t0 > 12:
                break
    secs = time.perf_counter() - t0
    return {"down_mbps": round(got * 8 / secs / 1e6, 1), "mb": round(got / 1e6, 1), "seconds": round(secs, 1), "ping_ms": latency()}


@bp.get("/api/network")
def n_state():
    w = wifi_status()
    return jsonify(wifi=w, conn=connection(), ping_ms=latency() if request.args.get("ping") else None, has_wifi=w is not None)


@bp.get("/api/network/wifi")
def n_list():
    return jsonify(networks(fresh=request.args.get("scan") == "1"))


@bp.post("/api/network/<action>")
def n_action(action):
    j = request.get_json(silent=True) or {}
    try:
        if action == "connect":
            return jsonify(connect(j.get("ssid", ""), j.get("password", "")))
        if action == "disconnect":
            _run("netsh wlan disconnect")
            CACHE.pop("conn", None)
        elif action == "forget":
            _run(f'netsh wlan delete profile name="{j.get("ssid", "")}"')
        elif action == "speed":
            return jsonify(speed_test())
        elif action == "settings":
            os.startfile("ms-settings:network-wifi" if wifi_status() else "ms-settings:network-status")
        elif action == "location":
            os.startfile("ms-settings:privacy-location")
        else:
            return jsonify(error="unknown action"), 400
    except Exception as e:
        return jsonify(error=str(e)[:300]), 400
    return jsonify(ok=True)
