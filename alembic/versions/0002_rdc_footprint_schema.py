"""rdc footprint schema

Revision ID: 0002_rdc_footprint_schema
Revises: 0001_initial
Create Date: 2026-04-13 00:30:00
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_rdc_footprint_schema"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("tickers", sa.Column("retail_location_count", sa.Integer(), nullable=True))
    op.add_column("tickers", sa.Column("fulfillment_center_count", sa.Integer(), nullable=True))
    op.add_column("tickers", sa.Column("average_square_footage", sa.Integer(), nullable=True))

    op.create_table(
        "regions",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("svg_polygon_path", sa.Text(), nullable=False),
        sa.Column("svg_view_box", sa.String(length=64), nullable=True),
        sa.Column("label_x", sa.Float(), nullable=True),
        sa.Column("label_y", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "region_aliases",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("alias", sa.String(length=128), nullable=False),
        sa.Column("region_id", sa.String(length=64), sa.ForeignKey("regions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("alias", name="uq_region_aliases_alias"),
    )

    op.create_table(
        "region_states",
        sa.Column("region_id", sa.String(length=64), sa.ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("state_code", sa.String(length=2), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "ticker_regions",
        sa.Column("ticker_symbol", sa.String(length=16), sa.ForeignKey("tickers.symbol", ondelete="CASCADE"), primary_key=True),
        sa.Column("region_id", sa.String(length=64), sa.ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )

    op.create_table(
        "ticker_key_markets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker_symbol", sa.String(length=16), sa.ForeignKey("tickers.symbol", ondelete="CASCADE"), nullable=False),
        sa.Column("market_name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("ticker_symbol", "market_name", name="uq_ticker_key_markets_symbol_name"),
    )

    op.create_table(
        "ticker_facility_types",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("ticker_symbol", sa.String(length=16), sa.ForeignKey("tickers.symbol", ondelete="CASCADE"), nullable=False),
        sa.Column("facility_type", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("ticker_symbol", "facility_type", name="uq_ticker_facility_types_symbol_type"),
    )

    op.add_column("facilities", sa.Column("region_id", sa.String(length=64), nullable=True))
    op.add_column("facilities", sa.Column("raw_region_value", sa.String(length=128), nullable=True))
    op.add_column("facilities", sa.Column("polygon_geojson", sa.JSON(), nullable=True))
    op.add_column("facilities", sa.Column("polygon_source", sa.String(length=64), nullable=True))
    op.add_column(
        "facilities",
        sa.Column("geometry_status", sa.String(length=32), nullable=False, server_default="not_available"),
    )
    op.add_column("facilities", sa.Column("external_source_name", sa.String(length=64), nullable=True))
    op.add_column("facilities", sa.Column("external_facility_id", sa.String(length=128), nullable=True))
    op.add_column("facilities", sa.Column("source_payload_json", sa.JSON(), nullable=True))
    op.add_column("facilities", sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("facilities", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "facilities",
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_foreign_key("fk_facilities_region_id", "facilities", "regions", ["region_id"], ["id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_facility_dedupe_key", "facilities", ["ticker_symbol", "name", "state", "facility_type"])

    op.create_index("ix_facilities_ticker_symbol", "facilities", ["ticker_symbol"])
    op.create_index("ix_facilities_region_id", "facilities", ["region_id"])
    op.create_index("ix_facilities_state", "facilities", ["state"])
    op.create_index("ix_facilities_facility_type", "facilities", ["facility_type"])
    op.create_index("ix_facilities_source_external", "facilities", ["external_source_name", "external_facility_id"])

    op.create_check_constraint(
        "ck_facilities_geometry_status",
        "facilities",
        "geometry_status IN ('not_available', 'point_only', 'polygon_available', 'error')",
    )
    op.create_check_constraint(
        "ck_facilities_latitude_range",
        "facilities",
        "latitude IS NULL OR (latitude >= -90 AND latitude <= 90)",
    )
    op.create_check_constraint(
        "ck_facilities_longitude_range",
        "facilities",
        "longitude IS NULL OR (longitude >= -180 AND longitude <= 180)",
    )


def downgrade() -> None:
    op.drop_constraint("ck_facilities_longitude_range", "facilities", type_="check")
    op.drop_constraint("ck_facilities_latitude_range", "facilities", type_="check")
    op.drop_constraint("ck_facilities_geometry_status", "facilities", type_="check")
    op.drop_index("ix_facilities_source_external", table_name="facilities")
    op.drop_index("ix_facilities_facility_type", table_name="facilities")
    op.drop_index("ix_facilities_state", table_name="facilities")
    op.drop_index("ix_facilities_region_id", table_name="facilities")
    op.drop_index("ix_facilities_ticker_symbol", table_name="facilities")
    op.drop_constraint("uq_facility_dedupe_key", "facilities", type_="unique")
    op.drop_constraint("fk_facilities_region_id", "facilities", type_="foreignkey")

    op.drop_column("facilities", "is_active")
    op.drop_column("facilities", "last_seen_at")
    op.drop_column("facilities", "first_seen_at")
    op.drop_column("facilities", "source_payload_json")
    op.drop_column("facilities", "external_facility_id")
    op.drop_column("facilities", "external_source_name")
    op.drop_column("facilities", "geometry_status")
    op.drop_column("facilities", "polygon_source")
    op.drop_column("facilities", "polygon_geojson")
    op.drop_column("facilities", "raw_region_value")
    op.drop_column("facilities", "region_id")

    op.drop_table("ticker_facility_types")
    op.drop_table("ticker_key_markets")
    op.drop_table("ticker_regions")
    op.drop_table("region_states")
    op.drop_table("region_aliases")
    op.drop_table("regions")

    op.drop_column("tickers", "average_square_footage")
    op.drop_column("tickers", "fulfillment_center_count")
    op.drop_column("tickers", "retail_location_count")
