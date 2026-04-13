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


def _sync_region_states(db: Session, *, region_id: str, states: list[str]) -> None:
    target_states = {state.upper() for state in states}
    existing_rows = db.query(RegionState).filter(RegionState.region_id == region_id).all()
    existing_states = {row.state_code for row in existing_rows}

    for row in existing_rows:
        if row.state_code not in target_states:
            db.delete(row)

    for state_code in sorted(target_states - existing_states):
        db.add(RegionState(region_id=region_id, state_code=state_code))


def _sync_ticker_key_markets(db: Session, *, ticker_symbol: str, key_markets: list[str]) -> None:
    target = {market.strip() for market in key_markets if market.strip()}
    existing_rows = db.query(TickerKeyMarket).filter(TickerKeyMarket.ticker_symbol == ticker_symbol).all()
    existing = {row.market_name for row in existing_rows}

    for row in existing_rows:
        if row.market_name not in target:
            db.delete(row)

    for market_name in sorted(target - existing):
        db.add(TickerKeyMarket(ticker_symbol=ticker_symbol, market_name=market_name))


def _sync_ticker_facility_types(db: Session, *, ticker_symbol: str, facility_types: list[str]) -> None:
    target = {facility_type.strip() for facility_type in facility_types if facility_type.strip()}
    existing_rows = db.query(TickerFacilityType).filter(TickerFacilityType.ticker_symbol == ticker_symbol).all()
    existing = {row.facility_type for row in existing_rows}

    for row in existing_rows:
        if row.facility_type not in target:
            db.delete(row)

    for facility_type in sorted(target - existing):
        db.add(TickerFacilityType(ticker_symbol=ticker_symbol, facility_type=facility_type))


def _sync_ticker_regions(db: Session, *, ticker_symbol: str, raw_regions: list[str]) -> None:
    resolved_region_ids = {resolve_region_id(db, raw_region) for raw_region in raw_regions}
    target = {region_id for region_id in resolved_region_ids if region_id}
    existing_rows = db.query(TickerRegion).filter(TickerRegion.ticker_symbol == ticker_symbol).all()
    existing = {row.region_id for row in existing_rows}

    for row in existing_rows:
        if row.region_id not in target:
            db.delete(row)

    for region_id in sorted(target - existing):
        db.add(TickerRegion(ticker_symbol=ticker_symbol, region_id=region_id))


def seed_rdc_data(db: Session, *, source_path: Path = DEFAULT_RDC_JSON_PATH, external_source_name: str = "rdc_sample_json") -> None:
    """Seed and normalize RDC sample data.

    The function is intentionally idempotent and deterministic so local reseeding
    keeps lookup and relationship tables synchronized with the bundled JSON.
    """
    with source_path.open("r", encoding="utf-8") as file_obj:
        payload = json.load(file_obj)

    svg_view_box = payload.get("svgViewBox")

    for region_payload in payload.get("regions", []):
        region = _upsert_region(db, region_payload, svg_view_box=svg_view_box)
        db.flush()
        _sync_region_states(db, region_id=region.id, states=region_payload.get("states", []))

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

        _sync_ticker_key_markets(db, ticker_symbol=symbol, key_markets=ticker_payload.get("keyMarkets", []))
        _sync_ticker_facility_types(db, ticker_symbol=symbol, facility_types=ticker_payload.get("facilityTypes", []))
        _sync_ticker_regions(db, ticker_symbol=symbol, raw_regions=ticker_payload.get("regions", []))

        for facility_payload in ticker_payload.get("distributionCenters", []):
            raw_region = facility_payload.get("region")
            normalized_region_id = resolve_region_id(db, raw_region)
            state = facility_payload.get("state", "").upper() or None
            facility_type = facility_payload.get("type", "distribution").strip().lower()
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
            external_key = f"{symbol}:{normalize_region_key(facility_name)}:{state or 'na'}:{facility_type}"
            facility.external_facility_id = external_key
            facility.source_payload_json = facility_payload
            if facility.first_seen_at is None:
                facility.first_seen_at = datetime.now(timezone.utc)
            facility.last_seen_at = datetime.now(timezone.utc)
            facility.is_active = True
            db.add(facility)

    db.commit()
