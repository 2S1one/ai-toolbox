import logging

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from app.config import settings
from app.db import get_mongo

log = logging.getLogger(__name__)

_subscribers = get_mongo().database["subscribers"]


async def _start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    chat_id = update.effective_chat.id
    if username not in settings.telegram_allowed_usernames:
        await update.message.reply_text("Access denied.")
        return
    _subscribers.update_one(
        {"username": username},
        {"$set": {"username": username, "chat_id": chat_id}},
        upsert=True,
    )
    await update.message.reply_text("Subscribed.")


async def _stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    _subscribers.delete_one({"username": username})
    await update.message.reply_text("Unsubscribed.")


def run_bot():
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", _start))
    app.add_handler(CommandHandler("stop", _stop))
    app.run_polling(stop_signals=None)
