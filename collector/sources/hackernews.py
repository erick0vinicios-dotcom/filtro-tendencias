import logging
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlencode

from collector.context import from_unix, iso
from collector.http import get_json
from collector.urls import product_key

FIREBASE_URL = "https://hacker-news.firebaseio.com/v0"
ALGOLIA_URL = "https://hn.algolia.com/api/v1/search_by_date"
ITEM_URL = "https://news.ycombinator.com/item?id={}"
ALGOLIA_PAGE_SIZE = 200
ALGOLIA_MAX_PAGES = 10
MAX_NAME_LENGTH = 60
SHOW_HN_PREFIX = re.compile(r"^\s*show\s+hn\s*[:\-–—]\s*", re.IGNORECASE)
NAME_SEPARATORS = (" – ", " — ", " - ", ": ", " | ", ", ")

log = logging.getLogger("hackernews")


def collect(settings, ctx):
    stories = {}
    errors = []

    log.info("etapa 1/3: lista atual do Show HN (Firebase)")
    try:
        stories.update(fetch_firebase(settings))
    except Exception as error:
        log.error("Firebase falhou: %s", error)
        errors.append(error)

    log.info("etapa 2/3: busca das últimas %sh (Algolia)", settings["lookback_hours"])
    try:
        for story_id, story in fetch_algolia(settings, ctx).items():
            stories.setdefault(story_id, story)
    except Exception as error:
        log.error("Algolia falhou: %s", error)
        errors.append(error)

    if len(errors) == 2:
        raise RuntimeError("Firebase e Algolia falharam")

    log.info("etapa 3/3: normalizando %d histórias", len(stories))
    items = [normalize(story, settings, ctx) for story in stories.values() if is_valid(story, settings)]
    items.sort(key=lambda item: item["velocity"], reverse=True)
    log.info("%d itens após filtros (mínimo de %s pontos)", len(items), settings["min_points"])
    return items


def fetch_firebase(settings):
    ids = get_json(f"{FIREBASE_URL}/showstories.json")[: settings["max_items"]]
    total = len(ids)
    log.info("%d ids recebidos; buscando detalhes com %s conexões", total, settings["workers"])
    stories = {}
    with ThreadPoolExecutor(max_workers=settings["workers"]) as pool:
        futures = {pool.submit(get_json, f"{FIREBASE_URL}/item/{story_id}.json"): story_id for story_id in ids}
        for position, future in enumerate(as_completed(futures), start=1):
            story_id = futures[future]
            try:
                raw = future.result()
            except Exception as error:
                log.warning("item %d/%d id=%s ignorado: %s", position, total, story_id, error)
                continue
            if not raw:
                log.warning("item %d/%d id=%s veio vazio", position, total, story_id)
                continue
            log.info("item %d/%d id=%s %s", position, total, story_id, raw.get("title", "")[:70])
            stories[story_id] = {
                "id": story_id,
                "title": raw.get("title", ""),
                "url": raw.get("url"),
                "points": raw.get("score", 0),
                "comments": raw.get("descendants", 0),
                "time": raw.get("time", 0),
                "type": raw.get("type"),
                "dead": raw.get("dead", False) or raw.get("deleted", False),
            }
    return stories


def fetch_algolia(settings, ctx):
    since = int(ctx.now.timestamp() - settings["lookback_hours"] * 3600)
    stories = {}
    for page in range(ALGOLIA_MAX_PAGES):
        query = urlencode({
            "tags": "show_hn",
            "numericFilters": f"created_at_i>{since},points>={settings['min_points']}",
            "hitsPerPage": ALGOLIA_PAGE_SIZE,
            "page": page,
        })
        result = get_json(f"{ALGOLIA_URL}?{query}")
        hits = result.get("hits", [])
        log.info("página %d: %d histórias", page + 1, len(hits))
        for hit in hits:
            story_id = int(hit["objectID"])
            stories[story_id] = {
                "id": story_id,
                "title": hit.get("title") or "",
                "url": hit.get("url"),
                "points": hit.get("points") or 0,
                "comments": hit.get("num_comments") or 0,
                "time": hit.get("created_at_i", 0),
                "type": "story",
                "dead": False,
            }
        if page + 1 >= result.get("nbPages", 0):
            break
    return stories


def is_valid(story, settings):
    return (
        story["type"] == "story"
        and not story["dead"]
        and story["time"]
        and story["points"] >= settings["min_points"]
    )


def normalize(story, settings, ctx):
    published = from_unix(story["time"])
    age_hours = ctx.hours_since(published)
    name, description = split_title(story["title"])
    url = story["url"]
    return {
        "source": "hackernews",
        "source_id": f"hn:{story['id']}",
        "name": name,
        "description": description,
        "url": url,
        "key": product_key(url, ctx.shared_hosts),
        "alt_keys": [],
        "evidence_url": ITEM_URL.format(story["id"]),
        "metric": {"name": "points", "value": story["points"]},
        "comments": story["comments"],
        "topics": [],
        "published_at": iso(published),
        "collected_at": ctx.now_iso,
        "age_hours": round(age_hours, 2),
        "velocity": round(story["points"] / max(age_hours, settings["min_age_hours"]), 3),
    }


def split_title(title):
    text = SHOW_HN_PREFIX.sub("", title).strip()
    for separator in NAME_SEPARATORS:
        name, found, rest = text.partition(separator)
        if found and name.strip() and len(name.strip()) <= MAX_NAME_LENGTH:
            return name.strip(), rest.strip()
    return text, ""
