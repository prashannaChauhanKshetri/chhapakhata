from __future__ import annotations

from decimal import Decimal

from django.utils import timezone
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.models import User
from apps.accounts.serializers import StaffField
from apps.core.permissions import Role
from apps.core.serializers import UserRefSerializer
from apps.inventory.models import Roll

from .models import Job, JobStageEvent, Priority, Stage
from .services import allowed_targets


class JobItemSerializer(serializers.Serializer):
    line_no = serializers.IntegerField()
    media_name = serializers.CharField()
    description = serializers.CharField()
    size_label = serializers.CharField()
    quantity = serializers.IntegerField()
    total_sqft = serializers.DecimalField(max_digits=12, decimal_places=2)
    finishing = serializers.CharField()
    addons = serializers.SerializerMethodField()

    def get_addons(self, obj) -> list[str]:
        return [a.name for a in obj.addons.all()]


class JobSerializer(serializers.ModelSerializer):
    order_id = serializers.IntegerField(read_only=True)
    order_no = serializers.CharField(source="order.order_no", read_only=True)
    customer_name = serializers.CharField(source="order.customer.name", read_only=True)
    customer_phone = serializers.CharField(source="order.customer.phone", read_only=True)
    item = JobItemSerializer(source="order_item", read_only=True)
    stage_label = serializers.CharField(source="get_stage_display", read_only=True)
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    operator = UserRefSerializer(read_only=True, allow_null=True)
    is_overdue = serializers.SerializerMethodField()
    is_due_today = serializers.SerializerMethodField()
    needs_material = serializers.SerializerMethodField()
    allowed_stages = serializers.SerializerMethodField()

    class Meta:
        model = Job
        fields = [
            "id",
            "job_no",
            "order_id",
            "order_no",
            "customer_name",
            "customer_phone",
            "item",
            "stage",
            "stage_label",
            "priority",
            "priority_label",
            "deadline",
            "is_overdue",
            "is_due_today",
            "operator",
            "design_file_ref",
            "notes",
            "material_recorded",
            "needs_material",
            "stage_changed_at",
            "allowed_stages",
            "created_at",
        ]

    def _open(self, obj: Job) -> bool:
        return obj.stage not in (Stage.DELIVERED, Stage.CANCELLED, Stage.READY)

    def get_is_overdue(self, obj: Job) -> bool:
        return bool(obj.deadline and self._open(obj) and obj.deadline < timezone.now())

    def get_is_due_today(self, obj: Job) -> bool:
        if not obj.deadline or not self._open(obj):
            return False
        return (
            timezone.localdate(obj.deadline) == timezone.localdate()
            and obj.deadline >= timezone.now()
        )

    def get_needs_material(self, obj: Job) -> bool:
        return obj.order_item.media_type.material_id is not None and not obj.material_recorded

    def get_allowed_stages(self, obj: Job) -> list[int]:
        request = self.context.get("request")
        return allowed_targets(request.user, obj) if request else []


class JobEventSerializer(serializers.ModelSerializer):
    from_label = serializers.SerializerMethodField()
    to_label = serializers.CharField(source="get_to_stage_display", read_only=True)
    created_by = UserRefSerializer(read_only=True, allow_null=True)

    class Meta:
        model = JobStageEvent
        fields = [
            "id",
            "from_stage",
            "from_label",
            "to_stage",
            "to_label",
            "note",
            "created_by",
            "created_at",
        ]

    def get_from_label(self, obj) -> str | None:
        return obj.get_from_stage_display() if obj.from_stage is not None else None


class JobMovementSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    movement_type = serializers.CharField()
    movement_type_label = serializers.CharField(source="get_movement_type_display")
    quantity = serializers.DecimalField(max_digits=12, decimal_places=2)
    roll_code = serializers.CharField(source="roll.code", default=None)
    reason = serializers.CharField()
    created_by = UserRefSerializer()
    created_at = serializers.DateTimeField()


class JobDetailSerializer(JobSerializer):
    events = JobEventSerializer(many=True, read_only=True)
    movements = serializers.SerializerMethodField()

    class Meta(JobSerializer.Meta):
        fields = [*JobSerializer.Meta.fields, "events", "movements"]

    @extend_schema_field(JobMovementSerializer(many=True))
    def get_movements(self, obj: Job) -> list[dict]:
        qs = obj.stock_movements.select_related("roll", "created_by").order_by("created_at")
        return JobMovementSerializer(qs, many=True).data


class JobUpdateSerializer(serializers.ModelSerializer):
    operator = StaffField(
        queryset=User.objects.filter(is_active=True, role=Role.OPERATOR),
        allow_null=True,
        required=False,
    )
    priority = serializers.ChoiceField(choices=Priority.choices, required=False)

    class Meta:
        model = Job
        fields = ["operator", "deadline", "priority", "design_file_ref", "notes"]


class MaterialInputSerializer(serializers.Serializer):
    roll = serializers.PrimaryKeyRelatedField(queryset=Roll.objects.all())
    used_sqft = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"))
    wastage_sqft = serializers.DecimalField(
        max_digits=10, decimal_places=2, min_value=Decimal("0"), default=Decimal("0")
    )
    wastage_reason = serializers.CharField(
        max_length=255, required=False, allow_blank=True, default=""
    )


class MoveJobSerializer(serializers.Serializer):
    to_stage = serializers.ChoiceField(
        choices=[c for c in Stage.choices if c[0] != Stage.CANCELLED]
    )
    note = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    material = MaterialInputSerializer(required=False, allow_null=True)
    skip_material = serializers.BooleanField(default=False)


class MoveResultSerializer(serializers.Serializer):
    job = JobSerializer()
    warnings = serializers.ListField(child=serializers.CharField())


class RollOptionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    width_ft = serializers.DecimalField(max_digits=6, decimal_places=2)
    remaining_sqft = serializers.DecimalField(max_digits=10, decimal_places=2)
    fits = serializers.BooleanField()


class MaterialOptionsSerializer(serializers.Serializer):
    stock_item_id = serializers.IntegerField(allow_null=True)
    stock_item_name = serializers.CharField(allow_null=True)
    default_used_sqft = serializers.DecimalField(max_digits=10, decimal_places=2)
    material_recorded = serializers.BooleanField()
    rolls = RollOptionSerializer(many=True)


class BoardColumnSerializer(serializers.Serializer):
    stage = serializers.IntegerField()
    label = serializers.CharField()
    count = serializers.IntegerField()
    jobs = JobSerializer(many=True)


class BoardSerializer(serializers.Serializer):
    columns = BoardColumnSerializer(many=True)
    total_open = serializers.IntegerField()
    overdue = serializers.IntegerField()
    due_today = serializers.IntegerField()
