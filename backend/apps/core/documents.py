"""PDF rendering with WeasyPrint. Fonts and images load from local files, so
documents render identically with or without internet."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.text import slugify

from .dates import bs_string
from .models import ShopSettings

PAGE_SIZES = {"a4": "A4", "a5": "A5", "80mm": "80mm 297mm"}
PX_TO_MM = 25.4 / 96
THERMAL_BOTTOM_MM = 8


def _file_uri(field: Any) -> str | None:
    if not field:
        return None
    try:
        path = Path(field.path)
    except (ValueError, NotImplementedError):
        return None
    return path.as_uri() if path.exists() else None


def base_context() -> dict[str, Any]:
    shop = ShopSettings.load()
    now = timezone.localtime()
    return {
        "shop": shop,
        "logo_uri": _file_uri(shop.logo),
        "stamp_uri": _file_uri(shop.stamp_image),
        "signature_uri": _file_uri(shop.signature_image),
        "fonts_uri": Path(settings.FONTS_DIR).as_uri(),
        "generated_at": now,
        "generated_at_bs": bs_string(now),
    }


def render_html(template: str, context: dict[str, Any]) -> str:
    return render_to_string(template, {**base_context(), **context})


def _content_height_mm(html: str) -> int | None:
    """Lay the page out once on a very tall roll and measure the content."""
    from weasyprint import HTML

    try:
        document = HTML(string=html, base_url=str(settings.BASE_DIR)).render()
        root = document.pages[0]._page_box.children[0]
        bottom_px = root.position_y + root.margin_height()
    except (AttributeError, IndexError):  # pragma: no cover - layout internals changed
        return None
    return math.ceil(bottom_px * PX_TO_MM) + THERMAL_BOTTOM_MM


def render_pdf(template: str, context: dict[str, Any], *, thermal: bool = False) -> bytes:
    """Render a template to PDF.

    ``thermal=True`` cuts a single 80 mm-wide page to the content's height,
    so receipt printers do not feed blank paper. WeasyPrint has no automatic
    page height, so the document is laid out twice.
    """
    from weasyprint import HTML  # imported lazily: heavy, and only needed here

    if thermal:
        tall = render_html(template, {**context, "thermal_height": "3000mm"})
        height = _content_height_mm(tall) or 297
        context = {**context, "thermal_height": f"{height}mm"}
    html = render_html(template, context)
    return HTML(string=html, base_url=str(settings.BASE_DIR)).write_pdf()


def file_response(content: bytes, filename: str, content_type: str, inline: bool) -> HttpResponse:
    response = HttpResponse(content, content_type=content_type)
    disposition = "inline" if inline else "attachment"
    response["Content-Disposition"] = f'{disposition}; filename="{filename}"'
    response["Cache-Control"] = "no-store"
    return response


def pdf_response(pdf: bytes, name: str, inline: bool = True) -> HttpResponse:
    return file_response(pdf, f"{slugify(name) or 'document'}.pdf", "application/pdf", inline)


XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def xlsx_response(content: bytes, name: str) -> HttpResponse:
    return file_response(content, f"{slugify(name) or 'export'}.xlsx", XLSX_TYPE, inline=False)
