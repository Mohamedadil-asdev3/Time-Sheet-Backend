# serializers.py
from rest_framework import serializers
from .models import TaskList, Platform, Task, SubTask, Status


class TaskListSerializer(serializers.ModelSerializer):
    platform_name = serializers.CharField(source='platform.name', read_only=True)
    task_name     = serializers.CharField(source='task.name', read_only=True)
    subtask_name  = serializers.CharField(
        source='subtask.name',
        read_only=True,
        allow_null=True
    )
    status_name   = serializers.CharField(source='status.name', read_only=True)
    user_username = serializers.CharField(source='user.firstname', read_only=True)

    class Meta:
        model = TaskList
        fields = [
            'id',
            'date',
            'user',           'user_username',
            'platform',       'platform_name',
            'task',           'task_name',
            'subtask',        'subtask_name',
            'bitrix_id',
            'duration',
            'description',
            'status',         'status_name',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'user',
            'user_username',
            'created_at',
            'updated_at',
            'platform_name',
            'task_name',
            'subtask_name',
            'status_name',
        ]

    def validate(self, data):
        task = data.get('task')
        subtask = data.get('subtask')

        # ✅ SubTask must belong to Task (THIS relationship exists)
        if subtask and subtask.task_id != task.id:
            raise serializers.ValidationError({
                "subtask": "Selected subtask does not belong to the chosen task"
            })

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user

        if 'status' not in validated_data:
            default_status = Status.objects.filter(
                code__in=['draft', 'pending']
            ).first()
            if default_status:
                validated_data['status'] = default_status

        return super().create(validated_data)
