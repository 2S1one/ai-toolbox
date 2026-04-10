from bson import ObjectId
from pymongo.collection import Collection

from app.models import Post, PostList, StatsResponse, IndexResponse


def _to_post(doc: dict) -> Post:
    doc["_id"] = str(doc["_id"])
    return Post(**doc)


def get_posts(collection: Collection, subreddit: str | None, limit: int, offset: int) -> PostList:
    query = {"subreddit": subreddit} if subreddit else {}
    docs = collection.find(query).skip(offset).limit(limit).sort("created_utc", -1)
    posts = [_to_post(d) for d in docs]
    total = collection.count_documents(query)
    return PostList(posts=posts, total=total)


def get_post_by_id(collection: Collection, post_id: str) -> Post | None:
    doc = collection.find_one({"_id": ObjectId(post_id)})
    return _to_post(doc) if doc else None


def get_stats(collection: Collection) -> StatsResponse:
    return StatsResponse(
        total_posts=collection.count_documents({}),
        indexed=collection.count_documents({"indexed": True}),
        with_summary=collection.count_documents({"summary": {"$ne": None}}),
    )



def run_index(collection: Collection, qdrant, index_fn) -> IndexResponse:
    query = {"indexed": {"$ne": True}}
    docs = list(collection.find(query))
    indexed = 0
    for doc in docs:
        if index_fn(doc, qdrant, collection):
            indexed += 1
    return IndexResponse(indexed=indexed)
