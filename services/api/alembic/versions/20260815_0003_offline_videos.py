"""Create offline video library table.

Revision ID: 20260815_0003
Revises: 20260813_0002
Create Date: 2026-08-15
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260815_0003"
down_revision: str | None = "20260813_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "offline_videos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("relative_path", sa.String(length=512), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("dataset_name", sa.String(length=120), nullable=True),
        sa.Column(
            "origin",
            sa.Enum(
                "public_dataset",
                "self_recorded",
                "synthetic",
                "other",
                name="offline_video_origin",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "label",
            sa.Enum(
                "fall",
                "adl",
                "near_fall",
                "unknown",
                name="offline_video_label",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("media_type", sa.String(length=100), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=True),
        sa.Column("license_note", sa.Text(), nullable=True),
        sa.Column("is_available", sa.Boolean(), nullable=False),
        sa.Column("file_modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_scanned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_offline_videos_relative_path"),
        "offline_videos",
        ["relative_path"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_offline_videos_relative_path"), table_name="offline_videos")
    op.drop_table("offline_videos")
