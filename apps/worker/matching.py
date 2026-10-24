"""Run a worker and one beat scheduler; broker must use durable Redis persistence."""

from celery import Celery
from fastapi import HTTPException
from kombu.exceptions import OperationalError as BrokerError
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from apps.api.applyos.config import settings
from apps.api.applyos.db import make_database
from apps.api.applyos.jobs_models import JobPosting
from apps.api.applyos.match_service import match_job
from apps.api.applyos.models import CandidateProfile

app = Celery("applyos-matching", broker=settings().redis_url.get_secret_value())
app.conf.update(
    task_default_queue="matching",
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    task_ignore_result=True,
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 300},
    task_soft_time_limit=90,
    task_time_limit=120,
    beat_schedule={"reconcile-matches": {"task": "matching.reconcile", "schedule": 300.0}},
)


def match_batch(cursor="", limit=50):
    """Bounded, indexed pages. Read IDs only; current inputs are reread in each task.

    Reconciliation recovers missed change notifications and broker outages.
    Repeated delivery is safe because matching hashes all current inputs.
    """
    engine, sessions = make_database(settings())
    try:
        with sessions() as db:
            return list(
                db.execute(
                    select(JobPosting.id, JobPosting.owner_id)
                    .join(CandidateProfile, CandidateProfile.owner_id == JobPosting.owner_id)
                    .where(JobPosting.id > cursor, CandidateProfile.revision > 0)
                    .order_by(JobPosting.id)
                    .limit(min(50, max(1, limit)))
                ).all()
            )
    finally:
        engine.dispose()


@app.task(
    name="matching.reconcile",
    autoretry_for=(SQLAlchemyError, OSError, BrokerError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def reconcile(cursor=""):
    rows = match_batch(cursor)
    for key, owner in rows:
        calculate_job.apply_async(args=[owner, key], queue="matching")
    if len(rows) == 50:
        reconcile.apply_async(args=[rows[-1][0]], queue="matching")
    return len(rows)


@app.task(
    name="matching.calculate",
    autoretry_for=(SQLAlchemyError, OSError),
    retry_backoff=True,
    retry_jitter=True,
    max_retries=5,
)
def calculate_job(owner, key):
    engine, sessions = make_database(settings())
    try:
        with sessions() as db:
            try:
                return match_job(db, owner, key)["id"]
            except HTTPException as error:
                # Deleted jobs/profiles are terminal, not retry storms.
                if error.status_code in (404, 409):
                    return None
                raise
    finally:
        engine.dispose()
