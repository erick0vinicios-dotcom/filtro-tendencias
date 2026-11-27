import json
import logging
import time
import urllib.error
import urllib.request

USER_AGENT = "filtro-tendencias/0.1"
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_RETRY_AFTER = 60

log = logging.getLogger("http")


class HttpError(Exception):
    pass


def request_json(url, method="GET", payload=None, headers=None, timeout=20, retries=3, backoff=2.0):
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    request_headers.update(headers or {})
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    last_error = None
    for attempt in range(1, retries + 1):
        request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        wait = backoff ** attempt
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response), dict(response.headers)
        except urllib.error.HTTPError as error:
            last_error = error
            if error.code not in RETRYABLE_STATUS:
                break
            retry_after = error.headers.get("Retry-After", "")
            if retry_after.isdigit():
                wait = min(int(retry_after), MAX_RETRY_AFTER)
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
        if attempt < retries:
            log.warning("tentativa %d/%d falhou para %s (%s); nova tentativa em %.0fs", attempt, retries, url, last_error, wait)
            time.sleep(wait)
    raise HttpError(f"{method} {url}: {last_error}") from last_error


def get_json(url, **kwargs):
    data, _ = request_json(url, **kwargs)
    return data
