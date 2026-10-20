"""Per-match narrative desk: schedules the newsroom without ever holding up the live stream.

For every moment:
  1. a template narrative is published immediately (status "draft"), so graphics never wait;
  2. the moment is queued for the AI newsroom; when the workflow finishes, the same moment_id is
     re-published with status "final" and the viewers' clients swap the text in place.

The queue is bounded and deadline-aware: if the match is replayed faster than the models can
write, low-priority moments are dropped and stale ones keep their template text. Goals, red
cards and recaps are never dropped.
"""
from __future__ import annotations

import asyncio
import logging
import time

from . import templates

log = logging.getLogger("matchlens.newsroom")

PRIORITY = {"full_time": 0, "half_time": 0, "goal": 1, "red_card": 1, "big_chance": 2, "state_of_play": 3}
MAX_QUEUE = 6
MAX_WAIT_S = 45.0            # wall-clock seconds a non-recap moment may wait before AI is skipped
MAX_LANGS = 3


class NarrativeDesk:
    def __init__(self, session, newsroom):
        self.session = session
        self.nr = newsroom
        self.queue: list[tuple[int, float, dict]] = []
        self.wake = asyncio.Event()
        self.task: asyncio.Task | None = None
        self.narratives: list[dict] = []           # latest version of each narrative, in order
        self.stats = {"published_final": 0, "fallbacks": 0, "skipped": 0}

    # ---- languages: viewers' requests plus the clubs' home markets
    def languages(self) -> list[str]:
        meta = self.session.meta
        langs = list(dict.fromkeys(
            [l for l in getattr(self.session, "viewer_langs", {}).values() if l and l != "en"] +
            [meta[s].get("market") for s in ("home", "away") if meta[s].get("market") not in (None, "en")] + ["es"]))
        return langs[:MAX_LANGS]

    # ---- intake
    def draft(self, sheet: dict) -> dict:
        return {"moment_id": sheet["moment_id"], "kind": sheet["kind"], "display_minute": sheet["display_minute"],
                "match_time_s": sheet["match_time_s"], "status": "draft", "source": "templates",
                "texts": {"en": templates.render(sheet, "en"), "es": templates.render(sheet, "es")},
                "fallback": False, "trace": []}

    def record(self, payload: dict, broadcast: bool = True):
        for i, n in enumerate(self.narratives):
            if n["moment_id"] == payload["moment_id"]:
                self.narratives[i] = payload
                break
        else:
            self.narratives.append(payload)
        if broadcast:
            mtype = "recap" if payload["kind"] in ("half_time", "full_time") else "narrative"
            self.session.broadcast(mtype, payload)

    def submit(self, sheet: dict, live: bool = True):
        self.record(self.draft(sheet), broadcast=live)
        if not live or not self.nr or not self.nr.enabled:
            return
        pr = PRIORITY.get(sheet["kind"], 3)
        self.queue.append((pr, time.monotonic(), sheet))
        if len(self.queue) > MAX_QUEUE:                          # drop the least important, oldest first
            self.queue.sort(key=lambda x: (-x[0], x[1]))
            dropped = self.queue.pop(0)
            if PRIORITY.get(dropped[2]["kind"], 3) <= 1:         # never drop goals / reds / recaps
                self.queue.append(dropped)
            else:
                self.stats["skipped"] += 1
        self.wake.set()
        if self.task is None or self.task.done():
            self.task = asyncio.create_task(self.worker())

    # ---- worker
    async def worker(self):
        while True:
            if not self.queue:
                self.wake.clear()
                try:
                    await asyncio.wait_for(self.wake.wait(), timeout=300)
                except asyncio.TimeoutError:
                    return
                continue
            self.queue.sort(key=lambda x: (x[0], x[1]))
            pr, queued_at, sheet = self.queue.pop(0)
            if pr > 0 and time.monotonic() - queued_at > MAX_WAIT_S:
                self.stats["skipped"] += 1
                continue
            try:
                payload = await self.nr.produce(sheet, self.languages())
            except Exception:
                log.exception("narrative failed")
                continue
            self.stats["published_final"] += 1
            self.stats["fallbacks"] += int(payload.get("fallback", False))
            self.record(payload)

    def stop(self):
        if self.task:
            self.task.cancel()
