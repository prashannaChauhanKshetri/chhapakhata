import datetime as dt
import threading

import pytest
from django.core.exceptions import ValidationError
from django.db import connection, transaction

from apps.core.models import DocumentSequence, ShopSettings, validate_number_pattern
from apps.core.sequences import DocType, next_number
from apps.tenancy.context import use_business


@pytest.mark.django_db
def test_job_numbers_start_at_1001():
    with transaction.atomic():
        first = next_number(DocType.JOB)
        second = next_number(DocType.JOB)
    assert (first.number, second.number) == ("JOB-1001", "JOB-1002")


@pytest.mark.django_db
def test_invoice_numbers_restart_each_fiscal_year():
    with transaction.atomic():
        a = next_number(DocType.INVOICE, dt.date(2026, 7, 16))
        b = next_number(DocType.INVOICE, dt.date(2026, 7, 17))
        c = next_number(DocType.INVOICE, dt.date(2026, 8, 1))
    assert a.number == "INV-2082/83-0001"
    assert b.number == "INV-2083/84-0001"
    assert c.number == "INV-2083/84-0002"


@pytest.mark.django_db
def test_patterns_come_from_settings():
    shop = ShopSettings.load()
    shop.order_number_pattern = "OM-{n:03d}"
    shop.save()
    with transaction.atomic():
        assert next_number(DocType.ORDER).number == "OM-001"


def test_pattern_validation_rejects_attribute_access():
    validate_number_pattern("JOB-{n}")
    validate_number_pattern("{fy}/{n:04d}")
    with pytest.raises(ValidationError):
        validate_number_pattern("{n.__class__}")
    with pytest.raises(ValidationError):
        validate_number_pattern("NO-NUMBER")


@pytest.mark.django_db(transaction=True)
def test_requires_transaction():
    with pytest.raises(RuntimeError):
        next_number(DocType.ORDER)


@pytest.mark.django_db(transaction=True)
def test_concurrent_allocation_never_duplicates(business):
    results: list[int] = []
    lock = threading.Lock()

    def worker():
        with use_business(business):  # a new thread starts with no business
            for _ in range(5):
                with transaction.atomic():
                    allocated = next_number(DocType.RECEIPT)
                with lock:
                    results.append(allocated.sequence)
        connection.close()

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == list(range(1, 21))
    assert DocumentSequence.objects.get(doc_type=DocType.RECEIPT).last_number == 20
