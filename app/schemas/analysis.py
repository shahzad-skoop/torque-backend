from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CreateAnalysisRunRequest(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)
    time_range: str = Field(default="earnings_window", max_length=64)


class AnalysisRunResponse(BaseModel):
    id: UUID
    ticker: str
    time_range: str
    status: str
    progress: int
    requested_by: str | None = None
    job_id: str | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AnalysisRunEventResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    step_key: str
    status: str
    message: str
    payload: dict | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AnalysisReportResponse(BaseModel):
    id: UUID
    analysis_run_id: UUID
    ticker: str
    stance: str
    confidence: int
    consensus_score: float
    narrative: str
    report_json: dict
    created_at: datetime

    class Config:
        from_attributes = True
