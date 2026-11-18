"""Every bill issued so far covers its one order."""

from django.db import migrations


def link(apps, schema_editor):
    Invoice = apps.get_model("billing", "Invoice")
    InvoiceOrder = apps.get_model("billing", "InvoiceOrder")
    InvoiceOrder.objects.bulk_create(
        InvoiceOrder(
            business_id=invoice.business_id,
            invoice_id=invoice.pk,
            order_id=invoice.order_id,
            is_active=invoice.status == "issued",
        )
        for invoice in Invoice.objects.only("pk", "business_id", "order_id", "status")
    )


class Migration(migrations.Migration):
    dependencies = [("billing", "0008_bill_many_orders")]

    operations = [migrations.RunPython(link, migrations.RunPython.noop)]
