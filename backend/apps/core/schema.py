"""OpenAPI post-processing.

Responses always include every serializer field, but drf-spectacular marks
fields with model defaults as optional. That would force the frontend to
handle impossible `undefined` values, so response components list every
property as required. In request components, fields that have a default are
made optional, matching how the API actually validates them.
"""

from __future__ import annotations

from typing import Any


def mark_response_fields_required(
    result: dict[str, Any], generator, request, public
) -> dict[str, Any]:
    schemas = result.get("components", {}).get("schemas", {})
    for name, schema in schemas.items():
        properties = schema.get("properties")
        if name.endswith("Request") or name.startswith("Patched"):
            # A request field with a server-side default may be omitted.
            if properties and schema.get("required"):
                schema["required"] = [
                    p for p in schema["required"] if "default" not in properties.get(p, {})
                ]
                if not schema["required"]:
                    del schema["required"]
            continue
        if schema.get("type") == "object" and properties:
            schema["required"] = sorted(properties)
    return result
