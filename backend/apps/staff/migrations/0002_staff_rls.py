from django.db import migrations

from apps.tenancy.operations import enable_rls


class Migration(migrations.Migration):
    """Each business sees and changes only its own staff, attendance and salaries."""

    dependencies = [("staff", "0001_initial")]

    operations = [
        enable_rls("staff_staff"),
        enable_rls("staff_historicalstaff"),
        enable_rls("staff_attendance"),
        enable_rls("staff_staffadvance"),
        enable_rls("staff_salarypayment"),
    ]
