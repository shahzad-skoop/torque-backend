from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False)


class Ticker(TimestampMixin, Base):
    __tablename__ = "tickers"

    symbol: Mapped[str] = mapped_column(String(16), primary_key=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_type: Mapped[str] = mapped_column(String(32), default="stock", nullable=False)
    sector: Mapped[str | None] = mapped_column(String(128), nullable=True)
    is_supported: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    retail_location_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fulfillment_center_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    average_square_footage: Mapped[int | None] = mapped_column(Integer, nullable=True)

    facilities = relationship("Facility", back_populates="ticker")
    regions = relationship("TickerRegion", back_populates="ticker", cascade="all, delete-orphan")
    key_markets = relationship("TickerKeyMarket", back_populates="ticker", cascade="all, delete-orphan")
    facility_types = relationship("TickerFacilityType", back_populates="ticker", cascade="all, delete-orphan")


class Region(TimestampMixin, Base):
    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    svg_polygon_path: Mapped[str] = mapped_column(Text, nullable=False)
    svg_view_box: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label_x: Mapped[float | None] = mapped_column(Float, nullable=True)
    label_y: Mapped[float | None] = mapped_column(Float, nullable=True)

    aliases = relationship("RegionAlias", back_populates="region", cascade="all, delete-orphan")
    states = relationship("RegionState", back_populates="region", cascade="all, delete-orphan")
    ticker_regions = relationship("TickerRegion", back_populates="region", cascade="all, delete-orphan")
    facilities = relationship("Facility", back_populates="region")


class RegionAlias(Base):
    __tablename__ = "region_aliases"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    alias: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    region_id: Mapped[str] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    region = relationship("Region", back_populates="aliases")


class RegionState(Base):
    __tablename__ = "region_states"

    region_id: Mapped[str] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True)
    state_code: Mapped[str] = mapped_column(String(2), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    region = relationship("Region", back_populates="states")


class TickerRegion(Base):
    __tablename__ = "ticker_regions"

    ticker_symbol: Mapped[str] = mapped_column(ForeignKey("tickers.symbol", ondelete="CASCADE"), primary_key=True)
    region_id: Mapped[str] = mapped_column(ForeignKey("regions.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    ticker = relationship("Ticker", back_populates="regions")
    region = relationship("Region", back_populates="ticker_regions")


class TickerKeyMarket(Base):
    __tablename__ = "ticker_key_markets"
    __table_args__ = (UniqueConstraint("ticker_symbol", "market_name", name="uq_ticker_key_markets_symbol_name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticker_symbol: Mapped[str] = mapped_column(ForeignKey("tickers.symbol", ondelete="CASCADE"), nullable=False)
    market_name: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    ticker = relationship("Ticker", back_populates="key_markets")


class TickerFacilityType(Base):
    __tablename__ = "ticker_facility_types"
    __table_args__ = (UniqueConstraint("ticker_symbol", "facility_type", name="uq_ticker_facility_types_symbol_type"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticker_symbol: Mapped[str] = mapped_column(ForeignKey("tickers.symbol", ondelete="CASCADE"), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    ticker = relationship("Ticker", back_populates="facility_types")


class Facility(TimestampMixin, Base):
    __tablename__ = "facilities"
    __table_args__ = (
        UniqueConstraint("ticker_symbol", "name", "state", "facility_type", name="uq_facility_dedupe_key"),
        Index("ix_facilities_ticker_symbol", "ticker_symbol"),
        Index("ix_facilities_region_id", "region_id"),
        Index("ix_facilities_state", "state"),
        Index("ix_facilities_facility_type", "facility_type"),
        Index("ix_facilities_source_external", "external_source_name", "external_facility_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticker_symbol: Mapped[str] = mapped_column(ForeignKey("tickers.symbol", ondelete="CASCADE"), nullable=False)
    region_id: Mapped[str | None] = mapped_column(ForeignKey("regions.id", ondelete="SET NULL"), nullable=True)
    raw_region_value: Mapped[str | None] = mapped_column(String(128), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    facility_type: Mapped[str] = mapped_column(String(64), nullable=False)
    state: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str | None] = mapped_column(String(128), nullable=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    geometry_wkt: Mapped[str | None] = mapped_column(Text, nullable=True)
    polygon_geojson: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    polygon_source: Mapped[str | None] = mapped_column(String(64), nullable=True)
    geometry_status: Mapped[str] = mapped_column(String(32), default="not_available", nullable=False)
    external_source_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_facility_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_payload_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    ticker = relationship("Ticker", back_populates="facilities")
    region = relationship("Region", back_populates="facilities")


class AnalysisRun(TimestampMixin, Base):
    __tablename__ = "analysis_runs"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    time_range: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="queued", nullable=False)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    requested_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    job_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    events = relationship("AnalysisRunEvent", back_populates="analysis_run", cascade="all, delete-orphan")
    report = relationship("AnalysisReport", back_populates="analysis_run", uselist=False, cascade="all, delete-orphan")


class AnalysisRunEvent(Base):
    __tablename__ = "analysis_run_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False)
    step_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    analysis_run = relationship("AnalysisRun", back_populates="events")


class AnalysisReport(Base):
    __tablename__ = "analysis_reports"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    analysis_run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("analysis_runs.id", ondelete="CASCADE"), nullable=False, unique=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    stance: Mapped[str] = mapped_column(String(16), nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False)
    consensus_score: Mapped[float] = mapped_column(Float, nullable=False)
    narrative: Mapped[str] = mapped_column(Text, nullable=False)
    report_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    analysis_run = relationship("AnalysisRun", back_populates="report")
