"""Confirmed orders not billed yet go on their customer's account.

Until now an order reached the statement only when billed. From this change a
confirmed order counts straight away (see billing.services.sync_order_charge);
this brings the orders already confirmed, and not billed, up to date.
"""

from decimal import Decimal

from django.db import migrations

OPEN = ("confirmed", "in_production", "ready", "delivered")


def charge(apps, schema_editor):
    Order = apps.get_model("orders", "Order")
    InvoiceOrder = apps.get_model("billing", "InvoiceOrder")
    LedgerEntry = apps.get_model("billing", "LedgerEntry")
    billed = set(
        InvoiceOrder.objects.filter(is_active=True).values_list("order_id", flat=True)
    )
    entries = []
    for order in Order.objects.filter(status__in=OPEN).exclude(source="import"):
        if order.pk in billed or order.total <= 0:
            continue
        on_account = sum(
            (e.debit - e.credit)
            for e in LedgerEntry.objects.filter(
                order_id=order.pk, entry_type__in=("imported_work", "order", "work_billed")
            )
        )
        if on_account:
            continue
        entries.append(
            LedgerEntry(
                business_id=order.business_id,
                customer_id=order.customer_id,
                entry_date=order.order_date,
                entry_type="order",
                debit=order.total,
                credit=Decimal("0"),
                order_id=order.pk,
                narration=f"Order {order.order_no}",
            )
        )
    LedgerEntry.objects.bulk_create(entries)


def uncharge(apps, schema_editor):
    apps.get_model("billing", "LedgerEntry").objects.filter(entry_type="order").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0010_order_charge"),
        ("orders", "0004_business_rls"),
    ]

    operations = [migrations.RunPython(charge, uncharge)]
