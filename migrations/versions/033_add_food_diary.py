"""Add food_products and food_logs tables

Revision ID: 033_add_food_diary
Revises: 032_add_height_cm
Create Date: 2026-05-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

_USERS_FK = "users.id"

revision: str = "033_add_food_diary"
down_revision: str | None = "032_add_height_cm"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "food_products",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(_USERS_FK, ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("brand", sa.String(200)),
        sa.Column("calories_per_100g", sa.Float()),
        sa.Column("protein_g_per_100g", sa.Float()),
        sa.Column("fat_g_per_100g", sa.Float()),
        sa.Column("carbs_g_per_100g", sa.Float()),
        sa.Column("fiber_g_per_100g", sa.Float()),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "calories_per_100g IS NULL OR calories_per_100g >= 0",
            name="valid_food_calories_per_100g",
        ),
        sa.CheckConstraint(
            "protein_g_per_100g IS NULL OR protein_g_per_100g >= 0",
            name="valid_food_protein_per_100g",
        ),
        sa.CheckConstraint(
            "fat_g_per_100g IS NULL OR fat_g_per_100g >= 0",
            name="valid_food_fat_per_100g",
        ),
        sa.CheckConstraint(
            "carbs_g_per_100g IS NULL OR carbs_g_per_100g >= 0",
            name="valid_food_carbs_per_100g",
        ),
        sa.CheckConstraint(
            "fiber_g_per_100g IS NULL OR fiber_g_per_100g >= 0",
            name="valid_food_fiber_per_100g",
        ),
    )
    op.create_index(
        "idx_food_product_user_name", "food_products", ["user_id", "name"]
    )

    op.create_table(
        "food_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey(_USERS_FK, ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("date", sa.Date(), nullable=False, index=True),
        sa.Column("meal_type", sa.String(50)),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("food_products.id", ondelete="SET NULL"),
        ),
        sa.Column("quantity_g", sa.Float()),
        sa.Column("description", sa.Text()),
        sa.Column("calories", sa.Float()),
        sa.Column("protein_g", sa.Float()),
        sa.Column("fat_g", sa.Float()),
        sa.Column("carbs_g", sa.Float()),
        sa.Column("notes", sa.Text()),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.CheckConstraint(
            "meal_type IS NULL OR meal_type IN "
            "('breakfast', 'lunch', 'dinner', 'snack', 'other')",
            name="valid_food_log_meal_type",
        ),
        sa.CheckConstraint(
            "calories IS NULL OR calories >= 0",
            name="valid_food_log_calories",
        ),
        sa.CheckConstraint(
            "quantity_g IS NULL OR quantity_g >= 0",
            name="valid_food_log_quantity_g",
        ),
        sa.CheckConstraint(
            "protein_g IS NULL OR protein_g >= 0",
            name="valid_food_log_protein_g",
        ),
        sa.CheckConstraint(
            "fat_g IS NULL OR fat_g >= 0",
            name="valid_food_log_fat_g",
        ),
        sa.CheckConstraint(
            "carbs_g IS NULL OR carbs_g >= 0",
            name="valid_food_log_carbs_g",
        ),
    )
    op.create_index("idx_food_log_user_date", "food_logs", ["user_id", "date"])
    op.create_index(
        "idx_food_log_user_consumed", "food_logs", ["user_id", "consumed_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_food_log_user_consumed", table_name="food_logs")
    op.drop_index("idx_food_log_user_date", table_name="food_logs")
    op.drop_table("food_logs")

    op.drop_index("idx_food_product_user_name", table_name="food_products")
    op.drop_table("food_products")
