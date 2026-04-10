"""
Topic matching test.
For each topic runs two classifiers against all posts in MongoDB:
  - Embedding: semantic search via Qdrant
  - LLM: Mistral YES/NO classifier (one request per post per topic)
Prints per-topic statistics and matched posts.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import OllamaEmbeddings
from qdrant_client.models import Fusion, FusionQuery, Prefetch, SparseVector
from fastembed import SparseTextEmbedding

from app.config import settings
from app.db import get_mongo, get_qdrant

# ── Topics ────────────────────────────────────────────────────────────────────

TOPICS = {
    "Docker hardening": (
        "hardened container images, Docker image hardening, "
        "CVE remediation container, SBOM signed image, CIS Docker benchmark, "
        "container security compliance, dockerfile hardening"
    ),
}

# ── Thresholds ─────────────────────────────────────────────────────────────────

EMBED_THRESHOLD = 0.5   # Qdrant RRF score
EMBED_TOP_K     = 50    # max candidates from Qdrant per topic

# ── Clients ────────────────────────────────────────────────────────────────────

_mongo  = get_mongo()
_qdrant = get_qdrant()
_dense  = OllamaEmbeddings(model=settings.embed_model, base_url=settings.ollama_url)
_sparse = SparseTextEmbedding(model_name=settings.sparse_model)

from app.services.agent import get_classifier_llm
_llm = get_classifier_llm()

# ── Classifiers ────────────────────────────────────────────────────────────────

def embed_matches(topic_description: str) -> set[str]:
    """Return set of reddit_urls that match the topic via hybrid search."""
    dense_vec  = _dense.embed_query(topic_description)
    sparse_vec = list(_sparse.embed([topic_description]))[0]

    results = _qdrant.query_points(
        collection_name=settings.qdrant_collection,
        prefetch=[
            Prefetch(query=dense_vec, using="dense", limit=EMBED_TOP_K),
            Prefetch(
                query=SparseVector(
                    indices=sparse_vec.indices.tolist(),
                    values=sparse_vec.values.tolist(),
                ),
                using="sparse",
                limit=EMBED_TOP_K,
            ),
        ],
        query=FusionQuery(fusion=Fusion.RRF),
        limit=EMBED_TOP_K,
        with_payload=True,
    )

    return {
        hit.payload["reddit_url"]
        for hit in results.points
        if hit.score >= EMBED_THRESHOLD and hit.payload.get("reddit_url")
    }


def llm_matches(posts: list[dict], topic_name: str, topic_description: str) -> set[str]:
    """Return set of reddit_urls classified as relevant by GPT."""
    system_prompt = (
        f"You are a classifier. Determine if a Reddit post is relevant to the following topic:\n"
        f"TOPIC: {topic_description}\n\n"
        f"Reply with exactly one word: YES if relevant, NO if not relevant. Nothing else."
    )
    matched = set()

    for post in posts:
        text = f"Title: {post.get('title', '')}"
        if post.get("summary"):
            text += f"\nSummary: {post['summary']}"
        elif post.get("selftext"):
            text += f"\nText: {post['selftext'][:500]}"

        try:
            resp = _llm.invoke([SystemMessage(system_prompt), HumanMessage(text)])
            answer = resp.content.strip().upper()
            if answer.startswith("YES"):
                matched.add(post["reddit_url"])
        except Exception as e:
            print(f"  [LLM error] {post.get('title', '')[:60]}: {e}")

    return matched


# ── Main ───────────────────────────────────────────────────────────────────────

def run():
    posts = list(_mongo.find({}, {"_id": 0, "reddit_url": 1, "title": 1, "selftext": 1, "summary": 1}))
    total = len(posts)
    url_to_post = {p["reddit_url"]: p for p in posts}

    print(f"\nTotal posts in MongoDB: {total}\n")

    for topic_name, topic_description in TOPICS.items():
        print(f"{'═' * 65}")
        print(f"  TOPIC: {topic_name}")
        print(f"{'═' * 65}")

        print(f"\n  [Embedding] searching...")
        embed_urls = embed_matches(topic_description)

        print(f"  [LLM]       classifying {total} posts (one request per post)...")
        llm_urls = llm_matches(posts, topic_name, topic_description)

        both_urls   = embed_urls & llm_urls
        only_embed  = embed_urls - llm_urls
        only_llm    = llm_urls - embed_urls
        union_urls  = embed_urls | llm_urls

        print(f"\n  ── Statistics ──────────────────────────────────────────")
        print(f"  Embedding only : {len(only_embed)}")
        print(f"  LLM only       : {len(only_llm)}")
        print(f"  Both agree     : {len(both_urls)}")
        print(f"  Total matched  : {len(union_urls)} / {total}")

        if union_urls:
            print(f"\n  ── Matched posts ───────────────────────────────────────")
            for url in sorted(union_urls):
                post = url_to_post.get(url, {})
                tag = ""
                if url in both_urls:
                    tag = "[embed+llm]"
                elif url in only_embed:
                    tag = "[embed]    "
                else:
                    tag = "[llm]      "
                print(f"  {tag} {post.get('title', url)[:70]}")
                print(f"             {url}")

        print()


if __name__ == "__main__":
    run()
