from __future__ import annotations

from decimal import Decimal

from django.contrib.auth.models import AbstractUser
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.core.permissions import Role, permissions_for
from apps.tenancy.context import business_default


class User(AbstractUser):
    """A shop staff account. Each person has a personal login and one role.

    Usernames are unique across the site; the account's business decides which
    shop's data it sees. Platform superusers have no business.
    """

    business = models.ForeignKey(
        "tenancy.Business",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        default=business_default,
        related_name="users",
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.FRONT_DESK)
    phone = models.CharField(max_length=20, blank=True)
    max_discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Leave empty to use the role default.",
    )

    class Meta:
        ordering = ["first_name", "username"]

    def __str__(self) -> str:
        return self.get_full_name() or self.username

    @property
    def permissions(self) -> frozenset[str]:
        return permissions_for(self)

    def can(self, perm: str) -> bool:
        return perm in self.permissions

    def discount_limit(self) -> Decimal | None:
        """Maximum discount as a percent of subtotal, or ``None`` for no limit."""
        if self.max_discount_percent is not None:
            return self.max_discount_percent
        if self.is_superuser or self.role == Role.OWNER:
            return None
        if self.role == Role.FRONT_DESK:
            from apps.core.models import ShopSettings

            return ShopSettings.load().front_desk_max_discount_percent
        return Decimal("0")
