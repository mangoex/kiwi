import pytest
import sqlalchemy as sa
from restaurant_os import delivery_fee, delivery_fee_fiscal
from restaurant_os.operations import BusinessError
from sqlalchemy.orm import Session


def legacy_database(revision: str):
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            sa.text("CREATE TABLE alembic_version (version_num VARCHAR(128) NOT NULL)")
        )
        connection.execute(
            sa.text("INSERT INTO alembic_version VALUES (:revision)"), {"revision": revision}
        )
    return engine


@pytest.mark.parametrize(
    "revision", ["0077_pos_branch_selection", "0087_fiscal_commands", "0099_mobile_password_access"]
)
def test_pre_fee_schema_reads_remain_explicitly_legacy(revision) -> None:
    engine = legacy_database(revision)
    with Session(engine) as session:
        assert delivery_fee.current_policy(session, "branch") is None
        assert delivery_fee.order_charge(session, "order") is None
        assert delivery_fee_fiscal.payment_charge(session, "order") is None
        delivery_fee_fiscal.reject_aggregate_receipt(session, ["order"])
    engine.dispose()


@pytest.mark.parametrize("revision", ["0100_delivery_fee", "9999_future", "unrecognized"])
def test_missing_fee_tables_in_current_or_unknown_schema_fail_closed(revision) -> None:
    engine = legacy_database(revision)
    with Session(engine) as session:
        with pytest.raises(BusinessError) as blocked:
            delivery_fee.current_policy(session, "branch")
        assert blocked.value.code == "delivery_schema_incomplete"
    engine.dispose()


def test_partially_missing_fee_schema_is_never_treated_as_legacy() -> None:
    engine = legacy_database("0099_mobile_password_access")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE delivery_tariffs (id VARCHAR(36))"))
    with Session(engine) as session:
        with pytest.raises(BusinessError) as blocked:
            delivery_fee_fiscal.payment_charge(session, "order")
        assert blocked.value.code == "delivery_schema_incomplete"
    engine.dispose()
