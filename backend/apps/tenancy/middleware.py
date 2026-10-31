from __future__ import annotations

from functools import cache

from django.urls import reverse

from .context import business_scope


@cache
def _admin_prefix() -> str:
    return reverse("admin:index")


class BusinessMiddleware:
    """Scope each request to the signed-in user's business.

    Anonymous requests and accounts without a business see no shop data.
    Superusers see every business in the Django admin only.
    Must come after ``AuthenticationMiddleware``.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = request.user
        signed_in = user.is_authenticated
        business_id = user.business_id if signed_in else None
        bypass = signed_in and user.is_superuser and request.path.startswith(_admin_prefix())
        with business_scope(business_id, bypass=bypass):
            return self.get_response(request)
