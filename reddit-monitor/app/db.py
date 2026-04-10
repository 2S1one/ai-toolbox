from pymongo import MongoClient, ASCENDING
from pymongo.collection import Collection
from pymongo.errors import ConnectionFailure
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse

from app.config import settings


def get_mongo() -> Collection:
    client = MongoClient(settings.mongo_uri)
    db = client[settings.mongo_db]
    return db[settings.mongo_collection]


def get_qdrant() -> QdrantClient:
    return QdrantClient(host=settings.qdrant_host, port=settings.qdrant_port, api_key=settings.qdrant_api_key)


def check_mongo(collection: Collection) -> None:
    """Raises RuntimeError if MongoDB is not reachable."""
    try:
        collection.database.client.admin.command("ping")
    except ConnectionFailure as e:
        raise RuntimeError(f"MongoDB unavailable: {e}") from e


def check_qdrant(client: QdrantClient) -> None:
    """Raises RuntimeError if Qdrant is not reachable."""
    try:
        client.get_collections()
    except Exception as e:
        raise RuntimeError(f"Qdrant unavailable: {e}") from e


def ensure_indexes(collection: Collection):
    collection.create_index("reddit_url", unique=True)
    collection.create_index([("subreddit", ASCENDING), ("created_utc", ASCENDING)])
