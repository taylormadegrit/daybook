"""
When Claude runs out of usage (Pro/Max limit, API credits, overload), a chat on a claude: model
carries on in Gemini with the same conversation instead of failing.
Uses fake `claude` / `gemini` CLIs, so no account or network is needed.
"""
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

from reminders import chat


def _fake_cli(folder, name, py_body):
    script = os.path.join(folder, name + ".py")
    with open(script, "w", encoding="utf-8") as f:
        f.write(py_body)
    bat = os.path.join(folder, name + ".bat")
    with open(bat, "w", encoding="utf-8") as f:
        f.write(f'@"{sys.executable}" "{script}" %*\n')
    return bat


CLAUDE_LIMIT = """import json, sys
sys.stdin.read()
print(json.dumps({"type": "system", "session_id": "s1"}))
print(json.dumps({"type": "result", "is_error": True, "result": "Claude AI usage limit reached|1760000000", "session_id": "s1"}))
sys.exit(1)
"""
CLAUDE_OK = """import json, sys
sys.stdin.read()
print(json.dumps({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "Hi from Claude"}}}))
print(json.dumps({"type": "result", "is_error": False, "session_id": "s2"}))
"""
GEMINI = """import sys
prompt = sys.stdin.read()
print("Hi from Gemini" + (" (saw history)" if "remember the milk" in prompt else ""))
"""


def _events(gen):
    out = []
    for chunk in gen:
        lines = chunk.strip().split("\n")
        out.append((lines[0][len("event: "):], json.loads(lines[1][len("data: "):])))
    return out


class TestGeminiFallback(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        chat._claude_limited_until = 0.0
        with chat._con() as con:
            cur = con.execute("INSERT INTO chats (model, persona, tools, created, updated) VALUES (?,?,?,?,?)",
                              ("claude:sonnet", "Assistant", "", chat._now(), chat._now()))
            self.cid = cur.lastrowid
        chat.add_msg(self.cid, "user", "please remember the milk")

    def tearDown(self):
        chat._claude_limited_until = 0.0
        self.tmp.cleanup()

    def _run(self, claude_body, gemini=True):
        claude = _fake_cli(self.tmp.name, "claude", claude_body)
        gem = _fake_cli(self.tmp.name, "gemini", GEMINI) if gemini else None
        with mock.patch.object(chat, "claude_cli", return_value=claude), mock.patch.object(chat, "gemini_cli", return_value=gem):
            return _events(chat.generate_claude(self.cid))

    def test_limit_falls_back_to_gemini_with_history(self):
        ev = self._run(CLAUDE_LIMIT)
        kinds = [k for k, _ in ev]
        self.assertIn("notice", kinds)
        self.assertNotIn("error", kinds)
        text = "".join(d.get("t", "") for k, d in ev if k == "token")
        self.assertIn("Hi from Gemini (saw history)", text)
        last = chat.history(self.cid)[-1]
        self.assertEqual(last["role"], "assistant")
        self.assertEqual(last["meta"]["model"], "gemini:default")
        self.assertTrue(chat.claude_limited())

    def test_cooldown_skips_claude(self):
        chat._mark_claude_limited()
        ev = self._run(CLAUDE_OK)  # Claude would answer, but we're inside the cooldown
        text = "".join(d.get("t", "") for k, d in ev if k == "token")
        self.assertIn("Hi from Gemini", text)
        self.assertNotIn("Hi from Claude", text)

    def test_claude_ok_no_fallback(self):
        ev = self._run(CLAUDE_OK)
        text = "".join(d.get("t", "") for k, d in ev if k == "token")
        self.assertIn("Hi from Claude", text)
        self.assertNotIn("notice", [k for k, _ in ev])
        self.assertFalse(chat.claude_limited())

    def test_limit_without_gemini_explains(self):
        ev = self._run(CLAUDE_LIMIT, gemini=False)
        errs = [d["message"] for k, d in ev if k == "error"]
        self.assertTrue(errs and "Gemini CLI" in errs[0])


if __name__ == "__main__":
    unittest.main()
