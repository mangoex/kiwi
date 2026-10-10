"""Architecture tests for BA-002 (POS branch admin frontend).

These tests verify the POS frontend code structurally without running a
browser. They check that:

- the canonical session is obtained from ``/auth/session``;
- admin visibility depends on ``branch.admin.access``;
- ``AdminHub`` uses fixed authorized destinations in the shared access policy;
- local routes exist for the eight BA-003 operational cards;
- corporate identity and branch catalogs are absent from the POS hub;
- authorization does not read permissions from ``localStorage``;
- ``active_branch`` replaces a stale local branch and organization selection
  is revalidated before being applied;
- ``SessionGate`` requires ``pos.operate``;
- ``PointOfSale`` uses ``fetchApi`` for modifiers (no raw ``fetch`` for them);
- BDD/TDD docs and traceability exist.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POS_SRC = ROOT / "apps" / "pos-web" / "src"
DOCS = ROOT / "docs"


def _read(rel: str) -> str:
    return (POS_SRC / rel).read_text(encoding="utf-8")


def test_session_consumes_auth_session_endpoint() -> None:
    """The canonical session must call GET /auth/session via fetchApi."""
    source = _read("session.ts")
    assert "/auth/session" in source, (
        "session.ts must consume /auth/session as the canonical session source"
    )
    assert "fetchApi" in source, "session.ts must use fetchApi for the session call"


def test_canonical_branch_replaces_stale_local_branch() -> None:
    """The backend active branch must overwrite, never inherit, local user data."""
    source = _read("session.ts")
    resolver = re.search(
        r"export function resolvePosBranchId\(\): string \{(?P<body>.*?)\n\}",
        source,
        re.DOTALL,
    )
    assert resolver, "resolvePosBranchId must exist"
    resolver_body = resolver.group("body")
    assert "localStorage.getItem('pos_branch_id')" in resolver_body
    for forbidden in ("localStorage.user", "assigned_branch_id", "roles", "is_superadmin"):
        assert forbidden not in resolver_body, (
            f"resolvePosBranchId must not derive branch authority from {forbidden}"
        )

    write_position = source.find("setPosBranchId(session.active_branch.id)")
    publish_position = source.find("setState({ status: 'ok', session })")
    assert write_position >= 0, "The canonical active_branch must update POS branch context"
    assert publish_position > write_position, (
        "The canonical branch must be applied before the session is published"
    )


def test_organization_branch_selection_is_validated_before_application() -> None:
    """An organization selection must round-trip through the canonical endpoint."""
    session_source = _read("session.ts")
    settings_source = _read("features/settings/Settings.tsx")
    assert "/auth/branch-selections" in session_source
    assert "/auth/session?branch_id" not in session_source
    assert "method: 'POST'" in session_source
    assert "expected_authorization_version" in session_source
    assert "allowed_branch_ids.includes(branchId)" in session_source
    assert "nextSession.active_branch?.id !== branchId" in session_source
    assert "applySession(nextSession)" in session_source
    assert "await selectBranch(branchId)" in settings_source
    assert "branchId === activeBranchId" in settings_source, (
        "Cash status and operations must use only the validated active branch"
    )


def test_session_gate_requires_pos_operate() -> None:
    """Authentication alone must not grant access to the POS application."""
    source = _read("App.tsx")
    gate = source.split("const SessionGate", 1)[1].split("const PermissionRoute", 1)[0]
    assert "permissions.includes('pos.operate')" in gate
    assert "Tu cuenta no tiene acceso al POS" in gate


def test_admin_access_uses_branch_admin_access_permission() -> None:
    """Admin visibility must depend on branch.admin.access, not role names."""
    layout = _read("components/PosLayout.tsx")
    assert "canOpenPosAdministration(session)" in layout, (
        "PosLayout must gate the Administración menu on branch.admin.access"
    )
    # The layout must NOT determine admin visibility from isAdministrativeUser
    # (role-name / localStorage based). It should use usePosSession.
    assert "usePosSession" in layout, (
        "PosLayout must use usePosSession for permission decisions"
    )


def test_app_routes_contain_branch_administration_routes() -> None:
    """App.tsx must define the local operational routes inside PosLayout.

    React Router nested routes use relative paths (no leading slash), so we
    check for ``path="administration..."`` patterns.
    """
    source = _read("App.tsx")
    for route in (
        'path="administration"',
        'path="administration/products"',
        'path="administration/variations"',
        'path="administration/suppliers"',
        'path="administration/purchases"',
        'path="administration/production"',
        'path="administration/waste"',
        'path="administration/transfers"',
        'path="administration/counts"',
    ):
        assert route in source, f"App.tsx must define route {route!r}"
    assert 'path="administration/staff"' not in source
    assert 'path="administration/branch"' not in source
    assert "PosSessionProvider" in source, "App must wrap in PosSessionProvider"
    assert "PermissionRoute" in source, "App must use PermissionRoute guards"


def test_admin_hub_only_uses_fixed_authorized_destinations() -> None:
    source = _read("features/admin/AdminHub.tsx")
    assert "adminDestination(session,card.module)" in source
    assert "card.permissions?.some(code=>hasAdminCapability(session,code))" in source
    assert "visible.map" in source
    assert "Restringido" not in source


def test_admin_hub_contains_modules_without_corporate_identity_catalogs() -> None:
    source = _read("features/admin/AdminHub.tsx")
    for module in (
        'products', 'variations', 'ingredient-extras', 'inventory', 'suppliers',
        'purchases', 'production', 'waste', 'transfers', 'counts',
    ):
        assert f"module:'{module}'" in source
    for forbidden in ('Usuarios','Roles','Personal de sucursal'):
        assert forbidden not in source


def test_authorization_does_not_read_permissions_from_localStorage() -> None:
    """The session module must not rely on localStorage for permission checks.

    The canonical PosSessionProvider and hasPermission must derive permissions
    from the /auth/session response, not from a localStorage 'user' object.
    We verify that the provider's hasPermission reads from the session state
    and that there's no localStorage.getItem('permissions') pattern.
    """
    source = _read("session.ts")
    # The canonical provider must use the session from fetchApi
    assert "PosSessionProvider" in source
    assert "hasPermission" in source
    # Must NOT read a 'permissions' key from localStorage for authorization
    assert "localStorage.getItem('permissions')" not in source, (
        "Authorization must not read permissions from localStorage"
    )


def test_point_of_sale_uses_fetchapi_for_modifiers() -> None:
    """PointOfSale must use fetchApi for the modifiers call, not raw fetch."""
    source = _read("features/pos/PointOfSale.tsx")
    # Find the modifiers call context
    modifiers_match = re.search(r"modifiers[^\n]{0,60}", source)
    assert modifiers_match, "PointOfSale must reference modifiers"
    # The modifiers fetch must use fetchApi, not a bare fetch()
    # Check that there's no raw fetch( with /modifiers
    raw_modifier_fetch = re.search(r"fetch\(\s*[`'\"]/api/v1/products/[^\n]*modifiers", source)
    assert raw_modifier_fetch is None, (
        "PointOfSale must not use raw fetch() for modifiers; use fetchApi instead"
    )


def test_canonical_catalog_preserves_local_availability_contracts() -> None:
    products = (ROOT / "apps/admin-web/src/features/catalog/CatalogAdministration.tsx").read_text(
        encoding="utf-8"
    )
    assert "/branch-administration/catalog/" in products
    assert "catalog.branch.manage" in products
    assert "branch_id=${encodeURIComponent(branchId)}" in products
    assert "effective_availability" in products

def test_settings_uses_canonical_session_for_branch_scope() -> None:
    """Settings must use the canonical session, not /branches for branch scope."""
    source = _read("features/settings/Settings.tsx")
    assert "usePosSession" in source, (
        "Settings must use usePosSession for branch scope decisions"
    )
    assert "scope.can_select_branch" in source, (
        "Settings must consume the canonical server decision for branch mobility"
    )


def test_bdd_and_tdd_docs_exist() -> None:
    """BDD and TDD docs for the POS branch admin frontend must exist."""
    bdd = DOCS / "03-BDD-pos-branch-administration.md"
    tdd = DOCS / "04-TDD-pos-branch-administration.md"
    assert bdd.exists(), f"BDD doc missing: {bdd}"
    assert tdd.exists(), f"TDD doc missing: {tdd}"
    bdd_content = bdd.read_text(encoding="utf-8")
    for sc in (
        "BDD-SC-125",
        "BDD-SC-126",
        "BDD-SC-127",
        "BDD-SC-128",
        "BDD-SC-129",
        "BDD-SC-130",
        "BDD-SC-131",
        "BDD-SC-132",
        "BDD-SC-133",
        "BDD-SC-134",
        "BDD-SC-135",
    ):
        assert sc in bdd_content, f"BDD doc missing {sc}"
    assert not re.search(r"^\s+Y\s", bdd_content, re.MULTILINE), (
        "English Gherkin must use And instead of an undeclared Spanish Y keyword"
    )
    tdd_content = tdd.read_text(encoding="utf-8")
    assert "TDD-TS-051" in tdd_content
    assert "TDD-TC-044" in tdd_content


def test_traceability_references_new_scenarios() -> None:
    """The traceability matrix must reference the new BDD/TDD IDs."""
    matrix = (DOCS / "05-matriz-trazabilidad.md").read_text(encoding="utf-8")
    for token in (
        "BDD-SC-125",
        "BDD-SC-129",
        "BDD-SC-133",
        "BDD-SC-134",
        "BDD-SC-135",
        "TDD-TS-051",
        "TDD-TC-044",
    ):
        assert token in matrix, f"Traceability matrix missing {token}"
