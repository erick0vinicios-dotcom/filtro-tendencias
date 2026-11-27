from bisect import bisect_left, bisect_right
from collections import defaultdict

CONFIDENCE_HIGH = "Alta"
CONFIDENCE_MEDIUM = "Média"
CONFIDENCE_LOW = "Baixa"
EVIDENCE_VERIFIED = "Verificada"
EVIDENCE_HYPOTHESIS = "Hipótese"


def add_percentiles(items):
    by_source = defaultdict(list)
    for item in items:
        by_source[item["source"]].append(item)
    for source_items in by_source.values():
        values = sorted(item["velocity"] for item in source_items)
        total = len(values)
        for item in source_items:
            below = bisect_left(values, item["velocity"])
            equal = bisect_right(values, item["velocity"]) - below
            item["percentile"] = round((below + equal / 2) / total, 4)


def score_group(group, settings):
    members = group["members"]
    weights = settings["weights"]
    sources = sorted({member["source"] for member in members})

    attention = max(member["percentile"] for member in members)
    full_at = max(settings["multi_source_full_at"], 2)
    multi_source = min((len(sources) - 1) / (full_at - 1), 1.0)
    revenue = next((member["revenue"] for member in members if member.get("revenue")), None)

    signals = {
        "attention": round(attention, 4),
        "multi_source": round(multi_source, 4),
        "revenue": 1.0 if revenue else 0.0,
    }
    total_weight = sum(weights.values()) or 1
    score = 100 * sum(weights[name] * value for name, value in signals.items()) / total_weight

    presence = len(sources) >= settings["min_sources_for_presence"]
    if revenue and presence:
        confidence = CONFIDENCE_HIGH
    elif revenue or presence:
        confidence = CONFIDENCE_MEDIUM
    else:
        confidence = CONFIDENCE_LOW

    return {
        "score": round(score, 2),
        "signals": signals,
        "confidence": confidence,
        "return_evidence": EVIDENCE_VERIFIED if revenue else EVIDENCE_HYPOTHESIS,
        "revenue": revenue,
        "source_names": sources,
    }
