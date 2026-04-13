from __future__ import annotations

import random
import time
from uuid import UUID

from app.celery_app import celery_app
from app.core.config import get_settings
from app.db.models import AnalysisRun
from app.db.session import SessionLocal
from app.services.analysis_service import add_run_event, create_report, update_run_status

settings = get_settings()


@celery_app.task(name="app.tasks.analysis_tasks.emit_heartbeat")
def emit_heartbeat() -> dict:
    return {"status": "ok"}


@celery_app.task(bind=True, name="app.tasks.analysis_tasks.run_analysis_pipeline")
def run_analysis_pipeline(self, run_id: str) -> dict:
    db = SessionLocal()
    try:
        run = db.query(AnalysisRun).filter(AnalysisRun.id == UUID(run_id)).first()
        if not run:
            return {"success": False, "error": "Run not found"}

        update_run_status(db, run=run, status="running", progress=5, job_id=self.request.id)
        steps = [
            ("validate", "Validating request", 10),
            ("footprint", "Resolving physical footprint", 25),
            ("weather", "Fetching weather context", 40),
            ("night_lights", "Fetching night lights proxy", 55),
            ("optical", "Fetching optical proxy", 70),
            ("scores", "Computing directional scores", 85),
            ("finalize", "Finalizing report", 95),
        ]

        for step_key, message, progress in steps:
            add_run_event(
                db,
                run=run,
                step_key=step_key,
                status="running",
                message=message,
                payload={"ticker": run.ticker, "progress": progress},
            )
            update_run_status(db, run=run, status="running", progress=progress)
            time.sleep(max(settings.simulate_analysis_delay_seconds, 0))

        stance = random.choice(["bullish", "neutral", "bearish"])
        confidence = random.randint(58, 84)
        consensus_score = round(random.uniform(-0.65, 0.72), 2)
        narrative = (
            f"Simulated report for {run.ticker}. "
            f"The current prototype pipeline completed successfully and produced a {stance} stance."
        )
        report_json = {
            "ticker": run.ticker,
            "time_range": run.time_range,
            "stance": stance,
            "confidence": confidence,
            "consensus_score": consensus_score,
            "module_outputs": [
                {"source": "weather", "directional_score": round(random.uniform(-0.3, 0.3), 2)},
                {"source": "night_lights", "directional_score": round(random.uniform(-0.7, 0.7), 2)},
                {"source": "optical", "directional_score": round(random.uniform(-0.6, 0.6), 2)},
            ],
            "limitations": [
                "This is a local simulated pipeline.",
                "Real provider integrations are not wired yet.",
            ],
        }

        create_report(
            db,
            run=run,
            ticker=run.ticker,
            stance=stance,
            confidence=confidence,
            consensus_score=consensus_score,
            narrative=narrative,
            report_json=report_json,
        )

        add_run_event(
            db,
            run=run,
            step_key="completed",
            status="completed",
            message="Analysis completed successfully",
            payload={"stance": stance, "confidence": confidence},
        )
        update_run_status(db, run=run, status="completed", progress=100)
        return {"success": True, "run_id": run_id}
    except Exception as exc:  # pragma: no cover
        run = db.query(AnalysisRun).filter(AnalysisRun.id == UUID(run_id)).first()
        if run:
            add_run_event(
                db,
                run=run,
                step_key="failed",
                status="failed",
                message=str(exc),
                payload=None,
            )
            update_run_status(db, run=run, status="failed", progress=100, error_message=str(exc))
        raise
    finally:
        db.close()
