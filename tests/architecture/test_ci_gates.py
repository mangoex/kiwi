import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
PACKAGE_JSON = ROOT / "package.json"

# A mapping key inside the `jobs:` block: indentation + name + colon at end of
# line. Steps and nested keys also match this, so callers must filter by the
# minimum indentation to keep only direct jobs.
_KEY_LINE_RE = re.compile(
    r"^(?P<indent>[ ]+)(?P<name>[A-Za-z_][A-Za-z0-9_-]*):[ ]*$", re.MULTILINE
)


def _ci_content() -> str:
    return CI_WORKFLOW.read_text(encoding="utf-8")


def _job_section(content: str, job_name: str) -> str:
    """Return the YAML text belonging to a direct job under `jobs:`.

    The section spans from the job key (e.g. `frontend:`) up to the next direct
    job or end of file. Only keys at the minimum indentation level inside the
    `jobs:` block count as direct jobs; nested steps (deeper indentation) are
    part of the current job's body. Raises AssertionError with a useful message
    if the job is missing.
    """
    jobs_match = re.search(r"^jobs:[ ]*$", content, re.MULTILINE)
    assert jobs_match is not None, f"Missing top-level 'jobs:' in {CI_WORKFLOW}"

    jobs_block = content[jobs_match.end():]
    candidates = list(_KEY_LINE_RE.finditer(jobs_block))
    assert candidates, f"No jobs found under 'jobs:' in {CI_WORKFLOW}"

    min_indent = min(len(match.group("indent")) for match in candidates)
    direct_jobs = [match for match in candidates if len(match.group("indent")) == min_indent]

    for index, match in enumerate(direct_jobs):
        if match.group("name") == job_name:
            start = match.end()
            has_next = index + 1 < len(direct_jobs)
            end = direct_jobs[index + 1].start() if has_next else len(jobs_block)
            return jobs_block[start:end]

    job_names = [match.group("name") for match in direct_jobs]
    raise AssertionError(
        f"Top-level job '{job_name}' missing from {CI_WORKFLOW}; found jobs: {job_names}"
    )


def _has_anchored_line(haystack: str, pattern: str) -> bool:
    """True if `pattern` matches a full YAML line within `haystack`.

    Patterns must be anchored with `^` and `$` and use `re.MULTILINE`, so a
    match requires the token to be a real line rather than a substring, a
    comment (`# run: ...`), or a fragment embedded in a different line.
    """
    return re.search(pattern, haystack, flags=re.MULTILINE) is not None


def _require_lines(haystack: str, labels_to_patterns: dict, where: str) -> None:
    """Assert every anchored pattern matches a full line in `haystack`."""
    missing = [
        label
        for label, pattern in labels_to_patterns.items()
        if not _has_anchored_line(haystack, pattern)
    ]
    assert missing == [], (
        f"{where} missing required YAML lines in {CI_WORKFLOW}: {missing}"
    )


# Triggers must be real YAML keys located in the `on:` block, before `jobs:`.
# Indentation is allowed (`^ *`) but a leading `#` or a fragment of a longer
# line is rejected by the `$` anchor.
_TRIGGER_PATTERNS = {
    "pull_request:": r"^ *pull_request:[ ]*$",
    "push:": r"^ *push:[ ]*$",
    'branches: ["main"]': r"^ *branches:[ ]*\[\"main\"\][ ]*$",
}

# Steps required inside the `frontend` job. Each must be a full YAML line, so
# `# run: pnpm typecheck` (comment) or a token embedded in another line is
# rejected. `uses:` lines carry the YAML list-item marker (`- uses:`), so the
# pattern permits an optional `- ` after the indentation. `run:` and scalar
# keys never have the marker.
#
# Note on pnpm version: the workflow MUST NOT declare a parallel pnpm version
# (no `version: "10"` under `pnpm/action-setup`). The single source of truth
# for the pnpm version is `packageManager` in `package.json`. That invariant is
# checked separately in `test_pnpm_version_comes_from_package_manager_only`.
_FRONTEND_STEP_PATTERNS = {
    "uses: pnpm/action-setup@v4": r"^ *(?:- )?uses:[ ]*pnpm/action-setup@v4[ ]*$",
    'node-version: "22"': r"^ *node-version:[ ]*\"22\"[ ]*$",
    "run: pnpm install --frozen-lockfile": r"^ *run:[ ]*pnpm install --frozen-lockfile[ ]*$",
    "run: pnpm typecheck": r"^ *run:[ ]*pnpm typecheck[ ]*$",
    "run: build @restaurantos/admin-web": (
        r"^ *run:[ ]*pnpm --filter @restaurantos/admin-web build[ ]*$"
    ),
    "run: build @restaurantos/pos-web": (
        r"^ *run:[ ]*pnpm --filter @restaurantos/pos-web build[ ]*$"
    ),
    "run: build @restaurantos/kds-web": (
        r"^ *run:[ ]*pnpm --filter @restaurantos/kds-web build[ ]*$"
    ),
}


def test_ci_triggers_precede_jobs() -> None:
    """`pull_request`, `push` and `branches: ["main"]` must be real YAML keys
    appearing before `jobs:`.

    Anchored patterns (`^ *...$` with `re.MULTILINE`) ensure these are actual
    trigger keys, not text repeated in a comment, a step body, or another job.
    """
    content = _ci_content()
    before_jobs_match = re.search(r"^jobs:[ ]*$", content, re.MULTILINE)
    assert before_jobs_match is not None, f"Missing top-level 'jobs:' in {CI_WORKFLOW}"
    before_jobs = content[: before_jobs_match.start()]

    _require_lines(before_jobs, _TRIGGER_PATTERNS, where="CI triggers block")


def test_frontend_job_exists() -> None:
    """A direct `frontend:` job must exist under `jobs:`."""
    _job_section(_ci_content(), "frontend")


def test_frontend_quality_gate_steps_present() -> None:
    """The `frontend` job must contain every required step as a real YAML line.

    Each required token is matched with an anchored `^ *...$` pattern against
    the `frontend` job body, so a match must be a genuine line. Commands cannot
    be hidden in comments or belong to a sibling job, because the search is
    scoped to the `frontend` section and the `$` anchor rejects comments like
    `# run: pnpm typecheck`.
    """
    frontend_section = _job_section(_ci_content(), "frontend")
    _require_lines(
        frontend_section, _FRONTEND_STEP_PATTERNS, where="'frontend' job"
    )


def test_pnpm_version_comes_from_package_manager_only() -> None:
    """The pnpm version is declared once, in `package.json#packageManager`.

    The `frontend` job must use `pnpm/action-setup@v4` WITHOUT a parallel
    `version:` override; the action reads the version from `packageManager`.
    This avoids the "double pnpm version" failure where the action and corepack
    disagree. Also asserts `package.json` pins `pnpm@10.0.0`.
    """
    package_json = PACKAGE_JSON.read_text(encoding="utf-8")
    assert '"packageManager": "pnpm@10.0.0"' in package_json, (
        f"{PACKAGE_JSON} must declare \"packageManager\": \"pnpm@10.0.0\""
    )

    frontend_section = _job_section(_ci_content(), "frontend")
    # No `version: "..."` line may appear inside the frontend job. The pattern
    # is anchored so a `node-version:` line is not mistaken for a pnpm version.
    has_pnpm_version_override = _has_anchored_line(
        frontend_section, r"^ *version:[ ]*\"?[0-9]+\"?[ ]*$"
    )
    assert not has_pnpm_version_override, (
        f"The 'frontend' job in {CI_WORKFLOW} must not declare a parallel "
        f"pnpm 'version:'; the version must come from packageManager only."
    )


# --- Negative test ---------------------------------------------------------
# Synthetic YAML where every required token is present, but either commented
# out (`# ...`) or placed inside a different job. Anchored matching against the
# real `frontend` section must NOT be satisfied. This proves the gate rejects
# attempts to fool substring checks with comments or sibling jobs.
_BAD_YAML = """\
name: CI

on:
  # pull_request:
  # push:
  #   branches: ["main"]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: pnpm/action-setup@v4
        with:
          version: "10"
      - uses: actions/setup-node@v4
        with:
          node-version: "22"
      - run: pnpm install --frozen-lockfile
      - run: pnpm typecheck
      # run: pnpm --filter @restaurantos/admin-web build
      - run: echo "pnpm --filter @restaurantos/pos-web build"
      - run: echo pnpm --filter @restaurantos/kds-web build
  frontend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
"""


def test_negative_synthetic_yaml_is_rejected() -> None:
    """The gate must reject commented-out or misplaced tokens.

    Demonstrates with a synthetic workflow that the anchored matching used by
    the real tests does not accept tokens that are: (a) inside comments, (b)
    inside a sibling job, or (c) embedded as a substring of another command.
    """
    triggers_region = _BAD_YAML.split("jobs:")[0]
    for label, pattern in _TRIGGER_PATTERNS.items():
        assert not _has_anchored_line(triggers_region, pattern), (
            f"Trigger '{label}' should NOT match a commented line, but pattern "
            f"{pattern!r} did"
        )

    frontend_section = _job_section(_BAD_YAML, "frontend")
    for label, pattern in _FRONTEND_STEP_PATTERNS.items():
        assert not _has_anchored_line(frontend_section, pattern), (
            f"Step '{label}' should NOT match when commented/misplaced, but "
            f"pattern {pattern!r} did"
        )
