"""Create synchronized device and channel tables.

Revision ID: 20260813_0002
Revises: 20260807_0001
Create Date: 2026-08-13
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260813_0002"
down_revision: str | None = "20260807_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("device_serial", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("model", sa.String(length=120), nullable=True),
        sa.Column(
            "online_status",
            sa.Enum("online", "offline", "unknown", name="device_online_status", native_enum=False),
            nullable=False,
        ),
        sa.Column("is_encrypted", sa.Boolean(), nullable=True),
        sa.Column("channel_count", sa.Integer(), nullable=False),
        sa.Column("is_present", sa.Boolean(), nullable=False),
        sa.Column("last_online_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_devices_device_serial"), "devices", ["device_serial"], unique=True)
    op.create_table(
        "device_channels",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("channel_no", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column(
            "online_status",
            sa.Enum(
                "online", "offline", "unknown", name="channel_online_status", native_enum=False
            ),
            nullable=False,
        ),
        sa.Column("is_encrypted", sa.Boolean(), nullable=True),
        sa.Column("video_level", sa.Integer(), nullable=True),
        sa.Column("is_present", sa.Boolean(), nullable=False),
        sa.Column("last_online_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "channel_no", name="uq_device_channel"),
    )
    op.create_index(
        op.f("ix_device_channels_device_id"), "device_channels", ["device_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_device_channels_device_id"), table_name="device_channels")
    op.drop_table("device_channels")
    op.drop_index(op.f("ix_devices_device_serial"), table_name="devices")
    op.drop_table("devices")
