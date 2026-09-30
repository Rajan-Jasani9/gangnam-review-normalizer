"""Resolve platform entities locally; do not ask an LLM to choose a clinic."""

import json
import unicodedata
from pathlib import Path

from rapidfuzz import fuzz

from app.models import ClinicNormalization

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
CLINICS = json.loads((DATA_DIR / "clinics.json").read_text(encoding="utf-8"))
PROCEDURES = json.loads((DATA_DIR / "procedures.json").read_text(encoding="utf-8"))
FUZZY_THRESHOLD = 92
MIN_CLINIC_MARGIN = 8


def comparison_key(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def normalize_clinic(raw: str | None) -> ClinicNormalization:
    if not raw or not raw.strip():
        return ClinicNormalization(clinic_raw=None, clinic_canonical=None, matched_alias=None, confidence=0, status="not_mentioned")

    raw = raw.strip()
    key = comparison_key(raw)
    candidates = []
    for clinic in CLINICS:
        aliases = [clinic["canonical_name"], *clinic["aliases"]]
        for alias in aliases:
            if key == comparison_key(alias):
                return ClinicNormalization(clinic_raw=raw, clinic_canonical=clinic["canonical_name"], matched_alias=alias, confidence=1, status="matched", match_method="exact")
        # Full-string ratio avoids overmatching generic "Plastic Surgery" suffixes.
        alias, score = max(((alias, fuzz.ratio(key, comparison_key(alias))) for alias in aliases), key=lambda item: item[1])
        candidates.append((score, clinic["canonical_name"], alias))

    candidates.sort(reverse=True)
    score, canonical, alias = candidates[0]
    runner_up = candidates[1][0] if len(candidates) > 1 else 0
    # Short names and near ties are too ambiguous to auto-resolve.
    if len(key.replace(" ", "")) >= 6 and score >= FUZZY_THRESHOLD and score - runner_up >= MIN_CLINIC_MARGIN:
        return ClinicNormalization(clinic_raw=raw, clinic_canonical=canonical, matched_alias=alias, confidence=round(score / 100, 4), status="matched", match_method="fuzzy")
    return ClinicNormalization(clinic_raw=raw, clinic_canonical=raw, matched_alias=None, confidence=round(score / 100, 4), status="unresolved")


def normalize_procedure(raw: str | None, extracted_english: str | None) -> str | None:
    if not raw:
        return None
    # Exact phrases only: avoid accidentally discarding qualifiers or multiple procedures.
    for candidate in (raw, extracted_english):
        if candidate:
            key = comparison_key(candidate)
            for canonical, aliases in PROCEDURES.items():
                if key in {comparison_key(item) for item in [canonical, *aliases]}:
                    return canonical
    return extracted_english or raw
