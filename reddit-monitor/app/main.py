import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.config import settings
from app.db import get_mongo, get_qdrant, ensure_indexes, check_mongo, check_qdrant
from app.routes import admin, posts, search
from app.services.cleaner import run_cleaner
from app.services.poller import run_poller
from app.services.telegram_bot import run_bot

from logging.handlers import RotatingFileHandler

_log_handler = RotatingFileHandler(
    "logs/app.log",
    maxBytes=10 * 1024 * 1024,
    backupCount=5,
    encoding="utf-8",
)
_log_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(), _log_handler],
)
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    collection = get_mongo()
    qdrant = get_qdrant()

    check_mongo(collection)
    check_qdrant(qdrant)
    log.info("Connected to MongoDB and Qdrant")

    ensure_indexes(collection)

    threading.Thread(target=run_poller, args=(collection, qdrant), daemon=True).start()
    log.info("Poller started")

    if settings.telegram_bot_token:
        threading.Thread(target=run_bot, daemon=True).start()
        log.info("Telegram bot started")

    threading.Thread(target=run_cleaner, daemon=True).start()
    log.info("Cleaner started")

    yield


app = FastAPI(title="Reddit Monitor API", lifespan=lifespan)

app.include_router(search.router)
app.include_router(posts.router)
app.include_router(admin.router)
