from django.http import JsonResponse

LOCKOUT_MESSAGE = (
    "Too many failed sign-in attempts. Wait 15 minutes, or ask the owner to unlock your account."
)


def lockout_response(request, credentials=None, *args, **kwargs) -> JsonResponse:
    """django-axes lockout handler: same error envelope as the rest of the API."""
    return JsonResponse(
        {
            "type": "client_error",
            "errors": [{"code": "locked_out", "detail": LOCKOUT_MESSAGE, "attr": None}],
        },
        status=429,
    )
