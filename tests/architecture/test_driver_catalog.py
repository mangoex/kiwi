"""Architecture contract for PRD-FR-210 driver catalog."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_admin_menu_and_route_expose_driver_catalog() -> None:
    layout = _read("apps/admin-web/src/components/AdminLayout.tsx")
    app = _read("apps/admin-web/src/App.tsx")
    assert "{ path: '/drivers', label: 'Repartidores'" in layout
    assert "import DriversList" in app
    assert '<Route path="drivers" element={<DriversList />} />' in app


def test_driver_screen_covers_requested_fields_and_states() -> None:
    source = _read("apps/admin-web/src/features/delivery/DriversList.tsx")
    for field in (
        "name",
        "license_number",
        "motorcycle_plate",
        "branch_id",
        "phone",
        "address",
        "emergency_contact_name",
    ):
        assert field in source
    for label in (
        "Repartidores",
        "Sucursal",
        "Licencia",
        "Placas",
        "Teléfono",
        "Domicilio",
        "Contacto",
        "Estado",
        "Nuevo repartidor",
        "Editar repartidor",
        "Desactivar",
    ):
        assert label in source
    assert "driversQuery.isLoading" in source
    assert "driversQuery.isError" in source
    assert "No hay repartidores registrados" in source
    assert "window.confirm" in source


def test_driver_domain_is_soft_delete_audited_and_pii_safe() -> None:
    operations = _read("apps/api/restaurant_os/operations.py")
    migration = _read(
        "apps/api/alembic/versions/202607230100_0030_driver_catalog.py"
    )
    assert 'require_permission(session, actor_id, "admin.manage")' in operations
    assert 'action="driver.created"' in operations
    assert 'action="driver.updated"' in operations
    assert 'action="driver.deactivated"' in operations
    assert '.values(status="inactive"' in operations
    assert '"changed_fields": changed_fields' in operations
    assert "Cannot downgrade 0030 while driver records exist" in migration


def test_driver_specs_and_traceability_exist() -> None:
    prd = _read("docs/01-PRD.md")
    bdd = _read("docs/03-BDD-driver-catalog.md")
    tdd = _read("docs/04-TDD-driver-catalog.md")
    matrix = _read("docs/05-matriz-trazabilidad.md")
    assert "PRD-FR-210" in prd
    for scenario in range(239, 243):
        assert f"BDD-SC-{scenario}" in bdd
        assert f"BDD-SC-{scenario}" in matrix
    assert "TDD-TS-071" in tdd and "TDD-TC-067" in tdd
    assert "TDD-TS-071" in matrix and "TDD-TC-067" in matrix
