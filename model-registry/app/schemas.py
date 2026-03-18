from __future__ import annotations

import datetime as dt
from typing import Any, Literal
from typing import Optional

from pydantic import BaseModel, Field

Stage = Literal["development", "staging", "production"]


class ModelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)


class ModelOut(BaseModel):
    name: str
    description: Optional[str]
    created_at: dt.datetime
    updated_at: dt.datetime


class ModelVersionCreate(BaseModel):
    version: str = Field(min_length=1, max_length=100)
    artifact_path: str = Field(min_length=1, max_length=4000)
    stage: Stage = "development"
    metadata: dict[str, Any] = Field(default_factory=dict)
    tags: dict[str, str] = Field(default_factory=dict)


class ModelVersionPatch(BaseModel):
    stage: Optional[Stage] = None
    metadata: Optional[dict[str, Any]] = None
    tags: Optional[dict[str, str]] = None


class ModelVersionOut(BaseModel):
    model_name: str
    version: str
    artifact_path: str
    stage: Stage
    metadata: dict[str, Any]
    tags: dict[str, str]
    created_at: dt.datetime
    created_by: Optional[str]


class ModelWithVersionsOut(BaseModel):
    model: ModelOut
    versions: list[ModelVersionOut]


class ScanRequest(BaseModel):
    root_subdir: Optional[str] = None


class ScanResult(BaseModel):
    registered_versions: int
    skipped_existing: int
    errors: list[str] = Field(default_factory=list)


class ArtifactLocation(BaseModel):
    path: str
    exists: bool

