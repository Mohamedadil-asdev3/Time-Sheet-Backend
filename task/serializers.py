# serializers.py
from rest_framework import serializers
from .models import TaskList, TaskListAuditLog, Status
from django.utils import timezone


class TaskListAuditLogSerializer(serializers.ModelSerializer):
    performed_by_username = serializers.CharField(source='performed_by.username', read_only=True)
    
    class Meta:
        model = TaskListAuditLog
        fields = [
            'id', 'action', 'performed_by', 'performed_by_username',
            'old_values', 'new_values', 'remarks', 'created_at','l1_action_at',
            'l1_action_by','l1_status','l2_action_at','l2_action_by','l2_status',
            'l1_rejected_at','l2_rejected_at'
            
        ]
        read_only_fields = fields


class TaskListSerializer(serializers.ModelSerializer):
    platform_name = serializers.CharField(source='platform.name', read_only=True)
    task_name     = serializers.CharField(source='task.name', read_only=True)
    subtask_name  = serializers.CharField(source='subtask.name', read_only=True)
    status_name   = serializers.CharField(source='status.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    l1_approver_name   = serializers.CharField(source='l1_approver.username', read_only=True, allow_null=True)
    l2_approver_name   = serializers.CharField(source='l2_approver.username', read_only=True, allow_null=True)
    last_modified_by_name = serializers.CharField(source='last_modified_by.username', read_only=True, allow_null=True)

    is_draft      = serializers.BooleanField(read_only=True)
    is_in_progress = serializers.BooleanField(read_only=True)
    is_completed  = serializers.BooleanField(read_only=True)

    # Approval action fields (write-only)
    action  = serializers.CharField(write_only=True, required=False)
    remarks = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = TaskList
        fields = [
            'id', 'date', 'user', 'user_username',
            'platform', 'platform_name',
            'task', 'task_name',
            'subtask', 'subtask_name',
            'bitrix_id', 'duration', 'description',
            'status', 'status_name',
            'l1_approver', 'l1_approver_name', 'l1_approved_at',
            'l2_approver', 'l2_approver_name', 'l2_approved_at',
            'last_modified_by', 'last_modified_by_name',
            'is_draft', 'is_in_progress', 'is_completed',
            'action', 'remarks',
            'created_at', 'updated_at',
        ]

        read_only_fields = [
            'id', 'user', 'user_username', 'created_at', 'updated_at',
            'platform_name', 'task_name', 'subtask_name', 'status_name',
            'l1_approver_name', 'l2_approver_name', 'last_modified_by_name',
            'l1_approved_at', 'l2_approved_at',
            'is_draft', 'is_in_progress', 'is_completed','status',
            'l1_approver', 'l2_approver','l1_rejected_at','l2_rejected_at'
        ]

    def validate(self, data):
        task    = data.get('task')
        subtask = data.get('subtask')
        if subtask and task and subtask.task_id != task.id:
            raise serializers.ValidationError({
                "subtask": "Selected subtask does not belong to selected task"
            })
        return data

    def create(self, validated_data):
        request = self.context['request']
        creator = request.user

        validated_data['user'] = creator
        validated_data['last_modified_by'] = creator

        if creator.first_level_manager:
            validated_data['l1_approver'] = creator.first_level_manager

        if creator.second_level_manager:
            validated_data['l2_approver'] = creator.second_level_manager

        if 'status' not in validated_data:
            draft = Status.objects.filter(name__iexact='draft').first()
            if draft:
                validated_data['status'] = draft

        return super().create(validated_data)
    def update(self, instance, validated_data):
        action = validated_data.pop('action', None)
        remarks = validated_data.pop('remarks', '')

        # 🚫 BLOCK frontend from changing status directly
        validated_data.pop('status', None)

        updated_instance = super().update(instance, validated_data)

        # Logging
        if action in ['L1_APPROVE', 'L2_APPROVE']:
            log_action = f"{action} - Approved"
        else:
            log_action = 'UPDATE'

        self._log_action(updated_instance, log_action, remarks)

        return updated_instance

    def _log_action(self, instance, action, remarks):
        request = self.context.get('request')
        if request:
            old_status = instance.status.name if instance.status else None
            TaskListAuditLog.objects.create(
                task=instance,
                action=action,
                performed_by=request.user,
                remarks=remarks,
                old_values={'status': old_status},
                new_values={'status': instance.status.name if instance.status else None}
            )