from __future__ import annotations

import logging
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from dataclasses import dataclass
from functools import lru_cache

LOGGER = logging.getLogger(__name__)
USER_AGENT = "CWA-local-board-meeting-monitor/0.1 (+https://calworkforce.org)"


@dataclass(frozen=True)
class FetchedPage:
    url: str
    status: int
    content_type: str
    body: bytes

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


@lru_cache(maxsize=256)
def _robots_for(base_url: str) -> urllib.robotparser.RobotFileParser:
    parsed = urllib.parse.urlparse(base_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(robots_url)
    try:
        rp.read()
    except Exception as exc:  # robots.txt fetch failures should not halt official public pages.
        LOGGER.debug("Could not read robots.txt %s: %s", robots_url, exc)
    return rp


def can_fetch(url: str) -> bool:
    rp = _robots_for(url)
    if rp.mtime() == 0:
        return True
    return rp.can_fetch(USER_AGENT, url)


def fetch_url(url: str, timeout: int = 8, retries: int = 1, respect_robots: bool = True) -> FetchedPage:
    if respect_robots and not can_fetch(url):
        raise PermissionError(f"robots.txt disallows fetching {url}")
    headers = {"User-Agent": USER_AGENT, "Accept": "text/html,application/pdf,*/*;q=0.8"}
    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return FetchedPage(
                    url=resp.geturl(),
                    status=resp.status,
                    content_type=resp.headers.get("content-type", ""),
                    body=resp.read(),
                )
        except (urllib.error.URLError, TimeoutError, PermissionError) as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(2**attempt)
    assert last_error is not None
    raise last_error


def absolute_url(base_url: str, href: str) -> str:
    return urllib.parse.urljoin(base_url, href)
