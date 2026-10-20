"""Check the AI newsroom against your model without starting the web app.

    python -m matchlens.newsroom                 # first goal of a season match, English + Spanish
    python -m matchlens.newsroom --kind full_time --langs es,fr

Prints which provider is configured, the texts each agent produced and the workflow trace.
MCP tools are only available while the web server is running (uvicorn on port 8000);
without it the agents work from the fact sheet alone.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging

from matchsim.replay import load_match

from ..facts import MomentDetector
from ..models import load_models
from ..state import MatchState
from . import Newsroom

KEY_TYPES = {"shot", "goal", "card", "substitution"}


def sheets_for(path: str) -> list[dict]:
    m = load_match(path)
    st, det, keys, out = MatchState(m["metadata"], load_models()), MomentDetector(m["metadata"]), [], []
    for ev in m["events"]:
        sig = st.update(ev)
        if ev["type"] in KEY_TYPES:
            keys.append({**ev, "details": {k: v for k, v in ev["details"].items() if k not in ("key_pass", "assist")}})
        out += det.observe(ev, sig, st, keys)
    return out


async def main():
    ap = argparse.ArgumentParser(prog="python -m matchlens.newsroom")
    ap.add_argument("--match", default="data/season_2026-27/matches/AUR26-MD10-KMU-THR")
    ap.add_argument("--kind", default="goal", choices=["goal", "red_card", "big_chance", "state_of_play", "half_time", "full_time"])
    ap.add_argument("--langs", default="es")
    a = ap.parse_args()
    logging.basicConfig(level=logging.WARNING)
    for noisy in ("httpx", "mcp", "agent_framework", "azure"):
        logging.getLogger(noisy).setLevel(logging.ERROR)

    nr = Newsroom()
    print(f"Provider: {nr.provider.name}" + (f" · model {nr.provider.model}" if nr.provider.model else ""))
    if not nr.enabled:
        print("No AI provider configured: showing the template texts. See .env.example to connect Microsoft Foundry.")
    sheet = next((s for s in sheets_for(a.match) if s["kind"] == a.kind), None)
    if not sheet:
        raise SystemExit(f"No {a.kind} moment in {a.match}")
    print(f"Moment: {sheet['kind']} at {sheet['display_minute']}\n")
    out = await nr.produce(sheet, [l.strip() for l in a.langs.split(",") if l.strip()])
    await nr.aclose()
    for lang, texts in out["texts"].items():
        print(f"--- {lang}")
        print(json.dumps(texts, ensure_ascii=False, indent=2))
    print("\nTrace:")
    for t in out["trace"]:
        print("  ", "OK " if t.get("ok") else "FAIL", t["step"], {k: v for k, v in t.items() if k not in ("step", "ok")})
    print(f"\nFallback to template: {out['fallback']} · total {out['latency_ms']} ms")


if __name__ == "__main__":
    asyncio.run(main())
