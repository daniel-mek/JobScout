"""Phase 2 source policies jobs provenance and runs

Revision ID: 98c00bbaf877
Revises: 7d1c7a05375f
"""

import json

import sqlalchemy as sa
from alembic import op

revision = "98c00bbaf877"
down_revision = "7d1c7a05375f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "source_policies",
        sa.Column("id", sa.String(length=60), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("documentation_url", sa.Text(), nullable=False),
        sa.Column("terms_url", sa.Text(), nullable=False),
        sa.Column("retrieval_method", sa.String(length=40), nullable=False),
        sa.Column("credentials", sa.JSON(), nullable=False),
        sa.Column("approved_boards", sa.JSON(), nullable=False),
        sa.Column("attribution", sa.String(length=200), nullable=False),
        sa.Column("source_link_required", sa.Boolean(), nullable=False),
        sa.Column("rate_limit", sa.JSON(), nullable=False),
        sa.Column("description_storage", sa.String(length=30), nullable=False),
        sa.Column("redistribution", sa.String(length=30), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("reviewed_at", sa.String(length=40), nullable=True),
        sa.Column("evidence", sa.Text(), nullable=False),
        sa.Column("adapter_version", sa.String(length=40), nullable=False),
        sa.Column("next_run_at", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "companies",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("normalized_name", sa.String(length=200), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "normalized_name"),
    )
    op.create_index(op.f("ix_companies_owner_id"), "companies", ["owner_id"], unique=False)
    op.create_table(
        "job_sources",
        sa.Column("cursor", sa.Integer(), nullable=False),
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("policy_id", sa.String(length=60), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("board", sa.String(length=200), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["policy_id"],
            ["source_policies.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "policy_id", "board"),
    )
    op.create_index(op.f("ix_job_sources_owner_id"), "job_sources", ["owner_id"], unique=False)
    op.create_table(
        "saved_searches",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("source_ids", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_saved_searches_owner_id"), "saved_searches", ["owner_id"], unique=False)
    op.create_table(
        "search_titles",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("role_family_id", sa.String(length=60), nullable=True),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["role_family_id"],
            ["role_families.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "title"),
    )
    op.create_index(op.f("ix_search_titles_owner_id"), "search_titles", ["owner_id"], unique=False)
    op.create_table(
        "job_postings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("company_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("normalized_title", sa.String(length=300), nullable=False),
        sa.Column("location", sa.String(length=300), nullable=True),
        sa.Column("country", sa.String(length=100), nullable=True),
        sa.Column("arrangement", sa.String(length=30), nullable=True),
        sa.Column("employment_type", sa.String(length=60), nullable=True),
        sa.Column("canonical_url", sa.String(length=2000), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("content_source_id", sa.String(length=36), nullable=False),
        sa.Column("discovered_at", sa.String(length=40), nullable=False),
        sa.Column("last_seen_at", sa.String(length=40), nullable=False),
        sa.Column("posted_at", sa.String(length=40), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("fingerprint", sa.String(length=64), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(
            ["company_id"],
            ["companies.id"],
        ),
        sa.ForeignKeyConstraint(
            ["content_source_id"],
            ["job_sources.id"],
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_id", "canonical_url"),
    )
    op.create_index(op.f("ix_job_postings_company_id"), "job_postings", ["company_id"], unique=False)
    op.create_index(
        op.f("ix_job_postings_normalized_title"), "job_postings", ["normalized_title"], unique=False
    )
    op.create_index(op.f("ix_job_postings_owner_id"), "job_postings", ["owner_id"], unique=False)
    op.create_table(
        "search_runs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("owner_id", sa.String(length=36), nullable=False),
        sa.Column("saved_search_id", sa.String(length=36), nullable=True),
        sa.Column("started_at", sa.String(length=40), nullable=False),
        sa.Column("finished_at", sa.String(length=40), nullable=True),
        sa.Column("state", sa.String(length=30), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["saved_search_id"],
            ["saved_searches.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_search_runs_owner_id"), "search_runs", ["owner_id"], unique=False)
    op.create_table(
        "source_health",
        sa.Column("cycle_started_at", sa.String(length=40), nullable=True),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("state", sa.String(length=40), nullable=False),
        sa.Column("last_success", sa.String(length=40), nullable=True),
        sa.Column("last_failure", sa.String(length=40), nullable=True),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("failures", sa.Integer(), nullable=False),
        sa.Column("next_run_at", sa.Integer(), nullable=False),
        sa.Column("last_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["source_id"], ["job_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("source_id"),
    )
    op.create_table(
        "job_posting_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.String(length=40), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job_postings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["job_sources.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", "version"),
    )
    op.create_index(op.f("ix_job_posting_versions_job_id"), "job_posting_versions", ["job_id"], unique=False)
    op.create_table(
        "job_source_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("source_id", sa.String(length=36), nullable=False),
        sa.Column("job_id", sa.String(length=36), nullable=False),
        sa.Column("external_id", sa.String(length=200), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.String(length=40), nullable=False),
        sa.Column("posted_at", sa.String(length=40), nullable=True),
        sa.Column("last_seen_at", sa.String(length=40), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("normalized_data", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["job_postings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["job_sources.id"],
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "external_id"),
    )
    op.create_index(op.f("ix_job_source_records_job_id"), "job_source_records", ["job_id"], unique=False)
    op.create_index(
        op.f("ix_job_source_records_source_id"), "job_source_records", ["source_id"], unique=False
    )
    policies = sa.table(
        "source_policies",
        sa.column("id", sa.String()),
        sa.column("display_name", sa.String()),
        sa.column("category", sa.String()),
        sa.column("documentation_url", sa.String()),
        sa.column("terms_url", sa.String()),
        sa.column("retrieval_method", sa.String()),
        sa.column("credentials", sa.JSON()),
        sa.column("approved_boards", sa.JSON()),
        sa.column("attribution", sa.String()),
        sa.column("source_link_required", sa.Boolean()),
        sa.column("rate_limit", sa.JSON()),
        sa.column("description_storage", sa.String()),
        sa.column("redistribution", sa.String()),
        sa.column("enabled", sa.Boolean()),
        sa.column("status", sa.String()),
        sa.column("reviewed_at", sa.String()),
        sa.column("evidence", sa.String()),
        sa.column("adapter_version", sa.String()),
        sa.column("next_run_at", sa.Integer()),
    )
    rows = [
        {
            "adapter_version": "1",
            "attribution": "Greenhouse",
            "category": "api",
            "credentials": [],
            "description_storage": "unknown",
            "display_name": "Greenhouse",
            "documentation_url": "https://docs.greenhouse.io/job-board",
            "enabled": False,
            "evidence": "Technical docs reviewed; storage/usage permission still requires review.",
            "id": "greenhouse",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": None,
            "source_link_required": True,
            "status": "NEEDS_REVIEW",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "Lever",
            "category": "api",
            "credentials": [],
            "description_storage": "unknown",
            "display_name": "Lever",
            "documentation_url": "https://github.com/lever/postings-api",
            "enabled": False,
            "evidence": "Technical docs reviewed; storage/usage permission still requires review.",
            "id": "lever",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": None,
            "source_link_required": True,
            "status": "NEEDS_REVIEW",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "Ashby",
            "category": "api",
            "credentials": [],
            "description_storage": "unknown",
            "display_name": "Ashby",
            "documentation_url": "https://developers.ashbyhq.com/docs/public-job-posting-api",
            "enabled": False,
            "evidence": "Technical docs reviewed; storage/usage permission still requires review.",
            "id": "ashby",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": None,
            "source_link_required": True,
            "status": "NEEDS_REVIEW",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "SmartRecruiters",
            "category": "api",
            "credentials": [],
            "description_storage": "unknown",
            "display_name": "SmartRecruiters",
            "documentation_url": "https://developers.smartrecruiters.com/docs/posting-api",
            "enabled": False,
            "evidence": "Technical docs reviewed; storage/usage permission still requires review.",
            "id": "smartrecruiters",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": None,
            "source_link_required": True,
            "status": "NEEDS_REVIEW",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "USAJOBS",
            "category": "api",
            "credentials": ["USAJOBS_API_KEY", "USAJOBS_EMAIL"],
            "description_storage": "unknown",
            "display_name": "USAJOBS",
            "documentation_url": "https://developer.usajobs.gov/",
            "enabled": False,
            "evidence": "Technical docs reviewed; storage/usage permission still requires review.",
            "id": "usajobs",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": None,
            "source_link_required": True,
            "status": "NEEDS_REVIEW",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "Adzuna",
            "category": "api",
            "credentials": ["ADZUNA_APP_ID", "ADZUNA_APP_KEY"],
            "description_storage": "unknown",
            "display_name": "Adzuna",
            "documentation_url": "https://developer.adzuna.com/docs/search",
            "enabled": False,
            "evidence": "Technical docs reviewed; storage/usage permission still requires review.",
            "id": "adzuna",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": None,
            "source_link_required": True,
            "status": "NEEDS_REVIEW",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "Remotive",
            "category": "unsupported",
            "credentials": [],
            "description_storage": "unknown",
            "display_name": "Remotive",
            "documentation_url": "https://remotive.com/remote-jobs/api",
            "enabled": False,
            "evidence": "Public API prohibits signup-gated listings; disabled for this authenticated "
            "workspace.",
            "id": "remotive",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": "2026-10-22",
            "source_link_required": True,
            "status": "DISABLED",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "Workday",
            "category": "unsupported",
            "credentials": [],
            "description_storage": "unknown",
            "display_name": "Workday",
            "documentation_url": "https://www.workday.com/",
            "enabled": False,
            "evidence": "Technical docs reviewed; storage/usage permission still requires review.",
            "id": "workday",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": None,
            "source_link_required": True,
            "status": "NEEDS_REVIEW",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "Company career site",
            "category": "unsupported",
            "credentials": [],
            "description_storage": "unknown",
            "display_name": "Company career site",
            "documentation_url": "https://schema.org/JobPosting",
            "enabled": False,
            "evidence": "Technical docs reviewed; storage/usage permission still requires review.",
            "id": "generic",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": None,
            "source_link_required": True,
            "status": "NEEDS_REVIEW",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "LinkedIn",
            "category": "unsupported",
            "credentials": [],
            "description_storage": "unknown",
            "display_name": "LinkedIn",
            "documentation_url": "https://www.linkedin.com/legal/user-agreement",
            "enabled": False,
            "evidence": "Technical docs reviewed; storage/usage permission still requires review.",
            "id": "linkedin",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": None,
            "source_link_required": True,
            "status": "DISABLED",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "Indeed",
            "category": "unsupported",
            "credentials": [],
            "description_storage": "unknown",
            "display_name": "Indeed",
            "documentation_url": "https://www.indeed.com/legal",
            "enabled": False,
            "evidence": "Technical docs reviewed; storage/usage permission still requires review.",
            "id": "indeed",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": None,
            "source_link_required": True,
            "status": "DISABLED",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "ZipRecruiter",
            "category": "unsupported",
            "credentials": [],
            "description_storage": "unknown",
            "display_name": "ZipRecruiter",
            "documentation_url": "https://www.ziprecruiter.com/terms",
            "enabled": False,
            "evidence": "Technical docs reviewed; storage/usage permission still requires review.",
            "id": "ziprecruiter",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": None,
            "source_link_required": True,
            "status": "DISABLED",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "Glassdoor",
            "category": "unsupported",
            "credentials": [],
            "description_storage": "unknown",
            "display_name": "Glassdoor",
            "documentation_url": "https://www.glassdoor.com/about/terms/",
            "enabled": False,
            "evidence": "Technical docs reviewed; storage/usage permission still requires review.",
            "id": "glassdoor",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "documented_api",
            "reviewed_at": None,
            "source_link_required": True,
            "status": "DISABLED",
            "terms_url": "",
        },
        {
            "adapter_version": "1",
            "attribution": "Manual import",
            "category": "manual",
            "credentials": [],
            "description_storage": "allowed",
            "display_name": "Manual import",
            "documentation_url": "",
            "enabled": True,
            "evidence": "User-supplied private records.",
            "id": "manual",
            "next_run_at": 0,
            "rate_limit": {"max_pages": 4, "min_interval_seconds": 1, "run_interval_seconds": 300},
            "redistribution": "private_only",
            "retrieval_method": "user_supplied",
            "reviewed_at": "2026-10-22",
            "source_link_required": True,
            "status": "APPROVED",
            "terms_url": "",
        },
    ]
    for row in rows:
        row["approved_boards"] = ["manual"] if row["id"] == "manual" else []
    if op.get_context().as_sql:
        for row in rows:
            for field in ("credentials", "rate_limit", "approved_boards"):
                row[field] = op.inline_literal(json.dumps(row[field]), type_=sa.String())
        op.bulk_insert(policies, rows, multiinsert=False)
    else:
        op.bulk_insert(policies, rows)


def downgrade() -> None:
    op.drop_index(op.f("ix_job_source_records_source_id"), table_name="job_source_records")
    op.drop_index(op.f("ix_job_source_records_job_id"), table_name="job_source_records")
    op.drop_table("job_source_records")
    op.drop_index(op.f("ix_job_posting_versions_job_id"), table_name="job_posting_versions")
    op.drop_table("job_posting_versions")
    op.drop_table("source_health")
    op.drop_index(op.f("ix_search_runs_owner_id"), table_name="search_runs")
    op.drop_table("search_runs")
    op.drop_index(op.f("ix_job_postings_owner_id"), table_name="job_postings")
    op.drop_index(op.f("ix_job_postings_normalized_title"), table_name="job_postings")
    op.drop_index(op.f("ix_job_postings_company_id"), table_name="job_postings")
    op.drop_table("job_postings")
    op.drop_index(op.f("ix_search_titles_owner_id"), table_name="search_titles")
    op.drop_table("search_titles")
    op.drop_index(op.f("ix_saved_searches_owner_id"), table_name="saved_searches")
    op.drop_table("saved_searches")
    op.drop_index(op.f("ix_job_sources_owner_id"), table_name="job_sources")
    op.drop_table("job_sources")
    op.drop_index(op.f("ix_companies_owner_id"), table_name="companies")
    op.drop_table("companies")
    op.drop_table("source_policies")
