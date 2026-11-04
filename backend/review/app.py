"""FastAPI application for the local photo review and editing workstation."""

from __future__ import annotations

from pathlib import Path
import base64
import binascii
import hmac
import os
import sqlite3
import subprocess
import sys
from typing import Literal
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from decimal import Decimal
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.catalog.database import connect

from .analysis import AnalysisProvider, AnalysisUnavailable, UnavailableAnalysisProvider
from .analysis_service import estimate_analysis, run_analysis
from . import local_corrections as local
from . import local_batch
from . import prompt_batch
from . import prompt_refinement
from .prompts import PromptConflict, approve_prompt, create_compiled_prompt, revise_prompt
from .editing import (
    EditConflict, EditProvider, batch_jobs, cancel_job, enqueue_batch,
    list_jobs, preview_batch, recover_jobs, review_version, run_job, save_mask, version_media,
)
from .image_pipeline import ImageIntegrityError, ensure_publication_input, private_path
from .export import ExportError, audit_artifacts, create_export, export_path, preview_export, recent_exports
from .openai_edit import configured_provider
from .local_model import ModelManager, ModelUnavailable
from .catalog_prefill import (
    bulk_location, decide as decide_suggestion, delete_city, list_cities,
    save_city, suggest, suggestions, undo as undo_suggestion, undo_bulk_location,
)

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


class RefinementRun(BaseModel):
    authorized: bool = False
    budget_usd: Decimal | None = Field(default=None, ge=0)


class EditBatch(BaseModel):
    photo_ids: list[str] = Field(min_length=1, max_length=20)
    engine: Literal["DETERMINISTIC", "GENERATIVE"] = "DETERMINISTIC"
    settings: dict[str, float] = Field(default_factory=dict)
    authorized: bool = False
    budget_usd: Decimal | None = None
    request_key: str = Field(default_factory=lambda: uuid4().hex, min_length=8, max_length=100)
    retry_override: bool = False
    replace_approved: bool = False
    mask_id: str | None = None


class LocalRecipeRequest(BaseModel):
    settings: dict
    expected_revision: int = Field(ge=0)
    request_key: str = Field(default_factory=lambda: uuid4().hex, min_length=8, max_length=100)
    retry_override: bool = False
    replace_approved: bool = False


class LocalPreviewRequest(BaseModel):
    settings: dict


class NamedLocalRecipe(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    settings: dict


class LocalBatchRequest(BaseModel):
    photo_ids: list[str] = Field(min_length=1, max_length=200)
    recipe_id: str | None = None
    overrides: dict[str, dict] = Field(default_factory=dict)
    retry_override: bool = False
    replace_approved: bool = False
    preview_signature: str = ""
    request_key: str = Field(default_factory=lambda: uuid4().hex)
    authorized: bool = False


class PromptBatchRequest(BaseModel):
    photo_ids: list[str] = Field(min_length=1, max_length=200)
    shared_instruction: str = Field(default="", max_length=2000)
    preview_signature: str = ""
    acknowledged_ids: list[str] = Field(default_factory=list)


class PromptBatchApproval(BaseModel):
    expected: dict[str, str]


class ReviewDecision(BaseModel):
    decision: Literal["APPROVED", "REJECTED"]
    reason: str | None = Field(default=None, max_length=1000)
    replace_approved: bool = False


class CitySave(BaseModel):
    city: str = Field(min_length=1, max_length=120)
    country: str = Field(min_length=1, max_length=120)
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    radius_km: float = Field(gt=0, le=200)


class PrefillRun(BaseModel):
    photo_ids: list[str] = Field(min_length=1, max_length=20)
    authorized: bool = False
    offline: bool = False


class SuggestionDecision(BaseModel):
    fields: list[str] = Field(default_factory=list)
    expected_revision: int = Field(ge=0)
    dismiss: bool = False


class LocationBatch(BaseModel):
    photo_ids: list[str] = Field(min_length=1, max_length=20)
    city_id: str
    authorized: bool = False
    expected_revisions: dict[str, int] | None = None


class ExportRequest(BaseModel):
    authorized: bool = False


def create_app(
    data_dir: Path,
    frontend_dist: Path | None = None,
    analysis_provider: AnalysisProvider | None = None,
    edit_provider: EditProvider | None = None,
    local_recognizer: ModelManager | None = None,
    access_password: str = "",
    refinement_provider: prompt_refinement.RefinementProvider | None = None,
) -> FastAPI:
    root = Path(data_dir).resolve()
    provider = analysis_provider or UnavailableAnalysisProvider()
    editor = edit_provider if edit_provider is not None else configured_provider()
    recognizer = local_recognizer or ModelManager()
    refiner = refinement_provider or prompt_refinement.OpenAITextRefiner()
    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="photo-edit")
    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        if (root / "catalog.sqlite").is_file():
            recover_jobs(root, editor, executor)
            for job_id in local_batch.resume_queued(root):
                executor.submit(local.run_job, root, job_id)
        yield
        executor.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(title="Photo Mass Editor", version="0.5.0", lifespan=lifespan)
    app.state.data_dir = root
    app.state.edit_executor = executor
    allowed_hosts = {"localhost", "127.0.0.1", "[::1]"}
    allowed_hosts.update(host.strip().lower() for host in os.environ.get("PHOTO_EDITOR_ALLOWED_HOSTS", "").split(",") if host.strip())

    @app.middleware("http")
    async def protect_local_session(request: Request, call_next):
        if access_password:
            host = request.headers.get("host", "").split(":", 1)[0].lower()
            if host not in allowed_hosts:
                return Response(status_code=400, content="Unrecognized host")
            header = request.headers.get("authorization", "")
            try:
                scheme, encoded = header.split(" ", 1)
                credentials = base64.b64decode(encoded, validate=True).decode("utf-8")
                username, password = credentials.split(":", 1)
                valid = scheme.lower() == "basic" and username == "owner" and hmac.compare_digest(password, access_password)
            except (ValueError, UnicodeDecodeError, binascii.Error):
                valid = False
            if not valid:
                return Response(status_code=401, headers={"WWW-Authenticate": 'Basic realm="Photo Mass Editor"', "Cache-Control": "no-store"})
            if request.headers.get("sec-fetch-site", "").lower() == "cross-site":
                return Response(status_code=403, content="Cross-site request blocked")
            origin = request.headers.get("origin")
            if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
                if not origin:
                    return Response(status_code=403, content="Write origin required")
                from urllib.parse import urlsplit
                parsed = urlsplit(origin)
                origin_host = (parsed.hostname or "").lower()
                if parsed.scheme not in {"http", "https"} or origin_host != host or parsed.port != request.url.port:
                    return Response(status_code=403, content="Cross-origin write blocked")
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        if request.url.path.startswith("/api/"):
            response.headers["Cache-Control"] = "no-store"
        return response
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "PATCH", "POST", "DELETE"],
        allow_headers=["Content-Type"],
    )

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/export/preview")
    def export_preview() -> dict:
        try:
            return preview_export(root)
        except (ExportError, ImageIntegrityError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/export")
    def export_website(payload: ExportRequest) -> dict:
        if not payload.authorized:
            raise HTTPException(status_code=403, detail="Current-run export authorization is required")
        try:
            return create_export(root)
        except (ExportError, ImageIntegrityError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/export/audit")
    def export_audit() -> dict:
        return audit_artifacts(root)

    @app.get("/api/export/history")
    def export_history() -> list[dict]:
        return recent_exports(root)

    @app.get("/api/export/{export_id}/{document}")
    def export_document(export_id: str, document: Literal["manifest", "cost_report"]):
        db = connect(root)
        try:
            row = db.execute(
                "SELECT manifest_path,cost_report_path FROM exports WHERE id=? AND status='COMPLETE'",
                (export_id,),
            ).fetchone()
        finally:
            db.close()
        if row is None:
            raise HTTPException(status_code=404, detail="Export not found")
        path = export_path(root, row["manifest_path" if document == "manifest" else "cost_report_path"])
        if not path.is_file():
            raise HTTPException(status_code=409, detail="Export document is missing")
        return FileResponse(path, media_type="application/json", filename=f"{document}-{export_id}.json")

    @app.post("/api/export/{export_id}/open-folder")
    def open_export_folder(export_id: str, request: Request) -> dict:
        if request.headers.get("X-Local-Action") != "open-export-folder":
            raise HTTPException(status_code=403, detail="Use the local export folder action")
        db = connect(root)
        try:
            row = db.execute("SELECT manifest_path FROM exports WHERE id=? AND status='COMPLETE'",
                             (export_id,)).fetchone()
        finally:
            db.close()
        if row is None:
            raise HTTPException(status_code=404, detail="Export not found")
        folder = export_path(root, row["manifest_path"]).parent
        if not folder.is_dir():
            raise HTTPException(status_code=409, detail="Export folder is missing")
        opener = "explorer.exe" if sys.platform == "win32" else "xdg-open"
        try:
            subprocess.Popen([opener, str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            raise HTTPException(status_code=503, detail="Could not open the export folder") from exc
        return {"opened": True}

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

    @app.get("/api/catalog/cities")
    def cities() -> list[dict]:
        return list_cities(root)

    @app.post("/api/catalog/cities")
    def create_city(payload: CitySave) -> dict:
        try:
            return save_city(root, payload.city, payload.country, payload.latitude, payload.longitude, payload.radius_km)
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="This city and country already exist") from exc

    @app.patch("/api/catalog/cities/{city_id}")
    def update_city(city_id: str, payload: CitySave) -> dict:
        try:
            return save_city(root, payload.city, payload.country, payload.latitude, payload.longitude, payload.radius_km, city_id)
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="City not found") from exc
        except sqlite3.IntegrityError as exc:
            raise HTTPException(status_code=409, detail="This city and country already exist") from exc

    @app.delete("/api/catalog/cities/{city_id}")
    def remove_city(city_id: str) -> dict:
        try:
            delete_city(root, city_id)
            return {"deleted": True}
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="City not found") from exc

    @app.get("/api/catalog/model-status")
    def model_status() -> dict:
        return recognizer.status()

    @app.post("/api/catalog/suggestions/run")
    def run_prefill(payload: PrefillRun) -> dict:
        try:
            return {"results": suggest(root, payload.photo_ids, recognizer, authorized=payload.authorized, offline=payload.offline)}
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ModelUnavailable as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Photo not found") from exc
        except (ValueError, ReviewConflict) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/photos/{photo_id}/catalog-suggestions")
    def photo_suggestions(photo_id: str) -> list[dict]:
        try:
            return suggestions(root, photo_id)
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Photo not found") from exc

    @app.post("/api/catalog/suggestions/{suggestion_id}/decide")
    def decide_prefill(suggestion_id: str, payload: SuggestionDecision) -> dict:
        try:
            return decide_suggestion(root, suggestion_id, payload.fields, payload.expected_revision, payload.dismiss)
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Suggestion not found") from exc
        except (ValueError, ReviewConflict) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/catalog/suggestions/{suggestion_id}/undo")
    def undo_prefill(suggestion_id: str) -> dict:
        try:
            return undo_suggestion(root, suggestion_id)
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Suggestion not found") from exc
        except ReviewConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/catalog/location/preview")
    def location_preview(payload: LocationBatch) -> dict:
        try:
            return bulk_location(root, payload.photo_ids, payload.city_id)
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Photo or city not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.post("/api/catalog/location/apply")
    def location_apply(payload: LocationBatch) -> dict:
        if not payload.authorized:
            raise HTTPException(status_code=403, detail="Authorize this bulk location assignment")
        try:
            return bulk_location(root, payload.photo_ids, payload.city_id, apply=True, expected_revisions=payload.expected_revisions)
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Photo or city not found") from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except ReviewConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/catalog/location/batches/{batch_id}/undo")
    def undo_location(batch_id: str) -> dict:
        try:
            return undo_bulk_location(root, batch_id)
        except ReviewNotFound as exc:
            raise HTTPException(status_code=404, detail="Location batch not found") from exc
        except ReviewConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

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

    @app.get("/api/photos/{photo_id}/prompt-refinements")
    def refinement_history(photo_id: str) -> list[dict]:
        try:
            return prompt_refinement.history(root, photo_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Photo not found") from exc

    @app.post("/api/prompts/{prompt_id}/refinement/estimate")
    def refinement_estimate(prompt_id: str) -> dict:
        try:
            return prompt_refinement.estimate(root, prompt_id, refiner)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Prompt not found") from exc
        except PromptConflict as exc:
            raise HTTPException(status_code=409, detail={"conflicts": exc.conflicts}) from exc

    @app.post("/api/prompts/{prompt_id}/refinement/run")
    def refinement_run(prompt_id: str, payload: RefinementRun) -> dict:
        try:
            return prompt_refinement.run(root, prompt_id, refiner,
                                         authorized=payload.authorized, budget_usd=payload.budget_usd)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Prompt not found") from exc
        except PromptConflict as exc:
            raise HTTPException(status_code=409, detail={"conflicts": exc.conflicts}) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except RuntimeError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc

    @app.post("/api/prompt-refinements/{refinement_id}/adopt")
    def refinement_adopt(refinement_id: str, payload: PromptEdit | None = None) -> dict:
        try:
            return prompt_refinement.adopt(root, refinement_id,
                                           payload.compiled_text if payload else None)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Refinement not found") from exc
        except PromptConflict as exc:
            raise HTTPException(status_code=409, detail={"conflicts": exc.conflicts}) from exc

    @app.post("/api/prompt-batches/preview")
    def preview_prompts(payload: PromptBatchRequest) -> dict:
        try:
            return prompt_batch.preview(root, payload.photo_ids, payload.shared_instruction)
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/prompt-batches/compile")
    def compile_prompts(payload: PromptBatchRequest) -> dict:
        try:
            return {"prompts": prompt_batch.compile_selected(root, payload.photo_ids,
                payload.shared_instruction, payload.preview_signature, payload.acknowledged_ids)}
        except (ValueError, PromptConflict) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/prompt-batches/approve")
    def approve_prompts(payload: PromptBatchApproval) -> dict:
        try:
            return {"prompts": prompt_batch.approve_selected(root, payload.expected)}
        except (ValueError, PromptConflict) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/edit/preview")
    def edit_preview(payload: EditBatch) -> dict:
        try:
            return preview_batch(root, payload.photo_ids, payload.engine, editor,
                                 payload.settings, payload.mask_id, payload.retry_override,
                                 payload.replace_approved)
        except EditConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/photos/{photo_id}/local-recommendation")
    def local_recommendation(photo_id: str, preset_id: str | None = None) -> dict:
        try:
            return local.recommend(root, photo_id, preset_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Photo not found") from exc
        except (local.LocalCorrectionError, ImageIntegrityError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/photos/{photo_id}/local-preview")
    def local_preview(photo_id: str, payload: LocalPreviewRequest):
        try:
            return Response(local.preview(root, photo_id, payload.settings), media_type="image/jpeg",
                            headers={"Cache-Control": "no-store"})
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Photo not found") from exc
        except (local.LocalCorrectionError, ImageIntegrityError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/photos/{photo_id}/local-edits")
    def local_edit(photo_id: str, payload: LocalRecipeRequest) -> dict:
        try:
            job = local.enqueue(root, photo_id, payload.settings, payload.expected_revision,
                                payload.request_key, payload.retry_override, payload.replace_approved)
            if job["status"] == "QUEUED":
                executor.submit(local.run_job, root, job["id"])
            return job
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Photo not found") from exc
        except (local.LocalCorrectionError, ImageIntegrityError) as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/local/recipes")
    def named_local_recipes() -> list[dict]:
        return local_batch.named_recipes(root)

    @app.post("/api/local/recipes")
    def save_local_recipe(payload: NamedLocalRecipe) -> dict:
        try:
            return local_batch.save_named_recipe(root, payload.name, payload.settings)
        except local.LocalCorrectionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/local/batches/preview")
    def preview_local_batch(payload: LocalBatchRequest) -> dict:
        try:
            return local_batch.preview(root, payload.photo_ids, payload.recipe_id, payload.overrides,
                                       payload.retry_override, payload.replace_approved)
        except local.LocalCorrectionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/local/batches")
    def create_local_batch(payload: LocalBatchRequest) -> dict:
        if not payload.authorized:
            raise HTTPException(status_code=403, detail="Authorize this local batch for the current run")
        try:
            batch = local_batch.enqueue(root, payload.photo_ids, payload.request_key, payload.preview_signature,
                                        payload.recipe_id, payload.overrides, payload.retry_override, payload.replace_approved)
            for job in batch["jobs"]:
                if job["status"] == "QUEUED":
                    executor.submit(local.run_job, root, job["id"])
            return batch
        except local.LocalCorrectionError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/local/batches/recent")
    def recent_local_batches() -> list[dict]:
        return local_batch.recent_batches(root)

    @app.get("/api/local/batches/{batch_id}")
    def get_local_batch(batch_id: str) -> dict:
        try:
            return local_batch.batch_status(root, batch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Local batch not found") from exc

    @app.post("/api/local/batches/{batch_id}/cancel")
    def cancel_local_batch(batch_id: str) -> dict:
        try:
            return local_batch.cancel(root, batch_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Local batch not found") from exc

    @app.get("/api/photos/{photo_id}/local-edits")
    def local_edits(photo_id: str) -> dict:
        return {"jobs": local.list_jobs(root, photo_id)}

    @app.get("/api/local/jobs/{job_id}")
    def local_job(job_id: str) -> dict:
        try:
            return local.job_status(root, job_id)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Local job not found") from exc

    @app.post("/api/edit/batches")
    def edit_batches(payload: EditBatch) -> dict:
        try:
            jobs = enqueue_batch(
                root, payload.photo_ids, payload.engine, payload.settings, editor,
                authorized=payload.authorized, budget_usd=payload.budget_usd,
                request_key=payload.request_key, retry_override=payload.retry_override,
                mask_id=payload.mask_id, replace_approved=payload.replace_approved,
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
        content = bytearray()
        async for chunk in request.stream():
            content.extend(chunk)
            if len(content) >= 4 * 1024 * 1024:
                raise HTTPException(status_code=413, detail="Mask must be smaller than 4 MB")
        try:
            return save_mask(root, photo_id, bytes(content))
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

    @app.get("/api/photos/{photo_id}/versions/{version_id}/master")
    def local_master(photo_id: str, version_id: str):
        try:
            return FileResponse(local.master_media(root, photo_id, version_id), media_type="image/png",
                                filename=f"photo-master-{version_id}.png")
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Local master not found") from exc
        except ImageIntegrityError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post("/api/photos/{photo_id}/versions/{version_id}/review")
    def decide_version(photo_id: str, version_id: str, payload: ReviewDecision) -> dict:
        try:
            return review_version(root, photo_id, version_id, payload.decision, payload.reason,
                                  payload.replace_approved)
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
