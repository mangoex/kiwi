"""An employee identifier is public, not a supervisor credential (CC-D08)."""

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import BRANCH_A, ORG_ID, CashWorld, cash_world, grant_permission, ident
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.auth import PASSWORD_ALGORITHM, generate_password_salt, hash_password
from sqlalchemy.orm import Session
from test_cash_ledger import NOW

__all__ = ["cash_world"]


def credential(session: Session, user: str, secret: str | None = None) -> str:
    secret = secret or ident("synthetic-f108-credential:" + user).upper() + "Aa1!"
    salt = generate_password_salt()
    session.execute(
        models.user_credentials.insert().values(
            user_id=user,
            password_salt=salt,
            password_hash=hash_password(secret, salt),
            password_algorithm=PASSWORD_ALGORITHM,
            updated_at=NOW,
        )
    )
    return secret


def test_employee_code_is_not_a_step_up_secret(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        session.execute(
            models.employee_code_registry.insert().values(
                organization_id=ORG_ID,
                employee_code="C108AA",
                subject_type="user",
                subject_id=world.actors["owner"],
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.users.update()
            .where(models.users.c.id == world.actors["owner"])
            .values(employee_code="C108AA")
        )
        secret = credential(session, world.actors["owner"])
        session.commit()
        with pytest.raises(ops.AuthorizationError, match="invalid"):
            ops.authorize_supervisor_step_up(
                session, "C108AA", BRANCH_A, supervisor_identity="C108AA"
            )
        assert (
            ops.authorize_supervisor_step_up(
                session, secret, BRANCH_A, supervisor_identity="C108AA"
            )["supervisor_user_id"]
            == world.actors["owner"]
        )


def test_secret_alone_does_not_inherit_admin_authority(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        secret = credential(session, world.actors["administrator"])
        session.commit()
        with pytest.raises(ops.AuthorizationError):
            ops.authorize_supervisor_step_up(
                session, secret, BRANCH_A, supervisor_identity=world.actors["administrator"]
            )
        grant_permission(session, world.roles["administrator"], "orders.discount.authorize")
        session.commit()
        result = ops.authorize_supervisor_step_up(
            session, secret, BRANCH_A, supervisor_identity=world.actors["administrator"]
        )
        assert result["supervisor_user_id"] == world.actors["administrator"]


def test_reviewed_owner_uses_own_secret(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        secret = credential(session, world.actors["owner"])
        session.commit()
        result = ops.authorize_supervisor_step_up(
            session, secret, BRANCH_A, supervisor_identity=world.actors["owner"]
        )
        assert result["supervisor_user_id"] == world.actors["owner"]


def test_identical_secrets_never_select_another_identity(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        secret = credential(session, world.actors["owner"])
        credential(session, world.actors["cashier"], secret)
        session.commit()
        with pytest.raises(ops.AuthorizationError):
            ops.authorize_supervisor_step_up(session, secret, BRANCH_A)
        with pytest.raises(ops.AuthorizationError):
            ops.authorize_supervisor_step_up(
                session, secret, BRANCH_A, supervisor_identity=world.actors["cashier"]
            )
        result = ops.authorize_supervisor_step_up(
            session, secret, BRANCH_A, supervisor_identity=world.actors["owner"]
        )
        assert result["supervisor_user_id"] == world.actors["owner"]
        records = list(session.execute(sa.select(models.audit_events)).mappings())
        assert secret not in str(records)
