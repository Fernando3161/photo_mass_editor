"""FastAPI application for the local photo review and editing workstation."""

from __future__ import annotations

from pathlib import Path
from typing import Literal
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.catalog.database import connect

from .analysis import AnalysisProvider, AnalysisUnavailable, UnavailableAnalysisProvider
from .analysis_service import estimate_analysis, run_analysis
from .prompts import PromptConflict, approve_prompt, create_compiled_prompt, revise_prompt
from .editing import (
    EditConflict, EditProvider, batch_jobs, cancel_job, enqueue_batch,
    list_jobs, preview_batch, recover_jobs, review_version, run_job, save_mask, version_media,
)
from .image_pipeline import ImageIntegrityError, ensure_publication_input, private_path
from .openai_edit import configured_provider

from .service import (
    ReviewConflict,
    ReviewNotFound,
    get_photo,
    list_options,
    list_photos,
    media_path,
    save_photo,
    update_preset,
)


class ReviewSave(BaseModel):
    expected_revision: int = Field(ge=0)
    editorial_description: str = ""
    city: str = ""
    country: str = ""
    primary_subject: str | None = None
    content_tags: list[str] = Field(default_factory=list)
    condition_tags: list[str] = Field(default_factory=list)
    preset_id: str | None = None
    publication_profile_id: str = "website-standard-v1"
    ai_allowance: int = Field(default=0, ge=0, le=10)
    ai_suggestion_editable: str = ""
    user_instructions: str = ""
    approved_constraints: str = ""
    semantic_change_consent: bool = False
    analysis_run_id: str | None = None
    review_state: Literal["UNREVIEWED", "IN_PROGRESS", "REVIEWED"] = "IN_PROGRESS"


class PresetSave(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    structured_instructions: str = Field(min_length=1, max_length=2000)


class AnalysisBatch(BaseModel):
    photo_ids: list[str] = Field(min_length=1, max_length=25)
    authorized: bool = False
    force_refresh: bool = False


class PromptEdit(BaseModel):
    compiled_text: str = Field(min_length=1, max_length=10000)


class EditBatch(BaseModel):
    photo_ids: list[str] = Field(min_length=1, max_length=20)
    engine: Literal["DETERMINISTIC", "GENERATIVE"] = "DETERMINISTIC"
    settings: dict[str, float] = Field(default_factory=dict)
    authorized: bool = False
    budget_usd: Decimal | None = None
    request_key: str = Field(default_factory=lambda: uuid4().hex, min_length=8, max_length=100)
    retry_override: bool = False
    mask_id: str | None = None


class ReviewDecision(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    reason: str | None = Field(default=None, max_length=1000)


def create_app(
    data_dir: Path,
    frontend_dist: Path | None = None,
    analysis_provider: AnalysisProvider | None = None,
    edit_provider: EditProvider | None = None,
) -> FastAPI:
    root = Path(data_dir).resolve()
    provider = analysis_provider or UnavailableAnalysisProvider()
    editor = edit_provider if edit_provider is not None else configured_provider()
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="photo-edit")
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if (root / "catalog.sqlite").is_file():
            recover_jobs(root, editor, executor)
        yield
        executor.shutdown(wait=False, cancel_futures=True)

    app = FastAPI(title="Photo Mass Editor", version="0.4.0", lifespan=lifespan)
    app.state.data_dir = root
    app.state.edit_executor = executor
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "PATCH", "POST"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/photos")
    def photos() -> list[dict]:
        return list_photos(root)

    @app.get("/api/photos/{photo_id}")
    def photo(photo_id: str) -> dict:
        try:
            return get_photo(root, photo_id)
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Photo not found") from exc

    @app.patch("/api/photos/{photo_id}")
    def save(photo_id: str, payload: ReviewSave) -> dict:
        try:
            return save_photo(root, photo_id, payload.model_dump())
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Photo not found") from exc
        except ReviewConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    def media(photo_id: str, kind: Literal["thumbnail", "original"]):
        try:
            path, media_type = media_path(root, photo_id, kind)
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Media not found") from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Media file is missing")
        return FileResponse(path, media_type=media_type, filename=None)

    @app.get("/api/photos/{photo_id}/thumbnail")
    def thumbnail(photo_id: str):
        return media(photo_id, "thumbnail")

    @app.get("/api/photos/{photo_id}/original")
    def original(photo_id: str):
        return media(photo_id, "original")

    @app.get("/api/options")
    def options() -> dict:
        return list_options(root)

    @app.patch("/api/presets/{preset_id}")
    def preset(preset_id: str, payload: PresetSave) -> dict:
        try:
            return update_preset(root, preset_id, payload.name, payload.structured_instructions)
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Preset not found") from exc

    @app.post("/api/analysis/estimate")
    def analysis_estimate(payload: AnalysisBatch) -> dict:
        try:
            return estimate_analysis(root, payload.photo_ids, provider)
        except AnalysisUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Photo not found") from exc

    @app.post("/api/analysis/run")
    def analysis_run(payload: AnalysisBatch) -> dict:
        try:
            return run_analysis(
                root, payload.photo_ids, provider,
                authorized=payload.authorized, force_refresh=payload.force_refresh,
            )
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except AnalysisUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Photo not found") from exc

    @app.post("/api/photos/{photo_id}/prompts/compile")
    def compile_photo_prompt(photo_id: str) -> dict:
        db = connect(root)
        try:
            result = create_compiled_prompt(db, photo_id)
            db.commit()
            return result
        except KeyError as exc:
            db.rollback()
            raise HTTPException(status_code=404, detail="Photo not found") from exc
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except PromptConflict as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail={"message": "Prompt conflicts", "conflicts": exc.conflicts}) from exc
        finally:
            db.close()

    @app.patch("/api/prompts/{prompt_id}")
    def edit_prompt(prompt_id: str, payload: PromptEdit) -> dict:
        db = connect(root)
        try:
            result = revise_prompt(db, prompt_id, payload.compiled_text)
            db.commit()
            return result
        except KeyError as exc:
            db.rollback()
            raise HTTPException(status_code=404, detail="Prompt not found") from exc
        finally:
            db.close()

    @app.post("/api/prompts/{prompt_id}/approve")
    def approve(prompt_id: str) -> dict:
        db = connect(root)
        try:
            result = approve_prompt(db, prompt_id)
            db.commit()
            return result
        except KeyError as exc:
            db.rollback()
            raise HTTPException(status_code=404, detail="Prompt not found") from exc
        except PromptConflict as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail={"message": "Prompt is stale", "conflicts": exc.conflicts}) from exc
        finally:
            db.close()

    @app.post("/api/edit/preview")
    def edit_preview(payload: EditBatch) -> dict:
        try:
            return preview_batch(root, payload.photo_ids, payload.engine, editor,
                                 payload.settings, payload.mask_id, payload.retry_override)
        except EditConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/edit/batches")
    def edit_batches(payload: EditBatch) -> dict:
        try:
            jobs = enqueue_batch(
                root, payload.photo_ids, payload.engine, payload.settings, editor,
                authorized=payload.authorized, budget_usd=payload.budget_usd,
                request_key=payload.request_key, retry_override=payload.retry_override,
                mask_id=payload.mask_id,
            )
            for job in jobs:
                if job["status"] == "QUEUED":
                    executor.submit(run_job, root, job["id"], editor)
            return {"jobs": jobs}
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except (EditConflict, ImageIntegrityError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/photos/{photo_id}/edits")
    def photo_edits(photo_id: str) -> dict:
        try:
            detail = get_photo(root, photo_id)
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Photo not found") from exc
        return {"jobs": list_jobs(root, photo_id), "versions": detail["versions"]}

    @app.get("/api/edit/batches/{batch_id}")
    def batch_status(batch_id: str) -> dict:
        jobs = batch_jobs(root, batch_id)
        if not jobs:
            raise HTTPException(status_code=404, detail="Edit batch not found")
        return {"jobs": jobs}

    @app.post("/api/edit/jobs/{job_id}/cancel")
    def cancel_edit(job_id: str) -> dict:
        try:
            return cancel_job(root, job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Edit job not found") from exc
        except EditConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/photos/{photo_id}/publication-input")
    def publication_input(photo_id: str):
        db = connect(root)
        try:
            prompt = db.execute(
                "SELECT * FROM compiled_prompts WHERE photo_id=? AND approved_for_job=1", (photo_id,)
            ).fetchone()
            if prompt is None:
                raise EditConflict("Approve a current prompt before creating the publication input")
            import json
            profile = json.loads(prompt["publication_profile_snapshot_json"])
            artifact = ensure_publication_input(db, root, photo_id, profile)
            db.commit()
            return FileResponse(private_path(root, artifact["path"]), media_type="image/jpeg")
        except (EditConflict, ImageIntegrityError) as exc:
            db.rollback()
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        finally:
            db.close()

    @app.post("/api/photos/{photo_id}/masks")
    async def upload_mask(photo_id: str, request: Request) -> dict:
        try:
            return save_mask(root, photo_id, await request.body())
        except (EditConflict, ImageIntegrityError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except OSError as exc:
            raise HTTPException(status_code=500, detail="Could not save the private mask") from exc

    @app.get("/api/photos/{photo_id}/versions/{version_id}/image")
    def edited_media(photo_id: str, version_id: str):
        try:
            return FileResponse(version_media(root, photo_id, version_id), media_type="image/jpeg")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Edit version not found") from exc
        except ImageIntegrityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/photos/{photo_id}/versions/{version_id}/review")
    def decide_version(photo_id: str, version_id: str, payload: ReviewDecision) -> dict:
        try:
            return review_version(root, photo_id, version_id, payload.decision, payload.reason)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Edit version not found") from exc
        except (EditConflict, ImageIntegrityError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    dist = Path(frontend_dist).resolve() if frontend_dist else Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if dist.is_dir():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/assets", StaticFiles(directory=assets), name="assets")

        @app.get("/{path:path}", include_in_schema=False)
        def frontend(path: str):
            candidate = (dist / path).resolve()
            if path and candidate.is_file() and dist in candidate.parents:
                return FileResponse(candidate)
            return FileResponse(dist / "index.html")

    return app
