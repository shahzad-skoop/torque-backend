from __future__ import annotations

import json
import time
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.api.deps import get_current_subject
from app.db.models import AnalysisRun, AnalysisRunEvent
from app.db.session import SessionLocal, get_db
from app.schemas.analysis import (
    AnalysisReportResponse,
    AnalysisRunEventResponse,
    AnalysisRunResponse,
    CreateAnalysisRunRequest,
)
from app.services.analysis_service import get_report_for_run, get_run_or_none
from app.tasks.analysis_tasks import run_analysis_pipeline

router = APIRouter()


@router.post("/runs", response_model=AnalysisRunResponse, status_code=status.HTTP_202_ACCEPTED)
def create_run(
    payload: CreateAnalysisRunRequest,
    current_subject: str = Depends(get_current_subject),
    db: Session = Depends(get_db),
):
    run = AnalysisRun(
        ticker=payload.ticker.upper(),
        time_range=payload.time_range,
        status="queued",
        progress=0,
        requested_by=current_subject,
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    task = run_analysis_pipeline.delay(str(run.id))
    run.job_id = task.id
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/runs/{run_id}", response_model=AnalysisRunResponse)
def get_run(run_id: UUID, db: Session = Depends(get_db)):
    run = get_run_or_none(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


@router.get("/runs/{run_id}/events", response_model=list[AnalysisRunEventResponse])
def get_run_events(run_id: UUID, db: Session = Depends(get_db)):
    run = get_run_or_none(db, run_id)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    events = (
        db.query(AnalysisRunEvent)
        .filter(AnalysisRunEvent.analysis_run_id == run_id)
        .order_by(AnalysisRunEvent.created_at.asc())
        .all()
    )
    return events


@router.get("/runs/{run_id}/report", response_model=AnalysisReportResponse)
def get_run_report(run_id: UUID, db: Session = Depends(get_db)):
    report = get_report_for_run(db, run_id)
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    return report


@router.get("/runs/{run_id}/stream")
def stream_run(run_id: UUID):
    def event_generator():
        last_seen = set()
        while True:
            db = SessionLocal()
            try:
                run = get_run_or_none(db, run_id)
                if not run:
                    yield "event: error\ndata: {\"message\": \"Run not found\"}\n\n"
                    return

                events = (
                    db.query(AnalysisRunEvent)
                    .filter(AnalysisRunEvent.analysis_run_id == run_id)
                    .order_by(AnalysisRunEvent.created_at.asc())
                    .all()
                )
                for event in events:
                    if str(event.id) in last_seen:
                        continue
                    last_seen.add(str(event.id))
                    payload = {
                        "id": str(event.id),
                        "step_key": event.step_key,
                        "status": event.status,
                        "message": event.message,
                        "payload": event.payload,
                        "created_at": event.created_at.isoformat(),
                    }
                    yield f"data: {json.dumps(payload)}\n\n"

                if run.status in {"completed", "failed"}:
                    summary = {
                        "run_id": str(run.id),
                        "status": run.status,
                        "progress": run.progress,
                        "error_message": run.error_message,
                    }
                    yield f"event: complete\ndata: {json.dumps(summary)}\n\n"
                    return
            finally:
                db.close()

            time.sleep(1)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
