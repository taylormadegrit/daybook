"""Natural-language → reminder, fully local: Ollama qwen2.5:7b first, dateparser as fallback.
e.g. "call mom every sunday at 5pm" → text="Call mom", due=next Sunday 17:00, repeat=weekly
"""
import calendar
import json
import re
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


def resolve_when(phrase, now):
    """Exact date math (qwen is unreliable at weekdays): plain-English phrase → datetime or None."""
    import dateparser
    phrase = (phrase or "").strip()
    if not phrase:
        return None
    p = phrase.lower()
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
- "task": what to be reminded of, short imperative, sentence case, without any date/time/repeat words (e.g. "Call mom")
- "when": the exact words from the request that say WHEN (date and/or time), without repeat words like "every".
  Examples: "sunday at 5pm", "in 20 minutes", "october 19", "tomorrow", "at 9am", "the 1st". "" if none.
- "repeat": "" or one of daily, weekdays, weekly, monthly, yearly, or every:<n>:<minutes|hours|days|weeks>
Reply with JSON only."""
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
    dt = resolve_when(phrase, now)
    if dt is None:
        dt = parse("x " + phrase, now)["due"]
    while dt <= now:
        dt += timedelta(days=1)
    return dt


def parse(text, now=None):
    """Returns dict(text, due: datetime, repeat, priority, engine). Never returns a due in the past."""
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
