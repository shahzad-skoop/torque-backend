"""initial schema

Revision ID: 0001_initial
Revises: None
Create Date: 2026-04-13 00:00:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS postgis')

    op.create_table(
        'tickers',
        sa.Column('symbol', sa.String(length=16), primary_key=True),
        sa.Column('company_name', sa.String(length=255), nullable=False),
        sa.Column('asset_type', sa.String(length=32), nullable=False, server_default='stock'),
        sa.Column('sector', sa.String(length=128), nullable=True),
        sa.Column('is_supported', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table(
        'facilities',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ticker_symbol', sa.String(length=16), sa.ForeignKey('tickers.symbol', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('facility_type', sa.String(length=64), nullable=False),
        sa.Column('state', sa.String(length=128), nullable=True),
        sa.Column('country', sa.String(length=128), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('geometry_wkt', sa.Text(), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table(
        'analysis_runs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('ticker', sa.String(length=16), nullable=False),
        sa.Column('time_range', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False, server_default='queued'),
        sa.Column('progress', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('requested_by', sa.String(length=255), nullable=True),
        sa.Column('job_id', sa.String(length=255), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table(
        'analysis_run_events',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('analysis_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_runs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('step_key', sa.String(length=64), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.create_table(
        'analysis_reports',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('analysis_run_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('analysis_runs.id', ondelete='CASCADE'), nullable=False, unique=True),
        sa.Column('ticker', sa.String(length=16), nullable=False),
        sa.Column('stance', sa.String(length=16), nullable=False),
        sa.Column('confidence', sa.Integer(), nullable=False),
        sa.Column('consensus_score', sa.Float(), nullable=False),
        sa.Column('narrative', sa.Text(), nullable=False),
        sa.Column('report_json', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
    )

    op.execute("""
    INSERT INTO tickers (symbol, company_name, asset_type, sector, is_supported)
    VALUES
      ('WMT', 'Walmart Inc.', 'stock', 'Consumer Defensive', true),
      ('TGT', 'Target Corporation', 'stock', 'Consumer Defensive', true),
      ('COST', 'Costco Wholesale Corporation', 'stock', 'Consumer Defensive', true)
    ON CONFLICT (symbol) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table('analysis_reports')
    op.drop_table('analysis_run_events')
    op.drop_table('analysis_runs')
    op.drop_table('facilities')
    op.drop_table('tickers')
