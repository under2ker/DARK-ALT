from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

def utcnow(): return datetime.now(timezone.utc)

class Wallpaper(Base):
    __tablename__ = "wallpapers"
    id: Mapped[int] = mapped_column(primary_key=True)
    slug: Mapped[str] = mapped_column(String(180), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(100), index=True)
    source_url: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str] = mapped_column(Text)
    thumbnail_url: Mapped[str] = mapped_column(Text)
    author: Mapped[str | None] = mapped_column(String(300), nullable=True)
    license: Mapped[str | None] = mapped_column(String(180), nullable=True)
    license_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    ratio: Mapped[str] = mapped_column(String(20), index=True)
    orientation: Mapped[str] = mapped_column(String(20), index=True)
    resolution: Mapped[str] = mapped_column(String(20), index=True)
    tone: Mapped[str] = mapped_column(String(20), default="NEUTRAL", index=True)
    dominant_color: Mapped[str | None] = mapped_column(String(10), nullable=True)
    brightness: Mapped[float | None] = mapped_column(Float, nullable=True)
    tags: Mapped[list] = mapped_column(JSON, default=list)
    categories: Mapped[list] = mapped_column(JSON, default=list)
    quality_score: Mapped[float] = mapped_column(Float, default=50)
    nsfw_score: Mapped[float] = mapped_column(Float, default=0)
    is_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True)
    provider_key: Mapped[str] = mapped_column(String(80), index=True)
    provider_external_id: Mapped[str] = mapped_column(String(200))
    indexed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("provider_key", "provider_external_id", name="uq_provider_external"),)

class ProviderState(Base):
    __tablename__ = "provider_states"
    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(30), default="ONLINE")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    images_discovered: Mapped[int] = mapped_column(Integer, default=0)
    images_accepted: Mapped[int] = mapped_column(Integer, default=0)
    images_rejected: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    jobs: Mapped[list["CrawlJob"]] = relationship(back_populates="provider")

class CrawlJob(Base):
    __tablename__ = "crawl_jobs"
    id: Mapped[int] = mapped_column(primary_key=True)
    provider_id: Mapped[int] = mapped_column(ForeignKey("provider_states.id"))
    status: Mapped[str] = mapped_column(String(30), default="RUNNING", index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discovered: Mapped[int] = mapped_column(Integer, default=0)
    accepted: Mapped[int] = mapped_column(Integer, default=0)
    duplicates: Mapped[int] = mapped_column(Integer, default=0)
    rejected: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider: Mapped[ProviderState] = relationship(back_populates="jobs")

class ImageAnalysis(Base):
    __tablename__ = "image_analyses"
    id: Mapped[int] = mapped_column(primary_key=True)
    wallpaper_id: Mapped[int] = mapped_column(ForeignKey("wallpapers.id"), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(30), default="PENDING", index=True)
    mime_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    file_size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    phash: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    dhash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ahash: Mapped[str | None] = mapped_column(String(32), nullable=True)
    dominant_color: Mapped[str | None] = mapped_column(String(10), nullable=True, index=True)
    brightness: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    saturation: Mapped[float | None] = mapped_column(Float, nullable=True)
    sharpness: Mapped[float | None] = mapped_column(Float, nullable=True)
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("wallpapers.id"), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    analyzed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class Favorite(Base):
    __tablename__ = "favorites"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    wallpaper_id: Mapped[int] = mapped_column(ForeignKey("wallpapers.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "wallpaper_id", name="uq_user_favorite"),)

class Collection(Base):
    __tablename__ = "collections"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("user_id", "name", name="uq_user_collection_name"),)

class CollectionItem(Base):
    __tablename__ = "collection_items"
    id: Mapped[int] = mapped_column(primary_key=True)
    collection_id: Mapped[int] = mapped_column(ForeignKey("collections.id"), index=True)
    wallpaper_id: Mapped[int] = mapped_column(ForeignKey("wallpapers.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    __table_args__ = (UniqueConstraint("collection_id", "wallpaper_id", name="uq_collection_wallpaper"),)

class Download(Base):
    __tablename__ = "downloads"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    wallpaper_id: Mapped[int] = mapped_column(ForeignKey("wallpapers.id"), index=True)
    variant: Mapped[str] = mapped_column(String(30), default="ORIGINAL")
    downloaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class ViewEvent(Base):
    __tablename__ = "view_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    wallpaper_id: Mapped[int] = mapped_column(ForeignKey("wallpapers.id"), index=True)
    viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

class SearchEvent(Base):
    __tablename__ = "search_events"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    query: Mapped[str] = mapped_column(String(300), index=True)
    result_count: Mapped[int] = mapped_column(Integer, default=0)
    searched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

class UserPreference(Base):
    __tablename__ = "user_preferences"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    preferred_moods: Mapped[list] = mapped_column(JSON, default=list)
    preferred_tones: Mapped[list] = mapped_column(JSON, default=list)
    preferred_resolutions: Mapped[list] = mapped_column(JSON, default=list)
    default_download_preset: Mapped[str] = mapped_column(String(20), default="ORIGINAL")
    allow_questionable: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

class SemanticProfile(Base):
    __tablename__ = "semantic_profiles"
    id: Mapped[int] = mapped_column(primary_key=True)
    wallpaper_id: Mapped[int] = mapped_column(ForeignKey("wallpapers.id"), unique=True, index=True)
    moods: Mapped[list] = mapped_column(JSON, default=list)
    generated_tags: Mapped[list] = mapped_column(JSON, default=list)
    scene: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    style: Mapped[str | None] = mapped_column(String(80), nullable=True, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    classified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    action: Mapped[str] = mapped_column(String(100), index=True)
    target: Mapped[str | None] = mapped_column(String(200), nullable=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
