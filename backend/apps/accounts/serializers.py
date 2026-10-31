from __future__ import annotations

from rest_framework import serializers

from apps.tenancy.context import current_business_id

from .models import User


class StaffField(serializers.PrimaryKeyRelatedField):
    """A user of the current business (users are not under row-level security)."""

    def get_queryset(self):
        return super().get_queryset().filter(business_id=current_business_id())


class BusinessRefSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class MeSerializer(serializers.ModelSerializer):
    business = BusinessRefSerializer(read_only=True, allow_null=True)
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    permissions = serializers.SerializerMethodField()
    discount_limit = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "role",
            "role_label",
            "permissions",
            "discount_limit",
            "business",
        ]

    def get_permissions(self, obj: User) -> list[str]:
        return sorted(obj.permissions)

    def get_discount_limit(self, obj: User) -> str | None:
        limit = obj.discount_limit()
        return None if limit is None else str(limit)


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField(max_length=150)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(trim_whitespace=False)
    new_password = serializers.CharField(trim_whitespace=False, min_length=8)


class ResetPasswordSerializer(serializers.Serializer):
    new_password = serializers.CharField(trim_whitespace=False, min_length=8)


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    role_label = serializers.CharField(source="get_role_display", read_only=True)
    password = serializers.CharField(
        write_only=True, required=False, trim_whitespace=False, min_length=8
    )

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "role",
            "role_label",
            "max_discount_percent",
            "is_active",
            "last_login",
            "date_joined",
            "password",
        ]
        read_only_fields = ["last_login", "date_joined"]

    def validate(self, attrs):
        if self.instance is None and not attrs.get("password"):
            raise serializers.ValidationError({"password": "Set a password for the new account."})
        return attrs
