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


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


_no_redirect_opener = urllib.request.build_opener(_NoRedirect)


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
                return json.load(response), response.headers
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


def rate_limit(headers, remaining_name, reset_name, reset_is_epoch):
    remaining = headers.get(remaining_name)
    reset = headers.get(reset_name)
    if remaining is None or reset is None:
        return None
    seconds = float(reset) - time.time() if reset_is_epoch else float(reset)
    return int(remaining), max(seconds, 0.0)


def resolve_redirect(url, timeout=10):
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    try:
        with _no_redirect_opener.open(request, timeout=timeout) as response:
            return response.url
    except urllib.error.HTTPError as error:
        if 300 <= error.code < 400 and error.headers.get("Location"):
            return error.headers["Location"]
        raise HttpError(f"HEAD {url}: {error}") from error
    except (urllib.error.URLError, TimeoutError) as error:
        raise HttpError(f"HEAD {url}: {error}") from error
