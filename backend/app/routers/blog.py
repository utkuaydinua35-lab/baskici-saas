"""
Vitrin Blogu (admin) — /api/blog/*

Mağaza Paneli'nden blog yazısı CRUD. Public okuma routers/public_shop.py'de
(/{slug}/blog). Shopify Online Store > Blog posts karşılığı.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import require_permission
from app.database import get_db
from app.models import BlogPost, Store, User
from app.routers.catalog import slugify

router = APIRouter(
    prefix="/api/blog", tags=["blog"],
    dependencies=[Depends(require_permission("vitrin"))],
)


class PostCreate(BaseModel):
    store_id: uuid.UUID
    title: str = Field(..., min_length=2, max_length=300)
    slug: str | None = Field(None, max_length=220)
    excerpt: str | None = Field(None, max_length=500)
    content: str = Field("", max_length=100_000)
    cover_url: str | None = Field(None, max_length=500)
    seo_title: str | None = Field(None, max_length=300)
    seo_description: str | None = Field(None, max_length=500)
    is_published: bool = False


class PostUpdate(BaseModel):
    title: str | None = Field(None, min_length=2, max_length=300)
    slug: str | None = Field(None, max_length=220)
    excerpt: str | None = Field(None, max_length=500)
    content: str | None = Field(None, max_length=100_000)
    cover_url: str | None = Field(None, max_length=500)
    seo_title: str | None = Field(None, max_length=300)
    seo_description: str | None = Field(None, max_length=500)
    is_published: bool | None = None


def _serialize(p: BlogPost) -> dict:
    return {
        "id": str(p.id),
        "slug": p.slug,
        "title": p.title,
        "excerpt": p.excerpt,
        "content": p.content,
        "cover_url": p.cover_url,
        "seo_title": p.seo_title,
        "seo_description": p.seo_description,
        "is_published": p.is_published,
        "published_at": p.published_at.isoformat() if p.published_at else None,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def _get_store(db: Session, tenant_id, store_id) -> Store:
    store = db.scalar(select(Store).where(
        Store.id == store_id, Store.tenant_id == tenant_id,
        Store.platform == "storefront",
    ))
    if not store:
        raise HTTPException(404, "Vitrin mağazası bulunamadı")
    return store


@router.get("", response_model=list[dict])
def list_posts(
    store_id: uuid.UUID = Query(...),
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    _get_store(db, user.tenant_id, store_id)
    rows = db.scalars(
        select(BlogPost).where(BlogPost.store_id == store_id)
        .order_by(BlogPost.created_at.desc())
    ).all()
    return [_serialize(p) for p in rows]


@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_post(
    body: PostCreate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    store = _get_store(db, user.tenant_id, body.store_id)
    slug = slugify(body.slug or body.title)
    if db.scalar(select(BlogPost).where(
            BlogPost.store_id == store.id, BlogPost.slug == slug)):
        slug = f"{slug}-{uuid.uuid4().hex[:6]}"
    post = BlogPost(
        tenant_id=user.tenant_id,
        store_id=store.id,
        slug=slug,
        title=body.title.strip(),
        excerpt=body.excerpt,
        content=body.content,
        cover_url=body.cover_url,
        seo_title=body.seo_title,
        seo_description=body.seo_description,
        is_published=body.is_published,
        published_at=datetime.now(timezone.utc) if body.is_published else None,
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return _serialize(post)


@router.patch("/{post_id}", response_model=dict)
def update_post(
    post_id: uuid.UUID,
    body: PostUpdate,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    post = db.scalar(select(BlogPost).where(
        BlogPost.id == post_id, BlogPost.tenant_id == user.tenant_id))
    if not post:
        raise HTTPException(404, "Yazı bulunamadı")

    updates = body.model_dump(exclude_unset=True)
    if "slug" in updates and updates["slug"]:
        new_slug = slugify(updates["slug"])
        clash = db.scalar(select(BlogPost).where(
            BlogPost.store_id == post.store_id, BlogPost.slug == new_slug,
            BlogPost.id != post.id))
        if clash:
            raise HTTPException(409, "Bu adres başka bir yazıda kullanılıyor")
        updates["slug"] = new_slug
    if updates.get("is_published") and not post.published_at:
        post.published_at = datetime.now(timezone.utc)
    for k, v in updates.items():
        setattr(post, k, v)
    db.commit()
    db.refresh(post)
    return _serialize(post)


@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: uuid.UUID,
    user: User = Depends(require_permission("vitrin")),
    db: Session = Depends(get_db),
):
    post = db.scalar(select(BlogPost).where(
        BlogPost.id == post_id, BlogPost.tenant_id == user.tenant_id))
    if not post:
        raise HTTPException(404, "Yazı bulunamadı")
    db.delete(post)
    db.commit()
