import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRD_DEFINITION = re.compile(r"^-\s+`(PRD-(?:FR|NFR)-\d{3})\b", re.MULTILINE)
BDD_FEATURE_DEFINITION = re.compile(r"^#{1,6}\s+(BDD-FEAT-\d{3})\b", re.MULTILINE)
BDD_SCENARIO_DEFINITION = re.compile(r"^\s*@(BDD-SC-\d{3})\s*$", re.MULTILINE)
TDD_SUITE_DEFINITION = re.compile(r"^#{1,6}\s+(TDD-TS-\d{3})\b", re.MULTILINE)
TDD_CASE_DEFINITION = re.compile(r"^#{1,6}\s+(TDD-TC-\d{3})\b", re.MULTILINE)
ALLOWED_STATUSES = {"Propuesto", "Disenado", "Scaffold", "Probado", "Implementado"}


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def _spec_files(prefix: str) -> list[Path]:
    return sorted(ROOT.glob(f"docs/{prefix}*.md"))


def _definition_locations(
    paths: list[Path], pattern: re.Pattern[str]
) -> dict[str, list[str]]:
    locations: dict[str, list[str]] = defaultdict(list)
    for path in paths:
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            match = pattern.match(line)
            if match:
                locations[match.group(1)].append(f"{path.relative_to(ROOT)}:{line_number}")
    return dict(locations)


def _duplicates(locations: dict[str, list[str]]) -> dict[str, list[str]]:
    return {identifier: found for identifier, found in locations.items() if len(found) != 1}


def _matrix_rows(matrix: str) -> list[tuple[int, list[str]]]:
    rows: list[tuple[int, list[str]]] = []
    for line_number, line in enumerate(matrix.splitlines(), 1):
        if re.match(r"^\| PRD-(?:FR|NFR)-\d{3} \|", line):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            assert len(cells) == 5, f"Invalid matrix row at line {line_number}: {line}"
            rows.append((line_number, cells))
    return rows


def _scenario_tag_errors(path: Path, content: str) -> list[str]:
    errors: list[str] = []
    lines = content.splitlines()
    for index, line in enumerate(lines):
        if not re.match(r"^\s*Scenario(?: Outline)?:", line):
            continue
        previous = index - 1
        while previous >= 0 and not lines[previous].strip():
            previous -= 1
        if previous < 0 or not BDD_SCENARIO_DEFINITION.match(lines[previous]):
            errors.append(f"{path.relative_to(ROOT)}:{index + 1}")
    return errors


def _matrix_column_type_errors(rows: list[tuple[int, list[str]]]) -> list[str]:
    errors: list[str] = []
    for line_number, cells in rows:
        requirement, _design, bdd, tdd, status = cells
        if re.search(r"TDD-T[SC]-\d{3}", bdd):
            errors.append(f"line {line_number} {requirement}: TDD identifier in BDD column")
        if re.search(r"BDD-(?:FEAT|SC)-\d{3}", tdd):
            errors.append(f"line {line_number} {requirement}: BDD identifier in TDD column")
        if status not in ALLOWED_STATUSES:
            errors.append(f"line {line_number} {requirement}: invalid status {status}")
    return errors


def test_traceability_mentions_every_prd_requirement_once() -> None:
    prd_path = ROOT / "docs/01-PRD.md"
    prd_definitions = _definition_locations([prd_path], PRD_DEFINITION)
    rows = _matrix_rows(_read("docs/05-matriz-trazabilidad.md"))
    matrix_requirements = [cells[0] for _line_number, cells in rows]

    assert _duplicates(prd_definitions) == {}
    assert [item for item, count in Counter(matrix_requirements).items() if count != 1] == []
    assert set(matrix_requirements) == set(prd_definitions)


def test_phase_zero_docs_exist() -> None:
    for path in [
        "docs/07-analisis-consistencia.md",
        "docs/08-adrs-propuestas.md",
        "docs/09-fase-0-y-vertical-slice.md",
    ]:
        assert (ROOT / path).exists()


def test_bdd_definitions_are_unique_and_every_scenario_is_tagged() -> None:
    bdd_files = _spec_files("03-BDD")
    feature_definitions = _definition_locations(bdd_files, BDD_FEATURE_DEFINITION)
    scenario_definitions = _definition_locations(bdd_files, BDD_SCENARIO_DEFINITION)
    tag_errors: list[str] = []
    for path in bdd_files:
        tag_errors.extend(_scenario_tag_errors(path, path.read_text(encoding="utf-8")))

    assert _duplicates(feature_definitions) == {}
    assert _duplicates(scenario_definitions) == {}
    assert tag_errors == [], f"BDD scenarios without their own identifier: {tag_errors}"


def test_tdd_suite_and_case_definitions_are_unique() -> None:
    tdd_files = _spec_files("04-TDD")
    suite_definitions = _definition_locations(tdd_files, TDD_SUITE_DEFINITION)
    case_definitions = _definition_locations(tdd_files, TDD_CASE_DEFINITION)

    assert _duplicates(suite_definitions) == {}
    assert _duplicates(case_definitions) == {}


def test_matrix_columns_keep_bdd_tdd_and_status_types_separate() -> None:
    rows = _matrix_rows(_read("docs/05-matriz-trazabilidad.md"))
    assert _matrix_column_type_errors(rows) == []


def test_traceability_bdd_scenarios_exist_and_are_not_orphaned() -> None:
    rows = _matrix_rows(_read("docs/05-matriz-trazabilidad.md"))
    matrix_scenarios = {
        identifier
        for _line_number, cells in rows
        for identifier in re.findall(r"BDD-SC-\d{3}", cells[2])
    }
    definitions = set(
        _definition_locations(_spec_files("03-BDD"), BDD_SCENARIO_DEFINITION)
    )

    assert sorted(matrix_scenarios - definitions) == []
    assert sorted(definitions - matrix_scenarios) == []


def test_traceability_tdd_elements_exist_and_suites_are_not_orphaned() -> None:
    rows = _matrix_rows(_read("docs/05-matriz-trazabilidad.md"))
    matrix_elements = {
        identifier
        for _line_number, cells in rows
        for identifier in re.findall(r"TDD-T[SC]-\d{3}", cells[3])
    }
    tdd_files = _spec_files("04-TDD")
    suites = set(_definition_locations(tdd_files, TDD_SUITE_DEFINITION))
    cases = set(_definition_locations(tdd_files, TDD_CASE_DEFINITION))

    assert sorted(matrix_elements - suites - cases) == []
    assert sorted(suites - matrix_elements) == []


def test_negative_synthetic_ambiguities_are_detected() -> None:
    duplicate_locations = {"BDD-SC-999": ["first.feature:2", "second.feature:7"]}
    scenario_without_tag = "Feature: Synthetic\n\n  Scenario: Missing identifier\n"
    wrong_column_rows = [
        (1, ["PRD-FR-999", "Design", "TDD-TC-999", "TDD-TS-999", "Scaffold"])
    ]

    assert _duplicates(duplicate_locations) == duplicate_locations
    assert _scenario_tag_errors(ROOT / "docs/03-BDD.md", scenario_without_tag) != []
    assert _matrix_column_type_errors(wrong_column_rows) == [
        "line 1 PRD-FR-999: TDD identifier in BDD column"
    ]
