from fastapi import APIRouter

from app.models import SearchRequest, SearchResponse
from app.services.agent import run_agent

router = APIRouter()


@router.post("/search", response_model=SearchResponse)
def search(request: SearchRequest):
    return run_agent(request.question, request.limit)
