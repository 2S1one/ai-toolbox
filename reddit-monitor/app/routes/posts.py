from fastapi import APIRouter, HTTPException, Query

from app.db import get_mongo
from app.models import Post, PostList
from app.services.posts import get_post_by_id, get_posts

router = APIRouter()


@router.get("/posts", response_model=PostList)
def list_posts(
    subreddit: str | None = Query(None),
    limit: int = Query(20, le=100),
    offset: int = Query(0),
):
    return get_posts(get_mongo(), subreddit, limit, offset)


@router.get("/posts/{post_id}", response_model=Post)
def get_post(post_id: str):
    try:
        post = get_post_by_id(get_mongo(), post_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid post_id")
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post
