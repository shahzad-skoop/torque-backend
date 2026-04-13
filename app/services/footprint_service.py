from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.db.models import Facility, Region, RegionAlias, Ticker


def normalize_region_key(value: str | None) -> str:
    if not value:
        return ""
    return "".join(char for char in value.strip().lower() if char.isalnum())


def resolve_region_id(db: Session, raw_region_value: str | None) -> str | None:
    normalized = normalize_region_key(raw_region_value)
    if not normalized:
        return None

    region = db.query(Region).filter(Region.id == normalized).first()
    if region:
        return region.id

    alias = db.query(RegionAlias).filter(RegionAlias.alias == normalized).first()
    return alias.region_id if alias else None


def list_regions(db: Session) -> list[Region]:
    return db.query(Region).options(joinedload(Region.states)).order_by(Region.display_name.asc()).all()


def list_ticker_footprints(db: Session) -> list[Ticker]:
    return (
        db.query(Ticker)
        .options(joinedload(Ticker.key_markets), joinedload(Ticker.facility_types), joinedload(Ticker.regions))
        .order_by(Ticker.symbol.asc())
        .all()
    )


def list_ticker_facilities(
    db: Session,
    *,
    ticker_symbol: str,
    region_id: str | None = None,
    state: str | None = None,
) -> list[Facility]:
    query = db.query(Facility).filter(Facility.ticker_symbol == ticker_symbol.upper())
    if region_id:
        query = query.filter(Facility.region_id == region_id)
    if state:
        query = query.filter(Facility.state == state.upper())
    return query.order_by(Facility.name.asc()).all()
