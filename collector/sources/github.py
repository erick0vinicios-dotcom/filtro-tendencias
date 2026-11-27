import logging
import os
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

from collector.context import iso
from collector.http import rate_limit, request_json
from collector.urls import clean_url, product_key

SEARCH_URL = "https://api.github.com/search/repositories"
MAX_RATE_WAIT = 65

log = logging.getLogger("github")


def collect(settings, ctx):
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        log.warning("GITHUB_TOKEN ausente; usando o limite sem autenticação (10 buscas/min)")

    since = (ctx.now - timedelta(days=settings["lookback_days"])).date().isoformat()
    topics = settings["topics"]
    repos = {}
    failures = 0

    for position, topic in enumerate(topics, start=1):
        query = f"topic:{topic} created:>={since} stars:>={settings['min_stars']}"
        log.info("busca %d/%d: %s", position, len(topics), query)
        params = urlencode({"q": query, "sort": "stars", "order": "desc", "per_page": settings["per_page"]})
        try:
            data, response_headers = request_json(f"{SEARCH_URL}?{params}", headers=headers)
        except Exception as error:
            log.error("busca por topic:%s falhou: %s", topic, error)
            failures += 1
            continue
        found = data.get("items", [])
        log.info("topic:%s retornou %d repositórios (total no GitHub: %s)", topic, len(found), data.get("total_count"))
        for repo in found:
            repos.setdefault(repo["id"], repo)
        wait_if_exhausted(response_headers)

    if failures == len(topics):
        raise RuntimeError("todas as buscas no GitHub falharam")

    log.info("normalizando %d repositórios únicos", len(repos))
    items = [normalize(repo, settings, ctx) for repo in repos.values() if not repo.get("fork") and not repo.get("archived")]
    items.sort(key=lambda item: item["velocity"], reverse=True)
    return items


def wait_if_exhausted(headers):
    limit = rate_limit(headers, "x-ratelimit-remaining", "x-ratelimit-reset", reset_is_epoch=True)
    if not limit:
        return
    remaining, seconds = limit
    if remaining > 0:
        return
    wait = min(seconds + 1, MAX_RATE_WAIT)
    log.info("limite de buscas atingido; aguardando %.0fs", wait)
    time.sleep(wait)


def normalize(repo, settings, ctx):
    created = datetime.fromisoformat(repo["created_at"].replace("Z", "+00:00"))
    age_hours = ctx.hours_since(created)
    html_url = repo["html_url"]
    homepage = clean_url(repo.get("homepage") or "") or None
    key = product_key(html_url, ctx.shared_hosts)
    homepage_key = product_key(homepage, ctx.shared_hosts)
    stars = repo.get("stargazers_count", 0)
    return {
        "source": "github",
        "source_id": f"gh:{repo['id']}",
        "name": repo["name"],
        "description": (repo.get("description") or "").strip(),
        "url": homepage or html_url,
        "key": key,
        "alt_keys": [homepage_key] if homepage_key and homepage_key != key else [],
        "evidence_url": html_url,
        "metric": {"name": "stars", "value": stars},
        "topics": repo.get("topics", []),
        "language": repo.get("language"),
        "published_at": iso(created),
        "collected_at": ctx.now_iso,
        "age_hours": round(age_hours, 2),
        "velocity": round(stars / max(age_hours, settings["min_age_hours"]), 3),
    }
