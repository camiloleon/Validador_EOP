from __future__ import annotations

from pydantic import BaseModel, Field


class ValidationIssue(BaseModel):
    row: int = Field(..., ge=1)
    field: str
    severity: str
    code: str
    message: str
    current_value: str | None = None
    suggested_value: str | None = None


class CorrectionLog(BaseModel):
    row: int = Field(..., ge=1)
    field: str
    old_value: str | None
    new_value: str | None
    rule: str


class ValidationSummary(BaseModel):
    template: str
    total_rows: int
    error_count: int
    warning_count: int
    suspicious_count: int
    correction_count: int
    can_continue: bool
    delimiter: str
    file_hash: str


class ValidationResult(BaseModel):
    summary: ValidationSummary
    issues: list[ValidationIssue]
    corrections: list[CorrectionLog]
    corrected_csv: str
    correction_options: dict[str, list[str]] = Field(default_factory=dict)
    correlation_maps: dict[str, object] = Field(default_factory=dict)
