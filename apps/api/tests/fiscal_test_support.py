# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-audit-fiscal-test-support-v1
"""Explicit synthetic issuer setup; never uses implicit provider mock mode."""

import base64

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.config import get_settings
from restaurant_os.invoicing import emitters


def encryption_environment(monkeypatch):
    monkeypatch.setenv(
        "RESTAURANTOS_FISCAL_ENCRYPTION_KEYS",
        '{"qa":"' + base64.b64encode(bytes(range(32))).decode() + '"}',
    )
    monkeypatch.setenv("RESTAURANTOS_FISCAL_ACTIVE_ENCRYPTION_KEY_ID", "qa")
    get_settings.cache_clear()


def configuration_payload(**changes):
    return {
        "expected_version": 0,
        "is_enabled": True,
        "environment": "sandbox",
        "api_key": "sk_test_synthetic_explicit_fixture",
        "organization_legal_name": "RESTAURANTE KIWI SA DE CV",
        "organization_rfc": "KIW210101ABC",
        "organization_tax_system": "601",
        "organization_zip": "80000",
        "default_product_sat_key": "90101501",
        "default_unit_sat_key": "E48",
        "series": "F",
        "enable_self_invoicing": True,
        "self_invoicing_domain": "kiwirest",
        "self_invoicing_days_valid": 7,
        "print_qr_on_ticket": True,
        **changes,
    }


def configure_issuer(session, actor, branch, **changes):
    emitter = session.scalar(
        sa.select(models.branches.c.legal_entity_id).where(models.branches.c.id == branch)
    )
    session.execute(
        models.legal_entities.update()
        .where(models.legal_entities.c.id == emitter)
        .values(tax_id="KIW210101ABC")
    )
    session.commit()
    return emitters.save_configuration(session, actor, emitter, configuration_payload(**changes))
