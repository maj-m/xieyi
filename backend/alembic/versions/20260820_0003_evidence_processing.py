"""Add durable evidence processing jobs and normalized document lineage."""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260820_0003"
down_revision: str | None = "20260820_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "evidence_processing_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("parser_name", sa.String(length=128)),
        sa.Column("parser_version", sa.String(length=32)),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="3", nullable=False),
        sa.Column("idempotency_key", sa.String(length=128), nullable=False),
        sa.Column(
            "available_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("lease_owner", sa.String(length=128)),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True)),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True)),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(length=128)),
        sa.Column("error_message", sa.Text()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("evidence_id", "idempotency_key", name="uq_processing_job_idempotency"),
    )
    op.create_index("ix_evidence_processing_jobs_case_id", "evidence_processing_jobs", ["case_id"])
    op.create_index(
        "ix_evidence_processing_jobs_evidence_id", "evidence_processing_jobs", ["evidence_id"]
    )
    op.create_index("ix_evidence_processing_jobs_status", "evidence_processing_jobs", ["status"])
    op.create_index(
        "ix_evidence_processing_jobs_lease_expires_at",
        "evidence_processing_jobs",
        ["lease_expires_at"],
    )
    op.create_index(
        "ix_processing_jobs_claim",
        "evidence_processing_jobs",
        ["status", "available_at", "created_at"],
    )

    op.create_table(
        "normalized_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("evidence_id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("parser_name", sa.String(length=128), nullable=False),
        sa.Column("parser_version", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=512)),
        sa.Column("text_preview", sa.Text()),
        sa.Column("language", sa.String(length=32)),
        sa.Column("content_object_key", sa.String(length=1024)),
        sa.Column("content_sha256", sa.String(length=64)),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["evidence_id"], ["evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["job_id"], ["evidence_processing_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("job_id", name="uq_normalized_documents_job_id"),
    )
    op.create_index("ix_normalized_documents_case_id", "normalized_documents", ["case_id"])
    op.create_index("ix_normalized_documents_evidence_id", "normalized_documents", ["evidence_id"])
    op.create_index("ix_normalized_documents_job_id", "normalized_documents", ["job_id"])
    op.create_index(
        "ix_normalized_documents_case_created", "normalized_documents", ["case_id", "created_at"]
    )

    op.create_table(
        "evidence_derivatives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("case_id", sa.Uuid(), nullable=False),
        sa.Column("source_evidence_id", sa.Uuid(), nullable=False),
        sa.Column("child_evidence_id", sa.Uuid()),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("derivative_type", sa.String(length=32), nullable=False),
        sa.Column("filename", sa.String(length=512), nullable=False),
        sa.Column("object_key", sa.String(length=1024), nullable=False),
        sa.Column("mime_type", sa.String(length=255), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("metadata_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["case_id"], ["cases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_evidence_id"], ["evidence.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["child_evidence_id"], ["evidence.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["job_id"], ["evidence_processing_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evidence_derivatives_case_id", "evidence_derivatives", ["case_id"])
    op.create_index(
        "ix_evidence_derivatives_child_evidence_id", "evidence_derivatives", ["child_evidence_id"]
    )
    op.create_index(
        "ix_evidence_derivatives_parent",
        "evidence_derivatives",
        ["source_evidence_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_table("evidence_derivatives")
    op.drop_table("normalized_documents")
    op.drop_table("evidence_processing_jobs")
