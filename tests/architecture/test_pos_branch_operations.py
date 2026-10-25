"""One administrative implementation; runtime policy/API tests complement these boundaries."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding='utf-8')


def test_pos_navigation_and_redirects_use_shared_authority():
    layout = read('apps/pos-web/src/components/PosLayout.tsx')
    hub = read('apps/pos-web/src/features/admin/AdminHub.tsx')
    redirect = read('apps/pos-web/src/features/admin/AdminNavigation.tsx')
    assert 'canOpenPosAdministration(session)' in layout
    assert 'adminDestination(session' in hub and 'adminDestination(session' in redirect
    assert 'hasAdminCapability(session' in hub
    assert 'Restringido' not in hub
    assert 'confirmWorkspaceNavigation()' in hub
    assert 'navigator.onLine' in hub
    for source in (layout, hub, redirect):
        assert 'is_superadmin' not in source
        assert "localStorage.getItem('user')" not in source


def test_legacy_routes_no_longer_mount_duplicate_implementations():
    app = read('apps/pos-web/src/App.tsx')
    for module in (
        'products', 'inventory', 'variations', 'ingredient-extras', 'suppliers',
        'purchases', 'production', 'waste', 'transfers', 'counts',
    ):
        assert (
            f'path="administration/{module}" '
            f'element={{<AdminModuleRedirect module="{module}"' in app
        )
    for obsolete in (
        'BranchAdminOperations', 'BranchAdminProducts', 'BranchAdminVariations',
        'BranchAdminIngredientExtras', 'PosInventory',
    ):
        assert obsolete not in app
    assert '<PhysicalCountCapturePage />' in app
    assert '<AttendanceReport />' in app


def test_admin_pages_are_guarded_before_mounting():
    app = read('apps/admin-web/src/App.tsx')
    layout = read('apps/admin-web/src/components/AdminLayout.tsx')
    session = read('apps/admin-web/src/lib/adminSession.tsx')
    assert '<AdminSessionProvider>' in app
    assert '<AdminRouteGuard><Outlet /></AdminRouteGuard>' in layout
    assert 'canAccessAdminRoute(session, pathname)' in session
    assert 'routeKey !== location.key' in session
    assert "fetchApi<AdminSession>('/auth/session'" in session
    assert "/auth/session${requested" not in session
    assert "localStorage.getItem('admin_branch_id')" not in session
    assert 'requested && session.active_branch.id !== requested' in session
    assert 'credential !== token()' in session
    assert 'resetQueries()' in session


def test_local_availability_is_not_mounted_for_global_order_comments():
    app = read('apps/admin-web/src/App.tsx')
    catalog = read('apps/admin-web/src/features/catalog/CatalogAdministration.tsx')
    for kind in ('products','variations','ingredient-extras'):
        assert f'<CatalogAdministration kind="{kind}"' in app
    for page in ('<ProductsList />','<VariationNotes />','<IngredientExtras />'):
        assert page in catalog
    assert "variations: 'variation-notes'" not in catalog
    assert "kind === 'ingredient-extras' && branchAccess && branchManage" in catalog
    assert 'branch_id=${encodeURIComponent(branchId)}' in catalog
    assert 'catalog.branch.manage' in catalog and 'branch.admin.access' in catalog
    assert "method: 'PUT'" in catalog
    assert 'row.has_local_override' in catalog


def test_every_order_comment_writer_uses_the_organization_lock():
    operations = read('apps/api/restaurant_os/operations.py')
    writers = (
        'archive_all_order_comments',
        'delete_order_comment',
        'delete_all_order_comments',
        'bulk_order_comments',
        'update_order_comment',
        'replace_order_comment_products',
    )
    for index, writer in enumerate(writers):
        start = operations.index(f'def {writer}(')
        remaining_starts = [
            operations.find(f'def {candidate}(', start + 1)
            for candidate in writers[index + 1:]
        ]
        next_starts = [position for position in remaining_starts if position >= 0]
        end = min(next_starts) if next_starts else operations.find('\n\ndef ', start + 1)
        body = operations[start:end if end >= 0 else len(operations)]
        assert '_require_order_comment_catalog_authority(session, actor_id)' in body
        assert (
            '_acquire_idempotency_lock(session, "order-comment-catalog", ORGANIZATION_ID)'
            in body
        )


def test_order_comment_write_responses_are_materialized_before_commit():
    operations = read('apps/api/restaurant_os/operations.py')
    boundaries = (
        ('bulk_order_comments', 'update_order_comment'),
        ('update_order_comment', 'replace_order_comment_products'),
        ('replace_order_comment_products', 'PRESET_VARIATION_GROUP'),
    )
    for writer, next_symbol in boundaries:
        start = operations.index(f'def {writer}(')
        end = operations.index(next_symbol, start + 1)
        body = operations[start:end]
        response_position = body.rfind('response = ')
        commit_position = body.rfind('session.commit()')
        return_position = body.rfind('return response')
        assert 0 <= response_position < commit_position < return_position


def test_read_only_and_directional_operations_use_canonical_capabilities():
    expected = {
        'purchasing/PurchasesList.tsx': 'purchases.manage',
        'purchasing/SuppliersList.tsx': 'catalog.manage',
        'purchasing/PresentationsList.tsx': 'admin.manage',
        'production/ProductionList.tsx': 'catalog.manage',
        'inventory/WasteList.tsx': 'inventory.waste',
        'inventory/TransferList.tsx': 'inventory.transfer.receive',
        'inventory/PhysicalCountList.tsx': 'inventory.count.approve',
    }
    for path, code in expected.items():
        assert f"useAdminPermission('{code}')" in read('apps/admin-web/src/features/'+path)
    purchases = read('apps/admin-web/src/features/purchasing/PurchasesList.tsx')
    assert '<PurchaseDocumentEditor' in purchases
    assert 'canWrite && canonicalSession' in purchases
    assert 'if (!canWrite || uncertain || sending.current) return;' in purchases
    transfers = read('apps/admin-web/src/features/inventory/TransferList.tsx')
    assert 'transfer.source_branch_id === branchId' in transfers
    assert 'transfer.destination_branch_id === branchId' in transfers


def test_branch_helper_never_treats_local_storage_or_role_names_as_authority():
    source = read('apps/admin-web/src/lib/branchContext.ts')
    assert 'canonicalSession?.active_branch.id' in source
    assert 'canonicalSession?.scope.level' in source
    assert "localStorage.getItem('user')" not in source
    assert "roles?.includes('Supervisor')" not in source
    for path in ('features/hubs/BranchesHub.tsx','features/admin-catalog/CategoryPriorities.tsx'):
        page = read('apps/admin-web/src/'+path)
        assert "localStorage.getItem('user')" not in page
        assert 'useAdminPermission(' in page


def test_cashier_capture_has_a_navigation_guard():
    source = read('apps/pos-web/src/features/pos/useCashierDrafts.ts')
    assert 'registerWorkspaceNavigationGuard' in source
    assert 'uncertainRef.current()' in source
    assert 'flushRef.current()' in source
    assert 'readyRef.current' in source


def test_bdd_tdd_and_traceability_cover_unification():
    bdd = read('docs/03-BDD-pos-branch-operations.md')
    tdd = read('docs/04-TDD-pos-branch-operations.md')
    matrix = read('docs/05-matriz-trazabilidad.md')
    for scenario in range(136,144):
        assert f'BDD-SC-{scenario}' in bdd and f'BDD-SC-{scenario}' in matrix
    assert 'TDD-TS-052' in tdd and 'TDD-TC-045' in tdd
    assert 'test_admin_access.mjs' in tdd and 'test_admin_unification.py' in tdd
