"""Deterministic, owner-configured editing guidance for catalog labels."""

from __future__ import annotations

import hashlib
from pathlib import Path

import yaml

from .ontology import ROOT, _UniqueLoader, load_ontology

RULES_PATH = ROOT / "config" / "prompt_rules.yaml"
SELECTORS = ("subject_groups", "subjects", "content_tags", "condition_tags")
LIST_FIELDS = (*SELECTORS, "incompatible_subject_groups", "incompatible_conditions", "conflicts_with")
ALLOWED = {"id", "name", "priority", "target", "instruction", "default_enabled", "requires_consent", *LIST_FIELDS}


class RuleConfigError(ValueError):
    pass


def load_rules(path: Path = RULES_PATH) -> dict:
    try:
        raw = path.read_bytes()
        document = yaml.load(raw, Loader=_UniqueLoader)
    except (OSError, yaml.YAMLError, ValueError) as exc:
        raise RuleConfigError(f"Cannot read prompt rules: {exc}") from exc
    if not isinstance(document, dict) or set(document) != {"version", "rules"} or not isinstance(document["version"], int) or not isinstance(document["rules"], list):
        raise RuleConfigError("Prompt rules need an integer version and a rules list")
    ontology = load_ontology()
    known = {kind: {name for name in concepts} for kind, concepts in ontology["concepts"].items()}
    known_groups = {value[1] for value in ontology["concepts"]["primary_subject"].values()}
    rules = []
    ids = set()
    for item in document["rules"]:
        if not isinstance(item, dict) or set(item) - ALLOWED:
            raise RuleConfigError("Each rule must be a mapping with supported fields")
        identity = item.get("id")
        if not isinstance(identity, str) or not identity or identity in ids:
            raise RuleConfigError(f"Missing or duplicate rule ID: {identity}")
        ids.add(identity)
        if (not isinstance(item.get("name"), str) or not item["name"].strip()
                or not isinstance(item.get("instruction"), str) or not item["instruction"].strip()
                or not isinstance(item.get("priority"), int) or item.get("target") not in ("instruction", "constraint")):
            raise RuleConfigError(f"Invalid rule {identity}")
        for field in ("default_enabled", "requires_consent"):
            if field in item and not isinstance(item[field], bool):
                raise RuleConfigError(f"{identity}.{field} must be a boolean")
        for field in LIST_FIELDS:
            values = item.get(field, [])
            if not isinstance(values, list) or any(not isinstance(value, str) or not value.strip() for value in values):
                raise RuleConfigError(f"{identity}.{field} must be a list of labels")
            catalog = (known_groups if field in ("subject_groups", "incompatible_subject_groups") else
                       known["primary_subject"] if field == "subjects" else
                       known["content_tags"] if field == "content_tags" else
                       known["condition_tags"] if field in ("condition_tags", "incompatible_conditions") else None)
            if catalog is not None and any(value.casefold() not in {label.casefold() for label in catalog} for value in values):
                raise RuleConfigError(f"{identity}.{field} references an unknown ontology label")
        if not any(item.get(field) for field in SELECTORS):
            raise RuleConfigError(f"{identity} needs a match selector")
        rules.append({**item, "default_enabled": item.get("default_enabled", True),
                      "requires_consent": item.get("requires_consent", False),
                      **{field: item.get(field, []) for field in LIST_FIELDS}})
    for rule in rules:
        if any(value not in ids for value in rule["conflicts_with"]):
            raise RuleConfigError(f"{rule['id']} conflicts with an unknown rule")
    return {"version": document["version"], "sha256": hashlib.sha256(raw).hexdigest(),
            "ontology_sha256": ontology["sha256"], "rules": sorted(rules, key=lambda rule: (rule["priority"], rule["id"]))}


def compose(primary_subject: str | None, content_tags: list[str], condition_tags: list[str],
            selected_ids: list[str] | None = None, enabled: bool = True,
            semantic_change_consent: bool = False, catalog: dict | None = None) -> dict:
    catalog = catalog or load_rules()
    ontology = load_ontology()
    subject = (primary_subject or "").strip().casefold()
    content = {tag.strip().casefold() for tag in content_tags}
    conditions = {tag.strip().casefold() for tag in condition_tags}
    concept = ontology["concepts"]["primary_subject"].get(subject)
    group = concept[1] if concept else None
    selected = set(selected_ids) if selected_ids is not None else None
    candidates = []
    for rule in catalog["rules"]:
        subject_match = (group in rule["subject_groups"] if group else False) or subject in {v.casefold() for v in rule["subjects"]}
        content_match = bool(content & {v.casefold() for v in rule["content_tags"]})
        condition_match = bool(conditions & {v.casefold() for v in rule["condition_tags"]})
        match = subject_match or content_match or condition_match
        if not match or group in rule["incompatible_subject_groups"] or conditions & {v.casefold() for v in rule["incompatible_conditions"]}:
            continue
        candidates.append({"id": rule["id"], "name": rule["name"], "target": rule["target"],
                           "instruction": rule["instruction"], "optional": not rule["default_enabled"],
                           "requires_consent": rule["requires_consent"], "priority": rule["priority"],
                           "stage": 0 if subject_match else 1 if content_match else 2,
                           "selected": enabled and (rule["id"] in selected if selected is not None else rule["default_enabled"])})
    candidates.sort(key=lambda rule: (3 if rule["optional"] else rule["stage"], rule["priority"], rule["id"]))
    active = {rule["id"] for rule in candidates if rule["selected"]}
    definitions = {rule["id"]: rule for rule in catalog["rules"]}
    conflicts = []
    for identity in active:
        rule = definitions[identity]
        if rule["requires_consent"] and not semantic_change_consent:
            conflicts.append(f"{rule['name']} requires explicit semantic-change consent")
        for other in rule["conflicts_with"]:
            if other in active:
                conflicts.append(f"{rule['name']} conflicts with {definitions[other]['name']}")
    active_rules = [rule for rule in candidates if rule["selected"]]
    def unique_text(target: str) -> str:
        seen: set[str] = set()
        lines = []
        for rule in active_rules:
            if rule["target"] != target:
                continue
            normalized = " ".join(rule["instruction"].split()).casefold()
            if normalized not in seen:
                seen.add(normalized)
                lines.append(rule["instruction"])
        return "\n".join(lines)
    return {"rules": candidates, "selected_ids": [rule["id"] for rule in active_rules],
            "instructions": unique_text("instruction"),
            "constraints": unique_text("constraint"),
            "conflicts": list(dict.fromkeys(conflicts)), "config_version": catalog["version"],
            "config_sha256": catalog["sha256"], "ontology_sha256": catalog["ontology_sha256"],
            "tag_snapshot": {"primary_subject": primary_subject or "", "content_tags": content_tags,
                             "condition_tags": condition_tags}}
