import logging

from fastembed import SparseTextEmbedding
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langchain_ollama import OllamaEmbeddings
from langchain_openai import ChatOpenAI
from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector

from app.config import settings
from app.db import get_mongo, get_qdrant
from app.models import SearchResponse, SearchSource

log = logging.getLogger(__name__)

_qdrant = get_qdrant()
_dense = OllamaEmbeddings(model=settings.embed_model, base_url=settings.ollama_url)
_sparse = SparseTextEmbedding(model_name=settings.sparse_model)

SYSTEM_PROMPT = (
    "You are a helpful assistant that searches Reddit security posts. "
    "Use the search_posts tool to find relevant posts. "
    "IMPORTANT: Only use URLs and titles exactly as returned by the search tool. "
    "Never invent or modify URLs, titles, or post content. "
    "If search returns no results or irrelevant results, rephrase the query and try again. "
    "Make up to 3 search attempts with different queries before concluding nothing was found. "
    "If the search results do not directly answer the question, say so clearly. "
    "Do not include posts that are only loosely related — only include posts that genuinely answer the question."
)


@tool
def search_posts(query: str) -> str:
    """Search Reddit security posts by semantic meaning.
    Use this to find posts related to a topic, vulnerability, or concept.
    Input should be a short English search query.
    """
    log.info("Searching: %s", query)
    dense_vector = _dense.embed_query(query)
    sparse_vector = list(_sparse.embed([query]))[0]

    results = _qdrant.query_points(
        collection_name=settings.qdrant_collection,
        prefetch=[
            Prefetch(query=dense_vector, using="dense", limit=20),
            Prefetch(
                query=SparseVector(
                    indices=sparse_vector.indices.tolist(),
                    values=sparse_vector.values.tolist(),
                ),
                using="sparse",
                limit=20,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=settings.top_k,
        with_payload=True,
    )

    hits = [h for h in results.points if h.score >= settings.score_threshold]
    if not hits:
        return "No relevant posts found."

    lines = []
    for hit in hits:
        p = hit.payload
        lines.append(
            f"- [{p.get('subreddit')}] {p.get('title')} (score: {hit.score:.2f})\n"
            f"  url: {p.get('reddit_url')}\n"
            f"  excerpt: {p.get('chunk', '')[:200]}"
        )
    return "\n\n".join(lines)


def get_llm():
    return ChatOpenAI(model=settings.openai_llm_model, api_key=settings.openai_api_key)


def get_classifier_llm():
    return ChatOpenAI(model=settings.openai_llm_model, api_key=settings.openai_api_key, temperature=0)


def run_agent(question: str, limit: int = 5) -> SearchResponse:
    llm = get_llm().bind_tools([search_posts])
    messages = [SystemMessage(SYSTEM_PROMPT), HumanMessage(question)]
    seen_urls: set[str] = set()

    for _ in range(settings.max_iterations):
        response = llm.invoke(messages)
        messages.append(response)

        if not response.tool_calls:
            sources = _build_sources(seen_urls, limit)
            return SearchResponse(answer=response.content, sources=sources)

        for tc in response.tool_calls:
            result = search_posts.invoke(tc["args"])
            messages.append(ToolMessage(content=result, tool_call_id=tc["id"]))
            _extract_urls(result, seen_urls)

    return SearchResponse(answer="Max iterations reached without a final answer.")


def _extract_urls(tool_result: str, seen_urls: set[str]):
    import re
    for url in re.findall(r"url: (https://\S+)", tool_result):
        seen_urls.add(url)


def _build_sources(urls: set[str], limit: int = 5) -> list[SearchSource]:
    if not urls:
        return []
    mongo = get_mongo()
    sources = []
    for doc in mongo.find({"reddit_url": {"$in": list(urls)}}).limit(limit):
        selftext = doc.get("selftext") or ""
        sources.append(SearchSource(
            title=doc.get("title", ""),
            subreddit=doc.get("subreddit", ""),
            reddit_url=doc.get("reddit_url", ""),
            excerpt=selftext[:200] if selftext else None,
        ))
    return sources
