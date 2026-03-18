from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Response
from sqlalchemy.orm import Session

from app.config import settings
from app.database import engine, get_db
from app.models import Base
from app.schemas import (
    ArtifactLocation,
    ModelCreate,
    ModelOut,
    ModelVersionCreate,
    ModelVersionOut,
    ModelVersionPatch,
    ModelWithVersionsOut,
    ScanRequest,
    ScanResult,
)
from app.services import ConflictError, NotFoundError, artifact_location, create_model, create_model_version, get_model, get_model_version, list_models, patch_model_version, scan_and_register


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="Model Registry", version="0.1.0", lifespan=lifespan)

DbDep = Annotated[Session, Depends(get_db)]


@app.get("/")
def root():
    return {"service": "Model Registry", "docs": "/docs", "openapi": "/openapi.json"}


def _mv_out(mv) -> ModelVersionOut:
    return ModelVersionOut(
        model_name=mv.model.name,
        version=mv.version,
        artifact_path=mv.artifact_path,
        stage=mv.stage,
        metadata=mv.metadata_json,
        tags=mv.tags_json,
        created_at=mv.created_at,
        created_by=mv.created_by,
    )


@app.post("/models", response_model=ModelOut, status_code=201)
def api_create_model(payload: ModelCreate, db: DbDep):
    try:
        m = create_model(db, name=payload.name, description=payload.description)
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return ModelOut(name=m.name, description=m.description, created_at=m.created_at, updated_at=m.updated_at)


@app.get("/models", response_model=list[ModelOut])
def api_list_models(
    db: DbDep,
    name: Optional[str] = None,
    stage: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    models = list_models(db, name=name, stage=stage, tag=tag, limit=limit, offset=offset)
    return [ModelOut(name=m.name, description=m.description, created_at=m.created_at, updated_at=m.updated_at) for m in models]


@app.get("/models/{name}", response_model=ModelWithVersionsOut)
def api_get_model(name: str, db: DbDep):
    try:
        m = get_model(db, name=name)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return ModelWithVersionsOut(
        model=ModelOut(name=m.name, description=m.description, created_at=m.created_at, updated_at=m.updated_at),
        versions=[_mv_out(v) for v in m.versions],
    )


@app.post("/models/{name}/versions", response_model=ModelVersionOut, status_code=201)
def api_create_version(name: str, payload: ModelVersionCreate, db: DbDep):
    try:
        mv = create_model_version(
            db,
            model_name=name,
            version=payload.version,
            artifact_path=payload.artifact_path,
            stage=payload.stage,
            metadata=payload.metadata,
            tags=payload.tags,
            created_by=settings.registry_actor,
        )
    except ConflictError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    return _mv_out(mv)


@app.get("/models/{name}/versions/{version}", response_model=ModelVersionOut)
def api_get_version(name: str, version: str, db: DbDep):
    try:
        mv = get_model_version(db, model_name=name, version=version)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _mv_out(mv)


@app.patch("/models/{name}/versions/{version}", response_model=ModelVersionOut)
def api_patch_version(name: str, version: str, payload: ModelVersionPatch, db: DbDep):
    try:
        mv = patch_model_version(
            db,
            model_name=name,
            version=version,
            stage=payload.stage,
            metadata=payload.metadata,
            tags=payload.tags,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return _mv_out(mv)


@app.get("/models/{name}/versions/{version}/artifact", response_model=ArtifactLocation)
def api_artifact(name: str, version: str, db: DbDep):
    try:
        mv = get_model_version(db, model_name=name, version=version)
    except NotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    try:
        p, exists = artifact_location(artifact_path=mv.artifact_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ArtifactLocation(path=p, exists=exists)


@app.post("/scan", response_model=ScanResult)
def api_scan(payload: ScanRequest, db: DbDep):
    root = settings.registry_root_path
    if payload.root_subdir:
        root = (root / Path(payload.root_subdir)).resolve()
    registered, skipped, errors = scan_and_register(db, root=root)
    return ScanResult(registered_versions=registered, skipped_existing=skipped, errors=errors)

