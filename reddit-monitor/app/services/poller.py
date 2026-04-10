import html
import logging
import random
import re
import time
from datetime import datetime, timezone

import feedparser
from pymongo.errors import DuplicateKeyError

from app.config import settings
from app.models import PostCreate
from app.services.indexer import index_doc
from app.services.notifier import check_and_notify

log = logging.getLogger(__name__)


def _clean_html(raw: str) -> str:
    text = re.sub(r"<[^>]+>", "", raw)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def _extract_external_url(summary_html: str, reddit_url: str) -> str | None:
    match = re.search(r'href="([^"]+)">\[link\]', summary_html)
    if not match:
        return None
    url = match.group(1)
    return url if url != reddit_url else None


def _parse_entry(entry, subreddit: str) -> PostCreate:
    reddit_url = entry.get("link", "")
    summary_html = entry.get("summary", "")
    return PostCreate(
        subreddit=subreddit,
        title=entry.get("title", ""),
        reddit_url=reddit_url,
        external_url=_extract_external_url(summary_html, reddit_url),
        author=entry.get("author", "").removeprefix("/u/") or None,
        selftext=_clean_html(summary_html) or None,
        created_utc=int(datetime(*entry.published_parsed[:6], tzinfo=timezone.utc).timestamp()),
        fetched_at=datetime.now(timezone.utc),
    )


DELAY_BETWEEN_REQUESTS = (1, 3)


def poll_once(collection, qdrant, seen: set):
    log.info("Poll cycle started")
    new_docs = []
    for subreddit in settings.subreddits:
        url = f"https://www.reddit.com/r/{subreddit}/new/.rss"
        feed = feedparser.parse(url)

        for entry in feed.entries:
            reddit_url = entry.get("link", "")
            if not reddit_url or reddit_url in seen:
                continue
            seen.add(reddit_url)

            post = _parse_entry(entry, subreddit)
            doc = post.model_dump()
            try:
                collection.insert_one(doc)
            except DuplicateKeyError:
                continue

            log.info("[%s] %s", subreddit, post.title)
            index_doc(doc, qdrant, collection)
            new_docs.append(doc)

        time.sleep(random.uniform(*DELAY_BETWEEN_REQUESTS))

    log.info("Poll cycle finished: %d new posts", len(new_docs))
    check_and_notify(new_docs)


def run_poller(collection, qdrant):
    log.info("Poller started")
    seen: set = set()
    while True:
        try:
            poll_once(collection, qdrant, seen)
        except Exception as e:
            log.error("Poller error: %s", e)
        time.sleep(settings.poll_interval)
