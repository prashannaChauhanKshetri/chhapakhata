"""Move the shop settings id counter past the existing row.

Before several businesses, the one settings row was always saved with id 1
by hand, so the counter never advanced and a second business's settings
would collide with it.
"""

from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("core", "0004_business_rls")]

    operations = [
        migrations.RunSQL(
            sql=(
                "SELECT setval(pg_get_serial_sequence('core_shopsettings', 'id'), "
                "COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM core_shopsettings"
            ),
            reverse_sql=migrations.RunSQL.noop,
        )
    ]
