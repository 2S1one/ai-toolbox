"""
Telegram bot test script.
- /start registers user if their username is in ALLOWED_USERNAMES
- /stop unregisters user
- Sends a test message to all registered users
"""

import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

from app.config import settings
from app.db import get_mongo

_subscribers = get_mongo().database["subscribers"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    await update.message.reply_text("Subscribed. You will receive notifications about target posts.")


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    username = update.effective_user.username
    _subscribers.delete_one({"username": username})
    await update.message.reply_text("Unsubscribed.")


async def send_test_message():
    from telegram import Bot
    bot = Bot(token=settings.telegram_bot_token)
    subscribers = list(_subscribers.find())
    if not subscribers:
        print("No subscribers yet. Send /start to the bot first.")
        return
    for sub in subscribers:
        await bot.send_message(chat_id=sub["chat_id"], text="Test message from Reddit Monitor.")
        print(f"Sent to @{sub['username']}")


def run_bot():
    app = ApplicationBuilder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    print("Bot is running. Send /start to subscribe.")
    app.run_polling()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "send":
        asyncio.run(send_test_message())
    else:
        run_bot()
