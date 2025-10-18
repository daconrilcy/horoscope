from typing import Any


def score_factor(f: dict[str, Any]) -> float:
    return f.get("weight", 1.0) * f.get("intensity", 1.0) - f.get("friction", 0.0)


def pick_today(transits: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ranked = sorted(transits, key=score_factor, reverse=True)
    leaders = ranked[:3]
    influences = ranked[3:6]
    return leaders, influences


def energy_attention_opportunity(leaders: list[dict[str, Any]]) -> dict[str, int]:
    e = sum(1 for f in leaders if f.get("axis") in ("SUN", "MARS", "ASC"))
    a = sum(1 for f in leaders if f.get("axis") in ("MERCURY", "SATURN", "MC"))
    o = sum(1 for f in leaders if f.get("axis") in ("VENUS", "JUPITER", "NN"))
    return {"energy": e, "attention": a, "opportunity": o}

