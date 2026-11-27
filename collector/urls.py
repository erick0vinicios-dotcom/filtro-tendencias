from urllib.parse import urlsplit


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
