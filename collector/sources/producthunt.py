import logging
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from collector.context import iso
from collector.errors import SourceSkipped
from collector.http import rate_limit, request_json, resolve_redirect
from collector.urls import clean_url, product_key

GRAPHQL_URL = "https://api.producthunt.com/v2/api/graphql"
QUERY = """
query Posts($first: Int!, $after: String, $postedAfter: DateTime!, $order: PostsOrder!, $featured: Boolean) {
  posts(first: $first, after: $after, postedAfter: $postedAfter, order: $order, featured: $featured) {
    pageInfo { hasNextPage endCursor }
    edges {
      node {
        id name tagline description url website votesCount commentsCount createdAt featuredAt
        topics(first: 6) { edges { node { slug } } }
      }
    }
  }
}
"""

log = logging.getLogger("producthunt")


def collect(settings, ctx):
    token = os.environ.get("PRODUCTHUNT_TOKEN")
    if not token:
        raise SourceSkipped("PRODUCTHUNT_TOKEN não definido")
    headers = {"Authorization": f"Bearer {token}"}

    posts = fetch_posts(settings, ctx, headers)
    log.info("resolvendo o site real de %d produtos", len(posts))
    websites = resolve_websites(posts, settings)

    items = [normalize(post, websites.get(post["id"]), settings, ctx) for post in posts]
    items.sort(key=lambda item: item["velocity"], reverse=True)
    return items


def fetch_posts(settings, ctx, headers):
    variables = {
        "first": settings["page_size"],
        "after": None,
        "postedAfter": iso(ctx.now - timedelta(hours=settings["lookback_hours"])),
        "order": settings["order"],
        "featured": True if settings["featured_only"] else None,
    }
    posts = []
    for page in range(1, settings["max_pages"] + 1):
        data, response_headers = request_json(GRAPHQL_URL, method="POST", payload={"query": QUERY, "variables": variables}, headers=headers)
        if data.get("errors"):
            raise RuntimeError("; ".join(error.get("message", "") for error in data["errors"]))
        connection = data["data"]["posts"]
        batch = [edge["node"] for edge in connection["edges"]]
        posts.extend(batch)
        log.info("página %d: %d produtos", page, len(batch))
        for node in batch:
            log.info("produto %s: %s (%s votos)", node["id"], node["name"], node["votesCount"])

        limit = rate_limit(response_headers, "X-Rate-Limit-Remaining", "X-Rate-Limit-Reset", reset_is_epoch=False)
        if limit:
            remaining, seconds = limit
            log.info("cota restante: %d pontos (renova em %.0fs)", remaining, seconds)
            if remaining < settings["min_remaining_quota"]:
                log.warning("cota abaixo de %d; parando a paginação", settings["min_remaining_quota"])
                break
        if not connection["pageInfo"]["hasNextPage"]:
            break
        variables["after"] = connection["pageInfo"]["endCursor"]
    return posts


def resolve_websites(posts, settings):
    if not settings["resolve_websites"]:
        return {}

    def resolve(post):
        try:
            return post["id"], clean_url(resolve_redirect(post["website"]))
        except Exception as error:
            log.warning("não consegui resolver o site de %s: %s", post["name"], error)
            return post["id"], None

    with ThreadPoolExecutor(max_workers=settings["workers"]) as pool:
        return {post_id: url for post_id, url in pool.map(resolve, posts) if url}


def normalize(post, website, settings, ctx):
    created = datetime.fromisoformat(post["createdAt"].replace("Z", "+00:00"))
    age_hours = ctx.hours_since(created)
    votes = post.get("votesCount", 0)
    return {
        "source": "producthunt",
        "source_id": f"ph:{post['id']}",
        "name": post["name"],
        "description": post.get("tagline") or "",
        "url": website,
        "key": product_key(website, ctx.shared_hosts),
        "alt_keys": [],
        "evidence_url": clean_url(post["url"]),
        "metric": {"name": "votes", "value": votes},
        "comments": post.get("commentsCount", 0),
        "topics": [edge["node"]["slug"] for edge in post["topics"]["edges"]],
        "featured": bool(post.get("featuredAt")),
        "published_at": iso(created),
        "collected_at": ctx.now_iso,
        "age_hours": round(age_hours, 2),
        "velocity": round(votes / max(age_hours, settings["min_age_hours"]), 3),
    }
