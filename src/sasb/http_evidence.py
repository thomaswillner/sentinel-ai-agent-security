"""The only network egress in the project.

Every outcome becomes a FetchResult. Network failures are returned as data, not
raised, so callers must classify them explicitly instead of letting a broad
try/except quietly turn a failure into a pass.
"""
from __future__ import annotations

import urllib.error
import urllib.request
from dataclasses import dataclass

USER_AGENT = (
    "sentinel-ai-agent-security/0.1 "
    "(+https://github.com/thomaswillner/sentinel-ai-agent-security)"
)


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    status: int
    body: str
    error: str | None = None

    @property
    def redirected(self) -> bool:
        return self.status != 0 and self.final_url.rstrip("/") != self.url.rstrip("/")

    @property
    def ok(self) -> bool:
        return self.status == 200


def fetch(url: str, *, timeout: int = 30) -> FetchResult:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            charset = resp.headers.get_content_charset() or "utf-8"
            return FetchResult(
                url=url,
                final_url=resp.geturl(),
                status=resp.status,
                body=raw.decode(charset, errors="replace"),
            )
    except urllib.error.HTTPError as exc:
        return FetchResult(url, url, exc.code, "", error=f"HTTP {exc.code}")
    except Exception as exc:  # network, DNS, TLS, timeout
        return FetchResult(url, url, 0, "", error=f"{type(exc).__name__}: {exc}")
