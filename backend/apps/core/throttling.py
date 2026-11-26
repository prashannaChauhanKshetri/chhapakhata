"""Rate limits for the API.

Every request counts towards a general limit (per signed-in user, or per address
for anonymous visitors). Requests that make PDFs or spreadsheets, import files or
run backups also count towards a tighter "heavy" limit, because each one costs the
server far more than an ordinary screen. Sign-in, password changes and "Backup
now" have their own scopes (see ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]``).

Counters live in the shared cache (``CACHES``), so all web workers count together.
"""

from __future__ import annotations

import re

from rest_framework.throttling import SimpleRateThrottle

#: Paths that render a document, move a whole file in or out, or erase data.
HEAVY_PATH = re.compile(
    r"/(print|receipt|slip|ticket|job-tickets-pdf|quotation-pdf|export|import|erase)/"
    r"|/settings/shop/preview/$"
)
#: ``?export=pdf`` or ``?export=xlsx`` on reports, statements and order lists.
HEAVY_EXPORTS = {"pdf", "xlsx"}


def is_heavy(request) -> bool:
    return bool(HEAVY_PATH.search(request.path)) or (
        request.query_params.get("export", "").lower() in HEAVY_EXPORTS
    )


class HeavyThrottle(SimpleRateThrottle):
    """30 documents, exports or imports a minute per person (or address)."""

    scope = "heavy"

    def get_cache_key(self, request, view):
        if not is_heavy(request):
            return None  # not throttled by this class
        if request.user and request.user.is_authenticated:
            ident = f"user-{request.user.pk}"
        else:
            ident = self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class BackupThrottle(SimpleRateThrottle):
    """The "Backup now" button runs a full database dump: a few times an hour at most."""

    scope = "backup"

    def get_cache_key(self, request, view):
        if request.method != "POST":
            return None
        return self.cache_format % {"scope": self.scope, "ident": f"user-{request.user.pk}"}
