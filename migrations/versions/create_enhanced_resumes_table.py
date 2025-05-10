"""Create enhanced_resumes table

Revision ID: 2023_10_20_enhanced_resumes
Revises: 2023_09_20_docs_table
Create Date: 2023-10-20 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '2023_10_20_enhanced_resumes'
down_revision = '2023_09_20_docs_table'  # Update this to match your last migration
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('enhanced_resumes',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('user_id', sa.String(), nullable=True),
        sa.Column('personal_info', sa.JSON(), nullable=False),
        sa.Column('work_experience', sa.JSON(), nullable=False),
        sa.Column('education', sa.JSON(), nullable=False),
        sa.Column('skills', sa.JSON(), nullable=False),
        sa.Column('projects', sa.JSON(), nullable=False),
        sa.Column('source_file_name', sa.String(), nullable=True),
        sa.Column('source_doc_id', sa.String(), nullable=True),
        sa.Column('meta_data', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['source_doc_id'], ['docs.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_enhanced_resumes_id'), 'enhanced_resumes', ['id'], unique=False)


def downgrade():
    op.drop_index(op.f('ix_enhanced_resumes_id'), table_name='enhanced_resumes')
    op.drop_table('enhanced_resumes') 