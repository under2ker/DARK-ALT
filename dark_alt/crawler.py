from datetime import datetime, timezone
from sqlalchemy import select
from sqlalchemy.orm import Session
from .models import CrawlJob, ProviderState, Wallpaper
from .provider_registry import enabled_providers
from .utils import clean_url, ratio_label, resolution_label, slugify
from .provider_safety import robots_allowed
from .config import settings

async def crawl_provider(db: Session, provider_key: str, limit: int = 20):
    match=next(((p,cfg) for p,cfg in enabled_providers() if p.key==provider_key),None)
    if not match: raise ValueError(f"Provider '{provider_key}' is missing or disabled")
    provider,_=match
    endpoint=getattr(provider,"endpoint",None)
    if endpoint and not await robots_allowed(endpoint,settings.user_agent,settings.request_timeout):
        raise ValueError(f"robots.txt does not allow crawling {provider.name}")
    state=db.scalar(select(ProviderState).where(ProviderState.key==provider.key))
    if not state:
        state=ProviderState(key=provider.key,name=provider.name,enabled=True); db.add(state); db.flush()
    job=CrawlJob(provider_id=state.id); db.add(job); db.commit(); db.refresh(job)
    try:
        items=await provider.fetch(limit); job.discovered=len(items); state.images_discovered+=len(items)
        for item in items:
            exists=db.scalar(select(Wallpaper).where(Wallpaper.provider_key==provider.key,Wallpaper.provider_external_id==item.external_id))
            if exists: job.duplicates+=1; state.duplicates+=1; continue
            if item.width<1280 or item.height<720: job.rejected+=1; state.images_rejected+=1; continue
            db.add(Wallpaper(slug=f"{slugify(item.title)}-{item.external_id}",title=item.title,description=item.description,
                source=provider.name,source_url=clean_url(item.source_url),image_url=clean_url(item.image_url),thumbnail_url=clean_url(item.thumbnail_url),
                author=item.author,license=item.license,license_url=item.license_url,width=item.width,height=item.height,
                ratio=ratio_label(item.width,item.height),orientation="landscape" if item.width>=item.height else "portrait",
                resolution=resolution_label(item.width,item.height),tone="NEUTRAL",tags=item.tags,categories=["FEATURED"],
                quality_score=min(100,55+max(item.width,item.height)/180),provider_key=provider.key,provider_external_id=item.external_id))
            job.accepted+=1; state.images_accepted+=1
        job.status="SUCCESS"; state.status="ONLINE"; state.last_success_at=datetime.now(timezone.utc)
    except Exception as exc:
        job.status="ERROR"; job.error=str(exc); state.status="ERROR"; state.last_error=str(exc); state.last_error_at=datetime.now(timezone.utc)
    finally:
        job.finished_at=datetime.now(timezone.utc); db.commit(); db.refresh(job)
    return job
