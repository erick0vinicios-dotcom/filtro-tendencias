from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

TRACKING_PARAMS = {"ref", "source", "via", "fbclid", "gclid"}


def product_key(url, shared_hosts):
    if not url:
        return None
    text = url.strip()
    if "://" not in text:
        text = f"https://{text}"
    parts = urlsplit(text)
    host = (parts.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host:
        return None
    depth = shared_hosts.get(host, 0)
    if not depth:
        return host
    segments = [segment.lower() for segment in parts.path.split("/") if segment][:depth]
    return "/".join([host, *segments])


def clean_url(url):
    if not url:
        return url
    parts = urlsplit(url.strip())
    query = [
        (name, value)
        for name, value in parse_qsl(parts.query, keep_blank_values=True)
        if name.lower() not in TRACKING_PARAMS and not name.lower().startswith("utm_")
    ]
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), ""))
