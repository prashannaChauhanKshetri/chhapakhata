from rest_framework.exceptions import ValidationError


class BusinessError(ValidationError):
    """A business rule was violated (for example, a roll would go negative).

    Raised by service functions; rendered as a 400 validation error with the
    standard error envelope, so the frontend shows the message to the user.
    """

    default_code = "business_rule"
