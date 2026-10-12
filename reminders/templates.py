"""Note templates — each one is a proven format for its situation (Cornell for classes, action-item
tables for meetings, timestamps for calls and videos…). {date} {time} {weekday} are filled in on use."""
from datetime import datetime

GROUPS = ["Meetings & calls", "Learning", "Thinking & planning", "Content & business", "Personal"]

TEMPLATES = [
    # ---------------- Meetings & calls ----------------
    dict(key="meeting", name="Meeting", icon="🤝", group="Meetings & calls", category="Meeting",
         best="Any scheduled meeting — team, client, group", why="Agenda → notes → decisions → owners. Nothing gets lost after the call.",
         words="meeting team standup sync agenda client call zoom", body="""# Meeting — {weekday} {date}

**When:** {time}  ·  **Where:** (Zoom / Discord / in person)
**Attendees:**
**Purpose:**

## Agenda
1.
2.
3.

## Notes
-

## Decisions
-

## Action items
- [ ] Task — **owner** — due
- [ ] Task — **owner** — due

## Follow-up
Next meeting:
Questions to bring:
"""),
    dict(key="discord", name="Discord / voice call", icon="🎧", group="Meetings & calls", category="Meeting",
         best="Live calls, community calls, Unleash U, Spaces", why="Timestamped moments so you can jump back to what mattered; links captured as they're shared.",
         words="discord voice call community live stream space server unleash group chat", body="""# Call — {weekday} {date}

**Server / channel:**
**Host & speakers:**
**Topic:**

## Key moments
- [{time}]
- [  :  ]
- [  :  ]

## Links & resources shared
-

## Ideas I want to try
-

## Follow-ups
- [ ] Message:
- [ ]
"""),
    dict(key="one_on_one", name="1-on-1 / mentor", icon="🧭", group="Meetings & calls", category="Meeting",
         best="Coaching, mentoring, check-ins with one person", why="Both sides' updates plus feedback and commitments — perfect for picking up next time.",
         words="mentor coach coaching one on one 1on1 check-in checkin advice", body="""# 1-on-1 with ____ — {date}

## Their updates
-

## My updates
-

## Advice & feedback
-

## Goals we talked about
-

## Commitments
- [ ] I will:
- [ ] They will:

**Next check-in:**
"""),
    dict(key="client", name="Client / interview call", icon="💼", group="Meetings & calls", category="Business",
         best="Sales calls, client discovery, interviews", why="Captures pain points in their own words, budget and timeline — everything you need for a proposal.",
         words="client sales discovery interview prospect customer lead pitch proposal", body="""# Call with ____ — {date}

**Company / person:**
**Contact:**
**Goal of the call:**

## Their situation
-

## Pain points (in their words)
> ""

## What they want
-

## Budget · Timeline
- Budget:
- Timeline:

## Next steps
- [ ] Send:
- [ ] Follow up on:
"""),
    # ---------------- Learning ----------------
    dict(key="cornell", name="Class / lecture (Cornell)", icon="🎓", group="Learning", category="YouTube / Learning",
         best="Classes, lectures, workshops, webinars", why="The Cornell method: notes while you listen, questions after, a summary in your own words — proven for remembering.",
         words="class lecture school course workshop webinar lesson study professor teacher", body="""# {date} — Topic:

**Course / source:**

## Notes
(write during the session — short phrases, not sentences)
-

## Cue questions
(after: turn each note into a question you could be quizzed on)
- ?
- ?

## Summary
(2–3 sentences in your own words)

"""),
    dict(key="video", name="YouTube / video", icon="▶️", group="Learning", category="YouTube / Learning",
         best="Tutorials, podcasts, YouTube videos", why="Timestamps let you jump straight back; 'Try this' turns watching into doing.",
         words="youtube video tutorial podcast watch watched channel creator", body="""# 🎬 Title:

**Channel / creator:**
**Link:**
**Watched:** {date}

## Timestamps
- 00:00 —
- 00:00 —

## Key ideas
1.
2.
3.

## Best quote
> ""

## Try this
- [ ]

**Rating:** ☆☆☆☆☆
"""),
    dict(key="book", name="Book / course", icon="📚", group="Learning", category="YouTube / Learning",
         best="Books, audiobooks, online courses (one note per chapter or module)", why="Big idea first, then concepts and quotes with page numbers, then what you'll actually change.",
         words="book read reading chapter audiobook course module author", body="""# 📖 Title — Chapter / module:

**Author / teacher:**

## The big idea
(one sentence)

## Key concepts
-

## Quotes
> "" (p. )

## How this applies to me
-

## Questions I still have
-
"""),
    dict(key="research", name="Research", icon="🔬", group="Learning", category="Tech",
         best="Looking something up, comparing tools, deep dives", why="Starts from a question and ends in a conclusion, with every source linked.",
         words="research compare comparison investigate look up deep dive find out which best tool", body="""# Research: (the question)

**Why I'm asking:**

## Sources
- [Title](link) — what it says
-

## Findings
-

## Conclusion
(the answer, in one or two lines)

## Open questions
-
"""),
    dict(key="study", name="Study / flashcards", icon="🧠", group="Learning", category="YouTube / Learning",
         best="Exams, certifications, memorizing anything", why="Active recall (Q/A) plus the Feynman test — explain it simply or you don't know it yet.",
         words="study exam test quiz memorize flashcards revise review certification", body="""# Study — Subject:

## Explain it simply (Feynman)
(as if teaching a 12-year-old)

## Flashcards
Q:
A:

Q:
A:

Q:
A:

## Weak spots to review
- [ ]
"""),
    # ---------------- Thinking & planning ----------------
    dict(key="brainstorm", name="Brainstorm", icon="💡", group="Thinking & planning", category="Idea",
         best="New ideas, names, angles, solutions", why="Separates wild ideas (no judging) from choosing the best — the two-step that produces better ideas.",
         words="brainstorm idea ideas names think concept creative", body="""# 💡 Brainstorm: (the goal)

**Constraints:**

## Raw ideas (no judging)
-
-
-
-
-

## Top 3
1.
2.
3.

## Next step
- [ ]
"""),
    dict(key="project", name="Project plan", icon="🗺️", group="Thinking & planning", category="Business",
         best="Starting anything with several steps", why="Defines 'done' up front, breaks it into milestones and tasks, and names the risks early.",
         words="project plan launch build roadmap milestone app website", body="""# 🗺️ Project:

**Goal:**
**Why it matters:**
**Deadline:**
**Done when:**

## Milestones
- [ ] 1.
- [ ] 2.
- [ ] 3.

## Tasks
- [ ]
- [ ]

## Tools & resources
-

## Risks → plan
- risk → what I'll do
"""),
    dict(key="decision", name="Decision", icon="⚖️", group="Thinking & planning", category="Personal",
         best="Big or tricky choices", why="Options side by side with pros, cons and a gut check — and a date to look back on it.",
         words="decide decision choose choice option should i pros cons", body="""# ⚖️ Decision:

**Decide by:**
**What matters most:**

## Option A —
- ➕
- ➖

## Option B —
- ➕
- ➖

## Gut feeling
(which one would you be relieved to pick?)

## Decision & why

**Revisit on:**
"""),
    dict(key="problem", name="Problem / troubleshooting", icon="🛠️", group="Thinking & planning", category="Tech",
         best="Bugs, PC issues, anything broken", why="What happened vs what should, steps to reproduce, what you tried — so you never solve the same thing twice.",
         words="bug error broken fix problem issue crash troubleshoot not working debug pc", body="""# 🛠️ Problem:

**What happened:**
**What should happen:**
**When it started:**

## Steps to reproduce
1.
2.

## Error message
```

```

## Tried
- [x]
- [ ]

## Fix / root cause

"""),
    dict(key="checklist", name="To-do (priorities)", icon="✅", group="Thinking & planning", category="To-do",
         best="Planning a day or a batch of tasks", why="Must / should / could keeps the important things first.",
         words="todo to-do tasks checklist list errands", body="""# ✅ To-do — {date}

## Must do
- [ ]
- [ ]

## Should do
- [ ]

## Could do
- [ ]
"""),
    # ---------------- Content & business ----------------
    dict(key="script", name="Video script / Short", icon="🎬", group="Content & business", category="Content",
         best="Shorts, Reels, TikToks, YouTube videos", why="Hook in the first 3 seconds, tight beats, one CTA — the structure short-form rewards.",
         words="script short shorts reel tiktok video content hook upload post caption", body="""# 🎬 Script:

**Platform:** (Shorts / Reels / TikTok / YouTube)  ·  **Length:**
**Audience:**

## Hook (first 3 seconds)

## Beats
1.
2.
3.

## Call to action

## Caption

**Hashtags:**
**Thumbnail / cover idea:**
"""),
    dict(key="content_plan", name="Content plan (week)", icon="📅", group="Content & business", category="Content",
         best="Planning a week of posts across channels", why="One table for the whole week — what, where, when, status.",
         words="content plan calendar week schedule posts uploads facebook youtube social", body="""# 📅 Content week of {date}

| Day | Platform | Idea | Status |
|-----|----------|------|--------|
| Mon |  |  | idea |
| Tue |  |  | idea |
| Wed |  |  | idea |
| Thu |  |  | idea |
| Fri |  |  | idea |
| Sat |  |  | idea |
| Sun |  |  | idea |

## Ideas backlog
-

## What did best last week
-
"""),
    dict(key="business", name="Business / client notes", icon="📈", group="Content & business", category="Business",
         best="Running a client, product or side business", why="Numbers, notes and next actions in one place you can scan quickly.",
         words="business numbers revenue sales money product client store gumroad depop", body="""# 📈 Business:

**Client / product:**

## Numbers
- Revenue:
- Costs:
- Key metric:

## Notes
-

## Action items
- [ ]
"""),
    # ---------------- Personal ----------------
    dict(key="journal", name="Daily journal", icon="🌅", group="Personal", category="Journal",
         best="End-of-day or morning reflection", why="Gratitude, wins and lessons — short prompts that take 5 minutes and build momentum.",
         words="journal diary day today reflection gratitude mood feel", body="""# 🌅 {weekday}, {date}

**Mood:** /10  ·  **Energy:** /10

## Grateful for
1.
2.
3.

## Today

## Wins
-

## Lessons
-

## Tomorrow's top 3
- [ ]
- [ ]
- [ ]
"""),
    dict(key="weekly", name="Weekly review", icon="🔁", group="Personal", category="Journal",
         best="Sunday reset / planning the week ahead", why="Look back, learn, then pick the big 3 for next week — the habit behind most productivity systems.",
         words="weekly review week sunday reset plan reflect", body="""# 🔁 Week of {date}

## Wins
-

## What didn't work
-

## Numbers
-

## Next week's big 3
1.
2.
3.

## Schedule check
- [ ] Calendar reviewed
- [ ] Reminders set
"""),
    dict(key="goal", name="Goal", icon="🎯", group="Personal", category="Personal",
         best="Setting a goal you actually want to hit", why="SMART goal + the why + daily habits + obstacles planned in advance.",
         words="goal goals resolution habit achieve target fitness", body="""# 🎯 Goal:

**Specific & measurable:**
**By when:**
**Why it matters to me:**

## Milestones
- [ ]
- [ ]

## Daily / weekly habits
-

## Obstacles → my plan
- If ____, then I will ____
"""),
]
BY_KEY = {t["key"]: t for t in TEMPLATES}


def fill(body):
    now = datetime.now()
    return (body.replace("{date}", now.strftime("%b %d, %Y").replace(" 0", " "))
                .replace("{time}", now.strftime("%I:%M %p").lstrip("0"))
                .replace("{weekday}", now.strftime("%A")))


def listing():
    return [{k: v for k, v in t.items()} for t in TEMPLATES]
