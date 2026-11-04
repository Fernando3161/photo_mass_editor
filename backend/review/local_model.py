"""Pinned, local CLIP inference. No image or metadata is uploaded."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from threading import Lock
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[2]
MANIFEST = json.loads((ROOT / "config" / "local_model.json").read_text(encoding="utf-8"))
LABELS = (
    "an opera house", "a parliament building", "a church", "a cathedral", "a museum",
    "a palace", "a castle", "a bridge", "a monument", "a sculpture", "a city street",
    "a building facade", "a portrait of a person", "a group of people", "a restaurant meal",
    "a river", "a lake", "a mountain landscape", "a garden", "a beach",
    "a waterfall", "a forest trail", "a desert landscape", "a snowy mountain",
    "a harbor", "a boat", "a train", "a market", "a shopfront",
    "an archaeological site", "an old town square", "a tower", "a skyline",
    "a street mural", "a painting in a museum", "an indoor artwork",
    "a person walking", "a crowded street", "a wildlife photograph",
    "a hotel interior", "a cafe interior", "a plated dessert", "a panoramic landscape",
)
CONDITIONS = (
    "a night photograph", "a daytime photograph", "a backlit photograph", "an evenly lit photograph",
    "a blurry photograph", "a sharp photograph", "a hazy photograph", "a clear photograph",
)
SETTINGS = {"labels": LABELS, "conditions": CONDITIONS, "template": "a travel photograph of {}", "version": 2}


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
        scale = 224 / min(w, h)
        image = image.resize((round(w * scale), round(h * scale)), Image.Resampling.BICUBIC)
        left = (image.width - 224) // 2
        top = (image.height - 224) // 2
        image = image.crop((left, top, left + 224, top + 224))
        array = np.asarray(image, dtype=np.float32) / 255.0
        luminance = 0.2126 * array[:, :, 0] + 0.7152 * array[:, :, 1] + 0.0722 * array[:, :, 2]
        measurements = {"mean_luminance": round(float(luminance.mean()), 3), "luminance_std": round(float(luminance.std()), 3)}
        array = (array - np.array([0.48145466, 0.4578275, 0.40821073])) / np.array([0.26862954, 0.26130258, 0.27577711])
        pixels = np.transpose(array.astype(np.float32), (2, 0, 1))[None]
        labels = LABELS + CONDITIONS
        encoded = self._tokenizer.encode_batch([SETTINGS["template"].format(label) for label in labels])
        tokens = np.array([item.ids[:77] + [0] * (77 - len(item.ids[:77])) for item in encoded], dtype=np.int64)
        masks = (tokens != 0).astype(np.int64)
        names = {item.name for item in self._session.get_inputs()}
        inputs = {"input_ids": tokens, "pixel_values": pixels}
        if "attention_mask" in names:
            inputs["attention_mask"] = masks
        outputs = self._session.run(None, {key: value for key, value in inputs.items() if key in names})
        output_names = [item.name for item in self._session.get_outputs()]
        if "logits_per_image" not in output_names:
            raise ModelUnavailable(f"Unexpected model outputs: {output_names}")
        scores = np.asarray(outputs[output_names.index("logits_per_image")]).reshape(-1)
        ranking = sorted(zip(labels, scores.tolist()), key=lambda pair: pair[1], reverse=True)
        return {"ranking": [{"label": label, "similarity": round(float(score), 4)} for label, score in ranking], "image_size": [w, h], "measurements": measurements}
