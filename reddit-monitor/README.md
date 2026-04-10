# Reddit Monitor

A FastAPI service that continuously monitors Reddit for security-relevant posts, indexes them for semantic search, and delivers real-time Telegram notifications based on configurable topics.

## Why

Security professionals need to stay current with a fragmented information landscape — relevant posts appear across dozens of subreddits with no consistent signal. This service solves that by combining:

- **Automated collection** from any set of subreddits via RSS
- **Hybrid semantic search** (dense embeddings + BM25) so you can ask questions in natural language, not just keyword-match
- **GPT-powered classification** that understands context and filters noise — you define what "relevant" means in plain English
- **Telegram notifications** that deliver only the posts that matter, with GPT's reasoning attached

## Architecture

```
Reddit RSS feeds
      │
   Poller (background thread, every 5 min)
      │
      ├── MongoDB (document store, 30-day retention)
      └── Qdrant (vector index: dense + sparse BM25)
                    │
              FastAPI REST API
              ├── GET  /posts         — browse collected posts
              ├── POST /search        — semantic RAG search via GPT agent
              └── GET  /stats         — collection stats
                    │
              Notifier (per poll cycle)
              └── GPT-4o-mini classifier → Telegram Bot
```

## Stack

| Component | Role |
|---|---|
| FastAPI | REST API |
| MongoDB | Post storage |
| Qdrant | Vector search (dense + sparse) |
| Ollama (`nomic-embed-text`) | Local text embeddings |
| fastembed (BM25) | Sparse keyword embeddings |
| LangChain + GPT-4o-mini | RAG agent, topic classifier |
| python-telegram-bot | Notifications |

## Setup

### 1. Dependencies

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Configuration

```bash
cp .env.example .env
# Edit .env — fill in MongoDB URI, OpenAI key, Telegram token, etc.
```

Key settings in `.env`:

- `NOTIFICATION_TOPICS` — describe in plain English what posts you want. Be specific. The more context, the better GPT filters.
- `SUBREDDITS` — JSON list of subreddits to poll
- `POLL_INTERVAL` — seconds between polls (default: 300)

### 3. External services required

- **MongoDB** — any instance, URI in `MONGO_URI`
- **Qdrant** — vector database, configure host/port in settings
- **Ollama** — must be running with `nomic-embed-text` model pulled:
  ```bash
  ollama pull nomic-embed-text
  ```
- **OpenAI API key** — for GPT-4o-mini (classification + RAG)

### 4. Run

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or with the included VSCode debug config (`.vscode/launch.json`).

### 5. Systemd (production)

```ini
[Unit]
Description=Reddit Monitor API
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/path/to/reddit-monitor
ExecStart=/path/to/.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

## API

### `POST /search`

Ask a natural language question about collected posts.

```json
{
  "question": "what are the best practices for hardening Docker base images?",
  "limit": 5
}
```

Response includes a GPT-generated answer and source posts with excerpts.

### `GET /posts?subreddit=devsecops`

List collected posts, optionally filtered by subreddit.

### `GET /stats`

```json
{
  "total_posts": 1240,
  "indexed": 1238,
  "with_summary": 0
}
```

## Notifications

Subscribe via Telegram: send `/start` to your bot. The bot checks `TELEGRAM_ALLOWED_USERNAMES` — only listed users can subscribe.

Each notification includes the post title, excerpt, and Reddit link. The GPT classifier's reasoning is stored in MongoDB (`notifications` collection) for later review.

## Data retention

Posts older than 30 days are automatically deleted from both MongoDB and Qdrant by a background cleaner thread.
