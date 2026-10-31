"""User account rules: the contract's active-user cap and keeping one owner.

Users are not under row-level security (sign-in must find them before a
business is known), so every query here filters by business itself.
"""

from __future__ import annotations

from typing import Any

from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

from apps.core.activity import log_activity
from apps.core.exceptions import BusinessError
from apps.core.permissions import Role

from .models import User


def active_user_count(business_id: int | None, exclude: User | None = None) -> int:
    qs = User.objects.filter(business_id=business_id, is_active=True, is_superuser=False)
    if exclude is not None and exclude.pk:
        qs = qs.exclude(pk=exclude.pk)
    return qs.count()


def _check_cap(business_id: int | None, exclude: User | None = None) -> None:
    limit = settings.MAX_ACTIVE_USERS
    if active_user_count(business_id, exclude) >= limit:
        raise BusinessError(
            f"Your plan includes {limit} active user accounts. "
            "Deactivate an account before adding another."
        )


def _check_password(password: str, user: User) -> None:
    try:
        validate_password(password, user)
    except DjangoValidationError as exc:
        raise BusinessError({"password": list(exc.messages)}) from exc


def _remaining_owners(excluding: User) -> int:
    return (
        User.objects.filter(business_id=excluding.business_id, is_active=True, role=Role.OWNER)
        .exclude(pk=excluding.pk)
        .count()
    )


@transaction.atomic
def create_user(*, actor: User, password: str, request: Any = None, **fields: Any) -> User:
    user = User(**fields)
    if actor is not None and actor.business_id is not None:
        user.business_id = actor.business_id  # staff join their owner's business
    if user.is_active:
        _check_cap(user.business_id)
    _check_password(password, user)
    user.set_password(password)
    user.save()
    log_activity(
        actor, "user.created", user, message=f"Role: {user.get_role_display()}", request=request
    )
    return user


@transaction.atomic
def update_user(*, actor: User, user: User, request: Any = None, **fields: Any) -> User:
    becoming_active = fields.get("is_active") is True and not user.is_active
    leaving_owner = user.role == Role.OWNER and (
        fields.get("is_active") is False or fields.get("role", Role.OWNER) != Role.OWNER
    )
    if becoming_active:
        _check_cap(user.business_id, exclude=user)
    if leaving_owner and _remaining_owners(user) == 0:
        raise BusinessError("At least one active owner account must remain.")
    for key, value in fields.items():
        setattr(user, key, value)
    user.save()
    log_activity(actor, "user.updated", user, metadata={"fields": sorted(fields)}, request=request)
    return user


@transaction.atomic
def set_user_password(*, actor: User, user: User, password: str, request: Any = None) -> None:
    _check_password(password, user)
    user.set_password(password)
    user.save(update_fields=["password"])
    action = "user.password_changed" if actor.pk == user.pk else "user.password_reset"
    log_activity(actor, action, user, request=request)
