import json
import logging
from collections import Counter
from datetime import timedelta
from pathlib import Path

from collector.category import build_matcher
from collector.scoring import add_percentiles, score_group
from collector.unify import domain_keys, unify

NAME_PRIORITY = ("producthunt", "github", "hackernews")
URL_PRIORITY = ("hackernews", "github", "producthunt")

log = logging.getLogger("ranking")


def build(items_by_source, report, config, ctx, history_dir):
    all_items = [item for items in items_by_source.values() for item in items]
    log.info("etapa 1/4: percentil de velocidade dentro de cada fonte (%d itens)", len(all_items))
    add_percentiles(all_items)

    log.info("etapa 2/4: unificando o mesmo produto entre fontes")
    unify_settings = config.get("unify", {})
    groups, discarded = split_clones(unify(all_items, unify_settings), unify_settings.get("max_items_per_source", 3))
    for entry in discarded:
        log.info("descartado como clone/spam: %s (%d cópias)", entry["name"], entry["copies"])

    log.info("etapa 3/4: filtro de categoria SaaS/IA")
    matcher = build_matcher(config.get("category", {}))
    selected = []
    for group in groups:
        for member in group["members"]:
            member["category_matches"] = matcher(member)
        if any(member["category_matches"] for member in group["members"]):
            selected.append(group)
    groups = selected
    log.info("%d produtos passaram no filtro; %d em mais de uma fonte", len(groups), sum(1 for group in groups if len({m["source"] for m in group["members"]}) > 1))

    log.info("etapa 4/4: pontuação e crescimento")
    scoring_settings = config["scoring"]
    previous = load_previous_metrics(history_dir, ctx, config.get("history", {}).get("growth_days", []))
    products = [build_product(group, scoring_settings, previous, ctx) for group in groups]
    products.sort(key=lambda product: (product["score"], product["signals"]["attention"]), reverse=True)
    products = products[: scoring_settings["max_items"]]

    return {
        "generated_at": ctx.now_iso,
        "sources": report,
        "weights": scoring_settings["weights"],
        "count": len(products),
        "items": products,
        "discarded": discarded,
    }


def split_clones(groups, max_items_per_source):
    kept, discarded = [], []
    for group in groups:
        copies = Counter(member["source"] for member in group["members"]).most_common(1)[0][1]
        if copies <= max_items_per_source:
            kept.append(group)
            continue
        first = group["members"][0]
        discarded.append({
            "name": first["name"],
            "copies": copies,
            "examples": [member["evidence_url"] for member in group["members"][:3]],
        })
    discarded.sort(key=lambda entry: entry["copies"], reverse=True)
    return kept, discarded


def build_product(group, settings, previous, ctx):
    members = group["members"]
    by_name = sorted(members, key=lambda member: (_rank(member["source"], NAME_PRIORITY), -member["percentile"]))
    by_url = sorted(members, key=lambda member: (_rank(member["source"], URL_PRIORITY), -member["percentile"]))
    keys = sorted({member["key"] for member in members if member.get("key")}) or sorted({key for member in members for key in domain_keys(member)})
    description = next((member["description"] for member in by_name if member["description"]), "")

    return {
        "id": keys[0] if keys else min(member["source_id"] for member in members),
        "name": by_name[0]["name"],
        "url": next((member["url"] for member in by_url if member.get("url")), by_url[0]["evidence_url"]),
        "description": description,
        "collected_at": ctx.now_iso,
        **score_group(group, settings),
        "matched_by_name": group["matched_by_name"],
        "category_matches": sorted({match for member in members for match in member["category_matches"]}),
        "sources": [source_entry(member, previous) for member in sorted(members, key=lambda m: -m["percentile"])],
    }


def source_entry(member, previous):
    return {
        "source": member["source"],
        "source_id": member["source_id"],
        "name": member["name"],
        "evidence_url": member["evidence_url"],
        "metric": member["metric"],
        "velocity": member["velocity"],
        "percentile": member["percentile"],
        "published_at": member["published_at"],
        "age_hours": member["age_hours"],
        "growth": growth(member, previous),
    }


def growth(member, previous):
    entries = []
    for days, snapshot in previous:
        before = snapshot["metrics"].get(member["source_id"])
        if before is None:
            continue
        entries.append({
            "period_days": days,
            "since": snapshot["collected_at"],
            "from": before,
            "to": member["metric"]["value"],
            "delta": member["metric"]["value"] - before,
        })
    return entries


def load_previous_metrics(history_dir, ctx, growth_days):
    snapshots = []
    for days in growth_days:
        path = history_dir / f"{(ctx.now - timedelta(days=days)).date().isoformat()}.json"
        if not path.exists():
            log.info("sem fotografia de %d dia(s) atrás (%s); crescimento desse período fica vazio", days, path.name)
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        metrics = {source_id: value for item in data["items"] for source_id, value in item["metrics"].items()}
        snapshots.append((days, {"collected_at": data["generated_at"], "metrics": metrics}))
    return snapshots


def history_snapshot(latest):
    return {
        "generated_at": latest["generated_at"],
        "items": [
            {
                "id": product["id"],
                "name": product["name"],
                "score": product["score"],
                "confidence": product["confidence"],
                "metrics": {source["source_id"]: source["metric"]["value"] for source in product["sources"]},
            }
            for product in latest["items"]
        ],
    }


def write_outputs(latest, ctx, data_dir):
    history_dir = data_dir / "history"
    history_dir.mkdir(parents=True, exist_ok=True)
    latest_path = data_dir / "latest.json"
    history_path = history_dir / f"{ctx.now.date().isoformat()}.json"
    _write(latest_path, latest)
    _write(history_path, history_snapshot(latest))
    log.info("gravados %s (%d produtos) e %s", latest_path, latest["count"], history_path)


def _write(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")


def _rank(source, priority):
    return priority.index(source) if source in priority else len(priority)
