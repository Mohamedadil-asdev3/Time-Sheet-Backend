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
            'old_values', 'new_values', 'remarks', 'created_at'
        ]
        read_only_fields = fields


class TaskListSerializer(serializers.ModelSerializer):
    platform_name = serializers.CharField(source='platform.name', read_only=True)
    task_name = serializers.CharField(source='task.name', read_only=True)
    subtask_name = serializers.CharField(source='subtask.name', read_only=True)
    status_name = serializers.CharField(source='status.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    l1_approver_name = serializers.CharField(source='l1_approver.username', read_only=True)
    l2_approver_name = serializers.CharField(source='l2_approver.username', read_only=True)
    last_modified_by_name = serializers.CharField(source='last_modified_by.username', read_only=True)
    
    is_draft = serializers.BooleanField(read_only=True)
    is_in_progress = serializers.BooleanField(read_only=True)
    is_completed = serializers.BooleanField(read_only=True)
    
    # For approval actions
    action = serializers.CharField(write_only=True, required=False)
    remarks = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = TaskList
        fields = [
            'id',
            'date',
            'user', 'user_username',
            'platform', 'platform_name',
            'task', 'task_name',
            'subtask', 'subtask_name',
            'bitrix_id',
            'duration',
            'description',
            'status', 'status_name',
            'l1_approver', 'l1_approver_name', 'l1_approved_at',
            'l2_approver', 'l2_approver_name', 'l2_approved_at',
            'last_modified_by', 'last_modified_by_name',
            'is_draft', 'is_in_progress', 'is_completed',
            'action', 'remarks',  # For approval actions
            'created_at',
            'updated_at',
        ]
        
        read_only_fields = [
            'id', 'user', 'user_username', 'created_at', 'updated_at',
            'platform_name', 'task_name', 'subtask_name', 'status_name',
            'l1_approver_name', 'l2_approver_name',
            'last_modified_by_name', 'l1_approved_at', 'l2_approved_at',
            'is_draft', 'is_in_progress', 'is_completed',
        ]

    def validate(self, data):
        task = data.get('task')
        subtask = data.get('subtask')

        if subtask and task and subtask.task_id != task.id:
            raise serializers.ValidationError({
                "subtask": "Selected subtask does not belong to selected task"
            })
        
        # Check if user is trying to change status when not allowed
        request = self.context.get('request')
        instance = self.instance
        
        if instance and 'status' in data:
            current_status_name = instance.status.name.lower() if instance.status else None
            new_status = data['status']
            new_status_name = new_status.name.lower() if hasattr(new_status, 'name') else None
            
            # For L1/L2 approvers, they can only change to specific statuses
            if request and hasattr(request, 'user'):
                user = request.user
                
                # L1 Approver can only change from DRAFT to IN_PROGRESS
                if user.groups.filter(name='L1_Approver').exists():
                    if current_status_name != 'draft' or new_status_name not in ['inprogress', 'in progress']:
                        raise serializers.ValidationError({
                            "status": "L1 approvers can only change status from Draft to In Progress"
                        })
                
                # L2 Approver can only change from IN_PROGRESS to COMPLETED
                elif user.groups.filter(name='L2_Approver').exists():
                    if current_status_name not in ['inprogress', 'in progress'] or new_status_name not in ['completed', 'done']:
                        raise serializers.ValidationError({
                            "status": "L2 approvers can only change status from In Progress to Completed"
                        })

        return data

    def create(self, validated_data):
        validated_data['user'] = self.context['request'].user

        if 'status' not in validated_data:
            # Look for draft status with different possible names
            draft_status = Status.objects.filter(
                name__iexact='draft'
            ).first()
            if draft_status:
                validated_data['status'] = draft_status

        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        action = validated_data.pop('action', None)
        remarks = validated_data.pop('remarks', None)
        
        # Call parent update method
        updated_instance = super().update(instance, validated_data)
        
        # Log the update if it's an approval action
        if action in ['L1_APPROVE', 'L2_APPROVE']:
            self._log_approval_action(instance, action, remarks)
        
        return updated_instance
    
    def _log_approval_action(self, instance, action, remarks):
        request = self.context.get('request')
        if request:
            TaskListAuditLog.objects.create(
                task=instance,
                action=action,
                performed_by=request.user,
                remarks=remarks,
                old_values={},
                new_values={'status': instance.status.name if instance.status else None}
            )