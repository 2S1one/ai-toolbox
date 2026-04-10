import logging
import time
import uuid

from fastembed import SparseTextEmbedding
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from qdrant_client.models import Distance, PointStruct, SparseVector, SparseVectorParams, VectorParams

from app.config import settings

log = logging.getLogger(__name__)

_dense = OllamaEmbeddings(model=settings.embed_model, base_url=settings.ollama_url)
_sparse = SparseTextEmbedding(model_name=settings.sparse_model)
_splitter = RecursiveCharacterTextSplitter(chunk_size=settings.chunk_size, chunk_overlap=settings.chunk_overlap)


def _ensure_collection(qdrant, vector_size: int):
    if settings.qdrant_collection not in [c.name for c in qdrant.get_collections().collections]:
        qdrant.create_collection(
            collection_name=settings.qdrant_collection,
            vectors_config={"dense": VectorParams(size=vector_size, distance=Distance.COSINE)},
            sparse_vectors_config={"sparse": SparseVectorParams()},
        )
        log.info("Created Qdrant collection: %s", QDRANT_COLLECTION)


def index_doc(doc: dict, qdrant, mongo) -> bool:
    parts = [doc.get("title", "")]
    if doc.get("selftext"):
        parts.append(doc["selftext"])
    text = "\n\n".join(parts)
    chunks = _splitter.split_text(text)

    for attempt in range(3):
        try:
            dense_vectors = _dense.embed_documents(chunks)
            break
        except Exception as e:
            wait = 2 ** attempt
            log.warning("Embedding failed (attempt %d): %s, retrying in %ds", attempt + 1, e, wait)
            time.sleep(wait)
    else:
        log.error("Skipping %s after 3 failed attempts", doc["_id"])
        return False

    sparse_vectors = list(_sparse.embed(chunks))
    _ensure_collection(qdrant, len(dense_vectors[0]))

    points = [
        PointStruct(
            id=str(uuid.uuid5(uuid.NAMESPACE_OID, f"{doc['_id']}:{j}")),
            vector={
                "dense": dense_vector,
                "sparse": SparseVector(
                    indices=sv.indices.tolist(),
                    values=sv.values.tolist(),
                ),
            },
            payload={
                "mongo_id": str(doc["_id"]),
                "reddit_url": doc.get("reddit_url", ""),
                "title": doc.get("title", ""),
                "subreddit": doc.get("subreddit", ""),
                "chunk": chunk,
            },
        )
        for j, (chunk, dense_vector, sv) in enumerate(zip(chunks, dense_vectors, sparse_vectors))
    ]

    qdrant.upsert(collection_name=settings.qdrant_collection, points=points)
    mongo.update_one({"_id": doc["_id"]}, {"$set": {"indexed": True}})
    return True
