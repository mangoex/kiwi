"""TDD-TC-247: combos keep frozen production facts across operational channels."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.combo import capture_combo_line, save_composition
from restaurant_os.integrations import channel_service
from restaurant_os.operations import (
    accept_public_order_intent,
    amend_order,
    apply_order_reopen_request,
    cancel_order,
    create_local_order,
    create_public_order_intent,
)
from test_cash_concepts import OWNER_ID
from test_cash_ledger import BRANCH_A, NOW, ORG_ID, SHIFT_ID, _new_session
from test_combo_compositions import (
    ACTOR,
    BURGER,
    CATEGORY,
    COMBO,
    DRINK,
    _seed,
    _seed_combo_recipes_and_order_scope,
)
from test_order_corrections import _approved_production_request, _order, _plan
from test_order_reopen_workflow import CHIEF_ID, CHIEF_ROLE_ID

PUBLIC_KEY = "pk_combo_operational_channels"


def _save_combo(session, key: str) -> None:
    save_composition(
        session,
        ACTOR,
        COMBO,
        None,
        expected_version=0,
        idempotency_key=key,
        components=[
            {"product_id": BURGER, "quantity": "1"},
            {"product_id": DRINK, "quantity": "1"},
        ],
    )


def _seed_correction_chief(session) -> None:
    """Add only correction-specific authority after combo order permissions exist."""
    session.execute(
        models.roles.insert().values(
            id=CHIEF_ROLE_ID,
            organization_id=ORG_ID,
            name="Cajero jefe",
            scope="branch",
            created_at=NOW,
        )
    )
    session.execute(
        models.users.insert().values(
            id=CHIEF_ID,
            organization_id=ORG_ID,
            email="chief-combo@example.invalid",
            display_name="Cajero jefe",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.execute(
        models.user_roles.insert().values(
            user_id=CHIEF_ID, role_id=CHIEF_ROLE_ID, branch_id=BRANCH_A
        )
    )
    for permission_id, code in (
        ("combo-reopen-request", "orders.reopen.request"),
        ("combo-reopen-authorize", "orders.reopen.authorize"),
    ):
        session.execute(
            models.permissions.insert().values(
                id=permission_id, code=code, description=code, created_at=NOW
            )
        )
    session.execute(
        models.role_permissions.insert(),
        [
            {"role_id": CHIEF_ROLE_ID, "permission_id": "combo-orders-read"},
            {"role_id": CHIEF_ROLE_ID, "permission_id": "combo-reopen-request"},
        ],
    )
    session.commit()


def _seed_accepted_combo_for_correction(session) -> tuple[str, str]:
    _seed(session)
    _seed_combo_recipes_and_order_scope(session)
    _seed_correction_chief(session)
    _save_combo(session, "combo-correction-composition-001")
    order_id = _order(session, 71)
    line_id = "018f6f73-2d0a-74f0-8f1c-000000009971"
    session.execute(
        models.orders.update()
        .where(models.orders.c.id == order_id)
        .values(total_cents=31800)
    )
    session.execute(
        models.payments.update()
        .where(models.payments.c.order_id == order_id)
        .values(amount_cents=31800)
    )
    session.execute(
        models.order_lines.insert().values(
            id=line_id,
            order_id=order_id,
            product_id=COMBO,
            product_name="Combo fijo",
            quantity=2,
            unit_price_cents=15900,
            line_total_cents=31800,
            station="packing",
            selected_modifiers=[],
            modifier_total_cents=0,
            line_notes=None,
            status="active",
            revision=1,
            supersedes_line_id=None,
            updated_at=NOW,
            removed_at=None,
            family_id_snapshot=CATEGORY,
            family_name_snapshot="Combos",
            family_snapshot_source="captured",
            created_at=NOW,
        )
    )
    cost_state = {
        "branch_id": BRANCH_A,
        "warehouse_id": "combo-warehouse",
        "item_id": "018f6f73-2d0a-74f0-8f1c-000000009307",
    }
    exists = session.scalar(
        sa.select(models.inventory_cost_states.c.item_id).where(
            *(models.inventory_cost_states.c[key] == value for key, value in cost_state.items())
        )
    )
    if exists:
        session.execute(
            models.inventory_cost_states.update()
            .where(
                *(models.inventory_cost_states.c[key] == value for key, value in cost_state.items())
            )
            .values(average_unit_cost=Decimal("4"), last_unit_cost=Decimal("4"), updated_at=NOW)
        )
    else:
        session.execute(
            models.inventory_cost_states.insert().values(
                **cost_state,
                quantity_on_hand=Decimal("0"),
                average_unit_cost=Decimal("4"),
                last_unit_cost=Decimal("4"),
                last_supplier_id=None,
                last_cost_at=None,
                updated_at=NOW,
            )
        )
    capture_combo_line(
        session,
        order={
            "id": order_id,
            "organization_id": ORG_ID,
            "branch_id": BRANCH_A,
            "folio": "PCO005-71",
        },
        line={"id": line_id, "product_id": COMBO, "product_name": "Combo fijo", "quantity": 2},
        created_at=NOW,
    )
    payment_id = session.scalar(
        sa.select(models.payments.c.id).where(models.payments.c.order_id == order_id)
    )
    assert payment_id
    session.execute(
        models.sales_operation_snapshots.insert().values(
            id="018f6f73-2d0a-74f0-8f1c-000000009972",
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            payment_id=payment_id,
            order_id=order_id,
            cash_shift_id=SHIFT_ID,
            register_code_snapshot="CAJA-01",
            folio_snapshot="PCO005-71",
            service_type_snapshot="takeout",
            currency="MXN",
            gross_cents=31800,
            net_cents=31800,
            discount_cents=0,
            courtesy_cents=0,
            tax_cents=0,
            quality_status="captured",
            confirmed_at=NOW,
            created_at=NOW,
        )
    )
    session.commit()
    return order_id, line_id


def test_correction_reduces_combo_once_and_restores_frozen_component_tasks() -> None:
    engine, session = _new_session()
    try:
        order_id, line_id = _seed_accepted_combo_for_correction(session)
        request = _approved_production_request(session, order_id, "combo-reduce")

        result = apply_order_reopen_request(
            session,
            str(request["id"]),
            _plan([{"source_line_id": line_id, "quantity": 1}]),
            "combo-correction-reduce-001",
            OWNER_ID,
        )

        adjustments = result["production_adjustments"]
        assert [(row["adjustment_type"], str(row["quantity"])) for row in adjustments] == [
            ("RELEASE", "1"),
            ("RELEASE", "1"),
        ]
        correction_id = result["correction"]["id"]
        releases = session.execute(
            sa.select(models.inventory_movements.c.quantity_delta).where(
                models.inventory_movements.c.document_id == correction_id,
                models.inventory_movements.c.movement_type == "RESERVATION_RELEASE",
            )
        ).scalars().all()
        assert sorted(Decimal(str(value)) for value in releases) == [
            Decimal("0.250000"),
            Decimal("0.250000"),
        ]
        net_reserved = session.execute(
            sa.select(
                sa.func.sum(models.inventory_movements.c.quantity_delta),
                sa.func.sum(models.inventory_movements.c.total_cost),
            ).where(
                models.inventory_movements.c.source_id.in_([order_id, correction_id]),
                models.inventory_movements.c.movement_type.in_(
                    ["SALE_RESERVATION", "RESERVATION_RELEASE"]
                ),
            )
        ).one()
        assert tuple(Decimal(str(value)) for value in net_reserved) == (
            Decimal("-0.500000"),
            Decimal("-2.000000"),
        )
        replay = apply_order_reopen_request(
            session,
            str(request["id"]),
            _plan([{"source_line_id": line_id, "quantity": 1}]),
            "combo-correction-reduce-001",
            OWNER_ID,
        )
        assert replay == result
        replay_net = session.execute(
            sa.select(sa.func.sum(models.inventory_movements.c.quantity_delta)).where(
                models.inventory_movements.c.source_id.in_([order_id, correction_id]),
                models.inventory_movements.c.movement_type.in_(
                    ["SALE_RESERVATION", "RESERVATION_RELEASE"]
                ),
            )
        ).scalar_one()
        assert Decimal(str(replay_net)) == Decimal("-0.500000")
        replacement_line_id = session.scalar(
            sa.select(models.order_correction_lines.c.operational_order_line_id).where(
                models.order_correction_lines.c.source_line_id == line_id
            )
        )
        assert replacement_line_id
        tasks = session.execute(
            sa.select(models.production_tasks).where(
                models.production_tasks.c.order_line_id == replacement_line_id,
                models.production_tasks.c.status == "PENDING",
            )
        ).mappings().all()
        assert {(task["station"], task["quantity"]) for task in tasks} == {
            ("kitchen", 1),
            ("beverages", 1),
        }
    finally:
        session.close()
        engine.dispose()


def test_combo_amendments_and_final_cancellation_leave_no_reservation() -> None:
    engine, session = _new_session()
    try:
        _seed(session)
        _seed_combo_recipes_and_order_scope(session)
        _save_combo(session, "combo-amend-cancel-composition-001")
        created = create_local_order(
            session,
            [{"product_id": COMBO, "quantity": 2}],
            register_id="CAJA-01",
            actor_user_id=ACTOR,
            idempotency_key="combo-amend-cancel-create-001",
        )
        first = amend_order(
            session,
            created["id"],
            [{"product_id": COMBO, "quantity": 1}],
            expected_version=1,
            idempotency_key="combo-amend-cancel-first-001",
            actor_user_id=ACTOR,
        )
        second = amend_order(
            session,
            created["id"],
            [{"product_id": COMBO, "quantity": 2}],
            expected_version=2,
            idempotency_key="combo-amend-cancel-second-001",
            actor_user_id=ACTOR,
        )
        assert second["version"] == 3
        cancelled = cancel_order(session, created["id"], actor_user_id=ACTOR)
        assert cancelled["status"] == "CANCELLED"
        remaining = session.execute(
            sa.select(
                sa.func.sum(models.inventory_movements.c.quantity_delta),
                sa.func.sum(models.inventory_movements.c.total_cost),
            ).where(
                models.inventory_movements.c.source_id == created["id"],
                models.inventory_movements.c.movement_type.in_(
                    ["SALE_RESERVATION", "RESERVATION_RELEASE"]
                ),
            )
        ).one()
        assert tuple(Decimal(str(value)) for value in remaining) == (
            Decimal("0.000000"),
            Decimal("0.000000"),
        )
        assert first["version"] == 2
        active_tasks = session.scalars(
            sa.select(sa.func.count()).select_from(models.production_tasks).where(
                models.production_tasks.c.order_id == created["id"],
                models.production_tasks.c.status == "PENDING",
            )
        ).one()
        assert active_tasks == 0
    finally:
        session.close()
        engine.dispose()


def test_correction_addition_expands_combo_without_generic_combo_task() -> None:
    engine, session = _new_session()
    try:
        order_id, _ = _seed_accepted_combo_for_correction(session)
        request = _approved_production_request(session, order_id, "combo-add")

        result = apply_order_reopen_request(
            session,
            str(request["id"]),
            _plan([{"product_id": COMBO, "quantity": 1}]),
            "combo-correction-add-001",
            OWNER_ID,
        )

        addition = next(
            row for row in result["production_adjustments"] if row["adjustment_type"] == "ADDITION"
        )
        added_line_id = session.scalar(
            sa.select(models.order_correction_lines.c.operational_order_line_id).where(
                models.order_correction_lines.c.correction_id == result["correction"]["id"],
                models.order_correction_lines.c.product_id == COMBO,
            )
        )
        assert added_line_id
        tasks = session.execute(
            sa.select(
                models.production_tasks.c.product_name, models.production_tasks.c.station
            ).where(
                models.production_tasks.c.order_line_id == added_line_id
            )
        ).all()
        assert set(tasks) == {("Hamburguesa", "kitchen"), ("Refresco", "beverages")}
        addition_movement = session.execute(
            sa.select(models.inventory_movements).where(
                models.inventory_movements.c.id == addition["inventory_movement_id"]
            )
        ).mappings().one()
        assert addition_movement["document_id"] == result["correction"]["id"]
        assert addition_movement["source_type"] == "order_correction"
        assert Decimal(str(addition_movement["quantity_delta"])) == Decimal("-0.500000")
    finally:
        session.close()
        engine.dispose()


def test_combo_correction_uses_task_identity_when_component_labels_collide() -> None:
    engine, session = _new_session()
    try:
        order_id, line_id = _seed_accepted_combo_for_correction(session)
        session.execute(
            models.products.update()
            .where(models.products.c.id == DRINK)
            .values(name="Hamburguesa", station="kitchen")
        )
        session.execute(
            models.production_tasks.update()
            .where(
                models.production_tasks.c.order_line_id == line_id,
                models.production_tasks.c.product_name == "Refresco",
            )
            .values(product_name="Hamburguesa", station="kitchen")
        )
        session.execute(
            models.order_line_component_snapshots.update()
            .where(
                models.order_line_component_snapshots.c.order_line_id == line_id,
                models.order_line_component_snapshots.c.component_product_id == DRINK,
            )
            .values(component_product_name="Hamburguesa", station="kitchen")
        )
        session.commit()
        task_ids = set(
            session.scalars(
                sa.select(models.production_tasks.c.id).where(
                    models.production_tasks.c.order_line_id == line_id
                )
            )
        )
        snapshot_task_ids = set(
            session.scalars(
                sa.select(models.order_line_component_snapshots.c.production_task_id).where(
                    models.order_line_component_snapshots.c.order_line_id == line_id
                )
            )
        )
        assert task_ids == snapshot_task_ids
        request = _approved_production_request(session, order_id, "combo-colliding-labels")

        result = apply_order_reopen_request(
            session,
            str(request["id"]),
            _plan([{"source_line_id": line_id, "quantity": 1}]),
            "combo-correction-colliding-labels-001",
            OWNER_ID,
        )

        correction_id = result["correction"]["id"]
        releases = session.scalars(
            sa.select(models.inventory_movements.c.quantity_delta).where(
                models.inventory_movements.c.document_id == correction_id,
                models.inventory_movements.c.movement_type == "RESERVATION_RELEASE",
            )
        ).all()
        assert sorted(Decimal(str(value)) for value in releases) == [
            Decimal("0.250000"),
            Decimal("0.250000"),
        ]
        replacement_task_ids = set(
            session.scalars(
                sa.select(models.order_production_adjustments.c.production_task_id).where(
                    models.order_production_adjustments.c.correction_id == correction_id
                )
            )
        )
        assert len(replacement_task_ids) == 2
        assert None not in replacement_task_ids
    finally:
        session.close()
        engine.dispose()


def test_each_combo_addition_links_its_own_reservation_movement() -> None:
    engine, session = _new_session()
    try:
        order_id, _ = _seed_accepted_combo_for_correction(session)
        request = _approved_production_request(session, order_id, "combo-two-additions")

        result = apply_order_reopen_request(
            session,
            str(request["id"]),
            _plan(
                [
                    {"product_id": COMBO, "quantity": 1},
                    {"product_id": COMBO, "quantity": 1},
                ]
            ),
            "combo-correction-two-additions-001",
            OWNER_ID,
        )

        additions = [
            row for row in result["production_adjustments"] if row["adjustment_type"] == "ADDITION"
        ]
        assert len(additions) == 2
        movement_ids = {row["inventory_movement_id"] for row in additions}
        assert len(movement_ids) == 2
        movements = session.execute(
            sa.select(models.inventory_movements).where(models.inventory_movements.c.id.in_(movement_ids))
        ).mappings().all()
        assert len(movements) == 2
        assert {row["document_id"] for row in movements} == {result["correction"]["id"]}
        quantity_delta = sum(
            (Decimal(str(row["quantity_delta"])) for row in movements), Decimal("0")
        )
        assert quantity_delta == Decimal("-1.000000")
    finally:
        session.close()
        engine.dispose()


def test_correction_settles_mixed_combo_task_states_by_component_snapshot() -> None:
    engine, session = _new_session()
    try:
        order_id, line_id = _seed_accepted_combo_for_correction(session)
        tasks = session.execute(
            sa.select(models.production_tasks).where(
                models.production_tasks.c.order_line_id == line_id
            )
        ).mappings().all()
        completed = next(task for task in tasks if task["product_name"] == "Hamburguesa")
        session.execute(
            models.production_tasks.update()
            .where(models.production_tasks.c.id == completed["id"])
            .values(status="COMPLETED", started_at=NOW, completed_at=NOW)
        )
        session.commit()
        request = _approved_production_request(session, order_id, "combo-mixed-state")

        result = apply_order_reopen_request(
            session,
            str(request["id"]),
            _plan(
                [{"source_line_id": line_id, "quantity": 1}],
                [
                    {
                        "source_line_id": line_id,
                        "source_task_id": completed["id"],
                        "quantity": 1,
                        "disposition": "recovery",
                    }
                ],
            ),
            "combo-correction-mixed-state-001",
            OWNER_ID,
        )

        correction_id = result["correction"]["id"]
        movements = session.execute(
            sa.select(
                models.inventory_movements.c.movement_type,
                models.inventory_movements.c.quantity_delta,
            )
            .where(models.inventory_movements.c.document_id == correction_id)
            .order_by(models.inventory_movements.c.movement_type)
        ).all()
        assert movements == [
            ("RECOVERY", Decimal("0.250000")),
            ("RESERVATION_RELEASE", Decimal("0.250000")),
        ]
        assert {row["adjustment_type"] for row in result["production_adjustments"]} == {
            "RECOVERY",
            "RELEASE",
        }
    finally:
        session.close()
        engine.dispose()


def test_correction_keeps_distinct_completed_combo_dispositions() -> None:
    engine, session = _new_session()
    try:
        order_id, line_id = _seed_accepted_combo_for_correction(session)
        tasks = session.execute(
            sa.select(models.production_tasks).where(
                models.production_tasks.c.order_line_id == line_id
            )
        ).mappings().all()
        session.execute(
            models.production_tasks.update()
            .where(models.production_tasks.c.order_line_id == line_id)
            .values(status="COMPLETED", started_at=NOW, completed_at=NOW)
        )
        session.commit()
        dispositions = [
            {
                "source_line_id": line_id,
                "source_task_id": task["id"],
                "quantity": 1,
                "disposition": "waste" if task["product_name"] == "Hamburguesa" else "recovery",
            }
            for task in tasks
        ]
        request = _approved_production_request(session, order_id, "combo-mixed-disposition")

        result = apply_order_reopen_request(
            session,
            str(request["id"]),
            _plan([{"source_line_id": line_id, "quantity": 1}], dispositions),
            "combo-correction-mixed-disposition-001",
            OWNER_ID,
        )

        correction_id = result["correction"]["id"]
        movements = session.execute(
            sa.select(
                models.inventory_movements.c.movement_type,
                models.inventory_movements.c.quantity_delta,
            )
            .where(models.inventory_movements.c.document_id == correction_id)
            .order_by(models.inventory_movements.c.movement_type)
        ).all()
        assert movements == [
            ("RECOVERY", Decimal("0.250000")),
            ("WASTE", Decimal("0.000000")),
        ]
        assert {row["adjustment_type"] for row in result["production_adjustments"]} == {
            "RECOVERY",
            "WASTE",
        }
    finally:
        session.close()
        engine.dispose()


def test_public_acceptance_freezes_combo_after_intent_capture() -> None:
    engine, session = _new_session()
    try:
        _seed(session)
        _seed_combo_recipes_and_order_scope(session)
        _save_combo(session, "combo-public-composition-001")
        session.execute(
            models.public_order_keys.insert().values(
                public_key=PUBLIC_KEY,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                status="active",
            )
        )
        session.commit()
        created, _ = create_public_order_intent(
            session,
            PUBLIC_KEY,
            {
                "customer_name": "Comprador de prueba",
                "customer_phone": "5512345678",
                "order_type": "takeout",
                "lines": [{"product_id": COMBO, "quantity": 2, "modifiers": []}],
            },
            "combo-public-intent-create-001",
        )
        intent_id = session.scalar(
            sa.select(models.public_order_intents.c.id).where(
                models.public_order_intents.c.public_reference == created["public_reference"]
            )
        )
        assert intent_id
        accepted, _ = accept_public_order_intent(
            session,
            str(intent_id),
            1,
            "combo-public-intent-accept-001",
            ACTOR,
        )
        tasks = session.execute(
            sa.select(models.production_tasks.c.station, models.production_tasks.c.quantity).where(
                models.production_tasks.c.order_id == accepted["id"]
            )
        ).all()
        assert set(tasks) == {("kitchen", 2), ("beverages", 2)}
        reservations = session.execute(
            sa.select(models.inventory_movements.c.quantity_delta).where(
                models.inventory_movements.c.document_id == accepted["id"],
                models.inventory_movements.c.movement_type == "SALE_RESERVATION",
            )
        ).scalars().all()
        assert [Decimal(str(value)) for value in reservations] == [Decimal("-1.000000")]
    finally:
        session.close()
        engine.dispose()


def test_public_acceptance_fails_closed_when_combo_was_withdrawn() -> None:
    engine, session = _new_session()
    try:
        _seed(session)
        _seed_combo_recipes_and_order_scope(session)
        _save_combo(session, "combo-public-withdrawn-composition-001")
        session.execute(
            models.public_order_keys.insert().values(
                public_key=PUBLIC_KEY,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                status="active",
            )
        )
        session.commit()
        created, _ = create_public_order_intent(
            session,
            PUBLIC_KEY,
            {
                "customer_name": "Comprador de prueba",
                "customer_phone": "5512345678",
                "order_type": "takeout",
                "lines": [{"product_id": COMBO, "quantity": 1, "modifiers": []}],
            },
            "combo-public-withdrawn-create-001",
        )
        intent_id = session.scalar(
            sa.select(models.public_order_intents.c.id).where(
                models.public_order_intents.c.public_reference == created["public_reference"]
            )
        )
        assert intent_id
        session.execute(
            models.product_compositions.update()
            .where(models.product_compositions.c.combo_product_id == COMBO)
            .values(status="superseded")
        )
        with pytest.raises(Exception) as rejected:
            accept_public_order_intent(
                session,
                str(intent_id),
                1,
                "combo-public-withdrawn-accept-001",
                ACTOR,
            )
        assert getattr(rejected.value, "code", None) == "public_order_transition_invalid"
        session.rollback()
        assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 0
    finally:
        session.close()
        engine.dispose()


def test_marketplace_auto_acceptance_freezes_combo_components() -> None:
    engine, session = _new_session()
    try:
        _seed(session)
        _seed_combo_recipes_and_order_scope(session)
        _save_combo(session, "combo-marketplace-composition-001")
        session.execute(
            models.channel_integrations.insert().values(
                id=str(uuid4()),
                organization_id=ORG_ID,
                provider="UBER_EATS",
                is_enabled=True,
                environment="sandbox",
                client_id=None,
                client_secret=None,
                webhook_secret=None,
                auto_accept=True,
                default_prep_time_minutes=20,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.channel_store_mappings.insert().values(
                id=str(uuid4()),
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                provider="UBER_EATS",
                external_store_id="combo-store-001",
                is_active=True,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.channel_product_mappings.insert().values(
                id=str(uuid4()),
                organization_id=ORG_ID,
                product_id=COMBO,
                provider="UBER_EATS",
                external_item_id="combo-external-001",
                is_active=True,
                created_at=NOW,
            )
        )
        session.commit()
        result = channel_service.process_webhook_order(
            session,
            ORG_ID,
            "UBER_EATS",
            {
                "id": "combo-marketplace-order-001",
                "display_id": "COMBO-1",
                "store": {"id": "combo-store-001"},
                "eater": {"first_name": "Comprador"},
                "cart": {
                    "items": [
                        {
                            "id": "combo-line-001",
                            "external_data": "combo-external-001",
                            "title": "Combo fijo",
                            "quantity": 2,
                            "price": {"unit_price": {"amount": 15900}},
                        }
                    ]
                },
                "payment": {"charges": {"total": {"amount": 31800}}},
                "currency": "MXN",
            },
        )
        assert result["order_status"] == "ACCEPTED"
        tasks = session.execute(
            sa.select(models.production_tasks.c.station, models.production_tasks.c.quantity).where(
                models.production_tasks.c.order_id == result["order_id"]
            )
        ).all()
        assert set(tasks) == {("kitchen", 2), ("beverages", 2)}
    finally:
        session.close()
        engine.dispose()


def test_marketplace_rejects_component_modifiers_for_fixed_combo() -> None:
    engine, session = _new_session()
    try:
        _seed(session)
        _seed_combo_recipes_and_order_scope(session)
        _save_combo(session, "combo-marketplace-modifier-composition-001")
        session.execute(
            models.channel_integrations.insert().values(
                id=str(uuid4()), organization_id=ORG_ID, provider="UBER_EATS", is_enabled=True,
                environment="sandbox", client_id=None, client_secret=None, webhook_secret=None,
                auto_accept=True, default_prep_time_minutes=20, created_at=NOW, updated_at=NOW,
            )
        )
        session.execute(
            models.channel_product_mappings.insert().values(
                id=str(uuid4()), organization_id=ORG_ID, product_id=COMBO, provider="UBER_EATS",
                external_item_id="combo-modifier-external-001", is_active=True, created_at=NOW,
            )
        )
        session.execute(
            models.channel_store_mappings.insert().values(
                id=str(uuid4()),
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                provider="UBER_EATS",
                external_store_id="combo-modifier-store-001",
                is_active=True,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.commit()
        with pytest.raises(Exception) as rejected:
            channel_service.process_webhook_order(
                session,
                ORG_ID,
                "UBER_EATS",
                {
                    "id": "combo-marketplace-modifier-order-001",
                    "display_id": "COMBO-MOD",
                    "store": {"id": "combo-modifier-store-001"},
                    "eater": {"first_name": "Comprador"},
                    "cart": {"items": [{
                        "id": "combo-modifier-line-001",
                        "external_data": "combo-modifier-external-001",
                        "title": "Combo fijo",
                        "quantity": 1,
                        "unit_price_cents": 15900,
                        "modifiers": [{"option": "sin hielo"}],
                    }]},
                    "total_cents": 15900,
                },
            )
        assert getattr(rejected.value, "code", None) == "combo_modifiers_not_supported"
        session.rollback()
        assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 0
    finally:
        session.close()
        engine.dispose()


def test_combo_rejects_an_archived_component_before_any_operational_fact() -> None:
    engine, session = _new_session()
    try:
        _seed(session)
        _seed_combo_recipes_and_order_scope(session)
        _save_combo(session, "combo-archived-component-composition-001")
        session.execute(
            models.products.update().where(models.products.c.id == DRINK).values(status="archived")
        )
        session.commit()
        with pytest.raises(Exception) as rejected:
            create_local_order(
                session,
                [{"product_id": COMBO, "quantity": 1}],
                register_id="CAJA-01",
                actor_user_id=ACTOR,
                idempotency_key="combo-archived-component-order-001",
            )
        assert getattr(rejected.value, "code", None) in {
            "combo_component_out_of_scope",
            "combo_component_unavailable",
        }
        session.rollback()
        assert session.scalar(sa.select(sa.func.count()).select_from(models.production_tasks)) == 0
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.inventory_movements)) == 0
        )
    finally:
        session.close()
        engine.dispose()
