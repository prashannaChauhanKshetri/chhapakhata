"""Role-based access control: the single source of truth for who can do what.

The matrix mirrors section 3.1 of the client proposal. Views declare the
permission each action needs through a ``required_perms`` attribute::

    class OrderViewSet(ModelViewSet):
        required_perms = {
            "list": Perm.ORDERS_VIEW,
            "create": Perm.ORDERS_MANAGE,
            "*": Perm.ORDERS_VIEW,       # fallback for any other action
        }

A view without ``required_perms`` (or an action without a mapping and no
``"*"`` fallback) is denied. That keeps new endpoints closed until someone
consciously opens them.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from django.conf import settings
from django.db import models
from rest_framework.permissions import BasePermission


class Role(models.TextChoices):
    OWNER = "owner", "Owner (Admin)"
    FRONT_DESK = "front_desk", "Front desk / Sales"
    OPERATOR = "operator", "Production operator"


class Perm:
    """Permission identifiers. Keep in sync with frontend/src/lib/permissions.ts."""

    CATALOG_VIEW = "catalog.view"
    CATALOG_MANAGE = "catalog.manage"
    CUSTOMERS_VIEW = "customers.view"
    CUSTOMERS_MANAGE = "customers.manage"
    ORDERS_VIEW = "orders.view"
    ORDERS_MANAGE = "orders.manage"
    DOCUMENTS_ISSUE = "documents.issue"
    INVOICES_VIEW = "invoices.view"
    INVOICES_CANCEL = "invoices.cancel"
    PAYMENTS_VIEW = "payments.view"
    PAYMENTS_RECEIVE = "payments.receive"
    PAYMENTS_VOID = "payments.void"
    LEDGER_VIEW = "ledger.view"
    LEDGER_MANAGE = "ledger.manage"
    PRODUCTION_VIEW = "production.view"
    PRODUCTION_MOVE = "production.move"
    INVENTORY_VIEW = "inventory.view"
    INVENTORY_RECORD_USAGE = "inventory.record_usage"
    INVENTORY_MANAGE = "inventory.manage"
    REPORTS_ALL = "reports.all"
    REPORTS_DAILY_SALES = "reports.daily_sales"
    REPORTS_OWN_PRODUCTION = "reports.own_production"
    DASHBOARD_SALES = "dashboard.sales"
    USERS_MANAGE = "users.manage"
    SETTINGS_MANAGE = "settings.manage"
    AUDIT_VIEW = "audit.view"
    SYSTEM_BACKUP = "system.backup"

    @classmethod
    def all(cls) -> frozenset[str]:
        return frozenset(
            value for key, value in vars(cls).items() if key.isupper() and isinstance(value, str)
        )


#: Marker meaning "any signed-in user".
AUTHENTICATED: tuple[str, ...] = ()

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    Role.OWNER: Perm.all(),
    Role.FRONT_DESK: frozenset(
        {
            Perm.CATALOG_VIEW,
            Perm.CUSTOMERS_VIEW,
            Perm.CUSTOMERS_MANAGE,
            Perm.ORDERS_VIEW,
            Perm.ORDERS_MANAGE,
            Perm.DOCUMENTS_ISSUE,
            Perm.INVOICES_VIEW,
            Perm.PAYMENTS_VIEW,
            Perm.PAYMENTS_RECEIVE,
            Perm.LEDGER_VIEW,
            Perm.PRODUCTION_VIEW,
            Perm.PRODUCTION_MOVE,
            Perm.INVENTORY_VIEW,
            Perm.REPORTS_DAILY_SALES,
            Perm.DASHBOARD_SALES,
        }
    ),
    Role.OPERATOR: frozenset(
        {
            Perm.PRODUCTION_VIEW,
            Perm.PRODUCTION_MOVE,
            Perm.INVENTORY_VIEW,
            Perm.INVENTORY_RECORD_USAGE,
            Perm.REPORTS_OWN_PRODUCTION,
        }
    ),
}


def permissions_for(user: Any) -> frozenset[str]:
    """Return every permission the user holds."""
    if not user or not user.is_authenticated or not user.is_active:
        return frozenset()
    if user.is_superuser:
        return Perm.all()
    return ROLE_PERMISSIONS.get(getattr(user, "role", ""), frozenset())


def user_can(user: Any, perm: str) -> bool:
    return perm in permissions_for(user)


def _normalise(perms: str | Iterable[str]) -> tuple[str, ...]:
    if isinstance(perms, str):
        return (perms,)
    return tuple(perms)


def required_perms_for(view: Any, method: str) -> tuple[str, ...] | None:
    """Resolve the permissions a view action needs, or ``None`` if it is not declared."""
    mapping = getattr(view, "required_perms", None)
    if mapping is None:
        return None
    if isinstance(mapping, str | tuple | list | frozenset | set):
        return _normalise(mapping)
    action = getattr(view, "action", None) or method.lower()
    perms = mapping.get(action, mapping.get("*"))
    if perms is None:
        return None
    return _normalise(perms)


class HasPerm(BasePermission):
    """DRF permission class enforcing ``view.required_perms``."""

    message = "You do not have permission to perform this action."

    def has_permission(self, request: Any, view: Any) -> bool:
        user = request.user
        if not (user and user.is_authenticated and user.is_active):
            return False
        required = required_perms_for(view, request.method)
        if required is None:
            return False
        held = permissions_for(user)
        return all(p in held for p in required)


class IsOwnerForDocs(BasePermission):
    """API schema and Swagger UI: open in development, owner-only in production."""

    def has_permission(self, request: Any, view: Any) -> bool:
        if settings.DEBUG:
            return True
        return user_can(request.user, Perm.SETTINGS_MANAGE)
