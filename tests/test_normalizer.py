import pytest

from app import normalizer
from app.normalizer import normalize_clinic, normalize_procedure


@pytest.mark.parametrize("raw", ["아이디병원", "ID Plastic Surgery", " id hospital korea ", "id hospital", "아이디 성형외과"])
def test_same_clinic_across_languages_and_aliases(raw):
    result = normalize_clinic(raw)
    assert result.clinic_canonical == "ID Hospital"
    assert result.status == "matched"
    assert result.confidence == 1
    assert result.match_method == "exact"


def test_minor_typo_can_resolve():
    result = normalize_clinic("ID Hospitl Korea")
    assert result.clinic_canonical == "ID Hospital"
    assert result.match_method == "fuzzy"
    assert .92 <= result.confidence < 1


@pytest.mark.parametrize("raw", ["Sunshine Aesthetic Center", "Plastic Surgery", "ID", "XD Hospital", "서울새로운의원"])
def test_unknown_or_generic_clinics_are_not_freely_renamed(raw):
    result = normalize_clinic(raw)
    assert result.status == "unresolved"
    assert result.clinic_canonical == raw
    assert result.matched_alias is None


def test_close_competing_candidates_remain_unresolved(monkeypatch):
    monkeypatch.setattr(normalizer, "CLINICS", [
        {"canonical_name": "Seoul Beauty Clinic A", "aliases": []},
        {"canonical_name": "Seoul Beauty Clinic B", "aliases": []},
    ])
    assert normalize_clinic("Seoul Beauty Clinic C").status == "unresolved"


def test_absent_clinic_and_procedure_stay_absent():
    assert normalize_clinic(None).status == "not_mentioned"
    assert normalize_clinic(None).clinic_canonical is None
    assert normalize_procedure(None, "Rhinoplasty") is None


@pytest.mark.parametrize("raw,english,expected", [
    ("코수술", "Nose surgery", "Rhinoplasty"),
    ("쌍꺼풀", None, "Double Eyelid Surgery"),
    ("지방흡입", None, "Liposuction"),
    ("코수술과 쌍꺼풀 수술", "Rhinoplasty and double eyelid surgery", "Rhinoplasty and double eyelid surgery"),
    ("레이저 시술", "Laser treatment", "Laser treatment"),
])
def test_procedure_aliases_preserve_unlisted_and_multiple_procedures(raw, english, expected):
    assert normalize_procedure(raw, english) == expected
