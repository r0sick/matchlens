"""Transfer Advisor: should I hold, watch or sell this player? A Microsoft Agent Framework workflow.

    Scout ──► Advisor ──► FactChecker ──(approved)──► Localiser ──► Publisher
   (code)    (agent,  ▲        │
              MCP)    └(retry)─┘

* Scout is deterministic code: it computes the signals (form vs price, season output, finishing luck,
  minutes trend, next fixtures), the HOLD / WATCH / SELL verdict and affordable replacements.
  The verdict is decided by transparent rules, never by the model.
* Advisor is an agent that explains the verdict to the manager in plain words. It may call the
  MatchLens MCP tool get_fantasy_player to compare a replacement.
* FactChecker is code: every number must come from the scout sheet or a tool result, the verdict
  must be the scout's, and only listed replacements may be recommended. At most two retries,
  then a template explanation is published.
"""
from __future__ import annotations

import json
import logging
import time

from agent_framework import Executor, WorkflowBuilder, WorkflowContext, handler

from ..facts import allowed_numbers, unsupported_numbers
from ..newsroom import prompts
from ..newsroom.workflow import MAX_RETRIES, check_translation, err_text, flatten_text
from . import season as S

log = logging.getLogger("matchlens.fantasy")

KEYS = ("headline", "explanation", "replacement_note")
VERDICT_WORDS = {"en": {"HOLD": "Hold", "WATCH": "Watch", "SELL": "Sell"},
                 "es": {"HOLD": "Mantener", "WATCH": "Vigilar", "SELL": "Vender"}}

ADVISOR = f"""You are the Transfer Advisor in a fantasy football app. A manager asks whether to keep a player.
You receive a SCOUT SHEET (JSON) with the player's signals, a verdict already decided by the scout's rules
(HOLD, WATCH or SELL) and up to three affordable replacements. Explain the verdict honestly and simply.

- "headline": at most 70 characters; must start with the verdict word (Hold, Watch or Sell) and the player's name.
- "explanation": 2-3 sentences. Name the two or three reasons that weigh most (the largest "effect" values),
  with their numbers. Say "goals vs expected goals" rather than "xG" at least once. Be fair: if the player
  is unlucky rather than bad, say so.
- "replacement_note": 1 sentence. For SELL or WATCH, name the best replacement from the list and why;
  for HOLD, say what would change your mind. Never recommend a player who is not in the list.

You may call get_fantasy_player once to check a replacement, only if it adds something.
{prompts.GROUNDING} Do not change the verdict.
If you receive FACT-CHECK FEEDBACK, fix exactly the problems listed.

Return only JSON: {{"headline": "...", "explanation": "...", "replacement_note": "..."}}"""


def scout(player_id: str, squad: list[str], matchday: int, bank: float = 0.0) -> dict:
    sig = S.signals(player_id, matchday)
    v = S.verdict(sig)
    return {"kind": "transfer_advice", "matchday": matchday, "bank": bank, "player": sig,
            "verdict": v["verdict"], "verdict_score": v["score"], "reasons": v["reasons"],
            "replacements": S.replacements(player_id, squad, matchday, bank)}


def template(sheet: dict, lang: str = "en") -> dict:
    p, v, reps = sheet["player"], sheet["verdict"], sheet["replacements"]
    top = sorted(sheet["reasons"], key=lambda r: -abs(r["effect"]))[:2]
    word = VERDICT_WORDS.get(lang, VERDICT_WORDS["en"])[v]
    if lang == "es":
        why = "; ".join(r["text"] for r in top)
        rep = (f"Mejor alternativa asequible: {reps[0]['name']} ({reps[0]['club']}, {reps[0]['price']}m)."
               if reps and v != "HOLD" else "Revísalo de nuevo tras la próxima jornada.")
        return {"headline": f"{word}: {p['name']} ({p['club']})", "explanation": f"Factores clave: {why}.",
                "replacement_note": rep}
    why = "; ".join(r["text"] for r in top)
    rep = (f"Best affordable alternative: {reps[0]['name']} ({reps[0]['club']}, {reps[0]['price']}m)."
           if reps and v != "HOLD" else "Check again after the next matchday.")
    return {"headline": f"{word}: {p['name']} ({p['club']})", "explanation": f"Key factors: {why}.",
            "replacement_note": rep}


def check_advice(draft: dict | None, sheet: dict, evidence: list) -> list[str]:
    if not isinstance(draft, dict):
        return ["Output was not a JSON object with the required keys."]
    issues = [f'Missing or empty "{k}".' for k in KEYS if not isinstance(draft.get(k), str) or not draft[k].strip()]
    if issues:
        return issues
    word = VERDICT_WORDS["en"][sheet["verdict"]]
    if not draft["headline"].lower().startswith(word.lower()):
        issues.append(f'"headline" must start with the verdict "{word}".')
    if len(draft["headline"]) > 80:
        issues.append('"headline" is longer than 70 characters.')
    others = {w for k, w in VERDICT_WORDS["en"].items() if k != sheet["verdict"]}
    if any(draft["headline"].lower().startswith(o.lower()) for o in others):
        issues.append("Do not change the verdict.")
    if sheet["player"]["name"] not in draft["headline"]:
        issues.append(f'"headline" must name {sheet["player"]["name"]}.')
    allowed = allowed_numbers(sheet, evidence)
    bad = unsupported_numbers(flatten_text(draft), allowed)
    if bad:
        issues.append(f"Numbers not found in the scout sheet or tool results: {', '.join(sorted(set(bad)))}.")
    listed = {r["name"] for r in sheet["replacements"]} | {sheet["player"]["name"]}
    pool = {P["name"] for P in S.load()["players"].values()}
    named = {n for n in pool if n in draft["replacement_note"] and len(n) > 3}
    stray = named - listed - {n for n in named for m in listed if n in m}
    if stray:
        issues.append(f"Only recommend players from the replacements list (not {', '.join(sorted(stray))}).")
    if sheet["verdict"] != "HOLD" and sheet["replacements"] and \
            not any(r["name"] in draft["replacement_note"] for r in sheet["replacements"]):
        issues.append('"replacement_note" must name one of the listed replacements.')
    return issues


# --------------------------------------------------------------------------- executors
def _trace(ctx: WorkflowContext, row: dict):
    tr = ctx.get_state("trace", []) or []
    tr.append(row)
    ctx.set_state("trace", tr)


class ScoutExecutor(Executor):
    def __init__(self):
        super().__init__(id="scout")

    @handler
    async def handle(self, job: dict, ctx: WorkflowContext[dict]) -> None:
        t0 = time.perf_counter()
        sheet = scout(job["player_id"], job["squad"], job["matchday"], job.get("bank", 0.0))
        ctx.set_state("sheet", sheet)
        ctx.set_state("lang", job.get("lang", "en"))
        ctx.set_state("evidence", [])
        _trace(ctx, {"step": "scout", "ok": True, "ms": round(1000 * (time.perf_counter() - t0)),
                     "verdict": sheet["verdict"]})
        await ctx.send_message({"attempt": 0})


class AdvisorExecutor(Executor):
    def __init__(self, nr):
        super().__init__(id="advisor")
        self.nr = nr

    @handler
    async def handle(self, msg: dict, ctx: WorkflowContext[dict]) -> None:
        sheet = ctx.get_state("sheet")
        attempt = msg.get("attempt", 0) + 1
        prompt = "SCOUT SHEET:\n" + json.dumps(sheet, ensure_ascii=False)
        if msg.get("feedback"):
            prompt += ("\n\nYOUR PREVIOUS DRAFT:\n" + json.dumps(msg.get("draft"), ensure_ascii=False) +
                       "\n\nFACT-CHECK FEEDBACK (fix all of these):\n- " + "\n- ".join(msg["feedback"]))
        try:
            r = await self.nr.run_agent("transfer_advisor", ADVISOR, prompt, use_tools=attempt == 1)
            ctx.set_state("evidence", (ctx.get_state("evidence", []) or []) + r["evidence"])
            draft = r["data"]
            _trace(ctx, {"step": "advisor", "attempt": attempt, "ok": draft is not None, "ms": r["ms"],
                         "tool_calls": r["tool_calls"]})
        except Exception as e:
            draft = None
            _trace(ctx, {"step": "advisor", "attempt": attempt, "ok": False, "error": err_text(e)})
        await ctx.send_message({"draft": draft, "attempt": attempt})


class AdviceCheckExecutor(Executor):
    def __init__(self):
        super().__init__(id="fact_checker")

    @handler
    async def handle(self, msg: dict, ctx: WorkflowContext[dict]) -> None:
        sheet, evidence = ctx.get_state("sheet"), ctx.get_state("evidence", []) or []
        draft, attempt = msg.get("draft"), msg["attempt"]
        issues = check_advice(draft, sheet, evidence)
        _trace(ctx, {"step": "fact_check", "attempt": attempt, "ok": not issues, "issues": issues[:5]})
        if not issues:
            await ctx.send_message({"approved": draft, "fallback": False})
        elif attempt <= MAX_RETRIES:
            await ctx.send_message({"retry": True, "feedback": issues, "draft": draft, "attempt": attempt})
        else:
            await ctx.send_message({"approved": template(sheet, "en"), "fallback": True})


class AdviceLocaliserExecutor(Executor):
    def __init__(self, nr):
        super().__init__(id="localiser")
        self.nr = nr

    @handler
    async def handle(self, msg: dict, ctx: WorkflowContext[dict, dict]) -> None:
        sheet, lang = ctx.get_state("sheet"), ctx.get_state("lang", "en")
        texts = {"en": msg["approved"]}
        if lang != "en":
            if msg["fallback"]:
                texts[lang] = template(sheet, lang) if lang == "es" else msg["approved"]
            else:
                try:
                    r = await self.nr.run_agent(f"localiser_{lang}", prompts.localiser(lang),
                                                json.dumps(msg["approved"], ensure_ascii=False))
                    allowed = allowed_numbers(sheet, ctx.get_state("evidence", []) or [], msg["approved"])
                    issues = check_translation(msg["approved"], r["data"], allowed)
                    _trace(ctx, {"step": f"localiser_{lang}", "ok": not issues, "ms": r["ms"], "issues": issues[:3]})
                    if not issues:
                        texts[lang] = r["data"]
                except Exception as e:
                    _trace(ctx, {"step": f"localiser_{lang}", "ok": False, "error": err_text(e)})
                if lang not in texts and lang == "es":
                    texts["es"] = template(sheet, "es")
        await ctx.yield_output({"texts": texts, "fallback": msg["fallback"],
                                "trace": ctx.get_state("trace", []) or []})


def build_advice_workflow(nr):
    sc, adv, chk, loc = ScoutExecutor(), AdvisorExecutor(nr), AdviceCheckExecutor(), AdviceLocaliserExecutor(nr)
    return (WorkflowBuilder(name="transfer_advisor", start_executor=sc, max_iterations=12)
            .add_edge(sc, adv)
            .add_edge(adv, chk)
            .add_edge(chk, adv, condition=lambda m: bool(m.get("retry")))
            .add_edge(chk, loc, condition=lambda m: "approved" in m)
            .build())


async def advise(nr, player_id: str, squad: list[str], matchday: int, bank: float = 0.0, lang: str = "en") -> dict:
    """Never raises: returns the scout sheet plus texts (AI when available, otherwise templates)."""
    t0 = time.perf_counter()
    sheet = scout(player_id, squad, matchday, bank)
    base = {"sheet": sheet, "verdict": sheet["verdict"], "player_id": player_id, "matchday": matchday}
    if nr is None or not nr.enabled:
        texts = {"en": template(sheet, "en")}
        if lang != "en":
            texts[lang] = template(sheet, lang) if lang == "es" else texts["en"]
        return base | {"texts": texts, "source": "templates", "model": None, "fallback": False, "trace": [],
                       "latency_ms": round(1000 * (time.perf_counter() - t0))}
    try:
        result = await build_advice_workflow(nr).run({"player_id": player_id, "squad": squad, "matchday": matchday,
                                                      "bank": bank, "lang": lang})
        outs = result.get_outputs()
        payload = outs[-1] if outs else None
    except Exception as e:
        log.exception("Transfer advisor failed")
        payload = {"texts": {"en": template(sheet, "en")}, "fallback": True,
                   "trace": [{"step": "workflow", "ok": False, "error": err_text(e)}]}
    if payload is None:
        payload = {"texts": {"en": template(sheet, "en")}, "fallback": True, "trace": []}
    return base | payload | {"source": nr.provider.name, "model": nr.provider.model,
                             "latency_ms": round(1000 * (time.perf_counter() - t0))}
