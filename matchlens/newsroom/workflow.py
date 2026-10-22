"""The MatchLens newsroom: a multi-agent workflow built with Microsoft Agent Framework.

Moment workflow (goals, red cards, big chances, 15-minute "state of play" reads):

    Analyst ──► Writer ──► FactChecker ──(approved)──► Localisers ──► Publisher
     (MCP tools)   ▲            │                       (one agent per language,
                   └──(retry)───┘                         run concurrently)

Big chances and state-of-play reads take a quick path (no Analyst call): Brief (code) ──► Writer ──► ...
Set MATCHLENS_ANALYST_KINDS to choose which moments get the Analyst (default: goal,red_card).

Recap workflow (half time, full time):

    RecapEditor ──► FactChecker ──(approved)──► Localisers ──► Publisher
     (MCP tools)  ▲      │
                  └(retry)┘

* The Analyst decides why the moment matters and may call MatchLens MCP tools for context.
* The Writer turns the brief into four texts for two audiences: on-screen caption, commentary,
  a plain-language fan line and a data-rich analyst line.
* The FactChecker is deterministic code, not a model: every number in the text must exist in the
  fact sheet or in a tool result the agents actually received. Failures go back to the writer with
  the exact problems (at most two retries); after that the safe template text is published.
* Localisers are separate agents per language and run concurrently.
* Every step is timed and recorded in a trace that ships with the narrative, so viewers and
  operators can see how each text was produced.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any

from agent_framework import Agent, Executor, WorkflowBuilder, WorkflowContext, handler

from ..facts import allowed_numbers, unsupported_numbers
from . import prompts, templates
from .llm import Provider, make_provider

log = logging.getLogger("matchlens.newsroom")

MAX_RETRIES = 2
AGENT_TIMEOUT_S = float(os.getenv("MATCHLENS_AGENT_TIMEOUT_S", "30"))
# moments that get the full Analyst step (with MCP tools); others go straight to the Writer to save one or two model calls
ANALYST_KINDS = set(filter(None, os.getenv("MATCHLENS_ANALYST_KINDS", "goal,red_card").split(",")))
MOMENT_KEYS = ("caption", "commentary", "fan", "analyst")
RECAP_KEYS = ("headline", "studio_script", "article", "social", "player_of_the_match")
FAN_JARGON = re.compile(r"\b(xg|ppda|field tilt|momentum index|expected goals)\b", re.I)


# --------------------------------------------------------------------------- helpers
def extract_json(text: str) -> dict | None:
    if not text:
        return None
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    try:
        v = json.loads(t)
        return v if isinstance(v, dict) else None
    except ValueError:
        pass
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            v = json.loads(m.group(0))
            return v if isinstance(v, dict) else None
        except ValueError:
            return None
    return None


def err_text(e: BaseException) -> str:
    """Short, user-readable error for the trace (exception type plus the service's message)."""
    msg = str(e).strip().replace("\n", " ")
    cause = e.__cause__ or e.__context__
    if cause and str(cause) not in msg:
        msg += f" | caused by {type(cause).__name__}: {str(cause).strip()}"
    return f"{type(e).__name__}: {msg[:400]}" if msg else type(e).__name__


def flatten_text(obj: Any) -> str:
    if isinstance(obj, dict):
        return " ".join(flatten_text(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(flatten_text(v) for v in obj)
    return str(obj) if obj is not None else ""


def check_moment(draft: dict | None, sheet: dict, evidence: list) -> list[str]:
    if not isinstance(draft, dict):
        return ["Output was not a JSON object with the required keys."]
    issues = []
    for k in MOMENT_KEYS:
        if not isinstance(draft.get(k), str) or not draft[k].strip():
            issues.append(f'Missing or empty "{k}".')
    if issues:
        return issues
    if len(draft["caption"]) > 70:
        issues.append(f'"caption" has {len(draft["caption"])} characters; the limit is 60.')
    for k in ("caption", "commentary", "fan"):                      # viewer-facing texts
        if FAN_JARGON.search(draft[k]):
            issues.append(f'"{k}" uses jargon (xG, PPDA, field tilt or momentum index); use plain words and percentages.')
    allowed = allowed_numbers(sheet, evidence)
    for k in MOMENT_KEYS:
        bad = unsupported_numbers(draft[k], allowed)
        if bad:
            issues.append(f'"{k}" contains numbers not found in the fact sheet or tool results: {", ".join(bad)}.')
    if sheet["kind"] == "goal":
        scorer = (sheet.get("scorer") or {}).get("name")
        if scorer and scorer not in draft["caption"] + draft["commentary"]:
            issues.append(f"The scorer {scorer} must be named in the caption or the commentary.")
    return issues


def check_recap(draft: dict | None, sheet: dict, evidence: list) -> list[str]:
    if not isinstance(draft, dict):
        return ["Output was not a JSON object with the required keys."]
    issues = [f'Missing "{k}".' for k in RECAP_KEYS if not draft.get(k)]
    if issues:
        return issues
    if len(str(draft["headline"])) > 80:
        issues.append('"headline" is longer than 70 characters.')
    if len(str(draft["social"])) > 280:
        issues.append('"social" is longer than 240 characters.')
    words = len(str(draft["studio_script"]).split())
    if not 40 <= words <= 150:
        issues.append(f'"studio_script" has {words} words; write 70-110.')
    for k in ("headline", "studio_script", "article", "social"):     # all read by viewers
        if FAN_JARGON.search(str(draft[k])):
            issues.append(f'"{k}" uses jargon (xG, PPDA, field tilt or momentum index); use plain words and percentages.')
    allowed = allowed_numbers(sheet, evidence)
    bad = unsupported_numbers(flatten_text(draft), allowed)
    if bad:
        issues.append(f"Numbers not found in the fact sheet or tool results: {', '.join(sorted(set(bad)))}.")
    potm = draft.get("player_of_the_match") or {}
    name = potm.get("name") if isinstance(potm, dict) else None
    if name and name not in json.dumps(sheet, ensure_ascii=False) + json.dumps(evidence, ensure_ascii=False):
        issues.append(f"Player of the match {name!r} does not appear in the match data.")
    return issues


def check_translation(original: dict, translated: dict | None, allowed: set) -> list[str]:
    if not isinstance(translated, dict) or set(translated) != set(original):
        return ["Translation must keep exactly the same keys."]
    bad = unsupported_numbers(flatten_text(translated), allowed)
    return [f"Translation changed numbers: {', '.join(bad)}."] if bad else []


# --------------------------------------------------------------------------- newsroom
class Newsroom:
    """Owns the model client, the agents and the MCP connection; runs one workflow per moment."""

    def __init__(self, provider: Provider | None = None, mcp_url: str | None = None):
        self.provider = provider or make_provider()
        self.mcp_url = mcp_url or os.getenv("MATCHLENS_MCP_URL", "http://127.0.0.1:8000/mcp/")
        self._mcp = None
        self._mcp_failed_at = 0.0
        self._mcp_lock = asyncio.Lock()
        self._agents: dict[str, Agent] = {}

    @property
    def enabled(self) -> bool:
        return self.provider.enabled

    # ---- MCP tools (connected lazily, retried at most once a minute after a failure)
    async def tools(self) -> list:
        if not self.enabled:
            return []
        async with self._mcp_lock:
            if self._mcp is not None:
                return [self._mcp]
            if time.monotonic() - self._mcp_failed_at < 60:
                return []
            try:
                from agent_framework import MCPStreamableHTTPTool
                tool = MCPStreamableHTTPTool(name="matchlens", url=self.mcp_url, request_timeout=10,
                                             description="MatchLens live match data (read-only)")
                await tool.__aenter__()
                self._mcp = tool
                log.info("Newsroom connected to MCP server at %s (%d tools)", self.mcp_url, len(tool.functions))
                return [tool]
            except Exception as e:
                self._mcp_failed_at = time.monotonic()
                log.warning("MCP server not reachable at %s (%s); agents continue without tools", self.mcp_url, e)
                return []

    async def aclose(self):
        if self._mcp is not None:
            try:
                await self._mcp.__aexit__(None, None, None)
            except Exception:
                pass
            self._mcp = None

    def agent(self, role: str, instructions: str) -> Agent:
        if role not in self._agents:
            self._agents[role] = Agent(self.provider.client, instructions, name=role)
        return self._agents[role]

    async def run_agent(self, role: str, instructions: str, prompt: str, use_tools: bool = False) -> dict:
        """Run one agent; returns parsed JSON, the raw tool results it received and timing."""
        t0 = time.perf_counter()
        tools = await self.tools() if use_tools else []
        agent = self.agent(role, instructions)
        resp = await asyncio.wait_for(agent.run(prompt, tools=tools or None), timeout=AGENT_TIMEOUT_S)
        evidence, calls = [], []
        for msg in resp.messages:
            for c in msg.contents:
                if c.type == "function_call":
                    calls.append(c.name)
                elif c.type == "function_result":
                    evidence.append(c.result if isinstance(c.result, str) else json.dumps(c.result, default=str))
        return {"data": extract_json(resp.text), "evidence": evidence, "tool_calls": calls,
                "ms": round(1000 * (time.perf_counter() - t0))}

    # ---- public entry point
    async def produce(self, sheet: dict, langs: list[str]) -> dict:
        """Run the workflow for one fact sheet. Never raises: falls back to templates on any error."""
        t0 = time.perf_counter()
        recap = sheet["kind"] in ("half_time", "full_time")
        if not self.enabled:
            return {"texts": {"en": templates.render(sheet, "en"), "es": templates.render(sheet, "es")},
                    "fallback": False, "trace": [], "moment_id": sheet["moment_id"], "kind": sheet["kind"],
                    "display_minute": sheet["display_minute"], "match_time_s": sheet["match_time_s"],
                    "status": "final", "source": "templates", "model": None, "latency_ms": 0}
        try:
            wf = (build_recap_workflow(self) if recap else build_moment_workflow(self) if sheet["kind"] in ANALYST_KINDS
                  else build_quick_workflow(self))
            result = await wf.run({"sheet": sheet, "langs": [l for l in langs if l != "en"]})
            out = result.get_outputs()
            payload = out[-1] if out else None
        except Exception as e:
            log.exception("Newsroom workflow failed for %s", sheet.get("moment_id"))
            payload = None
            err = str(e)
        else:
            err = None
        if payload is None:
            payload = {"texts": {"en": templates.render(sheet, "en"), "es": templates.render(sheet, "es")},
                       "fallback": True, "trace": [{"step": "workflow", "ok": False, "error": err}]}
        payload.update({"moment_id": sheet["moment_id"], "kind": sheet["kind"], "display_minute": sheet["display_minute"],
                        "match_time_s": sheet["match_time_s"], "status": "final",
                        "source": self.provider.name, "model": self.provider.model,
                        "latency_ms": round(1000 * (time.perf_counter() - t0))})
        return payload


# --------------------------------------------------------------------------- executors
def _trace(ctx: WorkflowContext, row: dict):
    tr = ctx.get_state("trace", []) or []
    tr.append(row)
    ctx.set_state("trace", tr)


class AnalystExecutor(Executor):
    def __init__(self, nr: Newsroom):
        super().__init__(id="analyst")
        self.nr = nr

    @handler
    async def handle(self, job: dict, ctx: WorkflowContext[dict]) -> None:
        sheet = job["sheet"]
        ctx.set_state("sheet", sheet)
        ctx.set_state("langs", job["langs"])
        ctx.set_state("evidence", [])
        try:
            r = await self.nr.run_agent("analyst", prompts.ANALYST,
                                        "FACT SHEET:\n" + json.dumps(sheet, ensure_ascii=False), use_tools=True)
            brief = r["data"] or {}
            ctx.set_state("evidence", r["evidence"])
            _trace(ctx, {"step": "analyst", "ok": bool(r["data"]), "ms": r["ms"], "tool_calls": r["tool_calls"]})
        except Exception as e:                       # the writer can still work from the fact sheet alone
            brief = {}
            _trace(ctx, {"step": "analyst", "ok": False, "error": err_text(e)})
        await ctx.send_message({"brief": brief, "attempt": 0})


class WriterExecutor(Executor):
    def __init__(self, nr: Newsroom):
        super().__init__(id="writer")
        self.nr = nr

    @handler
    async def handle(self, msg: dict, ctx: WorkflowContext[dict]) -> None:
        sheet = ctx.get_state("sheet")
        brief = msg.get("brief", ctx.get_state("brief", {}))
        ctx.set_state("brief", brief)
        attempt = msg.get("attempt", 0) + 1
        prompt = ("FACT SHEET:\n" + json.dumps(sheet, ensure_ascii=False) +
                  "\n\nANALYST BRIEF:\n" + json.dumps(brief, ensure_ascii=False))
        if msg.get("feedback"):
            prompt += ("\n\nYOUR PREVIOUS DRAFT:\n" + json.dumps(msg.get("draft"), ensure_ascii=False) +
                       "\n\nFACT-CHECK FEEDBACK (fix all of these):\n- " + "\n- ".join(msg["feedback"]))
        try:
            r = await self.nr.run_agent("writer", prompts.WRITER, prompt)
            draft = r["data"]
            _trace(ctx, {"step": "writer", "attempt": attempt, "ok": draft is not None, "ms": r["ms"]})
        except Exception as e:
            draft = None
            _trace(ctx, {"step": "writer", "attempt": attempt, "ok": False, "error": err_text(e)})
        await ctx.send_message({"draft": draft, "attempt": attempt})


class RecapEditorExecutor(Executor):
    def __init__(self, nr: Newsroom):
        super().__init__(id="recap_editor")
        self.nr = nr

    @handler
    async def handle(self, msg: dict, ctx: WorkflowContext[dict]) -> None:
        if "sheet" in msg:                            # first call: the job itself
            ctx.set_state("sheet", msg["sheet"])
            ctx.set_state("langs", msg["langs"])
            ctx.set_state("evidence", [])
        sheet = ctx.get_state("sheet")
        attempt = msg.get("attempt", 0) + 1
        which = "the half-time break" if sheet["kind"] == "half_time" else "the full-time whistle"
        prompt = "FACT SHEET:\n" + json.dumps(sheet, ensure_ascii=False)
        if msg.get("feedback"):
            prompt += ("\n\nYOUR PREVIOUS DRAFT:\n" + json.dumps(msg.get("draft"), ensure_ascii=False) +
                       "\n\nFACT-CHECK FEEDBACK (fix all of these):\n- " + "\n- ".join(msg["feedback"]))
        try:
            r = await self.nr.run_agent("recap_editor", prompts.RECAP.replace("{which}", which), prompt,
                                        use_tools=attempt == 1)
            ctx.set_state("evidence", (ctx.get_state("evidence", []) or []) + r["evidence"])
            draft = r["data"]
            _trace(ctx, {"step": "recap_editor", "attempt": attempt, "ok": draft is not None, "ms": r["ms"],
                         "tool_calls": r["tool_calls"]})
        except Exception as e:
            draft = None
            _trace(ctx, {"step": "recap_editor", "attempt": attempt, "ok": False, "error": err_text(e)})
        await ctx.send_message({"draft": draft, "attempt": attempt})


class FactCheckExecutor(Executor):
    """Deterministic guardrail: numbers must be grounded, formats respected, key facts named."""

    def __init__(self, recap: bool):
        super().__init__(id="fact_checker")
        self.recap = recap

    @handler
    async def handle(self, msg: dict, ctx: WorkflowContext[dict]) -> None:
        sheet, evidence = ctx.get_state("sheet"), ctx.get_state("evidence", []) or []
        draft, attempt = msg.get("draft"), msg["attempt"]
        issues = (check_recap if self.recap else check_moment)(draft, sheet, evidence)
        _trace(ctx, {"step": "fact_check", "attempt": attempt, "ok": not issues, "issues": issues[:5]})
        if not issues:
            await ctx.send_message({"approved": draft, "fallback": False})
        elif attempt <= MAX_RETRIES:
            await ctx.send_message({"retry": True, "feedback": issues, "draft": draft, "attempt": attempt})
        else:
            await ctx.send_message({"approved": templates.render(sheet, "en"), "fallback": True})


class LocaliserExecutor(Executor):
    def __init__(self, nr: Newsroom):
        super().__init__(id="localisers")
        self.nr = nr

    @handler
    async def handle(self, msg: dict, ctx: WorkflowContext[dict]) -> None:
        sheet, evidence = ctx.get_state("sheet"), ctx.get_state("evidence", []) or []
        langs = ctx.get_state("langs", []) or []
        original = msg["approved"]
        texts = {"en": original}
        if msg.get("fallback"):                      # templates already exist in Spanish; skip model calls
            texts["es"] = templates.render(sheet, "es")
        else:
            allowed = allowed_numbers(sheet, evidence, original)

            async def one(lang):
                r = await self.nr.run_agent(f"localiser_{lang}", prompts.localiser(lang),
                                            json.dumps(original, ensure_ascii=False))
                issues = check_translation(original, r["data"], allowed)
                _trace(ctx, {"step": f"localiser_{lang}", "ok": not issues, "ms": r["ms"], "issues": issues[:3]})
                return lang, (r["data"] if not issues else None)

            results = await asyncio.gather(*(one(l) for l in langs), return_exceptions=True)
            for res in results:
                if isinstance(res, Exception):
                    _trace(ctx, {"step": "localiser", "ok": False, "error": err_text(res)})
                    continue
                lang, data = res
                if data:
                    texts[lang] = data
                elif lang == "es":
                    texts["es"] = templates.render(sheet, "es")
        await ctx.send_message({"texts": texts, "fallback": msg.get("fallback", False)})


class PublisherExecutor(Executor):
    def __init__(self):
        super().__init__(id="publisher")

    @handler
    async def handle(self, msg: dict, ctx: WorkflowContext[dict, dict]) -> None:
        await ctx.yield_output({"texts": msg["texts"], "fallback": msg["fallback"],
                                "trace": ctx.get_state("trace", []) or []})


def build_moment_workflow(nr: Newsroom):
    analyst, writer, checker = AnalystExecutor(nr), WriterExecutor(nr), FactCheckExecutor(recap=False)
    localisers, publisher = LocaliserExecutor(nr), PublisherExecutor()
    return (WorkflowBuilder(name="moment_newsroom", start_executor=analyst, max_iterations=20)
            .add_edge(analyst, writer)
            .add_edge(writer, checker)
            .add_edge(checker, writer, condition=lambda m: bool(m.get("retry")))
            .add_edge(checker, localisers, condition=lambda m: "approved" in m)
            .add_edge(localisers, publisher)
            .build())


class BriefExecutor(Executor):
    """Quick path: no model call. The fact sheet itself is the brief (used for big chances and state-of-play reads)."""

    def __init__(self):
        super().__init__(id="brief")

    @handler
    async def handle(self, job: dict, ctx: WorkflowContext[dict]) -> None:
        ctx.set_state("sheet", job["sheet"])
        ctx.set_state("langs", job["langs"])
        ctx.set_state("evidence", [])
        await ctx.send_message({"brief": {}, "attempt": 0})


def build_quick_workflow(nr: Newsroom):
    brief, writer, checker = BriefExecutor(), WriterExecutor(nr), FactCheckExecutor(recap=False)
    localisers, publisher = LocaliserExecutor(nr), PublisherExecutor()
    return (WorkflowBuilder(name="moment_newsroom_quick", start_executor=brief, max_iterations=20)
            .add_edge(brief, writer)
            .add_edge(writer, checker)
            .add_edge(checker, writer, condition=lambda m: bool(m.get("retry")))
            .add_edge(checker, localisers, condition=lambda m: "approved" in m)
            .add_edge(localisers, publisher)
            .build())


def build_recap_workflow(nr: Newsroom):
    editor, checker = RecapEditorExecutor(nr), FactCheckExecutor(recap=True)
    localisers, publisher = LocaliserExecutor(nr), PublisherExecutor()
    return (WorkflowBuilder(name="recap_newsroom", start_executor=editor, max_iterations=20)
            .add_edge(editor, checker)
            .add_edge(checker, editor, condition=lambda m: bool(m.get("retry")))
            .add_edge(checker, localisers, condition=lambda m: "approved" in m)
            .add_edge(localisers, publisher)
            .build())
