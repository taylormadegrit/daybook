"""Natural-language → reminder, fully local: Ollama qwen2.5:7b first, dateparser as fallback.
e.g. "call mom every sunday at 5pm" → text="Call mom", due=next Sunday 17:00, repeat=weekly
"""
import calendar
import json
import re
import time
import urllib.request
from datetime import datetime, timedelta

from . import db

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"
DEFAULT_HOUR = 9  # "tomorrow" with no time → 9 AM


def _ask_ollama(prompt):
    body = json.dumps({"model": db.setting("ai_model") or OLLAMA_MODEL, "prompt": prompt, "stream": False, "format": "json",
                       "options": {"temperature": 0}}).encode()
    req = urllib.request.Request(OLLAMA_URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(json.loads(r.read())["response"])


def _ask_claude(prompt):
    """Claude Code CLI (if installed and signed in) as a fallback when Ollama isn't running."""
    import subprocess
    from .chat import claude_cli
    exe = claude_cli()
    if not exe:
        raise RuntimeError("Claude isn't installed")
    r = subprocess.run([exe, "-p", prompt + "\n\nReply with the JSON object only.", "--model", "haiku", "--output-format", "text",
                        "--disallowedTools", "Bash", "Edit", "Write", "WebFetch", "WebSearch"],
                       capture_output=True, text=True, encoding="utf-8", timeout=150, creationflags=0x08000000)
    m = re.search(r"\{.*\}", r.stdout, re.S)
    if not m:
        raise RuntimeError("Claude gave no JSON")
    return json.loads(m.group(0))


_CLAUDE_DOWN = {"until": 0.0}  # after Claude fails (offline, signed out, not installed), leave it alone for a while


def ask_json(prompt):
    """Ask the local model for JSON; if Ollama isn't running, ask Claude (unless turned off); raises if neither works."""
    from .chat import _ollama_up
    errors = []
    if _ollama_up():
        try:
            return _ask_ollama(prompt)
        except Exception as e:
            errors.append(f"Ollama: {e}")
    if db.setting("ai_cloud_fallback") == "0":
        errors.append("Claude: cloud fallback is off")
    elif time.time() < _CLAUDE_DOWN["until"]:
        errors.append("Claude: unavailable a few minutes ago")
    else:
        try:
            return _ask_claude(prompt)
        except Exception as e:
            _CLAUDE_DOWN["until"] = time.time() + 600
            errors.append(f"Claude: {e}")
    raise RuntimeError("; ".join(errors) or "No AI available")


HAS_TIME = re.compile(r"\d\s*(am|pm)\b|\d:\d\d|\bnoon\b|\bmidnight\b|\bminutes?\b|\bmins?\b|\bhours?\b|\bhrs?\b", re.I)
ALIASES = [(r"\btonight\b", "today 8pm"), (r"\bthis evening\b", "today 6pm"), (r"\bthis morning\b", "today 9am"),
           (r"\bthis afternoon\b", "today 2pm"), (r"\bmorning\b", "9am"), (r"\bevening\b", "6pm"),
           (r"\bafternoon\b", "2pm"), (r"\bnoon\b", "12pm"), (r"\bmidnight\b", "11:59pm"),
           (r"\bnext (mon|tues|wednes|thurs|fri|satur|sun)day\b", r"\1day"), (r"\bon the\b", ""), (r"^\s*(on|at)\s+", "")]
REPEATS = [
    (r"\bevery\s+(\d+)\s+(minute|hour|day|week)s?\b", None),
    (r"\b(every\s+weekday|weekdays|mon(day)?\s*-\s*fri(day)?)\b", "weekdays"),
    (r"\b(every\s*day|daily|each day|every morning|every night|every evening)\b", "daily"),
    (r"\b(every\s+week|weekly|every\s+(mon|tues|wednes|thurs|fri|satur|sun)day)\b", "weekly"),
    (r"\b(every\s+month|monthly)\b", "monthly"),
    (r"\b(every\s+year|yearly|annually)\b", "yearly"),
]


def detect_repeat(text):
    """→ (rule, matched words) or ('', '')"""
    for pat, rule in REPEATS:
        m = re.search(pat, text, re.I)
        if m:
            if rule is None:
                return f"every:{m.group(1)}:{m.group(2).lower()}s", m.group(0)
            return rule, m.group(0)
    return "", ""


URGENT = re.compile(r"\b(urgent|asap|important|critical|don'?t forget|must)\b", re.I)


DAYPART = re.compile(r"\b(tonight|tomorrow night|this (morning|afternoon|evening)|(today|tomorrow) (morning|afternoon|evening|night))\b")
CLOCK = re.compile(r"\b(?:at|by|@)?\s*(\d{1,2})(?::(\d\d))?\s*(am|pm)?\b")


def _daypart_with_time(p):
    """'tonight at 11pm' / 'this evening at 7' / 'tomorrow morning 6:30' → 'today 11:00pm' / 'today 7:00pm' / 'tomorrow 6:30am'.
    (The aliases alone turned 'tonight at 11pm' into 'today 8pm 11pm', which resolved to *now*.)"""
    m = DAYPART.search(p)
    if not m:
        return p
    rest = (p[:m.start()] + " " + p[m.end():]).strip()
    c = next((c for c in CLOCK.finditer(rest) if c.group(1) and (c.group(2) or c.group(3) or re.search(r"\b(at|by|@)\s*$", rest[:c.start(1)]))), None)
    if not c:
        return p
    hour, minute, ampm = int(c.group(1)), c.group(2) or "00", c.group(3)
    word = m.group(0)
    if not ampm and hour <= 12:
        ampm = "am" if "morning" in word else "pm"
    day = "tomorrow" if "tomorrow" in word else "today"
    return f"{day} {hour}:{minute}{ampm}"


WHEN_WORDS = re.compile(
    r"\b(?:(?:next|this)\s+)?(?:today|tonight|tomorrow(?:\s+(?:morning|afternoon|evening|night))?|this\s+(?:morning|afternoon|evening)|"
    r"(?:mon|tues|wednes|thurs|fri|satur|sun)day|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{1,2}(?:st|nd|rd|th)?|"
    r"the\s+\d{1,2}(?:st|nd|rd|th)|in\s+\d+\s+(?:minutes?|mins?|hours?|hrs?|days?|weeks?))\b"
    r"|(?:\b(?:at|by|@)\s*)?\b\d{1,2}(?::\d\d)?\s*(?:am|pm)\b|\d{1,2}:\d\d|\b(?:at|by)\s+\d{1,2}(?::\d\d)?\b|\bnoon\b|\bmidnight\b", re.I)


def when_words(text):
    """The words in a request that say when — found exactly in the text (the AI sometimes drops or changes them)."""
    found = [m.group(0).strip() for m in WHEN_WORDS.finditer(text)]
    for t in re.findall(r"(?<![\d:])\d{1,2}:\d\d(?![\d:])", text):  # "6:30" with no am/pm
        if not any(t in f for f in found):
            found.append(t)
    return " ".join(found)


def resolve_when(phrase, now):
    """Exact date math (qwen is unreliable at weekdays): plain-English phrase → datetime or None."""
    import dateparser
    phrase = (phrase or "").strip()
    if not phrase:
        return None
    p = phrase.lower().strip()

    # Fast-path 1: "in <N> <unit>"
    m_in = re.fullmatch(r"in\s+(\d+)\s+(minutes?|mins?|hours?|hrs?|days?|weeks?)", p)
    if m_in:
        amt, unit = int(m_in.group(1)), m_in.group(2)
        if "min" in unit:
            return now + timedelta(minutes=amt)
        if "hr" in unit or "hour" in unit:
            return now + timedelta(hours=amt)
        if "day" in unit:
            return now + timedelta(days=amt)
        if "week" in unit:
            return now + timedelta(weeks=amt)

    # Fast-path 2: "tomorrow [at] H[:M] [am|pm]"
    m_tom = re.fullmatch(r"tomorrow(?:\s+(?:at|by|@))?\s+(\d{1,2})(?::(\d\d))?\s*(am|pm)?", p)
    if m_tom:
        h = int(m_tom.group(1))
        mi = int(m_tom.group(2) or 0)
        ap = m_tom.group(3)
        if ap == "pm" and h < 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
        elif not ap and h < 8:
            h += 12
        return (now + timedelta(days=1)).replace(hour=h, minute=mi, second=0, microsecond=0)

    # Fast-path 3: "tonight [at] H[:M] [am|pm]"
    m_ton = re.fullmatch(r"tonight(?:\s+(?:at|by|@))?\s+(\d{1,2})(?::(\d\d))?\s*(am|pm)?", p)
    if m_ton:
        h = int(m_ton.group(1))
        mi = int(m_ton.group(2) or 0)
        ap = m_ton.group(3)
        if ap == "pm" and h < 12:
            h += 12
        elif not ap and h < 12:
            h += 12
        cand = now.replace(hour=h, minute=mi, second=0, microsecond=0)
        return cand if cand > now else cand + timedelta(days=1)

    # Fast-path 4: "[next|this] <weekday> [at] H[:M] [am|pm]"
    m_wk = re.fullmatch(r"(?:next\s+|this\s+)?(monday|tuesday|wednesday|thursday|friday|saturday|sunday)(?:\s+(?:at|by|@))?\s+(\d{1,2})(?::(\d\d))?\s*(am|pm)?", p)
    if m_wk:
        w_map = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
        target_wd = w_map[m_wk.group(1)]
        h = int(m_wk.group(2))
        mi = int(m_wk.group(3) or 0)
        ap = m_wk.group(4)
        if ap == "pm" and h < 12:
            h += 12
        elif ap == "am" and h == 12:
            h = 0
        elif not ap and h < 8:
            h += 12
        days_ahead = (target_wd - now.weekday()) % 7
        if days_ahead == 0 and (h < now.hour or (h == now.hour and mi <= now.minute)):
            days_ahead = 7
        return (now + timedelta(days=days_ahead)).replace(hour=h, minute=mi, second=0, microsecond=0)

    bare = re.fullmatch(r"\s*(?:at|by|@)\s+(\d{1,2})(?::(\d\d))?\s*", p)
    if bare and 1 <= int(bare.group(1)) <= 12:  # "at 5" → the next 5:00 (5 pm if it's past 5 am)
        h, mi = int(bare.group(1)), int(bare.group(2) or 0)
        cands = [now.replace(hour=h % 12 + add, minute=mi) for add in (0, 12)]
        cands += [c + timedelta(days=1) for c in cands]
        return min(c for c in cands if c > now)
    p = _daypart_with_time(p)
    for pat, rep in ALIASES:
        p = re.sub(pat, rep, p)
    # "the 1st" / "15th" with no month → next time that day of the month comes round
    m = re.fullmatch(r"\s*(?:the\s+)?(\d{1,2})(?:st|nd|rd|th)\s*(.*)", p)
    if m and 1 <= int(m.group(1)) <= 31:
        day = int(m.group(1))
        rest = resolve_when(m.group(2), now) if m.group(2).strip() else None
        hour, minute = (rest.hour, rest.minute) if rest else (DEFAULT_HOUR, 0)
        y, mo = now.year, now.month
        for _ in range(13):
            if day <= calendar.monthrange(y, mo)[1]:
                cand = datetime(y, mo, day, hour, minute)
                if cand > now:
                    return cand
            y, mo = (y + 1, 1) if mo == 12 else (y, mo + 1)
    dt = dateparser.parse(p, settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": now})
    if dt is None:
        return None
    dt = dt.replace(second=0, microsecond=0, tzinfo=None)
    if not HAS_TIME.search(p):  # a day with no time → morning
        dt = dt.replace(hour=DEFAULT_HOUR, minute=0)
    return dt


def _parse_with_ollama(text, now):
    prompt = f"""Split this reminder request into JSON: "{text}"
Fields:
- "task": what to be reminded of, in the person's own words (keep their verb, e.g. "text" stays "text"), sentence case,
  without any date/time/repeat words (e.g. "Call mom")
- "when": the exact words from the request that say WHEN (date and/or time), without repeat words like "every".
  Examples: "sunday at 5pm", "in 20 minutes", "october 19", "tomorrow", "at 9am", "the 1st". "" if none.
- "repeat": "" unless the request says it repeats ("every", "daily", "weekly"…); then one of daily, weekdays, weekly,
  monthly, yearly, or every:<n>:<minutes|hours|days|weeks>. "next monday" is NOT a repeat.
Reply with JSON only."""
    from .chat import _ollama_up
    if not _ollama_up():  # a refused local port takes ~2 s on Windows — fall straight through to dateparser
        raise RuntimeError("Ollama isn't running")
    out = _ask_ollama(prompt)
    task = str(out.get("task", "")).strip()
    return {"text": task[:1].upper() + task[1:], "due": resolve_when(str(out.get("when", "")), now),
            "repeat": db.validate_repeat(out.get("repeat", "")), "priority": 0}


def _parse_with_dateparser(text, now):
    from dateparser.search import search_dates
    found = search_dates(text, settings={"PREFER_DATES_FROM": "future", "RELATIVE_BASE": now})
    due, task = None, text
    if found:
        phrase, due = found[-1]
        task = text.replace(phrase, "")
    rep = ""
    for word, rule in (("every day", "daily"), ("daily", "daily"), ("weekdays", "weekdays"),
                       ("every week", "weekly"), ("weekly", "weekly"), ("every month", "monthly"), ("monthly", "monthly")):
        if word in text.lower():
            rep = rule
            task = re.sub(word, "", task, flags=re.I)
    task = re.sub(r"^\s*(remind me( to)?|to)\s+", "", task, flags=re.I).strip(" ,.") or text
    return {"text": task[:1].upper() + task[1:], "due": due, "repeat": rep, "priority": 0}


def when(phrase, now=None):
    """A bare time phrase ('tomorrow 10am', 'in 3 hours', 'friday 2pm') → future datetime.
    Exact date math first; the AI parser only if that fails."""
    now = now or datetime.now().replace(second=0, microsecond=0)
    rule, rep_phrase = detect_repeat(phrase)
    clean_phrase = phrase
    if rep_phrase:
        clean_phrase = re.sub(re.escape(rep_phrase), " ", clean_phrase, flags=re.I).strip()
    dt = resolve_when(clean_phrase, now) if clean_phrase else None
    if dt is None:
        dt = resolve_when(phrase, now)
    if dt is None:
        dt = parse("x " + phrase, now)["due"]
    while dt <= now:
        dt += timedelta(days=1)
    return dt


def parse(text, now=None):
    """Returns dict(text, due: datetime, repeat, priority, engine). Never returns a due in the past."""
    if not text or not str(text).strip():
        return {}
    now = now or datetime.now().replace(second=0, microsecond=0)
    result = None
    for engine in (_parse_with_ollama, _parse_with_dateparser):
        try:
            result = engine(text, now)
            result["engine"] = "ollama" if engine is _parse_with_ollama else "dateparser"
            if result["text"]:
                break
        except Exception:
            continue
    if not result or not result["text"]:
        result = {"text": text.strip(), "due": None, "repeat": "", "priority": 0, "engine": "none"}
    rule, phrase = detect_repeat(text)
    exact = when_words(re.sub(re.escape(phrase), " ", text, flags=re.I) if rule else text)
    if exact:  # the time written in the request beats the model's reading of it
        try:
            d = resolve_when(exact, now)
            if d:
                result["due"] = d
                result["when_words"] = exact
        except Exception:
            pass
    if not rule and not re.search(r"\b(every|each|daily|weekly|monthly|yearly|annually|weekdays|mon(day)?\s*-\s*fri)", text, re.I):
        result["repeat"] = ""  # the model sometimes invents a repeat ("next monday" → weekly)
    if rule:  # deterministic beats the model's guess
        result["repeat"] = rule
        result["text"] = re.sub(re.escape(phrase), "", result["text"], flags=re.I).strip(" ,.") or result["text"]
    # drop leftover time words the model left in the task ("Gym at 6am" → "Gym")
    result["text"] = re.sub(r"\s+(at|by|@)\s+\d{1,2}(:\d\d)?\s*(am|pm)?\s*$", "", result["text"], flags=re.I)
    result["text"] = re.sub(r"\s{2,}", " ", result["text"]).strip(" ,.") or text.strip()
    result["priority"] = 1 if URGENT.search(text) else 0
    result["text"] = re.sub(r"^\s*(urgent|asap|important)\s*[:\-!]*\s*", "", result["text"], flags=re.I) or result["text"]
    if result["due"] is None:  # no time given → tomorrow morning
        result["due"] = (now + timedelta(days=1)).replace(hour=DEFAULT_HOUR, minute=0)
        result["guessed_time"] = True
    if result["due"] <= now:
        result["due"] = db.next_occurrence(result["due"], result["repeat"] or "daily", now)
    return result
