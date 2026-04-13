from __future__ import annotations

from sqlalchemy import inspect

from app.db.models import Facility, Region, RegionAlias, Ticker
from app.db.seed_rdc import seed_rdc_data
from app.db.session import SessionLocal, engine
from app.services.footprint_service import resolve_region_id


def test_seed_rdc_idempotent():
    db = SessionLocal()
    try:
        seed_rdc_data(db)
        first_counts = (
            db.query(Region).count(),
            db.query(RegionAlias).count(),
            db.query(Ticker).count(),
            db.query(Facility).count(),
        )

        seed_rdc_data(db)
        second_counts = (
            db.query(Region).count(),
            db.query(RegionAlias).count(),
            db.query(Ticker).count(),
            db.query(Facility).count(),
        )
    finally:
        db.close()

    assert first_counts == second_counts


def test_region_alias_normalization():
    db = SessionLocal()
    try:
        seed_rdc_data(db)
        assert resolve_region_id(db, "Southeast") == "south"
        assert resolve_region_id(db, "Gulf Coast") == "south"
    finally:
        db.close()


def test_list_ticker_footprints_endpoint(client):
    db = SessionLocal()
    try:
        seed_rdc_data(db)
    finally:
        db.close()

    response = client.get("/api/v1/footprints/tickers")
    assert response.status_code == 200
    payload = response.json()
    assert any(item["symbol"] == "WMT" for item in payload)


def test_list_facilities_for_ticker_with_filters(client):
    db = SessionLocal()
    try:
        seed_rdc_data(db)
    finally:
        db.close()

    response = client.get("/api/v1/footprints/tickers/WMT/facilities?state=GA")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    assert payload[0]["name"] == "Atlanta Southeast DC"
    assert payload[0]["region_id"] == "south"


def test_regions_endpoint(client):
    db = SessionLocal()
    try:
        seed_rdc_data(db)
    finally:
        db.close()

    response = client.get("/api/v1/footprints/regions")
    assert response.status_code == 200
    payload = response.json()
    assert any(item["id"] == "northwest" for item in payload)


def test_schema_contains_rdc_tables_and_columns():
    inspector = inspect(engine)
    table_names = set(inspector.get_table_names())
    assert "regions" in table_names
    assert "region_aliases" in table_names
    assert "ticker_regions" in table_names
    assert "ticker_key_markets" in table_names
    assert "ticker_facility_types" in table_names

    facilities_columns = {column["name"] for column in inspector.get_columns("facilities")}
    assert "region_id" in facilities_columns
    assert "raw_region_value" in facilities_columns
    assert "external_facility_id" in facilities_columns
