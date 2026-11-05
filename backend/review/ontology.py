"""Owner-editable recognition vocabulary. Catalog labels remain unrestricted."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
KINDS = ("primary_subject", "content_tags", "condition_tags")


class OntologyError(ValueError):
    pass


class _UniqueLoader(yaml.SafeLoader):
    pass


def _unique_mapping(loader, node):
    mapping = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in mapping:
            raise OntologyError(f"Duplicate YAML key in ontology: {key}")
        mapping[key] = loader.construct_object(value_node)
    return mapping


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _unique_mapping)


def load_ontology(path: Path = ROOT / "config" / "ontology.yaml") -> dict:
    try:
        raw = path.read_bytes()
        document = yaml.load(raw, Loader=_UniqueLoader)
    except (OSError, yaml.YAMLError) as exc:
        raise OntologyError(f"Cannot read ontology {path}: {exc}") from exc
    if not isinstance(document, dict):
        raise OntologyError("Ontology must contain a YAML mapping with primary_subject, content_tags and condition_tags")
    if set(document) - set(KINDS):
        raise OntologyError(f"Unknown ontology sections: {', '.join(map(str, set(document) - set(KINDS)))}")
    concepts: dict[str, dict[str, tuple[str, ...]]] = {}
    for kind in KINDS:
        group = document.get(kind)
        if kind == "primary_subject":
            if not isinstance(group, dict) or not group:
                raise OntologyError("primary_subject must group concepts by category")
            entries = [(category, item) for category, values in group.items() for item in _sequence(values, f"primary_subject.{category}")]
        else:
            entries = [(kind, item) for item in _sequence(group, kind)]
        found: dict[str, tuple[str, ...]] = {}
        for category, item in entries:
            if isinstance(item, str):
                name, aliases = item, []
            elif isinstance(item, dict) and set(item) <= {"name", "aliases", "phrases"}:
                name = item.get("name")
                aliases = _sequence(item.get("aliases", []), f"{kind} aliases") + _sequence(item.get("phrases", []), f"{kind} phrases")
            else:
                raise OntologyError(f"Invalid {kind} concept {item!r}; use a label or name/aliases/phrases mapping")
            if not isinstance(name, str) or not name.strip():
                raise OntologyError(f"Invalid empty label in {kind}")
            name = name.strip()
            key = name.casefold()
            if key in found:
                raise OntologyError(f"Duplicate {kind} concept: {name}")
            if any(not isinstance(alias, str) or not alias.strip() for alias in aliases):
                raise OntologyError(f"Invalid phrase or alias for {name}")
            if len(aliases) > 8 or len(name) > 120 or any(len(alias) > 160 for alias in aliases):
                raise OntologyError(f"Too many or too long recognition phrases for {name}; use at most eight aliases")
            found[key] = (name, category, tuple(dict.fromkeys(alias.strip() for alias in aliases)))
        concepts[kind] = found
    # A phrase can be shared across kinds, but not between two concepts of one kind.
    for kind, values in concepts.items():
        seen = {}
        for name, _, aliases in values.values():
            for phrase in (name, *aliases):
                key = phrase.casefold()
                if key in seen and seen[key] != name:
                    raise OntologyError(f"Duplicate {kind} recognition phrase {phrase!r} for {seen[key]} and {name}")
                seen[key] = name
    return {"concepts": concepts, "sha256": hashlib.sha256(raw).hexdigest()}


def _sequence(value, label: str) -> list:
    if not isinstance(value, list):
        raise OntologyError(f"{label} must be a YAML list")
    return value


def phrases(ontology: dict) -> dict[str, list[str]]:
    """Canonical prompt plus owner aliases; aliases share one fixed score weight."""
    result = {}
    for kind, values in ontology["concepts"].items():
        for name, _, aliases in values.values():
            if kind == "condition_tags":
                prompt = f"a {name} travel photograph"
                alternatives = list(aliases)
            else:
                prompt = f"a travel photograph showing {name}"
                alternatives = list(aliases)
            result[f"{kind}:{name}"] = [prompt, *alternatives]
    return result
