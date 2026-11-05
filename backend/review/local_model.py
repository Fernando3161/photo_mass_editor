"""Pinned, local CLIP inference. No image or metadata is uploaded."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from urllib.request import urlopen

from .ontology import load_ontology, phrases

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((ROOT / "config" / "local_model.json").read_text(encoding="utf-8"))
SETTINGS = {"version": 3, "views": "whole-plus-center-for-wide", "phrase_aggregation": "half-canonical-half-mean-aliases"}


class ModelUnavailable(RuntimeError):
    pass


class ModelManager:
    def __init__(self, root: Path = ROOT):
        self.root = Path(root)
        self.cache = self.root / MANIFEST["cache_dir"]
        self.lock = Lock()
        self._prepare_lock = Lock()
        self._session_lock = Lock()
        self._status = {"state": "idle", "file": "", "downloaded": 0, "total": 0, "error": ""}
        self._session = None
        self._tokenizer = None

    def status(self) -> dict:
        with self.lock:
            return dict(self._status) | {"cached": self.cached()}

    def _set(self, **values) -> None:
        with self.lock:
            self._status.update(values)

    def cached(self) -> bool:
        return all(self._valid(name, digest) for name, digest in MANIFEST["files"].items())

    def _valid(self, name: str, digest: str) -> bool:
        path = self.cache / name
        if not path.is_file():
            return False
        h = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest() == digest

    def ensure(self, *, offline: bool = False) -> None:
        with self._prepare_lock:
            self._ensure(offline=offline)

    def _ensure(self, *, offline: bool = False) -> None:
        if self.cached():
            self._set(state="ready", error="")
            return
        if offline:
            raise ModelUnavailable("Verified local model cache is incomplete; run online once or use setup --prefetch-model")
        for name, digest in MANIFEST["files"].items():
            if self._valid(name, digest):
                continue
            target = self.cache / name
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".partial")
            url = f"https://huggingface.co/{MANIFEST['model_id']}/resolve/{MANIFEST['revision']}/{name}"
            self._set(state="downloading", file=name, downloaded=0, total=0, error="")
            try:
                h = hashlib.sha256()
                with urlopen(url, timeout=90) as response, partial.open("wb") as output:
                    total = int(response.headers.get("Content-Length", "0"))
                    self._set(total=total)
                    count = 0
                    for chunk in iter(lambda: response.read(1024 * 1024), b""):
                        output.write(chunk)
                        h.update(chunk)
                        count += len(chunk)
                        self._set(downloaded=count)
                if h.hexdigest() != digest:
                    raise ModelUnavailable(f"Checksum mismatch for {name}")
                os.replace(partial, target)
            except Exception as exc:
                partial.unlink(missing_ok=True)
                self._set(state="error", error=str(exc))
                raise ModelUnavailable(f"Could not prepare local model file {name}: {exc}") from exc
        self._set(state="ready", file="", error="")

    def classify(self, image_path: Path, *, offline: bool = False) -> dict:
        self.ensure(offline=offline)
        import numpy as np
        import onnxruntime as ort
        from PIL import Image, ImageOps
        from tokenizers import Tokenizer

        if self._session is None:
            with self._session_lock:
                if self._session is None:
                    self._session = ort.InferenceSession(str(self.cache / "onnx/model_quantized.onnx"), providers=["CPUExecutionProvider"])
                    self._tokenizer = Tokenizer.from_file(str(self.cache / "tokenizer.json"))
        with Image.open(image_path) as source:
            image = ImageOps.exif_transpose(source).convert("RGB")
        w, h = image.size
        whole = ImageOps.pad(image, (224, 224), method=Image.Resampling.BICUBIC, color=(128, 128, 128))
        views = [whole]
        if max(w, h) / min(w, h) > 1.65:
            views.append(ImageOps.fit(image, (224, 224), method=Image.Resampling.BICUBIC))
        # Measurements use actual scene pixels; neutral letterboxing must not
        # make a nighttime panorama appear brighter than it is.
        measured = ImageOps.contain(image, (512, 512), method=Image.Resampling.BICUBIC)
        array = np.asarray(measured, dtype=np.float32) / 255.0
        luminance = 0.2126 * array[:, :, 0] + 0.7152 * array[:, :, 1] + 0.0722 * array[:, :, 2]
        measurements = {"mean_luminance": round(float(luminance.mean()), 3), "luminance_std": round(float(luminance.std()), 3)}
        pixels = np.stack([np.transpose((np.asarray(view, dtype=np.float32) / 255.0 -
                        np.array([0.48145466, 0.4578275, 0.40821073])) /
                        np.array([0.26862954, 0.26130258, 0.27577711]), (2, 0, 1)) for view in views]).astype(np.float32)
        candidates = phrases(load_ontology())
        labels = list(candidates)
        phrase_list = [phrase for label in labels for phrase in candidates[label]]
        encoded = self._tokenizer.encode_batch(phrase_list)
        tokens = np.array([item.ids[:77] + [0] * (77 - len(item.ids[:77])) for item in encoded], dtype=np.int64)
        masks = (tokens != 0).astype(np.int64)
        names = {item.name for item in self._session.get_inputs()}
        output_names = [item.name for item in self._session.get_outputs()]
        if "logits_per_image" not in output_names:
            raise ModelUnavailable(f"Unexpected model outputs: {output_names}")
        scores = []
        for pixel in pixels:
            inputs = {"input_ids": tokens, "pixel_values": pixel[None]}
            if "attention_mask" in names:
                inputs["attention_mask"] = masks
            outputs = self._session.run(None, {key: value for key, value in inputs.items() if key in names})
            scores.append(np.asarray(outputs[output_names.index("logits_per_image")]).reshape(len(phrase_list)))
        scores = np.stack(scores)
        # Equal phrase weight, then whole-frame priority. A wide center view can help but cannot dominate.
        concept_scores = np.empty((len(views), len(labels)), dtype=np.float32)
        offset = 0
        for index, label in enumerate(labels):
            count = len(candidates[label])
            values = scores[:, offset:offset + count]
            concept_scores[:, index] = values[:, 0] if count == 1 else .5 * values[:, 0] + .5 * values[:, 1:].mean(axis=1)
            offset += count
        aggregate = concept_scores[0] if len(views) == 1 else .7 * concept_scores[0] + .3 * concept_scores[1]
        ranking = sorted(zip(labels, aggregate.tolist()), key=lambda pair: pair[1], reverse=True)
        return {"ranking": [{"label": label, "similarity": round(float(score), 4)} for label, score in ranking],
                "image_size": [w, h], "measurements": measurements, "views": len(views)}
