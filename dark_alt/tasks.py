import asyncio
from .celery_app import celery_app
from .crawler import crawl_provider
from .database import Base, SessionLocal, engine
from .image_analysis import analyze_pending
from .semantic import classify_pending

@celery_app.task(name="dark_alt.crawl_provider", autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries":3})
def crawl_provider_task(provider_key: str, limit: int = 20):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        job=asyncio.run(crawl_provider(db,provider_key,limit))
        return {"job_id":job.id,"status":job.status,"accepted":job.accepted,"duplicates":job.duplicates}

@celery_app.task(name="dark_alt.analyze_pending", autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries":3})
def analyze_pending_task(limit: int = 20):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        results=asyncio.run(analyze_pending(db,limit))
        return {"processed":len(results),"success":sum(x.status=="SUCCESS" for x in results),"errors":sum(x.status=="ERROR" for x in results)}

@celery_app.task(name="dark_alt.classify_pending", autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={"max_retries":3})
def classify_pending_task(limit: int = 100):
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        profiles=classify_pending(db,limit)
        return {"processed":len(profiles)}
