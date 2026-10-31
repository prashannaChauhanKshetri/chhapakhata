from __future__ import annotations

from typing import Any

from django.db import models
from rest_framework.validators import UniqueValidator


def unique_in_business(model: type[models.Model]) -> dict[str, Any]:
    """``extra_kwargs`` entry for a name that is unique within each business.

    Row-level security limits the lookup to the current business, matching the
    ``(business, name)`` constraint, so the duplicate is reported as a 400.
    """
    return {"validators": [UniqueValidator(queryset=model.objects.all())]}
