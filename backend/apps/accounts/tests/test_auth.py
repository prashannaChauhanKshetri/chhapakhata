import pytest
from django.test import Client, override_settings

from apps.accounts import services
from apps.accounts.models import User
from apps.core.exceptions import BusinessError
from apps.core.permissions import Role

pytestmark = pytest.mark.django_db


def _csrf_client() -> tuple[Client, str]:
    client = Client(enforce_csrf_checks=True)
    client.get("/api/v1/auth/csrf/")
    return client, client.cookies["csrftoken"].value


def test_login_me_logout_with_csrf(desk):
    client, token = _csrf_client()
    # Without the CSRF header the login is refused.
    assert (
        client.post(
            "/api/v1/auth/login/",
            {"username": "desk", "password": "Test@12345"},
            content_type="application/json",
        ).status_code
        == 403
    )
    response = client.post(
        "/api/v1/auth/login/",
        {"username": "desk", "password": "Test@12345"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 200
    body = response.json()
    assert body["role"] == Role.FRONT_DESK
    assert "orders.manage" in body["permissions"]
    assert body["discount_limit"] == "10.00"
    token = client.cookies["csrftoken"].value  # rotated on login
    assert client.get("/api/v1/auth/me/").status_code == 200
    assert client.post("/api/v1/auth/logout/", HTTP_X_CSRFTOKEN=token).status_code == 204
    assert client.get("/api/v1/auth/me/").status_code == 403


def test_wrong_password(desk):
    client, token = _csrf_client()
    response = client.post(
        "/api/v1/auth/login/",
        {"username": "desk", "password": "nope"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 400
    assert response.json()["errors"][0]["detail"] == "Incorrect username or password."


@override_settings(AXES_ENABLED=True, AXES_FAILURE_LIMIT=3)
def test_lockout_after_repeated_failures(desk):
    client, token = _csrf_client()
    for _ in range(3):
        client.post(
            "/api/v1/auth/login/",
            {"username": "desk", "password": "bad"},
            content_type="application/json",
            HTTP_X_CSRFTOKEN=token,
        )
    response = client.post(
        "/api/v1/auth/login/",
        {"username": "desk", "password": "Test@12345"},
        content_type="application/json",
        HTTP_X_CSRFTOKEN=token,
    )
    assert response.status_code == 429
    assert response.json()["errors"][0]["code"] == "locked_out"


@override_settings(MAX_ACTIVE_USERS=3)
def test_active_user_cap(owner, desk, operator):
    with pytest.raises(BusinessError):
        services.create_user(
            actor=owner, password="Long@Pass123", username="fourth", role=Role.OPERATOR
        )
    services.update_user(actor=owner, user=operator, is_active=False)
    services.create_user(
        actor=owner, password="Long@Pass123", username="fourth", role=Role.OPERATOR
    )
    with pytest.raises(BusinessError):
        services.update_user(actor=owner, user=operator, is_active=True)


def test_last_owner_cannot_be_removed(owner):
    with pytest.raises(BusinessError):
        services.update_user(actor=owner, user=owner, role=Role.FRONT_DESK)
    with pytest.raises(BusinessError):
        services.update_user(actor=owner, user=owner, is_active=False)


def test_weak_password_rejected(owner):
    with pytest.raises(BusinessError):
        services.create_user(actor=owner, password="12345678", username="weak", role=Role.OPERATOR)
    assert not User.objects.filter(username="weak").exists()


def test_user_api_create_and_reset(api, owner):
    response = api(owner).post(
        "/api/v1/users/",
        {"username": "hari", "first_name": "Hari", "role": "operator", "password": "Strong@Pass1"},
        format="json",
    )
    assert response.status_code == 201, response.content
    user_id = response.json()["id"]
    assert "password" not in response.json()
    reset = api(owner).post(
        f"/api/v1/users/{user_id}/reset-password/", {"new_password": "Another@Pass2"}, format="json"
    )
    assert reset.status_code == 204
    assert User.objects.get(pk=user_id).check_password("Another@Pass2")
