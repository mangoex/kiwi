"""Current human authority; consumers must materialize inside this transaction.

F1-04 primitive, deliberately not installed over legacy financial handlers yet.
No roles by name, permission aliases, cached grants, or organizational wildcard.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Sequence
from typing import TypeVar

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.financial_access_schema import CAPABILITIES, DATASETS
from restaurant_os.order_exception_schema import CAPABILITY as ORDER_EXCEPTION_CAPABILITY

T = TypeVar("T")
Pair = tuple[str, str]


def authorize_capability_assignment(
    session: Session,
    actor: str,
    permission_ids: Iterable[str],
    organization_id: str,
) -> None:
    """Ordinary admin.manage must not bootstrap new reviewed capabilities."""
    ids = list(permission_ids)
    protected = set(CAPABILITIES) | {ORDER_EXCEPTION_CAPABILITY}
    count_review = session.scalar(
        sa.select(models.permissions.c.id)
        .where(
            models.permissions.c.id.in_(ids),
            models.permissions.c.code.in_(
                ("inventory.count.review", "inventory.count.approve", "orders.discount.authorize")
            ),
        )
        .limit(1)
    )
    if count_review is not None and authority_tables_available(session):
        policy = models.blind_cash_policy_revisions
        # Privacy/assignment safeguards survive suspension; no return to broad roles.
        active = session.scalar(
            sa.select(policy.c.branch_id)
            .where(policy.c.organization_id == organization_id, policy.c.event == "activated")
            .limit(1)
        )
        if active is not None:
            protected.update(
                ("inventory.count.review", "inventory.count.approve", "orders.discount.authorize")
            )
    sensitive = session.scalar(
        sa.select(models.permissions.c.id)
        .where(
            models.permissions.c.id.in_(ids),
            models.permissions.c.code.in_(protected),
        )
        .limit(1)
    )
    if sensitive is not None:
        FinancialAuthority(session, actor, organization_id).require_capability(
            "financial.delegations.manage",
            None,
        )


def authorize_role_assignment(session: Session, actor: str, role_id: str) -> None:
    organization = session.scalar(
        sa.select(models.roles.c.organization_id).where(
            models.roles.c.id == role_id,
        )
    )
    permissions: Sequence[str] = session.scalars(
        sa.select(models.role_permissions.c.permission_id).where(
            models.role_permissions.c.role_id == role_id,
        )
    ).all()
    authorize_capability_assignment(session, actor, permissions, str(organization))


OWNER_DEFAULTS = frozenset(
    {
        ORDER_EXCEPTION_CAPABILITY,
        "financial.data.read",
        "financial.delegations.manage",
        "cash.user_cut.finalize",
        "cash.user_cut.operational.read",
        "reports.operational.read",
        "cash.shift.read",
        "cash.shift.open",
        "cash.shift.close",
        "cash.user_cut.reopen.request",
        "cash.user_cut.reopen.authorize",
        "purchases.receive",
        "purchases.prices.read",
        "inventory.costs.read",
        "inventory.count.capture",
        "inventory.count.review",
        "inventory.count.approve",
        "orders.discount.authorize",
    }
)
CAPABILITY_CODES = frozenset(CAPABILITIES) | OWNER_DEFAULTS | {"cash.user_cut.capture"}


OWNER_ONLY_CAPABILITIES = frozenset(
    {
        "financial.delegations.manage",
        "cash.user_cut.reopen.request",
        "cash.user_cut.reopen.authorize",
    }
)


def deny() -> None:
    raise ops.AuthorizationError("financial_access_denied", "Requested access is not authorized")


def governance_lock(session: Session, organization_id: str, *, write: bool = False) -> None:
    """Share the exact lock namespace of all existing role/user governance writers."""
    if session.get_bind().dialect.name == "postgresql":
        isolation = session.scalar(sa.text("SHOW transaction_isolation"))
        if isolation != "read committed":
            raise ops.BusinessError(
                "cash_authorization_changed", "Use a fresh READ COMMITTED transaction"
            )
        if not write:
            session.execute(
                sa.text("SELECT pg_advisory_xact_lock_shared(hashtextextended(:key, 0))"),
                {"key": f"authority-governance:{ops.ORGANIZATION_ID}:{organization_id}"},
            )
            return
    ops._authority_governance_lock(session, organization_id)


class FinancialAuthority:
    """Short-lived policy facade, never a transferable authorization token.

    Every public require call re-reads actor and authority. No commit/rollback occurs
    here: callers retain the lock through their protected query/materialization.
    """

    def __init__(self, session: Session, actor: str, organization_id: str) -> None:
        self.session, self.actor, self.organization_id = session, actor, organization_id

    def _begin(self, expected_version: int | None = None) -> int:
        governance_lock(self.session, self.organization_id)
        row = (
            self.session.execute(
                sa.select(
                    models.users.c.authorization_version,
                    models.users.c.status,
                )
                .where(
                    models.users.c.id == self.actor,
                    models.users.c.organization_id == self.organization_id,
                )
                .with_for_update(read=True)
            )
            .mappings()
            .first()
        )
        if row is None or row["status"] != "active":
            deny()
        assert row is not None
        version = int(row["authorization_version"])
        if expected_version is not None and expected_version != version:
            raise ops.BusinessError("cash_authorization_changed", "Refresh current authority")
        return version

    def _owner(self, version: int) -> bool:
        reviewed = self.session.scalar(
            sa.select(models.financial_owner_reviews.c.user_id).where(
                models.financial_owner_reviews.c.organization_id == self.organization_id,
                models.financial_owner_reviews.c.user_id == self.actor,
                models.financial_owner_reviews.c.authorization_version == version,
            )
        )
        if reviewed is None:
            return False
        return (
            self.session.scalar(
                sa.select(models.user_roles.c.user_id)
                .select_from(
                    models.user_roles.join(models.roles).join(models.role_authority_grants)
                )
                .where(
                    models.user_roles.c.user_id == self.actor,
                    models.user_roles.c.branch_id.is_(None),
                    models.roles.c.organization_id == self.organization_id,
                    models.roles.c.scope == "organization",
                    models.role_authority_grants.c.authority_kind == "organization_all_permissions",
                )
                .limit(1)
            )
            is not None
        )

    def _branches(self, branches: Iterable[str]) -> None:
        requested = sorted(set(branches))
        rows: Sequence[str] = self.session.scalars(
            sa.select(models.branches.c.id)
            .where(
                models.branches.c.organization_id == self.organization_id,
                models.branches.c.id.in_(requested),
            )
            .order_by(models.branches.c.id)
            .with_for_update(read=True)
        ).all()
        if set(rows) != set(requested):
            deny()

    def _explicit(self, capability: str, branch_id: str | None) -> bool:
        organization_scope = sa.and_(
            models.roles.c.scope == "organization",
            models.user_roles.c.branch_id.is_(None),
        )
        scope = (
            organization_scope
            if branch_id is None
            else sa.or_(
                organization_scope,
                sa.and_(
                    models.roles.c.scope == "branch",
                    models.user_roles.c.branch_id == branch_id,
                ),
            )
        )
        return (
            self.session.scalar(
                sa.select(models.permissions.c.id)
                .select_from(
                    models.user_roles.join(models.roles)
                    .join(models.role_permissions)
                    .join(models.permissions)
                )
                .where(
                    models.user_roles.c.user_id == self.actor,
                    models.roles.c.organization_id == self.organization_id,
                    models.permissions.c.code == capability,
                    scope,
                )
                .limit(1)
            )
            is not None
        )

    def require_capability(
        self, capability: str, branch_id: str | None, *, expected_version: int | None = None
    ) -> int:
        version = self._begin(expected_version)
        if capability not in CAPABILITY_CODES or capability == "financial.data.read":
            # A bare financial bit can never authorize a dataset, including for Owner.
            deny()
        if branch_id is not None:
            self._branches([branch_id])
        owner = self._owner(version)
        if capability in OWNER_ONLY_CAPABILITIES and not owner:
            deny()
        if not ((owner and capability in OWNER_DEFAULTS) or self._explicit(capability, branch_id)):
            deny()
        return version

    def require_financial(
        self, pairs: Iterable[Pair], *, expected_version: int | None = None
    ) -> int:
        version = self._begin(expected_version)
        requested = set(pairs)
        if not requested or any(dataset not in DATASETS for _, dataset in requested):
            deny()
        self._branches(branch for branch, _ in requested)
        if self._owner(version):
            return version
        if any(not self._explicit("financial.data.read", branch) for branch, _ in requested):
            deny()
        grants, scopes, revoked = (
            models.financial_access_grants,
            models.financial_access_grant_scopes,
            models.financial_access_grant_revocations,
        )
        rows = self.session.execute(
            sa.select(scopes.c.branch_id, scopes.c.dataset)
            .select_from(
                grants.join(
                    scopes,
                    sa.and_(
                        grants.c.id == scopes.c.grant_id,
                        grants.c.organization_id == scopes.c.organization_id,
                    ),
                )
            )
            .where(
                grants.c.organization_id == self.organization_id,
                grants.c.subject_user_id == self.actor,
                ~sa.exists(sa.select(revoked.c.grant_id).where(revoked.c.grant_id == grants.c.id)),
            )
        ).all()
        if not requested.issubset({(str(row[0]), str(row[1])) for row in rows}):
            deny()
        return version

    def materialize(
        self, pairs: Iterable[Pair], read: Callable[[], T], *, expected_version: int | None = None
    ) -> T:
        self.require_financial(pairs, expected_version=expected_version)
        # Synchronous DB work only. The consumer must not commit/release locks in read.
        return read()

    def require_operational_report(self, branch_id: str) -> int:
        version = self._begin()
        self._branches([branch_id])
        if self._owner(version) or self._explicit("reports.operational.read", branch_id):
            return version
        return self.require_financial([(branch_id, "sales")])

    def describe_scopes(
        self, branches: Iterable[str], *, expected_version: int
    ) -> dict[str, tuple[dict[str, bool], list[str]]]:
        """Transaction-local session metadata, not a reusable authorization decision."""
        version = self._begin(expected_version)
        requested = sorted(set(branches))
        self._branches(requested)
        owner = self._owner(version)
        explicit_rows = self.session.execute(
            sa.select(
                models.permissions.c.code, models.roles.c.scope, models.user_roles.c.branch_id
            )
            .select_from(
                models.user_roles.join(models.roles)
                .join(models.role_permissions)
                .join(models.permissions)
            )
            .where(
                models.user_roles.c.user_id == self.actor,
                models.roles.c.organization_id == self.organization_id,
            )
        ).all()
        grants, scopes, revoked = (
            models.financial_access_grants,
            models.financial_access_grant_scopes,
            models.financial_access_grant_revocations,
        )
        granted = set(
            self.session.execute(
                sa.select(scopes.c.branch_id, scopes.c.dataset)
                .select_from(
                    grants.join(
                        scopes,
                        sa.and_(
                            grants.c.id == scopes.c.grant_id,
                            grants.c.organization_id == scopes.c.organization_id,
                        ),
                    )
                )
                .where(
                    grants.c.organization_id == self.organization_id,
                    grants.c.subject_user_id == self.actor,
                    scopes.c.branch_id.in_(requested),
                    ~sa.exists(
                        sa.select(revoked.c.grant_id).where(revoked.c.grant_id == grants.c.id)
                    ),
                )
            ).all()
        )
        result = {}
        for branch in requested:
            explicit = {
                str(row.code)
                for row in explicit_rows
                if (row.scope == "organization" and row.branch_id is None)
                or (row.scope == "branch" and row.branch_id == branch)
            }
            datasets = [
                dataset
                for dataset in sorted(DATASETS)
                if owner or ("financial.data.read" in explicit and (branch, dataset) in granted)
            ]
            capabilities = {
                code: ((owner and code in OWNER_DEFAULTS) or code in explicit)
                and (owner or code not in OWNER_ONLY_CAPABILITIES)
                for code in sorted(CAPABILITY_CODES - {"financial.data.read"})
            }
            capabilities["reports.operational.read"] = (
                owner or "reports.operational.read" in explicit or "sales" in datasets
            )
            result[branch] = (capabilities, datasets)
        return result

    def policy_revision(self, branch_id: str) -> int | None:
        self._begin()
        self._branches([branch_id])
        return protected_policy_revision(self.session, self.organization_id, branch_id)


_LEGACY_AUTHORITY_REVISIONS = frozenset(
    {
        "0077_pos_branch_selection",
        "0087_fiscal_commands",
        "0099_mobile_password_access",
        "0100_delivery_fee",
    }
)


def authority_tables_available(session: Session) -> bool:
    """Only known pre-0101 schemas or isolated legacy fixtures may omit authority tables."""
    cached = session.info.get("_cc_authority_tables")
    if isinstance(cached, bool):
        return cached
    inspector = sa.inspect(session.connection())
    from restaurant_os.financial_access_schema import tables

    names = [table.name for table in tables(sa.MetaData())]
    if all(inspector.has_table(name) for name in names):
        session.info["_cc_authority_tables"] = True
        return True
    if not any(inspector.has_table(name) for name in names):
        if not inspector.has_table("alembic_version"):
            session.info["_cc_authority_tables"] = False
            return False
        revisions: Sequence[str] = (
            session.execute(sa.text("SELECT version_num FROM alembic_version")).scalars().all()
        )
        if len(revisions) == 1 and revisions[0] in _LEGACY_AUTHORITY_REVISIONS:
            session.info["_cc_authority_tables"] = False
            return False
    raise ops.BusinessError(
        "financial_schema_incomplete", "Financial authority schema requires migration or repair"
    )


def protected_policy_revision(session: Session, organization: str, branch: str) -> int | None:
    """None means not activated; suspension must never enable a legacy fallback."""
    if not authority_tables_available(session):
        return None
    policy = models.blind_cash_policy_revisions
    row = session.execute(
        sa.select(policy.c.revision, policy.c.event)
        .where(policy.c.organization_id == organization, policy.c.branch_id == branch)
        .order_by(policy.c.revision.desc())
        .limit(1)
    ).first()
    if row is None:
        return None
    if (
        row.event == "prepared"
        and session.scalar(
            sa.select(policy.c.revision)
            .where(
                policy.c.organization_id == organization,
                policy.c.branch_id == branch,
                policy.c.event.in_(("activated", "suspended")),
            )
            .limit(1)
        )
        is None
    ):
        return None
    if row.event != "activated":
        raise ops.BusinessError("cash_policy_suspended", "Cash policy is suspended")
    return int(row.revision)
