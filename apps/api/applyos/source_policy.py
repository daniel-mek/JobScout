"""Operator-only policy review. Account routes cannot approve providers."""

import argparse

from packages.job_sources.catalog import ADAPTERS
from packages.job_sources.safe_http import public_url

from .config import settings
from .db import make_database
from .jobs_models import SourcePolicy
from .jobs_service import sanitize_policy_history
from .models import now


def main():
    parser = argparse.ArgumentParser(description="Record completed source review and enforce retention.")
    parser.add_argument("provider", choices=sorted(ADAPTERS))
    parser.add_argument("--status", choices=("APPROVED", "NEEDS_REVIEW", "DISABLED"), required=True)
    parser.add_argument("--terms-url", required=True)
    parser.add_argument(
        "--evidence", required=True, help="Review reference, permission scope and retention obligations."
    )
    parser.add_argument("--description-storage", choices=("allowed", "prohibited", "unknown"), required=True)
    parser.add_argument("--attribution", required=True)
    parser.add_argument(
        "--board",
        action="append",
        required=True,
        help="Approved board ID; repeat as needed. '*' requires provider-wide permission evidence.",
    )
    parser.add_argument("--interval", type=int, default=2)
    parser.add_argument("--run-interval", type=int, default=300)
    args = parser.parse_args()
    if (
        len(args.evidence.strip()) < 30
        or not 1 <= args.interval <= 10
        or not 60 <= args.run_interval <= 86400
    ):
        parser.error("Provide substantive evidence and valid rate limits (1–10 / 60–86400 seconds).")
    url = public_url(args.terms_url)
    engine, sessions = make_database(settings())
    try:
        with sessions() as db:
            policy = db.get(SourcePolicy, args.provider, with_for_update=True)
            if policy is None:
                parser.error("Run migrations first.")
            policy.status, policy.enabled = args.status, args.status == "APPROVED"
            policy.terms_url, policy.evidence, policy.reviewed_at = url, args.evidence, now()
            policy.description_storage, policy.attribution = args.description_storage, args.attribution[:200]
            policy.approved_boards = args.board
            policy.rate_limit = {
                "min_interval_seconds": args.interval,
                "run_interval_seconds": args.run_interval,
                "max_pages": 4,
            }
            policy.redistribution = "private_only"
            sanitize_policy_history(db, policy)
            db.commit()
    finally:
        engine.dispose()
    print("Policy recorded; restricted live and historical content purged where required.")


if __name__ == "__main__":
    main()
