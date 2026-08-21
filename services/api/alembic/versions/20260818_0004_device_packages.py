"""Create device package activation audit table.

Revision ID: 20260818_0004
Revises: 20260815_0003
Create Date: 2026-08-18
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260818_0004"
down_revision: str | None = "20260815_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "device_package_activations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("package_slot", sa.Integer(), nullable=False),
        sa.Column("package_code_suffix", sa.String(length=4), nullable=False),
        sa.Column("device_id", sa.Integer(), nullable=False),
        sa.Column("channel_no", sa.Integer(), nullable=False),
        sa.Column(
            "activation_status",
            sa.Enum(
                "pending",
                "succeeded",
                "rejected",
                "failed",
                name="package_activation_status",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column("official_code", sa.String(length=32), nullable=True),
        sa.Column("official_message", sa.String(length=300), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_by", sa.Integer(), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["activated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["device_id"], ["devices.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("device_id", "channel_no", name="uq_device_package_channel"),
        sa.UniqueConstraint("package_slot", name="uq_device_package_slot"),
    )
    op.create_index(
        op.f("ix_device_package_activations_activated_by"),
        "device_package_activations",
        ["activated_by"],
        unique=False,
    )
    op.create_index(
        op.f("ix_device_package_activations_device_id"),
        "device_package_activations",
        ["device_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        op.f("ix_device_package_activations_device_id"),
        table_name="device_package_activations",
    )
    op.drop_index(
        op.f("ix_device_package_activations_activated_by"),
        table_name="device_package_activations",
    )
    op.drop_table("device_package_activations")
