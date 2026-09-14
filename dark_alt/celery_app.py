from celery import Celery
from .config import settings

celery_app = Celery("dark_alt", broker=settings.redis_url, backend=settings.redis_url, include=["dark_alt.tasks"])
celery_app.conf.update(
    task_serializer="json", result_serializer="json", accept_content=["json"],
    task_track_started=True, worker_prefetch_multiplier=1,
    task_acks_late=True, broker_connection_retry_on_startup=True,
    timezone="UTC", enable_utc=True,
    beat_schedule={
        "wikimedia-six-hour-index": {"task":"dark_alt.crawl_provider", "schedule":21600.0, "args":["wikimedia",20]},
        "nasa-six-hour-index": {"task":"dark_alt.crawl_provider", "schedule":21600.0, "args":["nasa",20]},
        "analysis-every-ten-minutes": {"task":"dark_alt.analyze_pending", "schedule":600.0, "args":[20]},
        "semantic-every-thirty-minutes": {"task":"dark_alt.classify_pending", "schedule":1800.0, "args":[100]},
    },
)
