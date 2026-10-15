"""Every role × endpoint, checked against the proposal's permission table (section 3.1).

``True`` means the role may call the endpoint; ``False`` means 403.
"""

from decimal import Decimal as D

import pytest

from apps.core.permissions import ROLE_PERMISSIONS, Perm, Role

pytestmark = pytest.mark.django_db

#             path                                   owner  desk   operator
READS = [
    ("/api/v1/media-types/", True, True, False),
    ("/api/v1/customers/", True, True, False),
    ("/api/v1/orders/", True, True, False),
    ("/api/v1/invoices/", True, True, False),
    ("/api/v1/payments/", True, True, False),
    ("/api/v1/jobs/board/", True, True, True),
    ("/api/v1/jobs/", True, True, True),
    ("/api/v1/stock-items/", True, True, True),
    ("/api/v1/rolls/", True, True, True),
    ("/api/v1/purchases/", True, False, False),
    ("/api/v1/suppliers/", True, False, False),
    ("/api/v1/users/", True, False, False),
    ("/api/v1/activity/", True, False, False),
    ("/api/v1/system/backups/", True, False, False),
    ("/api/v1/reports/daily-sales/", True, True, False),
    ("/api/v1/reports/monthly-sales/", True, False, False),
    ("/api/v1/reports/pending-dues/", True, False, False),
    ("/api/v1/reports/collections/", True, False, False),
    ("/api/v1/reports/material-vs-sales/", True, False, False),
    ("/api/v1/reports/operator-log/", True, False, True),
    ("/api/v1/reports/stock/", True, False, False),
    ("/api/v1/dashboard/", True, True, True),
    ("/api/v1/settings/shop/", True, True, True),
]


@pytest.mark.parametrize(("path", "as_owner", "as_desk", "as_operator"), READS)
def test_read_access(api, owner, desk, operator, path, as_owner, as_desk, as_operator):
    for user, allowed in ((owner, as_owner), (desk, as_desk), (operator, as_operator)):
        status = api(user).get(path).status_code
        assert (status == 200) is allowed, f"{user.role} GET {path} → {status}"


def test_anonymous_is_rejected(api):
    assert api().get("/api/v1/orders/").status_code == 403
    assert api().get("/api/v1/auth/me/").status_code == 403
    assert api().get("/api/v1/health/").status_code == 200


def test_write_rules(api, owner, desk, operator, customer, star_flex, eyelets):
    # Rate card: owner only
    body = {"name": "Mesh", "rate_per_sqft": "40"}
    assert api(desk).post("/api/v1/media-types/", body, format="json").status_code == 403
    assert api(operator).post("/api/v1/media-types/", body, format="json").status_code == 403
    assert api(owner).post("/api/v1/media-types/", body, format="json").status_code == 201

    # Orders: owner and front desk
    order = {
        "customer": customer.pk,
        "items": [{"media_type": star_flex.pk, "width": "3", "height": "2", "quantity": 1}],
    }
    assert api(operator).post("/api/v1/orders/", order, format="json").status_code == 403
    response = api(desk).post("/api/v1/orders/", {**order, "confirm": True}, format="json")
    assert response.status_code == 201, response.content
    order_id = response.json()["id"]

    # Payments: owner and front desk; voids owner only
    pay = {"customer": customer.pk, "order": order_id, "amount": "100", "mode": "cash"}
    assert api(operator).post("/api/v1/payments/", pay, format="json").status_code == 403
    payment = api(desk).post("/api/v1/payments/", pay, format="json")
    assert payment.status_code == 201
    void_url = f"/api/v1/payments/{payment.json()['id']}/void/"
    assert api(desk).post(void_url, {"reason": "Mistake entry"}, format="json").status_code == 403
    assert api(owner).post(void_url, {"reason": "Mistake entry"}, format="json").status_code == 200

    # Invoices: issue by front desk, cancel by owner only
    invoice = api(desk).post(f"/api/v1/orders/{order_id}/invoice/", {}, format="json")
    assert invoice.status_code == 201
    cancel_url = f"/api/v1/invoices/{invoice.json()['id']}/cancel/"
    assert api(desk).post(cancel_url, {"reason": "Wrong amount"}, format="json").status_code == 403
    assert api(owner).post(cancel_url, {"reason": "Wrong amount"}, format="json").status_code == 200

    # Stock adjustment: owner only. Wastage: owner and operator.
    from apps.inventory.models import StockItem

    ink = StockItem.objects.create(name="Ink", kind="ink", unit="litre", on_hand=D("0"))
    api(owner).post(f"/api/v1/stock-items/{ink.pk}/opening/", {"quantity": "5"}, format="json")
    adjust = {"counted_quantity": "4", "reason": "Count"}
    assert (
        api(desk).post(f"/api/v1/stock-items/{ink.pk}/adjust/", adjust, format="json").status_code
        == 403
    )
    assert (
        api(operator)
        .post(f"/api/v1/stock-items/{ink.pk}/adjust/", adjust, format="json")
        .status_code
        == 403
    )
    assert (
        api(owner).post(f"/api/v1/stock-items/{ink.pk}/adjust/", adjust, format="json").status_code
        == 200
    )
    waste = {"quantity": "0.5", "reason": "Spill"}
    assert (
        api(desk).post(f"/api/v1/stock-items/{ink.pk}/wastage/", waste, format="json").status_code
        == 403
    )
    assert (
        api(operator)
        .post(f"/api/v1/stock-items/{ink.pk}/wastage/", waste, format="json")
        .status_code
        == 200
    )


def test_operator_log_is_own_only(api, operator, owner):
    response = api(operator).get(f"/api/v1/reports/operator-log/?operator={owner.pk}")
    assert response.status_code == 200
    assert str(operator) in response.json()["title"]


def test_matrix_matches_proposal_summary():
    desk, op = ROLE_PERMISSIONS[Role.FRONT_DESK], ROLE_PERMISSIONS[Role.OPERATOR]
    assert Perm.CATALOG_MANAGE not in desk and Perm.CATALOG_MANAGE not in op
    assert Perm.LEDGER_VIEW in desk and Perm.LEDGER_MANAGE not in desk
    assert Perm.INVENTORY_RECORD_USAGE in op and Perm.INVENTORY_RECORD_USAGE not in desk
    assert Perm.USERS_MANAGE not in desk | op
    assert ROLE_PERMISSIONS[Role.OWNER] == Perm.all()
