"""Fantasy prices (EUR millions): set from quality and position, then moved by form, 0.1 at a time."""
from __future__ import annotations

POS_ADJ = {"GK": -0.5, "DEF": 0.0, "MID": 0.5, "FWD": 1.0}
MIN_PRICE = 3.5
MAX_MOVE = 1.5            # a price never moves more than this from its starting value


def base_price(overall: int, position: str) -> float:
    """Overall 72 or less -> 4.0, overall 95 -> about 12.3 (plus the position adjustment)."""
    p = 4.0 + max(0, overall - 72) * 0.36 + POS_ADJ.get(position, 0.0)
    return round(max(MIN_PRICE, min(14.0, round(p * 2) / 2)), 1)


def expected_points(price: float) -> float:
    """What a manager expects per match for that price (calibrated on the simulated season)."""
    return 1.0 + 0.3 * price


def form(history: list[dict], n: int = 3) -> float:
    """Average points over the last n matchdays (0 for matchdays missed)."""
    last = history[-n:]
    return sum(r["points"] for r in last) / max(1, len(last))


def next_price(price: float, start: float, history: list[dict]) -> float:
    gap = form(history) - expected_points(price)
    step = 0.2 if gap >= 2.5 else 0.1 if gap >= 1.0 else -0.2 if gap <= -2.5 else -0.1 if gap <= -1.5 else 0.0
    new = min(start + MAX_MOVE, max(start - MAX_MOVE, price + step))
    return round(max(MIN_PRICE, new), 1)
