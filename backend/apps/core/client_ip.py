"""The visitor's real address, behind Caddy (and Cloudflare in front of it).

Caddy works out the client's address, trusting Cloudflare's ``CF-Connecting-IP``
only when the request really comes from Cloudflare, and passes it on as
``X-Real-IP``. This middleware puts it in ``REMOTE_ADDR`` so the sign-in lock-out
(django-axes), the rate limits and the activity log all see the person, not a
Cloudflare server. The header is believed only when the request reached Django
through a proxy on the private network; sent straight to Django from outside, it
is ignored, so nobody can pick their own address.
"""

from __future__ import annotations

import ipaddress


def _address(value: str) -> ipaddress.IPv4Address | ipaddress.IPv6Address | None:
    try:
        return ipaddress.ip_address(value.strip())
    except ValueError:
        return None


def from_trusted_proxy(remote_addr: str) -> bool:
    """Caddy reaches Django over the Docker network (private) or locally (loopback)."""
    address = _address(remote_addr or "")
    return address is not None and (address.is_private or address.is_loopback)


class RealClientIPMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        real = request.META.get("HTTP_X_REAL_IP", "")
        if real and from_trusted_proxy(request.META.get("REMOTE_ADDR", "")):
            address = _address(real)
            if address is not None:
                request.META["REMOTE_ADDR"] = str(address)
        return self.get_response(request)
