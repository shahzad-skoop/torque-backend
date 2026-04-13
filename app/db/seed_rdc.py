from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import (
    Facility,
    Region,
    RegionAlias,
    RegionState,
    Ticker,
    TickerFacilityType,
    TickerKeyMarket,
    TickerRegion,
)
from app.services.footprint_service import normalize_region_key, resolve_region_id


DEFAULT_RDC_JSON_PATH = Path(__file__).resolve().parents[1] / "data" / "rdc-regions-footprints.json"


def _upsert_region(db: Session, payload: dict, svg_view_box: str | None) -> Region:
    region_id = normalize_region_key(payload["id"])
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        region = Region(id=region_id)
    region.display_name = payload["name"]
    region.svg_polygon_path = payload["polygon"]
    region.svg_view_box = svg_view_box
    region.label_x = payload.get("label", {}).get("x")
    region.label_y = payload.get("label", {}).get("y")
    db.add(region)
    return region


def seed_rdc_data(db: Session, *, source_path: Path = DEFAULT_RDC_JSON_PATH, external_source_name: str = "rdc_sample_json") -> None:
    with source_path.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    svg_view_box = payload.get("svgViewBox")

    for region_payload in payload.get("regions", []):
        region = _upsert_region(db, region_payload, svg_view_box=svg_view_box)
        db.flush()

        for state in region_payload.get("states", []):
            state_code = state.upper()
            exists = (
                db.query(RegionState)
                .filter(RegionState.region_id == region.id, RegionState.state_code == state_code)
                .first()
            )
            if not exists:
                db.add(RegionState(region_id=region.id, state_code=state_code))

    for alias_raw, canonical_raw in payload.get("regionAliases", {}).items():
        alias = normalize_region_key(alias_raw)
        canonical = normalize_region_key(canonical_raw)
        existing = db.query(RegionAlias).filter(RegionAlias.alias == alias).first()
        if not existing:
            existing = RegionAlias(alias=alias, region_id=canonical)
        existing.region_id = canonical
        db.add(existing)

    for ticker_symbol, ticker_payload in payload.get("tickerFootprints", {}).items():
        symbol = ticker_symbol.upper()
        ticker = db.query(Ticker).filter(Ticker.symbol == symbol).first()
        if not ticker:
            ticker = Ticker(symbol=symbol)
        ticker.company_name = ticker_payload["companyName"]
        ticker.asset_type = "stock"
        ticker.is_supported = True
        ticker.retail_location_count = ticker_payload.get("retailLocations")
        ticker.fulfillment_center_count = ticker_payload.get("fulfillmentCenters")
        ticker.average_square_footage = ticker_payload.get("avgSquareFootage")
        db.add(ticker)
        db.flush()

        for market in ticker_payload.get("keyMarkets", []):
            existing_market = (
                db.query(TickerKeyMarket)
                .filter(TickerKeyMarket.ticker_symbol == symbol, TickerKeyMarket.market_name == market)
                .first()
            )
            if not existing_market:
                db.add(TickerKeyMarket(ticker_symbol=symbol, market_name=market))

        for facility_type in ticker_payload.get("facilityTypes", []):
            existing_type = (
                db.query(TickerFacilityType)
                .filter(
                    TickerFacilityType.ticker_symbol == symbol,
                    TickerFacilityType.facility_type == facility_type,
                )
                .first()
            )
            if not existing_type:
                db.add(TickerFacilityType(ticker_symbol=symbol, facility_type=facility_type))

        seen_ticker_regions: set[str] = set()
        for raw_region in ticker_payload.get("regions", []):
            region_id = resolve_region_id(db, raw_region)
            if not region_id or region_id in seen_ticker_regions:
                continue
            seen_ticker_regions.add(region_id)
            existing_ticker_region = (
                db.query(TickerRegion)
                .filter(TickerRegion.ticker_symbol == symbol, TickerRegion.region_id == region_id)
                .first()
            )
            if not existing_ticker_region:
                db.add(TickerRegion(ticker_symbol=symbol, region_id=region_id))

        for facility_payload in ticker_payload.get("distributionCenters", []):
            raw_region = facility_payload.get("region")
            normalized_region_id = resolve_region_id(db, raw_region)
            state = facility_payload.get("state")
            facility_type = facility_payload.get("type", "distribution")
            facility_name = facility_payload["name"]

            facility = (
                db.query(Facility)
                .filter(
                    Facility.ticker_symbol == symbol,
                    Facility.name == facility_name,
                    Facility.state == state,
                    Facility.facility_type == facility_type,
                )
                .first()
            )
            if not facility:
                facility = Facility(
                    ticker_symbol=symbol,
                    name=facility_name,
                    state=state,
                    facility_type=facility_type,
                )

            facility.region_id = normalized_region_id
            facility.raw_region_value = raw_region
            facility.country = "US"
            facility.geometry_status = "not_available"
            facility.external_source_name = external_source_name
            facility.external_facility_id = f"{symbol}:{normalize_region_key(facility_name)}"
            facility.source_payload_json = facility_payload
            if facility.first_seen_at is None:
                facility.first_seen_at = datetime.now(timezone.utc)
            facility.last_seen_at = datetime.now(timezone.utc)
            facility.is_active = True
            db.add(facility)

    db.commit()
