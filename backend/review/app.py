"""FastAPI application for the local Phase 02 review workstation."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

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
    ai_allowance: int = Field(default=0, ge=0, le=10)
    ai_suggestion_editable: str = ""
    user_instructions: str = ""
    review_state: Literal["UNREVIEWED", "IN_PROGRESS", "REVIEWED"] = "IN_PROGRESS"


class PresetSave(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    structured_instructions: str = Field(min_length=1, max_length=2000)


def create_app(data_dir: Path, frontend_dist: Path | None = None) -> FastAPI:
    root = Path(data_dir).resolve()
    app = FastAPI(title="Photo Mass Editor", version="0.2.0")
    app.state.data_dir = root
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "PATCH"],
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
