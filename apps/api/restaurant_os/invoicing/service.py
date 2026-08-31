"""Facturapi & CFDI 4.0 Invoicing Domain Service."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
from typing import Any
import uuid
import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from .facturapi_client import FacturapiClient

logger = logging.getLogger(__name__)


class InvoicingService:
    """Orchestrator for Mexican electronic invoicing CFDI 4.0 via Facturapi."""

    def get_client(self, session: Session, organization_id: str) -> FacturapiClient:
        config = self.get_config(session, organization_id)
        api_key = config.get("api_key") if config else None
        is_mock = not api_key or (config.get("environment") == "sandbox" and "mock" in str(api_key))
        return FacturapiClient(api_key=api_key, is_mock=is_mock)

    def get_config(self, session: Session, organization_id: str) -> dict[str, Any] | None:
        row = session.execute(
            sa.select(models.facturapi_config).where(
                models.facturapi_config.c.organization_id == organization_id
            )
        ).mappings().first()
        return dict(row) if row else None

    def save_config(
        self, session: Session, organization_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        existing = self.get_config(session, organization_id)

        clean_data = {
            "is_enabled": bool(payload.get("is_enabled", False)),
            "environment": payload.get("environment") or "sandbox",
            "api_key": payload.get("api_key") or None,
            "organization_legal_name": payload.get("organization_legal_name") or "RESTAURANTE KIWI SA DE CV",
            "organization_rfc": (payload.get("organization_rfc") or "KIW210101ABC").upper().strip(),
            "organization_tax_system": payload.get("organization_tax_system") or "601",
            "organization_zip": payload.get("organization_zip") or "80000",
            "default_product_sat_key": payload.get("default_product_sat_key") or "90101501",
            "default_unit_sat_key": payload.get("default_unit_sat_key") or "E48",
            "series": (payload.get("series") or "F").upper().strip(),
            "enable_self_invoicing": bool(payload.get("enable_self_invoicing", True)),
            "self_invoicing_domain": payload.get("self_invoicing_domain") or "demo",
            "self_invoicing_days_valid": int(payload.get("self_invoicing_days_valid") or 30),
            "print_qr_on_ticket": bool(payload.get("print_qr_on_ticket", True)),
            "updated_at": now,
        }

        if existing:
            session.execute(
                models.facturapi_config.update()
                .where(models.facturapi_config.c.organization_id == organization_id)
                .values(clean_data)
            )
        else:
            config_id = str(uuid.uuid4())
            values_to_insert = dict(clean_data)
            values_to_insert["id"] = config_id
            values_to_insert["organization_id"] = organization_id
            values_to_insert["created_at"] = now
            session.execute(models.facturapi_config.insert().values(values_to_insert))

        session.commit()
        return self.get_config(session, organization_id) or {}

    def test_connection(self, session: Session, organization_id: str) -> dict[str, Any]:
        client = self.get_client(session, organization_id)
        return client.validate_api_key()

    def create_receipt_for_order(
        self, session: Session, organization_id: str, branch_id: str, order_id: str
    ) -> dict[str, Any]:
        """Generates an E-Receipt for an order so the customer can self-invoice."""
        config = self.get_config(session, organization_id)
        if not config or not config.get("is_enabled"):
            raise ValueError("La facturación electrónica no está habilitada en la configuración.")

        order_row = session.execute(
            sa.select(models.orders).where(
                models.orders.c.organization_id == organization_id,
                models.orders.c.id == order_id,
            )
        ).mappings().first()

        if not order_row:
            raise ValueError(f"Orden con ID {order_id} no encontrada.")

        # Payment form mapping
        pm = order_row.get("payment_method_intent") or "cash"
        payment_form_map = {
            "cash": "01",
            "card_debit": "28",
            "card_credit": "04",
            "transfer": "03",
            "marketplace_uber": "31",
        }
        sat_payment_form = payment_form_map.get(pm, "01")

        # Total in currency units
        total_amount = float(order_row["total_cents"]) / 100.0

        receipt_payload = {
            "payment_form": sat_payment_form,
            "items": [
                {
                    "quantity": 1,
                    "product": {
                        "description": f"Consumo en restaurante Folio {order_row['folio']}",
                        "product_key": config.get("default_product_sat_key") or "90101501",
                        "unit_key": config.get("default_unit_sat_key") or "E48",
                        "price": total_amount,
                        "taxes": [{"type": "IVA", "rate": 0.16}],
                    },
                }
            ],
        }

        client = self.get_client(session, organization_id)
        res = client.create_receipt(receipt_payload)

        receipt_id = res.get("id")
        self_invoice_url = res.get("self_invoice_url") or f"https://factura.space/{config.get('self_invoice_domain') or 'demo'}/receipt/{receipt_id}"

        return {
            "receipt_id": receipt_id,
            "order_id": order_id,
            "self_invoice_url": self_invoice_url,
            "key": res.get("key"),
            "status": "open",
        }

    def issue_invoice(
        self,
        session: Session,
        org_id: str,
        branch_id: str,
        order_ids: list[str],
        receptor: dict[str, Any],
    ) -> dict[str, Any]:
        """Directly issues a CFDI 4.0 for one or multiple orders."""
        config = self.get_config(session, org_id) or {}
        client = self.get_client(session, org_id)

        # Query orders
        orders_rows = session.execute(
            sa.select(models.orders).where(
                models.orders.c.organization_id == org_id,
                models.orders.c.id.in_(order_ids),
            )
        ).mappings().all()

        if not orders_rows:
            raise ValueError("No se encontraron pedidos válidos para facturar.")

        total_cents = sum(o["total_cents"] for o in orders_rows)
        total_amount = float(total_cents) / 100.0

        rfc_receptor = receptor.get("rfc", "XAXX010101000").upper().strip()
        legal_name = receptor.get("legal_name", "PUBLICO EN GENERAL").upper().strip()
        zip_code = str(receptor.get("zip", "80000")).strip()
        tax_system = str(receptor.get("tax_system", "616")).strip()
        use = str(receptor.get("use", "S01")).upper().strip()
        payment_form = str(receptor.get("payment_form", "01")).strip()
        payment_method = str(receptor.get("payment_method", "PUE")).upper().strip()

        customer_obj = {
            "legal_name": legal_name,
            "tax_id": rfc_receptor,
            "tax_system": tax_system,
            "address": {"zip": zip_code},
        }
        if receptor.get("email"):
            customer_obj["email"] = receptor["email"]

        folios_str = ", ".join(o["folio"] for o in orders_rows)
        invoice_payload = {
            "customer": customer_obj,
            "payment_form": payment_form,
            "payment_method": payment_method,
            "use": use,
            "series": config.get("series") or "F",
            "items": [
                {
                    "quantity": 1,
                    "product": {
                        "description": f"Consumo de alimentos y bebidas (Folios: {folios_str})",
                        "product_key": config.get("default_product_sat_key") or "90101501",
                        "unit_key": config.get("default_unit_sat_key") or "E48",
                        "price": total_amount,
                        "taxes": [{"type": "IVA", "rate": 0.16}],
                    },
                }
            ],
        }

        res = client.create_invoice(invoice_payload)

        invoice_db_id = str(uuid.uuid4())
        facturapi_inv_id = res.get("id") or str(uuid.uuid4())
        uuid_sat = res.get("uuid") or str(uuid.uuid4()).upper()
        folio_num = f"{config.get('series') or 'F'}-{res.get('folio_number') or uuid.uuid4().hex[:4].upper()}"
        now = datetime.now(timezone.utc)

        pdf_url = f"https://www.facturapi.io/v2/invoices/{facturapi_inv_id}/pdf"
        xml_url = f"https://www.facturapi.io/v2/invoices/{facturapi_inv_id}/xml"
        verification_url = res.get("verification_url") or f"https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?id={uuid_sat}"

        primary_order_id = orders_rows[0]["id"] if len(orders_rows) == 1 else None

        session.execute(
            models.cfdi_invoices.insert().values(
                id=invoice_db_id,
                organization_id=org_id,
                branch_id=branch_id,
                order_id=primary_order_id,
                facturapi_invoice_id=facturapi_inv_id,
                facturapi_receipt_id=None,
                uuid_sat=uuid_sat,
                folio_number=folio_num,
                rfc_emisor=config.get("organization_rfc") or "KIW210101ABC",
                rfc_receptor=rfc_receptor,
                nombre_receptor=legal_name,
                codigo_postal_receptor=zip_code,
                regimen_fiscal_receptor=tax_system,
                uso_cfdi=use,
                forma_pago_sat=payment_form,
                metodo_pago_sat=payment_method,
                total_cents=total_cents,
                currency="MXN",
                status="issued",
                verification_url=verification_url,
                self_invoice_url=None,
                pdf_url=pdf_url,
                xml_url=xml_url,
                cancellation_reason=None,
                raw_sat_response=res,
                created_at=now,
                cancelled_at=None,
            )
        )
        session.commit()

        # If email provided, send it
        if receptor.get("email"):
            try:
                client.send_email(facturapi_inv_id, receptor["email"])
            except Exception as e:
                logger.warning("No se pudo enviar factura por correo: %s", e)

        return self.get_invoice_detail(session, org_id, invoice_db_id) or {}

    def list_invoices(
        self,
        session: Session,
        org_id: str,
        branch_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        query = sa.select(models.cfdi_invoices).where(
            models.cfdi_invoices.c.organization_id == org_id
        )
        if branch_id:
            query = query.where(models.cfdi_invoices.c.branch_id == branch_id)
        if status:
            query = query.where(models.cfdi_invoices.c.status == status)

        query = query.order_by(models.cfdi_invoices.c.created_at.desc()).limit(limit).offset(offset)
        rows = session.execute(query).mappings().all()
        return [dict(r) for r in rows]

    def get_invoice_detail(
        self, session: Session, org_id: str, invoice_id: str
    ) -> dict[str, Any] | None:
        row = session.execute(
            sa.select(models.cfdi_invoices).where(
                models.cfdi_invoices.c.organization_id == org_id,
                models.cfdi_invoices.c.id == invoice_id,
            )
        ).mappings().first()
        return dict(row) if row else None

    def cancel_invoice(
        self,
        session: Session,
        org_id: str,
        invoice_id: str,
        motive: str = "02",
        substitution_uuid: str | None = None,
    ) -> dict[str, Any]:
        inv = self.get_invoice_detail(session, org_id, invoice_id)
        if not inv:
            raise ValueError(f"Factura con ID {invoice_id} no encontrada.")

        client = self.get_client(session, org_id)
        if inv.get("facturapi_invoice_id"):
            client.cancel_invoice(inv["facturapi_invoice_id"], motive, substitution_uuid)

        now = datetime.now(timezone.utc)
        session.execute(
            models.cfdi_invoices.update()
            .where(
                models.cfdi_invoices.c.organization_id == org_id,
                models.cfdi_invoices.c.id == invoice_id,
            )
            .values(
                status="cancelled",
                cancellation_reason=motive,
                cancelled_at=now,
            )
        )
        session.commit()
        return self.get_invoice_detail(session, org_id, invoice_id) or {}
