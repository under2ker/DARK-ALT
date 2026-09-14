from datetime import datetime, timezone
from io import BytesIO
import hashlib
import math

import httpx
import imagehash
from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import ImageAnalysis, Wallpaper

MAX_ANALYSIS_BYTES = 20 * 1024 * 1024
SUPPORTED_FORMATS = {"JPEG", "PNG", "WEBP", "AVIF", "GIF"}

def _color_metrics(image: Image.Image):
    rgb = image.convert("RGB")
    sample = rgb.copy(); sample.thumbnail((160, 160))
    quantized = sample.quantize(colors=8, method=Image.Quantize.MEDIANCUT).convert("RGB")
    colors = quantized.getcolors(maxcolors=256) or []
    _, dominant = max(colors, key=lambda x: x[0]) if colors else (0, (0, 0, 0))
    stat = ImageStat.Stat(sample)
    r, g, b = stat.mean[:3]
    brightness = (0.2126*r + 0.7152*g + 0.0722*b) / 255
    extrema = sample.getextrema()
    saturation = sum((hi-lo)/255 for lo,hi in extrema[:3]) / 3
    return "#%02X%02X%02X" % dominant, round(brightness, 4), round(saturation, 4)

def _sharpness(image: Image.Image):
    gray = image.convert("L"); gray.thumbnail((800, 800))
    edges = gray.filter(ImageFilter.FIND_EDGES)
    return round(ImageStat.Stat(edges).var[0], 2)

def _hash_distance(left: str, right: str) -> int:
    return imagehash.hex_to_hash(left) - imagehash.hex_to_hash(right)

async def analyze_wallpaper(db: Session, wallpaper: Wallpaper):
    record = db.scalar(select(ImageAnalysis).where(ImageAnalysis.wallpaper_id == wallpaper.id))
    if not record:
        record = ImageAnalysis(wallpaper_id=wallpaper.id); db.add(record); db.flush()
    record.status = "RUNNING"; record.error = None; db.commit()
    try:
        async with httpx.AsyncClient(timeout=settings.request_timeout, headers={"User-Agent":settings.user_agent}, follow_redirects=True) as client:
            response = await client.get(wallpaper.thumbnail_url)
            response.raise_for_status()
            raw = response.content
        if len(raw) > MAX_ANALYSIS_BYTES: raise ValueError("Image exceeds 20 MB analysis limit")
        with Image.open(BytesIO(raw)) as image:
            image.load()
            if image.format not in SUPPORTED_FORMATS: raise ValueError(f"Unsupported image format: {image.format}")
            record.mime_type = response.headers.get("content-type") or Image.MIME.get(image.format)
            record.file_size = len(raw)
            record.sha256 = hashlib.sha256(raw).hexdigest()
            record.phash = str(imagehash.phash(image)); record.dhash = str(imagehash.dhash(image)); record.ahash = str(imagehash.average_hash(image))
            record.dominant_color, record.brightness, record.saturation = _color_metrics(image)
            record.sharpness = _sharpness(image)
        exact = db.scalar(select(ImageAnalysis).where(ImageAnalysis.sha256 == record.sha256, ImageAnalysis.wallpaper_id != wallpaper.id))
        if exact: record.duplicate_of_id = exact.wallpaper_id
        elif record.phash:
            candidates = db.scalars(select(ImageAnalysis).where(ImageAnalysis.phash.is_not(None), ImageAnalysis.wallpaper_id != wallpaper.id)).all()
            near = next((x for x in candidates if _hash_distance(record.phash, x.phash) <= 4), None)
            if near: record.duplicate_of_id = near.wallpaper_id
        wallpaper.content_hash = record.sha256 if not record.duplicate_of_id else None
        wallpaper.dominant_color = record.dominant_color; wallpaper.brightness = record.brightness
        wallpaper.tone = "DARK" if record.brightness < .36 else "LIGHT" if record.brightness > .68 else "NEUTRAL"
        sharpness_score = min(20, math.sqrt(max(record.sharpness, 0)) * 1.7)
        resolution_score = min(45, max(wallpaper.width, wallpaper.height) / 180)
        wallpaper.quality_score = round(min(100, 30 + resolution_score + sharpness_score), 2)
        record.status = "DUPLICATE" if record.duplicate_of_id else "SUCCESS"
    except (httpx.HTTPError, UnidentifiedImageError, OSError, ValueError) as exc:
        record.status = "ERROR"; record.error = str(exc)[:1000]
    record.analyzed_at = datetime.now(timezone.utc); db.commit(); db.refresh(record)
    return record

async def analyze_pending(db: Session, limit: int = 10):
    analyzed_ids = select(ImageAnalysis.wallpaper_id)
    wallpapers = db.scalars(select(Wallpaper).where(Wallpaper.id.not_in(analyzed_ids)).order_by(Wallpaper.id).limit(limit)).all()
    results = []
    for wallpaper in wallpapers: results.append(await analyze_wallpaper(db, wallpaper))
    return results
