from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class RegionResponse(BaseModel):
    id: str
    display_name: str
    svg_polygon_path: str
    svg_view_box: str | None
    label_x: float | None
    label_y: float | None
    states: list[str]


class RegionAliasResolutionResponse(BaseModel):
    alias: str
    canonical_region_id: str | None
    canonical_region_name: str | None


class TickerFootprintSummaryResponse(BaseModel):
    symbol: str
    company_name: str
    retail_location_count: int | None
    fulfillment_center_count: int | None
    average_square_footage: int | None
    key_markets: list[str]
    facility_types: list[str]
    regions: list[str]


class FacilityResponse(BaseModel):
    id: UUID
    ticker_symbol: str
    region_id: str | None
    raw_region_value: str | None
    name: str
    facility_type: str
    state: str | None
    country: str | None
    latitude: float | None
    longitude: float | None
    geometry_status: str
    external_source_name: str | None
    external_facility_id: str | None
    first_seen_at: datetime | None
    last_seen_at: datetime | None
    is_active: bool
