from rest_framework import serializers
from .models import Entity, Department, Location, Task, SubTask, Role, Platform, Status


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