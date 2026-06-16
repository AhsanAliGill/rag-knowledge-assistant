"""add role to users

Revision ID: a1b2c3d4e5f6
Revises: 27a31a8e5963
Create Date: 2026-06-16

"""
import os
import uuid

import bcrypt
import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "27a31a8e5963"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Create the enum type — ignore if it already exists (idempotent)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE userrole AS ENUM ('admin', 'user');
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """)

    # 2. Add role column — nullable first so existing rows don't conflict
    op.add_column(
        "users",
        sa.Column("role", sa.Enum("admin", "user", name="userrole"), nullable=True),
    )

    # 3. Set ALL existing users to 'user'
    op.execute("UPDATE users SET role = 'user'")

    # 4. Now enforce NOT NULL with a server default for future inserts
    op.alter_column("users", "role", nullable=False, server_default="user")

    # 5. Seed admin user
    admin_id = str(uuid.uuid4())
    seed_pw = os.environ.get("ADMIN_SEED_PASSWORD", "changeme").encode()
    hashed_pw = bcrypt.hashpw(seed_pw, bcrypt.gensalt()).decode()

    op.execute(
        sa.text(
            """
            INSERT INTO users (id, username, email, hashed_password, is_active, role, created_at)
            VALUES (CAST(:id AS UUID), :username, :email, :hashed_password, true, 'admin', NOW())
            ON CONFLICT DO NOTHING
            """
        ).bindparams(
            id=admin_id,
            username="Ahsan ALi Gill",
            email="ahs462agk@gmail.com",
            hashed_password=hashed_pw,
        )
    )


def downgrade() -> None:
    op.drop_column("users", "role")
    op.execute("DROP TYPE userrole")
