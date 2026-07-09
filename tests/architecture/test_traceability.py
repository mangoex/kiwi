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


def test_traceability_bdd_scenarios_exist() -> None:
    matrix = _read("docs/05-matriz-trazabilidad.md")
    
    # Find all BDD-SC-xxx mentions in the matrix
    bdd_scenarios_in_matrix = set(re.findall(r"(BDD-SC-\d{3})", matrix))
    
    # Read all BDD docs
    bdd_content = ""
    for path in ROOT.glob("docs/03-BDD*.md"):
        bdd_content += path.read_text(encoding="utf-8")
        
    missing = [sc for sc in bdd_scenarios_in_matrix if sc not in bdd_content]
    assert missing == [], f"BDD Scenarios mentioned in matrix but missing from BDD files: {missing}"


def test_traceability_tdd_elements_exist() -> None:
    matrix = _read("docs/05-matriz-trazabilidad.md")
    
    # Find all TDD-TS-xxx and TDD-TC-xxx mentions in the matrix
    tdd_elements_in_matrix = set(re.findall(r"(TDD-T[SC]-\d{3})", matrix))
    
    # Read all TDD docs
    tdd_content = ""
    for path in ROOT.glob("docs/04-TDD*.md"):
        tdd_content += path.read_text(encoding="utf-8")
        
    missing = [tdd for tdd in tdd_elements_in_matrix if tdd not in tdd_content]
    assert missing == [], f"TDD Suites/Cases mentioned in matrix but missing from TDD files: {missing}"


