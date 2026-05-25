"""add resume columns to users

Revision ID: 002_add_resume_to_users
Revises: 55d6a69054e5
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = "002_add_resume_to_users"
down_revision = "55d6a69054e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("resume_text", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("resume_filename", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "resume_filename")
    op.drop_column("users", "resume_text")
