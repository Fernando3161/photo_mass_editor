"""FastAPI application for the local Phase 02 review workstation."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.catalog.database import connect

from .analysis import AnalysisProvider, AnalysisUnavailable, UnavailableAnalysisProvider
from .analysis_service import estimate_analysis, run_analysis
from .prompts import PromptConflict, approve_prompt, create_compiled_prompt, revise_prompt

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


def create_app(
    data_dir: Path,
    frontend_dist: Path | None = None,
    analysis_provider: AnalysisProvider | None = None,
) -> FastAPI:
    root = Path(data_dir).resolve()
    provider = analysis_provider or UnavailableAnalysisProvider()
    app = FastAPI(title="Photo Mass Editor", version="0.2.0")
    app.state.data_dir = root
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

    @app.get("/api/photos/{photo_id}/{kind}")
    def media(photo_id: str, kind: Literal["thumbnail", "original"]):
        try:
            path, media_type = media_path(root, photo_id, kind)
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Media not found") from exc
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Media file is missing")
        return FileResponse(path, media_type=media_type, filename=None)

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
