"""The business that the current request or command works for.

Every shop's rows carry a ``business_id``. PostgreSQL row-level security (see
``operations.py``) shows and accepts only the rows whose ``business_id``
matches the connection setting ``app.business_id``, so a missed filter in
Python can never reveal or change another shop's data.

This module keeps that setting in step with a context variable:

* ``BusinessMiddleware`` scopes each request to the signed-in user's business;
* management commands use ``use_business(business)``;
* migrations and platform commands use ``rls_bypass()``.

With no business set, tenant tables look empty and inserts fail (fail closed).
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager, suppress
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from django.db import DatabaseError, connection
from rest_framework.exceptions import PermissionDenied


@dataclass(frozen=True)
class Scope:
    business_id: int | None = None
    bypass: bool = False


# Scope is frozen, so sharing one default instance is safe.
_scope: ContextVar[Scope] = ContextVar("business_scope", default=Scope())  # noqa: B039


class NoBusinessError(PermissionDenied):
    default_detail = "This account is not linked to a business."
    default_code = "no_business"


def current_business_id() -> int | None:
    return _scope.get().business_id


def business_default() -> int | None:
    """Default for every ``business`` field: the current business, if any."""
    return _scope.get().business_id


def require_business_id() -> int:
    business_id = current_business_id()
    if business_id is None:
        raise NoBusinessError()
    return business_id


def apply_to_connection(conn: Any = None) -> None:
    """Copy the current scope into the database session settings."""
    conn = conn or connection
    scope = _scope.get()
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT set_config('app.business_id', %s, false),"
            " set_config('app.rls_bypass', %s, false)",
            [str(scope.business_id or ""), "on" if scope.bypass else "off"],
        )


def _sync() -> None:
    # Not connected yet: the connection_created signal applies the scope.
    if connection.connection is not None:
        apply_to_connection()


@contextmanager
def business_scope(business_id: int | None, *, bypass: bool = False) -> Iterator[None]:
    token = _scope.set(Scope(business_id, bypass))
    _sync()
    try:
        yield
    finally:
        _scope.reset(token)
        # If the transaction failed, rolling it back undoes the setting too.
        with suppress(DatabaseError):
            _sync()


def use_business(business: Any) -> Any:
    """Work as one business: ``with use_business(shop): ...`` (instance or id)."""
    return business_scope(getattr(business, "pk", business))


def rls_bypass() -> Any:
    """See every business. Only for migrations and platform commands."""
    return business_scope(None, bypass=True)


def activate(business_id: int | None) -> None:
    """Switch the rest of the current request to a business (used on sign-in).

    Call it only inside a ``business_scope`` (the middleware's), which restores
    the previous value on exit.
    """
    _scope.set(Scope(business_id))
    _sync()
