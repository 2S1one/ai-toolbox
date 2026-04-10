import asyncio
import json
import logging

from telegram import Bot
from langchain_core.messages import HumanMessage, SystemMessage

from app.config import settings
from app.db import get_mongo
from app.models import ClassifiedPost, ClassifierResponse, NotificationPost, TelegramNotification
from app.services.agent import get_classifier_llm

log = logging.getLogger(__name__)

_llm = get_classifier_llm()
_mongo = get_mongo()
_notifications = _mongo.database["notifications"]
_subscribers = _mongo.database["subscribers"]

SYSTEM_PROMPT = (
    "You are a strict relevance classifier for a Docker container security feed. "
    "You receive Reddit posts and must identify only those DIRECTLY and SUBSTANTIVELY about the given topics.\n\n"
    "Return a JSON object with key 'relevant' containing objects with 'id' and 'reason' (1-2 sentences why it matches). "
    'If no posts are relevant, return {"relevant": []}. Return only valid JSON, nothing else.\n\n'
    "INCLUDE a post only if it is clearly about: Docker/OCI container image hardening, securing or choosing base images "
    "with security intent, distroless or minimal images, CVE patching specifically in container images, "
    "image scanning tools/practices, SBOM for containers, CIS Docker benchmark, or real-world experiences "
    "with container image security (pain points, lessons learned, tooling decisions).\n\n"
    "EXCLUDE posts that are about:\n"
    "- General Docker usage questions (how to run containers, docker-compose setup, Docker internals/tutorials)\n"
    "- CVE announcements or PoC exploits unless they explicitly discuss impact on container images\n"
    "- Docker networking or firewall configuration (nftables, iptables, port blocking, proxies)\n"
    "- Kubernetes topics unless they specifically discuss image scanning or base image hardening\n"
    "- Tool or service announcements without substantive discussion of container security practices\n"
    "- Posts with no meaningful text body (link-only posts, metadata-only)\n"
    "- Posts that mention Docker only in passing while being about something else\n\n"
    "When in doubt, exclude the post."
)


def _already_sent(post_id: str) -> bool:
    return _notifications.find_one({"post_id": post_id}) is not None


def _mark_sent(post_id: str, reason: str):
    _notifications.insert_one({"post_id": post_id, "reason": reason})


def _to_telegram_notification(doc: dict) -> TelegramNotification:
    selftext = doc.get("selftext") or ""
    return TelegramNotification(
        subreddit=doc.get("subreddit", ""),
        title=doc.get("title", ""),
        reddit_url=doc.get("reddit_url", ""),
        excerpt=selftext[:200] if selftext else None,
    )


async def _send_to_subscribers(text: str):
    async with Bot(token=settings.telegram_bot_token) as bot:
        for sub in _subscribers.find():
            try:
                await bot.send_message(chat_id=sub["chat_id"], text=text)
            except Exception as e:
                log.error("Telegram send error for @%s: %s", sub["username"], e)


def check_and_notify(docs: list[dict]):
    if not settings.telegram_bot_token or not docs or not settings.notification_topics:
        return

    new_docs = [d for d in docs if not _already_sent(str(d["_id"]))]
    if not new_docs:
        return

    posts = [
        NotificationPost(
            id=str(d["_id"]),
            title=d.get("title", ""),
            text=d.get("selftext", "") or "",
        )
        for d in new_docs
    ]

    user_message = json.dumps({
        "posts": [p.model_dump() for p in posts],
        "topics": settings.notification_topics,
    }, ensure_ascii=False)

    try:
        response = _llm.invoke([SystemMessage(SYSTEM_PROMPT), HumanMessage(user_message)])
        result = ClassifierResponse.model_validate_json(response.content)
    except Exception as e:
        log.error("GPT classifier error: %s", e)
        return

    id_to_doc = {str(d["_id"]): d for d in new_docs}
    for classified in result.relevant:
        doc = id_to_doc.get(classified.id)
        if not doc:
            continue
        notification = _to_telegram_notification(doc)
        loop = asyncio.new_event_loop()
        loop.run_until_complete(_send_to_subscribers(notification.format_message()))
        loop.close()
        _mark_sent(classified.id, classified.reason)
        log.info("Notified: %s | reason: %s", doc.get("title"), classified.reason)
