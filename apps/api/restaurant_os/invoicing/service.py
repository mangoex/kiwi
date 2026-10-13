"""Facturapi & CFDI 4.0 Invoicing Domain Service."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    BusinessError,
    NotFoundError,
    _audit,
    _authority_governance_lock,
    require_permission,
)

from .authority import (
    authorized_read_branches,
    public_config,
    public_invoice,
    require_branch_permission,
    require_configuration_permission,
)
from .documents import document_available
from .eligibility import payment_snapshot
from .emitters import (
    client_for_configuration,
    configuration_for_branch,
    configuration_for_document,
)
from .facturapi_client import FacturapiClient

logger = logging.getLogger(__name__)


class InvoicingService:
    """Orchestrator for Mexican electronic invoicing CFDI 4.0 via Facturapi."""

    def get_client(
        self, session: Session, organization_id: str, configuration: dict[str, Any] | None = None
    ) -> FacturapiClient:
        if configuration is not None:
            return client_for_configuration(configuration)
        config = self.get_config(session, organization_id)
        api_key = config.get("api_key") if config else None
        return client_for_configuration({"api_key": api_key})

    def get_config(self, session: Session, organization_id: str) -> dict[str, Any] | None:
        row = (
            session.execute(
                sa.select(models.facturapi_config).where(
                    models.facturapi_config.c.organization_id == organization_id
                )
            )
            .mappings()
            .first()
        )
        return dict(row) if row else None

    def save_config(
        self,
        session: Session,
        organization_id: str,
        payload: dict[str, Any],
        *,
        actor_user_id: str | None = None,
    ) -> dict[str, Any]:
        require_configuration_permission(session, actor_user_id, lock_for_write=True)
        if organization_id != ORGANIZATION_ID:
            raise BusinessError("fiscal_organization_invalid", "Fiscal organization is invalid")
        now = datetime.now(timezone.utc)
        existing = self.get_config(session, organization_id)
        if set(payload) != {"is_enabled"} or payload["is_enabled"] is not False:
            raise BusinessError(
                "fiscal_emitter_configuration_required", "Configure an explicit legal issuer"
            )
        if existing is None:
            raise NotFoundError("fiscal_configuration_not_found", "Legacy configuration not found")
        clean_data = {
            "is_enabled": False,
            "updated_at": now,
        }

        try:
            config_id = str(existing["id"])
            session.execute(
                models.facturapi_config.update()
                .where(models.facturapi_config.c.organization_id == organization_id)
                .values(clean_data)
            )

            _audit(
                session,
                action="invoicing.config.updated",
                entity_type="fiscal_configuration",
                entity_id=config_id,
                branch_id=None,
                actor_user_id=actor_user_id,
                payload={
                    "is_enabled": clean_data["is_enabled"],
                    "environment": existing["environment"],
                    "credential_replaced": False,
                },
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        return public_config(self.get_config(session, organization_id))

    def test_connection(
        self,
        session: Session,
        organization_id: str,
        *,
        actor_user_id: str | None = None,
    ) -> dict[str, Any]:
        require_configuration_permission(session, actor_user_id)
        if organization_id != ORGANIZATION_ID:
            raise BusinessError("fiscal_organization_invalid", "Fiscal organization is invalid")
        raise BusinessError(
            "fiscal_emitter_configuration_required", "Select an explicit legal issuer"
        )

    def create_receipt_for_order(
        self,
        session: Session,
        organization_id: str,
        branch_id: str | None,
        order_id: str,
        *,
        actor_user_id: str | None = None,
        branch_context: str | None = None,
    ) -> dict[str, Any]:
        """Generates an E-Receipt for an order so the customer can self-invoice."""
        order_row = (
            session.execute(
                sa.select(models.orders).where(
                    models.orders.c.organization_id == organization_id,
                    models.orders.c.id == order_id,
                )
            )
            .mappings()
            .first()
        )

        if not order_row:
            require_permission(session, actor_user_id or "", "invoicing.receipt.create", None)
            raise NotFoundError("fiscal_order_not_found", "Order not found")
        require_branch_permission(
            session,
            actor_user_id,
            organization_id,
            order_row["branch_id"],
            "invoicing.receipt.create",
            branch_context,
        )
        if branch_id is not None and branch_id != order_row["branch_id"]:
            raise BusinessError("fiscal_branch_mismatch", "Declared branch does not match order")
        payment = payment_snapshot(session, organization_id, order_row["branch_id"], order_id)
        config = configuration_for_branch(session, organization_id, str(order_row["branch_id"]))

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
        total_amount = float(payment.total_cents) / 100.0

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

        client = self.get_client(session, organization_id, config)
        res = client.create_receipt(receipt_payload)

        receipt_id = res.get("id")
        subdomain = config.get("self_invoice_domain") or "demo"
        self_invoice_url = (
            res.get("self_invoice_url") or f"https://factura.space/{subdomain}/receipt/{receipt_id}"
        )

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
        branch_id: str | None,
        order_ids: Any,
        receptor: Any,
        *,
        actor_user_id: str | None = None,
        branch_context: str | None = None,
    ) -> dict[str, Any]:
        """Directly issues a CFDI 4.0 for one or multiple orders."""
        require_permission(session, actor_user_id or "", "invoicing.issue", None)
        if (
            not isinstance(order_ids, list)
            or not order_ids
            or any(not isinstance(value, str) or not value for value in order_ids)
            or len(set(order_ids)) != len(order_ids)
        ):
            raise BusinessError("fiscal_order_set_invalid", "Unique order IDs are required")

        # Query orders
        orders_rows = (
            session.execute(
                sa.select(models.orders).where(
                    models.orders.c.organization_id == org_id,
                    models.orders.c.id.in_(order_ids),
                )
            )
            .mappings()
            .all()
        )

        if {str(row["id"]) for row in orders_rows} != set(order_ids):
            raise BusinessError("fiscal_order_set_invalid", "All selected orders must exist")
        for order in orders_rows:
            require_branch_permission(
                session,
                actor_user_id,
                org_id,
                order["branch_id"],
                "invoicing.issue",
                branch_context,
            )
        branches = {str(row["branch_id"]) for row in orders_rows}
        if len(branches) != 1 or (branch_id is not None and branches != {branch_id}):
            raise BusinessError("fiscal_branch_mismatch", "Selected orders must share the branch")
        branch_id = str(orders_rows[0]["branch_id"])
        if len({row["currency"] for row in orders_rows}) != 1:
            raise BusinessError("fiscal_currency_mismatch", "Selected orders must share currency")
        if not isinstance(receptor, dict) or any(
            key in receptor and not isinstance(receptor[key], str)
            for key in (
                "rfc",
                "legal_name",
                "zip",
                "tax_system",
                "use",
                "payment_form",
                "payment_method",
                "email",
            )
        ):
            raise BusinessError(
                "fiscal_receiver_invalid", "Fiscal receiver must be an object with text fields"
            )
        config = configuration_for_branch(session, org_id, branch_id)
        payments = [
            payment_snapshot(session, org_id, branch_id, str(order["id"]))
            for order in sorted(orders_rows, key=lambda value: str(value["id"]))
        ]
        client = self.get_client(session, org_id, config)

        total_cents = sum(payment.total_cents for payment in payments)
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
        series = config.get("series") or "F"
        folio_part = res.get("folio_number") or uuid.uuid4().hex[:4].upper()
        folio_num = f"{series}-{folio_part}"
        now = datetime.now(timezone.utc)

        pdf_url = f"https://www.facturapi.io/v2/invoices/{facturapi_inv_id}/pdf"
        xml_url = f"https://www.facturapi.io/v2/invoices/{facturapi_inv_id}/xml"
        verification_url = (
            res.get("verification_url")
            or f"https://verificacfdi.facturaelectronica.sat.gob.mx/default.aspx?id={uuid_sat}"
        )

        primary_order_id = orders_rows[0]["id"] if len(orders_rows) == 1 else None

        session.execute(
            models.cfdi_invoices.insert().values(
                id=invoice_db_id,
                organization_id=org_id,
                branch_id=branch_id,
                emitter_configuration_id=config["id"],
                emitter_configuration_version=config["version"],
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

        return (
            self.get_invoice_detail(
                session,
                org_id,
                invoice_db_id,
                actor_user_id=actor_user_id,
                permission="invoicing.issue",
                branch_context=branch_context,
            )
            or {}
        )

    def list_invoices(
        self,
        session: Session,
        org_id: str,
        branch_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
        *,
        actor_user_id: str | None = None,
        branch_context: str | None = None,
    ) -> list[dict[str, Any]]:
        query = sa.select(models.cfdi_invoices).where(
            models.cfdi_invoices.c.organization_id == org_id
        )
        allowed = authorized_read_branches(
            session, actor_user_id, org_id, branch_id, branch_context
        )
        query = query.where(models.cfdi_invoices.c.branch_id.in_(allowed))
        if status:
            query = query.where(models.cfdi_invoices.c.status == status)

        query = query.order_by(models.cfdi_invoices.c.created_at.desc()).limit(limit).offset(offset)
        rows = session.execute(query).mappings().all()
        return [public_invoice(dict(r)) for r in rows]

    def get_invoice_detail(
        self,
        session: Session,
        org_id: str,
        invoice_id: str,
        *,
        actor_user_id: str | None = None,
        permission: str = "invoicing.read",
        branch_context: str | None = None,
    ) -> dict[str, Any] | None:
        invoice = self._authorized_invoice(
            session,
            org_id,
            invoice_id,
            actor_user_id=actor_user_id,
            permission=permission,
            branch_context=branch_context,
        )
        return public_invoice(invoice) if invoice else None

    def _authorized_invoice(
        self,
        session: Session,
        org_id: str,
        invoice_id: str,
        *,
        actor_user_id: str | None = None,
        permission: str = "invoicing.read",
        branch_context: str | None = None,
    ) -> dict[str, Any] | None:
        row = (
            session.execute(
                sa.select(models.cfdi_invoices).where(
                    models.cfdi_invoices.c.organization_id == org_id,
                    models.cfdi_invoices.c.id == invoice_id,
                )
            )
            .mappings()
            .first()
        )
        if not row:
            require_permission(session, actor_user_id or "", permission, None)
            return None
        require_branch_permission(
            session, actor_user_id, org_id, row["branch_id"], permission, branch_context
        )
        return dict(row)

    def download_invoice(
        self,
        session: Session,
        org_id: str,
        invoice_id: str,
        format: str,
        *,
        actor_user_id: str | None = None,
        branch_context: str | None = None,
    ) -> bytes:
        invoice = self._authorized_invoice(
            session,
            org_id,
            invoice_id,
            actor_user_id=actor_user_id,
            branch_context=branch_context,
        )
        if invoice is None:
            raise NotFoundError("fiscal_invoice_not_found", "Fiscal invoice not found")
        if format not in {"pdf", "xml"} or not document_available(invoice):
            raise BusinessError(
                "fiscal_document_not_available", "Confirmed fiscal document required"
            )
        remote_id = str(invoice["facturapi_invoice_id"])
        configuration = configuration_for_document(session, org_id, invoice)
        if configuration is None:
            legacy = self.get_config(session, org_id)
            if not legacy or legacy.get("organization_rfc") != invoice.get("rfc_emisor"):
                raise BusinessError(
                    "fiscal_document_origin_invalid", "Historical fiscal issuer is not known"
                )
        client = (
            self.get_client(session, org_id, configuration)
            if configuration is not None
            else self.get_client(session, org_id)
        )
        # Authorization is checked again after transport; no DB fence survives network I/O.
        session.rollback()
        content = client.download_invoice(remote_id, format)
        try:
            # Match the canonical revocation lock order, only after releasing network I/O.
            _authority_governance_lock(session)
            session.execute(
                sa.select(models.users.c.id)
                .where(
                    models.users.c.organization_id == org_id,
                    models.users.c.id == actor_user_id,
                )
                .with_for_update()
            ).scalar_one_or_none()
            session.execute(
                sa.select(models.cfdi_invoices.c.id)
                .where(
                    models.cfdi_invoices.c.organization_id == org_id,
                    models.cfdi_invoices.c.id == invoice_id,
                )
                .with_for_update()
            ).scalar_one_or_none()
            current = self._authorized_invoice(
                session,
                org_id,
                invoice_id,
                actor_user_id=actor_user_id,
                branch_context=branch_context,
            )
            if (
                current is None
                or not document_available(current)
                or current["facturapi_invoice_id"] != remote_id
                or current["branch_id"] != invoice["branch_id"]
                or current["uuid_sat"] != invoice["uuid_sat"]
                or current.get("emitter_configuration_id")
                != invoice.get("emitter_configuration_id")
                or current.get("emitter_configuration_version")
                != invoice.get("emitter_configuration_version")
            ):
                raise BusinessError("fiscal_document_not_available", "Fiscal document changed")
            _audit(
                session,
                action="invoicing.document.downloaded",
                entity_type="cfdi_invoice",
                entity_id=invoice_id,
                branch_id=str(current["branch_id"]),
                actor_user_id=actor_user_id,
                payload={"format": format},
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
        return content

    def cancel_invoice(
        self,
        session: Session,
        org_id: str,
        invoice_id: str,
        motive: str = "02",
        substitution_uuid: str | None = None,
        *,
        actor_user_id: str | None = None,
        branch_context: str | None = None,
    ) -> dict[str, Any]:
        inv = self.get_invoice_detail(
            session,
            org_id,
            invoice_id,
            actor_user_id=actor_user_id,
            permission="invoicing.cancel",
            branch_context=branch_context,
        )
        if not inv:
            raise NotFoundError("fiscal_invoice_not_found", "Invoice not found")

        configuration = configuration_for_document(session, org_id, inv)
        if configuration is None:
            raise BusinessError(
                "fiscal_document_origin_invalid", "Cancellation requires explicit fiscal origin"
            )
        client = self.get_client(session, org_id, configuration)
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
        return (
            self.get_invoice_detail(
                session,
                org_id,
                invoice_id,
                actor_user_id=actor_user_id,
                permission="invoicing.cancel",
                branch_context=branch_context,
            )
            or {}
        )
