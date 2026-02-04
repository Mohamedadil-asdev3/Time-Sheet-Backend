from rest_framework import serializers
from .models import Entity, Department, Location, Task, SubTask, Role, Platform, Status,Holiday,EmailTemplate


class EntitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Entity
        fields = "__all__"


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = "__all__"


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = "__all__"


class TaskSerializer(serializers.ModelSerializer):
    class Meta:
        model = Task
        fields = "__all__"


# class SubTaskSerializer(serializers.ModelSerializer):
#     class Meta:
#         model = SubTask
#         fields = "__all__"
class SubTaskSerializer(serializers.ModelSerializer):
    task_id = serializers.PrimaryKeyRelatedField(
        queryset=Task.objects.filter(is_active=True),
        source='task'
    )

    class Meta:
        model = SubTask
        fields = [
            'id',
            'task_id',
            'name',
            'description',
            'displayName',
            'created_by',
            'modified_by',
            'created_at',
            'updated_at',
            'is_active'
        ]

class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = "__all__"

class PlatformSerializer(serializers.ModelSerializer):
    class Meta:
        model = Platform
        fields = "__all__"


class StatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Status
        fields = "__all__"
        
class HolidaySerializer(serializers.ModelSerializer):
    entity_names = serializers.ReadOnlyField()
    department_name = serializers.CharField(
        source='department.name', read_only=True
    )
    location_name = serializers.CharField(
        source='location.name', read_only=True
    )

    class Meta:
        model = Holiday
        fields = [
            'id',
            'entity_ids',
            'entity_names',
            'department',
            'department_name',
            'location',
            'location_name',
            'name',
            'date',
            'description',
            'status',
            'code',
            'created_on',
            'created_by',
            'created_ip',
            'modified_on',
            'modified_by',
            'modified_ip',
        ]

        # 🔑 IMPORTANT
        read_only_fields = [
            'created_on',
            'created_by',
            'created_ip',
            'modified_on',
            'modified_by',
            'modified_ip',
        ]

    def validate_department(self, value):
        if value is None:
            return value
        if not Department.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Invalid department ID")
        return value

    def validate_location(self, value):
        if value is None:
            return value
        if not Location.objects.filter(id=value.id).exists():
            raise serializers.ValidationError("Invalid location ID")
        return value

class EmailTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmailTemplate
        fields = '__all__'