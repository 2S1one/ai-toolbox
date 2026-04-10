import logging
import time
from datetime import datetime, timezone, timedelta

from qdrant_client.models import FieldCondition, Filter, MatchValue

from app.config import settings
from app.db import get_mongo, get_qdrant

log = logging.getLogger(__name__)

RETENTION_DAYS = 30
RUN_INTERVAL = 24 * 60 * 60  # seconds


def clean_once():
    mongo = get_mongo()
    qdrant = get_qdrant()

    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    cutoff_ts = int(cutoff.timestamp())

    old_docs = list(mongo.find({"created_utc": {"$lt": cutoff_ts}}, {"_id": 1}))
    if not old_docs:
        log.info("Cleaner: nothing to delete")
        return

    mongo_ids = [str(d["_id"]) for d in old_docs]

    for mongo_id in mongo_ids:
        try:
            qdrant.delete(
                collection_name=settings.qdrant_collection,
                points_selector=Filter(
                    must=[FieldCondition(key="mongo_id", match=MatchValue(value=mongo_id))]
                ),
            )
        except Exception as e:
            log.error("Qdrant delete error for %s: %s", mongo_id, e)

    result = mongo.delete_many({"created_utc": {"$lt": cutoff_ts}})
    log.info("Cleaner: deleted %d posts older than %d days", result.deleted_count, RETENTION_DAYS)


def run_cleaner():
    log.info("Cleaner started")
    while True:
        try:
            clean_once()
        except Exception as e:
            log.error("Cleaner error: %s", e)
        time.sleep(RUN_INTERVAL)
