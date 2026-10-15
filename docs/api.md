# API conventions

The live reference is Swagger at `/api/docs/` (development, or owner sign-in in production). The schema is `backend/schema.yml`.

## Basics

- Base path `/api/v1/`. JSON in and out; decimals are strings (`"1250.00"`).
- **Auth:** `GET auth/csrf/` sets the CSRF cookie; `POST auth/login/` starts a session; `GET auth/me/` returns the user and their permission list. Unsafe requests send `X-CSRFToken`.
- **Lists:** `?page=`, `?page_size=` (max 200), `?search=`, `?ordering=` (prefix `-` for descending), plus filters per resource.
- **Dates:** AD dates as `YYYY-MM-DD`; responses add `*_bs` fields with the Bikram Sambat date.
- **Exports:** report and statement endpoints accept `?export=xlsx` or `?export=pdf`. (The parameter is `export`, not `format`, which DRF reserves.)

## Errors

Every error uses one shape:

```json
{
  "type": "validation_error",
  "errors": [
    { "code": "invalid", "detail": "Width must be greater than zero.", "attr": "items.0.width" }
  ]
}
```

`attr` is a dotted path that matches the frontend form field. Business-rule failures (stock would go negative, discount above limit) are `validation_error` with code `business_rule`. Missing permission is `403`; an expired session is `403` with code `not_authenticated`; login lockout is `429` with code `locked_out`.

## State changes are explicit actions

Status fields are never patched directly. Use the action endpoints:

| Action | Endpoint |
|---|---|
| Live price | `POST orders/price-preview/` |
| Confirm quotation | `POST orders/{id}/confirm/` |
| Cancel order | `POST orders/{id}/cancel/` `{reason}` |
| Issue invoice | `POST orders/{id}/invoice/` |
| Deliver and settle | `POST orders/{id}/deliver/` `{issue_invoice, payment?}` |
| Move job | `POST jobs/{id}/move/` `{to_stage, material?, skip_material?}` |
| Record material | `POST jobs/{id}/record-material/` |
| Print invoice (counts the print) | `POST invoices/{id}/print/?size=a4|a5|80mm` |
| Cancel invoice | `POST invoices/{id}/cancel/` `{reason}` |
| Void payment | `POST payments/{id}/void/` `{reason}` |
| Stock | `POST stock-items/{id}/opening|usage|wastage|adjust/`, `POST rolls/{id}/finish/` |
| Backup now | `POST system/backups/run/` |

## Changing the API

1. Change serializers/views; annotate custom actions with `@extend_schema`.
2. `make schema` regenerates `schema.yml` and the TypeScript types.
3. Fix any TypeScript errors in the frontend, then commit both files.
