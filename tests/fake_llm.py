"""A scripted stand-in for the Foundry model, so the newsroom can be tested offline.

It recognises which agent is calling from the instructions, and answers with valid JSON.
`invent_number_first=True` makes the writer's first draft contain an unsupported number,
which the fact checker must reject.
"""
from __future__ import annotations

import json
import re

from agent_framework import (BaseChatClient, ChatMiddlewareLayer, ChatResponse, Content,
                             FunctionInvocationLayer, Message)


def _system_text(messages, options) -> str:
    parts = [m.text or "" for m in messages if str(m.role) in ("system", "Role.SYSTEM", "developer")]
    if isinstance(options, dict) and options.get("instructions"):
        parts.append(str(options["instructions"]))
    return " ".join(parts)


class ScriptedChatClient(FunctionInvocationLayer, ChatMiddlewareLayer, BaseChatClient):
    def __init__(self, invent_number_first: bool = True, call_tools: bool = True, fail_roles: tuple = ()):
        super().__init__()
        self.invent = invent_number_first
        self.call_tools = call_tools
        self.fail_roles = fail_roles
        self.calls: list[str] = []
        self.writer_calls = 0

    async def _inner_get_response(self, *, messages, stream, options, **kwargs):
        sysmsg = _system_text(messages, options)
        user = next((m.text for m in reversed(messages) if str(m.role) in ("user", "Role.USER")), "") or ""
        has_tool_result = any(c.type == "function_result" for m in messages for c in m.contents)
        role = ("analyst" if "match analyst" in sysmsg else "writer" if "lead writer" in sysmsg
                else "recap" if "studio editor" in sysmsg else "localiser" if "broadcaster and editor" in sysmsg else "?")
        self.calls.append(role)
        if role in self.fail_roles:
            raise RuntimeError(f"simulated {role} outage")
        sheet = _sheet_from(user)

        def say(obj):
            return ChatResponse(messages=[Message(role="assistant", contents=[json.dumps(obj, ensure_ascii=False)])])

        tools_available = bool(isinstance(options, dict) and options.get("tools"))
        if role in ("analyst", "recap") and self.call_tools and tools_available and not has_tool_result and sheet:
            return ChatResponse(messages=[Message(role="assistant", contents=[Content.from_function_call(
                call_id="call_1", name="get_match_state", arguments={"match_id": sheet["match_id"]})])])
        if role == "analyst":
            return say({"angle": f"{sheet['kind']} changes the game", "why_it_matters": "It shifts the balance.",
                        "key_facts": [f"Score {sheet['match']['score']['home']}-{sheet['match']['score']['away']}"],
                        "tone": "excited"})
        if role == "writer":
            self.writer_calls += 1
            m = sheet["match"]
            name = ((sheet.get("scorer") or sheet.get("player") or {}).get("name")) or sheet["home"]["short_name"]
            cap = f"{name} at {m['minute']}"
            if self.invent and "FACT-CHECK FEEDBACK" not in user:
                return say({"caption": cap, "commentary": f"{name} makes it count, 487 fans agree.",
                            "fan": "A huge moment.", "analyst": "Big swing."})
            return say({"caption": cap, "commentary": f"{name} makes it count at {m['minute']}.",
                        "fan": f"The score is now {m['score']['home']}-{m['score']['away']}.",
                        "analyst": f"Possession {m['possession_pct']['home']}% for the home side."})
        if role == "recap":
            m, top = sheet["match"], (sheet.get("top_players") or [{"name": "?", "rating": 6}])[0]
            script = " ".join(["The"] + ["story"] * 60 + [f"ends {m['score']['home']}-{m['score']['away']}."])
            return say({"headline": f"{sheet['home']['short_name']} {m['score']['home']}-{m['score']['away']} {sheet['away']['short_name']}",
                        "studio_script": script, "article": script + " " + script,
                        "social": f"#{sheet['home']['abbr']} {m['score']['home']}-{m['score']['away']} #{sheet['away']['abbr']}",
                        "player_of_the_match": {"name": top["name"], "reason": f"Rated {top['rating']}."}})
        if role == "localiser":
            obj = json.loads(user)
            return say({k: (f"[es] {v}" if isinstance(v, str) else v) for k, v in obj.items()})
        return say({})


def _sheet_from(user: str) -> dict | None:
    m = re.search(r"FACT SHEET:\n(\{.*?\})(?:\n\n|$)", user, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None
