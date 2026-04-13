from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.models import Region, RegionAlias
from app.db.session import get_db
from app.schemas.footprint import (
    FacilityResponse,
    RegionAliasResolutionResponse,
    RegionResponse,
    TickerFootprintSummaryResponse,
)
from app.services.footprint_service import (
    list_regions,
    list_ticker_facilities,
    list_ticker_footprints,
    normalize_region_key,
)

router = APIRouter()


@router.get("/regions", response_model=list[RegionResponse])
def get_regions(db: Session = Depends(get_db)):
    regions = list_regions(db)
    return [
        RegionResponse(
            id=region.id,
            display_name=region.display_name,
            svg_polygon_path=region.svg_polygon_path,
            svg_view_box=region.svg_view_box,
            label_x=region.label_x,
            label_y=region.label_y,
            states=sorted([state.state_code for state in region.states]),
        )
        for region in regions
    ]


@router.get("/regions/resolve", response_model=RegionAliasResolutionResponse)
def resolve_region_alias(alias: str = Query(...), db: Session = Depends(get_db)):
    normalized = normalize_region_key(alias)
    region = db.query(Region).filter(Region.id == normalized).first()
    if region:
        return RegionAliasResolutionResponse(
            alias=alias,
            canonical_region_id=region.id,
            canonical_region_name=region.display_name,
        )

    alias_row = db.query(RegionAlias).filter(RegionAlias.alias == normalized).first()
    if not alias_row:
        return RegionAliasResolutionResponse(alias=alias, canonical_region_id=None, canonical_region_name=None)
    return RegionAliasResolutionResponse(
        alias=alias,
        canonical_region_id=alias_row.region.id,
        canonical_region_name=alias_row.region.display_name,
    )


@router.get("/tickers", response_model=list[TickerFootprintSummaryResponse])
def get_ticker_footprints(db: Session = Depends(get_db)):
    tickers = list_ticker_footprints(db)
    return [
        TickerFootprintSummaryResponse(
            symbol=ticker.symbol,
            company_name=ticker.company_name,
            retail_location_count=ticker.retail_location_count,
            fulfillment_center_count=ticker.fulfillment_center_count,
            average_square_footage=ticker.average_square_footage,
            key_markets=sorted({market.market_name for market in ticker.key_markets}),
            facility_types=sorted({facility_type.facility_type for facility_type in ticker.facility_types}),
            regions=sorted({ticker_region.region_id for ticker_region in ticker.regions}),
        )
        for ticker in tickers
    ]


@router.get("/tickers/{ticker_symbol}/facilities", response_model=list[FacilityResponse])
def get_facilities_for_ticker(
    ticker_symbol: str,
    region_id: str | None = Query(default=None),
    state: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    facilities = list_ticker_facilities(db, ticker_symbol=ticker_symbol, region_id=region_id, state=state)
    return [FacilityResponse.model_validate(facility, from_attributes=True) for facility in facilities]
