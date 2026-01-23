"""add_variable_mapping_to_campaigns

Revision ID: 0261f23a3702
Revises: 15863af40fe3
Create Date: 2026-01-22 21:49:47.441002

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0261f23a3702"
down_revision: Union[str, Sequence[str], None] = "15863af40fe3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add the variable_mapping column
    op.add_column(
        "campaigns",
        sa.Column(
            "variable_mapping", postgresql.JSONB(astext_type=sa.Text()), nullable=True
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Remove the variable_mapping column
    op.drop_column("campaigns", "variable_mapping")
