from datetime import datetime

from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    subreddit: str
    title: str
    reddit_url: str
    external_url: str | None = None
    author: str | None = None
    selftext: str | None = None
    created_utc: int
    fetched_at: datetime


class Post(BaseModel):
    id: str = Field(alias="_id")
    subreddit: str
    title: str
    reddit_url: str
    external_url: str | None = None
    author: str | None = None
    selftext: str | None = None
    summary: str | None = None
    created_utc: int
    fetched_at: datetime
    indexed: bool = False

    model_config = {"populate_by_name": True}


class PostList(BaseModel):
    posts: list[Post]
    total: int


class StatsResponse(BaseModel):
    total_posts: int
    indexed: int
    with_summary: int



class IndexResponse(BaseModel):
    indexed: int


class SearchRequest(BaseModel):
    question: str
    limit: int = Field(default=5, ge=1, le=50)


class SearchSource(BaseModel):
    title: str
    subreddit: str
    reddit_url: str
    excerpt: str | None = None


class SearchResponse(BaseModel):
    answer: str
    sources: list[SearchSource] = []


class NotificationPost(BaseModel):
    id: str
    title: str
    text: str


class ClassifiedPost(BaseModel):
    id: str
    reason: str


class ClassifierResponse(BaseModel):
    relevant: list[ClassifiedPost]


class TelegramNotification(BaseModel):
    subreddit: str
    title: str
    reddit_url: str
    excerpt: str | None = None

    def format_message(self) -> str:
        lines = [f"[{self.subreddit}] {self.title}", ""]
        if self.excerpt:
            lines += [self.excerpt, ""]
        lines.append(f"🔗 {self.reddit_url}")
        return "\n".join(lines)
