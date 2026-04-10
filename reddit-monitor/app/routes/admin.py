from fastapi import APIRouter

from app.db import get_mongo, get_qdrant
from app.models import IndexResponse, StatsResponse
from app.services.indexer import index_doc
from app.services.posts import get_stats, run_index

router = APIRouter()


@router.post("/index/run", response_model=IndexResponse)
def index_run():
    return run_index(get_mongo(), get_qdrant(), index_doc)


@router.get("/stats", response_model=StatsResponse)
def stats():
    return get_stats(get_mongo())
