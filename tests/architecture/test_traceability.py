import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_traceability_mentions_every_prd_requirement() -> None:
    prd = _read("docs/01-PRD.md")
    matrix = _read("docs/05-matriz-trazabilidad.md")

    requirement_ids = sorted(set(re.findall(r"`(PRD-(?:FR|NFR)-\d{3})", prd)))
    missing = [requirement_id for requirement_id in requirement_ids if requirement_id not in matrix]

    assert missing == []


def test_phase_zero_docs_exist() -> None:
    for path in [
        "docs/07-analisis-consistencia.md",
        "docs/08-adrs-propuestas.md",
        "docs/09-fase-0-y-vertical-slice.md",
    ]:
        assert (ROOT / path).exists()

