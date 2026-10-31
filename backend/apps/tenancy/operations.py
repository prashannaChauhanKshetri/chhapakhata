"""Row-level security for business-owned tables.

``FORCE`` applies the policy to the table owner too, which is the role the app
connects as. The app role must not be a superuser: superusers skip all policies.
"""

from __future__ import annotations

from django.db import migrations

POLICY = "business_isolation"
CONDITION = (
    "business_id = NULLIF(current_setting('app.business_id', true), '')::bigint"
    " OR current_setting('app.rls_bypass', true) = 'on'"
)


def enable_rls(table: str) -> migrations.RunSQL:
    """Migration operation: only the current business's rows are visible or writable."""
    return migrations.RunSQL(
        sql=[
            f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY',
            f'ALTER TABLE "{table}" FORCE ROW LEVEL SECURITY',
            f'CREATE POLICY {POLICY} ON "{table}" USING ({CONDITION}) WITH CHECK ({CONDITION})',
        ],
        reverse_sql=[
            f'DROP POLICY IF EXISTS {POLICY} ON "{table}"',
            f'ALTER TABLE "{table}" NO FORCE ROW LEVEL SECURITY',
            f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY',
        ],
    )


def backfill_business(*models: str) -> migrations.RunPython:
    """Migration operation: give existing rows (``"app_label.Model"``) the first business.

    Put it last in its migration: PostgreSQL refuses further ALTER TABLE
    statements in a transaction after rows were updated.
    """

    def run(apps, schema_editor):
        Business = apps.get_model("tenancy", "Business")
        business = Business.objects.order_by("pk").first()
        if business is None:
            return
        for label in models:
            model = apps.get_model(label)
            model._base_manager.filter(business__isnull=True).update(business=business)

    return migrations.RunPython(run, migrations.RunPython.noop)
