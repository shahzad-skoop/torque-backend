from __future__ import annotations

from app.db.seed_rdc import seed_rdc_data
from app.db.session import SessionLocal


def main() -> None:
    db = SessionLocal()
    try:
        seed_rdc_data(db)
        print("RDC sample data seeded successfully.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
