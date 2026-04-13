from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import AnalysisReport, AnalysisRun, AnalysisRunEvent


TERMINAL_STATES = {"completed", "failed"}


def add_run_event(
    db: Session,
    *,
    run: AnalysisRun,
    step_key: str,
    status: str,
    message: str,
    payload: dict | None = None,
) -> AnalysisRunEvent:
    event = AnalysisRunEvent(
        analysis_run_id=run.id,
        step_key=step_key,
        status=status,
        message=message,
        payload=payload,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def update_run_status(
    db: Session,
    *,
    run: AnalysisRun,
    status: str,
    progress: int | None = None,
    job_id: str | None = None,
    error_message: str | None = None,
) -> AnalysisRun:
    run.status = status
    if progress is not None:
        run.progress = progress
    if job_id is not None:
        run.job_id = job_id
    run.error_message = error_message
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def create_report(
    db: Session,
    *,
    run: AnalysisRun,
    ticker: str,
    stance: str,
    confidence: int,
    consensus_score: float,
    narrative: str,
    report_json: dict,
) -> AnalysisReport:
    report = AnalysisReport(
        analysis_run_id=run.id,
        ticker=ticker,
        stance=stance,
        confidence=confidence,
        consensus_score=consensus_score,
        narrative=narrative,
        report_json=report_json,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def get_run_or_none(db: Session, run_id: UUID) -> AnalysisRun | None:
    return db.query(AnalysisRun).filter(AnalysisRun.id == run_id).first()


def get_report_for_run(db: Session, run_id: UUID) -> AnalysisReport | None:
    return db.query(AnalysisReport).filter(AnalysisReport.analysis_run_id == run_id).first()
