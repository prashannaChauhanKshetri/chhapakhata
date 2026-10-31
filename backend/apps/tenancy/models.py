from __future__ import annotations

from django.db import models

from .context import business_default


class Business(models.Model):
    """One print shop. Each shop sees only its own data (see context.py)."""

    name = models.CharField(max_length=150)
    slug = models.SlugField(max_length=60, unique=True)
    is_active = models.BooleanField(
        default=True, help_text="Staff of an inactive business cannot sign in."
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "businesses"

    def __str__(self) -> str:
        return self.name


class BusinessOwned(models.Model):
    """Base for every table that belongs to one business.

    ``business`` is filled from the current scope, so services never pass it.
    Each subclass's table also needs ``enable_rls`` in its migration.
    """

    business = models.ForeignKey(
        Business, on_delete=models.PROTECT, default=business_default, related_name="+"
    )

    class Meta:
        abstract = True
