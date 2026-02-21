# models.py - Update the properties
from django.db import models
from django.conf import settings
from master.models import Platform, Status, Task, SubTask
from users.models import User
from django.utils import timezone


class BaseModel(models.Model):
    created_by = models.IntegerField()
    modified_by = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        abstract = True


class TaskList(models.Model):
    date = models.DateField()

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="created_tasks",
        db_index=True,
    )

    platform = models.ForeignKey(Platform, on_delete=models.CASCADE)

    task = models.ForeignKey(
        Task,
        on_delete=models.PROTECT,
        related_name="task_entries",
    )

    subtask = models.ForeignKey(
        SubTask,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="subtask_entries",
    )

    bitrix_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        db_index=True,
        help_text="External Bitrix ID"
    )

    duration = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=0,
        help_text="Hours spent (e.g. 4.50)"
    )

    description = models.TextField(blank=True, null=True)

    status = models.ForeignKey(
        Status,
        on_delete=models.PROTECT,
        related_name="task_entries",
    )
    
    # New fields for approval workflow
    l1_approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="l1_approved_tasks",
        help_text="Level 1 Approver"
    )
    
    l2_approver = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="l2_approved_tasks",
        help_text="Level 2 Approver"
    )
    
    l1_approved_at = models.DateTimeField(null=True, blank=True)
    l2_approved_at = models.DateTimeField(null=True, blank=True)
    
    # Track who last modified (for non-draft statuses)
    last_modified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="modified_tasks"
    )

    created_at = models.DateTimeField(default=timezone.now, editable=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "task_list"
        ordering = ["-date", "task__name"]
        indexes = [
            models.Index(fields=["user", "date"]),
            models.Index(fields=["platform", "status"]),
            models.Index(fields=["bitrix_id"]),
            models.Index(fields=["user", "status"]),
            models.Index(fields=["l1_approver", "status"]),
            models.Index(fields=["l2_approver", "status"]),
        ]

    def __str__(self):
        subtask_part = f" → {self.subtask.name}" if self.subtask else ""
        return f"{self.user.username} – {self.task.name}{subtask_part} ({self.date}) [{self.status.name}]"
    
    @property
    def is_draft(self):
        return self.status.name.lower() == 'draft' if self.status else False
    
    @property
    def is_in_progress(self):
        return self.status.name.lower() in ['inprogress', 'in progress'] if self.status else False
    
    @property
    def is_completed(self):
        return self.status.name.lower() in ['completed', 'done', 'finished'] if self.status else False
    
    def get_status_lower(self):
        """Helper method to get lowercase status name"""
        return self.status.name.lower() if self.status else None


class TaskListAuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('L1_APPROVE', 'L1 Approval'),
        ('L2_APPROVE', 'L2 Approval'),
        ('STATUS_CHANGE', 'Status Change'),
    ]
    
    task = models.ForeignKey(
        TaskList,
        on_delete=models.CASCADE,
        related_name="audit_logs"
    )
    
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    
    performed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="task_audit_actions"
    )
    
    old_values = models.JSONField(null=True, blank=True)
    new_values = models.JSONField(null=True, blank=True)
    
    remarks = models.TextField(blank=True, null=True)
    
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = "task_list_audit_log"
        ordering = ["-created_at"]
    
    def __str__(self):
        return f"{self.task.id} - {self.action} by {self.performed_by.username if self.performed_by else 'System'}"