from __future__ import annotations

from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.core.activity import log_activity
from apps.core.permissions import AUTHENTICATED, Perm
from apps.tenancy.context import activate

from . import services
from .lockout import lockout_response
from .models import User
from .serializers import (
    ChangePasswordSerializer,
    LoginSerializer,
    MeSerializer,
    ResetPasswordSerializer,
    UserSerializer,
)


@method_decorator(ensure_csrf_cookie, name="dispatch")
class CsrfView(APIView):
    """Sets the CSRF cookie. The SPA calls this once before logging in."""

    permission_classes = [AllowAny]
    authentication_classes: list = []

    @extend_schema(responses={204: None})
    def get(self, request):
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name="dispatch")
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "login"

    @extend_schema(request=LoginSerializer, responses=MeSerializer)
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        django_request = request._request
        user = authenticate(
            django_request,
            username=serializer.validated_data["username"],
            password=serializer.validated_data["password"],
        )
        if getattr(django_request, "axes_locked_out", False):
            return lockout_response(django_request)
        if user is None or not user.is_active:
            raise ValidationError({"non_field_errors": ["Incorrect username or password."]})
        if user.business is not None and not user.business.is_active:
            raise ValidationError(
                {"non_field_errors": ["This business's account is paused. Contact support."]}
            )
        login(django_request, user)
        # The middleware saw an anonymous visitor; the rest of this request
        # (activity log, /me data) belongs to the user's business.
        activate(user.business_id)
        log_activity(user, "auth.login", user, request=request)
        return Response(MeSerializer(user).data)


class LogoutView(APIView):
    required_perms = AUTHENTICATED

    @extend_schema(request=None, responses={204: None})
    def post(self, request):
        log_activity(request.user, "auth.logout", request.user, request=request)
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):
    required_perms = AUTHENTICATED

    @extend_schema(responses=MeSerializer)
    def get(self, request):
        return Response(MeSerializer(request.user).data)


class ChangePasswordView(APIView):
    required_perms = AUTHENTICATED

    @extend_schema(request=ChangePasswordSerializer, responses={204: None})
    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not request.user.check_password(serializer.validated_data["current_password"]):
            raise ValidationError({"current_password": ["Your current password is incorrect."]})
        services.set_user_password(
            actor=request.user,
            user=request.user,
            password=serializer.validated_data["new_password"],
            request=request,
        )
        update_session_auth_hash(request._request, request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)


class UserViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Staff accounts. Accounts are deactivated, never deleted, so history keeps names."""

    queryset = User.objects.filter(is_superuser=False)  # narrowed per business below
    serializer_class = UserSerializer
    search_fields = ["username", "first_name", "last_name", "phone"]
    filterset_fields = ["role", "is_active"]
    ordering_fields = ["first_name", "username", "last_login"]
    required_perms = {
        "list": Perm.USERS_MANAGE,
        "retrieve": Perm.USERS_MANAGE,
        "create": Perm.USERS_MANAGE,
        "update": Perm.USERS_MANAGE,
        "partial_update": Perm.USERS_MANAGE,
        "reset_password": Perm.USERS_MANAGE,
        "operators": Perm.PRODUCTION_VIEW,
    }

    def get_queryset(self):
        return super().get_queryset().filter(business_id=self.request.user.business_id)

    def perform_create(self, serializer):
        data = dict(serializer.validated_data)
        password = data.pop("password")
        serializer.instance = services.create_user(
            actor=self.request.user, password=password, request=self.request, **data
        )

    def perform_update(self, serializer):
        data = dict(serializer.validated_data)
        password = data.pop("password", None)
        user = services.update_user(
            actor=self.request.user, user=serializer.instance, request=self.request, **data
        )
        if password:
            services.set_user_password(
                actor=self.request.user, user=user, password=password, request=self.request
            )
        serializer.instance = user

    @extend_schema(request=ResetPasswordSerializer, responses={204: None})
    @action(detail=True, methods=["post"], url_path="reset-password")
    def reset_password(self, request, pk=None):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_user_password(
            actor=request.user,
            user=self.get_object(),
            password=serializer.validated_data["new_password"],
            request=request,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(responses=UserSerializer(many=True))
    @action(detail=False, methods=["get"], pagination_class=None)
    def operators(self, request):
        """Active production operators, for assigning jobs."""
        qs = User.objects.filter(
            business_id=request.user.business_id, is_active=True, role="operator"
        )
        return Response(UserSerializer(qs, many=True).data)
