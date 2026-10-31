from __future__ import annotations

from contextvars import Token
from typing import Any

from django.db.backends.signals import connection_created
from django.db.models.signals import post_migrate, pre_migrate
from django.dispatch import receiver

from . import context


@receiver(connection_created)
def apply_scope_on_connect(sender: Any, connection: Any, **kwargs: Any) -> None:
    if connection.vendor == "postgresql":
        context.apply_to_connection(connection)


# Migrations see every business, so data migrations can update all rows.
_migrating: Token[context.Scope] | None = None


@receiver(pre_migrate)
def bypass_during_migrate(sender: Any, **kwargs: Any) -> None:
    global _migrating
    if _migrating is None:
        _migrating = context._scope.set(context.Scope(bypass=True))
        context._sync()


@receiver(post_migrate)
def end_bypass_after_migrate(sender: Any, **kwargs: Any) -> None:
    global _migrating
    if _migrating is not None:
        context._scope.reset(_migrating)
        _migrating = None
        context._sync()
