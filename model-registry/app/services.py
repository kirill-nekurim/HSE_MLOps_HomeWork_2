from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Any
from typing import Optional

from sqlalchemy import and_, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import settings
from app.models import Model, ModelVersion


class ConflictError(Exception):
    pass


class NotFoundError(Exception):
    pass


def create_model(db: Session, *, name: str, description: Optional[str]) -> Model:
    model = Model(name=name, description=description)
    db.add(model)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ConflictError(f"model '{name}' already exists") from e
    db.refresh(model)
    return model


def get_model(db: Session, *, name: str) -> Model:
    stmt = select(Model).where(Model.name == name)
    model = db.execute(stmt).scalar_one_or_none()
    if not model:
        raise NotFoundError(f"model '{name}' not found")
    return model


def list_models(
    db: Session,
    *,
    name: Optional[str],
    stage: Optional[str],
    tag: Optional[str],
    limit: int,
    offset: int,
) -> list[Model]:
    stmt = select(Model)
    if name:
        stmt = stmt.where(Model.name.contains(name))

    if stage or tag:
        stmt = stmt.join(ModelVersion, ModelVersion.model_id == Model.id)
        conds = []
        if stage:
            conds.append(ModelVersion.stage == stage)
        if tag:
            # tag is "k:v"
            if ":" not in tag:
                conds.append(func.json_extract(ModelVersion.tags_json, f"$.{tag}") != None)  # noqa: E711
            else:
                k, v = tag.split(":", 1)
                conds.append(func.json_extract(ModelVersion.tags_json, f"$.{k}") == v)
        stmt = stmt.where(and_(*conds))

    stmt = stmt.order_by(Model.updated_at.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().unique().all())


def create_model_version(
    db: Session,
    *,
    model_name: str,
    version: str,
    artifact_path: str,
    stage: str,
    metadata: dict[str, Any],
    tags: dict[str, str],
    created_by: Optional[str],
) -> ModelVersion:
    model = db.execute(select(Model).where(Model.name == model_name)).scalar_one_or_none()
    if not model:
        model = Model(name=model_name, description=None)
        db.add(model)
        db.flush()

    mv = ModelVersion(
        model_id=model.id,
        version=version,
        artifact_path=artifact_path,
        stage=stage,
        metadata_json=metadata,
        tags_json=tags,
        created_by=created_by,
    )
    db.add(mv)
    try:
        db.commit()
    except IntegrityError as e:
        db.rollback()
        raise ConflictError(f"version '{model_name}:{version}' already exists") from e
    db.refresh(mv)
    return mv


def get_model_version(db: Session, *, model_name: str, version: str) -> ModelVersion:
    stmt = (
        select(ModelVersion)
        .join(Model, Model.id == ModelVersion.model_id)
        .where(Model.name == model_name, ModelVersion.version == version)
    )
    mv = db.execute(stmt).scalar_one_or_none()
    if not mv:
        raise NotFoundError(f"version '{model_name}:{version}' not found")
    return mv


def patch_model_version(
    db: Session,
    *,
    model_name: str,
    version: str,
    stage: Optional[str],
    metadata: Optional[dict[str, Any]],
    tags: Optional[dict[str, str]],
) -> ModelVersion:
    mv = get_model_version(db, model_name=model_name, version=version)
    if stage is not None:
        mv.stage = stage
    if metadata is not None:
        mv.metadata_json = metadata
    if tags is not None:
        mv.tags_json = tags
    mv.model.updated_at = dt.datetime.now(dt.timezone.utc)
    db.add(mv)
    db.commit()
    db.refresh(mv)
    return mv


def artifact_location(*, artifact_path: str) -> tuple[str, bool]:
    p = Path(artifact_path)
    if not p.is_absolute():
        root_abs = settings.registry_root_path.resolve()
        p = (root_abs / p).resolve()
        if not p.is_relative_to(root_abs):
            raise ValueError("artifact_path escapes registry root")
    exists = p.exists()
    return str(p), exists


def scan_and_register(db: Session, *, root: Path) -> tuple[int, int, list[str]]:
    registered = 0
    skipped = 0
    errors: list[str] = []

    if not root.exists():
        return 0, 0, [f"root does not exist: {root}"]

    # expecting: root/<team>/<model_folder>/
    root_abs = root.resolve()
    registry_root_abs = settings.registry_root_path.resolve()

    for team_dir in sorted([p for p in root_abs.iterdir() if p.is_dir()]):
        for model_dir in sorted([p for p in team_dir.iterdir() if p.is_dir()]):
            model_name = model_dir.name
            version = "1"
            model_dir_abs = model_dir.resolve()
            rel_path = (
                str(model_dir_abs.relative_to(registry_root_abs))
                if model_dir_abs.is_relative_to(registry_root_abs)
                else str(model_dir_abs)
            )
            try:
                create_model_version(
                    db,
                    model_name=model_name,
                    version=version,
                    artifact_path=rel_path,
                    stage="development",
                    metadata={"scanned": True, "team": team_dir.name},
                    tags={"team": team_dir.name},
                    created_by=settings.registry_actor,
                )
                registered += 1
            except ConflictError:
                skipped += 1
            except Exception as e:  # noqa: BLE001
                errors.append(f"{model_dir}: {type(e).__name__}: {e}")

    return registered, skipped, errors

