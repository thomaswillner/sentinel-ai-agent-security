"""Fetch the source article from the Khoros v1 REST API.

The rendered TechCommunity page is a client-side SPA, so its HTML is not a
usable source -- a plain fetch returns only the title. This endpoint returns the
message as structured JSON including post_time and last_edit_time, which give
exact change detection on the article itself.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from .http_evidence import fetch

MESSAGE_ID = "4542583"
ARTICLE_API = (
    "https://techcommunity.microsoft.com/t5/s/gxcuf89792/restapi/vc/messages/"
    f"id/{MESSAGE_ID}?restapi.response_format=json"
)
ARTICLE_URL = (
    "https://techcommunity.microsoft.com/blog/coreinfrastructureandsecurityblog/"
    f"securing-enterprise-ai-agents-with-microsoft-sentinel/{MESSAGE_ID}"
)


@dataclass(frozen=True)
class ArticleRecord:
    message_id: str
    subject: str
    author: str
    post_time: str
    last_edit_time: str
    body_hash: str
    labels: list[str]
    source_url: str = ARTICLE_URL


def _scalar(node: object) -> str:
    if isinstance(node, dict):
        value = node.get("$")
        return "" if value is None else str(value)
    return "" if node is None else str(node)


def parse_article(payload: dict) -> ArticleRecord:
    msg = payload["response"]["message"]
    body = _scalar(msg.get("body"))
    labels = sorted(
        _scalar(item.get("text"))
        for item in (msg.get("labels") or {}).get("label", [])
    )
    return ArticleRecord(
        message_id=_scalar(msg.get("id")) or MESSAGE_ID,
        subject=_scalar(msg.get("subject")),
        author=_scalar((msg.get("author") or {}).get("login")),
        post_time=_scalar(msg.get("post_time")),
        last_edit_time=_scalar(msg.get("last_edit_time")),
        body_hash=hashlib.sha256(body.encode("utf-8")).hexdigest(),
        labels=labels,
    )


def load_article() -> ArticleRecord | None:
    """Return the article record, or None when the source is unreachable."""
    result = fetch(ARTICLE_API)
    if not result.ok:
        return None
    try:
        return parse_article(json.loads(result.body))
    except (KeyError, TypeError, json.JSONDecodeError):
        return None
