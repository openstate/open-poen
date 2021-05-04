"""Add hidden_sponsors to project model

Revision ID: 7cbba327356e
Revises: 576c02dcd565
Create Date: 2021-04-14 16:28:16.425100

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7cbba327356e'
down_revision = '576c02dcd565'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('project', sa.Column('hidden_sponsors', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('project', 'hidden_sponsors')
    # ### end Alembic commands ###