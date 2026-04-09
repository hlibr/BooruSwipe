"""SQLAlchemy models for BooruSwipe."""
import json
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import String, Text, TypeDecorator
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class JSONList(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return []
        return json.loads(value)


class JSONDict(TypeDecorator):
    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return {}
        return json.loads(value)


class Swipe(Base):
    """Represents a user swipe (like/dislike) event."""

    __tablename__ = "swipes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    booru: Mapped[str] = mapped_column(String(64), nullable=False)
    image_id: Mapped[str] = mapped_column(String(128), nullable=False)
    post_url: Mapped[str] = mapped_column(String(512), nullable=False)
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    tags: Mapped[List[str]] = mapped_column(JSONList(), nullable=False, default=list)
    liked: Mapped[bool] = mapped_column(nullable=False)
    weight: Mapped[int] = mapped_column(nullable=False, default=1)
    timestamp: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class PreferenceProfile(Base):
    """User preference profile for LLM learning."""

    __tablename__ = "preference_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    preferences: Mapped[dict] = mapped_column(JSONDict(), nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class TagCount(Base):
    """Tag frequency counters for LLM architecture."""

    __tablename__ = "tag_counts"

    tag: Mapped[str] = mapped_column(String(256), primary_key=True)
    liked_count: Mapped[int] = mapped_column(default=0, nullable=False)
    disliked_count: Mapped[int] = mapped_column(default=0, nullable=False)
    last_updated: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class SwipedImage(Base):
    """Tracks all swiped images to prevent repeats."""

    __tablename__ = "swiped_images"

    image_id: Mapped[int] = mapped_column(primary_key=True)
    liked: Mapped[bool] = mapped_column(nullable=False)
    swiped_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class DoubleLikedImage(Base):
    """Tracks double-liked images that should NEVER be ignored."""

    __tablename__ = "double_liked_images"

    image_id: Mapped[int] = mapped_column(primary_key=True)
    liked_at: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
